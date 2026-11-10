import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.security import verificar_token
from app.core.tenant_guard import resolver_tenant_operacion, resolver_sucursal_autorizada
from app.modules.reservas.services.atender_reserva_services import (
    listar_reservas_atender,
    obtener_reserva_atender,
    ejecutar_cobro_reserva_pos,
    ejecutar_entrega_reserva_pagada,
    ejecutar_atencion_reserva
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/atender-reserva",
    tags=["Atender Reserva - POS"]
)


# --- DTOs ---

class ItemSeleccionadoDTO(BaseModel):
    id_detalle_reserva: int = Field(..., gt=0, description="ID del detalle de la reserva")
    id_variante: Optional[int] = Field(None, gt=0, description="ID de la variante")
    cantidad: Optional[int] = Field(None, gt=0, description="Cantidad reservada")
    aceptado: bool = Field(True, description="True si el cliente compra la prenda, False si la devuelve al stock")


class DatosFacturacionDTO(BaseModel):
    nit_ci: Optional[str] = Field(None, description="NIT o CI para comprobante")
    razon_social: Optional[str] = Field(None, description="Nombre o Razón Social")
    correo_facturacion: Optional[str] = Field(None, description="Correo para envío de comprobante")
    tipo_documento: Optional[str] = Field("COMPROBANTE", description="COMPROBANTE, FACTURA o RECIBO")


class CobroReservaPosDTO(BaseModel):
    id_sesion_caja: Optional[int] = Field(None, description="Sesión de caja activa (opcional, autodetectada)")
    id_metodo_pago: int = Field(3, description="1: Tarjeta, 3: Efectivo, 4: QR")
    monto_recibido: Optional[float] = Field(None, ge=0.0, description="Monto entregado en efectivo por el cliente")
    monto_cambio: Optional[float] = Field(0.0, ge=0.0, description="Cambio entregado")
    referencia_transaccion: Optional[str] = Field(None, description="Código de autorización o comprobante")
    descuento: Optional[float] = Field(0.0, ge=0.0, description="Descuento en Bs.")
    observacion: Optional[str] = Field(None, max_length=300)
    datos_facturacion: Optional[DatosFacturacionDTO] = None
    items_seleccionados: Optional[List[ItemSeleccionadoDTO]] = None


class EntregaReservaDTO(BaseModel):
    items_seleccionados: Optional[List[ItemSeleccionadoDTO]] = None


# --- ENDPOINTS ---

