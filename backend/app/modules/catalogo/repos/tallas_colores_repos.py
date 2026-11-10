from typing import Optional, List, Dict, Any
import copy
import threading
import time
from app.core.postgres import PostgreSQL
from app.core.config import Config

_TC_CACHE_LOCK = threading.Lock()
_TALLAS_CACHE: Dict[tuple, tuple] = {}
_COLORES_CACHE: Dict[tuple, tuple] = {}
_TC_CACHE_TTL_SECONDS = 30.0


def invalidar_cache_tallas_colores() -> None:
    with _TC_CACHE_LOCK:
        _TALLAS_CACHE.clear()
        _COLORES_CACHE.clear()


# ==============================================================================
# REPOSITORIO DE TALLAS
# ==============================================================================

def obtener_tallas(
    id_empresa: Optional[int] = None, 
    solo_activas: bool = False, 
    busqueda: Optional[str] = None
) -> List[Dict[str, Any]]:
    schema = Config.SCHEMA or 'comercio'
    busq_norm = busqueda.strip().lower() if busqueda and busqueda.strip() else ""
    cache_key = (schema, id_empresa, bool(solo_activas), busq_norm)
    now = time.monotonic()
    if not busq_norm:
        with _TC_CACHE_LOCK:
            cached = _TALLAS_CACHE.get(cache_key)
            if cached is not None and (now - cached[0]) < _TC_CACHE_TTL_SECONDS:
                return copy.deepcopy(cached[1])

    db = PostgreSQL()
    db.create_connection()
    try:
        condiciones = []
        params = []

        if id_empresa is not None:
            condiciones.append("t.id_empresa = %s")
            params.append(id_empresa)

        if solo_activas:
            condiciones.append("(t.activo = TRUE AND t.estado = TRUE)")

        if busq_norm:
            condiciones.append("(LOWER(t.nombre) LIKE %s OR LOWER(t.descripcion) LIKE %s)")
            termino = f"%{busq_norm}%"
            params.extend([termino, termino])

        where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""

        query = f"""
            SELECT 
                t.id_talla,
                t.nombre,
                t.descripcion,
                t.id_empresa,
                e.nombre_empresa,
                COALESCE(t.activo, t.estado, TRUE) AS activo,
                COALESCE(t.estado, t.activo, TRUE) AS estado,
                t.created_at,
                t.updated_at,
                COALESCE(var_cnt.total_variantes, 0) AS total_variantes
            FROM {schema}.t_talla t
            LEFT JOIN {schema}.empresa e ON t.id_empresa = e.id_empresa
            LEFT JOIN (
                SELECT id_talla, COUNT(*)::int AS total_variantes
                FROM {schema}.t_producto_talla_color
                GROUP BY id_talla
            ) var_cnt ON var_cnt.id_talla = t.id_talla
            {where_clause}
            ORDER BY t.id_talla ASC;
        """
        resultados = db.execute_query(query, tuple(params) if params else None, fetchall=True)

        tallas = []
        if resultados:
            for r in resultados:
                is_activo = bool(r[5])
                tallas.append({
                    "id_talla": r[0],
                    "nombre": r[1],
                    "descripcion": r[2] or "",
                    "id_empresa": r[3],
                    "empresa_nombre": r[4] or "Sin Empresa",
                    "activo": is_activo,
                    "estado": "ACTIVO" if is_activo else "INACTIVO",
                    "created_at": r[7].isoformat() if r[7] else None,
                    "updated_at": r[8].isoformat() if r[8] else None,
                    "total_variantes": int(r[9]) if r[9] is not None else 0
                })
        if not busq_norm:
            with _TC_CACHE_LOCK:
                _TALLAS_CACHE[cache_key] = (now, copy.deepcopy(tallas))
        return tallas
    finally:
        db.close_connection()

