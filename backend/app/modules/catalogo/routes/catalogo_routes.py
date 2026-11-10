import copy
import threading
import time
from typing import Dict, Optional
from fastapi import APIRouter, Query, HTTPException, status
from app.core.config import Config
from app.modules.catalogo.repos import catalogo_repos

router = APIRouter(prefix="/api/catalogo", tags=["Catálogo Público"])

_CATALOGO_META_LOCK = threading.Lock()
_CATALOGO_META_CACHE: Dict[tuple, tuple] = {}
_CATALOGO_META_TTL_S = 30.0


def invalidar_cache_catalogo_publico() -> None:
    with _CATALOGO_META_LOCK:
        _CATALOGO_META_CACHE.clear()


def _obtener_tenants_cached():
    schema = Config.SCHEMA or "comercio"
    key = ("tenants", schema)
    now = time.monotonic()
    with _CATALOGO_META_LOCK:
        entry = _CATALOGO_META_CACHE.get(key)
        if entry and entry[0] > now:
            return copy.deepcopy(entry[1])
    res = catalogo_repos.obtener_tenants_publicos()
    with _CATALOGO_META_LOCK:
        _CATALOGO_META_CACHE[key] = (time.monotonic() + _CATALOGO_META_TTL_S, copy.deepcopy(res))
    return res


def _obtener_info_tenant_cached(id_empresa: int):
    schema = Config.SCHEMA or "comercio"
    key = ("info_tenant", schema, int(id_empresa))
    now = time.monotonic()
    with _CATALOGO_META_LOCK:
        entry = _CATALOGO_META_CACHE.get(key)
        if entry and entry[0] > now:
            return copy.deepcopy(entry[1])
    res = catalogo_repos.obtener_info_tenant(id_empresa)
    with _CATALOGO_META_LOCK:
        _CATALOGO_META_CACHE[key] = (time.monotonic() + _CATALOGO_META_TTL_S, copy.deepcopy(res))
    return res


def _obtener_filtros_cached(id_empresa: int):
    schema = Config.SCHEMA or "comercio"
    key = ("filtros", schema, int(id_empresa))
    now = time.monotonic()
    with _CATALOGO_META_LOCK:
        entry = _CATALOGO_META_CACHE.get(key)
        if entry and entry[0] > now:
            return copy.deepcopy(entry[1])
    res = catalogo_repos.obtener_filtros_disponibles(id_empresa)
    with _CATALOGO_META_LOCK:
        _CATALOGO_META_CACHE[key] = (time.monotonic() + _CATALOGO_META_TTL_S, copy.deepcopy(res))
    return res


@router.get('/tenants', summary="Listar tiendas/marcas públicas activas")
def listar_tenants_publicos():
    """
    Lista las empresas/tiendas activas disponibles para que los visitantes
    puedan seleccionar la marca o tienda a explorar.
    """
    try:
        tenants = _obtener_tenants_cached()
        return {
            "success": True,
            "total": len(tenants),
            "data": tenants
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar tiendas activas: {str(e)}"
        )


@router.get('/tenant-by-slug/{slug}', summary="Resolver tienda activa por slug único")
def resolver_tenant_por_slug(slug: str):
    """
    Resuelve la tienda activa correspondiente al slug o subdominio.
    """
    try:
        info = catalogo_repos.obtener_info_tenant_por_slug(slug)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró una tienda activa con ese identificador."
            )
        filtros = _obtener_filtros_cached(info["id_empresa"])
        return {
            "success": True,
            "empresa": info,
            "filtros": filtros
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al resolver tienda por slug: {str(e)}"
        )


