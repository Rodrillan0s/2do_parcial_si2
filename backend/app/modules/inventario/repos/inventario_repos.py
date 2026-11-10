import logging
from typing import Optional, Dict, Any, List
from app.core.postgres import PostgreSQL, atomic
from app.core.inventory_integrity import lock_position
from fastapi import HTTPException
from app.core.config import Config

logger = logging.getLogger(__name__)

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def validar_pertenencia_tenant(id_sucursal: int, id_variante: int, id_empresa: Optional[int]) -> Dict[str, Any]:
    """
    Valida estrictamente en la base de datos que la sucursal y la variante pertenezcan
    al tenant/empresa autenticado.
    Si id_empresa es None (SUPERADMIN / alcance PLATAFORMA), se valida que ambas existan.
    """
    schema = _get_schema()
    db = PostgreSQL()
    try:
        db.create_connection()
        if not db.conn:
            return {"valido": False, "error": "ERROR_CONEXION_BD", "mensaje": "No se pudo conectar a la base de datos."}

        # 1. Validar sucursal y su empresa
        query_sucursal = f"""
            SELECT id_sucursal, id_empresa, nombre, activo
            FROM {schema}.t_sucursal
            WHERE id_sucursal = %s;
        """
        sucursal = db.execute_query(query_sucursal, (id_sucursal,), fetchone=True)
        if not sucursal:
            return {"valido": False, "error": "SUCURSAL_NO_ENCONTRADA", "mensaje": f"La sucursal {id_sucursal} no existe."}

        suc_empresa = sucursal[1]

        # 2. Validar variante y la empresa del producto padre
        query_variante = f"""
            SELECT ptc.id_variante, p.id_producto, p.id_empresa, p.nombre, ptc.sku
            FROM {schema}.t_producto_talla_color ptc
            JOIN {schema}.t_producto p ON ptc.id_producto = p.id_producto
            WHERE ptc.id_variante = %s;
        """
        variante = db.execute_query(query_variante, (id_variante,), fetchone=True)
        if not variante:
            return {"valido": False, "error": "VARIANTE_NO_ENCONTRADA", "mensaje": f"La variante {id_variante} no existe."}

        prod_empresa = variante[2]

        # 3. Validación de tenant multi-tenant
        if id_empresa is not None and id_empresa != 0:
            if suc_empresa != id_empresa:
                return {
                    "valido": False,
                    "error": "SUCURSAL_AJENA_TENANT",
                    "mensaje": f"La sucursal {id_sucursal} no pertenece a la empresa del usuario ({id_empresa})."
                }
            if prod_empresa != id_empresa:
                return {
                    "valido": False,
                    "error": "VARIANTE_AJENA_TENANT",
                    "mensaje": f"El producto de la variante {id_variante} no pertenece a la empresa del usuario ({id_empresa})."
                }
        else:
            # Si el usuario es plataforma pero la sucursal y el producto tienen empresas distintas
            if suc_empresa is not None and prod_empresa is not None and suc_empresa != prod_empresa:
                return {
                    "valido": False,
                    "error": "TENANT_MISMATCH",
                    "mensaje": "La sucursal y el producto pertenecen a empresas distintas."
                }

        return {
            "valido": True,
            "sucursal": {"id_sucursal": sucursal[0], "nombre": sucursal[2], "id_empresa": suc_empresa},
            "variante": {"id_variante": variante[0], "id_producto": variante[1], "id_empresa": prod_empresa, "producto_nombre": variante[3], "sku": variante[4]}
        }
    except Exception as e:
        logger.error(f"Error validando pertenencia tenant: {e}")
        return {"valido": False, "error": "ERROR_INTERNO", "mensaje": str(e)}
    finally:
        db.close_connection()