def obtener_talla_por_id(id_talla: int) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                t.id_talla,
                t.nombre,
                t.descripcion,
                t.id_empresa,
                e.nombre_empresa,
                COALESCE(t.activo, t.estado, TRUE) AS activo,
                COALESCE(t.estado, t.activo, TRUE) AS estado,
                t.created_at,
                t.updated_at,
                (SELECT COUNT(*) FROM {schema}.t_producto_talla_color ptc WHERE ptc.id_talla = t.id_talla) AS total_variantes
            FROM {schema}.t_talla t
            LEFT JOIN {schema}.empresa e ON t.id_empresa = e.id_empresa
            WHERE t.id_talla = %s;
        """
        r = db.execute_query(query, (id_talla,), fetchone=True)
        if r:
            is_activo = bool(r[5])
            return {
                "id_talla": r[0],
                "nombre": r[1],
                "descripcion": r[2] or "",
                "id_empresa": r[3],
                "empresa_nombre": r[4] or "Sin Empresa",
                "activo": is_activo,
                "estado": "ACTIVO" if is_activo else "INACTIVO",
                "created_at": r[7].isoformat() if r[7] else None,
                "updated_at": r[8].isoformat() if r[8] else None,
                "total_variantes": int(r[9]) if r[9] is not None else 0
            }
        return None
    finally:
        db.close_connection()

def verificar_nombre_talla_duplicado(nombre: str, id_empresa: Optional[int], id_talla_excluir: Optional[int] = None) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        condiciones = ["LOWER(TRIM(nombre)) = %s", "COALESCE(id_empresa, 0) = COALESCE(%s, 0)"]
        params = [nombre.strip().lower(), id_empresa]

        if id_talla_excluir:
            condiciones.append("id_talla != %s")
            params.append(id_talla_excluir)

        query = f"SELECT 1 FROM {schema}.t_talla WHERE {' AND '.join(condiciones)} LIMIT 1;"
        res = db.execute_query(query, tuple(params), fetchone=True)
        return bool(res)
    finally:
        db.close_connection()

def crear_talla_db(nombre: str, descripcion: str, id_empresa: Optional[int], activo: bool = True) -> Optional[int]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_talla (nombre, descripcion, id_empresa, activo, estado)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_talla;
        """
        resultado = db.execute_query(
            query,
            (nombre.strip(), descripcion.strip() if descripcion else "", id_empresa, activo, activo),
            fetchone=True,
            commit=True
        )
        return resultado[0] if resultado else None
    finally:
        db.close_connection()

def actualizar_talla_db(id_talla: int, nombre: str, descripcion: str, id_empresa: Optional[int], activo: bool = True) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_talla
            SET nombre = %s,
                descripcion = %s,
                id_empresa = %s,
                activo = %s,
                estado = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_talla = %s;
        """
        filas = db.execute_query(
            query,
            (nombre.strip(), descripcion.strip() if descripcion else "", id_empresa, activo, activo, id_talla),
            commit=True
        )
        return filas > 0
    finally:
        db.close_connection()

def cambiar_estado_talla_db(id_talla: int, activo: bool) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_talla
            SET activo = %s, estado = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id_talla = %s;
        """
        filas = db.execute_query(query, (activo, activo, id_talla), commit=True)
        return filas > 0
    finally:
        db.close_connection()

def contar_variantes_por_talla(id_talla: int) -> int:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"SELECT COUNT(*) FROM {schema}.t_producto_talla_color WHERE id_talla = %s;"
        res = db.execute_query(query, (id_talla,), fetchone=True)
        return int(res[0]) if res else 0
    finally:
        db.close_connection()

def eliminar_talla_fisico_db(id_talla: int) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"DELETE FROM {schema}.t_talla WHERE id_talla = %s;"
        filas = db.execute_query(query, (id_talla,), commit=True)
        return filas > 0
    finally:
        db.close_connection()


# ==============================================================================
# REPOSITORIO DE COLORES
# ==============================================================================

def obtener_colores(
    id_empresa: Optional[int] = None, 
    solo_activos: bool = False, 
    busqueda: Optional[str] = None
) -> List[Dict[str, Any]]:
    schema = Config.SCHEMA or 'comercio'
    busq_norm = busqueda.strip().lower() if busqueda and busqueda.strip() else ""
    cache_key = (schema, id_empresa, bool(solo_activos), busq_norm)
    now = time.monotonic()
    if not busq_norm:
        with _TC_CACHE_LOCK:
            cached = _COLORES_CACHE.get(cache_key)
            if cached is not None and (now - cached[0]) < _TC_CACHE_TTL_SECONDS:
                return copy.deepcopy(cached[1])

    db = PostgreSQL()
    db.create_connection()
    try:
        condiciones = []
        params = []

        if id_empresa is not None:
            condiciones.append("c.id_empresa = %s")
            params.append(id_empresa)

        if solo_activos:
            condiciones.append("(c.activo = TRUE AND c.estado = TRUE)")

        if busq_norm:
            condiciones.append("(LOWER(c.nombre) LIKE %s OR LOWER(c.codigo_hex) LIKE %s)")
            termino = f"%{busq_norm}%"
            params.extend([termino, termino])

        where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""

        query = f"""
            SELECT 
                c.id_color,
                c.nombre,
                c.codigo_hex,
                c.id_empresa,
                e.nombre_empresa,
                COALESCE(c.activo, c.estado, TRUE) AS activo,
                COALESCE(c.estado, c.activo, TRUE) AS estado,
                c.created_at,
                c.updated_at,
                COALESCE(var_cnt.total_variantes, 0) AS total_variantes
            FROM {schema}.t_color c
            LEFT JOIN {schema}.empresa e ON c.id_empresa = e.id_empresa
            LEFT JOIN (
                SELECT id_color, COUNT(*)::int AS total_variantes
                FROM {schema}.t_producto_talla_color
                GROUP BY id_color
            ) var_cnt ON var_cnt.id_color = c.id_color
            {where_clause}
            ORDER BY c.id_color ASC;
        """
        resultados = db.execute_query(query, tuple(params) if params else None, fetchall=True)

        colores = []
        if resultados:
            for r in resultados:
                is_activo = bool(r[5])
                colores.append({
                    "id_color": r[0],
                    "nombre": r[1],
                    "codigo_hex": r[2] or "#000000",
                    "id_empresa": r[3],
                    "empresa_nombre": r[4] or "Sin Empresa",
                    "activo": is_activo,
                    "estado": "ACTIVO" if is_activo else "INACTIVO",
                    "created_at": r[7].isoformat() if r[7] else None,
                    "updated_at": r[8].isoformat() if r[8] else None,
                    "total_variantes": int(r[9]) if r[9] is not None else 0
                })
        if not busq_norm:
            with _TC_CACHE_LOCK:
                _COLORES_CACHE[cache_key] = (now, copy.deepcopy(colores))
        return colores
    finally:
        db.close_connection()