@router.get('/filtros', summary="Obtener filtros disponibles para el catálogo del Tenant")
def obtener_filtros_catalogo(
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    slug: Optional[str] = Query(None, description="Slug opcional del Tenant")
):
    """
    Retorna dinámicamente las categorías, públicos, sucursales, tallas, colores, temporadas y colecciones
    disponibles en el Tenant indicado. Si no se especifica, toma la primera tienda activa.
    """
    try:
        info_empresa = None
        if slug and slug.strip():
            info_empresa = catalogo_repos.obtener_info_tenant_por_slug(slug)
            if info_empresa:
                id_empresa = info_empresa["id_empresa"]

        if not id_empresa:
            tenants = _obtener_tenants_cached()
            if not tenants:
                return {
                    "success": True,
                    "empresa": None,
                    "data": {"categorias": [], "publicos": [], "sucursales": [], "tallas": [], "colores": [], "temporadas": [], "colecciones": []}
                }
            id_empresa = tenants[0]["id_empresa"]

        if not info_empresa:
            info_empresa = _obtener_info_tenant_cached(id_empresa)
        filtros = _obtener_filtros_cached(id_empresa)

        return {
            "success": True,
            "empresa": info_empresa,
            "data": filtros
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener filtros del catálogo: {str(e)}"
        )

@router.get('/productos', summary="Consultar productos activos del catálogo público")
def listar_productos_catalogo(
    id_empresa: Optional[int] = Query(None, description="ID del Tenant (empresa)"),
    slug: Optional[str] = Query(None, description="Slug opcional del Tenant"),
    busqueda: Optional[str] = Query(None, description="Buscar por nombre, código o marca"),
    id_categoria: Optional[int] = Query(None, description="Filtrar por categoría"),
    publico: Optional[str] = Query(None, description="Filtrar por público objetivo (Mujer, Hombre, Unisex, Niños, Niñas, Bebés)"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal con stock"),
    id_talla: Optional[int] = Query(None, description="Filtrar por talla disponible"),
    id_color: Optional[int] = Query(None, description="Filtrar por color disponible"),
    temporada: Optional[str] = Query(None, description="Filtrar por temporada"),
    coleccion: Optional[str] = Query(None, description="Filtrar por colección"),
    precio_min: Optional[float] = Query(None, ge=0, description="Precio mínimo"),
    precio_max: Optional[float] = Query(None, ge=0, description="Precio máximo"),
    orden: Optional[str] = Query("destacados", description="destacados | precio_asc | precio_desc | nombre_asc | nombre_desc | recientes"),
    limit: int = Query(50, ge=1, le=100, description="Cantidad por página"),
    offset: int = Query(0, ge=0, description="Desplazamiento")
):
    """
    Consulta pública de prendas activas del Tenant con filtros múltiples y ordenamiento.
    No requiere autenticación. Cumple aislamiento estricto por empresa.
    """
    try:
        info_empresa = None
        if slug and slug.strip():
            info_empresa = catalogo_repos.obtener_info_tenant_por_slug(slug)
            if info_empresa:
                id_empresa = info_empresa["id_empresa"]

        # Resolver Tenant si no fue provisto
        if not id_empresa:
            tenants = _obtener_tenants_cached()
            if not tenants:
                return {
                    "success": True,
                    "empresa": None,
                    "total": 0,
                    "data": []
                }
            id_empresa = tenants[0]["id_empresa"]

        if not info_empresa:
            info_empresa = _obtener_info_tenant_cached(id_empresa)
        resultado = catalogo_repos.listar_catalogo_publico(
            id_empresa=id_empresa,
            busqueda=busqueda,
            id_categoria=id_categoria,
            publico=publico,
            id_sucursal=id_sucursal,
            id_talla=id_talla,
            id_color=id_color,
            temporada=temporada,
            coleccion=coleccion,
            precio_min=precio_min,
            precio_max=precio_max,
            orden=orden,
            limit=limit,
            offset=offset
        )

        return {
            "success": True,
            "empresa": info_empresa,
            "total": resultado["total"],
            "limit": resultado["limit"],
            "offset": resultado["offset"],
            "data": resultado["productos"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar el catálogo: {str(e)}"
        )

@router.get('/productos/{id_producto}', summary="Consultar detalle de prenda con variantes y stock")
def obtener_detalle_producto_catalogo(
    id_producto: int,
    id_empresa: Optional[int] = Query(None, description="Opcional: ID de la empresa para validar aislamiento")
):
    """
    Retorna el detalle completo de una prenda activa:
    - Galería de fotos
    - Variantes activas de talla y color
    - Disponibilidad en inventario por sucursal vigente
    - Marcadores para reserva, compra y vestidor RA
    """
    try:
        producto = catalogo_repos.obtener_detalle_producto_publico(
            id_producto=id_producto,
            id_empresa=id_empresa
        )
        if not producto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La prenda solicitada no existe, se encuentra inactiva o no pertenece a esta tienda."
            )

        return {
            "success": True,
            "data": producto
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener detalle del producto: {str(e)}"
        )

@router.get('/variantes/{id_variante}/disponibilidad', summary="Consultar disponibilidad en inventario de una variante por sucursal")
def consultar_disponibilidad_variante(
    id_variante: int,
    id_empresa: Optional[int] = Query(None, description="Opcional: ID de la empresa para validación multi-tenant")
):
    """
    Consulta en tiempo real el stock de una variante de producto en las sucursales
    activas del Tenant. Retorna sucursal, ciudad, dirección, horario y cantidad disponible.
    No permite modificar inventario ni muestra cantidades negativas.
    """
    try:
        disponibilidad = catalogo_repos.obtener_disponibilidad_variante_sucursales(
            id_variante=id_variante,
            id_empresa=id_empresa
        )
        if not disponibilidad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La variante solicitada no existe, se encuentra inactiva o no pertenece a la tienda indicada."
            )

        return {
            "success": True,
            "data": disponibilidad
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar disponibilidad por sucursal: {str(e)}"
        )

