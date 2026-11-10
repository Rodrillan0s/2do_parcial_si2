from app.core.postgres import PostgreSQL
from app.core.config import Config
from typing import Dict, Any, List, Optional

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def obtener_info_empresa_para_reporte_db(id_empresa: Optional[int] = 1) -> Dict[str, Any]:
    """
    Recupera los datos institucionales de la empresa para el encabezado del reporte corporativo.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        emp_id = id_empresa or 1
        q = f"""
            SELECT nombre_empresa, razon_social, COALESCE(nit, '1020304050'), COALESCE(direccion_fiscal, 'Av. San Martín #450'), COALESCE(telefono, '70011223')
            FROM {schema}.empresa
            WHERE id_empresa = %s;
        """
        row = db.execute_query(q, (emp_id,), fetchone=True)
        if row:
            return {
                "nombre_empresa": row[0],
                "razon_social": row[1],
                "nit": row[2],
                "direccion": row[3],
                "telefono": row[4]
            }
        return {
            "nombre_empresa": "AURA Atelier Bolivia",
            "razon_social": "AURA Atelier S.R.L.",
            "nit": "4045127018",
            "direccion": "Av. San Martín #450, Equipetrol",
            "telefono": "70011223"
        }
    finally:
        db.close_connection()


def obtener_reporte_ventas_db(
    id_empresa: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    estado: Optional[str] = None,
    id_metodo_pago: Optional[int] = None
) -> Dict[str, Any]:
    """
    Recupera el listado detallado de transacciones de venta con agregaciones.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        where = ["1=1"]
        params = []

        if id_empresa:
            where.append("v.id_empresa = %s")
            params.append(id_empresa)
        if id_sucursal:
            where.append("v.id_sucursal = %s")
            params.append(id_sucursal)
        if fecha_inicio:
            where.append("v.fecha_venta >= %s")
            params.append(fecha_inicio)
        if fecha_fin:
            where.append("v.fecha_venta <= %s")
            params.append(fecha_fin)
        if estado and estado.upper() != 'TODOS':
            where.append("UPPER(v.estado) = %s")
            params.append(estado.upper())
        else:
            where.append("UPPER(COALESCE(v.estado, '')) NOT IN ('ANULADA', 'CANCELADA')")
        if id_metodo_pago:
            where.append("p.id_metodo_pago = %s")
            params.append(id_metodo_pago)

        where_sql = " AND ".join(where)

        q = f"""
            SELECT 
                v.id_venta,
                v.numero_venta,
                TO_CHAR(v.fecha_venta, 'YYYY-MM-DD HH24:MI') AS fecha_formateada,
                s.nombre AS sucursal_nombre,
                COALESCE(v.razon_social, u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cliente Mostrador') AS cliente_nombre,
                COALESCE(v.nit_ci, '0') AS nit_ci,
                COALESCE(mp.nombre, 'Efectivo / Mostrador') AS metodo_pago,
                COALESCE(v.subtotal, 0) AS subtotal,
                COALESCE(v.descuento, 0) AS descuento,
                COALESCE(v.total, 0) AS total,
                COALESCE(v.estado, 'COMPLETADA') AS estado
            FROM {schema}.t_venta v
            JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = v.id_usuario
            LEFT JOIN {schema}.t_pago p ON p.id_venta = v.id_venta
            LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
            WHERE {where_sql}
            ORDER BY v.fecha_venta DESC;
        """
        rows = db.execute_query(q, tuple(params) if params else None, fetchall=True) or []

        items = []
        suma_total = 0.0
        suma_subtotal = 0.0
        suma_descuento = 0.0

        for r in rows:
            subt = float(r[7] or 0)
            desc = float(r[8] or 0)
            tot = float(r[9] or 0)
            suma_subtotal += subt
            suma_descuento += desc
            suma_total += tot
            items.append({
                "id_venta": r[0],
                "numero_venta": r[1],
                "fecha": r[2],
                "sucursal": r[3],
                "cliente": r[4],
                "nit_ci": r[5],
                "metodo_pago": r[6],
                "subtotal": subt,
                "descuento": desc,
                "total": tot,
                "estado": r[10]
            })

        cant = len(items)
        return {
            "items": items,
            "resumen": {
                "cantidad_ventas": cant,
                "total_recaudado": round(suma_total, 2),
                "total_subtotal": round(suma_subtotal, 2),
                "total_descuento": round(suma_descuento, 2),
                "ticket_promedio": round(suma_total / cant, 2) if cant > 0 else 0.0
            }
        }
    finally:
        db.close_connection()


