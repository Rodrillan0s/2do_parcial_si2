from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import verificar_token_opcional, verificar_token, require_permission, tiene_permiso
from app.core.tenant_guard import resolver_tenant_operacion
from app.modules.ia.services import ml_preferencias_services

router = APIRouter(prefix="/api/recomendaciones", tags=["Mini Machine Learning - Recomendaciones"])


@router.get("/mis-recomendaciones", summary="Obtener recomendaciones personalizadas por Machine Learning")
def obtener_mis_recomendaciones(
    limite: int = 6,
    id_empresa: Optional[int] = Query(None, description="ID opcional de empresa para visitantes"),
    token_data: Optional[dict] = Depends(verificar_token_opcional)
):
    """
    Retorna prendas sugeridas basadas en el aprendizaje automático de preferencias
    (categoría, talla, color, rango de precios) a partir de compras históricas del cliente.
    Si el usuario es anónimo o nuevo, devuelve la selección icónica de tendencia.
    """
    id_usuario = token_data.get("id_usuario") if token_data else None
    empresa_efectiva = (token_data.get("id_empresa") if token_data else None) or id_empresa or 1

    try:
        recomendaciones = ml_preferencias_services.obtener_recomendaciones_cliente(
            id_usuario=id_usuario,
            id_empresa=empresa_efectiva,
            limite=limite
        )
        return {
            "success": True,
            "total": len(recomendaciones),
            "personalizado": bool(id_usuario),
            "recomendaciones": recomendaciones
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo recomendaciones de Machine Learning: {str(e)}"
        )


@router.get("/cliente/{id_cliente}", summary="Consultar perfil de preferencias y recomendaciones de un cliente (Admin)")
def obtener_recomendaciones_por_cliente(
    id_cliente: int,
    limite: int = 8,
    id_empresa: Optional[int] = Query(None, description="Empresa si es admin global"),
    token_data: dict = Depends(verificar_token)
):
    """
    Permite al personal de boutique o administración consultar el perfil de afinidad
    y las recomendaciones generadas por el modelo para un cliente específico.
    """
    roles = {str(r).upper() for r in (token_data.get("roles") or [])}
    rol = str(token_data.get("nombre_rol") or token_data.get("rol") or "").upper()
    if rol:
        roles.add(rol)

    if not (tiene_permiso(token_data, "ia.recomendar") or tiene_permiso(token_data, "pos.vender") or bool(roles.intersection({"ADMINISTRADOR", "SUPERADMIN", "ADMINISTRADOR_TIENDA", "ENCARGADO_SUCURSAL", "CAJERO"}))):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes para consultar perfil de cliente.")

    try:
        id_empresa_efectiva = resolver_tenant_operacion(token_data, id_empresa, permitir_global=True) or 1
        resultado = ml_preferencias_services.aprender_preferencias_cliente(
            id_cliente=id_cliente,
            id_empresa=id_empresa_efectiva
        )
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluando perfil del cliente {id_cliente}: {str(e)}"
        )


@router.post("/entrenar", summary="Ejecutar re-entrenamiento global del modelo de preferencias (Admin)")
def reentrenar_modelo_global(
    id_empresa: Optional[int] = Query(None, description="Empresa si es admin global"),
    token_data: dict = Depends(verificar_token)
):
    """
    Dispara el entrenamiento completo del mini modelo de Machine Learning
    recorriendo todas las ventas y pedidos de la empresa para actualizar t_preferencia_cliente y t_recomendacion.
    """
    roles = {str(r).upper() for r in (token_data.get("roles") or [])}
    rol = str(token_data.get("nombre_rol") or token_data.get("rol") or "").upper()
    if rol:
        roles.add(rol)

    if not (tiene_permiso(token_data, "ia.entrenar") or bool(roles.intersection({"ADMINISTRADOR", "SUPERADMIN", "ADMINISTRADOR_TIENDA"}))):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso 'ia.entrenar' requerido.")

    try:
        id_empresa_efectiva = resolver_tenant_operacion(token_data, id_empresa)
        res = ml_preferencias_services.entrenar_modelo_todos_los_clientes(id_empresa=id_empresa_efectiva)
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en reentrenamiento del modelo: {str(e)}"
        )