# ==============================================================================
# M14 - VESTIDOR VIRTUAL REALIDAD AUMENTADA
# ==============================================================================

@router.get('/vestidor/prendas', summary="M14: Listar prendas compatibles con Vestidor Virtual RA")
def listar_prendas_vestidor_ra(
    id_empresa: Optional[int] = Query(None, description="Filtrar por Tenant activo"),
    tipo_prenda: Optional[str] = Query(None, description="Filtrar por tipo: TOP, PANT, DRESS o TODAS")
):
    """
    Retorna la lista de prendas activas habilitadas para el Vestidor Virtual (M14)
    con sus URLs de modelos 2D transparentes y categorías de pose.
    """
    try:
        prendas = catalogo_repos.obtener_prendas_vestidor_ra(
            id_empresa=id_empresa,
            tipo_prenda=tipo_prenda
        )
        return {
            "success": True,
            "data": prendas
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar prendas para el vestidor: {str(e)}"
        )

@router.get('/productos/{id_producto}/vestidor', summary="M14: Obtener configuración RA de una prenda")
def obtener_vestidor_producto(id_producto: int):
    """
    Retorna la configuración y recurso 2D de vestidor virtual para la prenda dada.
    """
    try:
        config = catalogo_repos.obtener_config_vestidor_producto(id_producto)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La prenda no existe o no se encuentra activa."
            )
        return {
            "success": True,
            "data": config
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar configuración del vestidor: {str(e)}"
        )


@router.get('/delta', summary="Sincronización incremental del catálogo para clientes offline (PWA / POS)")
@router.get('/productos/delta', summary="Sincronización incremental del catálogo")
def obtener_delta_productos_catalogo(
    updated_since: Optional[str] = Query(None, description="Cursor ISO 8601 de la última sincronización"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por tenant específico"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar stock por sucursal específica"),
    limit: int = Query(200, ge=1, le=1000, description="Límite máximo de productos por lote")
):
    """
    Retorna únicamente los productos y variantes modificados o eliminados desde 'updated_since'.
    Permite a la PWA o aplicación POS mantener su copia IndexedDB al día con consumo mínimo de datos.
    """
    try:
        resultado = catalogo_repos.obtener_delta_catalogo(
            id_empresa=id_empresa,
            updated_since=updated_since,
            id_sucursal=id_sucursal,
            limit=limit
        )
        return {
            "success": True,
            **resultado
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar delta de catálogo: {str(e)}"
        )

