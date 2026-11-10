import logging
import random
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.core.postgres import PostgreSQL, atomic
from app.core.config import Config
from app.modules.pos.repos import caja_repos
logger = logging.getLogger(__name__)

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def obtener_metodos_pago_activos() -> List[Dict[str, Any]]:
    """
    Retorna la lista de métodos de pago activos en el sistema (Efectivo, Tarjeta, QR, etc.).
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT id_metodo_pago, nombre, tipo, estado
            FROM {schema}.t_metodo_pago
            WHERE estado = TRUE
            ORDER BY id_metodo_pago ASC;
        """
        rows = db.execute_query(q, fetchall=True) or []
        resultado = []
        for r in rows:
            resultado.append({
                "id_metodo_pago": r[0],
                "nombre": r[1],
                "tipo": r[2],
                "estado": bool(r[3])
            })
        return resultado
    finally:
        db.close_connection()

def validar_venta_para_pago_caja(
    id_venta: int,
    id_usuario: int,
    id_sucursal: Optional[int] = None,
    id_empresa: Optional[int] = None
) -> Dict[str, Any]:
    """
    Realiza todas las validaciones de negocio de W28 antes de permitir el cobro:
    - La venta debe existir.
    - Debe pertenecer al tenant y a la sucursal del cajero.
    - Debe estar en estado PENDIENTE_PAGO.
    - El cajero debe tener una caja física ABIERTA en dicha sucursal.
    - No debe existir un pago aprobado previo.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # 1. Consultar cabecera de la venta
        q_vta = f"""
            SELECT 
                v.id_venta,
                v.numero_venta,
                v.id_sucursal,
                v.id_empresa,
                v.id_cliente,
                v.id_usuario,
                v.subtotal,
                v.descuento,
                v.total,
                v.estado,
                v.fecha_venta,
                v.observacion,
                v.nit_ci,
                v.razon_social,
                v.correo_facturacion,
                v.tipo_documento,
                v.id_sesion_caja,
                s.nombre AS sucursal_nombre,
                u_cajero.nombre AS cajero_nombre,
                u_cajero.apellido AS cajero_apellido
            FROM {schema}.t_venta v
            JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
            LEFT JOIN {schema}.t_usuario u_cajero ON u_cajero.id_usuario = v.id_usuario
            WHERE v.id_venta = %s FOR UPDATE OF v;
        """
        row = db.execute_query(q_vta, (id_venta,), fetchone=True)
        if not row:
            raise ValueError(f"La venta con ID {id_venta} no existe en el sistema.")

        venta_sucursal = row[2]
        venta_empresa = row[3]
        venta_estado = row[9]
        venta_total = float(row[8])

        # 2. Validar tenant y sucursal
        if id_empresa and venta_empresa != id_empresa:
            raise ValueError("Acceso denegado: la venta pertenece a otra empresa o cadena de tiendas.")

        if id_sucursal and venta_sucursal != id_sucursal:
            raise ValueError("Acceso denegado: la venta pertenece a una sucursal distinta a la asignada.")

        # 3. Validar estado de la venta
        if venta_estado in ('PAGADO', 'COMPLETADA'):
            raise ValueError("La venta ya ha sido cobrada exitosamente con anterioridad. No se permite doble cobro.")

        if venta_estado != 'PENDIENTE_PAGO':
            raise ValueError(f"La venta no está disponible para cobro (estado actual: {venta_estado}).")

        if venta_total <= 0:
            raise ValueError("El monto total de la venta debe ser mayor a 0.")

        # 4. Validar que no exista pago APROBADO previo
        q_pago_previo = f"""
            SELECT id_pago, codigo_transaccion, monto, fecha_pago
            FROM {schema}.t_pago
            WHERE id_venta = %s AND estado = 'APROBADO'
            LIMIT 1;
        """
        pago_existente = db.execute_query(q_pago_previo, (id_venta,), fetchone=True)
        if pago_existente:
            raise ValueError(f"La venta ya cuenta con un pago registrado (ID Pago: {pago_existente[0]}).")

        # 5. Validar que el usuario tenga una caja ABIERTA en esta sucursal (Regla RB03)
        sesion_activa = caja_repos.obtener_sesion_activa_usuario(id_usuario, venta_sucursal)
        if not sesion_activa:
            raise ValueError("Para procesar pagos el cajero debe contar con una sesión de caja ABIERTA en su sucursal.")

        # 6. Obtener datos del cliente si existe
        cliente_info = None
        id_cliente = row[4]
        if id_cliente:
            q_cli = f"""
                SELECT c.id_cliente, c.nit_ci, c.telefono, u.nombre, u.apellido, u.correo
                FROM {schema}.t_cliente c
                JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
                WHERE c.id_cliente = %s;
            """
            cli_row = db.execute_query(q_cli, (id_cliente,), fetchone=True)
            if cli_row:
                cliente_info = {
                    "id_cliente": cli_row[0],
                    "nit_ci": cli_row[1],
                    "telefono": cli_row[2],
                    "nombre_completo": f"{cli_row[3]} {cli_row[4]}".strip(),
                    "correo": cli_row[5]
                }

        # 7. Obtener ítems del detalle de la venta
        q_items = f"""
            SELECT 
                dv.id_detalle_venta,
                dv.id_variante,
                dv.cantidad,
                dv.precio_unitario,
                dv.subtotal,
                p.nombre AS producto_nombre,
                vptc.sku AS producto_codigo,
                p.imagen_url,
                t.nombre AS talla_nombre,
                col.nombre AS color_nombre,
                col.codigo_hex AS color_hex,
                vptc.sku
            FROM {schema}.t_detalle_venta dv
            JOIN {schema}.t_producto_talla_color vptc ON vptc.id_variante = dv.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = vptc.id_producto
            LEFT JOIN {schema}.t_talla t ON t.id_talla = vptc.id_talla
            LEFT JOIN {schema}.t_color col ON col.id_color = vptc.id_color
            WHERE dv.id_venta = %s
            ORDER BY dv.id_detalle_venta ASC;
        """
        item_rows = db.execute_query(q_items, (id_venta,), fetchall=True) or []
        items = []
        for it in item_rows:
            items.append({
                "id_detalle_venta": it[0],
                "id_variante": it[1],
                "cantidad": it[2],
                "precio_unitario": float(it[3]),
                "subtotal": float(it[4]),
                "producto_nombre": it[5],
                "producto_codigo": it[6],
                "imagen_url": it[7],
                "talla_nombre": it[8],
                "color_nombre": it[9],
                "color_hex": it[10],
                "sku": it[11]
            })

        cajero_nom = f"{row[18] or ''} {row[19] or ''}".strip() or "Cajero de Sucursal"

        return {
            "id_venta": row[0],
            "numero_venta": row[1],
            "id_sucursal": row[2],
            "sucursal_nombre": row[17],
            "id_empresa": row[3],
            "id_cliente": row[4],
            "cliente": cliente_info,
            "cajero_nombre": cajero_nom,
            "subtotal": float(row[6]),
            "descuento": float(row[7]),
            "total": venta_total,
            "estado": venta_estado,
            "fecha_venta": row[10].isoformat() if row[10] else None,
            "observacion": row[11],
            "nit_ci": row[12],
            "razon_social": row[13],
            "correo_facturacion": row[14],
            "tipo_documento": row[15] or 'COMPROBANTE',
            "id_sesion_caja": row[16],
            "sesion_caja_activa": sesion_activa,
            "items": items
        }
    finally:
        db.close_connection()

def calcular_desglose_cambio_optimo(
    monto_cambio: float,
    denominaciones_activas: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Calcula el desglose óptimo de billetes y monedas para entregar como cambio
    utilizando algoritmo voraz (greedy) sobre denominaciones ordenadas descendente.
    """
    rem = round(float(monto_cambio), 2)
    desglose = []
    # Ordenar por valor descendente
    denoms_ordenadas = sorted(denominaciones_activas, key=lambda d: float(d["valor"]), reverse=True)

    for d in denoms_ordenadas:
        val = float(d["valor"])
        if val <= 0:
            continue
        if rem >= val:
            cant = int(rem // val)
            if cant > 0:
                subt = round(cant * val, 2)
                rem = round(rem - subt, 2)
                desglose.append({
                    "id_denominacion": d["id_denominacion"],
                    "valor": val,
                    "cantidad": cant,
                    "subtotal": subt
                })
        if rem <= 0.001:
            break

    return desglose

@atomic
def ejecutar_pago_caja(
    id_venta: int,
    id_usuario: int,
    id_metodo_pago: int,
    monto_recibido: Optional[float] = None,
    referencia_transaccion: Optional[str] = None,
    referencia_externa: Optional[str] = None,
    datos_facturacion: Optional[Dict[str, Any]] = None,
    id_sucursal: Optional[int] = None,
    id_empresa: Optional[int] = None,
    id_sesion_caja: Optional[int] = None,
    desglose_recibido: Optional[List[Dict[str, Any]]] = None,
    desglose_cambio: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Ejecuta el registro transaccional atómico de pago en caja:
    1. Valida venta y caja abierta.
    2. Valida método de pago y monto recibido vs total.
    3. Registra en t_pago con estado 'APROBADO'.
    4. Registra denominaciones recibidas (ENTRADA_EFECTIVO) y cambio (SALIDA_CAMBIO) en t_pago_denominacion.
    5. Actualiza t_venta a 'PAGADO' y snapshot de facturación.
    6. Todo dentro de una única transacción ACID de PostgreSQL.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # 1. Validar la venta de forma previa
        venta_validada = validar_venta_para_pago_caja(id_venta, id_usuario, id_sucursal, id_empresa)
        active = venta_validada['sesion_caja_activa']
        if id_sesion_caja is not None and int(id_sesion_caja) != int(active['id_sesion_caja']):
            from fastapi import HTTPException
            raise HTTPException(403, 'La sesión de caja del pago no es la sesión autorizada del cajero.')
        locked_session = db.execute_query(f'''SELECT id_usuario,id_sucursal,id_empresa,estado
            FROM {schema}.t_caja_sesion WHERE id_sesion_caja=%s FOR UPDATE''',
            (active['id_sesion_caja'],), fetchone=True)
        if not locked_session or tuple(locked_session) != (id_usuario, venta_validada['id_sucursal'], venta_validada['id_empresa'], 'ABIERTA'):
            from fastapi import HTTPException
            raise HTTPException(403, 'La sesión de caja ya no corresponde al contexto del pago.')
        total_venta = venta_validada["total"]

        # 2. Validar método de pago
        q_metodo = f"""
            SELECT id_metodo_pago, nombre, tipo, estado
            FROM {schema}.t_metodo_pago
            WHERE id_metodo_pago = %s;
        """
        metodo_row = db.execute_query(q_metodo, (id_metodo_pago,), fetchone=True)
        if not metodo_row or not metodo_row[3]:
            raise ValueError("El método de pago seleccionado no es válido o se encuentra inactivo.")

        metodo_nombre = metodo_row[1]
        metodo_tipo = metodo_row[2].upper()

        # 3. Validación de efectivo y cálculo de cambio
        cambio = 0.00
        monto_pagado_registrado = total_venta
        items_recibido_final = []
        items_cambio_final = []

        if monto_recibido is not None:
            monto_recibido = float(monto_recibido)

        if metodo_tipo == 'EFECTIVO':
            denominaciones_activas = caja_repos.obtener_denominaciones_activas()
            denoms_map = {d["id_denominacion"]: d for d in denominaciones_activas}

            # Si el frontend envió desglose de billetes/monedas recibidos
            if desglose_recibido:
                suma_rec = 0.00
                for item in desglose_recibido:
                    id_d = item.get("id_denominacion")
                    cant = int(item.get("cantidad", 0))
                    if cant > 0 and id_d in denoms_map:
                        val = float(denoms_map[id_d]["valor"])
                        subt = round(val * cant, 2)
                        suma_rec += subt
                        items_recibido_final.append({
                            "id_denominacion": id_d,
                            "valor": val,
                            "cantidad": cant,
                            "subtotal": subt
                        })
                suma_rec = round(suma_rec, 2)
                if suma_rec > 0:
                    monto_recibido = suma_rec

            # Si no envió desglose pero envió monto_recibido, autocalcular desglose óptimo recibido
            elif monto_recibido and monto_recibido > 0:
                items_recibido_final = calcular_desglose_cambio_optimo(monto_recibido, denominaciones_activas)

            if monto_recibido is None or monto_recibido <= 0:
                raise ValueError("Debe ingresar el monto en efectivo recibido de parte del comprador.")

            if round(monto_recibido, 2) < round(total_venta, 2):
                raise ValueError(
                    f"Efectivo insuficiente: Se recibieron Bs. {monto_recibido:.2f}, pero el total a pagar es Bs. {total_venta:.2f}."
                )

            cambio = round(monto_recibido - total_venta, 2)

            # Desglose de cambio entregado
            if cambio > 0:
                if desglose_cambio:
                    suma_cam = 0.00
                    for item in desglose_cambio:
                        id_d = item.get("id_denominacion")
                        cant = int(item.get("cantidad", 0))
                        if cant > 0 and id_d in denoms_map:
                            val = float(denoms_map[id_d]["valor"])
                            subt = round(val * cant, 2)
                            suma_cam += subt
                            items_cambio_final.append({
                                "id_denominacion": id_d,
                                "valor": val,
                                "cantidad": cant,
                                "subtotal": subt
                            })
                    suma_cam = round(suma_cam, 2)
                    # Si no coincide exactamente con el cambio matemático, usar el algoritmo óptimo
                    if abs(suma_cam - cambio) > 0.05:
                        items_cambio_final = calcular_desglose_cambio_optimo(cambio, denominaciones_activas)
                else:
                    items_cambio_final = calcular_desglose_cambio_optimo(cambio, denominaciones_activas)
        else:
            monto_recibido = total_venta

        # 4. Generar código de transacción único y referencia externa
        ref_efectiva = referencia_externa or referencia_transaccion
        random_suffix = f"{random.randint(1000, 9999)}"
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
        codigo_transaccion = ref_efectiva or f"POS-{metodo_tipo[:3]}-{timestamp_str}-{random_suffix}"

        # 5. Inserción atómica en t_pago
        q_insert_pago = f"""
            INSERT INTO {schema}.t_pago (
                id_venta,
                id_metodo_pago,
                codigo_transaccion,
                referencia_externa,
                monto,
                fecha_pago,
                estado
            ) VALUES (
                %s, %s, %s, %s, %s, NOW(), 'APROBADO'
            ) RETURNING id_pago, fecha_pago;
        """
        pago_res = db.execute_query(
            q_insert_pago,
            (id_venta, id_metodo_pago, codigo_transaccion, ref_efectiva, monto_pagado_registrado),
            fetchone=True
        )
        id_pago = pago_res[0]
        fecha_pago = pago_res[1]

        # 5.1 Inserción de denominaciones de Efectivo (Entrada y Cambio) en t_pago_denominacion
        sesion_caja_id = (
            id_sesion_caja 
            or venta_validada.get("id_sesion_caja") 
            or (venta_validada.get("sesion_caja_activa") or {}).get("id_sesion_caja")
        )

        if metodo_tipo == 'EFECTIVO':
            # Registrar billetes/monedas recibidos (ENTRADA_EFECTIVO)
            for it_rec in items_recibido_final:
                q_ins_denom_rec = f"""
                    INSERT INTO {schema}.t_pago_denominacion (
                        id_pago, id_venta, id_sesion_caja, tipo_movimiento,
                        id_denominacion, valor_denominacion, cantidad, subtotal
                    ) VALUES (%s, %s, %s, 'ENTRADA_EFECTIVO', %s, %s, %s, %s);
                """
                db.execute_query(
                    q_ins_denom_rec,
                    (id_pago, id_venta, sesion_caja_id, it_rec["id_denominacion"], it_rec["valor"], it_rec["cantidad"], it_rec["subtotal"])
                )

            # Registrar billetes/monedas entregados de cambio (SALIDA_CAMBIO)
            for it_cam in items_cambio_final:
                q_ins_denom_cam = f"""
                    INSERT INTO {schema}.t_pago_denominacion (
                        id_pago, id_venta, id_sesion_caja, tipo_movimiento,
                        id_denominacion, valor_denominacion, cantidad, subtotal
                    ) VALUES (%s, %s, %s, 'SALIDA_CAMBIO', %s, %s, %s, %s);
                """
                db.execute_query(
                    q_ins_denom_cam,
                    (id_pago, id_venta, sesion_caja_id, it_cam["id_denominacion"], it_cam["valor"], it_cam["cantidad"], it_cam["subtotal"])
                )

        # 6. Actualizar t_venta a PAGADO y asociar snapshot de facturación
        razon_social_snap = None
        nit_ci_snap = None
        correo_snap = None
        tipo_doc_snap = 'COMPROBANTE'

        if datos_facturacion:
            razon_social_snap = (datos_facturacion.get("razon_social") or "").strip() or None
            nit_ci_snap = (datos_facturacion.get("nit_ci") or "").strip() or None
            correo_snap = (datos_facturacion.get("correo_facturacion") or "").strip() or None
            tipo_doc_snap = (datos_facturacion.get("tipo_documento") or "COMPROBANTE").strip()

        q_update_venta = f"""
            UPDATE {schema}.t_venta
            SET 
                estado = 'PAGADO',
                razon_social = COALESCE(%s, razon_social),
                nit_ci = COALESCE(%s, nit_ci),
                correo_facturacion = COALESCE(%s, correo_facturacion),
                tipo_documento = COALESCE(%s, tipo_documento)
            WHERE id_venta = %s;
        """
        db.execute_query(
            q_update_venta,
            (razon_social_snap, nit_ci_snap, correo_snap, tipo_doc_snap, id_venta)
        )

        # 7. Confirmar transacción
        db.commit()
        logger.info(f"✅ Pago en caja registrado: id_pago={id_pago}, id_venta={id_venta}, total=Bs.{total_venta:.2f}, metodo={metodo_nombre}")

        return {
            "id_pago": id_pago,
            "id_venta": id_venta,
            "numero_venta": venta_validada["numero_venta"],
            "total": total_venta,
            "id_metodo_pago": id_metodo_pago,
            "metodo_pago": metodo_nombre,
            "metodo_tipo": metodo_tipo,
            "monto_recibido": round(monto_recibido, 2),
            "cambio": cambio,
            "desglose_recibido": items_recibido_final,
            "desglose_cambio": items_cambio_final,
            "codigo_transaccion": codigo_transaccion,
            "fecha_pago": fecha_pago.isoformat() if fecha_pago else datetime.now().isoformat(),
            "estado_venta": "PAGADO"
        }
    except Exception as e:
        if db.conn:
            db.rollback()
        logger.error(f"[ERROR EJECUTAR PAGO CAJA] {e}")
        raise
    finally:
        db.close_connection()