def obtener_reporte_inventario_db(
    id_empresa: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    id_categoria: Optional[int] = None,
    estado_stock: Optional[str] = None
) -> Dict[str, Any]:
    """
    Recupera el listado detallado de existencias en almacenes y sucursales.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        where = ["1=1"]
        params = []

        if id_empresa:
            where.append("s.id_empresa = %s")
            params.append(id_empresa)
        if id_sucursal:
            where.append("i.id_sucursal = %s")
            params.append(id_sucursal)
        if id_categoria:
            where.append("p.id_categoria = %s")
            params.append(id_categoria)

        if estado_stock:
            est = estado_stock.lower()
            if est == 'bajo':
                where.append("i.stock_disponible <= i.stock_minimo AND i.stock_disponible > 0")
            elif est == 'agotado':
                where.append("i.stock_disponible = 0")
            elif est == 'disponible':
                where.append("i.stock_disponible > i.stock_minimo")

        where_sql = " AND ".join(where)

        q = f"""
            SELECT 
                p.id_producto,
                p.nombre AS producto_nombre,
                ptc.sku,
                p.codigo_producto,
                COALESCE(c.nombre, 'Alta Costura') AS categoria_nombre,
                COALESCE(t.nombre, '') AS talla,
                COALESCE(col.nombre, '') AS color,
                s.nombre AS sucursal_nombre,
                i.stock_actual,
                i.stock_reservado,
                i.stock_disponible,
                i.stock_minimo,
                CASE 
                    WHEN i.stock_disponible = 0 THEN 'AGOTADO'
                    WHEN i.stock_disponible <= i.stock_minimo THEN 'BAJO STOCK'
                    ELSE 'ÓPTIMO'
                END AS estado_alerta
            FROM {schema}.t_inventario i
            JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = i.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
            JOIN {schema}.t_sucursal s ON s.id_sucursal = i.id_sucursal
            LEFT JOIN {schema}.t_categoria c ON c.id_categoria = p.id_categoria
            LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
            LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color
            WHERE {where_sql}
            ORDER BY s.nombre ASC, p.nombre ASC, ptc.sku ASC;
        """
        rows = db.execute_query(q, tuple(params) if params else None, fetchall=True) or []

        items = []
        tot_actual = 0
        tot_reservado = 0
        tot_disponible = 0
        cant_agotados = 0
        cant_bajo = 0

        for r in rows:
            act = int(r[8] or 0)
            res = int(r[9] or 0)
            disp = int(r[10] or 0)
            tot_actual += act
            tot_reservado += res
            tot_disponible += disp
            alerta = r[12]
            if alerta == 'AGOTADO':
                cant_agotados += 1
            elif alerta == 'BAJO STOCK':
                cant_bajo += 1

            items.append({
                "id_producto": r[0],
                "producto": r[1],
                "sku": r[2],
                "codigo_producto": r[3],
                "categoria": r[4],
                "talla": r[5],
                "color": r[6],
                "sucursal": r[7],
                "stock_actual": act,
                "stock_reservado": res,
                "stock_disponible": disp,
                "stock_minimo": int(r[11] or 0),
                "estado_alerta": alerta
            })

        return {
            "items": items,
            "resumen": {
                "total_items_registrados": len(items),
                "stock_total_unidades": tot_actual,
                "stock_reservado_unidades": tot_reservado,
                "stock_disponible_unidades": tot_disponible,
                "items_agotados": cant_agotados,
                "items_bajo_stock": cant_bajo
            }
        }
    finally:
        db.close_connection()


def obtener_reporte_productos_vendidos_db(
    id_empresa: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    id_categoria: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None
) -> Dict[str, Any]:
    """
    Recupera el volumen de ventas e ingresos por producto/variante.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        where = ["1=1", "UPPER(COALESCE(v.estado, '')) NOT IN ('ANULADA', 'CANCELADA')"]
        params = []

        if id_empresa:
            where.append("v.id_empresa = %s")
            params.append(id_empresa)
        if id_sucursal:
            where.append("v.id_sucursal = %s")
            params.append(id_sucursal)
        if id_categoria:
            where.append("p.id_categoria = %s")
            params.append(id_categoria)
        if fecha_inicio:
            where.append("v.fecha_venta >= %s")
            params.append(fecha_inicio)
        if fecha_fin:
            where.append("v.fecha_venta <= %s")
            params.append(fecha_fin)

        where_sql = " AND ".join(where)

        q = f"""
            SELECT 
                p.id_producto,
                p.nombre AS producto_nombre,
                ptc.sku,
                COALESCE(c.nombre, 'Alta Costura') AS categoria_nombre,
                COALESCE(t.nombre, '') AS talla,
                COALESCE(col.nombre, '') AS color,
                COALESCE(SUM(dv.cantidad), 0) AS unidades_vendidas,
                COALESCE(AVG(dv.precio_unitario), 0) AS precio_promedio,
                COALESCE(SUM(dv.subtotal), 0) AS subtotal_ingresos
            FROM {schema}.t_detalle_venta dv
            JOIN {schema}.t_venta v ON v.id_venta = dv.id_venta
            JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dv.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
            LEFT JOIN {schema}.t_categoria c ON c.id_categoria = p.id_categoria
            LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
            LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color
            WHERE {where_sql}
            GROUP BY p.id_producto, p.nombre, ptc.sku, c.nombre, t.nombre, col.nombre
            ORDER BY unidades_vendidas DESC, subtotal_ingresos DESC;
        """
        rows = db.execute_query(q, tuple(params) if params else None, fetchall=True) or []

        items = []
        total_unidades = 0
        total_ingresos = 0.0

        for r in rows:
            u = int(r[6] or 0)
            subt = float(r[8] or 0)
            total_unidades += u
            total_ingresos += subt
            items.append({
                "id_producto": r[0],
                "producto": r[1],
                "sku": r[2],
                "categoria": r[3],
                "talla": r[4],
                "color": r[5],
                "unidades_vendidas": u,
                "precio_promedio": round(float(r[7] or 0), 2),
                "total_ingresos": round(subt, 2)
            })

        # Calcular participación %
        for it in items:
            it["participacion_pct"] = round((it["total_ingresos"] / total_ingresos * 100), 1) if total_ingresos > 0 else 0.0

        return {
            "items": items,
            "resumen": {
                "total_productos_distintos": len(items),
                "total_unidades_vendidas": total_unidades,
                "total_ingresos": round(total_ingresos, 2),
                "precio_promedio_general": round(total_ingresos / total_unidades, 2) if total_unidades > 0 else 0.0
            }
        }
    finally:
        db.close_connection()


