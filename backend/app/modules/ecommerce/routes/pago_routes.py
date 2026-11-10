import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.config import Config
from app.core.security import verificar_token
from app.modules.ecommerce.repos import pago_repos
from app.modules.catalogo.repos import catalogo_repos
from app.modules.ecommerce.services import paypal_service
from app.modules.pos.services import comprobante_service
from app.shared.email_service import enviar_correo_comprobante

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pagos", tags=["W27 - Procesamiento de Pagos"])

class CrearOrdenPayPalDTO(BaseModel):
    id_pedido: int = Field(..., gt=0, description="ID del pedido a pagar")
    id_empresa: Optional[int] = Field(None, description="ID del Tenant")

class CapturarPayPalDTO(BaseModel):
    id_pedido: int = Field(..., gt=0)
    order_id: str = Field(..., min_length=5, description="Order ID retornado por PayPal")
    nit_ci: Optional[str] = Field(None, max_length=50)
    razon_social: Optional[str] = Field(None, max_length=150)
    id_empresa: Optional[int] = None

class ProcesarTarjetaDTO(BaseModel):
    id_pedido: int = Field(..., gt=0)
    titular: str = Field(..., min_length=3, max_length=150, description="Nombre como figura en la tarjeta")
    numero_tarjeta: str = Field(..., min_length=13, max_length=19, description="Número de tarjeta")
    mes_exp: str = Field(..., min_length=2, max_length=2, description="Mes MM")
    anio_exp: str = Field(..., min_length=2, max_length=4, description="Año YY o YYYY")
    cvv: str = Field(..., min_length=3, max_length=4, description="Código de seguridad")
    nit_ci: Optional[str] = Field(None, max_length=50)
    razon_social: Optional[str] = Field(None, max_length=150)
    id_empresa: Optional[int] = None

class ProcesarQRDTO(BaseModel):
    id_pedido: int = Field(..., gt=0, description="ID del pedido a pagar")
    codigo_transaccion: Optional[str] = Field(None, max_length=100, description="Código de referencia QR o comprobante bancario")
    nit_ci: Optional[str] = Field(None, max_length=50)
    razon_social: Optional[str] = Field(None, max_length=150)
    id_empresa: Optional[int] = None

class CancelarPagoDTO(BaseModel):
    id_pedido: int = Field(..., gt=0)
    motivo: Optional[str] = Field("Cancelado por el usuario", max_length=200)

def _enviar_comprobante_background(id_venta: int):
    """
    Tarea en background para generar y enviar el comprobante por correo sin bloquear al cliente.
    """
    try:
        datos = comprobante_service.obtener_datos_venta_comprobante(id_venta)
        if not datos or not datos.get("cliente_correo"):
            return
        pdf_bytes = comprobante_service.generar_pdf_venta(id_venta)
        enviar_correo_comprobante(
            destinatario_email=datos["cliente_correo"],
            destinatario_nombre=datos["cliente_nombre"],
            tipo_documento=datos["tipo_documento"],
            numero_documento=datos["numero_venta"],
            total_bs=datos["total"],
            pdf_bytes=pdf_bytes,
            nombre_archivo=f"{datos['tipo_documento']}_{datos['numero_venta']}.pdf",
            nombre_tienda=datos.get("empresa_nombre", "Tienda Oficial")
        )
    except Exception as e:
        logger.error(f"[W29 BACKGROUND EMAIL ERROR] {e}")