def obtener_color_por_id(id_color: int) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                c.id_color,
                c.nombre,
                c.codigo_hex,
                c.id_empresa,
                e.nombre_empresa,
                COALESCE(c.activo, c.estado, TRUE) AS activo,
                COALESCE(c.estado, c.activo, TRUE) AS estado,
                c.created_at,
                c.updated_at,
                (SELECT COUNT(*) FROM {schema}.t_producto_talla_color ptc WHERE ptc.id_color = c.id_color) AS total_variantes
            FROM {schema}.t_color c
            LEFT JOIN {schema}.empresa e ON c.id_empresa = e.id_empresa
            WHERE c.id_color = %s;
        """
        r = db.execute_query(query, (id_color,), fetchone=True)
        if r:
            is_activo = bool(r[5])
            return {
                "id_color": r[0],
                "nombre": r[1],
                "codigo_hex": r[2] or "#000000",
                "id_empresa": r[3],
                "empresa_nombre": r[4] or "Sin Empresa",
                "activo": is_activo,
                "estado": "ACTIVO" if is_activo else "INACTIVO",
                "created_at": r[7].isoformat() if r[7] else None,
                "updated_at": r[8].isoformat() if r[8] else None,
                "total_variantes": int(r[9]) if r[9] is not None else 0
            }
        return None
    finally:
        db.close_connection()

def verificar_nombre_color_duplicado(nombre: str, id_empresa: Optional[int], id_color_excluir: Optional[int] = None) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        condiciones = ["LOWER(TRIM(nombre)) = %s", "COALESCE(id_empresa, 0) = COALESCE(%s, 0)"]
        params = [nombre.strip().lower(), id_empresa]

        if id_color_excluir:
            condiciones.append("id_color != %s")
            params.append(id_color_excluir)

        query = f"SELECT 1 FROM {schema}.t_color WHERE {' AND '.join(condiciones)} LIMIT 1;"
        res = db.execute_query(query, tuple(params), fetchone=True)
        return bool(res)
    finally:
        db.close_connection()

def crear_color_db(nombre: str, codigo_hex: str, id_empresa: Optional[int], activo: bool = True) -> Optional[int]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_color (nombre, codigo_hex, id_empresa, activo, estado)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_color;
        """
        resultado = db.execute_query(
            query,
            (nombre.strip(), codigo_hex.strip().upper(), id_empresa, activo, activo),
            fetchone=True,
            commit=True
        )
        return resultado[0] if resultado else None
    finally:
        db.close_connection()

def actualizar_color_db(id_color: int, nombre: str, codigo_hex: str, id_empresa: Optional[int], activo: bool = True) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_color
            SET nombre = %s,
                codigo_hex = %s,
                id_empresa = %s,
                activo = %s,
                estado = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_color = %s;
        """
        filas = db.execute_query(
            query,
            (nombre.strip(), codigo_hex.strip().upper(), id_empresa, activo, activo, id_color),
            commit=True
        )
        return filas > 0
    finally:
        db.close_connection()

def cambiar_estado_color_db(id_color: int, activo: bool) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_color
            SET activo = %s, estado = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id_color = %s;
        """
        filas = db.execute_query(query, (activo, activo, id_color), commit=True)
        return filas > 0
    finally:
        db.close_connection()

def contar_variantes_por_color(id_color: int) -> int:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"SELECT COUNT(*) FROM {schema}.t_producto_talla_color WHERE id_color = %s;"
        res = db.execute_query(query, (id_color,), fetchone=True)
        return int(res[0]) if res else 0
    finally:
        db.close_connection()

def eliminar_color_fisico_db(id_color: int) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"DELETE FROM {schema}.t_color WHERE id_color = %s;"
        filas = db.execute_query(query, (id_color,), commit=True)
        return filas > 0
    finally:
        db.close_connection()
