import logging
import secrets
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, Any, Optional
from app.core.config import Config

logger = logging.getLogger(__name__)

# Tasa de cambio referencial BOB a USD para PayPal Sandbox
TASA_CAMBIO_BOB_USD = 6.96

def obtener_access_token() -> str:
    """
    Obtiene un Bearer token de autenticación de PayPal API v2 OAuth2.
    """
    client_id = Config.PAYPAL_CLIENT_ID
    client_secret = Config.PAYPAL_CLIENT_SECRET
    base_url = Config.PAYPAL_BASE_URL or "https://api-m.sandbox.paypal.com"

    if not client_id or not client_secret:
        raise ValueError("Credenciales de PayPal no configuradas en el servidor.")

    url = f"{base_url}/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "es_BO"
    }
    data = {"grant_type": "client_credentials"}

    try:
        res = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(client_id, client_secret), timeout=10)
        if res.status_code != 200:
            logger.error(f"[PAYPAL AUTH ERROR] Status {res.status_code}: {res.text}")
            raise ValueError("Error al autenticarse con el proveedor de pagos PayPal.")
        
        token_data = res.json()
        return token_data.get("access_token")
    except requests.RequestException as e:
        logger.error(f"[PAYPAL CONNECTION ERROR] {e}")
        raise ValueError(f"Fallo de conexión con PayPal: {str(e)}")

