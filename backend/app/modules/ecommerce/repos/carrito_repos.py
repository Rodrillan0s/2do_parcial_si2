from typing import Optional, Dict, Any, List
from app.core.postgres import PostgreSQL, atomic
from fastapi import HTTPException
from app.core.config import Config

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def obtener_o_crear_cliente(id_usuario: int) -> int:
    """
    Obtiene el id_cliente asociado al usuario autenticado.
    Si aún no existe registro en t_cliente para este usuario, lo crea automáticamente.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q_find = f"SELECT id_cliente FROM {schema}.t_cliente WHERE id_usuario = %s ORDER BY id_cliente LIMIT 2;"
        rows = db.execute_query(q_find, (id_usuario,), fetchall=True) or []
        if len(rows) > 1:
            raise HTTPException(409, 'CLIENT_PROFILE_RECONCILIATION_REQUIRED: varios perfiles; no se eligió ni fusionó ninguno.')
        res = rows[0] if rows else None
        if res:
            return res[0]

        db.close_connection()
        return _crear_cliente_serializado(id_usuario)
    finally:
        db.close_connection()


@atomic
def _crear_cliente_serializado(id_usuario):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        db.execute_query('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                         (f'client-profile:{schema}:{id_usuario}',))
        rows = db.execute_query(f'SELECT id_cliente FROM {schema}.t_cliente WHERE id_usuario=%s ORDER BY id_cliente LIMIT 2',
                                (id_usuario,), fetchall=True) or []
        if len(rows) > 1:
            raise HTTPException(409, 'CLIENT_PROFILE_RECONCILIATION_REQUIRED: varios perfiles; requiere conciliación.')
        if rows:
            return rows[0][0]
        q_ins = f"""
            INSERT INTO {schema}.t_cliente (id_usuario, fecha_registro)
            VALUES (%s, NOW())
            RETURNING id_cliente;
        """
        ins_res = db.execute_query(q_ins, (id_usuario,), fetchone=True, commit=True)
        return ins_res[0]
    finally:
        db.close_connection(commit=True)

def obtener_id_carrito_activo(id_cliente: int, id_empresa: int) -> int:
    """
    Recupera el carrito activo del cliente para la empresa (Tenant) indicada.
    Si no existe uno activo, crea un nuevo registro.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q_find = f"""
            SELECT id_carrito 
            FROM {schema}.t_carrito 
            WHERE id_cliente = %s AND id_empresa = %s AND estado = 'ACTIVO' 
            LIMIT 1;
        """
        res = db.execute_query(q_find, (id_cliente, id_empresa), fetchone=True)
        if res:
            return res[0]

        # Crear nuevo carrito activo
        q_ins = f"""
            INSERT INTO {schema}.t_carrito (id_cliente, id_empresa, estado, fecha_creacion, fecha_actualizacion)
            VALUES (%s, %s, 'ACTIVO', NOW(), NOW())
            RETURNING id_carrito;
        """
        ins_res = db.execute_query(q_ins, (id_cliente, id_empresa), fetchone=True, commit=True)
        return ins_res[0]
    finally:
        db.close_connection(commit=True)

def obtener_stock_total_variante(id_variante: int, id_empresa: int) -> int:
    """
    Calcula el stock total disponible vigente para una variante en todas
    las sucursales activas del Tenant. Evita valores negativos.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT COALESCE(SUM(GREATEST(0, inv.stock_disponible)), 0)
            FROM {schema}.t_inventario inv
            JOIN {schema}.t_sucursal s ON s.id_sucursal = inv.id_sucursal
            WHERE inv.id_variante = %s AND s.id_empresa = %s AND s.activo = TRUE AND inv.estado = TRUE;
        """
        res = db.execute_query(q, (id_variante, id_empresa), fetchone=True)
        return int(res[0]) if res else 0
    finally:
        db.close_connection()

