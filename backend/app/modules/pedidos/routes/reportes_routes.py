from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime

from app.modules.pedidos.services import reportes_services
from app.core.security import verificar_token, require_permission

router = APIRouter(prefix='/api/reportes', tags=["Reportes Bajo Demanda W33"])

@router.get('/ventas')
def reporte_ventas(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha final YYYY-MM-DD"),
    id_sucursal: Optional[int] = Query(None, description="ID de sucursal específica"),
    estado: Optional[str] = Query(None, description="Estado de venta: COMPLETADA, PENDIENTE, ANULADA"),
    id_metodo_pago: Optional[int] = Query(None, description="Filtrar por método de pago"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por empresa / tenant"),
    formato: str = Query('json', description="Formato de salida: 'json' o 'pdf'"),
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera el reporte de ventas bajo demanda con filtros dinámicos.
    Soporta visualización JSON para frontend y descarga directa en PDF con ReportLab.
    """
    try:
        fmt = formato.lower().strip()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt == 'pdf':
            pdf_buffer = reportes_services.generar_pdf_reporte_ventas(
                token_data, id_sucursal, fecha_inicio, fecha_fin, estado, id_metodo_pago, id_empresa
            )
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=reporte_ventas_{ts}.pdf"}
            )
        elif fmt == 'csv':
            csv_buffer = reportes_services.generar_csv_reporte_ventas(
                token_data, id_sucursal, fecha_inicio, fecha_fin, estado, id_metodo_pago, id_empresa
            )
            return StreamingResponse(
                csv_buffer,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename=reporte_ventas_{ts}.csv"}
            )
        elif fmt == 'xlsx':
            xlsx_buffer = reportes_services.generar_xlsx_reporte_ventas(
                token_data, id_sucursal, fecha_inicio, fecha_fin, estado, id_metodo_pago, id_empresa
            )
            return StreamingResponse(
                xlsx_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=reporte_ventas_{ts}.xlsx"}
            )
        else:
            return reportes_services.generar_reporte_ventas(
                token_data, id_sucursal, fecha_inicio, fecha_fin, estado, id_metodo_pago, id_empresa
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando reporte de ventas: {str(e)}")


@router.get('/inventario')
def reporte_inventario(
    id_sucursal: Optional[int] = Query(None, description="ID de sucursal específica"),
    id_categoria: Optional[int] = Query(None, description="Filtrar por categoría"),
    estado_stock: Optional[str] = Query(None, description="Estado de existencias: 'todos', 'bajo', 'agotado', 'disponible'"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por empresa / tenant"),
    formato: str = Query('json', description="Formato de salida: 'json' o 'pdf'"),
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera el reporte de inventario y existencias por almacén/sucursal.
    """
    try:
        fmt = formato.lower().strip()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt == 'pdf':
            pdf_buffer = reportes_services.generar_pdf_reporte_inventario(
                token_data, id_sucursal, id_categoria, estado_stock, id_empresa
            )
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=reporte_inventario_{ts}.pdf"}
            )
        elif fmt == 'csv':
            csv_buffer = reportes_services.generar_csv_reporte_inventario(
                token_data, id_sucursal, id_categoria, estado_stock, id_empresa
            )
            return StreamingResponse(
                csv_buffer,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename=reporte_inventario_{ts}.csv"}
            )
        elif fmt == 'xlsx':
            xlsx_buffer = reportes_services.generar_xlsx_reporte_inventario(
                token_data, id_sucursal, id_categoria, estado_stock, id_empresa
            )
            return StreamingResponse(
                xlsx_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=reporte_inventario_{ts}.xlsx"}
            )
        else:
            return reportes_services.generar_reporte_inventario(
                token_data, id_sucursal, id_categoria, estado_stock, id_empresa
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando reporte de inventario: {str(e)}")


@router.get('/productos-vendidos')
def reporte_productos_vendidos(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha final YYYY-MM-DD"),
    id_sucursal: Optional[int] = Query(None, description="ID de sucursal específica"),
    id_categoria: Optional[int] = Query(None, description="Filtrar por categoría"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por empresa / tenant"),
    formato: str = Query('json', description="Formato de salida: 'json' o 'pdf'"),
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera el reporte de productos más vendidos, unidades y recaudación generada.
    """
    try:
        fmt = formato.lower().strip()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt == 'pdf':
            pdf_buffer = reportes_services.generar_pdf_reporte_productos_vendidos(
                token_data, id_sucursal, id_categoria, fecha_inicio, fecha_fin, id_empresa
            )
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=reporte_productos_vendidos_{ts}.pdf"}
            )
        elif fmt == 'csv':
            csv_buffer = reportes_services.generar_csv_reporte_productos_vendidos(
                token_data, id_sucursal, id_categoria, fecha_inicio, fecha_fin, id_empresa
            )
            return StreamingResponse(
                csv_buffer,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename=reporte_productos_vendidos_{ts}.csv"}
            )
        elif fmt == 'xlsx':
            xlsx_buffer = reportes_services.generar_xlsx_reporte_productos_vendidos(
                token_data, id_sucursal, id_categoria, fecha_inicio, fecha_fin, id_empresa
            )
            return StreamingResponse(
                xlsx_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=reporte_productos_vendidos_{ts}.xlsx"}
            )
        else:
            return reportes_services.generar_reporte_productos_vendidos(
                token_data, id_sucursal, id_categoria, fecha_inicio, fecha_fin, id_empresa
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando reporte de productos: {str(e)}")


@router.get('/sucursales')
def reporte_sucursales(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha final YYYY-MM-DD"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por empresa / tenant"),
    formato: str = Query('json', description="Formato de salida: 'json' o 'pdf'"),
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera el reporte comparativo entre sucursales de la empresa.
    """
    try:
        fmt = formato.lower().strip()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt == 'pdf':
            pdf_buffer = reportes_services.generar_pdf_reporte_sucursales(
                token_data, fecha_inicio, fecha_fin, id_empresa
            )
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=reporte_sucursales_{ts}.pdf"}
            )
        elif fmt == 'csv':
            csv_buffer = reportes_services.generar_csv_reporte_sucursales(
                token_data, fecha_inicio, fecha_fin, id_empresa
            )
            return StreamingResponse(
                csv_buffer,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename=reporte_sucursales_{ts}.csv"}
            )
        elif fmt == 'xlsx':
            xlsx_buffer = reportes_services.generar_xlsx_reporte_sucursales(
                token_data, fecha_inicio, fecha_fin, id_empresa
            )
            return StreamingResponse(
                xlsx_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=reporte_sucursales_{ts}.xlsx"}
            )
        else:
            return reportes_services.generar_reporte_sucursales(
                token_data, fecha_inicio, fecha_fin, id_empresa
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando reporte de sucursales: {str(e)}")


@router.get('/valoraciones')
def reporte_valoraciones(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha final YYYY-MM-DD"),
    id_sucursal: Optional[int] = Query(None, description="ID de sucursal específica"),
    puntuacion: Optional[int] = Query(None, ge=1, le=5, description="Filtrar por estrellas (1 a 5)"),
    requiere_revision: Optional[bool] = Query(None, description="Filtrar solo alertas críticas (1★ o a revisar)"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por empresa / tenant"),
    formato: str = Query('json', description="Formato de salida: 'json', 'pdf', 'csv' o 'xlsx'"),
    token_data: dict = Depends(require_permission('reportes.ver'))
):
    """
    Genera el reporte de satisfacción, opiniones y valoraciones de clientes bajo demanda.
    Soporta visualización JSON, PDF, CSV y XLSX.
    """
    try:
        fmt = formato.lower().strip()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt == 'pdf':
            pdf_buffer = reportes_services.generar_pdf_reporte_valoraciones(
                token_data, id_sucursal, fecha_inicio, fecha_fin, puntuacion, requiere_revision, id_empresa
            )
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=reporte_valoraciones_{ts}.pdf"}
            )
        elif fmt == 'csv':
            csv_buffer = reportes_services.generar_csv_reporte_valoraciones(
                token_data, id_sucursal, fecha_inicio, fecha_fin, puntuacion, requiere_revision, id_empresa
            )
            return StreamingResponse(
                csv_buffer,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename=reporte_valoraciones_{ts}.csv"}
            )
        elif fmt == 'xlsx':
            xlsx_buffer = reportes_services.generar_xlsx_reporte_valoraciones(
                token_data, id_sucursal, fecha_inicio, fecha_fin, puntuacion, requiere_revision, id_empresa
            )
            return StreamingResponse(
                xlsx_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=reporte_valoraciones_{ts}.xlsx"}
            )
        else:
            return reportes_services.generar_reporte_valoraciones(
                token_data, id_sucursal, fecha_inicio, fecha_fin, puntuacion, requiere_revision, id_empresa
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando reporte de valoraciones: {str(e)}")

