import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import verificar_token, require_permission
from app.modules.pedidos.services.reports.engine.catalog import CATALOGO_REPORTES
from app.modules.pedidos.services.reports.parser.command_parser import interpretar_comando_reporte
from app.modules.pedidos.services.reports.engine.report_engine import (
    ejecutar_reporte_dinamico,
    generar_pdf_reporte_dinamico,
    generar_csv_reporte_dinamico,
    generar_xlsx_reporte_dinamico,
    _resolver_contexto_tenant
)

router = APIRouter(prefix="/api/motor-reportes", tags=["Motor de Reportes Dinámico"])


class ParseCommandIn(BaseModel):
    command: Optional[str] = Field(None, description="Comando en lenguaje natural")
    comando: Optional[str] = Field(None, description="Alias en español para el comando")
    id_empresa: Optional[int] = Field(None, gt=0)
    contexto: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Contexto opcional")

    def texto_comando(self) -> str:
        return (self.command or self.comando or "").strip()


class ReporteEjecucionIn(BaseModel):
    id_empresa: Optional[int] = Field(None, gt=0)
    tipo_reporte: str = Field(..., description="Código canónico del reporte (ej. ventas, inventario, etc.)")
    filtros: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Diccionario de filtros normalizados")
    groupBy: Optional[str] = Field(None, description="Campo para agrupación SQL")
    orderBy: Optional[str] = Field(None, description="Columna para ordenamiento")
    orderDirection: Optional[str] = Field("DESC", description="ASC o DESC")


def _contexto_reporte(payload, empresa):
    from app.core.tenant_guard import resolver_tenant_operacion, es_administrador_global
    from app.modules.saas.services.saas_services import exigir_vigencia

    # Para Administrador Global, si no se envió una empresa específica en el payload,
    # resolver automáticamente la primera empresa activa en lugar de arrojar error 400.
    if not empresa and es_administrador_global(payload):
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
            if row:
                empresa = row[0]
        finally:
            db.close_connection()

    empresa = resolver_tenant_operacion(payload, empresa)
    exigir_vigencia(empresa, reportes=True)
    return {**payload, '_empresa_reporte': empresa}


@router.get("/catalogo")
def obtener_catalogo_reportes(token_data: dict = Depends(require_permission('reportes.ver'))):
    """
    Retorna la lista de reportes disponibles en el motor, sus vistas,
    filtros permitidos, agrupaciones y metadatos de columnas.
    """
    try:
        return {
            "success": True,
            "total": len(CATALOGO_REPORTES),
            "catalogo": list(CATALOGO_REPORTES.values())
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo catálogo de reportes: {str(e)}"
        )


@router.post("/parse-command")
def parsear_comando_reporte(
    payload: ParseCommandIn,
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Interpreta un comando de voz o texto determinísticamente.
    Retorna un ReportRequest canónico y si existen ambigüedades.
    """
    try:
        empresa_req = payload.id_empresa or (payload.contexto or {}).get("id_empresa")
        token_data = _contexto_reporte(token_data, empresa_req)
        txt = payload.texto_comando()
        if not txt:
            raise ValueError("Debe ingresar o dictar un comando de texto.")

        id_empresa, _ = _resolver_contexto_tenant(token_data)
        resultado = interpretar_comando_reporte(txt, id_empresa=id_empresa)
        return {
            "success": True,
            **resultado
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interpretando comando: {str(e)}"
        )


@router.post("/ejecutar")
def ejecutar_reporte(
    payload: ReporteEjecucionIn,
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Ejecuta una consulta SQL parametrizada a través del motor de reportes dinámico.
    Garantiza aislamiento multi-tenant estricto según la empresa del usuario.
    """
    try:
        empresa_req = payload.id_empresa or (payload.filtros or {}).get("id_empresa")
        token_data = _contexto_reporte(token_data, empresa_req)
        req_dict = payload.model_dump()
        if empresa_req and not req_dict.get("id_empresa"):
            req_dict["id_empresa"] = empresa_req
        datos = ejecutar_reporte_dinamico(req_dict, token_data)
        return {
            "success": True,
            "data": datos
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando reporte dinámico: {str(e)}"
        )


@router.post("/exportar/pdf")
def exportar_reporte_pdf(
    payload: ReporteEjecucionIn,
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera y descarga en streaming un PDF profesional del reporte especificado.
    """
    try:
        empresa_req = payload.id_empresa or (payload.filtros or {}).get("id_empresa")
        token_data = _contexto_reporte(token_data, empresa_req)
        req_dict = payload.model_dump()
        if empresa_req and not req_dict.get("id_empresa"):
            req_dict["id_empresa"] = empresa_req
        datos = ejecutar_reporte_dinamico(req_dict, token_data)
        
        pdf_buffer = generar_pdf_reporte_dinamico(datos, token_data)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tipo = payload.tipo_reporte
        filename = f"reporte_{tipo}_{timestamp}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF del reporte: {str(e)}"
        )


@router.post("/exportar/csv")
def exportar_reporte_csv(
    payload: ReporteEjecucionIn,
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera y descarga en streaming un CSV delimitado por comas con codificación UTF-8 BOM.
    """
    try:
        empresa_req = payload.id_empresa or (payload.filtros or {}).get("id_empresa")
        token_data = _contexto_reporte(token_data, empresa_req)
        req_dict = payload.model_dump()
        if empresa_req and not req_dict.get("id_empresa"):
            req_dict["id_empresa"] = empresa_req
        datos = ejecutar_reporte_dinamico(req_dict, token_data)
        
        csv_buffer = generar_csv_reporte_dinamico(datos)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tipo = payload.tipo_reporte
        filename = f"reporte_{tipo}_{timestamp}.csv"

        return StreamingResponse(
            csv_buffer,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando CSV del reporte: {str(e)}"
        )


@router.post("/exportar/xlsx")
def exportar_reporte_xlsx(
    payload: ReporteEjecucionIn,
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera y descarga en streaming un archivo XLSX con formato institucional y resumen.
    """
    try:
        empresa_req = payload.id_empresa or (payload.filtros or {}).get("id_empresa")
        token_data = _contexto_reporte(token_data, empresa_req)
        req_dict = payload.model_dump()
        if empresa_req and not req_dict.get("id_empresa"):
            req_dict["id_empresa"] = empresa_req
        datos = ejecutar_reporte_dinamico(req_dict, token_data)
        
        xlsx_buffer = generar_xlsx_reporte_dinamico(datos)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tipo = payload.tipo_reporte
        filename = f"reporte_{tipo}_{timestamp}.xlsx"

        return StreamingResponse(
            xlsx_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando XLSX del reporte: {str(e)}"
        )
