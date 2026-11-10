import logging
import json
from typing import Dict, Any, List, Optional
from app.core.postgres import PostgreSQL, atomic
from app.core.config import Config

logger = logging.getLogger(__name__)

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def obtener_politica_contingencia(id_empresa: int) -> Dict[str, Any]:
    """
    Obtiene la política de contingencia offline configurada para el tenant.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT COALESCE(politica_contingencia_pos, '{{}}'::jsonb)
            FROM {schema}.empresa
            WHERE id_empresa = %s;
        """
        row = db.execute_query(q, (id_empresa,), fetchone=True)
        politica_defecto = {
            "habilitado": True,
            "modo": "PORCENTAJE",
            "porcentaje_defecto": 15.0,
            "cantidad_fija_defecto": 2,
            "minimo_unidades": 1,
            "maximo_unidades": 10,
            "permitir_sobreventa_con_incidencia": True,
            "solo_efectivo_offline": True
        }
        if row and row[0]:
            if isinstance(row[0], dict):
                politica_defecto.update(row[0])
            elif isinstance(row[0], str):
                try:
                    politica_defecto.update(json.loads(row[0]))
                except Exception:
                    pass
        return politica_defecto
    finally:
        db.close_connection()

def actualizar_politica_contingencia(id_empresa: int, nueva_politica: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualiza la política de contingencia offline del tenant.
    """
    actual = obtener_politica_contingencia(id_empresa)
    actual.update(nueva_politica)
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            UPDATE {schema}.empresa
            SET politica_contingencia_pos = %s::jsonb
            WHERE id_empresa = %s;
        """
        db.execute_query(q, (json.dumps(actual), id_empresa), commit=True)
        return actual
    finally:
        db.close_connection()

def calcular_y_asignar_cuotas_sesion(
    id_sesion_caja: int,
    id_caja: int,
    id_sucursal: int,
    id_empresa: int,
    db: Optional[PostgreSQL] = None
) -> List[Dict[str, Any]]:
    """
    Calcula y preasigna transaccionalmente las cuotas de contingencia para una sesión de caja.
    Garantiza que una misma unidad física no sea asignada a dos terminales activos.
    """
    own_conn = False
    if db is None:
        db = PostgreSQL()
        db.create_connection()
        own_conn = True

    try:
        schema = _get_schema()
        politica = obtener_politica_contingencia(id_empresa)
        if not politica.get("habilitado", True):
            return []

        # 1. Obtener inventario de la sucursal con bloqueo FOR UPDATE
        q_inv = f"""
            SELECT 
                inv.id_inventario,
                inv.id_variante,
                inv.stock_actual,
                COALESCE(inv.stock_reservado, 0) AS stock_reservado,
                COALESCE(inv.stock_contingencia, 0) AS stock_contingencia,
                inv.cuota_manual_contingencia,
                v.sku,
                p.nombre AS nombre_producto,
                COALESCE(v.precio, p.precio, 0.00) AS precio
            FROM {schema}.t_inventario inv
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = inv.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            WHERE inv.id_sucursal = %s AND p.id_empresa = %s AND p.activo = TRUE AND v.activo = TRUE
            ORDER BY inv.id_variante ASC
            FOR UPDATE OF inv;
        """
        items_inv = db.execute_query(q_inv, (id_sucursal, id_empresa), fetchall=True) or []
        cuotas_generadas = []

        # 2. Consultar cuotas ya activas en otras sesiones abiertas de la sucursal
        q_otras_cuotas = f"""
            SELECT id_variante, COALESCE(SUM(cuota_asignada - cuota_consumida), 0)
            FROM {schema}.t_caja_cuota_contingencia
            WHERE id_sucursal = %s AND estado = 'ACTIVA' AND id_sesion_caja != %s
            GROUP BY id_variante;
        """
        otras_rows = db.execute_query(q_otras_cuotas, (id_sucursal, id_sesion_caja), fetchall=True) or []
        otras_comprometidas = {r[0]: int(r[1]) for r in otras_rows}

        modo = politica.get("modo", "PORCENTAJE").upper()
        pct = float(politica.get("porcentaje_defecto", 15.0)) / 100.0
        fijo = int(politica.get("cantidad_fija_defecto", 2))
        min_u = int(politica.get("minimo_unidades", 1))
        max_u = int(politica.get("maximo_unidades", 10))

        for row in items_inv:
            id_inv, id_var, st_actual, st_res, st_cont, cuota_man, sku, prod_nom, precio = row
            st_actual = int(st_actual or 0)
            st_res = int(st_res or 0)
            st_cont = int(st_cont or 0)

            # Unidades físicas libres en la tienda antes de contingencia
            disponible_total = max(st_actual - st_res, 0)
            if disponible_total <= 0:
                continue

            # Determinación híbrida de la cuota deseada
            if cuota_man is not None:
                cuota_objetivo = int(cuota_man)
            elif modo == "CANTIDAD_FIJA":
                cuota_objetivo = fijo
            else:  # PORCENTAJE
                cuota_objetivo = max(min_u, int(round(disponible_total * pct)))

            cuota_objetivo = min(max(cuota_objetivo, min_u), max_u)
            cuota_objetivo = min(cuota_objetivo, disponible_total)

            # Descontar lo comprometido en otras cajas activas
            ya_comprometido = otras_comprometidas.get(id_var, 0)
            cuota_posible = max(disponible_total - ya_comprometido, 0)
            cuota_asignar = min(cuota_objetivo, cuota_posible)

            if cuota_asignar <= 0:
                continue

            # Actualizar stock_contingencia en t_inventario para que no compita online
            nuevo_stock_contingencia = max(st_cont, cuota_asignar + ya_comprometido)
            nuevo_stock_contingencia = min(nuevo_stock_contingencia, disponible_total)

            q_upd_inv = f"""
                UPDATE {schema}.t_inventario
                SET stock_contingencia = %s,
                    stock_disponible = GREATEST(stock_actual - COALESCE(stock_reservado, 0) - %s, 0)
                WHERE id_inventario = %s;
            """
            db.execute_query(q_upd_inv, (nuevo_stock_contingencia, nuevo_stock_contingencia, id_inv))

            # Upsert en t_caja_cuota_contingencia para esta sesión
            q_upsert_cuota = f"""
                INSERT INTO {schema}.t_caja_cuota_contingencia (
                    id_empresa, id_sucursal, id_caja, id_sesion_caja, id_variante,
                    cuota_asignada, cuota_consumida, estado, fecha_asignacion
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, 0, 'ACTIVA', CURRENT_TIMESTAMP
                )
                ON CONFLICT (id_sesion_caja, id_variante) DO UPDATE
                SET cuota_asignada = EXCLUDED.cuota_asignada,
                    estado = 'ACTIVA'
                RETURNING id_cuota;
            """
            cuota_res = db.execute_query(
                q_upsert_cuota,
                (id_empresa, id_sucursal, id_caja, id_sesion_caja, id_var, cuota_asignar),
                fetchone=True
            )
            id_cuota = cuota_res[0] if cuota_res else None

            cuotas_generadas.append({
                "id_cuota": id_cuota,
                "id_variante": id_var,
                "sku": sku,
                "producto_nombre": prod_nom,
                "precio_unitario": float(precio),
                "cuota_asignada": cuota_asignar,
                "cuota_consumida": 0,
                "cuota_disponible": cuota_asignar
            })

        if own_conn:
            db.conn.commit()

        return cuotas_generadas
    except Exception as e:
        if own_conn and db.conn:
            db.conn.rollback()
        logger.error(f"Error asignando cuotas de contingencia: {e}")
        raise
    finally:
        if own_conn:
            db.close_connection()

def obtener_cuotas_activas_sesion(id_sesion_caja: int, id_empresa: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retorna el listado de cuotas de contingencia activas y disponibles para la sesión de caja,
    destinado a la descarga y cacheo local en IndexedDB.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        emp_filter = "AND c.id_empresa = %s" if id_empresa else ""
        params: List[Any] = [id_sesion_caja]
        if id_empresa:
            params.append(id_empresa)
        q = f"""
            SELECT 
                c.id_cuota,
                c.id_sesion_caja,
                c.id_caja,
                c.id_sucursal,
                c.id_empresa,
                c.id_variante,
                v.sku,
                p.nombre AS producto_nombre,
                COALESCE(v.precio, p.precio, 0.00) AS precio_unitario,
                c.cuota_asignada,
                c.cuota_consumida,
                GREATEST(c.cuota_asignada - c.cuota_consumida, 0) AS cuota_disponible,
                c.estado,
                c.fecha_asignacion
            FROM {schema}.t_caja_cuota_contingencia c
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = c.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            WHERE c.id_sesion_caja = %s AND c.estado = 'ACTIVA' {emp_filter}
            ORDER BY p.nombre ASC, v.id_variante ASC;
        """
        rows = db.execute_query(q, tuple(params), fetchall=True) or []
        resultado = []
        for r in rows:
            resultado.append({
                "id_cuota": r[0],
                "id_sesion_caja": r[1],
                "id_caja": r[2],
                "id_sucursal": r[3],
                "id_empresa": r[4],
                "id_variante": r[5],
                "sku": r[6],
                "producto_nombre": r[7],
                "precio_unitario": float(r[8]),
                "cuota_asignada": int(r[9]),
                "cuota_consumida": int(r[10]),
                "cuota_disponible": int(r[11]),
                "estado": r[12],
                "fecha_asignacion": r[13].isoformat() if r[13] else None
            })
        return resultado
    finally:
        db.close_connection()

def consumir_cuota_contingencia_transaccional(
    db: PostgreSQL,
    id_sesion_caja: int,
    id_variante: int,
    cantidad: int,
    id_sucursal: int
) -> Optional[int]:
    """
    Consume de la cuota de contingencia asignada a la caja dentro de una transacción activa.
    Retorna el id_cuota si fue cubierto total o parcialmente por contingencia.
    """
    schema = _get_schema()
    q_cuota = f"""
        SELECT id_cuota, cuota_asignada, cuota_consumida
        FROM {schema}.t_caja_cuota_contingencia
        WHERE id_sesion_caja = %s AND id_variante = %s AND estado = 'ACTIVA'
        FOR UPDATE;
    """
    row = db.execute_query(q_cuota, (id_sesion_caja, id_variante), fetchone=True)
    if not row:
        return None

    id_cuota, asignada, consumida = row
    disponible = max(asignada - consumida, 0)
    consumo_real = min(disponible, cantidad)

    if consumo_real > 0:
        q_upd = f"""
            UPDATE {schema}.t_caja_cuota_contingencia
            SET cuota_consumida = cuota_consumida + %s
            WHERE id_cuota = %s;
        """
        db.execute_query(q_upd, (consumo_real, id_cuota))

        # Disminuir stock_contingencia en t_inventario y restituir a stock_disponible
        # la porción que fn_registrar_venta_pos había descontado de disponible,
        # protegiendo el stock online de la tienda y preservando la ecuación de balance.
        q_inv = f"""
            UPDATE {schema}.t_inventario
            SET stock_contingencia = GREATEST(stock_contingencia - %s, 0),
                stock_disponible = stock_disponible + %s
            WHERE id_sucursal = %s AND id_variante = %s;
        """
        db.execute_query(q_inv, (consumo_real, consumo_real, id_sucursal, id_variante))

    return id_cuota

def registrar_incidencia_sobreventa(
    db: PostgreSQL,
    id_empresa: int,
    id_sucursal: int,
    id_venta_pos: Optional[int],
    id_variante: int,
    cantidad_solicitada: int,
    stock_fisico_disponible: int,
    observaciones: str,
    creado_por: Optional[int]
) -> int:
    """
    Registra una incidencia de sobreventa para resolución centralizada.
    """
    schema = _get_schema()
    q = f"""
        INSERT INTO {schema}.t_incidencia_sobreventa (
            id_empresa, id_sucursal, id_venta_pos, id_variante,
            cantidad_solicitada, stock_fisico_disponible, estado,
            observaciones, creado_por, creado_en
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, 'PENDIENTE_CONCILIACION',
            %s, %s, CURRENT_TIMESTAMP
        )
        RETURNING id_incidencia;
    """
    row = db.execute_query(
        q,
        (id_empresa, id_sucursal, id_venta_pos, id_variante,
         cantidad_solicitada, stock_fisico_disponible, observaciones, creado_por),
        fetchone=True
    )
    return row[0] if row else 0

def liberar_cuotas_sesion_caja(id_sesion_caja: int, db: Optional[PostgreSQL] = None) -> int:
    """
    Al cerrar la caja (una vez conciliadas las operaciones pendientes),
    devuelve las cuotas no consumidas al inventario disponible general.
    """
    own_conn = False
    if db is None:
        db = PostgreSQL()
        db.create_connection()
        own_conn = True

    try:
        schema = _get_schema()
        # 1. Obtener cuotas no consumidas de la sesión
        q = f"""
            SELECT id_cuota, id_sucursal, id_variante, (cuota_asignada - cuota_consumida) AS remanente
            FROM {schema}.t_caja_cuota_contingencia
            WHERE id_sesion_caja = %s AND estado = 'ACTIVA' AND (cuota_asignada - cuota_consumida) > 0
            FOR UPDATE;
        """
        rows = db.execute_query(q, (id_sesion_caja,), fetchall=True) or []
        liberadas = 0

        for r in rows:
            id_cuota, id_suc, id_var, remanente = r
            remanente = int(remanente or 0)
            if remanente > 0:
                # Disminuir stock_contingencia en inventario para devolverlo a disponible online
                q_inv = f"""
                    UPDATE {schema}.t_inventario
                    SET stock_contingencia = GREATEST(stock_contingencia - %s, 0),
                        stock_disponible = GREATEST(stock_actual - COALESCE(stock_reservado, 0) - GREATEST(stock_contingencia - %s, 0), 0)
                    WHERE id_sucursal = %s AND id_variante = %s;
                """
                db.execute_query(q_inv, (remanente, remanente, id_suc, id_var))
                liberadas += remanente

        # 2. Marcar cuotas como LIBERADAS
        q_lib = f"""
            UPDATE {schema}.t_caja_cuota_contingencia
            SET estado = 'LIBERADA',
                fecha_conciliacion = CURRENT_TIMESTAMP
            WHERE id_sesion_caja = %s AND estado = 'ACTIVA';
        """
        db.execute_query(q_lib, (id_sesion_caja,))

        if own_conn:
            db.conn.commit()

        return liberadas
    except Exception as e:
        if own_conn and db.conn:
            db.conn.rollback()
        logger.error(f"Error liberando cuotas de contingencia: {e}")
        raise
    finally:
        if own_conn:
            db.close_connection()

def listar_incidencias_sobreventa(id_empresa: int, estado: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lista las incidencias de sobreventa para resolución por administradores.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        estado_clause = "AND inc.estado = %s" if estado else ""
        params = [id_empresa]
        if estado:
            params.append(estado)

        q = f"""
            SELECT 
                inc.id_incidencia,
                inc.id_empresa,
                inc.id_sucursal,
                suc.nombre AS nombre_sucursal,
                inc.id_venta_pos,
                v.numero_venta,
                inc.id_variante,
                p.nombre AS nombre_producto,
                var.sku,
                inc.cantidad_solicitada,
                inc.stock_fisico_disponible,
                inc.estado,
                inc.resolucion_tipo,
                inc.observaciones,
                inc.creado_en
            FROM {schema}.t_incidencia_sobreventa inc
            JOIN {schema}.t_sucursal suc ON suc.id_sucursal = inc.id_sucursal
            LEFT JOIN {schema}.t_venta v ON v.id_venta = inc.id_venta_pos
            JOIN {schema}.t_producto_talla_color var ON var.id_variante = inc.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = var.id_producto
            WHERE inc.id_empresa = %s {estado_clause}
            ORDER BY inc.creado_en DESC;
        """
        rows = db.execute_query(q, tuple(params), fetchall=True) or []
        resultado = []
        for r in rows:
            resultado.append({
                "id_incidencia": r[0],
                "id_empresa": r[1],
                "id_sucursal": r[2],
                "nombre_sucursal": r[3],
                "id_venta_pos": r[4],
                "numero_venta": r[5] or "N/A",
                "id_variante": r[6],
                "nombre_producto": r[7],
                "sku": r[8],
                "cantidad_solicitada": int(r[9]),
                "stock_fisico_disponible": int(r[10]),
                "estado": r[11],
                "resolucion_tipo": r[12],
                "observaciones": r[13],
                "creado_en": r[14].isoformat() if r[14] else None
            })
        return resultado
    finally:
        db.close_connection()
