import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
from app.core.config import Config
from app.core.postgres import PostgreSQL, transaction
from app.core.security import verificar_token, tiene_permiso
from app.core.commerce_tenant import resolver_empresa_compra
from app.modules.ecommerce.repos import carrito_repos
from app.modules.reservas.repos import reserva_repos
from app.modules.pos.repos import pos_repos, caja_repos, caja_pago_repos

router = APIRouter(prefix="/api/sync", tags=["Sincronización Offline-First (PWA & Mobile)"])

class SyncOperationItemDTO(BaseModel):
    operation_id: str = Field(..., min_length=6, max_length=64, description="UUID idempotente único por operación")
    kind: str = Field(
        ...,
        description="CART_ADD_ITEM | CART_UPDATE_QTY | CART_REMOVE_ITEM | CART_CLEAR | RESERVA_SOLICITUD | VENTA_CONTADO",
    )
    tenant_id: Optional[int] = Field(None, description="ID de la empresa/tenant")
    branch_id: Optional[int] = Field(None, description="ID de sucursal cuando aplique")
    entity_id: Optional[Any] = Field(None, description="ID de entidad o clave local")
    client_version: Optional[Any] = Field(None, description="Versión o timestamp conocido por el cliente")
    created_at: Optional[str] = Field(None, description="Timestamp ISO de creación en el cliente")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Datos validados de la operación")


class SyncBatchRequestDTO(BaseModel):
    operations: List[SyncOperationItemDTO] = Field(..., min_length=1, max_length=50)


def _resultado_no_confirmado(op, code, message, http_status=503):
    return {
        "operation_id": op.operation_id,
        "kind": op.kind.strip().upper(),
        "status": "failed_retryable",
        "http_status": http_status,
        "conflict_code": code,
        "message": message,
        "confirmation_verified": False,
        "reconciliation_required": op.kind.strip().upper() == "VENTA_CONTADO",
    }