def obtener_empresa_de_variante(id_variante: int) -> Optional[int]:
    """
    Recupera el id_empresa al que pertenece una variante de producto.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT p.id_empresa
            FROM {schema}.t_producto_talla_color v
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            WHERE v.id_variante = %s
            LIMIT 1;
        """
        res = db.execute_query(q, (id_variante,), fetchone=True)
        return int(res[0]) if res else None
    finally:
        db.close_connection()

def obtener_datos_variante_tenant(id_variante: int, id_empresa: int) -> Optional[Dict[str, Any]]:
    """
    Verifica que la variante exista, pertenezca a un producto activo del Tenant
    indicado y que talla, color y prenda se encuentren activos.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT 
                v.id_variante,
                v.id_producto,
                p.id_empresa,
                p.nombre AS producto_nombre,
                p.codigo_producto,
                t.id_talla,
                t.nombre AS talla_nombre,
                col.id_color,
                col.nombre AS color_nombre,
                col.codigo_hex,
                v.sku,
                COALESCE(v.precio, p.precio) AS precio_vigente,
                (
                    SELECT img.imagen_url 
                    FROM {schema}.t_producto_imagen img 
                    WHERE img.id_producto = p.id_producto 
                    ORDER BY img.es_principal DESC, img.orden ASC, img.id_imagen ASC 
                    LIMIT 1
                ) AS imagen_url,
                p.activo AS producto_activo,
                v.activo AS variante_activa
            FROM {schema}.t_producto_talla_color v
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            JOIN {schema}.t_talla t ON t.id_talla = v.id_talla AND t.activo = TRUE
            JOIN {schema}.t_color col ON col.id_color = v.id_color AND col.activo = TRUE
            WHERE v.id_variante = %s AND p.id_empresa = %s
            LIMIT 1;
        """
        r = db.execute_query(q, (id_variante, id_empresa), fetchone=True)
        if not r:
            return None

        return {
            "id_variante": r[0],
            "id_producto": r[1],
            "id_empresa": r[2],
            "producto_nombre": r[3],
            "codigo_producto": r[4],
            "id_talla": r[5],
            "talla_nombre": r[6],
            "id_color": r[7],
            "color_nombre": r[8],
            "codigo_hex": r[9],
            "sku": r[10],
            "precio_vigente": float(r[11]) if r[11] is not None else 0.0,
            "imagen_url": r[12],
            "producto_activo": r[13],
            "variante_activa": r[14]
        }
    finally:
        db.close_connection()