@router.get('/resumen/{id_pedido}', summary="Consultar resumen del pedido antes de pagar")
def obtener_resumen_pago(
    id_pedido: int,
    id_empresa: Optional[int] = Query(None),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        pedido = pago_repos.validar_pedido_para_pago(id_pedido, id_usuario, id_empresa)
        pedido["paypal_client_id"] = Config.PAYPAL_CLIENT_ID
        return {
            "success": True,
            "data": pedido
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/paypal/crear-orden', summary="W27: Iniciar orden de pago con PayPal")
def crear_orden_paypal_endpoint(
    body: CrearOrdenPayPalDTO,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        pedido = pago_repos.validar_pedido_para_pago(body.id_pedido, id_usuario, body.id_empresa)

        paypal_res = paypal_service.crear_orden_paypal(
            id_pedido=pedido["id_pedido"],
            codigo_pedido=pedido["codigo_pedido"],
            monto_bob=pedido["total"],
            nombre_tienda=pedido.get("nombre_empresa", "AURA Atelier")
        )

        return {
            "success": True,
            "message": "Orden de PayPal creada exitosamente.",
            "data": {
                "order_id": paypal_res["order_id"],
                "approve_url": paypal_res["approve_url"],
                "total_bob": pedido["total"],
                "total_usd": paypal_res["monto_usd"],
                "codigo_pedido": pedido["codigo_pedido"]
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/paypal/capturar', summary="W27 + W29: Capturar orden de PayPal y confirmar venta")
def capturar_paypal_endpoint(
    body: CapturarPayPalDTO,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        try:
            pedido = pago_repos.validar_pedido_para_pago(body.id_pedido, id_usuario, body.id_empresa)
        except ValueError as ve:
            if "ya se encuentra pagado" in str(ve).lower():
                from app.core.postgres import PostgreSQL
                db = PostgreSQL()
                db.create_connection()
                try:
                    schema = Config.SCHEMA or 'comercio'
                    q_venta = f"""
                        SELECT v.id_venta, v.numero_venta, v.tipo_documento, v.total, p.codigo_transaccion, ped.codigo_pedido
                        FROM {schema}.t_pedido ped
                        JOIN {schema}.t_venta v ON ped.id_venta = v.id_venta
                        LEFT JOIN {schema}.t_pago p ON p.id_venta = v.id_venta
                        WHERE ped.id_pedido = %s
                        LIMIT 1;
                    """
                    row_v = db.execute_query(q_venta, (body.id_pedido,), fetchone=True)
                    if row_v:
                        return {
                            "success": True,
                            "message": "El pago de este pedido ya ha sido confirmado previamente.",
                            "data": {
                                "id_pedido": body.id_pedido,
                                "codigo_pedido": row_v[5] or f"PED-{body.id_pedido}",
                                "id_venta": row_v[0],
                                "numero_venta": row_v[1],
                                "tipo_documento": row_v[2],
                                "total": float(row_v[3]),
                                "metodo_pago": "PayPal",
                                "codigo_transaccion": row_v[4] or f"PAYPAL-{body.order_id}",
                                "url_descarga_pdf": f"/api/comprobantes/venta/{row_v[0]}/pdf"
                            }
                        }
                finally:
                    db.close_connection()
            raise ve

        # 0. Pre-vuelo de inventario: verificar integridad antes de capturar dinero en PayPal
        pago_repos.validar_integridad_inventario_pedido(
            id_pedido=pedido["id_pedido"],
            id_sucursal=pedido["id_sucursal"],
            id_empresa=pedido["id_empresa"],
            items=pedido.get("items", [])
        )

        # 1. Capturar pago con el proveedor PayPal
        captura = paypal_service.capturar_orden_paypal(body.order_id)
        if not captura.get("success") or captura.get("status") != "COMPLETED":
            err_msg = captura.get("message") or "El proveedor de pagos PayPal no confirmó la transacción."
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

        codigo_transaccion = captura.get("capture_id") or f"PAYPAL-{body.order_id}"

        # 2. Confirmación atómica en PostgreSQL mediante fn_confirmar_pago_pedido
        res_db = pago_repos.ejecutar_confirmacion_pago(
            id_pedido=pedido["id_pedido"],
            tipo_metodo="PAYPAL",
            codigo_transaccion=codigo_transaccion,
            monto=pedido["total"],
            id_usuario=id_usuario,
            nit_ci=body.nit_ci,
            razon_social=body.razon_social,
            tipo_documento="FACTURA" if (body.nit_ci and body.nit_ci.strip()) else "COMPROBANTE"
        )

        id_venta = res_db.get("id_venta")

        # 3. W29: Disparar envío de correo en background
        if id_venta:
            background_tasks.add_task(_enviar_comprobante_background, id_venta)

        return {
            "success": True,
            "message": "Pago con PayPal acreditado y venta registrada exitosamente.",
            "data": {
                "id_pedido": pedido["id_pedido"],
                "codigo_pedido": pedido["codigo_pedido"],
                "id_venta": id_venta,
                "numero_venta": res_db.get("numero_venta"),
                "tipo_documento": res_db.get("tipo_documento"),
                "total": pedido["total"],
                "metodo_pago": "PayPal",
                "codigo_transaccion": codigo_transaccion,
                "url_descarga_pdf": f"/api/comprobantes/venta/{id_venta}/pdf"
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/tarjeta/procesar', summary="W27 + W29: Procesar pago con tarjeta y confirmar venta")
def procesar_tarjeta_endpoint(
    body: ProcesarTarjetaDTO,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        pedido = pago_repos.validar_pedido_para_pago(body.id_pedido, id_usuario, body.id_empresa)

        # 1. Validación de tarjeta segura (sin almacenar PAN ni CVV)
        clean_pan = "".join(filter(str.isdigit, body.numero_tarjeta))
        if len(clean_pan) < 13 or len(clean_pan) > 19:
            raise ValueError("Número de tarjeta inválido. Debe contener entre 13 y 19 dígitos.")

        # Simular rechazo si la tarjeta termina en 0000 o monto negativo
        if clean_pan.endswith("0000"):
            raise ValueError("La tarjeta fue rechazada por el emisor bancario (Fondos insuficientes o tarjeta bloqueada).")

        ultimos_cuatro = clean_pan[-4:]
        import uuid
        codigo_auth = f"AUTH-{uuid.uuid4().hex[:8].upper()}-*{ultimos_cuatro}"

        # 2. Confirmación atómica en PostgreSQL mediante fn_confirmar_pago_pedido
        res_db = pago_repos.ejecutar_confirmacion_pago(
            id_pedido=pedido["id_pedido"],
            tipo_metodo="TARJETA",
            codigo_transaccion=codigo_auth,
            monto=pedido["total"],
            id_usuario=id_usuario,
            nit_ci=body.nit_ci,
            razon_social=body.razon_social,
            tipo_documento="FACTURA" if (body.nit_ci and body.nit_ci.strip()) else "COMPROBANTE"
        )

        id_venta = res_db.get("id_venta")

        # 3. W29: Disparar envío de correo en background
        if id_venta:
            background_tasks.add_task(_enviar_comprobante_background, id_venta)

        return {
            "success": True,
            "message": "Pago con tarjeta aprobado y venta confirmada exitosamente.",
            "data": {
                "id_pedido": pedido["id_pedido"],
                "codigo_pedido": pedido["codigo_pedido"],
                "id_venta": id_venta,
                "numero_venta": res_db.get("numero_venta"),
                "tipo_documento": res_db.get("tipo_documento"),
                "total": pedido["total"],
                "metodo_pago": f"Tarjeta (terminada en {ultimos_cuatro})",
                "codigo_transaccion": codigo_auth,
                "url_descarga_pdf": f"/api/comprobantes/venta/{id_venta}/pdf"
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/qr/confirmar', summary="W27 + W29: Confirmar pago por QR Simple interoperable")
def confirmar_qr_endpoint(
    body: ProcesarQRDTO,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        pedido = pago_repos.validar_pedido_para_pago(body.id_pedido, id_usuario, body.id_empresa)

        import uuid
        codigo_transaccion = body.codigo_transaccion or f"QR-BCB-{uuid.uuid4().hex[:8].upper()}"

        # Confirmación atómica en PostgreSQL mediante fn_confirmar_pago_pedido con tipo_metodo="QR"
        res_db = pago_repos.ejecutar_confirmacion_pago(
            id_pedido=pedido["id_pedido"],
            tipo_metodo="QR",
            codigo_transaccion=codigo_transaccion,
            monto=pedido["total"],
            id_usuario=id_usuario,
            nit_ci=body.nit_ci,
            razon_social=body.razon_social,
            tipo_documento="FACTURA" if (body.nit_ci and body.nit_ci.strip()) else "COMPROBANTE"
        )

        id_venta = res_db.get("id_venta")
        if id_venta:
            background_tasks.add_task(_enviar_comprobante_background, id_venta)

        return {
            "success": True,
            "message": "Pago por QR Simple acreditado y venta confirmada exitosamente.",
            "data": {
                "id_pedido": pedido["id_pedido"],
                "codigo_pedido": pedido["codigo_pedido"],
                "id_venta": id_venta,
                "numero_venta": res_db.get("numero_venta"),
                "tipo_documento": res_db.get("tipo_documento"),
                "total": pedido["total"],
                "metodo_pago": "QR Simple Interoperable",
                "codigo_transaccion": codigo_transaccion,
                "url_descarga_pdf": f"/api/comprobantes/venta/{id_venta}/pdf"
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/cancelar', summary="Cancelar proceso de pago en curso")
def cancelar_pago_endpoint(
    body: CancelarPagoDTO,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        pedido = pago_repos.validar_pedido_para_pago(body.id_pedido, id_usuario)
        return {
            "success": True,
            "message": "Operación de pago cancelada. Tu pedido sigue reservado en estado PENDIENTE_PAGO.",
            "id_pedido": pedido["id_pedido"],
            "estado": pedido["estado"]
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
