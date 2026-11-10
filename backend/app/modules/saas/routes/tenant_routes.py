from fastapi import APIRouter, Body, HTTPException, Depends, Request
from app.modules.saas.services import tenant_services
from app.core.security import require_permission, require_platform_admin

router = APIRouter(tags=["Empresas (Tenants)"])

# Dependencia de seguridad estricta para SuperAdministrador de la plataforma
def require_superadmin(payload: dict = Depends(require_platform_admin)):
    return payload

@router.get('/')
def get_empresas(payload: dict = Depends(require_permission('sucursales.ver'))):
    try:
        return tenant_services.listar_empresas(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al listar empresas: {str(e)}")

@router.get('/{id_empresa}')
def get_empresa(id_empresa: int, payload: dict = Depends(require_permission('sucursales.ver'))):
    try:
        return tenant_services.obtener_empresa(id_empresa, payload)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al obtener empresa: {str(e)}")

@router.post('/', status_code=201)
def create_empresa(request: Request, data: dict = Body(...), payload: dict = Depends(require_superadmin)):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
    
    try:
        return tenant_services.registrar_empresa(data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al registrar Tenant: {str(e)}")

@router.put('/{id_empresa}')
def update_empresa(id_empresa: int, request: Request, data: dict = Body(...), payload: dict = Depends(require_superadmin)):
    if not data:
        raise HTTPException(status_code=400, detail='El cuerpo de la petición está vacío.')
        
    try:
        return tenant_services.actualizar_empresa(id_empresa, data, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al actualizar Tenant: {str(e)}")

@router.delete('/{id_empresa}')
def delete_empresa(id_empresa: int, request: Request, payload: dict = Depends(require_superadmin)):
    try:
        return tenant_services.borrar_empresa(id_empresa, payload, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar Tenant: {str(e)}")