def consultar_carrito_completo(id_usuario: int, id_empresa: int) -> Dict[str, Any]:
    """
    Obtiene el carrito activo del usuario para el Tenant especificado.
    Recalcula la disponibilidad vigente y precios actuales en tiempo real.
    Si algún producto tiene stock insuficiente o se ha desactivado, lo marca claramente.
    """
    id_cliente = obtener_o_crear_cliente(id_usuario)
    id_carrito = obtener_id_carrito_activo(id_cliente, id_empresa)

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Obtener datos de la empresa
        q_emp = f"SELECT nombre_empresa FROM {schema}.empresa WHERE id_empresa = %s LIMIT 1;"
        emp_res = db.execute_query(q_emp, (id_empresa,), fetchone=True)
        nombre_empresa = emp_res[0] if emp_res else "Boutique AURA"

        # Consultar detalles del carrito junto con el stock disponible por variante en 1 sola consulta (sin N+1)
        q_items = f"""
            SELECT 
                d.id_detalle_carrito,
                d.id_variante,
                d.cantidad,
                d.precio_unitario,
                d.subtotal,
                p.id_producto,
                p.nombre AS producto_nombre,
                p.codigo_producto,
                t.nombre AS talla_nombre,
                col.nombre AS color_nombre,
                col.codigo_hex,
                v.sku,
                COALESCE(v.precio, p.precio) AS precio_vigente,
                (
                    SELECT img.imagen_url 
                    FROM {schema}.t_producto_imagen img 
                    WHERE img.id_producto = p.id_producto 
                    ORDER BY img.es_principal DESC, img.orden ASC, img.id_imagen ASC 
                    LIMIT 1
                ) AS imagen_url,
                p.activo AS producto_activo,
                v.activo AS variante_activa,
                COALESCE(stk.stock_total, 0) AS stock_disponible_total
            FROM {schema}.t_detalle_carrito d
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = d.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            JOIN {schema}.t_talla t ON t.id_talla = v.id_talla
            JOIN {schema}.t_color col ON col.id_color = v.id_color
            LEFT JOIN (
                SELECT inv.id_variante, COALESCE(SUM(GREATEST(0, inv.stock_disponible)), 0)::int AS stock_total
                FROM {schema}.t_inventario inv
                JOIN {schema}.t_sucursal s ON s.id_sucursal = inv.id_sucursal
                WHERE s.id_empresa = %s AND s.activo = TRUE AND inv.estado = TRUE
                GROUP BY inv.id_variante
            ) stk ON stk.id_variante = d.id_variante
            WHERE d.id_carrito = %s AND p.id_empresa = %s
            ORDER BY d.id_detalle_carrito ASC;
        """
        filas = db.execute_query(q_items, (id_empresa, id_carrito, id_empresa), fetchall=True) or []

        items: List[Dict[str, Any]] = []
        total_items = 0
        subtotal_acumulado = 0.0
        todos_tienen_stock = True

        for r in filas:
            id_det = r[0]
            id_var = r[1]
            cant = r[2]
            p_unit_db = float(r[3]) if r[3] is not None else 0.0
            p_vigente = float(r[12]) if r[12] is not None else p_unit_db

            # Recalcular precio vigente si cambió
            precio_final = p_vigente
            subtot = round(cant * precio_final, 2)
            if p_unit_db != precio_final:
                # Sincronizar precio en BD
                db.execute_query(
                    f"UPDATE {schema}.t_detalle_carrito SET precio_unitario = %s, subtotal = %s WHERE id_detalle_carrito = %s;",
                    (precio_final, subtot, id_det),
                    commit=True
                )

            # Stock disponible calculado en el JOIN agrupado sin consulta N+1 adicional
            stock_disp = int(r[16] or 0)
            prod_activo = bool(r[14])
            var_activa = bool(r[15])

            es_valido = prod_activo and var_activa and stock_disp >= cant and cant > 0
            advertencia = None

            if not prod_activo or not var_activa:
                advertencia = "Esta prenda o variante ha sido descontinuada."
                todos_tienen_stock = False
            elif stock_disp == 0:
                advertencia = "Prenda agotada en todas las sucursales."
                todos_tienen_stock = False
            elif stock_disp < cant:
                advertencia = f"Stock insuficiente. Solo quedan {stock_disp} unidades disponibles."
                todos_tienen_stock = False

            total_items += cant
            subtotal_acumulado += subtot

            items.append({
                "id_detalle_carrito": id_det,
                "id_variante": id_var,
                "id_producto": r[5],
                "producto_nombre": r[6],
                "codigo_producto": r[7],
                "talla_nombre": r[8],
                "color_nombre": r[9],
                "codigo_hex": r[10],
                "sku": r[11],
                "imagen_url": r[13],
                "cantidad": cant,
                "precio_unitario": precio_final,
                "subtotal": subtot,
                "stock_disponible": stock_disp,
                "disponible": es_valido,
                "advertencia_stock": advertencia
            })

        puede_continuar = (len(items) > 0) and todos_tienen_stock

        return {
            "id_carrito": id_carrito,
            "id_empresa": id_empresa,
            "nombre_empresa": nombre_empresa,
            "items": items,
            "total_items": total_items,
            "subtotal": round(subtotal_acumulado, 2),
            "descuento": 0.0,
            "total": round(subtotal_acumulado, 2),
            "puede_continuar_compra": puede_continuar
        }
    finally:
        db.close_connection(commit=True)

