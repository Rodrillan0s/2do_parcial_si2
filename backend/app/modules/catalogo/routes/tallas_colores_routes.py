from fastapi import APIRouter, Body, HTTPException, Depends, Request
from typing import Optional
from app.modules.catalogo.services import tallas_colores_services
from app.core.security import require_permission

tallas_router = APIRouter(tags=["Tallas"])
colores_router = APIRouter(tags=["Colores"])

# ==============================================================================
# RUTAS DE TALLAS
# ==============================================================================

@tallas_router.get('')
@tallas_router.get('/')
def get_tallas(
    solo_activas: bool = False,
    busqueda: Optional[str] = None,
    id_empresa: Optional[int] = None,
    payload: dict = Depends(require_permission('tallas.ver'))
):
    try:
        return tallas_colores_services.listar_tallas(
            payload=payload,
            solo_activas=solo_activas,
            busqueda=busqueda,
            id_empresa=id_empresa
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al listar tallas: {str(e)}")

@tallas_router.get('/{id_talla}')
def get_talla_by_id(
    id_talla: int,
    payload: dict = Depends(require_permission('tallas.ver'))
):
    try:
        return tallas_colores_services.obtener_talla(id_talla, payload)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al consultar talla: {str(e)}")

@tallas_router.post('')
@tallas_router.post('/')
def create_talla(
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('tallas.crear'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return tallas_colores_services.registrar_talla(data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al registrar talla: {str(e)}")

@tallas_router.put('/{id_talla}')
def update_talla(
    id_talla: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('tallas.editar'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return tallas_colores_services.actualizar_talla(id_talla, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al actualizar talla: {str(e)}")

@tallas_router.put('/{id_talla}/estado')
def toggle_estado_talla(
    id_talla: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('tallas.editar'))
):
    try:
        activo = bool(data.get('activo', False))
        return tallas_colores_services.cambiar_estado_talla(id_talla, activo, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al cambiar estado de talla: {str(e)}")

@tallas_router.delete('/{id_talla}')
def delete_talla(
    id_talla: int,
    request: Request,
    payload: dict = Depends(require_permission('tallas.desactivar'))
):
    try:
        return tallas_colores_services.eliminar_talla(id_talla, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar talla: {str(e)}")


# ==============================================================================
# RUTAS DE COLORES
# ==============================================================================

@colores_router.get('')
@colores_router.get('/')
def get_colores(
    solo_activos: bool = False,
    busqueda: Optional[str] = None,
    id_empresa: Optional[int] = None,
    payload: dict = Depends(require_permission('colores.ver'))
):
    try:
        return tallas_colores_services.listar_colores(
            payload=payload,
            solo_activos=solo_activos,
            busqueda=busqueda,
            id_empresa=id_empresa
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al listar colores: {str(e)}")

@colores_router.get('/{id_color}')
def get_color_by_id(
    id_color: int,
    payload: dict = Depends(require_permission('colores.ver'))
):
    try:
        return tallas_colores_services.obtener_color(id_color, payload)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al consultar color: {str(e)}")

@colores_router.post('')
@colores_router.post('/')
def create_color(
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('colores.crear'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return tallas_colores_services.registrar_color(data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al registrar color: {str(e)}")

@colores_router.put('/{id_color}')
def update_color(
    id_color: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('colores.editar'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return tallas_colores_services.actualizar_color(id_color, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al actualizar color: {str(e)}")

@colores_router.put('/{id_color}/estado')
def toggle_estado_color(
    id_color: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('colores.editar'))
):
    try:
        activo = bool(data.get('activo', False))
        return tallas_colores_services.cambiar_estado_color(id_color, activo, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al cambiar estado de color: {str(e)}")

@colores_router.delete('/{id_color}')
def delete_color(
    id_color: int,
    request: Request,
    payload: dict = Depends(require_permission('colores.desactivar'))
):
    try:
        return tallas_colores_services.eliminar_color(id_color, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar color: {str(e)}")
