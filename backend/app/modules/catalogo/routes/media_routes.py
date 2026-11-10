from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from app.core.security import verificar_token
from app.shared import cloudinary_service
from typing import Optional

router = APIRouter(prefix='/api/media', tags=["Gestión Multimedia y Cloudinary"])

@router.get('/cloudinary/status')
def check_cloudinary_status():
    """
    Verifica el estado de conexión con Cloudinary.
    """
    resultado = cloudinary_service.probar_conexion_cloudinary()
    if not resultado.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resultado
        )
    return resultado

@router.post('/upload')
async def upload_file_to_cloudinary(
    file: UploadFile = File(...),
    folder: Optional[str] = Form("aurora_store/general"),
    token_data: dict = Depends(verificar_token)
):
    """
    Sube un archivo de imagen a Cloudinary (requiere sesión activa).
    """
    try:
        contenido = await file.read()
        resultado = cloudinary_service.subir_imagen_cloudinary(contenido, folder=folder)
        return {
            "success": True,
            "message": "Archivo subido exitosamente a Cloudinary.",
            "data": resultado
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir imagen a Cloudinary: {str(e)}"
        )
