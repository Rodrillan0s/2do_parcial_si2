from fastapi import APIRouter, Body, HTTPException, Request
from app.modules.auth.services import auth_services
router = APIRouter(tags=["Autenticación y Seguridad"])

@router.post('/register')
def register(request: Request, data: dict = Body(...)):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return auth_services.registrar_cliente(data, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post('/login')
def login(request: Request, data: dict = Body(...)):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return auth_services.iniciar_sesion(data, request)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Configuración de autenticación incompleta: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post('/verify-device')
def verify_device(data: dict = Body(...)):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return auth_services.verificar_nuevo_dispositivo(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post('/forgot-password')
def forgot_password(data: dict = Body(...)):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return auth_services.solicitar_recuperacion_clave(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post('/verify-recovery-code')
def verify_recovery_code(data: dict = Body(...)):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return auth_services.verificar_codigo_recuperacion(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post('/reset-password')
def reset_password(data: dict = Body(...)):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")
    try:
        return auth_services.restablecer_clave(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
