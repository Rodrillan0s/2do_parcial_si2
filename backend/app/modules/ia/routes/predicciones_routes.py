from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.core.security import verificar_token, tiene_permiso
from app.core.tenant_guard import resolver_tenant_operacion, resolver_sucursal_autorizada, obtener_alcance_usuario
from app.modules.ia.services import demanda_forecast_services

router = APIRouter(prefix="/api/ia/predicciones", tags=["CU23W — Predicciones de Demanda y Reposición IA"])

class BacktestingEvalIn(BaseModel):
    id_empresa: Optional[int] = Field(None, description="Filtrar por empresa / tenant")
    id_sucursal: Optional[int] = Field(None, description="Filtrar por sucursal")
    id_producto: Optional[int] = Field(None, description="Filtrar por prenda específica")
    dias_test: int = Field(14, ge=3, le=60, description="Días de backtesting para partición de prueba")


def _validar_permisos_ia(token_data: dict, id_empresa_param: Optional[int] = None, id_sucursal_param: Optional[int] = None):
    alcance = obtener_alcance_usuario(token_data)
    if alcance == "CLIENTE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Las predicciones analíticas son de uso administrativo."
        )
    
    roles = {str(r).upper() for r in token_data.get("roles", [])}
    roles.add(str(token_data.get("nombre_rol") or token_data.get("rol") or "").upper())
    
    tiene_perm = (
        "ia.recomendar" in token_data.get("permisos", []) or
        "reportes.ver" in token_data.get("permisos", []) or
        tiene_permiso(token_data, "ia.recomendar") or
        tiene_permiso(token_data, "reportes.ver") or
        tiene_permiso(token_data, "admin.acceder") or
        bool(roles.intersection({"ADMINISTRADOR", "ADMIN_EMPRESA", "ADMINISTRADOR_TIENDA", "SUPERADMIN", "ENCARGADO_SUCURSAL", "ENCARGADO"}))
    )
    if not tiene_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permisos para consultar predicciones de demanda."
        )

    # Si no se especificó id_empresa pero sí id_sucursal, deducir la empresa correspondiente
    if not id_empresa_param and id_sucursal_param:
        from app.core.postgres import PostgreSQL
        from app.core.config import Config
        db = PostgreSQL()
        db.create_connection()
        try:
            schema = Config.SCHEMA or 'comercio'
            row = db.execute_query(
                f"SELECT id_empresa FROM {schema}.t_sucursal WHERE id_sucursal = %s;",
                (id_sucursal_param,),
                fetchone=True
            )
            if row and row[0]:
                id_empresa_param = int(row[0])
        finally:
            db.close_connection()

    # Si aún no hay empresa y el usuario es Administrador Global, resolver el primer tenant activo
    from app.core.tenant_guard import es_administrador_global
    if not id_empresa_param and es_administrador_global(token_data):
        from app.core.postgres import PostgreSQL
        from app.core.config import Config
        db = PostgreSQL()
        db.create_connection()
        try:
            schema = Config.SCHEMA or 'comercio'
            row = db.execute_query(
                f"SELECT id_empresa FROM {schema}.empresa WHERE estado = 'ACTIVO' ORDER BY id_empresa LIMIT 1;",
                fetchone=True
            )
            if row and row[0]:
                id_empresa_param = int(row[0])
        finally:
            db.close_connection()
        
    empresa = resolver_tenant_operacion(token_data, id_empresa_param, permitir_global=False)
    sucursal = resolver_sucursal_autorizada(token_data, id_sucursal_param)
    
    # Validar que si se indicó sucursal, efectivamente pertenezca a la empresa resuelta
    if sucursal and empresa:
        from app.core.postgres import PostgreSQL
        from app.core.config import Config
        db = PostgreSQL()
        db.create_connection()
        try:
            schema = Config.SCHEMA or 'comercio'
            row = db.execute_query(
                f"SELECT id_empresa FROM {schema}.t_sucursal WHERE id_sucursal = %s;",
                (sucursal,),
                fetchone=True
            )
            if not row or int(row[0]) != int(empresa):
                sucursal = None  # No pertenece al tenant seleccionado; consolidar
        finally:
            db.close_connection()

    return empresa, sucursal