@atomic
def registrar_movimiento_inventario(
    id_sucursal: int,
    id_variante: int,
    tipo_movimiento: str,
    cantidad: int,
    id_usuario: int,
    motivo: str,
    id_empresa: Optional[int]
) -> Dict[str, Any]:
    """
    Ejecuta el movimiento de inventario invocando la función PostgreSQL atómica fn_movimiento_inventario.
    Aplica FOR UPDATE sobre t_inventario dentro de la transacción.
    """
    # 1. Validación estricta multi-tenant previa
    check_tenant = validar_pertenencia_tenant(id_sucursal, id_variante, id_empresa)
    if not check_tenant["valido"]:
        return {
            "success": False,
            "error": check_tenant.get("error", "ACCESO_DENEGADO"),
            "message": check_tenant.get("mensaje", "Acceso denegado por validación de tenant.")
        }

    schema = _get_schema()
    db = PostgreSQL()
    try:
        db.create_connection()
        if not db.conn:
            return {"success": False, "error": "ERROR_CONEXION_BD", "message": "No se pudo conectar a la base de datos."}

        lock_position(db, schema, id_sucursal, id_variante, id_empresa, allow_missing=True)
        # 2. Invocación de la función PostgreSQL transaccional
        query_fn = f"""
            SELECT {schema}.fn_movimiento_inventario(
                %s, %s, %s, %s, %s, %s
            );
        """
        res = db.execute_query(
            query_fn,
            (id_sucursal, id_variante, tipo_movimiento, cantidad, id_usuario, motivo),
            fetchone=True,
            commit=True
        )

        if not res or not res[0]:
            return {"success": False, "error": "RESPUESTA_VACIA", "message": "La función no devolvió resultado."}

        resultado_json = res[0]
        if not resultado_json.get('success'):
            raise HTTPException(400, resultado_json.get('message') or 'Movimiento rechazado; no se modificó el inventario.')
        lock_position(db, schema, id_sucursal, id_variante, id_empresa)
        return resultado_json
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Excepción en registrar_movimiento_inventario: {e}")
        return {"success": False, "error": "EXCEPCION_BD", "message": str(e)}
    finally:
        db.close_connection()

