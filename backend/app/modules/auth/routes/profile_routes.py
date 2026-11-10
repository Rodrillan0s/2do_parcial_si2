from fastapi import APIRouter, Body, HTTPException, Depends
from app.modules.auth.services import profile_services
from app.core.security import verificar_token

router = APIRouter(tags=['Perfil'])

@router.get('')
@router.get('/')
def get_profile(token_data: dict = Depends(verificar_token)):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        return profile_services.obtener_perfil_usuario(id_usuario)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Error interno al obtener perfil: {err}")

@router.put('')
@router.put('/')
def update_profile(token_data: dict = Depends(verificar_token), data: dict = Body(...)):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        return profile_services.actualizar_perfil_usuario(id_usuario, data, token_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Error interno al actualizar perfil: {err}")

@router.put('/cambiar-password')
def change_password(token_data: dict = Depends(verificar_token), data: dict = Body(...)):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        return profile_services.cambiar_password_usuario(id_usuario, data, token_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Error interno al cambiar contraseña: {err}")