@router.get("/demanda", summary="Proyección de demanda e intervalos de confianza (CU23W)")
def proyeccion_demanda(
    id_empresa: Optional[int] = Query(None, description="ID del tenant a consultar"),
    id_sucursal: Optional[int] = Query(None, description="ID de sucursal específica"),
    id_producto: Optional[int] = Query(None, description="ID de producto específico"),
    dias_proyeccion: int = Query(14, ge=1, le=60, description="Días a proyectar en el futuro"),
    dias_historia: int = Query(60, ge=14, le=180, description="Días de historia a analizar"),
    token_data: dict = Depends(verificar_token)
):
    try:
        empresa_id, sucursal_id = _validar_permisos_ia(token_data, id_empresa, id_sucursal)
        serie = demanda_forecast_services.obtener_serie_temporal_ventas(
            id_empresa=empresa_id,
            id_sucursal=sucursal_id,
            id_producto=id_producto,
            dias_historia=dias_historia
        )
        forecast = demanda_forecast_services.predecir_demanda_serie(
            serie=serie,
            dias_proyeccion=dias_proyeccion
        )
        return {
            "success": True,
            "id_empresa": empresa_id,
            "id_sucursal": sucursal_id,
            "id_producto": id_producto,
            "dias_analizados": len(serie),
            "dias_proyectados": dias_proyeccion,
            **forecast
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculando proyección de demanda: {str(e)}"
        )


@router.get("/reposicion", summary="Recomendaciones de abastecimiento y riesgo de quiebre de stock (CU23W)")
def recomendaciones_reposicion(
    id_empresa: Optional[int] = Query(None, description="ID del tenant"),
    id_sucursal: Optional[int] = Query(None, description="ID de sucursal específica"),
    lead_time_dias: int = Query(7, ge=1, le=30, description="Días estimados de entrega de proveedores"),
    token_data: dict = Depends(verificar_token)
):
    try:
        empresa_id, sucursal_id = _validar_permisos_ia(token_data, id_empresa, id_sucursal)
        recomendaciones = demanda_forecast_services.calcular_recomendaciones_reposicion_db(
            id_empresa=empresa_id,
            id_sucursal=sucursal_id,
            lead_time_dias=lead_time_dias
        )
        
        # Resumen general de criticidad
        total_criticos = sum(1 for r in recomendaciones if r["riesgo_rotura"] == "CRITICO")
        total_altos = sum(1 for r in recomendaciones if r["riesgo_rotura"] == "ALTO")
        inversion_total_bs = sum(r["inversion_estimada_bs"] for r in recomendaciones)
        
        return {
            "success": True,
            "id_empresa": empresa_id,
            "id_sucursal": sucursal_id,
            "lead_time_dias": lead_time_dias,
            "total_prendas_analizadas": len(recomendaciones),
            "resumen": {
                "alertas_criticas": total_criticos,
                "alertas_altas": total_altos,
                "inversion_sugerida_bs": round(inversion_total_bs, 2)
            },
            "recomendaciones": recomendaciones
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo recomendaciones de reposición: {str(e)}"
        )


@router.post("/evaluar", summary="Backtesting temporal y evaluación de métricas MAE, RMSE, MAPE (CU23W)")
def evaluar_backtesting(
    payload: BacktestingEvalIn,
    token_data: dict = Depends(verificar_token)
):
    try:
        empresa_id, sucursal_id = _validar_permisos_ia(token_data, payload.id_empresa, payload.id_sucursal)
        serie = demanda_forecast_services.obtener_serie_temporal_ventas(
            id_empresa=empresa_id,
            id_sucursal=sucursal_id,
            id_producto=payload.id_producto,
            dias_historia=90
        )
        evaluacion = demanda_forecast_services.evaluar_backtesting_modelo(
            serie=serie,
            dias_test=payload.dias_test
        )
        return {
            "success": True,
            "id_empresa": empresa_id,
            "id_sucursal": sucursal_id,
            "id_producto": payload.id_producto,
            "evaluacion": evaluacion
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluando precisión del modelo: {str(e)}"
        )
