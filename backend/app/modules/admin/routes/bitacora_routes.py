from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.core.security import require_permission
from app.modules.admin.services import bitacora_services
router = APIRouter(tags=["Bitácora y Auditoría"])

@router.get('')
@router.get('/')
def get_bitacora(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    modulo: Optional[str] = None,
    accion: Optional[str] = None,
    resultado: Optional[str] = None,
    nivel: Optional[str] = None,
    id_usuario: Optional[int] = None,
    id_empresa: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    search: Optional[str] = None,
    payload: dict = Depends(require_permission('bitacora.ver'))
):
    try:
        filtros = {
            "modulo": modulo,
            "accion": accion,
            "resultado": resultado,
            "nivel": nivel,
            "id_usuario": id_usuario,
            "id_empresa": id_empresa,
            "id_sucursal": id_sucursal,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "search": search
        }
        
        # Eliminar filtros nulos
        filtros = {k: v for k, v in filtros.items() if v is not None}
        
        return bitacora_services.obtener_eventos(payload, filtros, page, limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get('/{id_bitacora}')
def get_detalle_bitacora(
    id_bitacora: int,
    payload: dict = Depends(require_permission('bitacora.ver'))
):
    try:
        return bitacora_services.obtener_detalle_evento(id_bitacora, payload)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
