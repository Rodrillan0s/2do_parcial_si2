import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.config import Config
from app.core.postgres import PostgreSQL
from app.core.security import verificar_token, verificar_token_opcional
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

class IniciarPagoDelegadoDTO(BaseModel):
    intent_id: str = Field(..., min_length=8, description="Identificador UUID único del intento offline generado en Dispositivo A")
    id_empresa: int = Field(..., gt=0, description="ID del Tenant")
    id_sucursal: Optional[int] = Field(None, gt=0, description="ID de la sucursal")
    monto_total: float = Field(..., gt=0, description="Monto total en BOB")
    items: Optional[list] = Field(default_factory=list, description="Lista de prendas del carrito")
    cliente_nombre: Optional[str] = Field(None, max_length=150)
    nit_ci: Optional[str] = Field(None, max_length=50)
    razon_social: Optional[str] = Field(None, max_length=150)
    id_pedido: Optional[int] = Field(None, gt=0)
    codigo_referencia: Optional[str] = Field(None, max_length=100)

class CapturarPagoDelegadoDTO(BaseModel):
    intent_id: str = Field(..., min_length=8, description="Identificador UUID del intento offline")
    order_id: str = Field(..., min_length=5, description="ID de la orden de PayPal")
    nit_ci: Optional[str] = Field(None, max_length=50)
    razon_social: Optional[str] = Field(None, max_length=150)

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

