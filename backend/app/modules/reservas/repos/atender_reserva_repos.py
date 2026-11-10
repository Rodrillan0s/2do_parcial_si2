from app.core.inventory_integrity import lock_items, lock_position
import logging
import random
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from app.core.postgres import PostgreSQL, atomic
from app.core.config import Config
from app.modules.pos.repos import caja_repos
from app.modules.pos.repos import caja_pago_repos
logger = logging.getLogger(__name__)


def _get_schema():
    return Config.SCHEMA or "comercio"


def listar_reservas_para_atender(
    id_empresa: int,
    id_sucursal: int,
    busqueda: Optional[str] = None,
    estado: Optional[str] = None
) -> Dict[str, Any]:
    # Expiración oportuna de citas vencidas en el mostrador POS
    try:
        from app.modules.reservas.repos.reserva_repos import expirar_reservas_vencidas
        expirar_reservas_vencidas(id_empresa=id_empresa, tolerancia_horas=12)
    except Exception as exp_err:
        logger.warning(f"[OPORTUNISTIC EXPIRATION ATENDER] {exp_err}")

    db = PostgreSQL()
    db.create_connection()
    schema = _get_schema()

    try:
        filtros = ["r.id_sucursal = %s", "s.id_empresa = %s"]
        params: List[Any] = [id_sucursal, id_empresa]

        if estado and estado.strip() and estado.upper() != "TODAS":
            filtros.append("r.estado = %s")
            params.append(estado.strip().upper())
        else:
            filtros.append("r.estado IN ('PENDIENTE', 'CONFIRMADA')")

        if busqueda and busqueda.strip():
            b = f"%{busqueda.strip()}%"
            filtros.append("""(
                r.codigo_reserva ILIKE %s
                OR u.nombre ILIKE %s
                OR u.apellido ILIKE %s
                OR c.ci ILIKE %s
                OR u.telefono ILIKE %s
            )""")
            params.extend([b, b, b, b, b])

        where_clause = " AND ".join(filtros)

        query = f"""
            SELECT
                r.id_reserva,
                r.codigo_reserva,
                r.id_cliente,
                r.id_sucursal,
                r.fecha_reserva,
                r.fecha_hora_visita,
                r.estado,
                r.observaciones,
                r.id_venta,

                u.nombre AS cliente_nombre,
                u.apellido AS cliente_apellido,
                c.ci AS cliente_ci,
                u.telefono AS cliente_telefono,
                u.correo AS cliente_correo,

                s.nombre AS sucursal_nombre,

                v.estado AS venta_estado,
                v.numero_venta,
                v.total AS venta_total,

                COALESCE(r.con_pago, false) AS con_pago,
                COALESCE(r.estado_pago, 'SIN_PAGO') AS estado_pago,
                COALESCE(r.monto_pagado, 0.0) AS monto_pagado

            FROM {schema}.t_reserva r
            LEFT JOIN {schema}.t_cliente c ON c.id_cliente = r.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            INNER JOIN {schema}.t_sucursal s ON s.id_sucursal = r.id_sucursal
            LEFT JOIN {schema}.t_venta v ON v.id_venta = r.id_venta
            WHERE {where_clause}
            ORDER BY
                r.fecha_hora_visita ASC NULLS LAST,
                r.id_reserva DESC
        """

        reservas = db.execute_query(query, tuple(params), fetchall=True) or []
        resultado = []

        for reserva in reservas:
            id_reserva = reserva[0]
            id_venta = reserva[8]
            venta_estado = reserva[15]
            es_con_pago = bool(reserva[18])
            res_estado_pago = reserva[19]
            monto_pagado = float(reserva[20] or 0.0)

            venta_pagada = False
            if id_venta:
                venta_pagada = (venta_estado in ("PAGADO", "COMPLETADA"))
            elif es_con_pago and res_estado_pago == "PAGADO":
                venta_pagada = True

            query_detalles = f"""
                SELECT
                    dr.id_detalle_reserva,
                    dr.id_variante,
                    dr.cantidad,
                    dr.estado_prenda,

                    p.id_producto,
                    p.codigo_producto,
                    p.nombre AS producto_nombre,
                    COALESCE(ptc.precio, p.precio, 0) AS precio,

                    ptc.sku,
                    t.nombre AS talla,
                    co.nombre AS color,
                    co.codigo_hex,

                    COALESCE(
                        (
                            SELECT pi.imagen_url
                            FROM {schema}.t_producto_imagen pi
                            WHERE pi.id_producto = p.id_producto AND pi.es_principal = TRUE
                            ORDER BY pi.id_imagen LIMIT 1
                        ),
                        (
                            SELECT pi.imagen_url
                            FROM {schema}.t_producto_imagen pi
                            WHERE pi.id_producto = p.id_producto
                            ORDER BY pi.id_imagen LIMIT 1
                        ),
                        p.imagen_url
                    ) AS imagen_url

                FROM {schema}.t_detalle_reserva dr
                INNER JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dr.id_variante
                INNER JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
                LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
                LEFT JOIN {schema}.t_color co ON co.id_color = ptc.id_color
                WHERE dr.id_reserva = %s
                ORDER BY dr.id_detalle_reserva ASC
            """

            detalles = db.execute_query(query_detalles, (id_reserva,), fetchall=True) or []
            prendas = []
            total_calculado = 0.0

            for item in detalles:
                cant = int(item[2] or 0)
                precio = float(item[7] or 0)
                subt = round(cant * precio, 2)
                total_calculado += subt

                prendas.append({
                    "id_detalle_reserva": item[0],
                    "id_variante": item[1],
                    "cantidad": cant,
                    "estado_prenda": item[3] or "RESERVADA",
                    "id_producto": item[4],
                    "codigo_producto": item[5],
                    "nombre": item[6],
                    "precio": precio,
                    "subtotal": subt,
                    "sku": item[8],
                    "talla": item[9],
                    "color": item[10],
                    "codigo_hex": item[11],
                    "imagen_url": item[12]
                })

            total_final = float(reserva[17] or 0) if venta_pagada else round(total_calculado, 2)

            resultado.append({
                "id_reserva": reserva[0],
                "codigo_reserva": reserva[1],
                "id_cliente": reserva[2],
                "id_sucursal": reserva[3],
                "fecha_reserva": reserva[4].isoformat() if reserva[4] else None,
                "fecha_hora_visita": reserva[5].isoformat() if reserva[5] else None,
                "estado": reserva[6],
                "observaciones": reserva[7],
                "id_venta": reserva[8],

                "sucursal": reserva[14],

                "cliente": {
                    "id_cliente": reserva[2],
                    "nombre": reserva[9],
                    "apellido": reserva[10],
                    "nombre_completo": f"{reserva[9] or ''} {reserva[10] or ''}".strip(),
                    "ci": reserva[11],
                    "telefono": reserva[12],
                    "correo": reserva[13]
                },

                "venta": {
                    "id_venta": reserva[8],
                    "numero_venta": reserva[16],
                    "estado": reserva[15],
                    "total": float(reserva[17] or 0),
                    "pagada": venta_pagada
                },

                "venta_pagada": venta_pagada,
                "con_pago": es_con_pago,
                "estado_pago": res_estado_pago,
                "monto_pagado": monto_pagado,
                "total_estimado": total_final,
                "cantidad_prendas": len(prendas),
                "puede_atender": (reserva[6] not in ("CANCELADA", "ATENDIDA", "VENCIDA")),
                "prendas": prendas
            })

        return {
            "success": True,
            "message": "Reservas obtenidas correctamente.",
            "data": resultado,
            "total": len(resultado)
        }

    except Exception as e:
        logger.error(f"[ERROR LISTAR RESERVAS ATENDER] {e}")
        return {
            "success": False,
            "message": f"Error al listar las reservas: {str(e)}",
            "data": []
        }
    finally:
        db.close_connection()


