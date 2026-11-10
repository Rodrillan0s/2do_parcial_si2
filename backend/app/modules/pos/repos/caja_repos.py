import logging
from typing import Dict, Any, List, Optional
from app.core.postgres import PostgreSQL, atomic
from app.core.config import Config

logger = logging.getLogger(__name__)

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def obtener_denominaciones_activas() -> List[Dict[str, Any]]:
    """
    Retorna la lista de billetes y monedas configuradas activas,
    ordenadas según su denominación.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT id_denominacion, valor, moneda, tipo, orden
            FROM {schema}.t_denominacion
            WHERE activo = TRUE
            ORDER BY orden ASC, valor DESC;
        """
        rows = db.execute_query(q, fetchall=True) or []
        resultado = []
        for r in rows:
            resultado.append({
                "id_denominacion": r[0],
                "valor": float(r[1]),
                "moneda": r[2],
                "tipo": r[3],
                "orden": r[4]
            })
        return resultado
    finally:
        db.close_connection()

def obtener_sesion_activa_usuario(id_usuario: int, id_sucursal: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Obtiene la sesión de caja actualmente ABIERTA para el usuario/cajero y sucursal.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        sucursal_clause = "AND s.id_sucursal = %s" if id_sucursal else ""
        params = [id_usuario]
        if id_sucursal:
            params.append(id_sucursal)

        q = f"""
            SELECT 
                s.id_sesion_caja,
                s.id_caja,
                s.id_usuario,
                s.id_sucursal,
                s.id_empresa,
                s.fecha_apertura,
                s.monto_inicial,
                s.estado,
                s.observacion_apertura,
                c.codigo_caja,
                c.nombre AS nombre_caja,
                suc.nombre AS nombre_sucursal,
                emp.nombre_empresa,
                u.nombre AS nombre_cajero,
                u.apellido AS apellido_cajero
            FROM {schema}.t_caja_sesion s
            JOIN {schema}.t_caja c ON c.id_caja = s.id_caja
            JOIN {schema}.t_sucursal suc ON suc.id_sucursal = s.id_sucursal
            LEFT JOIN {schema}.empresa emp ON emp.id_empresa = s.id_empresa
            JOIN {schema}.t_usuario u ON u.id_usuario = s.id_usuario
            WHERE s.id_usuario = %s AND s.estado = 'ABIERTA' {sucursal_clause}
            ORDER BY s.id_sesion_caja DESC
            LIMIT 1;
        """
        row = db.execute_query(q, tuple(params), fetchone=True)
        if not row:
            return None

        return {
            "id_sesion_caja": row[0],
            "id_caja": row[1],
            "id_usuario": row[2],
            "id_sucursal": row[3],
            "id_empresa": row[4],
            "fecha_apertura": row[5].isoformat() if row[5] else None,
            "monto_inicial": float(row[6]),
            "estado": row[7],
            "observacion_apertura": row[8],
            "codigo_caja": row[9],
            "nombre_caja": row[10],
            "nombre_sucursal": row[11],
            "nombre_empresa": row[12] or "Aurora Store",
            "cajero_nombre_completo": f"{row[13]} {row[14]}".strip()
        }
    finally:
        db.close_connection()

def obtener_sesion_caja_por_id(id_sesion_caja: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene los datos base de una sesión de caja por su identificador.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT 
                s.id_sesion_caja,
                s.id_caja,
                s.id_usuario,
                s.id_sucursal,
                s.id_empresa,
                s.fecha_apertura,
                s.fecha_cierre,
                s.monto_inicial,
                s.estado,
                s.observacion_apertura,
                c.codigo_caja,
                c.nombre AS nombre_caja,
                suc.nombre AS nombre_sucursal
            FROM {schema}.t_caja_sesion s
            JOIN {schema}.t_caja c ON c.id_caja = s.id_caja
            JOIN {schema}.t_sucursal suc ON suc.id_sucursal = s.id_sucursal
            WHERE s.id_sesion_caja = %s;
        """
        row = db.execute_query(q, (id_sesion_caja,), fetchone=True)
        if not row:
            return None
        return {
            "id_sesion_caja": row[0],
            "id_caja": row[1],
            "id_usuario": row[2],
            "id_sucursal": row[3],
            "id_empresa": row[4],
            "fecha_apertura": row[5].isoformat() if row[5] else None,
            "fecha_cierre": row[6].isoformat() if row[6] else None,
            "monto_inicial": float(row[7]) if row[7] is not None else 0.0,
            "estado": row[8],
            "observacion_apertura": row[9],
            "codigo_caja": row[10],
            "nombre_caja": row[11],
            "nombre_sucursal": row[12]
        }
    finally:
        db.close_connection()

def obtener_caja_disponible_sucursal(id_sucursal: int, id_empresa: int) -> Dict[str, Any]:
    """
    Retorna la caja principal de la sucursal o crea una si no existe.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT id_caja, codigo_caja, nombre, estado
            FROM {schema}.t_caja
            WHERE id_sucursal = %s AND estado = 'ACTIVA'
            ORDER BY id_caja ASC
            LIMIT 1;
        """
        row = db.execute_query(q, (id_sucursal,), fetchone=True)
        if row:
            return {
                "id_caja": row[0],
                "codigo_caja": row[1],
                "nombre": row[2],
                "estado": row[3]
            }

        # Si no existe, crear Caja 01
        q_suc = f"SELECT nombre FROM {schema}.t_sucursal WHERE id_sucursal = %s;"
        nom_suc_row = db.execute_query(q_suc, (id_sucursal,), fetchone=True)
        nombre_suc = nom_suc_row[0] if nom_suc_row else f"Sucursal {id_sucursal}"

        q_insert = f"""
            INSERT INTO {schema}.t_caja (id_sucursal, id_empresa, codigo_caja, nombre, estado)
            VALUES (%s, %s, %s, %s, 'ACTIVA')
            RETURNING id_caja, codigo_caja, nombre, estado;
        """
        cod = f"CAJA-SUC-{id_sucursal}-01"
        nom = f"Caja 01 - {nombre_suc}"
        new_row = db.execute_query(q_insert, (id_sucursal, id_empresa, cod, nom), fetchone=True, commit=True)
        return {
            "id_caja": new_row[0],
            "codigo_caja": new_row[1],
            "nombre": new_row[2],
            "estado": new_row[3]
        }
    finally:
        db.close_connection()

def verificar_caja_ocupada(id_caja: int) -> Optional[int]:
    """
    Verifica si una caja física ya tiene una sesión abierta activa.
    Retorna el id_sesion_caja si está ocupada, o None si está libre.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT id_sesion_caja FROM {schema}.t_caja_sesion
            WHERE id_caja = %s AND estado = 'ABIERTA'
            LIMIT 1;
        """
        row = db.execute_query(q, (id_caja,), fetchone=True)
        return row[0] if row else None
    finally:
        db.close_connection()

@atomic
def abrir_caja_sesion(
    id_usuario: int,
    id_sucursal: int,
    id_empresa: int,
    id_caja: int,
    conteo_items: List[Dict[str, Any]],
    observacion: Optional[str] = None
) -> Dict[str, Any]:
    """
    Abre una nueva sesión de caja mediante conteo físico de billetes y monedas.
    Recalcula estrictamente el fondo inicial en el servidor.
    """
    # 1. Obtener denominaciones activas para validar y multiplicar
    denominaciones = {d["id_denominacion"]: d for d in obtener_denominaciones_activas()}

    total_recalculado = 0.00
    detalles_para_insertar = []

    for item in conteo_items:
        id_denom = item.get("id_denominacion")
        cant = item.get("cantidad", 0)

        if cant is None or cant < 0:
            raise ValueError("Las cantidades de denominaciones no pueden ser negativas.")

        if id_denom not in denominaciones:
            raise ValueError(f"Denominación con ID {id_denom} no es válida o se encuentra inactiva.")

        if cant > 0:
            val = denominaciones[id_denom]["valor"]
            subtot = round(val * cant, 2)
            total_recalculado += subtot
            detalles_para_insertar.append((id_denom, val, cant, subtot))

    total_recalculado = round(total_recalculado, 2)

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # The existing user/cash-box rows serialize absent sessions too.
        user = db.execute_query(f'SELECT id_empresa FROM {schema}.t_usuario WHERE id_usuario=%s FOR UPDATE',
                                (id_usuario,), fetchone=True)
        box = db.execute_query(f'''SELECT c.id_sucursal,c.id_empresa,s.id_empresa FROM {schema}.t_caja c
            JOIN {schema}.t_sucursal s ON s.id_sucursal=c.id_sucursal WHERE c.id_caja=%s FOR UPDATE OF c''',
            (id_caja,), fetchone=True)
        if not user or (user[0] is not None and user[0] != id_empresa) or not box or tuple(box) != (id_sucursal,id_empresa,id_empresa):
            from fastapi import HTTPException
            raise HTTPException(403, 'La caja, sucursal, empresa o usuario no coinciden con el contexto autorizado.')

        # Verificar que el usuario no tenga OTRA caja abierta en esta sucursal
        q_check_user = f"""
            SELECT id_sesion_caja FROM {schema}.t_caja_sesion
            WHERE id_usuario = %s AND id_sucursal = %s AND estado = 'ABIERTA'
            LIMIT 1;
        """
        user_open = db.execute_query(q_check_user, (id_usuario, id_sucursal), fetchone=True)
        if user_open:
            raise ValueError("El usuario ya tiene una sesión de caja abierta activa en esta sucursal.")

        # Si el usuario tenía sesiones abiertas en otras sucursales, cerrarlas ordenadamente por cambio de sucursal
        q_close_other = f"""
            UPDATE {schema}.t_caja_sesion
            SET estado = 'CERRADA',
                fecha_cierre = CURRENT_TIMESTAMP,
                observacion_cierre = COALESCE(observacion_cierre, '') || ' [Cierre automático por cambio de sucursal]'
            WHERE id_usuario = %s AND id_sucursal != %s AND estado = 'ABIERTA';
        """
        db.execute_query(q_close_other, (id_usuario, id_sucursal))

        # Verificar que la caja física no esté abierta por otro usuario
        q_check_caja = f"""
            SELECT id_sesion_caja FROM {schema}.t_caja_sesion
            WHERE id_caja = %s AND estado = 'ABIERTA'
            LIMIT 1;
        """
        caja_open = db.execute_query(q_check_caja, (id_caja,), fetchone=True)
        if caja_open:
            raise ValueError("La caja seleccionada ya se encuentra abierta por otro turno.")

        # Insertar cabecera de sesión
        q_sesion = f"""
            INSERT INTO {schema}.t_caja_sesion (
                id_caja, id_usuario, id_sucursal, id_empresa,
                monto_inicial, estado, observacion_apertura
            ) VALUES (
                %s, %s, %s, %s, %s, 'ABIERTA', %s
            ) RETURNING id_sesion_caja, fecha_apertura;
        """
        res_sesion = db.execute_query(
            q_sesion,
            (id_caja, id_usuario, id_sucursal, id_empresa, total_recalculado, observacion),
            fetchone=True
        )
        id_sesion = res_sesion[0]
        fecha_apertura = res_sesion[1]

        # Insertar detalle de conteo histórico de apertura
        for id_denom, val, cant, subtot in detalles_para_insertar:
            q_conteo = f"""
                INSERT INTO {schema}.t_caja_conteo (
                    id_sesion_caja, tipo_conteo, id_denominacion,
                    valor_denominacion, cantidad, subtotal
                ) VALUES (
                    %s, 'APERTURA', %s, %s, %s, %s
                );
            """
            db.execute_query(q_conteo, (id_sesion, id_denom, val, cant, subtot))

        # Asignar automáticamente cuotas de contingencia offline para la sesión de caja
        cuotas_contingencia = []
        try:
            from app.modules.pos.repos import contingencia_repos
            cuotas_contingencia = contingencia_repos.calcular_y_asignar_cuotas_sesion(
                id_sesion_caja=id_sesion,
                id_caja=id_caja,
                id_sucursal=id_sucursal,
                id_empresa=id_empresa,
                db=db
            )
        except Exception as e_cont:
            logger.warning(f"Aviso no bloqueante: no se pudieron precargar cuotas de contingencia: {e_cont}")

        db.commit()

        # Retornar sesión completa
        return {
            "id_sesion_caja": id_sesion,
            "id_caja": id_caja,
            "id_usuario": id_usuario,
            "id_sucursal": id_sucursal,
            "id_empresa": id_empresa,
            "fecha_apertura": fecha_apertura.isoformat() if fecha_apertura else None,
            "monto_inicial": total_recalculado,
            "estado": "ABIERTA",
            "observacion_apertura": observacion,
            "conteo_items": [
                {"id_denominacion": d[0], "valor": d[1], "cantidad": d[2], "subtotal": d[3]}
                for d in detalles_para_insertar
            ],
            "cuotas_contingencia": cuotas_contingencia
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close_connection()

def calcular_resumen_caja(id_sesion_caja: int, id_empresa: Optional[int] = None) -> Dict[str, Any]:
    """
    Calcula el resumen financiero de la sesión de caja:
    - Fondo inicial
    - Ventas en efectivo, tarjeta, otros métodos
    - Efectivo esperado = fondo_inicial + ventas_efectivo - salidas
    - Cantidad total de ventas realizadas
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Obtener sesión
        q_sesion = f"""
            SELECT id_sesion_caja, id_caja, id_usuario, id_sucursal, id_empresa,
                   monto_inicial, fecha_apertura, fecha_cierre, estado, diferencia,
                   efectivo_esperado, efectivo_contado
            FROM {schema}.t_caja_sesion
            WHERE id_sesion_caja = %s;
        """
        s_row = db.execute_query(q_sesion, (id_sesion_caja,), fetchone=True)
        if not s_row:
            raise ValueError(f"Sesión de caja {id_sesion_caja} no encontrada.")

        if id_empresa is not None and s_row[4] is not None and int(s_row[4]) != int(id_empresa):
            raise ValueError("Acceso denegado: la sesión de caja no pertenece al tenant autorizado.")

        monto_inicial = float(s_row[5])
        estado_sesion = s_row[8]

        # Total ventas de la sesión
        q_ventas = f"""
            SELECT 
                COUNT(id_venta) AS cant_ventas,
                COALESCE(SUM(total), 0.00) AS total_ventas,
                COUNT(CASE WHEN estado = 'PAGADO' OR estado = 'COMPLETADA' THEN 1 END) AS cant_pagadas,
                COUNT(CASE WHEN estado = 'PENDIENTE_PAGO' THEN 1 END) AS cant_pendientes
            FROM {schema}.t_venta
            WHERE id_sesion_caja = %s;
        """
        v_row = db.execute_query(q_ventas, (id_sesion_caja,), fetchone=True)
        cant_ventas = v_row[0] if v_row else 0
        total_ventas = float(v_row[1]) if v_row else 0.00
        cant_pagadas = v_row[2] if v_row else 0
        cant_pendientes = v_row[3] if v_row else 0

        # Pagos clasificados por método de pago para ventas de esta sesión
        q_pagos = f"""
            SELECT 
                COALESCE(UPPER(mp.tipo), 'OTRO') AS tipo_metodo,
                COALESCE(SUM(p.monto), 0.00) AS monto_acumulado
            FROM {schema}.t_pago p
            JOIN {schema}.t_venta v ON v.id_venta = p.id_venta
            LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
            WHERE v.id_sesion_caja = %s AND p.estado = 'APROBADO'
            GROUP BY COALESCE(UPPER(mp.tipo), 'OTRO');
        """
        p_rows = db.execute_query(q_pagos, (id_sesion_caja,), fetchall=True) or []
        desglose_pagos = {}
        ventas_efectivo = 0.00
        ventas_tarjeta = 0.00
        ventas_qr = 0.00

        for pr in p_rows:
            tipo = pr[0]
            monto = float(pr[1])
            desglose_pagos[tipo] = monto
            if tipo == 'EFECTIVO':
                ventas_efectivo += monto
            elif 'TARJETA' in tipo:
                ventas_tarjeta += monto
            elif 'QR' in tipo or 'PAYPAL' in tipo:
                ventas_qr += monto

        # Reembolsos en efectivo emitidos en esta sesión de caja (egresos de caja)
        q_reembolsos = f"""
            SELECT COALESCE(SUM(monto_reembolso), 0.00)
            FROM {schema}.t_devolucion
            WHERE id_sesion_caja = %s AND estado = 'COMPLETADA' AND metodo_reembolso = 'EFECTIVO';
        """
        r_row = db.execute_query(q_reembolsos, (id_sesion_caja,), fetchone=True)
        reembolsos_efectivo = float(r_row[0]) if r_row else 0.00

        efectivo_esperado = round(monto_inicial + ventas_efectivo - reembolsos_efectivo, 2)

        # Cálculo de Efectivo Esperado por Denominación
        # 1. Denominaciones activas
        q_denoms = f"""
            SELECT id_denominacion, valor, moneda, tipo, orden
            FROM {schema}.t_denominacion
            WHERE activo = TRUE
            ORDER BY orden ASC, valor DESC;
        """
        denom_rows = db.execute_query(q_denoms, fetchall=True) or []

        # 2. Conteo de Apertura por denominación
        q_apertura = f"""
            SELECT id_denominacion, COALESCE(SUM(cantidad), 0)
            FROM {schema}.t_caja_conteo
            WHERE id_sesion_caja = %s AND tipo_conteo = 'APERTURA'
            GROUP BY id_denominacion;
        """
        apertura_rows = db.execute_query(q_apertura, (id_sesion_caja,), fetchall=True) or []
        apertura_map = {r[0]: int(r[1]) for r in apertura_rows}

        # 3. Billetes/monedas recibidos en pagos de efectivo (ENTRADA_EFECTIVO)
        q_recibido = f"""
            SELECT id_denominacion, COALESCE(SUM(cantidad), 0)
            FROM {schema}.t_pago_denominacion
            WHERE id_sesion_caja = %s AND tipo_movimiento = 'ENTRADA_EFECTIVO'
            GROUP BY id_denominacion;
        """
        recibido_rows = db.execute_query(q_recibido, (id_sesion_caja,), fetchall=True) or []
        recibido_map = {r[0]: int(r[1]) for r in recibido_rows}

        # 4. Billetes/monedas entregados como cambio (SALIDA_CAMBIO)
        q_cambio = f"""
            SELECT id_denominacion, COALESCE(SUM(cantidad), 0)
            FROM {schema}.t_pago_denominacion
            WHERE id_sesion_caja = %s AND tipo_movimiento = 'SALIDA_CAMBIO'
            GROUP BY id_denominacion;
        """
        cambio_rows = db.execute_query(q_cambio, (id_sesion_caja,), fetchall=True) or []
        cambio_map = {r[0]: int(r[1]) for r in cambio_rows}

        # 5. Si ya está cerrada, obtener el conteo de cierre registrado
        conteo_cierre_map = {}
        if estado_sesion == 'CERRADA':
            q_cierre = f"""
                SELECT id_denominacion, COALESCE(SUM(cantidad), 0)
                FROM {schema}.t_caja_conteo
                WHERE id_sesion_caja = %s AND tipo_conteo = 'CIERRE'
                GROUP BY id_denominacion;
            """
            cierre_rows = db.execute_query(q_cierre, (id_sesion_caja,), fetchall=True) or []
            conteo_cierre_map = {r[0]: int(r[1]) for r in cierre_rows}

        denominaciones_esperadas = []
        for dr in denom_rows:
            id_d = dr[0]
            val_d = float(dr[1])
            cant_ap = apertura_map.get(id_d, 0)
            cant_rec = recibido_map.get(id_d, 0)
            cant_cam = cambio_map.get(id_d, 0)
            cant_esp = cant_ap + cant_rec - cant_cam
            subt_esp = round(cant_esp * val_d, 2)
            
            item_denom = {
                "id_denominacion": id_d,
                "valor": val_d,
                "moneda": dr[2],
                "tipo": dr[3],
                "orden": dr[4],
                "cantidad_apertura": cant_ap,
                "cantidad_recibida": cant_rec,
                "cantidad_cambio": cant_cam,
                "cantidad_esperada": cant_esp,
                "subtotal_esperado": subt_esp
            }
            if estado_sesion == 'CERRADA':
                item_denom["cantidad_contada"] = conteo_cierre_map.get(id_d, 0)
                item_denom["subtotal_contado"] = round(item_denom["cantidad_contada"] * val_d, 2)
                item_denom["diferencia_unidades"] = item_denom["cantidad_contada"] - cant_esp

            denominaciones_esperadas.append(item_denom)

        return {
            "id_sesion_caja": id_sesion_caja,
            "estado": estado_sesion,
            "fecha_apertura": s_row[6].isoformat() if s_row[6] else None,
            "fecha_cierre": s_row[7].isoformat() if s_row[7] else None,
            "monto_inicial": monto_inicial,
            "ventas_efectivo": round(ventas_efectivo, 2),
            "reembolsos_efectivo": round(reembolsos_efectivo, 2),
            "ventas_tarjeta": round(ventas_tarjeta, 2),
            "ventas_electronicas": round(ventas_qr, 2),
            "desglose_pagos": desglose_pagos,
            "efectivo_esperado": efectivo_esperado,
            "efectivo_contado": float(s_row[11]) if s_row[11] is not None else None,
            "diferencia": float(s_row[9]) if s_row[9] is not None else None,
            "total_ventas": round(total_ventas, 2),
            "cant_ventas": cant_ventas,
            "cant_pagadas": cant_pagadas,
            "cant_pendientes": cant_pendientes,
            "denominaciones_esperadas": denominaciones_esperadas
        }
    finally:
        db.close_connection()

def cerrar_caja_sesion(
    id_sesion_caja: int,
    id_usuario: int,
    conteo_items: List[Dict[str, Any]],
    observacion: Optional[str] = None,
    id_empresa: Optional[int] = None
) -> Dict[str, Any]:
    """
    Cierra la sesión de caja mediante conteo por denominaciones.
    Compara efectivo contado vs esperado y registra el arqueo.
    """
    denominaciones = {d["id_denominacion"]: d for d in obtener_denominaciones_activas()}

    efectivo_contado = 0.00
    detalles_para_insertar = []

    for item in conteo_items:
        id_denom = item.get("id_denominacion")
        cant = item.get("cantidad", 0)

        if cant is None or cant < 0:
            raise ValueError("Las cantidades de denominaciones no pueden ser negativas.")

        if id_denom not in denominaciones:
            raise ValueError(f"Denominación con ID {id_denom} no es válida.")

        if cant > 0:
            val = denominaciones[id_denom]["valor"]
            subtot = round(val * cant, 2)
            efectivo_contado += subtot
            detalles_para_insertar.append((id_denom, val, cant, subtot))

    efectivo_contado = round(efectivo_contado, 2)

    # Calcular resumen actual
    resumen = calcular_resumen_caja(id_sesion_caja, id_empresa=id_empresa)
    if resumen["estado"] != "ABIERTA":
        raise ValueError("La sesión de caja ya se encuentra cerrada.")

    efectivo_esperado = resumen["efectivo_esperado"]
    diferencia = round(efectivo_contado - efectivo_esperado, 2)

    estado_diferencia = "CUADRA"
    if diferencia > 0:
        estado_diferencia = "SOBRANTE"
    elif diferencia < 0:
        estado_diferencia = "FALTANTE"

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Actualizar sesión a CERRADA
        q_update = f"""
            UPDATE {schema}.t_caja_sesion
            SET fecha_cierre = CURRENT_TIMESTAMP,
                efectivo_esperado = %s,
                efectivo_contado = %s,
                diferencia = %s,
                estado = 'CERRADA',
                observacion_cierre = %s
            WHERE id_sesion_caja = %s AND estado = 'ABIERTA'
            RETURNING fecha_cierre;
        """
        res_close = db.execute_query(
            q_update,
            (efectivo_esperado, efectivo_contado, diferencia, observacion, id_sesion_caja),
            fetchone=True
        )
        if not res_close:
            raise ValueError("No se pudo cerrar la caja. Verifique que la sesión siga abierta.")

        fecha_cierre = res_close[0]

        # Insertar conteo histórico de cierre
        for id_denom, val, cant, subtot in detalles_para_insertar:
            q_conteo = f"""
                INSERT INTO {schema}.t_caja_conteo (
                    id_sesion_caja, tipo_conteo, id_denominacion,
                    valor_denominacion, cantidad, subtotal
                ) VALUES (
                    %s, 'CIERRE', %s, %s, %s, %s
                );
            """
            db.execute_query(q_conteo, (id_sesion_caja, id_denom, val, cant, subtot))

        # Liberar cuotas de contingencia no consumidas de regreso al inventario vendible
        cuotas_liberadas = 0
        try:
            from app.modules.pos.repos import contingencia_repos
            cuotas_liberadas = contingencia_repos.liberar_cuotas_sesion_caja(id_sesion_caja, db=db)
        except Exception as e_lib:
            logger.warning(f"Aviso no bloqueante: no se pudieron liberar cuotas de contingencia al cerrar caja: {e_lib}")

        db.conn.commit()

        return {
            "id_sesion_caja": id_sesion_caja,
            "estado": "CERRADA",
            "fecha_apertura": resumen["fecha_apertura"],
            "fecha_cierre": fecha_cierre.isoformat() if fecha_cierre else None,
            "monto_inicial": resumen["monto_inicial"],
            "ventas_efectivo": resumen["ventas_efectivo"],
            "ventas_tarjeta": resumen["ventas_tarjeta"],
            "efectivo_esperado": efectivo_esperado,
            "efectivo_contado": efectivo_contado,
            "diferencia": diferencia,
            "estado_diferencia": estado_diferencia,
            "observacion_cierre": observacion,
            "cuotas_contingencia_liberadas": cuotas_liberadas,
            "conteo_items": [
                {"id_denominacion": d[0], "valor": d[1], "cantidad": d[2], "subtotal": d[3]}
                for d in detalles_para_insertar
            ]
        }
    except Exception as e:
        db.conn.rollback()
        raise e
    finally:
        db.close_connection()


def monitorear_cajas_tienda_sucursal(
    id_empresa: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    estado_filtro: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retorna la lista de todas las cajas registradoras físicas con su estado en vivo,
    turno activo actual (si está abierta) o último cierre registrado.
    Permite a Administradores Globales, Administradores de Tienda y Encargados
    supervisar todas las cajas de sus tiendas y sucursales.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        filtros = []
        params = []

        if id_empresa:
            filtros.append("c.id_empresa = %s")
            params.append(id_empresa)
        if id_sucursal:
            filtros.append("c.id_sucursal = %s")
            params.append(id_sucursal)

        where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""

        q = f"""
            SELECT 
                c.id_caja,
                c.codigo_caja,
                c.nombre AS nombre_caja,
                c.estado AS estado_caja,
                c.id_sucursal,
                s.nombre AS nombre_sucursal,
                COALESCE(ciu.nombre, '') AS ciudad_sucursal,
                c.id_empresa,
                COALESCE(e.nombre_empresa, 'Aurora Store') AS nombre_empresa,
                sa.id_sesion_caja AS sesion_activa_id,
                sa.fecha_apertura AS sesion_activa_fecha_apertura,
                sa.monto_inicial AS sesion_activa_monto_inicial,
                sa.id_usuario AS sesion_activa_id_usuario,
                u.nombre AS sesion_activa_usuario_nombre,
                u.apellido AS sesion_activa_usuario_apellido,
                sa.observacion_apertura AS sesion_activa_observacion
            FROM {schema}.t_caja c
            INNER JOIN {schema}.t_sucursal s ON s.id_sucursal = c.id_sucursal
            LEFT JOIN {schema}.t_ciudad ciu ON ciu.id_ciudad = s.id_ciudad
            LEFT JOIN {schema}.empresa e ON e.id_empresa = c.id_empresa
            LEFT JOIN {schema}.t_caja_sesion sa ON sa.id_caja = c.id_caja AND sa.estado = 'ABIERTA'
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = sa.id_usuario
            {where_clause}
            ORDER BY c.id_empresa, s.nombre, c.id_caja ASC;
        """
        rows = db.execute_query(q, tuple(params), fetchall=True) or []

        cajas = []
        total_abiertas = 0
        total_cerradas = 0
        efectivo_total_en_cajas = 0.0

        for r in rows:
            id_caja = r[0]
            sesion_activa_id = r[9]
            estado_turno = "ABIERTA" if sesion_activa_id else "CERRADA"

            if estado_filtro and estado_filtro.upper() in ('ABIERTA', 'CERRADA') and estado_turno != estado_filtro.upper():
                continue

            sesion_activa_info = None
            if sesion_activa_id:
                total_abiertas += 1
                monto_ini = float(r[11] or 0.0)
                # Resumen financiero en vivo
                resumen_vivo = calcular_resumen_caja(sesion_activa_id)
                efectivo_caja = resumen_vivo.get("efectivo_esperado", monto_ini)
                efectivo_total_en_cajas += efectivo_caja
                cajero_nom = f"{r[13] or ''} {r[14] or ''}".strip() or "Cajero Asignado"

                sesion_activa_info = {
                    "id_sesion_caja": sesion_activa_id,
                    "id_usuario": r[12],
                    "cajero_nombre": cajero_nom,
                    "fecha_apertura": r[10].isoformat() if r[10] else None,
                    "monto_inicial": monto_ini,
                    "observacion": r[15],
                    "total_ventas": resumen_vivo.get("total_ventas", 0.0),
                    "cant_ventas": resumen_vivo.get("cant_ventas", 0),
                    "ventas_efectivo": resumen_vivo.get("ventas_efectivo", 0.0),
                    "ventas_tarjeta": resumen_vivo.get("ventas_tarjeta", 0.0),
                    "ventas_qr": resumen_vivo.get("ventas_qr", 0.0),
                    "efectivo_esperado": efectivo_caja,
                    "resumen": resumen_vivo
                }
            else:
                total_cerradas += 1

            # Obtener última sesión cerrada para contexto
            q_ult = f"""
                SELECT 
                    cs.id_sesion_caja, cs.fecha_cierre, cs.monto_inicial,
                    cs.efectivo_esperado, cs.efectivo_contado, cs.diferencia,
                    u.nombre, u.apellido
                FROM {schema}.t_caja_sesion cs
                LEFT JOIN {schema}.t_usuario u ON u.id_usuario = cs.id_usuario
                WHERE cs.id_caja = %s AND cs.estado = 'CERRADA'
                ORDER BY cs.id_sesion_caja DESC
                LIMIT 1;
            """
            ult_row = db.execute_query(q_ult, (id_caja,), fetchone=True)
            ult_info = None
            if ult_row:
                ult_cajero = f"{ult_row[6] or ''} {ult_row[7] or ''}".strip()
                ult_info = {
                    "id_sesion_caja": ult_row[0],
                    "fecha_cierre": ult_row[1].isoformat() if ult_row[1] else None,
                    "monto_inicial": float(ult_row[2] or 0.0),
                    "efectivo_esperado": float(ult_row[3] or 0.0),
                    "efectivo_contado": float(ult_row[4] or 0.0),
                    "diferencia": float(ult_row[5] or 0.0),
                    "cajero_nombre": ult_cajero or "Anterior"
                }

            cajas.append({
                "id_caja": id_caja,
                "codigo_caja": r[1],
                "nombre": r[2],
                "estado_caja": r[3],
                "id_sucursal": r[4],
                "sucursal_nombre": r[5],
                "sucursal_ciudad": r[6],
                "id_empresa": r[7],
                "empresa_nombre": r[8],
                "estado_turno": estado_turno,
                "sesion_activa": sesion_activa_info,
                "ultima_sesion_cerrada": ult_info
            })

        return {
            "success": True,
            "cajas": cajas,
            "total_cajas": len(cajas),
            "total_abiertas": total_abiertas,
            "total_cerradas": total_cerradas,
            "efectivo_total_en_cajas": round(efectivo_total_en_cajas, 2)
        }
    finally:
        db.close_connection()


def listar_todas_sesiones_caja(
    id_empresa: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    id_caja: Optional[int] = None,
    limite: int = 50
) -> List[Dict[str, Any]]:
    """
    Retorna el historial cronológico de sesiones de caja (turnos y arqueos).
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        filtros = []
        params = []
        if id_empresa:
            filtros.append("cs.id_empresa = %s")
            params.append(id_empresa)
        if id_sucursal:
            filtros.append("cs.id_sucursal = %s")
            params.append(id_sucursal)
        if id_caja:
            filtros.append("cs.id_caja = %s")
            params.append(id_caja)

        where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        params.append(limite)

        q = f"""
            SELECT 
                cs.id_sesion_caja,
                cs.id_caja,
                c.codigo_caja,
                c.nombre AS nombre_caja,
                cs.id_sucursal,
                s.nombre AS nombre_sucursal,
                cs.id_empresa,
                COALESCE(e.nombre_empresa, 'Aurora Store') AS nombre_empresa,
                cs.id_usuario,
                u.nombre AS cajero_nombre,
                u.apellido AS cajero_apellido,
                cs.fecha_apertura,
                cs.fecha_cierre,
                cs.monto_inicial,
                cs.efectivo_esperado,
                cs.efectivo_contado,
                cs.diferencia,
                cs.estado,
                cs.observacion_apertura,
                cs.observacion_cierre
            FROM {schema}.t_caja_sesion cs
            JOIN {schema}.t_caja c ON c.id_caja = cs.id_caja
            JOIN {schema}.t_sucursal s ON s.id_sucursal = cs.id_sucursal
            LEFT JOIN {schema}.empresa e ON e.id_empresa = cs.id_empresa
            JOIN {schema}.t_usuario u ON u.id_usuario = cs.id_usuario
            {where_clause}
            ORDER BY cs.id_sesion_caja DESC
            LIMIT %s;
        """
        rows = db.execute_query(q, tuple(params), fetchall=True) or []
        sesiones = []
        for r in rows:
            caj = f"{r[9] or ''} {r[10] or ''}".strip()
            sesiones.append({
                "id_sesion_caja": r[0],
                "id_caja": r[1],
                "codigo_caja": r[2],
                "nombre_caja": r[3],
                "id_sucursal": r[4],
                "sucursal_nombre": r[5],
                "id_empresa": r[6],
                "empresa_nombre": r[7],
                "id_usuario": r[8],
                "cajero_nombre": caj or "Cajero",
                "fecha_apertura": r[11].isoformat() if r[11] else None,
                "fecha_cierre": r[12].isoformat() if r[12] else None,
                "monto_inicial": float(r[13] or 0.0),
                "efectivo_esperado": float(r[14]) if r[14] is not None else None,
                "efectivo_contado": float(r[15]) if r[15] is not None else None,
                "diferencia": float(r[16]) if r[16] is not None else None,
                "estado": r[17],
                "observacion_apertura": r[18],
                "observacion_cierre": r[19]
            })
        return sesiones
    finally:
        db.close_connection()


def crear_nueva_caja(id_sucursal: int, id_empresa: int, nombre: str, codigo_caja: Optional[str] = None) -> Dict[str, Any]:
    """
    Registra una nueva caja física para una sucursal y empresa.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        if not codigo_caja or not codigo_caja.strip():
            # Contar cajas existentes en la sucursal para generar código secuencial
            q_cnt = f"SELECT COUNT(*) FROM {schema}.t_caja WHERE id_sucursal = %s;"
            cnt = db.execute_query(q_cnt, (id_sucursal,), fetchone=True)[0] or 0
            codigo_caja = f"CAJA-SUC-{id_sucursal}-{(cnt + 1):02d}"

        q_insert = f"""
            INSERT INTO {schema}.t_caja (id_sucursal, id_empresa, codigo_caja, nombre, estado)
            VALUES (%s, %s, %s, %s, 'ACTIVA')
            RETURNING id_caja, codigo_caja, nombre, estado, id_sucursal, id_empresa, created_at;
        """
        row = db.execute_query(q_insert, (id_sucursal, id_empresa, codigo_caja.strip().upper(), nombre.strip()), fetchone=True, commit=True)
        return {
            "id_caja": row[0],
            "codigo_caja": row[1],
            "nombre": row[2],
            "estado": row[3],
            "id_sucursal": row[4],
            "id_empresa": row[5],
            "created_at": row[6].isoformat() if row[6] else None
        }
    finally:
        db.close_connection()

