import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel

from app.core.security import verificar_token
from app.modules.pos.services import comprobante_service
from app.modules.ecommerce.repos import pago_repos
from app.shared.email_service import enviar_correo_comprobante

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/comprobantes", tags=["W29 - Emisión de Comprobantes"])

class ReenviarCorreoDTO(BaseModel):
    correo_destino: Optional[str] = None

@router.get('/venta/{id_venta}/pdf', summary="W29: Descargar comprobante de venta o factura en PDF")
def descargar_pdf_venta(
    id_venta: int,
    token_data: dict = Depends(verificar_token)
):
    try:
        datos = comprobante_service.obtener_datos_venta_comprobante(id_venta)
        if not datos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado.")

        pdf_bytes = comprobante_service.generar_pdf_venta(id_venta)
        filename = f"{datos['tipo_documento']}_{datos['numero_venta']}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Document-Type": datos["tipo_documento"],
                "X-Document-Number": datos["numero_venta"]
            }
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al generar PDF: {str(e)}")

@router.get('/pedido/{id_pedido}/pdf', summary="W29: Descargar comprobante por ID de pedido")
def descargar_pdf_por_pedido(
    id_pedido: int,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        venta_info = pago_repos.obtener_venta_por_pedido(id_pedido)
        if not venta_info or not venta_info.get("id_venta"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El pedido aún no cuenta con una venta confirmada ni comprobante emitido."
            )

        id_venta = venta_info["id_venta"]
        return descargar_pdf_venta(id_venta, token_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/reserva/{id_reserva}/pdf', summary="W29: Descargar comprobante de reserva en PDF")
def descargar_pdf_reserva(
    id_reserva: int,
    token_data: dict = Depends(verificar_token)
):
    try:
        pdf_bytes = comprobante_service.generar_pdf_reserva(id_reserva)
        filename = f"Comprobante_Reserva_{id_reserva}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/venta/{id_venta}/reenviar-correo', summary="W29: Reintentar envío de comprobante al correo del cliente")
def reenviar_correo_venta(
    id_venta: int,
    body: Optional[ReenviarCorreoDTO] = None,
    token_data: dict = Depends(verificar_token)
):
    try:
        datos = comprobante_service.obtener_datos_venta_comprobante(id_venta)
        if not datos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")

        correo_dest = (body.correo_destino if body and body.correo_destino else None) or datos["cliente_correo"]
        if not correo_dest or '@' not in correo_dest:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cliente no tiene un correo válido registrado.")

        pdf_bytes = comprobante_service.generar_pdf_venta(id_venta)
        filename = f"{datos['tipo_documento']}_{datos['numero_venta']}.pdf"

        enviado = enviar_correo_comprobante(
            destinatario_email=correo_dest,
            destinatario_nombre=datos["cliente_nombre"],
            tipo_documento=datos["tipo_documento"],
            numero_documento=datos["numero_venta"],
            total_bs=datos["total"],
            pdf_bytes=pdf_bytes,
            nombre_archivo=filename
        )

        if not enviado:
            return {
                "success": False,
                "message": "No se pudo entregar el correo en este momento, pero puedes descargar el PDF directamente.",
                "correo": correo_dest
            }

        return {
            "success": True,
            "message": f"Comprobante enviado exitosamente a {correo_dest}.",
            "correo": correo_dest
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

class EmitirComprobanteDTO(BaseModel):
    razon_social: str
    nit_ci: str
    correo_facturacion: Optional[str] = None
    tipo_documento: Optional[str] = "FACTURA"
    enviar_correo: bool = False

@router.get('/venta/{id_venta}/datos', summary="W29: Consultar datos completos para emisión de comprobante")
def obtener_datos_comprobante_venta(
    id_venta: int,
    token_data: dict = Depends(verificar_token)
):
    try:
        datos = comprobante_service.obtener_datos_venta_comprobante(id_venta)
        if not datos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")

        if datos["estado"] not in ('PAGADO', 'COMPLETADA'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La venta con ID {id_venta} no ha sido pagada (estado actual: {datos['estado']}). Debe procesarse el cobro en caja (W28) antes de emitir el comprobante."
            )

        if "pago" not in datos and datos.get("metodo_pago"):
            datos["pago"] = {
                "id_pago": datos.get("id_pago"),
                "metodo": datos.get("metodo_pago"),
                "monto": datos.get("total"),
                "fecha": datos.get("fecha_venta"),
                "estado": "APROBADO"
            }

        return {
            "success": True,
            "datos": datos,
            "venta": datos,
            "data": datos,
            "pdf_url": f"/api/comprobantes/venta/{id_venta}/pdf"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/venta/{id_venta}/emitir', summary="W29: Emitir comprobante o factura de venta presencial")
def emitir_comprobante_venta(
    id_venta: int,
    body: EmitirComprobanteDTO,
    token_data: dict = Depends(verificar_token)
):
    try:
        from app.core.postgres import PostgreSQL
        from app.core.config import Config

        # 1. Validar que la venta exista y esté PAGADA
        datos = comprobante_service.obtener_datos_venta_comprobante(id_venta)
        if not datos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")

        if datos["estado"] not in ('PAGADO', 'COMPLETADA'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede emitir comprobante para una venta no pagada (estado actual: {datos['estado']})."
            )

        # 2. Validar que tenga pago asociado
        if not datos.get("codigo_transaccion") or datos.get("codigo_transaccion") == "TXN-MANUAL":
            # Verificar si existe en t_pago
            db = PostgreSQL()
            db.create_connection()
            try:
                schema = Config.SCHEMA or 'comercio'
                pago_row = db.execute_query(
                    f"SELECT id_pago FROM {schema}.t_pago WHERE id_venta = %s AND estado = 'APROBADO';",
                    (id_venta,), fetchone=True
                )
                if not pago_row:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No se encontró un pago aprobado asociado a esta venta."
                    )
            finally:
                db.close_connection()

        # 3. Validar obligatoriedad de datos
        razon_social = (body.razon_social or "").strip()
        nit_ci = (body.nit_ci or "").strip()
        correo_fac = (body.correo_facturacion or "").strip() or None
        tipo_doc = (body.tipo_documento or "FACTURA").strip().upper()

        if not razon_social:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre o razón social es obligatorio para emitir el comprobante.")
        if not nit_ci:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El número de NIT o Carnet de Identidad (CI) es obligatorio.")

        # 4. Actualizar snapshot en t_venta
        db = PostgreSQL()
        db.create_connection()
        try:
            schema = Config.SCHEMA or 'comercio'
            q_up = f"""
                UPDATE {schema}.t_venta
                SET 
                    razon_social = %s,
                    nit_ci = %s,
                    correo_facturacion = %s,
                    tipo_documento = %s
                WHERE id_venta = %s;
            """
            db.execute_query(q_up, (razon_social, nit_ci, correo_fac, tipo_doc, id_venta), commit=True)
        finally:
            db.close_connection()

        # 5. Envío opcional por correo
        correo_enviado = False
        if body.enviar_correo and correo_fac and '@' in correo_fac:
            try:
                pdf_bytes = comprobante_service.generar_pdf_venta(id_venta)
                filename = f"{tipo_doc}_{datos['numero_venta']}.pdf"
                correo_enviado = bool(enviar_correo_comprobante(
                    destinatario_email=correo_fac,
                    destinatario_nombre=razon_social,
                    tipo_documento=tipo_doc,
                    numero_documento=datos["numero_venta"],
                    total_bs=datos["total"],
                    pdf_bytes=pdf_bytes,
                    nombre_archivo=filename
                ))
            except Exception as e:
                logger.warn(f"[EMITIR CORREO WARNING] No se pudo enviar email: {e}")

        # Recargar datos actualizados
        datos_actualizados = comprobante_service.obtener_datos_venta_comprobante(id_venta)

        return {
            "success": True,
            "message": f"{tipo_doc} emitida exitosamente para {razon_social}.",
            "correo_enviado": correo_enviado,
            "pdf_url": f"/api/comprobantes/venta/{id_venta}/pdf",
            "datos": datos_actualizados,
            "venta": datos_actualizados,
            "data": datos_actualizados
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[EMITIR COMPROBANTE ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