def obtener_reserva_para_atender(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int
) -> Dict[str, Any]:
    db = PostgreSQL()
    db.create_connection()
    schema = _get_schema()

    try:
        query_reserva = f"""
            SELECT
                r.id_reserva,
                r.codigo_reserva,
                r.id_cliente,
                r.id_sucursal,
                r.fecha_reserva,
                r.fecha_hora_visita,
                r.estado,
                r.observaciones,
                r.id_venta,

                u.nombre AS cliente_nombre,
                u.apellido AS cliente_apellido,
                c.ci AS cliente_ci,
                u.telefono AS cliente_telefono,
                u.correo AS cliente_correo,

                s.nombre AS sucursal_nombre,

                v.estado AS venta_estado,
                v.numero_venta,
                v.subtotal AS venta_subtotal,
                v.descuento AS venta_descuento,
                v.total AS venta_total,

                COALESCE(r.con_pago, false) AS con_pago,
                COALESCE(r.estado_pago, 'SIN_PAGO') AS estado_pago,
                COALESCE(r.monto_pagado, 0.0) AS monto_pagado

            FROM {schema}.t_reserva r
            LEFT JOIN {schema}.t_cliente c ON c.id_cliente = r.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            INNER JOIN {schema}.t_sucursal s ON s.id_sucursal = r.id_sucursal
            LEFT JOIN {schema}.t_venta v ON v.id_venta = r.id_venta
            WHERE r.id_reserva = %s
              AND r.id_sucursal = %s
              AND s.id_empresa = %s
        """

        reserva = db.execute_query(
            query_reserva,
            (id_reserva, id_sucursal, id_empresa),
            fetchone=True
        )

        if not reserva:
            return {
                "success": False,
                "message": "La reserva no existe o no pertenece a esta sucursal."
            }

        query_detalles = f"""
            SELECT
                dr.id_detalle_reserva,
                dr.id_variante,
                dr.cantidad,
                dr.estado_prenda,

                p.id_producto,
                p.codigo_producto,
                p.nombre AS producto_nombre,
                COALESCE(ptc.precio, p.precio, 0) AS precio_variante,

                ptc.sku,
                t.nombre AS talla,
                co.nombre AS color,
                co.codigo_hex,

                COALESCE(
                    (
                        SELECT pi.imagen_url
                        FROM {schema}.t_producto_imagen pi
                        WHERE pi.id_producto = p.id_producto AND pi.es_principal = TRUE
                        ORDER BY pi.id_imagen LIMIT 1
                    ),
                    (
                        SELECT pi.imagen_url
                        FROM {schema}.t_producto_imagen pi
                        WHERE pi.id_producto = p.id_producto
                        ORDER BY pi.id_imagen LIMIT 1
                    ),
                    p.imagen_url
                ) AS imagen_url

            FROM {schema}.t_detalle_reserva dr
            INNER JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dr.id_variante
            INNER JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
            LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
            LEFT JOIN {schema}.t_color co ON co.id_color = ptc.id_color
            WHERE dr.id_reserva = %s
            ORDER BY dr.id_detalle_reserva ASC
        """

        detalles = db.execute_query(query_detalles, (id_reserva,), fetchall=True) or []
        prendas = []
        total_prendas_calculado = 0.0

        for item in detalles:
            cant = int(item[2] or 0)
            precio = float(item[7] or 0)
            subt = round(cant * precio, 2)
            total_prendas_calculado += subt

            prendas.append({
                "id_detalle_reserva": item[0],
                "id_variante": item[1],
                "id_producto": item[4],
                "codigo_producto": item[5],
                "nombre": item[6],
                "sku": item[8],
                "talla": item[9],
                "color": item[10],
                "codigo_hex": item[11],
                "cantidad": cant,
                "precio": precio,
                "subtotal": subt,
                "estado_prenda": item[3] or "RESERVADA",
                "imagen_url": item[12]
            })

        es_con_pago = bool(reserva[20])
        res_estado_pago = reserva[21] or "SIN_PAGO"
        monto_pagado = float(reserva[22] or 0.0)

        venta_pagada = False
        if reserva[8]:
            venta_pagada = reserva[15] in ("PAGADO", "COMPLETADA")
        elif es_con_pago and res_estado_pago == "PAGADO":
            venta_pagada = True

        return {
            "success": True,
            "data": {
                "reserva": {
                    "id_reserva": reserva[0],
                    "codigo_reserva": reserva[1],
                    "id_cliente": reserva[2],
                    "id_sucursal": reserva[3],
                    "sucursal": reserva[14],
                    "fecha_reserva": reserva[4].isoformat() if reserva[4] else None,
                    "fecha_hora_visita": reserva[5].isoformat() if reserva[5] else None,
                    "estado": reserva[6],
                    "observaciones": reserva[7],
                    "id_venta": reserva[8],
                    "con_pago": es_con_pago,
                    "estado_pago": res_estado_pago,
                    "monto_pagado": monto_pagado
                },

                "cliente": {
                    "id_cliente": reserva[2],
                    "nombre": reserva[9],
                    "apellido": reserva[10],
                    "nombre_completo": f"{reserva[9] or ''} {reserva[10] or ''}".strip(),
                    "ci": reserva[11],
                    "telefono": reserva[12],
                    "correo": reserva[13]
                },

                "venta": {
                    "id_venta": reserva[8],
                    "numero_venta": reserva[16],
                    "estado": reserva[15],
                    "subtotal": float(reserva[17] or 0),
                    "descuento": float(reserva[18] or 0),
                    "total": float(reserva[19] or 0),
                    "pagada": venta_pagada
                },

                "venta_pagada": venta_pagada,
                "con_pago": es_con_pago,
                "estado_pago": res_estado_pago,
                "monto_pagado": monto_pagado,
                "total_prendas": round(total_prendas_calculado, 2),
                "prendas": prendas,
                "puede_atender": (reserva[6] not in ("CANCELADA", "ATENDIDA", "VENCIDA"))
            }
        }

    except Exception as e:
        logger.error(f"[ERROR OBTENER RESERVA ATENDER] {e}")
        return {
            "success": False,
            "message": f"Error al obtener la reserva: {str(e)}"
        }
    finally:
        db.close_connection()