@router.get("", summary="Listar reservas de la sucursal para atención en POS")
def listar_reservas_para_atencion(
    id_sucursal: Optional[int] = Query(None, description="ID de la sucursal"),
    id_empresa: Optional[int] = Query(None, description="ID de la empresa (multi-tenant)"),
    q: Optional[str] = Query(None, description="Buscador por código de reserva, nombre cliente o CI"),
    estado: Optional[str] = Query(None, description="Filtro de estado: PENDIENTE, CONFIRMADA o TODAS"),
    payload: dict = Depends(verificar_token)
):
    try:
        empresa_efectiva = resolver_tenant_operacion(payload, id_empresa, permitir_global=False)
        sucursal_efectiva = resolver_sucursal_autorizada(payload, id_sucursal)

        return listar_reservas_atender(
            id_empresa=empresa_efectiva,
            id_sucursal=sucursal_efectiva,
            busqueda=q,
            estado=estado
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR LISTAR RESERVAS ATENDER] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{id_reserva}", summary="Consultar reserva específica para atención")
def obtener_reserva_para_atencion(
    id_reserva: int,
    id_sucursal: Optional[int] = Query(None, description="ID de la sucursal"),
    id_empresa: Optional[int] = Query(None, description="ID de la empresa"),
    payload: dict = Depends(verificar_token)
):
    try:
        empresa_efectiva = resolver_tenant_operacion(payload, id_empresa, permitir_global=False)
        sucursal_efectiva = resolver_sucursal_autorizada(payload, id_sucursal)

        return obtener_reserva_atender(
            id_reserva=id_reserva,
            id_empresa=empresa_efectiva,
            id_sucursal=sucursal_efectiva
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR OBTENER RESERVA ATENDER] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id_reserva}/cobrar-pos", summary="Cobro en mostrador POS y entrega de prendas reservadas")
def cobrar_reserva_pos_endpoint(
    id_reserva: int,
    body: CobroReservaPosDTO,
    background_tasks: BackgroundTasks,
    id_sucursal: Optional[int] = Query(None, description="ID de la sucursal"),
    id_empresa: Optional[int] = Query(None, description="ID de la empresa"),
    payload: dict = Depends(verificar_token)
):
    try:
        id_usuario = payload.get("nro_usuario") or payload.get("id_usuario")
        empresa_efectiva = resolver_tenant_operacion(payload, id_empresa, permitir_global=False)
        sucursal_efectiva = resolver_sucursal_autorizada(payload, id_sucursal)

        datos_cobro = body.dict()

        resultado = ejecutar_cobro_reserva_pos(
            id_reserva=id_reserva,
            id_empresa=empresa_efectiva,
            id_sucursal=sucursal_efectiva,
            id_usuario=id_usuario,
            datos_cobro=datos_cobro
        )

        if not resultado.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=resultado.get("message", "Error al procesar el cobro en mostrador.")
            )

        # Enviar comprobante oficial por correo en background si se generó venta
        if resultado.get("id_venta"):
            from app.modules.ecommerce.routes.pago_routes import _enviar_comprobante_background
            background_tasks.add_task(_enviar_comprobante_background, resultado["id_venta"])

        return resultado
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR COBRAR POS ENDPOINT] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id_reserva}/entregar", summary="Entrega directa para reserva prepagada online")
def entregar_reserva_pagada_endpoint(
    id_reserva: int,
    background_tasks: BackgroundTasks,
    body: Optional[EntregaReservaDTO] = None,
    id_sucursal: Optional[int] = Query(None, description="ID de la sucursal"),
    id_empresa: Optional[int] = Query(None, description="ID de la empresa"),
    payload: dict = Depends(verificar_token)
):
    try:
        id_usuario = payload.get("nro_usuario") or payload.get("id_usuario")
        empresa_efectiva = resolver_tenant_operacion(payload, id_empresa, permitir_global=False)
        sucursal_efectiva = resolver_sucursal_autorizada(payload, id_sucursal)

        items_sel = [it.dict() for it in body.items_seleccionados] if (body and body.items_seleccionados) else None

        resultado = ejecutar_entrega_reserva_pagada(
            id_reserva=id_reserva,
            id_empresa=empresa_efectiva,
            id_sucursal=sucursal_efectiva,
            id_usuario=id_usuario,
            items_seleccionados=items_sel
        )

        if not resultado.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=resultado.get("message", "Error al registrar la entrega de la reserva.")
            )

        # Enviar comprobante oficial por correo en background si existe venta asociada
        id_venta_ret = resultado.get("data", {}).get("id_venta")
        if id_venta_ret:
            from app.modules.ecommerce.routes.pago_routes import _enviar_comprobante_background
            background_tasks.add_task(_enviar_comprobante_background, id_venta_ret)

        return resultado
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR ENTREGAR RESERVA ENDPOINT] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{id_reserva}", summary="Endpoint legacy de atención de reserva")
def atender_reserva_legacy_endpoint(
    id_reserva: int,
    id_sucursal: Optional[int] = Query(None, description="ID de la sucursal"),
    id_empresa: Optional[int] = Query(None, description="ID de la empresa"),
    payload: dict = Depends(verificar_token)
):
    try:
        empresa_efectiva = resolver_tenant_operacion(payload, id_empresa, permitir_global=False)
        sucursal_efectiva = resolver_sucursal_autorizada(payload, id_sucursal)

        return ejecutar_atencion_reserva(
            id_reserva=id_reserva,
            id_empresa=empresa_efectiva,
            id_sucursal=sucursal_efectiva
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR ATENDER RESERVA LEGACY] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))