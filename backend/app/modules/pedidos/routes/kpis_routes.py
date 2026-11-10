from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from app.modules.pedidos.services import kpis_services
from app.core.security import verificar_token

router = APIRouter(prefix='/api/dashboard', tags=["Analítica y KPIs"])
kpis_router = APIRouter(prefix='/api/kpis', tags=["Indicadores Empresariales W32"])

# ==============================================================================
# COMPATIBILIDAD CON ENDPOINTS ANTERIORES
# ==============================================================================

@router.post('/etl/ejecutar')
def trigger_etl_process(token_data: dict = Depends(verificar_token)):
    """Puebla el Data Warehouse con los datos del día anterior."""
    try:
        return kpis_services.procesar_etl_diario(token_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/metricas')
def get_kpis_operacionales(
    id_empresa: Optional[int] = Query(None, description="Filtrar por empresa/tienda específica"),
    token_data: dict = Depends(verificar_token)
):
    """Retorna la analítica general o por empresa dependiendo del rol y parámetros del JWT."""
    try:
        return kpis_services.generar_dashboard(token_data, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al calcular métricas: {str(e)}")


@kpis_router.get('/tenants')
@router.get('/tenants')
def get_tenants_dashboard(token_data: dict = Depends(verificar_token)):
    """
    Retorna el catálogo de empresas / tiendas (tenants) con su resumen de sucursales,
    prendas activas, inventario disponible y ventas acumuladas.
    """
    try:
        return kpis_services.obtener_tenants_dashboard(token_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener listado de tiendas: {str(e)}")


# ==============================================================================
# W32 — ENDPOINTS ESPECÍFICOS DE INDICADORES EMPRESARIALES
# ==============================================================================

@kpis_router.get('/resumen')
@router.get('/resumen')
def get_kpis_resumen(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal específica"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tienda/tenant específico"),
    token_data: dict = Depends(verificar_token)
):
    """
    Retorna los KPIs ejecutivos consolidados: Ventas totales, ingresos, ticket promedio,
    variación respecto al período anterior y resumen de inventario físico.
    """
    try:
        return kpis_services.obtener_resumen_indicadores(token_data, fecha_inicio, fecha_fin, id_sucursal, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener resumen de KPIs: {str(e)}")


@kpis_router.get('/ventas')
@router.get('/ventas')
def get_kpis_ventas_timeline(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal específica"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tienda/tenant específico"),
    token_data: dict = Depends(verificar_token)
):
    """
    Retorna la serie temporal de ventas agregada por fecha para graficación reactiva.
    """
    try:
        return kpis_services.obtener_ventas_periodo(token_data, fecha_inicio, fecha_fin, id_sucursal, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener serie de ventas: {str(e)}")


@kpis_router.get('/productos-mas-vendidos')
@router.get('/productos-mas-vendidos')
def get_kpis_productos_mas_vendidos(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal específica"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tienda/tenant específico"),
    limit: int = Query(8, ge=1, le=50, description="Cantidad de productos en ranking"),
    token_data: dict = Depends(verificar_token)
):
    """
    Retorna los productos con mayor volumen de venta e ingresos generados.
    """
    try:
        return kpis_services.obtener_productos_mas_vendidos(token_data, fecha_inicio, fecha_fin, id_sucursal, limit, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener ranking de productos: {str(e)}")


@kpis_router.get('/inventario')
@router.get('/inventario')
def get_kpis_inventario(
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal específica"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tienda/tenant específico"),
    token_data: dict = Depends(verificar_token)
):
    """
    Retorna alertas de inventario crítico: productos con stock bajo o agotados.
    """
    try:
        return kpis_services.obtener_inventario_kpis(token_data, id_sucursal, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener KPIs de inventario: {str(e)}")


@kpis_router.get('/ventas-sucursal')
@router.get('/ventas-sucursal')
def get_kpis_ventas_sucursal(
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tienda/tenant específico"),
    token_data: dict = Depends(verificar_token)
):
    """
    Retorna la comparativa de ventas, ingresos y prendas vendidas entre sucursales de la empresa.
    """
    try:
        return kpis_services.obtener_ventas_sucursal(token_data, fecha_inicio, fecha_fin, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener ventas por sucursal: {str(e)}")


@kpis_router.get('/ranking-satisfaccion')
@router.get('/ranking-satisfaccion')
def get_kpis_ranking_satisfaccion(
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal específica"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tienda/tenant específico"),
    limit: int = Query(5, ge=1, le=20, description="Cantidad de prendas en ranking"),
    token_data: dict = Depends(verificar_token)
):
    """
    Retorna el ranking de prendas con mejor valoración de clientes.
    """
    try:
        return kpis_services.obtener_ranking_satisfaccion_prendas(token_data, id_sucursal, limit, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener ranking de satisfacción: {str(e)}")


@kpis_router.get('/alertas-calidad')
@router.get('/alertas-calidad')
def get_kpis_alertas_calidad(
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal específica"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tienda/tenant específico"),
    limit: int = Query(10, ge=1, le=50, description="Cantidad de alertas críticas"),
    token_data: dict = Depends(verificar_token)
):
    """
    Retorna valoraciones de 1 estrella o marcadas para revisión administrativa urgente.
    """
    try:
        return kpis_services.obtener_alertas_calidad_criticas(token_data, id_sucursal, limit, id_empresa)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al obtener alertas críticas de satisfacción: {str(e)}")
