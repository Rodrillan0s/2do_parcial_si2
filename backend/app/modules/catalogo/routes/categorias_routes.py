from fastapi import APIRouter, Body, HTTPException, Depends, Request, UploadFile, File, Form
from typing import Optional
from app.modules.catalogo.services import categorias_services
from app.core.security import require_permission
from app.shared.cloudinary_service import subir_imagen_cloudinary

router = APIRouter(tags=["Categorías"])

@router.get('')
@router.get('/')
def get_categorias(
    solo_activas: bool = False,
    busqueda: Optional[str] = None,
    id_empresa: Optional[int] = None,
    payload: dict = Depends(require_permission('categorias.ver'))
):
    try:
        return categorias_services.listar_categorias(
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
        raise HTTPException(status_code=500, detail=f"Error interno al listar categorías: {str(e)}")

@router.get('/{id_categoria}')
def get_categoria_by_id(
    id_categoria: int,
    payload: dict = Depends(require_permission('categorias.ver'))
):
    try:
        return categorias_services.obtener_categoria(id_categoria, payload)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al obtener categoría: {str(e)}")

@router.post('/upload-image')
def upload_categoria_image(
    file: UploadFile = File(...),
    payload: dict = Depends(require_permission('categorias.crear'))
):
    try:
        resultado = subir_imagen_cloudinary(file.file, folder="aurora_store/categorias")
        return {
            "success": True,
            "message": "Imagen subida a Cloudinary exitosamente",
            "url": resultado.get("url"),
            "public_id": resultado.get("public_id"),
            "data": resultado
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al subir imagen a Cloudinary: {str(e)}")

@router.post('')
@router.post('/')
def create_categoria(
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('categorias.crear'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")

    try:
        return categorias_services.registrar_categoria(data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al crear categoría: {str(e)}")

@router.put('/{id_categoria}')
def update_categoria(
    id_categoria: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('categorias.editar'))
):
    if not data:
        raise HTTPException(status_code=400, detail="El cuerpo de la petición está vacío.")

    try:
        return categorias_services.actualizar_categoria(id_categoria, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al actualizar categoría: {str(e)}")

@router.put('/{id_categoria}/estado')
def toggle_estado_categoria(
    id_categoria: int,
    request: Request,
    data: dict = Body(...),
    payload: dict = Depends(require_permission('categorias.editar'))
):
    try:
        activo = bool(data.get('activo', False))
        return categorias_services.cambiar_estado_categoria(id_categoria, activo, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al cambiar estado de categoría: {str(e)}")

@router.delete('/{id_categoria}')
def delete_categoria(
    id_categoria: int,
    request: Request,
    payload: dict = Depends(require_permission('categorias.desactivar'))
):
    try:
        return categorias_services.eliminar_categoria(id_categoria, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar/desactivar categoría: {str(e)}")