@router.post('/paypal/delegado/iniciar', summary="Iniciar orden de PayPal delegada desde otro dispositivo")
def iniciar_pago_delegado_endpoint(
    body: IniciarPagoDelegadoDTO,
    token_data: Optional[dict] = Depends(verificar_token_opcional)
):
    try:
        user_id = token_data.get('nro_usuario') or token_data.get('id_usuario') if token_data else None
        db = PostgreSQL()
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        try:
            if not user_id:
                row_u = db.execute_query(f"SELECT id_usuario FROM {schema}.t_usuario WHERE estado=TRUE ORDER BY id_usuario ASC LIMIT 1;", fetchone=True)
                user_id = row_u[0] if row_u else 3
            q_prev = f"""
                SELECT operation_id, status, response_json 
                FROM {schema}.t_sync_operacion 
                WHERE operation_id = %s 
                LIMIT 1;
            """
            prev = db.execute_query(q_prev, (body.intent_id,), fetchone=True)
            if prev:
                prev_status = prev[1]
                prev_json = prev[2] if isinstance(prev[2], dict) else json.loads(prev[2] or "{}")
                if prev_status in ('synced', 'completed'):
                    return {
                        "success": True,
                        "message": "La intención de pago ya fue completada y capturada previamente.",
                        "data": prev_json
                    }
                elif prev_status == 'pending' and prev_json.get("order_id"):
                    return {
                        "success": True,
                        "message": "Orden de PayPal existente en curso.",
                        "data": {
                            "intent_id": body.intent_id,
                            "order_id": prev_json.get("order_id"),
                            "approve_url": prev_json.get("approve_url"),
                            "monto_total": body.monto_total,
                            "monto_usd": prev_json.get("monto_usd")
                        }
                    }

            ref_codigo = body.codigo_referencia or f"DEL-{body.intent_id[:8].upper()}"
            frontend_base = getattr(Config, 'FRONTEND_URL', None) or 'http://localhost:4200'
            paypal_res = paypal_service.crear_orden_paypal(
                id_pedido=body.id_pedido,
                codigo_pedido=ref_codigo,
                monto_bob=body.monto_total,
                nombre_tienda="Aurora Store - Pago Delegado",
                return_url=f"{frontend_base.rstrip('/')}/pago-delegado/exito?intent_id={body.intent_id}",
                cancel_url=f"{frontend_base.rstrip('/')}/pago-delegado/cancelado?intent_id={body.intent_id}"
            )

            resp_payload = {
                "order_id": paypal_res.get("order_id"),
                "approve_url": paypal_res.get("approve_url"),
                "monto_total": body.monto_total,
                "monto_usd": paypal_res.get("monto_usd"),
                "items": body.items,
                "id_sucursal": body.id_sucursal,
                "id_empresa": body.id_empresa,
                "cliente_nombre": body.cliente_nombre,
                "nit_ci": body.nit_ci,
                "razon_social": body.razon_social,
                "id_pedido": body.id_pedido,
                "codigo_referencia": ref_codigo,
                "estado": "ESPERANDO_APROBACION"
            }

            now = datetime.now(timezone.utc)
            q_upsert = f"""
                INSERT INTO {schema}.t_sync_operacion (
                    operation_id, id_usuario, id_empresa, kind, status, http_status, response_json, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (id_usuario, id_empresa, operation_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    http_status = EXCLUDED.http_status,
                    response_json = EXCLUDED.response_json,
                    updated_at = EXCLUDED.updated_at;
            """
            db.execute_query(
                q_upsert,
                (
                    body.intent_id,
                    user_id,
                    body.id_empresa,
                    "PAYPAL_OFFLINE_DELEGADO",
                    "pending",
                    202,
                    json.dumps(resp_payload),
                    now,
                    now
                ),
                commit=True
            )

            return {
                "success": True,
                "message": "Orden de PayPal creada para pago delegado.",
                "data": {
                    "intent_id": body.intent_id,
                    "order_id": paypal_res.get("order_id"),
                    "approve_url": paypal_res.get("approve_url"),
                    "monto_total": body.monto_total,
                    "monto_usd": paypal_res.get("monto_usd")
                }
            }
        finally:
            db.close_connection()
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PAYPAL DELEGADO INICIAR ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/paypal/delegado/capturar', summary="Capturar pago de PayPal delegado desde el segundo dispositivo")
def capturar_pago_delegado_endpoint(
    body: CapturarPagoDelegadoDTO,
    background_tasks: BackgroundTasks,
    token_data: Optional[dict] = Depends(verificar_token_opcional)
):
    try:
        db = PostgreSQL()
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        try:
            q_op = f"""
                SELECT operation_id, id_usuario, id_empresa, status, response_json 
                FROM {schema}.t_sync_operacion 
                WHERE operation_id = %s 
                LIMIT 1;
            """
            op = db.execute_query(q_op, (body.intent_id,), fetchone=True)
            if not op:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intención de pago delegado no encontrada.")

            curr_status = op[3]
            resp_json = op[4] if isinstance(op[4], dict) else json.loads(op[4] or "{}")

            if curr_status in ('synced', 'completed'):
                return {
                    "success": True,
                    "message": "El pago ya se encuentra capturado y confirmado previamente.",
                    "data": resp_json
                }

            captura = paypal_service.capturar_orden_paypal(body.order_id)
            if not captura.get("success") or captura.get("status") != "COMPLETED":
                err_msg = captura.get("message") or "El proveedor PayPal no confirmó la transacción."
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

            capture_id = captura.get("capture_id") or f"PAYPAL-{body.order_id}"
            now_iso = datetime.now(timezone.utc).isoformat()
            total_monto = float(resp_json.get("monto_total") or 0.0)
            id_pedido = resp_json.get("id_pedido")

            id_venta = None
            numero_venta = None

            if id_pedido:
                try:
                    res_pago = pago_repos.ejecutar_confirmacion_pago(
                        id_pedido=int(id_pedido),
                        tipo_metodo="PAYPAL",
                        codigo_transaccion=capture_id,
                        monto=total_monto,
                        id_usuario=op[1],
                        nit_ci=body.nit_ci or resp_json.get("nit_ci"),
                        razon_social=body.razon_social or resp_json.get("razon_social"),
                        tipo_documento="FACTURA" if (body.nit_ci or resp_json.get("nit_ci")) else "COMPROBANTE"
                    )
                    id_venta = res_pago.get("id_venta")
                    numero_venta = res_pago.get("numero_venta")
                    if id_venta:
                        background_tasks.add_task(_enviar_comprobante_background, id_venta)
                except Exception as ex_pago:
                    logger.warning(f"[PAYPAL DELEGADO PEDIDO CONFIRMATION WARNING] {ex_pago}")

            result_data = {
                "success": True,
                "status": "COMPLETED",
                "intent_id": body.intent_id,
                "order_id": body.order_id,
                "capture_id": capture_id,
                "monto_total": total_monto,
                "id_pedido": id_pedido,
                "id_venta": id_venta,
                "numero_venta": numero_venta,
                "metodo_pago": "PayPal",
                "fecha_pago": now_iso
            }

            now = datetime.now(timezone.utc)
            q_upd = f"""
                UPDATE {schema}.t_sync_operacion 
                SET status = 'synced',
                    http_status = 200,
                    conflict_code = NULL,
                    response_json = %s::jsonb,
                    updated_at = %s
                WHERE operation_id = %s;
            """
            db.execute_query(q_upd, (json.dumps(result_data), now, body.intent_id), commit=True)

            return {
                "success": True,
                "message": "Pago con PayPal completado y capturado exitosamente.",
                "data": result_data
            }
        finally:
            db.close_connection()
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PAYPAL DELEGADO CAPTURAR ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/paypal/delegado/estado/{intent_id}', summary="Consultar estado de la intención de pago delegada")
def consultar_estado_pago_delegado(
    intent_id: str,
    token_data: Optional[dict] = Depends(verificar_token_opcional)
):
    db = PostgreSQL()
    db.create_connection()
    schema = Config.SCHEMA or 'comercio'
    try:
        q = f"""
            SELECT operation_id, status, http_status, conflict_code, response_json 
            FROM {schema}.t_sync_operacion 
            WHERE operation_id = %s 
            LIMIT 1;
        """
        row = db.execute_query(q, (intent_id,), fetchone=True)
        if not row:
            return {
                "success": False,
                "status": "NO_ENCONTRADO",
                "capturado": False,
                "message": "La intención de pago delegado no fue encontrada o aún no ha sido registrada."
            }

        st = row[1]
        data = row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}")

        if st in ('synced', 'completed'):
            return {
                "success": True,
                "status": "COMPLETADO",
                "capturado": True,
                "message": "Pago verificado y capturado exitosamente en el servidor.",
                "data": data
            }
        elif st == 'pending':
            return {
                "success": True,
                "status": "PENDIENTE",
                "capturado": False,
                "message": "Esperando aprobación y captura en el dispositivo remoto.",
                "data": data
            }
        else:
            return {
                "success": False,
                "status": "CONFLICTO",
                "capturado": False,
                "conflict_code": row[3],
                "message": data.get("message") or "Incidencia en el procesamiento del pago delegado.",
                "data": data
            }
    finally:
        db.close_connection()