def listar_inventario(id_empresa: Optional[int], filtros: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consulta el inventario con soporte de filtros por sucursal, producto, talla, color,
    estado, estado de stock (bajo_stock, sin_stock) y búsqueda de texto.
    Garantiza aislamiento multi-tenant.
    """
    schema = _get_schema()
    db = PostgreSQL()
    try:
        db.create_connection()
        if not db.conn:
            return {"success": False, "items": [], "total": 0, "message": "Sin conexión a BD"}

        where_clauses = []
        params: List[Any] = []

        # 1. Aislamiento Multi-Tenant
        if id_empresa is not None and id_empresa != 0:
            where_clauses.append("s.id_empresa = %s")
            params.append(id_empresa)
            where_clauses.append("p.id_empresa = %s")
            params.append(id_empresa)

        # 2. Filtro por Sucursal
        id_sucursal = filtros.get("id_sucursal")
        if id_sucursal:
            try:
                where_clauses.append("inv.id_sucursal = %s")
                params.append(int(id_sucursal))
            except (ValueError, TypeError):
                pass

        # 3. Filtro por Producto
        id_producto = filtros.get("id_producto")
        if id_producto:
            try:
                where_clauses.append("p.id_producto = %s")
                params.append(int(id_producto))
            except (ValueError, TypeError):
                pass

        # 3.1 Filtro por Variante
        id_variante = filtros.get("id_variante")
        if id_variante:
            try:
                where_clauses.append("inv.id_variante = %s")
                params.append(int(id_variante))
            except (ValueError, TypeError):
                pass

        # 4. Filtro por Talla
        id_talla = filtros.get("id_talla")
        if id_talla:
            try:
                where_clauses.append("ptc.id_talla = %s")
                params.append(int(id_talla))
            except (ValueError, TypeError):
                pass

        # 5. Filtro por Color
        id_color = filtros.get("id_color")
        if id_color:
            try:
                where_clauses.append("ptc.id_color = %s")
                params.append(int(id_color))
            except (ValueError, TypeError):
                pass

        # 6. Filtro por Estado (True/False)
        estado = filtros.get("estado")
        if estado is not None and estado != "":
            if str(estado).lower() in ("true", "1", "activo"):
                where_clauses.append("inv.estado = TRUE")
            elif str(estado).lower() in ("false", "0", "inactivo"):
                where_clauses.append("inv.estado = FALSE")

        # 7. Filtro rápido de Alerta de Stock
        filtro_stock = filtros.get("filtro_stock")
        if filtro_stock == "bajo_stock":
            where_clauses.append("inv.stock_disponible > 0 AND inv.stock_disponible <= inv.stock_minimo")
        elif filtro_stock == "sin_stock":
            where_clauses.append("inv.stock_disponible <= 0")
        elif filtro_stock == "disponible":
            where_clauses.append("inv.stock_disponible > inv.stock_minimo")

        # 8. Búsqueda por texto (Nombre producto, SKU, Código barras, Código producto)
        busqueda = filtros.get("busqueda")
        if busqueda and busqueda.strip():
            patron = f"%{busqueda.strip()}%"
            where_clauses.append("""(
                p.nombre ILIKE %s OR 
                p.codigo_producto ILIKE %s OR 
                ptc.sku ILIKE %s OR 
                ptc.codigo_barras ILIKE %s OR
                s.nombre ILIKE %s
            )""")
            params.extend([patron, patron, patron, patron, patron])

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        # Totales agregados y conteo total unificados en una sola consulta SQL
        query_totales = f"""
            SELECT 
                COUNT(inv.id_inventario) AS total_posiciones,
                COALESCE(SUM(inv.stock_actual), 0) AS total_actual,
                COALESCE(SUM(inv.stock_reservado), 0) AS total_reservado,
                COALESCE(SUM(inv.stock_disponible), 0) AS total_disponible,
                COUNT(CASE WHEN inv.stock_disponible > 0 AND inv.stock_disponible <= inv.stock_minimo THEN 1 END) AS total_bajo_stock,
                COUNT(CASE WHEN inv.stock_disponible <= 0 THEN 1 END) AS total_sin_stock
            FROM {schema}.t_inventario inv
            JOIN {schema}.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            JOIN {schema}.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN {schema}.t_producto p ON ptc.id_producto = p.id_producto
            {where_sql};
        """
        totales_res = db.execute_query(query_totales, tuple(params), fetchone=True)
        total_items = int(totales_res[0]) if totales_res and totales_res[0] is not None else 0
        resumen = {
            "total_posiciones": total_items,
            "total_actual": int(totales_res[1]) if totales_res else 0,
            "total_reservado": int(totales_res[2]) if totales_res else 0,
            "total_disponible": int(totales_res[3]) if totales_res else 0,
            "total_bajo_stock": int(totales_res[4]) if totales_res else 0,
            "total_sin_stock": int(totales_res[5]) if totales_res else 0
        }

        # Paginación
        pagina = int(filtros.get("pagina", 1))
        limite = int(filtros.get("limite", 20))
        offset = (pagina - 1) * limite

        rows = []
        if total_items > 0:
            # Consulta principal de la página actual
            query_items = f"""
                SELECT 
                    inv.id_inventario,
                    inv.id_sucursal,
                    s.nombre AS sucursal_nombre,
                    s.codigo_sucursal,
                    s.id_empresa,
                    inv.id_variante,
                    p.id_producto,
                    p.nombre AS producto_nombre,
                    p.codigo_producto,
                    p.imagen_url,
                    p.marca,
                    ptc.sku,
                    ptc.codigo_barras,
                    ptc.precio,
                    t.id_talla,
                    COALESCE(t.nombre, 'Única') AS talla_nombre,
                    c.id_color,
                    COALESCE(c.nombre, 'Estándar') AS color_nombre,
                    COALESCE(c.codigo_hex, '#4F46E5') AS color_hex,
                    COALESCE(inv.stock_actual, 0) AS stock_actual,
                    COALESCE(inv.stock_reservado, 0) AS stock_reservado,
                    COALESCE(inv.stock_disponible, 0) AS stock_disponible,
                    COALESCE(inv.stock_minimo, 0) AS stock_minimo,
                    COALESCE(inv.estado, TRUE) AS estado,
                    inv.fecha_actualizacion
                FROM {schema}.t_inventario inv
                JOIN {schema}.t_sucursal s ON inv.id_sucursal = s.id_sucursal
                JOIN {schema}.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
                JOIN {schema}.t_producto p ON ptc.id_producto = p.id_producto
                LEFT JOIN {schema}.t_talla t ON ptc.id_talla = t.id_talla
                LEFT JOIN {schema}.t_color c ON ptc.id_color = c.id_color
                {where_sql}
                ORDER BY p.nombre ASC, ptc.sku ASC, s.nombre ASC
                LIMIT %s OFFSET %s;
            """
            query_params = list(params) + [limite, offset]
            rows = db.execute_query(query_items, tuple(query_params), fetchall=True) or []

        items = []
        for r in rows:
            stock_actual = r[19]
            stock_reservado = r[20]
            stock_disponible = r[21]
            stock_minimo = r[22]

            # Determinación de estado semáforo
            if stock_disponible <= 0:
                semaforo = "SIN_STOCK"
            elif stock_disponible <= stock_minimo:
                semaforo = "BAJO_STOCK"
            else:
                semaforo = "NORMAL"

            items.append({
                "id_inventario": r[0],
                "id_sucursal": r[1],
                "sucursal_nombre": r[2],
                "codigo_sucursal": r[3],
                "id_empresa": r[4],
                "id_variante": r[5],
                "id_producto": r[6],
                "producto_nombre": r[7],
                "codigo_producto": r[8],
                "imagen_url": r[9],
                "marca": r[10],
                "sku": r[11],
                "codigo_barras": r[12],
                "precio": float(r[13]) if r[13] is not None else 0.0,
                "id_talla": r[14],
                "talla_nombre": r[15],
                "id_color": r[16],
                "color_nombre": r[17],
                "color_hex": r[18],
                "stock_actual": stock_actual,
                "stock_reservado": stock_reservado,
                "stock_disponible": stock_disponible,
                "stock_minimo": stock_minimo,
                "estado": bool(r[23]),
                "fecha_actualizacion": r[24].isoformat() if r[24] else None,
                "semaforo": semaforo
            })

        return {
            "success": True,
            "items": items,
            "total": total_items,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": (total_items + limite - 1) // limite if limite > 0 else 1,
            "resumen": resumen
        }
    except Exception as e:
        logger.error(f"Error listando inventario: {e}")
        return {"success": False, "items": [], "total": 0, "message": str(e)}
    finally:
        db.close_connection()

def obtener_inventario_por_id(id_inventario: int, id_empresa: Optional[int]) -> Optional[Dict[str, Any]]:
    """
    Obtiene el detalle completo de un registro de inventario validando tenant.
    """
    schema = _get_schema()
    db = PostgreSQL()
    try:
        db.create_connection()
        if not db.conn:
            return None

        where_tenant = ""
        params: List[Any] = [id_inventario]
        if id_empresa is not None and id_empresa != 0:
            where_tenant = "AND s.id_empresa = %s AND p.id_empresa = %s"
            params.extend([id_empresa, id_empresa])

        query = f"""
            SELECT 
                inv.id_inventario,
                inv.id_sucursal,
                s.nombre AS sucursal_nombre,
                s.id_empresa,
                inv.id_variante,
                p.id_producto,
                p.nombre AS producto_nombre,
                p.codigo_producto,
                p.imagen_url,
                ptc.sku,
                COALESCE(t.nombre, 'Única') AS talla_nombre,
                COALESCE(c.nombre, 'Estándar') AS color_nombre,
                COALESCE(c.codigo_hex, '#4F46E5') AS color_hex,
                COALESCE(inv.stock_actual, 0) AS stock_actual,
                COALESCE(inv.stock_reservado, 0) AS stock_reservado,
                COALESCE(inv.stock_disponible, 0) AS stock_disponible,
                COALESCE(inv.stock_minimo, 0) AS stock_minimo,
                COALESCE(inv.estado, TRUE) AS estado,
                inv.fecha_actualizacion
            FROM {schema}.t_inventario inv
            JOIN {schema}.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            JOIN {schema}.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN {schema}.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN {schema}.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN {schema}.t_color c ON ptc.id_color = c.id_color
            WHERE inv.id_inventario = %s {where_tenant};
        """
        r = db.execute_query(query, tuple(params), fetchone=True)
        if not r:
            return None

        return {
            "id_inventario": r[0],
            "id_sucursal": r[1],
            "sucursal_nombre": r[2],
            "id_empresa": r[3],
            "id_variante": r[4],
            "id_producto": r[5],
            "producto_nombre": r[6],
            "codigo_producto": r[7],
            "imagen_url": r[8],
            "sku": r[9],
            "talla_nombre": r[10],
            "color_nombre": r[11],
            "color_hex": r[12],
            "stock_actual": r[13],
            "stock_reservado": r[14],
            "stock_disponible": r[15],
            "stock_minimo": r[16],
            "estado": bool(r[17]),
            "fecha_actualizacion": r[18].isoformat() if r[18] else None
        }
    except Exception as e:
        logger.error(f"Error obteniendo inventario por id: {e}")
        return None
    finally:
        db.close_connection()

def listar_movimientos_inventario(id_empresa: Optional[int], filtros: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lista el historial de movimientos de inventario de t_movimiento_inventario,
    con datos de auditoría (usuario, fecha, tipo, cantidades, motivo) y filtros.
    """
    schema = _get_schema()
    db = PostgreSQL()
    try:
        db.create_connection()
        if not db.conn:
            return {"success": False, "items": [], "total": 0, "message": "Sin conexión a BD"}

        where_clauses = []
        params: List[Any] = []

        # 1. Filtro Multi-Tenant
        if id_empresa is not None and id_empresa != 0:
            where_clauses.append("s.id_empresa = %s")
            params.append(id_empresa)
            where_clauses.append("p.id_empresa = %s")
            params.append(id_empresa)

        # 2. Filtro por posición de inventario
        id_inventario = filtros.get("id_inventario")
        if id_inventario:
            try:
                where_clauses.append("m.id_inventario = %s")
                params.append(int(id_inventario))
            except (ValueError, TypeError):
                pass

        # 3. Filtro por Sucursal
        id_sucursal = filtros.get("id_sucursal")
        if id_sucursal:
            try:
                where_clauses.append("inv.id_sucursal = %s")
                params.append(int(id_sucursal))
            except (ValueError, TypeError):
                pass

        # 4. Filtro por Variante
        id_variante = filtros.get("id_variante")
        if id_variante:
            try:
                where_clauses.append("inv.id_variante = %s")
                params.append(int(id_variante))
            except (ValueError, TypeError):
                pass

        # 5. Filtro por Tipo de Movimiento
        tipo = filtros.get("tipo_movimiento")
        if tipo and tipo.strip():
            where_clauses.append("UPPER(m.tipo_movimiento) = UPPER(%s)")
            params.append(tipo.strip())

        # 6. Búsqueda de texto
        busqueda = filtros.get("busqueda")
        if busqueda and busqueda.strip():
            patron = f"%{busqueda.strip()}%"
            where_clauses.append("""(
                p.nombre ILIKE %s OR 
                ptc.sku ILIKE %s OR 
                m.motivo ILIKE %s OR
                u.nombre ILIKE %s OR
                u.apellido ILIKE %s
            )""")
            params.extend([patron, patron, patron, patron, patron])

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        # Conteo
        query_count = f"""
            SELECT COUNT(*)
            FROM {schema}.t_movimiento_inventario m
            JOIN {schema}.t_inventario inv ON m.id_inventario = inv.id_inventario
            JOIN {schema}.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            JOIN {schema}.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN {schema}.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN {schema}.t_usuario u ON m.id_usuario = u.id_usuario
            {where_sql};
        """
        count_res = db.execute_query(query_count, tuple(params), fetchone=True)
        total_items = count_res[0] if count_res else 0

        # Paginación
        pagina = int(filtros.get("pagina", 1))
        limite = int(filtros.get("limite", 20))
        offset = (pagina - 1) * limite

        query_items = f"""
            SELECT 
                m.id_movimiento,
                m.id_inventario,
                m.id_usuario,
                COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), u.username, 'Sistema') AS usuario_nombre,
                m.tipo_movimiento,
                m.cantidad,
                m.stock_anterior,
                m.stock_nuevo,
                m.motivo,
                m.fecha_movimiento,
                s.id_sucursal,
                s.nombre AS sucursal_nombre,
                inv.id_variante,
                p.nombre AS producto_nombre,
                ptc.sku,
                COALESCE(t.nombre, 'Única') AS talla_nombre,
                COALESCE(c.nombre, 'Estándar') AS color_nombre,
                p.imagen_url
            FROM {schema}.t_movimiento_inventario m
            JOIN {schema}.t_inventario inv ON m.id_inventario = inv.id_inventario
            JOIN {schema}.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            JOIN {schema}.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN {schema}.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN {schema}.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN {schema}.t_color c ON ptc.id_color = c.id_color
            LEFT JOIN {schema}.t_usuario u ON m.id_usuario = u.id_usuario
            {where_sql}
            ORDER BY m.fecha_movimiento DESC, m.id_movimiento DESC
            LIMIT %s OFFSET %s;
        """
        query_params = list(params) + [limite, offset]
        rows = db.execute_query(query_items, tuple(query_params), fetchall=True) or []

        items = []
        for r in rows:
            items.append({
                "id_movimiento": r[0],
                "id_inventario": r[1],
                "id_usuario": r[2],
                "usuario_nombre": r[3],
                "tipo_movimiento": r[4],
                "cantidad": r[5],
                "stock_anterior": r[6],
                "stock_nuevo": r[7],
                "motivo": r[8],
                "fecha_movimiento": r[9].isoformat() if r[9] else None,
                "id_sucursal": r[10],
                "sucursal_nombre": r[11],
                "id_variante": r[12],
                "producto_nombre": r[13],
                "sku": r[14],
                "talla_nombre": r[15],
                "color_nombre": r[16],
                "imagen_url": r[17]
            })

        return {
            "success": True,
            "items": items,
            "total": total_items,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": (total_items + limite - 1) // limite if limite > 0 else 1
        }
    except Exception as e:
        logger.error(f"Error listando movimientos de inventario: {e}")
        return {"success": False, "items": [], "total": 0, "message": str(e)}
    finally:
        db.close_connection()