def agregar_item_al_carrito(id_usuario: int, id_empresa: int, id_variante: int, cantidad: int) -> Dict[str, Any]:
    """
    Agrega una variante al carrito del cliente para el Tenant actual.
    Valida que pertenezca a la empresa, que la cantidad sea > 0 y no supere el stock vigente.
    """
    if cantidad <= 0:
        raise ValueError("La cantidad solicitada debe ser mayor a 0.")

    # 1. Validar que la variante exista y pertenezca al Tenant
    var_data = obtener_datos_variante_tenant(id_variante, id_empresa)
    if not var_data:
        raise ValueError("La prenda seleccionada no existe o no pertenece a esta tienda.")

    if not var_data["producto_activo"] or not var_data["variante_activa"]:
        raise ValueError("La prenda o variante seleccionada se encuentra inactiva.")

    # 2. Validar stock disponible vigente
    stock_disp = obtener_stock_total_variante(id_variante, id_empresa)
    if stock_disp <= 0:
        raise ValueError("Esta prenda no tiene existencias disponibles en las sucursales físicas.")

    id_cliente = obtener_o_crear_cliente(id_usuario)
    id_carrito = obtener_id_carrito_activo(id_cliente, id_empresa)

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Verificar si la variante ya existe en el carrito
        q_find = f"""
            SELECT id_detalle_carrito, cantidad 
            FROM {schema}.t_detalle_carrito 
            WHERE id_carrito = %s AND id_variante = %s 
            LIMIT 1;
        """
        item_existente = db.execute_query(q_find, (id_carrito, id_variante), fetchone=True)

        precio_vigente = var_data["precio_vigente"]

        if item_existente:
            id_det = item_existente[0]
            cant_actual = item_existente[1]
            nueva_cant = cant_actual + cantidad

            if nueva_cant > stock_disp:
                raise ValueError(
                    f"No puedes agregar {cantidad} unidad(es) más. Ya tienes {cant_actual} en tu bolsa y el stock total es de {stock_disp} unidades."
                )

            nuevo_subtotal = round(nueva_cant * precio_vigente, 2)
            q_upd = f"""
                UPDATE {schema}.t_detalle_carrito 
                SET cantidad = %s, precio_unitario = %s, subtotal = %s 
                WHERE id_detalle_carrito = %s;
            """
            db.execute_query(q_upd, (nueva_cant, precio_vigente, nuevo_subtotal, id_det), commit=True)
        else:
            if cantidad > stock_disp:
                raise ValueError(
                    f"La cantidad solicitada ({cantidad}) supera el stock disponible ({stock_disp} unidades)."
                )

            subtotal = round(cantidad * precio_vigente, 2)
            q_ins = f"""
                INSERT INTO {schema}.t_detalle_carrito (id_carrito, id_variante, cantidad, precio_unitario, subtotal)
                VALUES (%s, %s, %s, %s, %s);
            """
            db.execute_query(q_ins, (id_carrito, id_variante, cantidad, precio_vigente, subtotal), commit=True)

        # Actualizar fecha del carrito
        db.execute_query(f"UPDATE {schema}.t_carrito SET fecha_actualizacion = NOW() WHERE id_carrito = %s;", (id_carrito,), commit=True)
    finally:
        db.close_connection(commit=True)

    return consultar_carrito_completo(id_usuario, id_empresa)