def crear_orden_paypal(
    id_pedido: Optional[int] = None,
    codigo_pedido: Optional[str] = None,
    monto_bob: Optional[float] = None,
    nombre_tienda: str = "AURA Atelier",
    return_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
    descripcion: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea una orden de pago en PayPal con Intent CAPTURE.
    Soporta pagos de pedidos de ecommerce y contrataciones SaaS.
    Convierte el monto de Bolivianos a USD para la pasarela internacional.
    """
    # Resolver monto compatible con monto_bob o monto_bs
    if monto_bob is None:
        monto_bob = float(kwargs.get("monto_bs") or kwargs.get("monto") or 0.0)

    # Resolver referencia
    ref_codigo = codigo_pedido or kwargs.get("id_pedido_referencia") or ""
    if not ref_codigo and id_pedido:
        ref_codigo = f"PED-{id_pedido}"
    elif not ref_codigo:
        ref_codigo = f"ORD-{secrets.token_hex(4).upper()}"

    ref_id = f"PED-{id_pedido}" if id_pedido else f"AUR-{ref_codigo[:15]}"
    custom_id = str(id_pedido if id_pedido else ref_codigo)
    desc = descripcion or f"{nombre_tienda} — Pago {ref_codigo}"

    frontend_base = getattr(Config, 'FRONTEND_URL', None) or 'http://localhost:4200'
    final_return_url = return_url or (f"{frontend_base.rstrip('/')}/pago/{id_pedido}" if id_pedido else f"{frontend_base.rstrip('/')}/saas/planes")
    final_cancel_url = cancel_url or (f"{frontend_base.rstrip('/')}/pago/{id_pedido}" if id_pedido else f"{frontend_base.rstrip('/')}/saas/planes")

    token = obtener_access_token()
    base_url = Config.PAYPAL_BASE_URL or "https://api-m.sandbox.paypal.com"
    url = f"{base_url}/v2/checkout/orders"

    monto_usd = round(monto_bob / TASA_CAMBIO_BOB_USD, 2)
    if monto_usd <= 0:
        monto_usd = 0.50

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": ref_id,
                "description": desc[:127],
                "custom_id": custom_id[:127],
                "amount": {
                    "currency_code": "USD",
                    "value": f"{monto_usd:.2f}"
                }
            }
        ],
        "application_context": {
            "brand_name": (nombre_tienda or "AuroraStore")[:127],
            "landing_page": "NO_PREFERENCE",
            "user_action": "PAY_NOW",
            "return_url": final_return_url,
            "cancel_url": final_cancel_url
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        if res.status_code not in (200, 201):
            logger.error(f"[PAYPAL CREATE ORDER ERROR] Status {res.status_code}: {res.text}")
            raise ValueError(f"No fue posible crear la orden en PayPal ({res.status_code}): {res.text}")

        order_data = res.json()
        order_id = order_data.get("id")

        approve_url = None
        for link in order_data.get("links", []):
            if link.get("rel") == "approve":
                approve_url = link.get("href")
                break

        return {
            "success": True,
            "order_id": order_id,
            "status": order_data.get("status"),
            "approve_url": approve_url,
            "monto_bob": monto_bob,
            "monto_bs": monto_bob,
            "monto_usd": monto_usd
        }
    except requests.RequestException as e:
        logger.error(f"[PAYPAL ORDER EXCEPTION] {e}")
        raise ValueError(f"Error comunicando con PayPal: {str(e)}")

def capturar_orden_paypal(paypal_order_id: str) -> Dict[str, Any]:
    """
    Captura los fondos de una orden aprobada por el cliente en PayPal.
    Verifica que el estado final sea 'COMPLETED'.
    """
    token = obtener_access_token()
    base_url = Config.PAYPAL_BASE_URL or "https://api-m.sandbox.paypal.com"
    url = f"{base_url}/v2/checkout/orders/{paypal_order_id}/capture"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        res = requests.post(url, headers=headers, timeout=15)
        res_data = res.json()

        if res.status_code in (200, 201):
            status = res_data.get("status")
            if status == "COMPLETED":
                # Extraer ID de captura de purchase_units
                capture_id = None
                try:
                    purchase_units = res_data.get("purchase_units", [])
                    if purchase_units:
                        captures = purchase_units[0].get("payments", {}).get("captures", [])
                        if captures:
                            capture_id = captures[0].get("id")
                except Exception:
                    pass

                return {
                    "success": True,
                    "status": "COMPLETED",
                    "order_id": paypal_order_id,
                    "capture_id": capture_id or f"CAP-{paypal_order_id[:12]}",
                    "data": res_data
                }
            else:
                return {
                    "success": False,
                    "status": status,
                    "message": f"El pago de PayPal no se completó (estado: {status}).",
                    "data": res_data
                }
        else:
            # Manejo idempotente de ORDER_ALREADY_CAPTURED si ya fue capturado previamente
            is_already_captured = False
            is_not_approved = False
            for detail in res_data.get("details", []):
                if detail.get("issue") == "ORDER_ALREADY_CAPTURED":
                    is_already_captured = True
                    break
                if detail.get("issue") == "ORDER_NOT_APPROVED":
                    is_not_approved = True

            if is_not_approved:
                logger.warning(f"[PAYPAL ORDER NOT APPROVED] Orden {paypal_order_id} no ha sido autorizada en PayPal.")
                return {
                    "success": False,
                    "status": "ORDER_NOT_APPROVED",
                    "message": "La orden no ha sido aprobada en PayPal. Debes autorizar el pago en la ventana de PayPal antes de confirmar.",
                    "data": res_data
                }

            if is_already_captured:
                try:
                    get_url = f"{base_url}/v2/checkout/orders/{paypal_order_id}"
                    get_res = requests.get(get_url, headers=headers, timeout=10)
                    if get_res.status_code == 200:
                        get_data = get_res.json()
                        if get_data.get("status") == "COMPLETED":
                            capture_id = None
                            try:
                                purchase_units = get_data.get("purchase_units", [])
                                if purchase_units:
                                    captures = purchase_units[0].get("payments", {}).get("captures", [])
                                    if captures:
                                        capture_id = captures[0].get("id")
                            except Exception:
                                pass
                            return {
                                "success": True,
                                "status": "COMPLETED",
                                "order_id": paypal_order_id,
                                "capture_id": capture_id or f"CAP-{paypal_order_id[:12]}",
                                "already_captured": True,
                                "data": get_data
                            }
                except Exception as ex_get:
                    logger.warning(f"Error consultando orden ya capturada: {ex_get}")

            err_msg = res_data.get("message") or "Error capturando la orden de PayPal."
            logger.error(f"[PAYPAL CAPTURE ERROR] Status {res.status_code}: {res.text}")
            return {
                "success": False,
                "status": "ERROR",
                "message": err_msg,
                "detail": res_data
            }
    except requests.RequestException as e:
        logger.error(f"[PAYPAL CAPTURE EXCEPTION] {e}")
        raise ValueError(f"Error de red al capturar orden de PayPal: {str(e)}")


def reembolsar_captura_paypal(
    capture_id: str,
    monto_usd: Optional[float] = None,
    nota: Optional[str] = None
) -> Dict[str, Any]:
    """
    Emite un reembolso formal en PayPal REST API v2 sobre una captura confirmada.
    Endpoint: POST /v2/payments/captures/{capture_id}/refund
    """
    token = obtener_access_token()
    base_url = Config.PAYPAL_BASE_URL or "https://api-m.sandbox.paypal.com"
    url = f"{base_url}/v2/payments/captures/{capture_id}/refund"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload: Dict[str, Any] = {
        "note_to_payer": (nota or "Reembolso por garantía comercial - AuroraStore SaaS")[:255]
    }
    if monto_usd and monto_usd > 0:
        payload["amount"] = {
            "value": f"{monto_usd:.2f}",
            "currency_code": "USD"
        }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        res_data = res.json()

        if res.status_code in (200, 201):
            refund_id = res_data.get("id")
            status = res_data.get("status")
            logger.info(f"[PAYPAL REFUND SUCCESS] Reembolso {refund_id} aprobado para captura {capture_id}.")
            return {
                "success": True,
                "refund_id": refund_id,
                "status": status,
                "data": res_data
            }
        else:
            err_msg = res_data.get("message") or f"Error en PayPal al reembolsar ({res.status_code})"
            logger.error(f"[PAYPAL REFUND ERROR] Status {res.status_code}: {res.text}")
            return {
                "success": False,
                "status": "ERROR",
                "message": err_msg,
                "detail": res_data
            }
    except requests.RequestException as e:
        logger.error(f"[PAYPAL REFUND EXCEPTION] {e}")
        return {
            "success": False,
            "status": "EXCEPTION",
            "message": str(e)
        }
