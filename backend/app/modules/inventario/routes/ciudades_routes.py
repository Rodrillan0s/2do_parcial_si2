from fastapi import APIRouter, Body, HTTPException, Depends, Request
from typing import Optional
from app.modules.inventario.services import ciudades_services
from app.core.security import require_permission

router = APIRouter(tags=["Ciudades"])

@router.get('')
@router.get('/')
def get_ciudades(
    solo_activas: bool = False,
    busqueda: Optional[str] = None,
    payload: dict = Depends(require_permission('sucursales.ver'))
):
    try:
        return ciudades_services.listar_ciudades(solo_activas=solo_activas, busqueda=busqueda)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar ciudades: {str(e)}")

@router.post('')
@router.post('/')
def create_ciudad(
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('sucursales.crear'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return ciudades_services.registrar_ciudad(data, payload, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al registrar ciudad: {str(e)}")

@router.put('/{id_ciudad}')
def update_ciudad(
    id_ciudad: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('sucursales.editar'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return ciudades_services.actualizar_ciudad(id_ciudad, data, payload, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al actualizar ciudad: {str(e)}")

@router.put('/{id_ciudad}/estado')
def toggle_estado_ciudad(
    id_ciudad: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('sucursales.editar'))
):
    try:
        return ciudades_services.cambiar_estado_ciudad(id_ciudad, data, payload, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cambiar estado de ciudad: {str(e)}")

@router.delete('/{id_ciudad}')
def delete_ciudad(
    id_ciudad: int,
    request: Request,
    payload: dict = Depends(require_permission('sucursales.desactivar'))
):
    try:
        return ciudades_services.cambiar_estado_ciudad(id_ciudad, {"estado": False}, payload, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al desactivar ciudad: {str(e)}")
