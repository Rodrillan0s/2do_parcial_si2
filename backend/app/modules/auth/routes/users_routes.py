from typing import Optional
from fastapi import APIRouter, Body, HTTPException, Depends, Request, Query
from app.modules.auth.services import users_services
from app.core.security import require_permission

router = APIRouter(tags=["Usuarios"])

@router.get('')
@router.get('/')
def get_users(
    id_empresa: Optional[int] = Query(None, description="Filtro de Tenant (Solo Administrador Global)"),
    payload: dict = Depends(require_permission('usuarios.ver'))
):
    try:
        return users_services.listar_usuarios(payload, id_empresa_filtro=id_empresa)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get('/{id_usuario}')
def get_user_by_id(
    id_usuario: int,
    payload: dict = Depends(require_permission('usuarios.ver'))
):
    return users_services.obtener_usuario_detalle(id_usuario, payload)

@router.post('')
@router.post('/')
def create_user(request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('usuarios.crear'))):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
    
    try:
        return users_services.registrar_usuario(data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        if "uk_nombre_usuario" in error_msg:
            raise HTTPException(status_code=400, detail="El nombre de usuario elegido ya está en uso. Por favor, elija otro.")
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {error_msg}")

@router.put('/{id_usuario}')
def update_user(id_usuario: int, request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('usuarios.editar'))):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
        
    try:
        return users_services.actualizar_usuario(id_usuario, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        if "uk_nombre_usuario" in error_msg:
            raise HTTPException(status_code=400, detail="El nombre de usuario elegido ya está en uso por otra persona.")
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {error_msg}")

@router.put('/{id_usuario}/estado')
def toggle_estado_user(id_usuario: int, request: Request, data: dict = Body(...), payload: dict = Depends(require_permission('usuarios.editar'))):
    try:
        return users_services.cambiar_estado_usuario(id_usuario, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al cambiar estado: {str(e)}")

@router.delete('/{id_usuario}')
def delete_user(id_usuario: int, request: Request, payload: dict = Depends(require_permission('usuarios.desactivar'))):
    try:
        return users_services.eliminar_usuario(id_usuario, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en BD: {str(e)}")