def _procesar_operacion_individual(op: SyncOperationItemDTO, token_data: dict) -> Dict[str, Any]:
    """One durable receipt and all business effects share a single commit.

    The transaction lock covers absent rows too, across processes and servers.
    The savepoint rolls back rejected business effects without releasing that lock.
    A reply is constructed inside the transaction but returned only after COMMIT.
    """
    schema = Config.SCHEMA or "comercio"
    kind = op.kind.strip().upper()
    user_id = int(token_data.get("nro_usuario") or token_data.get("id_usuario") or 0)
    try:
        with transaction() as db:
            requested = op.tenant_id or op.payload.get("id_empresa")
            empresa = resolver_empresa_compra(token_data, int(requested) if requested is not None else None)
            # Recheck current authority even for a replay; client tenant is only context.
            if kind in ("VENTA_CONTADO", "RESERVA_SOLICITUD"):
                from app.modules.saas.services.saas_services import exigir_vigencia
                exigir_vigencia(empresa)
            if kind == "VENTA_CONTADO":
                from app.core.tenant_guard import obtener_sucursales_autorizadas
                roles = {str(r).upper() for r in token_data.get("roles", [])}
                roles.add(str(token_data.get("nombre_rol") or token_data.get("rol") or "").upper())
                allowed = (tiene_permiso(token_data, "pos.vender") or tiene_permiso(token_data, "pos.cobrar")
                           or tiene_permiso(token_data, "caja.ver") or bool(roles.intersection(
                               {"ADMIN_EMPRESA", "ADMINISTRADOR", "SUPERADMIN", "CAJERO", "VENDEDOR", "ENCARGADO"})))
                if not allowed or roles == {"CLIENTE"}:
                    return {**_resultado_no_confirmado(op, "ROLE_FORBIDDEN", "Acceso POS denegado.", 403), "status": "conflict"}
                branch = int(op.payload.get("id_sucursal") or op.branch_id or token_data.get("id_sucursal") or 0)
                permitted = obtener_sucursales_autorizadas(token_data)
                if permitted is not None and branch not in permitted:
                    raise HTTPException(403, "Sucursal no autorizada.")

            db.execute_query("SET LOCAL lock_timeout = '5s'; SET LOCAL synchronous_commit = on")
            scope = json.dumps([schema, user_id, empresa, op.operation_id], separators=(",", ":"))
            db.execute_query("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (scope,))
            # Selecting request_hash also checks that BOTH required migrations exist.
            previous = db.execute_query(
                f"SELECT kind, status, request_hash, response_json FROM {schema}.t_sync_operacion "
                "WHERE id_usuario=%s AND id_empresa=%s AND operation_id=%s FOR UPDATE",
                (user_id, empresa, op.operation_id), fetchone=True,
            )
            boundary = db.execute_query(
                f"SELECT inicio_garantia FROM {schema}.t_sync_control WHERE id=1", fetchone=True,
            )
            if not boundary:
                raise RuntimeError("Falta el control de inicio de la garantía persistente.")
            canonical = json.dumps({"kind": kind, "branch_id": op.branch_id, "entity_id": op.entity_id,
                                    "payload": op.payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if previous:
                if previous[0] != kind or (previous[1] == "synced" and previous[2] and previous[2] != fingerprint):
                    return {**_resultado_no_confirmado(op, "IDEMPOTENCY_KEY_REUSED",
                            "La clave pertenece a otra operación o contenido confirmado.", 409), "status": "conflict"}
                if not previous[2]:
                    return {**_resultado_no_confirmado(op, "LEGACY_RECEIPT_REQUIRES_REVIEW",
                            "Registro previo sin huella verificable; conservar y conciliar antes de reenviar.", 409), "status": "conflict"}
                if previous[1] == "synced":
                    receipt = previous[3] if isinstance(previous[3], dict) else json.loads(previous[3])
                    return {**receipt, "idempotent_replay": True, "confirmation_verified": True}

            if not previous and kind in ("VENTA_CONTADO", "RESERVA_SOLICITUD"):
                try:
                    created = datetime.fromisoformat((op.created_at or "").replace("Z", "+00:00"))
                    if created.tzinfo is None or created < boundary[0]:
                        raise ValueError("Operación anterior al inicio de la garantía.")
                except (ValueError, TypeError):
                    return {**_resultado_no_confirmado(op, "LEGACY_OPERATION_REQUIRES_REVIEW",
                            "No hay recibo verificable de esta operación previa o sin fecha válida. Conserve y concilie la operación.", 409), "status": "conflict"}

            db.cur.execute("SAVEPOINT sync_effects")
            # Lock inventory in stable order before validation, including across
            # different operation IDs. Tenant join prevents cross-company locks.
            if kind in ("VENTA_CONTADO", "RESERVA_SOLICITUD"):
                branch = int(op.payload.get("id_sucursal") or op.branch_id or token_data.get("id_sucursal") or 0)
                items = op.payload.get("items") or []
                variants = [int(it.get("id_variante") or 0) for it in items]
                if len(variants) != len(set(variants)):
                    result = {**_resultado_no_confirmado(op, "INVALID_PAYLOAD", "Combine las cantidades de variantes repetidas.", 400), "status": "failed_permanent"}
                else:
                    if kind == "VENTA_CONTADO":
                        db.execute_query(
                            f"SELECT id_sesion_caja FROM {schema}.t_caja_sesion "
                            "WHERE id_usuario=%s AND id_empresa=%s AND id_sucursal=%s AND estado='ABIERTA' "
                            "ORDER BY id_sesion_caja FOR UPDATE", (user_id, empresa, branch), fetchall=True,
                        )
                    db.execute_query(
                        f"SELECT inv.id_inventario FROM {schema}.t_inventario inv "
                        f"JOIN {schema}.t_sucursal s ON s.id_sucursal=inv.id_sucursal "
                        "WHERE s.id_empresa=%s AND inv.id_sucursal=%s AND inv.id_variante=ANY(%s) "
                        "ORDER BY inv.id_variante, inv.id_inventario FOR UPDATE OF inv",
                        (empresa, branch, variants), fetchall=True,
                    )
                    result = _aplicar_operacion(op, token_data, empresa, db=db)
            else:
                result = _aplicar_operacion(op, token_data, empresa, db=db)
            if result.get("status") != "synced":
                db.cur.execute("ROLLBACK TO SAVEPOINT sync_effects")
                db._rollback_only = False
                result["confirmation_verified"] = False
            elif getattr(db, "_rollback_only", False):
                raise RuntimeError("No se puede confirmar una operación con errores de persistencia.")
            else:
                result["confirmation_verified"] = True
                result["confirmation"] = {"operation_id": op.operation_id, "id_usuario": user_id,
                                          "id_empresa": empresa, "request_hash": fingerprint}
            db.cur.execute("RELEASE SAVEPOINT sync_effects")
            db.execute_query(
                f"INSERT INTO {schema}.t_sync_operacion "
                "(operation_id,id_usuario,id_empresa,kind,status,http_status,conflict_code,response_json,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) "
                "ON CONFLICT (id_usuario,id_empresa,operation_id) DO UPDATE SET "
                "status=EXCLUDED.status,http_status=EXCLUDED.http_status,conflict_code=EXCLUDED.conflict_code,"
                "response_json=EXCLUDED.response_json,request_hash=EXCLUDED.request_hash,updated_at=now()",
                (op.operation_id, user_id, empresa, kind, result["status"], result["http_status"],
                 result.get("conflict_code"), json.dumps(result), fingerprint),
            )
        return result
    except HTTPException as exc:
        return {**_resultado_no_confirmado(op, "TENANT_FORBIDDEN", str(exc.detail), exc.status_code), "status": "conflict"}
    except Exception:
        logger.exception("Sync sin confirmación persistente: %s", op.operation_id)
        return _resultado_no_confirmado(op, "PERSISTENT_IDEMPOTENCY_UNAVAILABLE",
                                      "No hay confirmación durable. Conserve la operación y reintente con la misma clave.")


def _obtener_stock_sucursal_variante(schema: str, id_variante: int, id_sucursal: int, id_empresa: int) -> int:
    db = PostgreSQL()
    db.create_connection()
    if not db.conn:
        return 0
    try:
        row = db.execute_query(
            f"""
            SELECT COALESCE(SUM(GREATEST(0, inv.stock_disponible)), 0)
            FROM {schema}.t_inventario inv
            JOIN {schema}.t_sucursal s ON s.id_sucursal = inv.id_sucursal
            WHERE inv.id_variante = %s
              AND inv.id_sucursal = %s
              AND s.id_empresa = %s
              AND COALESCE(s.activo, TRUE) = TRUE
              AND (s.estado IS NULL OR s.estado::text IN ('true', 'TRUE', 't', '1', 'ACTIVO', 'ACTIVA'))
              AND COALESCE(inv.estado, TRUE) = TRUE;
            """,
            (id_variante, id_sucursal, id_empresa),
            fetchone=True,
        )
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        db.close_connection()


def _verificar_sucursal_activa_empresa(schema: str, id_sucursal: int, id_empresa: int) -> Optional[Dict[str, Any]]:
    if id_sucursal <= 0:
        return None
    db = PostgreSQL()
    db.create_connection()
    if not db.conn:
        return None
    try:
        row = db.execute_query(
            f"""
            SELECT id_sucursal, nombre, activo, estado
            FROM {schema}.t_sucursal
            WHERE id_sucursal = %s AND id_empresa = %s
            LIMIT 1;
            """,
            (id_sucursal, id_empresa),
            fetchone=True,
        )
        if not row:
            return None
        activo_col = bool(row[2]) if row[2] is not None else True
        estado_val = row[3]
        if isinstance(estado_val, bool):
            estado_ok = estado_val
        elif estado_val is not None:
            estado_ok = str(estado_val).upper() in ("ACTIVO", "TRUE", "1", "ACTIVA")
        else:
            estado_ok = True
        activa = activo_col and estado_ok
        return {
            "id_sucursal": int(row[0]),
            "nombre": row[1],
            "activa": activa,
        }
    finally:
        db.close_connection()


def _resolver_metodo_pago_efectivo(schema: str, requested_id_metodo: Optional[int] = None) -> Dict[str, Any]:
    """
    Resuelve o valida el método de pago para ventas offline.
    Si requested_id_metodo apunta a un método electrónico (TARJETA, QR, PAYPAL), lo retorna con su tipo real
    para que el validador lo rechace con PAYMENT_REQUIRES_ONLINE.
    Si no se especificó id_metodo_pago o se pidió EFECTIVO, retorna el método EFECTIVO activo.
    """
    db = PostgreSQL()
    db.create_connection()
    if not db.conn:
        raise RuntimeError("No se pudo conectar a PostgreSQL para validar método de pago.")
    try:
        if requested_id_metodo and int(requested_id_metodo) > 0:
            row = db.execute_query(
                f"""
                SELECT id_metodo_pago, nombre, UPPER(tipo), estado
                FROM {schema}.t_metodo_pago
                WHERE id_metodo_pago = %s
                LIMIT 1;
                """,
                (int(requested_id_metodo),),
                fetchone=True,
            )
            if row:
                return {
                    "id_metodo_pago": int(row[0]),
                    "codigo": str(row[2]).upper(),
                    "nombre": row[1],
                    "tipo": str(row[2]).upper(),
                    "activo": bool(row[3]),
                }

        row_ef = db.execute_query(
            f"""
            SELECT id_metodo_pago, nombre, UPPER(tipo), estado
            FROM {schema}.t_metodo_pago
            WHERE UPPER(tipo) = 'EFECTIVO'
              AND COALESCE(estado, TRUE) = TRUE
            ORDER BY id_metodo_pago ASC
            LIMIT 1;
            """,
            fetchone=True,
        )
        if row_ef:
            return {
                "id_metodo_pago": int(row_ef[0]),
                "codigo": "EFECTIVO",
                "nombre": row_ef[1],
                "tipo": "EFECTIVO",
                "activo": bool(row_ef[3]),
            }

        # Si el entorno de pruebas aislado aún no tiene la semilla EFECTIVO en t_metodo_pago, crearla
        ins = db.execute_query(
            f"""
            INSERT INTO {schema}.t_metodo_pago (nombre, tipo, estado)
            VALUES ('Efectivo en Caja', 'EFECTIVO', TRUE)
            RETURNING id_metodo_pago, nombre, tipo, estado;
            """,
            fetchone=True,
            commit=True,
        )
        return {
            "id_metodo_pago": int(ins[0]),
            "codigo": "EFECTIVO",
            "nombre": ins[1],
            "tipo": "EFECTIVO",
            "activo": bool(ins[3]),
        }
    finally:
        db.close_connection()


def _aplicar_operacion(op: SyncOperationItemDTO, token_data: dict, empresa_id: int, db: Optional[Any] = None) -> Dict[str, Any]:
    schema = Config.SCHEMA or "comercio"
    id_usuario = int(token_data.get("nro_usuario") or token_data.get("id_usuario") or 0)
    if not id_usuario:
        return {
            "operation_id": op.operation_id,
            "kind": op.kind,
            "status": "failed_permanent",
            "http_status": 401,
            "conflict_code": "UNAUTHORIZED",
            "message": "Sesión no válida o expirada.",
        }

    kind = (op.kind or "").strip().upper()
    payload = op.payload or {}

    requested_tenant = empresa_id

    try:
        # ======================================================================
        # CASO 1: CARRITO — AGREGAR / FIJAR CANTIDAD DE PRENDA (CU08W)
        # ======================================================================
        if kind == "CART_ADD_ITEM":
            id_variante = int(payload.get("id_variante") or 0)
            cantidad = int(payload.get("cantidad") or 1)
            expected_price = payload.get("expected_unit_price")
            mode = str(payload.get("mode") or "ADD").upper()

            if id_variante <= 0 or cantidad <= 0:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "failed_permanent",
                    "http_status": 400,
                    "conflict_code": "INVALID_PAYLOAD",
                    "message": "Variante y cantidad (> 0) son obligatorias.",
                }

            var_data = carrito_repos.obtener_datos_variante_tenant(id_variante, empresa_id)
            if not var_data:
                res_conf = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 409,
                    "conflict_code": "PRODUCT_INACTIVE",
                    "message": "La prenda seleccionada no existe o no pertenece a esta tienda.",
                }
                return res_conf

            if not var_data["producto_activo"] or not var_data["variante_activa"]:
                res_conf = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 409,
                    "conflict_code": "PRODUCT_INACTIVE",
                    "message": f"La prenda '{var_data['producto_nombre']}' fue desactivada mientras estabas sin conexión.",
                    "conflict_detail": {"id_variante": id_variante, "producto_nombre": var_data["producto_nombre"]},
                }
                return res_conf

            if expected_price is not None:
                try:
                    exp_p = round(float(expected_price), 2)
                    cur_p = round(float(var_data["precio_vigente"]), 2)
                    if abs(exp_p - cur_p) >= 0.01 and not payload.get("accept_price_change"):
                        res_conf = {
                            "operation_id": op.operation_id,
                            "kind": kind,
                            "status": "conflict",
                            "http_status": 409,
                            "conflict_code": "PRICE_CHANGED",
                            "message": f"El precio de '{var_data['producto_nombre']}' cambió de Bs. {exp_p:.2f} a Bs. {cur_p:.2f}.",
                            "conflict_detail": {
                                "id_variante": id_variante,
                                "producto_nombre": var_data["producto_nombre"],
                                "expected_unit_price": exp_p,
                                "current_unit_price": cur_p,
                            },
                        }
                        return res_conf
                except (TypeError, ValueError):
                    pass

            stock_disp = carrito_repos.obtener_stock_total_variante(id_variante, empresa_id)
            if stock_disp < cantidad:
                res_conf = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 409,
                    "conflict_code": "STOCK_INSUFFICIENT",
                    "message": (
                        f"Stock insuficiente para '{var_data['producto_nombre']}'. "
                        f"Solicitaste {cantidad} y hay {stock_disp} disponible(s)."
                    ),
                    "conflict_detail": {
                        "id_variante": id_variante,
                        "producto_nombre": var_data["producto_nombre"],
                        "requested_quantity": cantidad,
                        "available_stock": stock_disp,
                    },
                }
                return res_conf

            # Si mode == 'SET', fijar la cantidad exacta para evitar duplicar en reintentos
            if mode == "SET":
                carrito_actual = carrito_repos.consultar_carrito_completo(id_usuario, empresa_id)
                existente = next(
                    (it for it in carrito_actual.get("items", []) if int(it["id_variante"]) == id_variante),
                    None,
                )
                if existente:
                    carrito = carrito_repos.actualizar_cantidad_item(
                        id_usuario=id_usuario,
                        id_empresa=empresa_id,
                        id_detalle_carrito=int(existente["id_detalle_carrito"]),
                        nueva_cantidad=cantidad,
                    )
                else:
                    carrito = carrito_repos.agregar_item_al_carrito(
                        id_usuario=id_usuario,
                        id_empresa=empresa_id,
                        id_variante=id_variante,
                        cantidad=cantidad,
                    )
            else:
                try:
                    carrito = carrito_repos.agregar_item_al_carrito(
                        id_usuario=id_usuario,
                        id_empresa=empresa_id,
                        id_variante=id_variante,
                        cantidad=cantidad,
                    )
                except ValueError as ve:
                    res_conf = {
                        "operation_id": op.operation_id,
                        "kind": kind,
                        "status": "conflict",
                        "http_status": 409,
                        "conflict_code": "STOCK_INSUFFICIENT",
                        "message": str(ve),
                        "conflict_detail": {
                            "id_variante": id_variante,
                            "available_stock": stock_disp,
                        },
                    }
                    return res_conf

            res_ok = {
                "operation_id": op.operation_id,
                "kind": kind,
                "status": "synced",
                "http_status": 200,
                "conflict_code": None,
                "message": "Prenda sincronizada en tu bolsa de compras.",
                "data": carrito,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "idempotent_replay": False,
            }
            return res_ok

        # ======================================================================
        # CASO 2: CARRITO — ACTUALIZAR CANTIDAD (CU08W)
        # ======================================================================
        elif kind == "CART_UPDATE_QTY":
            id_detalle = int(payload.get("id_detalle_carrito") or 0)
            id_variante = int(payload.get("id_variante") or 0)
            cantidad = int(payload.get("cantidad") or 1)

            if cantidad <= 0:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "failed_permanent",
                    "http_status": 400,
                    "conflict_code": "INVALID_PAYLOAD",
                    "message": "La cantidad debe ser mayor a 0.",
                }

            # Si el ítem se creó offline con id_detalle negativo, resolver por id_variante
            if id_detalle <= 0 and id_variante > 0:
                carrito_actual = carrito_repos.consultar_carrito_completo(id_usuario, empresa_id)
                existente = next(
                    (it for it in carrito_actual.get("items", []) if int(it["id_variante"]) == id_variante),
                    None,
                )
                if existente:
                    id_detalle = int(existente["id_detalle_carrito"])
                else:
                    sub_op = SyncOperationItemDTO(
                        operation_id=op.operation_id,
                        kind="CART_ADD_ITEM",
                        tenant_id=empresa_id,
                        payload={"id_variante": id_variante, "cantidad": cantidad, "mode": "SET"},
                    )
                    # Reuse business logic, keeping the original receipt identity
                    # and the coordinator's single transaction/savepoint.
                    result = _aplicar_operacion(sub_op, token_data, empresa_id)
                    return {**result, "kind": kind}

            try:
                carrito = carrito_repos.actualizar_cantidad_item(
                    id_usuario=id_usuario,
                    id_empresa=empresa_id,
                    id_detalle_carrito=id_detalle,
                    nueva_cantidad=cantidad,
                )
            except ValueError as ve:
                stock_disp = carrito_repos.obtener_stock_total_variante(id_variante, empresa_id) if id_variante > 0 else 0
                res_conf = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 409,
                    "conflict_code": "STOCK_INSUFFICIENT",
                    "message": str(ve),
                    "conflict_detail": {
                        "id_detalle_carrito": id_detalle,
                        "id_variante": id_variante,
                        "requested_quantity": cantidad,
                        "available_stock": stock_disp,
                    },
                }
                return res_conf

            res_ok = {
                "operation_id": op.operation_id,
                "kind": kind,
                "status": "synced",
                "http_status": 200,
                "conflict_code": None,
                "message": "Cantidad actualizada en tu bolsa de compras.",
                "data": carrito,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "idempotent_replay": False,
            }
            return res_ok

        # ======================================================================
        # CASO 3: CARRITO — ELIMINAR PRENDA (CU08W)
        # ======================================================================
        elif kind == "CART_REMOVE_ITEM":
            id_detalle = int(payload.get("id_detalle_carrito") or 0)
            id_variante = int(payload.get("id_variante") or 0)

            if id_detalle <= 0 and id_variante > 0:
                carrito_actual = carrito_repos.consultar_carrito_completo(id_usuario, empresa_id)
                existente = next(
                    (it for it in carrito_actual.get("items", []) if int(it["id_variante"]) == id_variante),
                    None,
                )
                if existente:
                    id_detalle = int(existente["id_detalle_carrito"])

            if id_detalle > 0:
                carrito = carrito_repos.eliminar_item_del_carrito(
                    id_usuario=id_usuario,
                    id_empresa=empresa_id,
                    id_detalle_carrito=id_detalle,
                )
            else:
                carrito = carrito_repos.consultar_carrito_completo(id_usuario, empresa_id)

            res_ok = {
                "operation_id": op.operation_id,
                "kind": kind,
                "status": "synced",
                "http_status": 200,
                "conflict_code": None,
                "message": "Prenda eliminada de la bolsa.",
                "data": carrito,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "idempotent_replay": False,
            }
            return res_ok

        # ======================================================================
        # CASO 4: CARRITO — VACIAR BOLSA (CU08W)
        # ======================================================================
        elif kind == "CART_CLEAR":
            carrito = carrito_repos.vaciar_carrito_cliente(id_usuario, empresa_id)
            res_ok = {
                "operation_id": op.operation_id,
                "kind": kind,
                "status": "synced",
                "http_status": 200,
                "conflict_code": None,
                "message": "Bolsa de compras vaciada.",
                "data": carrito,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "idempotent_replay": False,
            }
            return res_ok

        # ======================================================================
        # CASO 5: RESERVA — SOLICITUD PENDIENTE VALIDADA Y CONFIRMADA ONLINE (CU10W)
        # ======================================================================
        elif kind == "RESERVA_SOLICITUD":
            # Regla #6: Nunca procesar cobros electrónicos offline; reservas desde cola deben ser sin pago
            if payload.get("con_pago"):
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 409,
                    "conflict_code": "PAYMENT_REQUIRES_ONLINE",
                    "message": "Las reservas con pago anticipado requieren validación interactiva en línea.",
                }

            id_sucursal = int(payload.get("id_sucursal") or op.branch_id or 0)
            items = payload.get("items") or []
            if id_sucursal <= 0 or not isinstance(items, list) or len(items) == 0:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "failed_permanent",
                    "http_status": 400,
                    "conflict_code": "INVALID_PAYLOAD",
                    "message": "Sucursal e ítems de la reserva son obligatorios.",
                }

            from app.modules.saas.services.saas_services import exigir_vigencia
            try:
                exigir_vigencia(empresa_id)
            except HTTPException as he:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict" if he.status_code in (403, 409) else "failed_permanent",
                    "http_status": he.status_code,
                    "conflict_code": "TENANT_FORBIDDEN",
                    "message": str(he.detail),
                }

            suc_info = _verificar_sucursal_activa_empresa(schema, id_sucursal, empresa_id)
            if not suc_info or not suc_info["activa"]:
                res_conf = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 409,
                    "conflict_code": "BRANCH_INACTIVE",
                    "message": "La sucursal seleccionada para la reserva no está activa o no pertenece a esta tienda.",
                    "conflict_detail": {"id_sucursal": id_sucursal},
                }
                return res_conf

            accept_price_change_global = bool(payload.get("accept_price_change"))
            items_limpios: List[Dict[str, Any]] = []

            for raw_item in items:
                id_var = int(raw_item.get("id_variante") or 0)
                cant = int(raw_item.get("cantidad") or 0)
                if id_var <= 0 or cant <= 0:
                    return {
                        "operation_id": op.operation_id,
                        "kind": kind,
                        "status": "failed_permanent",
                        "http_status": 400,
                        "conflict_code": "INVALID_PAYLOAD",
                        "message": "Cada prenda reservada debe tener variante y cantidad (> 0).",
                    }

                var_data = carrito_repos.obtener_datos_variante_tenant(id_var, empresa_id)
                if not var_data or not var_data["producto_activo"] or not var_data["variante_activa"]:
                    nombre_p = var_data["producto_nombre"] if var_data else f"Variante #{id_var}"
                    res_conf = {
                        "operation_id": op.operation_id,
                        "kind": kind,
                        "status": "conflict",
                        "http_status": 409,
                        "conflict_code": "PRODUCT_INACTIVE",
                        "message": f"La prenda '{nombre_p}' ya no se encuentra disponible para reserva.",
                        "conflict_detail": {"id_variante": id_var, "producto_nombre": nombre_p},
                    }
                    return res_conf

                exp_price = raw_item.get("expected_unit_price", payload.get("expected_unit_price"))
                accept_item_price = accept_price_change_global or bool(raw_item.get("accept_price_change"))
                if exp_price is not None and not accept_item_price:
                    try:
                        exp_p = round(float(exp_price), 2)
                        cur_p = round(float(var_data["precio_vigente"]), 2)
                        if abs(exp_p - cur_p) >= 0.01:
                            res_conf = {
                                "operation_id": op.operation_id,
                                "kind": kind,
                                "status": "conflict",
                                "http_status": 409,
                                "conflict_code": "PRICE_CHANGED",
                                "message": (
                                    f"El precio de '{var_data['producto_nombre']}' cambió de "
                                    f"Bs. {exp_p:.2f} a Bs. {cur_p:.2f} antes de confirmar tu reserva."
                                ),
                                "conflict_detail": {
                                    "id_variante": id_var,
                                    "producto_nombre": var_data["producto_nombre"],
                                    "expected_unit_price": exp_p,
                                    "current_unit_price": cur_p,
                                },
                            }
                            return res_conf
                    except (TypeError, ValueError):
                        pass

                stock_suc = _obtener_stock_sucursal_variante(schema, id_var, id_sucursal, empresa_id)
                if stock_suc < cant:
                    res_conf = {
                        "operation_id": op.operation_id,
                        "kind": kind,
                        "status": "conflict",
                        "http_status": 409,
                        "conflict_code": "STOCK_INSUFFICIENT",
                        "message": (
                            f"Stock insuficiente en sucursal '{suc_info['nombre']}' para '{var_data['producto_nombre']}'. "
                            f"Solicitaste {cant} y hay {stock_suc} disponible(s)."
                        ),
                        "conflict_detail": {
                            "id_variante": id_var,
                            "producto_nombre": var_data["producto_nombre"],
                            "id_sucursal": id_sucursal,
                            "requested_quantity": cant,
                            "available_stock": stock_suc,
                        },
                    }
                    return res_conf

                items_limpios.append({"id_variante": id_var, "cantidad": cant})

            try:
                reserva = reserva_repos.crear_reserva(
                    id_usuario=id_usuario,
                    id_empresa=empresa_id,
                    datos={
                        "id_sucursal": id_sucursal,
                        "fecha_hora_visita": payload.get("fecha_hora_visita"),
                        "observaciones": payload.get("observaciones"),
                        "items": items_limpios,
                        "con_pago": False,
                        "monto_pagado": 0.0,
                    },
                )
            except ValueError as ve:
                res_conf = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 409,
                    "conflict_code": "STOCK_INSUFFICIENT",
                    "message": str(ve),
                }
                return res_conf
            except HTTPException as he:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict" if he.status_code in (403, 409) else "failed_permanent",
                    "http_status": he.status_code,
                    "conflict_code": "TENANT_FORBIDDEN",
                    "message": str(he.detail),
                }

            res_ok = {
                "operation_id": op.operation_id,
                "kind": kind,
                "status": "synced",
                "http_status": 201,
                "conflict_code": None,
                "message": f"Reserva {reserva.get('codigo_reserva')} confirmada en línea exitosamente.",
                "data": reserva,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "idempotent_replay": False,
            }
            return res_ok

        # ======================================================================
        # CASO 6: POS / CAJA — VENTA DE CONTADO EN EFECTIVO OFFLINE (CU24W)
        # ======================================================================
        elif kind == "VENTA_CONTADO":
            # 1. Validar rol y permisos RBAC de Punto de Venta / Caja en servidor
            roles_usuario = {str(r).upper() for r in (token_data.get("roles") or [])}
            rol_principal = str(token_data.get("nombre_rol") or token_data.get("rol") or "").upper()
            if rol_principal:
                roles_usuario.add(rol_principal)

            tiene_acceso_pos = (
                tiene_permiso(token_data, "pos.vender")
                or tiene_permiso(token_data, "pos.cobrar")
                or tiene_permiso(token_data, "caja.ver")
                or bool(roles_usuario.intersection({"ADMIN_EMPRESA", "ADMINISTRADOR", "SUPERADMIN", "CAJERO", "VENDEDOR", "ENCARGADO"}))
            )
            if not tiene_acceso_pos or (roles_usuario == {"CLIENTE"}):
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "conflict",
                    "http_status": 403,
                    "conflict_code": "ROLE_FORBIDDEN",
                    "message": "Acceso denegado. No posee permisos para registrar ventas en Punto de Venta (POS).",
                }

            # 2. Autorizar tenant y sucursal del empleado/cajero
            from app.core.tenant_guard import resolver_tenant_operacion, obtener_sucursales_autorizadas
            from app.modules.saas.services.saas_services import exigir_vigencia
            try:
                empresa_pos = resolver_tenant_operacion(token_data, requested_tenant or empresa_id)
                exigir_vigencia(empresa_pos)
            except HTTPException as he:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "failed_permanent",
                    "http_status": he.status_code,
                    "conflict_code": "TENANT_FORBIDDEN",
                    "message": str(he.detail),
                }

            id_sucursal = int(payload.get("id_sucursal") or op.branch_id or token_data.get("id_sucursal") or 0)
            suc_info = _verificar_sucursal_activa_empresa(schema, id_sucursal, empresa_pos)
            if not suc_info or not suc_info["activa"]:
                res_inc = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 409,
                    "conflict_code": "BRANCH_INACTIVE",
                    "message": "La sucursal de la venta en efectivo no está activa o no pertenece a la empresa.",
                    "conflict_detail": {"id_sucursal": id_sucursal, "reconciliation_required": True},
                }
                return res_inc

            suc_permitidas = obtener_sucursales_autorizadas(token_data)
            if suc_permitidas is not None and id_sucursal not in suc_permitidas:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "failed_permanent",
                    "http_status": 403,
                    "conflict_code": "TENANT_FORBIDDEN",
                    "message": "No tiene autorización para registrar ventas en esta sucursal.",
                }

            # 3. Prohibir estrictamente pagos electrónicos offline (solo EFECTIVO)
            metodo_tipo = str(payload.get("metodo_tipo") or payload.get("metodo_pago") or "EFECTIVO").strip().upper()
            req_id_metodo = payload.get("id_metodo_pago")
            metodo_info = _resolver_metodo_pago_efectivo(schema, req_id_metodo)
            if metodo_tipo != "EFECTIVO" or metodo_info["tipo"] != "EFECTIVO":
                res_qr = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 409,
                    "conflict_code": "PAYMENT_REQUIRES_ONLINE",
                    "message": (
                        f"El método de pago '{metodo_tipo if metodo_tipo != 'EFECTIVO' else metodo_info['tipo']}' "
                        "no está permitido en modo offline. Solo se admiten ventas de contado en EFECTIVO."
                    ),
                    "conflict_detail": {"reconciliation_required": True, "tipo_detectado": metodo_tipo},
                }
                return res_qr

            # 4. Validar descuento manual si existe
            descuento = round(float(payload.get("descuento") or 0.0), 2)
            if descuento < 0:
                descuento = 0.0
            if descuento > 0 and not (
                tiene_permiso(token_data, "pos.descuento")
                or bool(roles_usuario.intersection({"ADMIN_EMPRESA", "ADMINISTRADOR", "SUPERADMIN", "ENCARGADO"}))
            ):
                res_inc = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 403,
                    "conflict_code": "DISCOUNT_FORBIDDEN",
                    "message": "Incidencia en venta offline: el usuario no posee permiso 'pos.descuento' para aplicar descuento.",
                    "conflict_detail": {"descuento": descuento, "reconciliation_required": True},
                }
                return res_inc

            # 5. Validar ítems, vigencia de prendas, precios y stock físico en la sucursal
            items_raw = payload.get("items") or []
            if not isinstance(items_raw, list) or len(items_raw) == 0:
                return {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "failed_permanent",
                    "http_status": 400,
                    "conflict_code": "INVALID_PAYLOAD",
                    "message": "La venta debe incluir al menos una prenda.",
                }

            accept_price_change_global = bool(payload.get("accept_price_change"))
            items_pos: List[Dict[str, int]] = []
            subtotal_servidor = 0.0

            for raw_item in items_raw:
                id_var = int(raw_item.get("id_variante") or 0)
                cant = int(raw_item.get("cantidad") or 0)
                if id_var <= 0 or cant <= 0:
                    return {
                        "operation_id": op.operation_id,
                        "kind": kind,
                        "status": "failed_permanent",
                        "http_status": 400,
                        "conflict_code": "INVALID_PAYLOAD",
                        "message": "Variante y cantidad (> 0) son obligatorias en cada línea de venta.",
                    }

                var_data = carrito_repos.obtener_datos_variante_tenant(id_var, empresa_pos)
                if not var_data or not var_data["producto_activo"] or not var_data["variante_activa"]:
                    nombre_p = var_data["producto_nombre"] if var_data else f"Variante #{id_var}"
                    res_inc = {
                        "operation_id": op.operation_id,
                        "kind": kind,
                        "status": "reconciliation_required",
                        "reconciliation_required": True,
                        "http_status": 409,
                        "conflict_code": "PRODUCT_INACTIVE",
                        "message": (
                            f"Incidencia de conciliación en venta en efectivo: la prenda '{nombre_p}' "
                            "fue desactivada antes de sincronizar."
                        ),
                        "conflict_detail": {
                            "id_variante": id_var,
                            "producto_nombre": nombre_p,
                            "reconciliation_required": True,
                        },
                    }
                    return res_inc

                cur_p = round(float(var_data["precio_vigente"]), 2)
                exp_price = raw_item.get("expected_unit_price", raw_item.get("precio_unitario"))
                accept_item_price = accept_price_change_global or bool(raw_item.get("accept_price_change"))
                if exp_price is not None and not accept_item_price:
                    try:
                        exp_p = round(float(exp_price), 2)
                        if abs(exp_p - cur_p) >= 0.01:
                            res_inc = {
                                "operation_id": op.operation_id,
                                "kind": kind,
                                "status": "reconciliation_required",
                                "reconciliation_required": True,
                                "http_status": 409,
                                "conflict_code": "PRICE_CHANGED",
                                "message": (
                                    f"Incidencia de conciliación en venta en efectivo: el precio oficial de "
                                    f"'{var_data['producto_nombre']}' cambió de Bs. {exp_p:.2f} a Bs. {cur_p:.2f}."
                                ),
                                "conflict_detail": {
                                    "id_variante": id_var,
                                    "producto_nombre": var_data["producto_nombre"],
                                    "expected_unit_price": exp_p,
                                    "current_unit_price": cur_p,
                                    "reconciliation_required": True,
                                },
                            }
                            return res_inc
                    except (TypeError, ValueError):
                        pass

                stock_suc = _obtener_stock_sucursal_variante(schema, id_var, id_sucursal, empresa_pos)
                if stock_suc < cant:
                    res_inc = {
                        "operation_id": op.operation_id,
                        "kind": kind,
                        "status": "reconciliation_required",
                        "reconciliation_required": True,
                        "http_status": 409,
                        "conflict_code": "STOCK_INSUFFICIENT",
                        "message": (
                            f"Incidencia de conciliación en venta en efectivo: stock insuficiente para "
                            f"'{var_data['producto_nombre']}' ({var_data['talla_nombre']} / {var_data['color_nombre']}). "
                            f"Vendido offline: {cant}, stock confirmado en sucursal: {stock_suc}."
                        ),
                        "conflict_detail": {
                            "id_variante": id_var,
                            "producto_nombre": var_data["producto_nombre"],
                            "id_sucursal": id_sucursal,
                            "requested_quantity": cant,
                            "available_stock": stock_suc,
                            "reconciliation_required": True,
                        },
                    }
                    return res_inc

                subtotal_servidor = round(subtotal_servidor + round(cur_p * cant, 2), 2)
                items_pos.append({"id_variante": id_var, "cantidad": cant})

            total_servidor = round(subtotal_servidor - descuento, 2)
            if total_servidor <= 0:
                res_inc = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 409,
                    "conflict_code": "INVALID_TOTAL",
                    "message": "El descuento supera o iguala el subtotal oficial de la venta.",
                    "conflict_detail": {
                        "subtotal": subtotal_servidor,
                        "descuento": descuento,
                        "reconciliation_required": True,
                    },
                }
                return res_inc

            monto_recibido_raw = payload.get("monto_recibido")
            monto_recibido = round(float(monto_recibido_raw), 2) if monto_recibido_raw is not None else total_servidor
            if monto_recibido < total_servidor:
                res_inc = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 409,
                    "conflict_code": "MONTO_INSUFICIENTE",
                    "message": (
                        f"Incidencia de conciliación: el efectivo recibido (Bs. {monto_recibido:.2f}) "
                        f"es menor al total oficial calculado por el servidor (Bs. {total_servidor:.2f})."
                    ),
                    "conflict_detail": {
                        "monto_recibido": monto_recibido,
                        "total_actual": total_servidor,
                        "reconciliation_required": True,
                    },
                }
                return res_inc

            # 6. Resolver sesión activa de caja para el cajero en la sucursal
            sesion_activa = caja_repos.obtener_sesion_activa_usuario(id_usuario, id_sucursal)
            if not sesion_activa:
                res_inc = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 409,
                    "conflict_code": "CAJA_CERRADA",
                    "message": (
                        "Incidencia de conciliación: no tienes una sesión de caja ABIERTA en esta sucursal. "
                        "Abre tu turno de caja y pulsa 'Reintentar' para asentar la venta en efectivo."
                    ),
                    "conflict_detail": {
                        "id_sucursal": id_sucursal,
                        "id_sesion_caja_original": payload.get("id_sesion_caja"),
                        "reconciliation_required": True,
                    },
                }
                return res_inc

            id_sesion_activa = int(sesion_activa["id_sesion_caja"])
            id_cliente_pos = payload.get("id_cliente")
            if id_cliente_pos is not None:
                try:
                    id_cliente_pos = int(id_cliente_pos)
                except (TypeError, ValueError):
                    id_cliente_pos = None

            # 7. Ejecutar registro transaccional de venta POS + cobro en efectivo
            try:
                venta_res = pos_repos.ejecutar_registro_venta_pos(
                    id_sesion_caja=id_sesion_activa,
                    id_usuario=id_usuario,
                    id_sucursal=id_sucursal,
                    id_empresa=empresa_pos,
                    id_cliente=id_cliente_pos,
                    descuento=descuento,
                    items=items_pos,
                )
            except ValueError as ve:
                res_inc = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 409,
                    "conflict_code": "STOCK_INSUFFICIENT",
                    "message": f"Incidencia en venta en efectivo: {str(ve)}",
                    "conflict_detail": {"id_sucursal": id_sucursal, "reconciliation_required": True},
                }
                return res_inc

            try:
                ref_offline = f"OFFLINE-{empresa_id}-{id_usuario}-{op.operation_id}"
                pago_res = caja_pago_repos.ejecutar_pago_caja(
                    id_venta=int(venta_res["id_venta"]),
                    id_usuario=id_usuario,
                    id_sucursal=id_sucursal,
                    id_empresa=empresa_pos,
                    id_sesion_caja=id_sesion_activa,
                    id_metodo_pago=int(metodo_info["id_metodo_pago"]),
                    monto_recibido=monto_recibido,
                    referencia_externa=ref_offline,
                    datos_facturacion=payload.get("datos_facturacion"),
                    desglose_recibido=payload.get("desglose_recibido") or [],
                    desglose_cambio=payload.get("desglose_cambio") or [],
                )
            except Exception as pago_err:
                # The coordinator rolls back sale, stock and payment to its savepoint.
                res_inc = {
                    "operation_id": op.operation_id,
                    "kind": kind,
                    "status": "reconciliation_required",
                    "reconciliation_required": True,
                    "http_status": 409,
                    "conflict_code": "PAYMENT_REGISTRATION_ERROR",
                    "message": f"Incidencia al registrar cobro en efectivo: {str(pago_err)}",
                    "conflict_detail": {"reconciliation_required": True},
                }
                return res_inc

            # Registrar contingencia offline y consumir cuotas transaccionalmente si aplica
            es_contingencia = bool(payload.get("contingencia") or payload.get("es_contingencia_offline") or payload.get("cuota_utilizada"))
            id_cuota_usada = None
            if db and es_contingencia:
                try:
                    # Comprobar si la tabla t_caja_cuota_contingencia existe en el esquema (Migración 008)
                    has_cuotas_table = db.execute_query(
                        "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name='t_caja_cuota_contingencia'",
                        (schema,),
                        fetchone=True
                    )
                    if has_cuotas_table and has_cuotas_table[0]:
                        from app.modules.pos.repos import contingencia_repos
                        for it in items_pos:
                            c_id = contingencia_repos.consumir_cuota_contingencia_transaccional(
                                db=db,
                                id_sesion_caja=id_sesion_activa,
                                id_variante=int(it["id_variante"]),
                                cantidad=int(it["cantidad"]),
                                id_sucursal=id_sucursal
                            )
                            if c_id and not id_cuota_usada:
                                id_cuota_usada = c_id

                        db.execute_query(
                            f"UPDATE {schema}.t_venta SET es_contingencia_offline = TRUE, "
                            "comprobante_tipo_provisional = 'PROVISIONAL_CONTINGENCIA', "
                            "id_cuota_contingencia = %s WHERE id_venta = %s",
                            (id_cuota_usada, int(venta_res["id_venta"]))
                        )
                except Exception as e_cont:
                    logger.warning(f"Aviso no bloqueante en contingencia sync: {e_cont}")

            combined_data = {
                **venta_res,
                **pago_res,
                "estado_venta": "PAGADO",
                "estado": "PAGADO",
                "referencia_offline": f"OFFLINE-{empresa_id}-{id_usuario}-{op.operation_id}",
                "es_contingencia_offline": bool(es_contingencia or id_cuota_usada),
                "comprobante_tipo_provisional": "PROVISIONAL_CONTINGENCIA" if (es_contingencia or id_cuota_usada) else None,
                "id_cuota_contingencia": id_cuota_usada,
            }
            res_ok = {
                "operation_id": op.operation_id,
                "kind": kind,
                "status": "synced",
                "reconciliation_required": False,
                "http_status": 200,
                "conflict_code": None,
                "message": f"Venta de contado en efectivo #{venta_res.get('numero_venta')} sincronizada y cobrada.",
                "data": combined_data,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "idempotent_replay": False,
            }
            return res_ok

        else:
            return {
                "operation_id": op.operation_id,
                "kind": kind,
                "status": "failed_permanent",
                "http_status": 400,
                "conflict_code": "UNSUPPORTED_OPERATION",
                "message": f"Tipo de operación '{kind}' no soportado en la cola de sincronización.",
            }

    except HTTPException as he:
        return {
            "operation_id": op.operation_id,
            "kind": kind,
            "status": "conflict" if he.status_code in (403, 409) else "failed_retryable",
            "http_status": he.status_code,
            "conflict_code": "SERVER_REJECTED",
            "message": str(he.detail),
        }
    except Exception as e:
        logger.warning(f"Error resolviendo tenant en sync: {e}")
        return {
            "operation_id": op.operation_id,
            "kind": kind,
            "status": "failed_retryable",
            "http_status": 500,
            "conflict_code": "SERVER_ERROR",
            "message": f"Error al procesar operación: {str(e)}",
        }