def actualizar_cantidad_item(id_usuario: int, id_empresa: int, id_detalle_carrito: int, nueva_cantidad: int) -> Dict[str, Any]:
    """
    Modifica la cantidad de un ítem existente en el carrito activo del usuario.
    Valida stock y no permite cantidades <= 0.
    """
    if nueva_cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0. Para quitar la prenda, usa el botón de eliminar.")

    id_cliente = obtener_o_crear_cliente(id_usuario)
    id_carrito = obtener_id_carrito_activo(id_cliente, id_empresa)

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Validar pertenencia del detalle al carrito del cliente
        q_item = f"""
            SELECT d.id_detalle_carrito, d.id_variante, COALESCE(v.precio, p.precio) AS precio_vigente
            FROM {schema}.t_detalle_carrito d
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = d.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            WHERE d.id_detalle_carrito = %s AND d.id_carrito = %s AND p.id_empresa = %s
            LIMIT 1;
        """
        row = db.execute_query(q_item, (id_detalle_carrito, id_carrito, id_empresa), fetchone=True)
        if not row:
            raise ValueError("El producto no fue encontrado en tu carrito activo.")

        id_var = row[1]
        precio_vigente = float(row[2]) if row[2] is not None else 0.0

        # Validar stock vigente
        stock_disp = obtener_stock_total_variante(id_var, id_empresa)
        if nueva_cantidad > stock_disp:
            raise ValueError(f"No hay suficiente stock disponible. Stock máximo actual: {stock_disp} unidades.")

        nuevo_subtotal = round(nueva_cantidad * precio_vigente, 2)
        q_upd = f"""
            UPDATE {schema}.t_detalle_carrito 
            SET cantidad = %s, precio_unitario = %s, subtotal = %s 
            WHERE id_detalle_carrito = %s;
        """
        db.execute_query(q_upd, (nueva_cantidad, precio_vigente, nuevo_subtotal, id_detalle_carrito), commit=True)
        db.execute_query(f"UPDATE {schema}.t_carrito SET fecha_actualizacion = NOW() WHERE id_carrito = %s;", (id_carrito,), commit=True)
    finally:
        db.close_connection(commit=True)

    return consultar_carrito_completo(id_usuario, id_empresa)

def eliminar_item_del_carrito(id_usuario: int, id_empresa: int, id_detalle_carrito: int) -> Dict[str, Any]:
    """
    Elimina una prenda del carrito activo del usuario.
    """
    id_cliente = obtener_o_crear_cliente(id_usuario)
    id_carrito = obtener_id_carrito_activo(id_cliente, id_empresa)

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q_del = f"DELETE FROM {schema}.t_detalle_carrito WHERE id_detalle_carrito = %s AND id_carrito = %s;"
        db.execute_query(q_del, (id_detalle_carrito, id_carrito), commit=True)
        db.execute_query(f"UPDATE {schema}.t_carrito SET fecha_actualizacion = NOW() WHERE id_carrito = %s;", (id_carrito,), commit=True)
    finally:
        db.close_connection(commit=True)

    return consultar_carrito_completo(id_usuario, id_empresa)

def vaciar_carrito_cliente(id_usuario: int, id_empresa: int) -> Dict[str, Any]:
    """
    Vacía todos los productos del carrito activo del usuario para la empresa indicada.
    """
    id_cliente = obtener_o_crear_cliente(id_usuario)
    id_carrito = obtener_id_carrito_activo(id_cliente, id_empresa)

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q_del = f"DELETE FROM {schema}.t_detalle_carrito WHERE id_carrito = %s;"
        db.execute_query(q_del, (id_carrito,), commit=True)
        db.execute_query(f"UPDATE {schema}.t_carrito SET fecha_actualizacion = NOW() WHERE id_carrito = %s;", (id_carrito,), commit=True)
    finally:
        db.close_connection(commit=True)

    return consultar_carrito_completo(id_usuario, id_empresa)

def obtener_resumen_rapido_carrito(id_usuario: int, id_empresa: int) -> Dict[str, Any]:
    """
    Retorna un resumen ligero del carrito para el indicador del Navbar.
    """
    id_cliente = obtener_o_crear_cliente(id_usuario)
    id_carrito = obtener_id_carrito_activo(id_cliente, id_empresa)

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT 
                COALESCE(SUM(d.cantidad), 0) AS total_items,
                COALESCE(SUM(d.subtotal), 0) AS subtotal
            FROM {schema}.t_detalle_carrito d
            WHERE d.id_carrito = %s;
        """
        res = db.execute_query(q, (id_carrito,), fetchone=True)
        return {
            "total_items": int(res[0]) if res else 0,
            "subtotal": float(res[1]) if res else 0.0
        }
    finally:
        db.close_connection()
