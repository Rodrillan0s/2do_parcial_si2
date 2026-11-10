from fastapi import APIRouter, Body, HTTPException, Depends, Request
from app.modules.auth.services import roles_services
from app.core.security import require_permission, require_platform_admin

router = APIRouter(tags=["Roles"])

@router.get('/')
def get_roles(payload: dict = Depends(require_permission('roles.ver'))):
    try:
        return roles_services.listar_roles(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post('/', dependencies=[Depends(require_platform_admin)])
def create_rol(request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('roles.crear'))):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
    
    try:
        return roles_services.registrar_rol(data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {str(e)}")

@router.put('/{id_rol}', dependencies=[Depends(require_platform_admin)])
def update_rol(id_rol: int, request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('roles.editar'))):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
        
    try:
        return roles_services.actualizar_rol(id_rol, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {str(e)}")

@router.delete('/{id_rol}', dependencies=[Depends(require_platform_admin)])
def delete_rol(id_rol: int, request: Request, payload: dict = Depends(require_permission('roles.eliminar'))):
    try:
        return roles_services.borrar_rol(id_rol, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        if "fk_usuario_rol" in error_msg:
            raise HTTPException(status_code=400, detail="No se puede eliminar este rol porque hay usuarios asignados a él.")
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {error_msg}")