@router.get("/ping", summary="Comprobación rápida de conectividad real con la API (0 consultas SQL)")
def sync_ping():
    return {
        "success": True,
        "status": "ONLINE",
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


def _ejecutar_lote_sync(body: SyncBatchRequestDTO, token_data: dict) -> Dict[str, Any]:
    # Prioridad P0: Procesar ventas presenciales POS antes de carritos o reservas online
    operaciones_ordenadas = sorted(
        body.operations,
        key=lambda op: 0 if (op.kind or "").strip().upper() == "VENTA_CONTADO" else 1
    )
    results: List[Dict[str, Any]] = []
    synced_count = 0
    conflict_count = 0
    reconciliation_count = 0
    failed_count = 0

    for op in operaciones_ordenadas:
        res = _procesar_operacion_individual(op, token_data)
        st = res.get("status")
        if st == "synced":
            synced_count += 1
        elif st in ("conflict", "reconciliation_required"):
            conflict_count += 1
            if st == "reconciliation_required" or res.get("reconciliation_required"):
                reconciliation_count += 1
        else:
            failed_count += 1
        results.append(res)

    return {
        "success": True,
        "total": len(results),
        "synced_count": synced_count,
        "conflict_count": conflict_count,
        "reconciliation_count": reconciliation_count,
        "failed_count": failed_count,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


@router.post("/lote", summary="CU38W / CU39W: Procesar lote de operaciones offline (reservas, ventas en efectivo y carrito)")
def sync_lote_batch(
    body: SyncBatchRequestDTO,
    token_data: dict = Depends(verificar_token),
):
    return _ejecutar_lote_sync(body, token_data)


@router.post("/operations", summary="CU38W / CU39W: Alias compatible para procesar lote de operaciones offline")
def sync_operations_batch(
    body: SyncBatchRequestDTO,
    token_data: dict = Depends(verificar_token),
):
    return _ejecutar_lote_sync(body, token_data)