def obtener_reporte_sucursales_db(
    id_empresa: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None
) -> Dict[str, Any]:
    """
    Recupera la comparativa entre sucursales: ventas, ingresos y prendas vendidas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        v_where = ["1=1", "UPPER(COALESCE(v.estado, '')) NOT IN ('ANULADA', 'CANCELADA')"]
        params = []

        if id_empresa:
            v_where.append("v.id_empresa = %s")
            params.append(id_empresa)
        if fecha_inicio:
            v_where.append("v.fecha_venta >= %s")
            params.append(fecha_inicio)
        if fecha_fin:
            v_where.append("v.fecha_venta <= %s")
            params.append(fecha_fin)

        v_where_sql = " AND ".join(v_where)

        s_where = ["s.activo = TRUE"]
        s_params = []
        if id_empresa:
            s_where.append("s.id_empresa = %s")
            s_params.append(id_empresa)
        s_where_sql = " AND ".join(s_where)

        q = f"""
            SELECT 
                s.id_sucursal,
                s.nombre AS sucursal_nombre,
                COALESCE(c.nombre, 'No asignada') AS ciudad,
                s.telefono,
                COUNT(v.id_venta) AS cantidad_ventas,
                COALESCE(SUM(v.total), 0) AS total_ingresos,
                COALESCE(SUM(dv_agg.total_items), 0) AS total_unidades,
                COALESCE(AVG(v.total), 0) AS ticket_promedio
            FROM {schema}.t_sucursal s
            LEFT JOIN {schema}.t_ciudad c ON c.id_ciudad = s.id_ciudad
            LEFT JOIN {schema}.t_venta v ON v.id_sucursal = s.id_sucursal AND {v_where_sql}
            LEFT JOIN (
                SELECT id_venta, SUM(cantidad) AS total_items
                FROM {schema}.t_detalle_venta
                GROUP BY id_venta
            ) dv_agg ON dv_agg.id_venta = v.id_venta
            WHERE {s_where_sql}
            GROUP BY s.id_sucursal, s.nombre, c.nombre, s.telefono
            ORDER BY total_ingresos DESC;
        """
        all_params = params + s_params
        rows = db.execute_query(q, tuple(all_params) if all_params else None, fetchall=True) or []

        items = []
        tot_tx = 0
        tot_ing = 0.0
        tot_unid = 0

        for r in rows:
            tx = int(r[4] or 0)
            ing = float(r[5] or 0)
            unid = int(r[6] or 0)
            tot_tx += tx
            tot_ing += ing
            tot_unid += unid

            items.append({
                "id_sucursal": r[0],
                "sucursal": r[1],
                "ciudad": r[2],
                "telefono": r[3] or "",
                "cantidad_ventas": tx,
                "total_ingresos": round(ing, 2),
                "unidades_vendidas": unid,
                "ticket_promedio": round(float(r[7] or 0), 2)
            })

        for it in items:
            it["participacion_ingresos_pct"] = round((it["total_ingresos"] / tot_ing * 100), 1) if tot_ing > 0 else 0.0

        return {
            "items": items,
            "resumen": {
                "total_sucursales": len(items),
                "total_ventas": tot_tx,
                "total_ingresos": round(tot_ing, 2),
                "total_unidades_vendidas": tot_unid,
                "ticket_promedio_general": round(tot_ing / tot_tx, 2) if tot_tx > 0 else 0.0
            }
        }
    finally:
        db.close_connection()


def obtener_reporte_valoraciones_db(
    id_empresa: Optional[int] = None,
    id_sucursal: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    puntuacion: Optional[int] = None,
    requiere_revision: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Recupera el listado detallado de valoraciones y satisfacción de clientes con métricas agregadas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        where = ["1=1"]
        params = []

        if id_empresa:
            where.append("val.id_empresa = %s")
            params.append(id_empresa)
        if id_sucursal:
            where.append("val.id_sucursal = %s")
            params.append(id_sucursal)
        if fecha_inicio:
            where.append("val.fecha_creacion >= %s")
            params.append(fecha_inicio)
        if fecha_fin:
            where.append("val.fecha_creacion <= %s")
            params.append(fecha_fin)
        if puntuacion:
            where.append("val.puntuacion = %s")
            params.append(puntuacion)
        if requiere_revision is not None:
            where.append("val.requiere_revision = %s")
            params.append(requiere_revision)

        where_sql = " AND ".join(where)

        q = f"""
            SELECT 
                val.id_valoracion,
                TO_CHAR(val.fecha_creacion, 'YYYY-MM-DD HH24:MI') AS fecha,
                COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cliente Anónimo') AS cliente,
                COALESCE(p.nombre, 'Servicio General') AS producto,
                COALESCE(cat.nombre, 'Servicio / General') AS categoria,
                COALESCE(s.nombre, 'Sin sucursal') AS sucursal,
                val.puntuacion,
                COALESCE(ped.codigo_pedido, v.numero_venta, 'Sin código') AS codigo_referencia,
                COALESCE(val.motivo_negativo, 'Ninguno') AS motivo_negativo,
                COALESCE(val.comentario, '') AS comentario,
                CASE 
                    WHEN val.puntuacion >= 4 THEN 'POSITIVA'
                    WHEN val.puntuacion = 3 THEN 'NEUTRA'
                    ELSE 'CRITICA'
                END AS estado_satisfaccion,
                val.requiere_revision
            FROM {schema}.t_valoracion val
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = val.id_sucursal
            LEFT JOIN {schema}.t_producto p ON p.id_producto = val.id_producto
            LEFT JOIN {schema}.t_categoria cat ON cat.id_categoria = p.id_categoria
            LEFT JOIN {schema}.t_cliente cli ON cli.id_cliente = val.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = cli.id_usuario
            LEFT JOIN {schema}.t_pedido ped ON ped.id_pedido = val.id_pedido
            LEFT JOIN {schema}.t_venta v ON v.id_venta = val.id_venta
            WHERE {where_sql}
            ORDER BY val.fecha_creacion DESC;
        """
        rows = db.execute_query(q, tuple(params) if params else None, fetchall=True) or []

        items = []
        suma_puntuacion = 0
        positivas = 0
        criticas = 0

        for r in rows:
            pts = int(r[6] or 0)
            suma_puntuacion += pts
            if pts >= 4:
                positivas += 1
            elif pts <= 2:
                criticas += 1

            items.append({
                "id_valoracion": r[0],
                "fecha": r[1],
                "cliente": r[2],
                "producto": r[3],
                "categoria": r[4],
                "sucursal": r[5],
                "puntuacion": pts,
                "codigo_referencia": r[7],
                "motivo_negativo": r[8],
                "comentario": r[9],
                "estado_satisfaccion": r[10],
                "requiere_revision": bool(r[11])
            })

        total_reg = len(items)
        promedio = round(suma_puntuacion / total_reg, 2) if total_reg > 0 else 0.0
        csat_pct = round((positivas / total_reg * 100), 1) if total_reg > 0 else 0.0

        return {
            "items": items,
            "resumen": {
                "total_valoraciones": total_reg,
                "calificacion_promedio": promedio,
                "tasa_satisfaccion_pct": csat_pct,
                "valoraciones_positivas": positivas,
                "alertas_criticas": criticas
            }
        }
    finally:
        db.close_connection()

