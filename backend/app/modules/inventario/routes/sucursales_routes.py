from fastapi import APIRouter, Body, HTTPException, Depends, Request
from typing import Optional
from app.modules.inventario.services import sucursales_services
from app.core.security import require_permission

router = APIRouter(tags=["Sucursales"])

@router.get('')
@router.get('/')
def get_sucursales(id_empresa: Optional[int] = None, payload: dict = Depends(require_permission('sucursales.ver'))):
    try:
        return sucursales_services.listar_sucursales(id_empresa, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get('/{id_sucursal}')
def get_sucursal_by_id(id_sucursal: int, payload: dict = Depends(require_permission('sucursales.ver'))):
    return sucursales_services.obtener_sucursal_detalle(id_sucursal, payload)

@router.post('')
@router.post('/')
def create_sucursal(request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('sucursales.crear'))):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
    
    try:
        return sucursales_services.registrar_sucursal(data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {str(e)}")

@router.put('/{id_sucursal}')
def update_sucursal(id_sucursal: int, request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('sucursales.editar'))):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
        
    try:
        return sucursales_services.actualizar_sucursal(id_sucursal, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {str(e)}")

@router.put('/{id_sucursal}/estado')
def toggle_estado_sucursal(id_sucursal: int, request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('sucursales.editar'))):
    try:
        return sucursales_services.cambiar_estado_sucursal(id_sucursal, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {str(e)}")

@router.delete('/{id_sucursal}')
def delete_sucursal(id_sucursal: int, request: Request, payload: dict = Depends(require_permission('sucursales.desactivar'))):
    try:
        return sucursales_services.borrar_sucursal(id_sucursal, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {str(e)}")