@atomic
def cobrar_y_atender_reserva_pos(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int,
    id_usuario: int,
    datos_cobro: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Ejecuta el ciclo de Atención y Cobro POS especializado para reservas:
    1. Bloquea la reserva y valida pertenencia y estado (PENDIENTE o CONFIRMADA).
    2. Valida sesión de caja activa ABIERTA en la sucursal (RB03).
    3. Para cada prenda reservada:
       - Si es ACEPTADA por el cliente: Descuenta de stock_actual y stock_reservado; genera movimiento SALIDA.
       - Si es RECHAZADA (no la lleva tras probarse): Libera stock_reservado -> stock_disponible; genera movimiento LIBERACION_RESERVA.
    4. Si se adquirieron prendas:
       - Crea cabecera t_venta en estado 'PAGADO', asociada a id_reserva, tipo_venta='PRESENCIAL'.
       - Inserta t_detalle_venta con los ítems adquiridos.
       - Registra t_pago en estado 'APROBADO'.
       - Si el pago fue en efectivo, registra desglose en t_pago_denominacion.
       - Actualiza t_reserva a 'ATENDIDA' con id_venta.
    5. Si el cliente decidió no adquirir ninguna prenda:
       - Libera todas las prendas al stock disponible.
       - Actualiza t_reserva a 'ATENDIDA' con nota de desistimiento.
    6. Todo dentro de una única transacción ACID de PostgreSQL.
    """
    db = PostgreSQL()
    db.create_connection()
    schema = _get_schema()

    try:
        # 1. Bloquear cabecera de reserva
        q_reserva = f"""
            SELECT
                r.id_reserva,
                r.codigo_reserva,
                r.id_cliente,
                r.id_sucursal,
                r.estado,
                r.id_venta,
                s.id_empresa,
                u.nombre AS cliente_nombre,
                u.apellido AS cliente_apellido,
                c.ci AS cliente_ci,
                u.telefono AS cliente_telefono,
                u.correo AS cliente_correo
            FROM {schema}.t_reserva r
            INNER JOIN {schema}.t_sucursal s ON s.id_sucursal = r.id_sucursal
            LEFT JOIN {schema}.t_cliente c ON c.id_cliente = r.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            WHERE r.id_reserva = %s
              AND r.id_sucursal = %s
              AND s.id_empresa = %s
            FOR UPDATE OF r;
        """
        res_row = db.execute_query(q_reserva, (id_reserva, id_sucursal, id_empresa), fetchone=True)
        if not res_row:
            raise ValueError("La reserva no existe o no corresponde a esta empresa y sucursal.")

        codigo_reserva = res_row[1]
        id_cliente = res_row[2]
        estado_reserva = res_row[4]
        id_venta_existente = res_row[5]

        if estado_reserva == "ATENDIDA":
            raise ValueError("Esta reserva ya fue atendida previamente.")
        if estado_reserva in ("CANCELADA", "VENCIDA"):
            raise ValueError(f"La reserva se encuentra en estado '{estado_reserva}' y no puede ser atendida.")

        # 2. Consultar ítems de la reserva
        q_detalles = f"""
            SELECT
                dr.id_detalle_reserva,
                dr.id_variante,
                dr.cantidad,
                dr.estado_prenda,
                COALESCE(ptc.precio, p.precio, 0) AS precio_unitario,
                p.nombre AS producto_nombre,
                ptc.sku
            FROM {schema}.t_detalle_reserva dr
            INNER JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dr.id_variante
            INNER JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
            WHERE dr.id_reserva = %s
            FOR UPDATE OF dr;
        """
        detalles_rows = db.execute_query(q_detalles, (id_reserva,), fetchall=True) or []
        if not detalles_rows:
            raise ValueError("La reserva no contiene prendas asociadas.")

        stock_items = [dict(id_variante=r[1],cantidad=r[2]) for r in detalles_rows]
        totals, positions = lock_items(db,schema,id_sucursal,stock_items,id_empresa)
        if any(totals[v] > positions[v][2] for v in totals):
            raise ValueError('INVENTORY_RECONCILIATION_REQUIRED: cantidad sin respaldo reservado.')

        # Mapa de selección desde frontend: id_detalle_reserva -> bool (True=Llevar, False=Devolver)
        items_payload = datos_cobro.get("items_seleccionados") or []
        mapa_seleccion = {}
        for it in items_payload:
            id_det = it.get("id_detalle_reserva")
            if id_det:
                mapa_seleccion[int(id_det)] = bool(it.get("aceptado", True))

        items_aceptados = []
        items_rechazados = []
        subtotal_venta = 0.0

        for row in detalles_rows:
            id_det = row[0]
            id_var = row[1]
            cant = int(row[2])
            prec = float(row[4])
            nom = row[5]
            sku = row[6]

            # Si no se envió selección explícita, se asume aceptado por defecto
            es_aceptado = mapa_seleccion.get(id_det, True) if mapa_seleccion else True

            if es_aceptado:
                subt = round(cant * prec, 2)
                subtotal_venta += subt
                items_aceptados.append({
                    "id_detalle_reserva": id_det,
                    "id_variante": id_var,
                    "cantidad": cant,
                    "precio_unitario": prec,
                    "subtotal": subt,
                    "nombre": nom,
                    "sku": sku
                })
            else:
                items_rechazados.append({
                    "id_detalle_reserva": id_det,
                    "id_variante": id_var,
                    "cantidad": cant,
                    "nombre": nom,
                    "sku": sku
                })

        # 3. Procesar inventario para prendas RECHAZADAS (devolver al stock disponible)
        for it_rech in items_rechazados:
            id_det = it_rech["id_detalle_reserva"]
            id_var = it_rech["id_variante"]
            cant = it_rech["cantidad"]

            # Actualizar detalle de reserva
            db.execute_query(
                f"UPDATE {schema}.t_detalle_reserva SET estado_prenda = 'RECHAZADA' WHERE id_detalle_reserva = %s;",
                (id_det,)
            )

            # Restituir inventario: disminuir stock_reservado y aumentar stock_disponible
            q_inv = f"""
                SELECT id_inventario, stock_actual, stock_reservado, stock_disponible
                FROM {schema}.t_inventario
                WHERE id_sucursal = %s AND id_variante = %s
                FOR UPDATE;
            """
            inv_row = db.execute_query(q_inv, (id_sucursal, id_var), fetchone=True)
            if inv_row:
                id_inv, st_act, st_res, st_disp = inv_row[0], inv_row[1], inv_row[2], inv_row[3]
                nuevo_res = max(0, st_res - cant)
                nuevo_disp = max(0, st_act - nuevo_res)

                db.execute_query(
                    f"""
                        UPDATE {schema}.t_inventario
                        SET stock_reservado = %s,
                            stock_disponible = %s,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id_inventario = %s;
                    """,
                    (nuevo_res, nuevo_disp, id_inv)
                )

                # Registrar movimiento de liberación
                db.execute_query(
                    f"""
                        INSERT INTO {schema}.t_movimiento_inventario (
                            id_inventario, id_usuario, tipo_movimiento, cantidad,
                            stock_anterior, stock_nuevo, motivo, fecha_movimiento
                        ) VALUES (%s, %s, 'LIBERACION_RESERVA', %s, %s, %s, %s, CURRENT_TIMESTAMP);
                    """,
                    (id_inv, id_usuario, cant, st_disp, nuevo_disp, f"Prenda devuelta al stock desde probador (Reserva {codigo_reserva})")
                )

        # 4. Si el cliente no aceptó ninguna prenda (devolución completa / cancelación en mostrador)
        if len(items_aceptados) == 0:
            db.execute_query(
                f"""
                    UPDATE {schema}.t_reserva
                    SET estado = 'CANCELADA',
                        observaciones = COALESCE(observaciones, '') || ' [Atención POS: Cliente devolvió todas las prendas al stock / Reserva cancelada]'
                    WHERE id_reserva = %s;
                """,
                (id_reserva,)
            )
            lock_items(db,schema,id_sucursal,stock_items,id_empresa)
            db.commit()
            return {
                "success": True,
                "accion": "LIBERADA_COMPLETA",
                "message": "Todas las prendas fueron devueltas al inventario con éxito. La reserva ha sido cancelada.",
                "items_devueltos": len(items_rechazados),
                "items_adquiridos": 0
            }

        # 5. Validar sesión de caja activa (solo necesaria para cobro y venta efectiva)
        id_sesion_caja = datos_cobro.get("id_sesion_caja")
        if not id_sesion_caja:
            sesion_act = caja_repos.obtener_sesion_activa_usuario(id_usuario, id_sucursal)
            if not sesion_act:
                raise ValueError("Para procesar el cobro en mostrador el cajero debe contar con una caja ABIERTA en esta sucursal.")
            id_sesion_caja = sesion_act["id_sesion_caja"]

        q_sesion = f"""
            SELECT estado, id_sucursal, id_empresa, id_usuario
            FROM {schema}.t_caja_sesion
            WHERE id_sesion_caja = %s
            FOR UPDATE;
        """
        ses_row = db.execute_query(q_sesion, (id_sesion_caja,), fetchone=True)
        if not ses_row or ses_row[0] != "ABIERTA":
            raise ValueError("La sesión de caja especificada no se encuentra ABIERTA.")
        if ses_row[1] != id_sucursal:
            raise ValueError("La sesión de caja pertenece a una sucursal distinta a la de la reserva.")
        if ses_row[2:] != (id_empresa,id_usuario):
            raise HTTPException(403,'La sesión de caja no corresponde al tenant y cajero autorizados.')

        # 6. Procesar inventario para prendas ACEPTADAS
        for it_acep in items_aceptados:
            id_det = it_acep["id_detalle_reserva"]
            id_var = it_acep["id_variante"]
            cant = it_acep["cantidad"]

            # Actualizar detalle de reserva
            db.execute_query(
                f"UPDATE {schema}.t_detalle_reserva SET estado_prenda = 'ATENDIDA' WHERE id_detalle_reserva = %s;",
                (id_det,)
            )

            # Descontar inventario: el ítem ya estaba reservado, por lo que descontamos de stock_actual y de stock_reservado
            q_inv = f"""
                SELECT id_inventario, stock_actual, stock_reservado, stock_disponible
                FROM {schema}.t_inventario
                WHERE id_sucursal = %s AND id_variante = %s
                FOR UPDATE;
            """
            inv_row = db.execute_query(q_inv, (id_sucursal, id_var), fetchone=True)
            if inv_row:
                id_inv, st_act, st_res, st_disp = inv_row[0], inv_row[1], inv_row[2], inv_row[3]
                nuevo_act = max(0, st_act - cant)
                nuevo_res = max(0, st_res - cant)
                # Si por alguna inconsistencia stock_reservado era menor a la cantidad, ajustar disponible
                nuevo_disp = st_disp
                if st_res < cant:
                    dif = cant - st_res
                    nuevo_disp = max(0, st_disp - dif)

                db.execute_query(
                    f"""
                        UPDATE {schema}.t_inventario
                        SET stock_actual = %s,
                            stock_reservado = %s,
                            stock_disponible = %s,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id_inventario = %s;
                    """,
                    (nuevo_act, nuevo_res, nuevo_disp, id_inv)
                )

                # Registrar movimiento de SALIDA
                db.execute_query(
                    f"""
                        INSERT INTO {schema}.t_movimiento_inventario (
                            id_inventario, id_usuario, tipo_movimiento, cantidad,
                            stock_anterior, stock_nuevo, motivo, fecha_movimiento
                        ) VALUES (%s, %s, 'SALIDA', %s, %s, %s, %s, CURRENT_TIMESTAMP);
                    """,
                    (id_inv, id_usuario, cant, st_act, nuevo_act, f"Venta en mostrador POS (Reserva {codigo_reserva})")
                )

        # 7. Validar totales, descuentos y método de pago
        descuento = float(datos_cobro.get("descuento") or 0.0)
        if descuento < 0:
            descuento = 0.0
        if descuento > subtotal_venta:
            descuento = subtotal_venta

        total_venta = round(subtotal_venta - descuento, 2)
        if total_venta < 0:
            total_venta = 0.0

        id_metodo_pago = int(datos_cobro.get("id_metodo_pago") or 3)  # default 3 = Efectivo
        q_met = f"SELECT id_metodo_pago, nombre, tipo, estado FROM {schema}.t_metodo_pago WHERE id_metodo_pago = %s;"
        met_row = db.execute_query(q_met, (id_metodo_pago,), fetchone=True)
        if not met_row or not met_row[3]:
            raise ValueError("El método de pago seleccionado no es válido o está inactivo.")

        metodo_nombre = met_row[1]
        metodo_tipo = (met_row[2] or "EFECTIVO").upper()

        monto_recibido = float(datos_cobro.get("monto_recibido") or total_venta)
        cambio = 0.0

        if metodo_tipo == "EFECTIVO":
            if round(monto_recibido, 2) < round(total_venta, 2):
                raise ValueError(f"Efectivo insuficiente: Se recibieron Bs. {monto_recibido:.2f}, pero el total a cobrar es Bs. {total_venta:.2f}.")
            cambio = round(monto_recibido - total_venta, 2)
        else:
            monto_recibido = total_venta

        # 8. Datos de facturación
        dfact = datos_cobro.get("datos_facturacion") or {}
        nit_ci_val = (dfact.get("nit_ci") or res_row[9] or "0").strip()
        razon_social_val = (dfact.get("razon_social") or f"{res_row[7] or ''} {res_row[8] or ''}".strip() or "CONTROL INTERNO").strip()
        correo_fac_val = (dfact.get("correo_facturacion") or res_row[11] or "").strip() or None
        tipo_doc_val = (dfact.get("tipo_documento") or "COMPROBANTE").strip()

        # 9. Insertar cabecera t_venta
        timestamp_str = datetime.now().strftime("%Y%m%d")
        rnd_num = random.randint(10000, 99999)
        numero_venta = f"VTA-{timestamp_str}-{rnd_num}"

        obs_venta = datos_cobro.get("observacion") or f"Cobro en mostrador POS - Reserva {codigo_reserva}"

        q_ins_venta = f"""
            INSERT INTO {schema}.t_venta (
                id_cliente,
                id_sucursal,
                id_usuario,
                numero_venta,
                tipo_venta,
                fecha_venta,
                subtotal,
                descuento,
                total,
                estado,
                observacion,
                id_empresa,
                id_sesion_caja,
                tipo_documento,
                nit_ci,
                razon_social,
                correo_facturacion
            ) VALUES (
                %s, %s, %s, %s, 'PRESENCIAL', CURRENT_TIMESTAMP,
                %s, %s, %s, 'PAGADO', %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id_venta, fecha_venta;
        """
        vta_res = db.execute_query(
            q_ins_venta,
            (
                id_cliente,
                id_sucursal,
                id_usuario,
                numero_venta,
                subtotal_venta,
                descuento,
                total_venta,
                obs_venta,
                id_empresa,
                id_sesion_caja,
                tipo_doc_val,
                nit_ci_val,
                razon_social_val,
                correo_fac_val
            ),
            fetchone=True
        )
        id_venta = vta_res[0]
        fecha_venta = vta_res[1]

        # 10. Insertar detalle t_detalle_venta
        for it_acep in items_aceptados:
            q_ins_det_vta = f"""
                INSERT INTO {schema}.t_detalle_venta (
                    id_venta,
                    id_variante,
                    cantidad,
                    precio_unitario,
                    descuento,
                    subtotal
                ) VALUES (%s, %s, %s, %s, 0.00, %s);
            """
            db.execute_query(
                q_ins_det_vta,
                (
                    id_venta,
                    it_acep["id_variante"],
                    it_acep["cantidad"],
                    it_acep["precio_unitario"],
                    it_acep["subtotal"]
                )
            )

        # 11. Registrar t_pago
        ref_trans = (datos_cobro.get("referencia_transaccion") or f"POS-RES-{timestamp_str}-{rnd_num}").strip()
        q_ins_pago = f"""
            INSERT INTO {schema}.t_pago (
                id_venta,
                id_metodo_pago,
                codigo_transaccion,
                referencia_externa,
                monto,
                fecha_pago,
                estado
            ) VALUES (
                %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'APROBADO'
            ) RETURNING id_pago;
        """
        pago_res = db.execute_query(
            q_ins_pago,
            (
                id_venta,
                id_metodo_pago,
                ref_trans,
                ref_trans,
                total_venta
            ),
            fetchone=True
        )
        id_pago = pago_res[0]

        # 12. Registrar denominaciones en t_pago_denominacion si fue Efectivo
        if metodo_tipo == "EFECTIVO":
            denominaciones_activas = caja_repos.obtener_denominaciones_activas()
            desglose_rec = caja_pago_repos.calcular_desglose_cambio_optimo(monto_recibido, denominaciones_activas)
            for d in desglose_rec:
                db.execute_query(
                    f"""
                        INSERT INTO {schema}.t_pago_denominacion (
                            id_pago, id_venta, id_sesion_caja, tipo_movimiento,
                            id_denominacion, valor_denominacion, cantidad, subtotal
                        ) VALUES (%s, %s, %s, 'ENTRADA_EFECTIVO', %s, %s, %s, %s);
                    """,
                    (id_pago, id_venta, id_sesion_caja, d["id_denominacion"], d["valor"], d["cantidad"], d["subtotal"])
                )

            if cambio > 0:
                desglose_cam = caja_pago_repos.calcular_desglose_cambio_optimo(cambio, denominaciones_activas)
                for d in desglose_cam:
                    db.execute_query(
                        f"""
                            INSERT INTO {schema}.t_pago_denominacion (
                                id_pago, id_venta, id_sesion_caja, tipo_movimiento,
                                id_denominacion, valor_denominacion, cantidad, subtotal
                            ) VALUES (%s, %s, %s, 'SALIDA_CAMBIO', %s, %s, %s, %s);
                        """,
                        (id_pago, id_venta, id_sesion_caja, d["id_denominacion"], d["valor"], d["cantidad"], d["subtotal"])
                    )

        # 13. Actualizar t_reserva: vincular id_venta y marcar ATENDIDA
        db.execute_query(
            f"""
                UPDATE {schema}.t_reserva
                SET estado = 'ATENDIDA',
                    id_venta = %s
                WHERE id_reserva = %s;
            """,
            (id_venta, id_reserva)
        )

        lock_items(db,schema,id_sucursal,stock_items,id_empresa)
        db.commit()
        logger.info(f"✅ Venta y Atención de Reserva completada: id_reserva={id_reserva}, id_venta={id_venta}, total={total_venta}")

        return {
            "success": True,
            "message": "Venta en mostrador y entrega de prendas procesada exitosamente.",
            "accion": "VENTA_POS_COMPLETADA",
            "data": {
                "id_reserva": id_reserva,
                "codigo_reserva": codigo_reserva,
                "id_venta": id_venta,
                "numero_venta": numero_venta,
                "fecha_venta": fecha_venta.isoformat() if hasattr(fecha_venta, 'isoformat') else str(fecha_venta),
                "subtotal": subtotal_venta,
                "descuento": descuento,
                "total": total_venta,
                "monto_recibido": monto_recibido,
                "cambio": cambio,
                "metodo_pago": metodo_nombre,
                "metodo_tipo": metodo_tipo,
                "codigo_transaccion": ref_trans,
                "items_adquiridos": len(items_aceptados),
                "items_devueltos": len(items_rechazados),
                "url_ticket_pdf": f"/api/comprobantes/venta/{id_venta}/pdf"
            }
        }

    except Exception as e:
        if db.conn:
            db.rollback()
        logger.error(f"[ERROR COBRAR POS RESERVA] {e}")
        if isinstance(e,HTTPException):
            raise
        raise HTTPException(400,f'Error al procesar la atención POS de la reserva: {e}') from e
    finally:
        db.close_connection()


@atomic
def atender_reserva_pagada(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int,
    id_usuario: Optional[int] = None,
    items_seleccionados: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Atiende y entrega una reserva que ya cuenta con pago online completado.
    Permite también selección en probador (prendas aceptadas vs prendas devueltas).
    """
    db = PostgreSQL()
    db.create_connection()
    schema = _get_schema()

    try:
        query = f"""
            SELECT
                r.id_reserva,
                r.codigo_reserva,
                r.estado,
                r.id_venta,
                v.estado AS venta_estado,
                COALESCE(r.con_pago, false) AS con_pago,
                COALESCE(r.estado_pago, 'SIN_PAGO') AS estado_pago,
                COALESCE(r.monto_pagado, 0.0) AS monto_pagado,
                r.id_cliente
            FROM {schema}.t_reserva r
            INNER JOIN {schema}.t_sucursal s ON s.id_sucursal = r.id_sucursal
            LEFT JOIN {schema}.t_venta v ON v.id_venta = r.id_venta
            WHERE r.id_reserva = %s
              AND r.id_sucursal = %s
              AND s.id_empresa = %s
            FOR UPDATE OF r
        """

        reserva = db.execute_query(query, (id_reserva, id_sucursal, id_empresa), fetchone=True)
        if not reserva:
            return {"success": False, "message": "La reserva no existe."}

        codigo_reserva = reserva[1]
        estado = reserva[2]
        id_venta = reserva[3]
        venta_estado = reserva[4]
        con_pago = bool(reserva[5])
        estado_pago = reserva[6]
        monto_pagado = float(reserva[7] or 0.0)
        id_cliente = reserva[8]

        if estado == "ATENDIDA":
            return {"success": False, "message": "La reserva ya fue atendida."}
        if estado in ("CANCELADA", "VENCIDA"):
            return {"success": False, "message": f"La reserva no puede ser atendida (estado: {estado})."}

        pagada_online = con_pago and (estado_pago == "PAGADO")
        if not id_venta and pagada_online:
            raise ValueError('PAYMENT_RECONCILIATION_REQUIRED: declaración de pago sin venta/evidencia; no se formalizó una venta ficticia.')
        if any(not it.get('aceptado', True) for it in (items_seleccionados or [])):
            raise ValueError('REFUND_EVIDENCE_REQUIRED: entrega pagada con rechazo requiere conciliacion financiera.')
        if not id_venta and not pagada_online:
            return {"success": False, "message": "La reserva no ha sido pagada previamente. Debe cobrarse mediante el POS."}
        if id_venta and venta_estado not in ("PAGADO", "COMPLETADA"):
            return {"success": False, "message": f"La venta asociada no se encuentra pagada (estado: {venta_estado})."}

        # Si se especificó selección de prendas
        mapa_seleccion = {}
        if items_seleccionados:
            for it in items_seleccionados:
                id_det = it.get("id_detalle_reserva")
                if id_det:
                    mapa_seleccion[int(id_det)] = bool(it.get("aceptado", True))

        q_det = f"""
            SELECT id_detalle_reserva, id_variante, cantidad
            FROM {schema}.t_detalle_reserva
            WHERE id_reserva = %s
            FOR UPDATE;
        """
        det_rows = db.execute_query(q_det, (id_reserva,), fetchall=True) or []

        stock_items = [dict(id_variante=r[1],cantidad=r[2]) for r in det_rows]
        totals, positions = lock_items(db,schema,id_sucursal,stock_items,id_empresa)
        if any(totals[v] > positions[v][2] for v in totals):
            raise ValueError('INVENTORY_RECONCILIATION_REQUIRED: cantidad sin respaldo reservado.')

        items_entregados_count = 0
        items_devueltos_count = 0

        for r_det in det_rows:
            id_det = r_det[0]
            id_var = r_det[1]
            cant = int(r_det[2])

            es_aceptado = mapa_seleccion.get(id_det, True) if mapa_seleccion else True

            if es_aceptado:
                items_entregados_count += 1
                db.execute_query(
                    f"UPDATE {schema}.t_detalle_reserva SET estado_prenda = 'ATENDIDA' WHERE id_detalle_reserva = %s;",
                    (id_det,)
                )
                # Al entregar la prenda reservada, descontar tanto stock_actual como stock_reservado
                q_inv = f"SELECT id_inventario, stock_actual, stock_reservado FROM {schema}.t_inventario WHERE id_sucursal = %s AND id_variante = %s FOR UPDATE;"
                inv_row = db.execute_query(q_inv, (id_sucursal, id_var), fetchone=True)
                if inv_row:
                    id_inv, st_act, st_res = inv_row[0], inv_row[1], inv_row[2]
                    nuevo_act = max(0, st_act - cant)
                    nuevo_res = max(0, st_res - cant)
                    db.execute_query(
                        f"UPDATE {schema}.t_inventario SET stock_actual = %s, stock_reservado = %s, fecha_actualizacion = CURRENT_TIMESTAMP WHERE id_inventario = %s;",
                        (nuevo_act, nuevo_res, id_inv)
                    )
                    db.execute_query(
                        f"""
                            INSERT INTO {schema}.t_movimiento_inventario (
                                id_inventario, id_usuario, tipo_movimiento, cantidad,
                                stock_anterior, stock_nuevo, motivo, fecha_movimiento
                            ) VALUES (%s, %s, 'SALIDA', %s, %s, %s, %s, CURRENT_TIMESTAMP);
                        """,
                        (id_inv, id_usuario, cant, st_act, nuevo_act, f"Entrega de prenda reservada {codigo_reserva}")
                    )
            else:
                items_devueltos_count += 1
                db.execute_query(
                    f"UPDATE {schema}.t_detalle_reserva SET estado_prenda = 'RECHAZADA' WHERE id_detalle_reserva = %s;",
                    (id_det,)
                )
                # Liberar prenda rechazada a stock disponible
                q_inv = f"SELECT id_inventario, stock_reservado, stock_disponible FROM {schema}.t_inventario WHERE id_sucursal = %s AND id_variante = %s FOR UPDATE;"
                inv_row = db.execute_query(q_inv, (id_sucursal, id_var), fetchone=True)
                if inv_row:
                    id_inv, st_res, st_disp = inv_row[0], inv_row[1], inv_row[2]
                    nuevo_res = max(0, st_res - cant)
                    nuevo_disp = st_disp + cant
                    db.execute_query(
                        f"UPDATE {schema}.t_inventario SET stock_reservado = %s, stock_disponible = %s, fecha_actualizacion = CURRENT_TIMESTAMP WHERE id_inventario = %s;",
                        (nuevo_res, nuevo_disp, id_inv)
                    )
                    db.execute_query(
                        f"""
                            INSERT INTO {schema}.t_movimiento_inventario (
                                id_inventario, id_usuario, tipo_movimiento, cantidad,
                                stock_anterior, stock_nuevo, motivo, fecha_movimiento
                            ) VALUES (%s, %s, 'LIBERACION_RESERVA', %s, %s, %s, %s, CURRENT_TIMESTAMP);
                        """,
                        (id_inv, id_usuario, cant, st_disp, nuevo_disp, f"Prenda devuelta de reserva {codigo_reserva}")
                    )

        # Si no había id_venta previo pero la reserva fue pagada online, formalizar la venta
        if not id_venta and items_entregados_count > 0:
            timestamp_str = datetime.now().strftime("%Y%m%d")
            rnd_num = random.randint(10000, 99999)
            numero_venta = f"VTA-{timestamp_str}-{rnd_num}"
            q_ins_venta = f"""
                INSERT INTO {schema}.t_venta (
                    id_cliente, id_sucursal, id_usuario, numero_venta, tipo_venta,
                    fecha_venta, subtotal, descuento, total, estado, observacion,
                    id_empresa, tipo_documento
                ) VALUES (
                    %s, %s, %s, %s, 'RESERVA_ONLINE',
                    CURRENT_TIMESTAMP, %s, 0.00, %s, 'PAGADO', %s,
                    %s, 'COMPROBANTE'
                ) RETURNING id_venta;
            """
            vta_res = db.execute_query(
                q_ins_venta,
                (
                    id_cliente, id_sucursal, id_usuario, numero_venta,
                    monto_pagado, monto_pagado, f"Entrega de reserva prepagada {codigo_reserva}",
                    id_empresa
                ),
                fetchone=True
            )
            if vta_res:
                id_venta = vta_res[0]
                db.execute_query(
                    f"UPDATE {schema}.t_reserva SET id_venta = %s WHERE id_reserva = %s;",
                    (id_venta, id_reserva)
                )

        # Actualizar t_reserva a ATENDIDA
        db.execute_query(
            f"UPDATE {schema}.t_reserva SET estado = 'ATENDIDA' WHERE id_reserva = %s;",
            (id_reserva,)
        )

        lock_items(db,schema,id_sucursal,stock_items,id_empresa)
        db.commit()

        return {
            "success": True,
            "message": "Prendas entregadas y reserva atendida correctamente.",
            "accion": "ENTREGADA",
            "data": {
                "id_reserva": id_reserva,
                "codigo_reserva": codigo_reserva,
                "id_venta": id_venta,
                "items_entregados": items_entregados_count,
                "items_devueltos": items_devueltos_count,
                "url_ticket_pdf": f"/api/comprobantes/venta/{id_venta}/pdf"
            }
        }

    except Exception as e:
        if db.conn:
            db.rollback()
        logger.error(f"[ERROR ATENDER RESERVA PAGADA] {e}")
        if isinstance(e,HTTPException):
            raise
        raise HTTPException(400,f'Error al atender la reserva: {e}') from e
    finally:
        db.close_connection()


def atender_reserva(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int
) -> Dict[str, Any]:
    """
    Función de compatibilidad previa. Si ya está pagada la atiende, sino retorna información para cobrarla.
    """
    reserva = obtener_reserva_para_atender(
        id_reserva,
        id_empresa,
        id_sucursal
    )

    if not reserva["success"]:
        return reserva

    data = reserva["data"]
    if not data["puede_atender"]:
        return {
            "success": False,
            "message": "La reserva no puede ser atendida."
        }

    venta = data["venta"]
    if venta["id_venta"] and venta["pagada"]:
        return atender_reserva_pagada(
            id_reserva,
            id_empresa,
            id_sucursal
        )

    return {
        "success": True,
        "message": "La reserva requiere cobro en mostrador mediante el POS.",
        "accion": "COBRO_POS_REQUERIDO",
        "data": data
    }
