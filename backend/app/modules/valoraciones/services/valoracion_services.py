"""
Servicio de negocio para el Sistema de Valoraciones de Calidad y Servicio.
Orquesta validaciones de compra verificada, aislamiento multitenant y flujos alternativos A1 y A2.
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from app.modules.ecommerce.repos.carrito_repos import obtener_o_crear_cliente
from app.modules.valoraciones.repos import valoracion_repos
from app.modules.valoraciones.schemas.valoracion_schemas import (
    CrearValoracionDTO,
    AtenderValoracionDTO
)


def registrar_valoracion_cliente(dto: CrearValoracionDTO, token_data: dict) -> Dict[str, Any]:
    """
    Registra una valoración proveniente del cliente garantizando:
    1. Compra verificada previa (t_pedido, t_venta o t_reserva).
    2. Flujo A2: Si la puntuación es 1 estrella, exige motivo_negativo y activa revisión.
    3. Prevención de valoraciones duplicadas por la misma transacción.
    4. Determinación segura del id_empresa e id_sucursal en base a la compra real.
    """
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    if not id_usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado o token inválido."
        )

    id_cliente = obtener_o_crear_cliente(id_usuario)

    # Flujo A2: Regla de negocio para 1 estrella
    if dto.puntuacion == 1:
        if not dto.motivo_negativo or len(dto.motivo_negativo.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Para valoraciones de 1 estrella es necesario detallar el motivo en el panel de texto para dar seguimiento."
            )

    # Validar elegibilidad de compra
    try:
        contexto = valoracion_repos.validar_elegibilidad_compra(
            id_cliente=id_cliente,
            id_producto=dto.id_producto,
            id_pedido=dto.id_pedido,
            id_venta=dto.id_venta,
            id_reserva=dto.id_reserva
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    id_empresa = contexto["id_empresa"]
    id_sucursal = contexto.get("id_sucursal")
    id_venta = contexto.get("id_venta")
    id_pedido = contexto.get("id_pedido")
    id_reserva = contexto.get("id_reserva")

    # Verificar si ya existe
    if valoracion_repos.verificar_valoracion_existente(
        id_cliente=id_cliente,
        id_producto=dto.id_producto,
        id_pedido=id_pedido,
        id_venta=id_venta,
        id_reserva=id_reserva
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya has registrado una valoración para esta compra."
        )

    # Persistencia
    resultado = valoracion_repos.registrar_valoracion(
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        id_cliente=id_cliente,
        puntuacion=dto.puntuacion,
        id_producto=dto.id_producto,
        id_pedido=id_pedido,
        id_venta=id_venta,
        id_reserva=id_reserva,
        comentario=dto.comentario.strip() if dto.comentario else None,
        motivo_negativo=dto.motivo_negativo.strip() if dto.motivo_negativo else None
    )

    return {
        "success": True,
        "message": "Valoración registrada exitosamente.",
        "data": resultado
    }


def obtener_resumen_producto(id_producto: int) -> Dict[str, Any]:
    """Obtiene el resumen público de valoraciones de un producto."""
    if id_producto <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de producto inválido.")
    datos = valoracion_repos.obtener_resumen_producto(id_producto)
    return {
        "success": True,
        "data": datos
    }


def obtener_pendientes_cliente(token_data: dict) -> Dict[str, Any]:
    """Obtiene las compras recientes del cliente pendientes de valorar."""
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    if not id_usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado.")

    id_cliente = obtener_o_crear_cliente(id_usuario)
    items = valoracion_repos.obtener_compras_pendientes_cliente(id_cliente)
    return {
        "success": True,
        "data": items
    }


def listar_valoraciones_admin(
    token_data: dict,
    id_empresa_param: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    solo_criticas: bool = False,
    atendido: Optional[bool] = None,
    limite: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Lista valoraciones para administradores de tienda."""
    from app.core.commerce_tenant import resolver_empresa_compra
    id_empresa = resolver_empresa_compra(token_data, id_empresa_param)

    items = valoracion_repos.listar_valoraciones_admin(
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        solo_criticas=solo_criticas,
        atendido=atendido,
        limite=limite,
        offset=offset
    )
    return {
        "success": True,
        "data": items
    }


def atender_valoracion_admin(
    id_valoracion: int,
    dto: AtenderValoracionDTO,
    token_data: dict,
    id_empresa_param: Optional[int] = None
) -> Dict[str, Any]:
    """Registra la resolución administrativa de una valoración crítica."""
    from app.core.commerce_tenant import resolver_empresa_compra
    id_empresa = resolver_empresa_compra(token_data, id_empresa_param)

    ok = valoracion_repos.resolver_valoracion_admin(
        id_valoracion=id_valoracion,
        id_empresa=id_empresa,
        notas_admin=dto.notas_admin,
        atendido=dto.atendido
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Valoración no encontrada.")

    return {
        "success": True,
        "message": "Valoración actualizada correctamente."
    }
