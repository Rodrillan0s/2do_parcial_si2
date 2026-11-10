from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.core.security import verificar_token
from app.modules.pedidos.repos import pedido_repos
from app.modules.catalogo.repos import catalogo_repos
router = APIRouter(prefix="/api/pedidos", tags=["Pedidos y Checkout"])

class CrearPedidoDTO(BaseModel):
    id_sucursal: int = Field(..., gt=0, description="ID de la sucursal seleccionada")
    modalidad_compra: str = Field("RETIRO_SUCURSAL", description="RETIRO_SUCURSAL o ENTREGA_DOMICILIO")
    nombre_contacto: str = Field(..., min_length=2, max_length=150, description="Nombre de quien retira o recibe")
    telefono_contacto: str = Field(..., min_length=5, max_length=50, description="Teléfono de contacto")
    correo_contacto: Optional[str] = Field(None, max_length=150, description="Correo electrónico")
    direccion_entrega: Optional[str] = Field(None, max_length=255, description="Dirección si es entrega a domicilio")
    ciudad_entrega: Optional[str] = Field(None, max_length=100, description="Ciudad de entrega")
    notas_entrega: Optional[str] = Field(None, max_length=500, description="Instrucciones adicionales")
    id_empresa: Optional[int] = Field(None, description="ID del Tenant")

def _resolver_id_empresa(id_empresa_param: Optional[int], token_data: dict) -> int:
    from app.core.commerce_tenant import resolver_empresa_compra
    return resolver_empresa_compra(token_data, id_empresa_param)

@router.get('/sucursales', summary="Listar sucursales activas del Tenant para checkout")
def listar_sucursales_checkout(
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        empresa_id = _resolver_id_empresa(id_empresa, token_data)
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        sucursales = pedido_repos.obtener_sucursales_tenant(empresa_id, id_usuario=id_usuario)
        return {
            "success": True,
            "data": sucursales
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener sucursales del Tenant: {str(e)}"
        )

@router.post('', status_code=status.HTTP_201_CREATED, summary="Crear pedido a partir del carrito activo")
@router.post('/', status_code=status.HTTP_201_CREATED, summary="Crear pedido a partir del carrito activo")
def crear_pedido(
    body: CrearPedidoDTO,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        empresa_id = _resolver_id_empresa(body.id_empresa, token_data)

        from app.modules.saas.services.saas_services import exigir_vigencia
        from app.core.tenant_guard import obtener_alcance_usuario, resolver_sucursal_autorizada
        exigir_vigencia(empresa_id)
        if obtener_alcance_usuario(token_data) != 'CLIENTE':
            resolver_sucursal_autorizada(token_data, body.id_sucursal)
        datos = body.model_dump()
        pedido_creado = pedido_repos.validar_y_crear_pedido(id_usuario, empresa_id, datos)

        return {
            "success": True,
            "message": "Pedido generado exitosamente en estado PENDIENTE_PAGO.",
            "data": pedido_creado
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar el pedido: {str(e)}"
        )

@router.get('', summary="Listar pedidos del cliente autenticado con filtros y paginación")
@router.get('/', summary="Listar pedidos del cliente autenticado con filtros y paginación")
@router.get('/mis-pedidos', summary="Alias para listar pedidos del cliente autenticado")
def listar_pedidos_cliente(
    estado: Optional[str] = Query(None, description="Filtro por estado del pedido"),
    estado_pago: Optional[str] = Query(None, description="Filtro por estado de pago"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    fecha_fin: Optional[str] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    codigo: Optional[str] = Query(None, description="Búsqueda por código de pedido"),
    page: int = Query(1, ge=1, description="Número de página (1-indexado)"),
    limit: int = Query(10, ge=1, le=100, description="Límite por página"),
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    """
    W11 - CU11: Consulta el historial de pedidos del cliente autenticado.
    Soporta filtros combinados por estado, estado de pago, rango de fechas y código,
    así como paginación y aislamiento multitenant.
    """
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        if not id_usuario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o sin identificador de usuario."
            )

        empresa_id = None
        if id_empresa and id_empresa > 0:
            empresa_id = id_empresa
        elif token_data.get('id_empresa') and token_data.get('id_empresa') > 0:
            empresa_id = token_data['id_empresa']

        offset = (page - 1) * limit

        resultado = pedido_repos.listar_pedidos_cliente(
            id_usuario=id_usuario,
            id_empresa=empresa_id,
            estado=estado,
            estado_pago=estado_pago,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            codigo=codigo,
            limit=limit,
            offset=offset
        )

        total = resultado["total"]
        total_paginas = (total + limit - 1) // limit if total > 0 else 1

        return {
            "success": True,
            "total": total,
            "page": page,
            "limit": limit,
            "total_paginas": total_paginas,
            "data": resultado["data"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar el historial de pedidos: {str(e)}"
        )

@router.get('/{id_pedido}', summary="Consultar detalle de un pedido creado")
def obtener_pedido(
    id_pedido: int,
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        if not id_usuario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o sin identificador de usuario."
            )

        empresa_id = None
        if id_empresa and id_empresa > 0:
            empresa_id = id_empresa
        elif token_data.get('id_empresa') and token_data.get('id_empresa') > 0:
            empresa_id = token_data['id_empresa']

        pedido = pedido_repos.obtener_pedido_por_id(id_pedido, id_usuario, empresa_id)

        if not pedido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado o no pertenece a tu cuenta."
            )

        return {
            "success": True,
            "data": pedido
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar el pedido: {str(e)}"
        )

class CancelarPedidoDTO(BaseModel):
    motivo: Optional[str] = Field("Cancelado por el cliente", max_length=250, description="Motivo de la cancelación")

@router.post('/{id_pedido}/cancelar', summary="Cancelar pedido propio en estado PENDIENTE_PAGO y liberar stock")
def cancelar_pedido(
    id_pedido: int,
    body: Optional[CancelarPedidoDTO] = None,
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        if not id_usuario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token sin identificador de usuario."
            )

        empresa_id = _resolver_id_empresa(id_empresa, token_data)
        motivo = body.motivo if body and body.motivo else "Cancelado por el cliente"
        res = pedido_repos.cancelar_pedido_cliente(id_pedido, id_usuario, empresa_id, motivo=motivo)
        return {
            "success": True,
            "message": "Pedido cancelado y existencias liberadas exitosamente.",
            "data": res
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cancelar el pedido: {str(e)}"
        )

@router.post('/expirar', summary="Ejecutar expiración automática de pedidos vencidos sin pago")
def expirar_pedidos(
    horas: int = Query(48, ge=1, le=720, description="Tolerancia de horas antes de expirar"),
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        empresa_id = _resolver_id_empresa(id_empresa, token_data)
        res = pedido_repos.expirar_pedidos_vencidos(id_empresa=empresa_id, horas_tolerancia=horas)
        return {
            "success": True,
            "message": f"Proceso de expiración ejecutado. {res['pedidos_expirados']} pedido(s) expirados y {res['prendas_liberadas']} prenda(s) liberadas.",
            "data": res
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando expiración de pedidos: {str(e)}"
        )

