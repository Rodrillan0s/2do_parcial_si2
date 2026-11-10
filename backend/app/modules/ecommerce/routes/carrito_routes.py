from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from pydantic import BaseModel, Field
from app.core.security import verificar_token
from app.modules.ecommerce.repos import carrito_repos
from app.modules.catalogo.repos import catalogo_repos
router = APIRouter(prefix="/api/carrito", tags=["Carrito de Compras"])

class AgregarItemCarritoDTO(BaseModel):
    id_variante: int = Field(..., gt=0, description="ID de la variante de producto (talla + color)")
    cantidad: int = Field(1, gt=0, description="Cantidad a agregar")
    id_empresa: Optional[int] = Field(None, description="ID del Tenant (empresa)")

class ActualizarCantidadItemDTO(BaseModel):
    cantidad: int = Field(..., gt=0, description="Nueva cantidad de la prenda")
    id_empresa: Optional[int] = Field(None, description="ID del Tenant")

def _resolver_id_empresa(id_empresa_param: Optional[int], token_data: dict) -> int:
    from app.core.commerce_tenant import resolver_empresa_compra
    return resolver_empresa_compra(token_data, id_empresa_param)

@router.get('', summary="Consultar carrito activo del usuario para el Tenant actual")
@router.get('/', summary="Consultar carrito activo del usuario para el Tenant actual")
def obtener_carrito(
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        empresa_id = _resolver_id_empresa(id_empresa, token_data)
        carrito = carrito_repos.consultar_carrito_completo(id_usuario, empresa_id)
        return {
            "success": True,
            "data": carrito
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar el carrito de compras: {str(e)}"
        )

@router.get('/resumen', summary="Obtener resumen rápido de conteo de prendas y subtotal para el Navbar")
def obtener_resumen(
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        empresa_id = _resolver_id_empresa(id_empresa, token_data)
        resumen = carrito_repos.obtener_resumen_rapido_carrito(id_usuario, empresa_id)
        return {
            "success": True,
            "data": resumen
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener resumen del carrito: {str(e)}"
        )

@router.post('/items', summary="Agregar variante de producto al carrito")
def agregar_item(
    payload: AgregarItemCarritoDTO,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        tenant_target = payload.id_empresa
        empresa_variante = carrito_repos.obtener_empresa_de_variante(payload.id_variante)
        if empresa_variante and (not tenant_target or tenant_target != empresa_variante):
            tenant_target = empresa_variante
        empresa_id = _resolver_id_empresa(tenant_target, token_data)
        carrito = carrito_repos.agregar_item_al_carrito(
            id_usuario=id_usuario,
            id_empresa=empresa_id,
            id_variante=payload.id_variante,
            cantidad=payload.cantidad
        )
        return {
            "success": True,
            "message": "Prenda agregada a la bolsa de compras exitosamente.",
            "data": carrito
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al agregar producto al carrito: {str(e)}"
        )

@router.put('/items/{id_detalle_carrito}', summary="Modificar cantidad de una prenda en el carrito")
def actualizar_cantidad(
    id_detalle_carrito: int,
    payload: ActualizarCantidadItemDTO,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        empresa_id = _resolver_id_empresa(payload.id_empresa, token_data)
        carrito = carrito_repos.actualizar_cantidad_item(
            id_usuario=id_usuario,
            id_empresa=empresa_id,
            id_detalle_carrito=id_detalle_carrito,
            nueva_cantidad=payload.cantidad
        )
        return {
            "success": True,
            "message": "Cantidad actualizada correctamente.",
            "data": carrito
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar cantidad: {str(e)}"
        )

@router.delete('/items/{id_detalle_carrito}', summary="Eliminar una prenda del carrito")
def eliminar_item(
    id_detalle_carrito: int,
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        empresa_id = _resolver_id_empresa(id_empresa, token_data)
        carrito = carrito_repos.eliminar_item_del_carrito(
            id_usuario=id_usuario,
            id_empresa=empresa_id,
            id_detalle_carrito=id_detalle_carrito
        )
        return {
            "success": True,
            "message": "Prenda eliminada del carrito.",
            "data": carrito
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar prenda del carrito: {str(e)}"
        )

@router.delete('/vaciar', summary="Vaciar todos los productos del carrito")
def vaciar_carrito(
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        empresa_id = _resolver_id_empresa(id_empresa, token_data)
        carrito = carrito_repos.vaciar_carrito_cliente(id_usuario, empresa_id)
        return {
            "success": True,
            "message": "La bolsa de compras ha sido vaciada.",
            "data": carrito
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al vaciar el carrito: {str(e)}"
        )
