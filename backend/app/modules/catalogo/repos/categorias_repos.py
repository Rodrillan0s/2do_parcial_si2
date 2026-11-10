from typing import Optional, List, Dict, Any
import copy
import threading
import time
from app.core.postgres import PostgreSQL
from app.core.config import Config

_CAT_CACHE_LOCK = threading.Lock()
_CATEGORIAS_CACHE: Dict[tuple, tuple] = {}
_CAT_CACHE_TTL_SECONDS = 30.0


def invalidar_cache_categorias() -> None:
    with _CAT_CACHE_LOCK:
        _CATEGORIAS_CACHE.clear()


def obtener_categorias(
    id_empresa: Optional[int] = None, 
    solo_activas: bool = False, 
    busqueda: Optional[str] = None
) -> List[Dict[str, Any]]:
    schema = Config.SCHEMA or 'comercio'
    busq_norm = busqueda.strip().lower() if busqueda and busqueda.strip() else ""
    cache_key = (schema, id_empresa, bool(solo_activas), busq_norm)
    now = time.monotonic()
    if not busq_norm:
        with _CAT_CACHE_LOCK:
            cached = _CATEGORIAS_CACHE.get(cache_key)
            if cached is not None and (now - cached[0]) < _CAT_CACHE_TTL_SECONDS:
                return copy.deepcopy(cached[1])

    db = PostgreSQL()
    db.create_connection()
    try:
        condiciones = []
        params = []

        if id_empresa is not None:
            condiciones.append("c.id_empresa = %s")
            params.append(id_empresa)

        if solo_activas:
            condiciones.append("(c.activo = TRUE AND c.estado = TRUE)")

        if busq_norm:
            condiciones.append("(LOWER(c.nombre) LIKE %s OR LOWER(c.descripcion) LIKE %s)")
            termino = f"%{busq_norm}%"
            params.extend([termino, termino])

        where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""

        query = f"""
            SELECT 
                c.id_categoria, 
                c.nombre, 
                c.descripcion, 
                c.id_padre,
                cp.nombre AS nombre_padre,
                c.id_empresa,
                e.nombre_empresa,
                c.imagen_url,
                c.imagen_public_id,
                COALESCE(c.activo, c.estado, TRUE) AS activo,
                COALESCE(c.estado, c.activo, TRUE) AS estado,
                c.created_at,
                c.updated_at,
                COALESCE(prod_cnt.total_productos, 0) AS total_productos,
                COALESCE(sub_cnt.total_subcategorias, 0) AS total_subcategorias
            FROM {schema}.t_categoria c
            LEFT JOIN {schema}.t_categoria cp ON c.id_padre = cp.id_categoria
            LEFT JOIN {schema}.empresa e ON c.id_empresa = e.id_empresa
            LEFT JOIN (
                SELECT id_categoria, COUNT(*)::int AS total_productos
                FROM {schema}.t_producto
                GROUP BY id_categoria
            ) prod_cnt ON prod_cnt.id_categoria = c.id_categoria
            LEFT JOIN (
                SELECT id_padre, COUNT(*)::int AS total_subcategorias
                FROM {schema}.t_categoria
                WHERE id_padre IS NOT NULL
                GROUP BY id_padre
            ) sub_cnt ON sub_cnt.id_padre = c.id_categoria
            {where_clause}
            ORDER BY COALESCE(c.id_padre, c.id_categoria) ASC, c.id_padre NULLS FIRST, c.nombre ASC;
        """
        resultados = db.execute_query(query, tuple(params) if params else None, fetchall=True)

        categorias = []
        if resultados:
            for r in resultados:
                is_activo = bool(r[9])
                categorias.append({
                    "id_categoria": r[0],
                    "nombre": r[1],
                    "descripcion": r[2] or "",
                    "id_padre": r[3],
                    "nombre_padre": r[4] or None,
                    "id_empresa": r[5],
                    "empresa_nombre": r[6] or "Sin Empresa",
                    "imagen_url": r[7] or "",
                    "imagen_public_id": r[8] or "",
                    "activo": is_activo,
                    "estado": "ACTIVO" if is_activo else "INACTIVO",
                    "created_at": r[11].isoformat() if r[11] else None,
                    "updated_at": r[12].isoformat() if r[12] else None,
                    "total_productos": int(r[13]) if r[13] is not None else 0,
                    "total_subcategorias": int(r[14]) if r[14] is not None else 0,
                    "es_raiz": r[3] is None
                })
        if not busq_norm:
            with _CAT_CACHE_LOCK:
                _CATEGORIAS_CACHE[cache_key] = (now, copy.deepcopy(categorias))
        return categorias
    finally:
        db.close_connection()

def obtener_categoria_por_id(id_categoria: int) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                c.id_categoria, 
                c.nombre, 
                c.descripcion, 
                c.id_padre,
                cp.nombre AS nombre_padre,
                c.id_empresa,
                e.nombre_empresa,
                c.imagen_url,
                c.imagen_public_id,
                COALESCE(c.activo, c.estado, TRUE) AS activo,
                COALESCE(c.estado, c.activo, TRUE) AS estado,
                c.created_at,
                c.updated_at,
                (SELECT COUNT(*) FROM {schema}.t_producto p WHERE p.id_categoria = c.id_categoria) AS total_productos,
                (SELECT COUNT(*) FROM {schema}.t_categoria sub WHERE sub.id_padre = c.id_categoria) AS total_subcategorias
            FROM {schema}.t_categoria c
            LEFT JOIN {schema}.t_categoria cp ON c.id_padre = cp.id_categoria
            LEFT JOIN {schema}.empresa e ON c.id_empresa = e.id_empresa
            WHERE c.id_categoria = %s;
        """
        r = db.execute_query(query, (id_categoria,), fetchone=True)
        if r:
            is_activo = bool(r[9])
            return {
                "id_categoria": r[0],
                "nombre": r[1],
                "descripcion": r[2] or "",
                "id_padre": r[3],
                "nombre_padre": r[4] or None,
                "id_empresa": r[5],
                "empresa_nombre": r[6] or "Sin Empresa",
                "imagen_url": r[7] or "",
                "imagen_public_id": r[8] or "",
                "activo": is_activo,
                "estado": "ACTIVO" if is_activo else "INACTIVO",
                "created_at": r[11].isoformat() if r[11] else None,
                "updated_at": r[12].isoformat() if r[12] else None,
                "total_productos": int(r[13]) if r[13] is not None else 0,
                "total_subcategorias": int(r[14]) if r[14] is not None else 0,
                "es_raiz": r[3] is None
            }
        return None
    finally:
        db.close_connection()

def verificar_nombre_duplicado(nombre: str, id_empresa: Optional[int], id_categoria_excluir: Optional[int] = None) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        condiciones = ["LOWER(TRIM(nombre)) = %s", "COALESCE(id_empresa, 0) = COALESCE(%s, 0)"]
        params = [nombre.strip().lower(), id_empresa]

        if id_categoria_excluir:
            condiciones.append("id_categoria != %s")
            params.append(id_categoria_excluir)

        query = f"SELECT 1 FROM {schema}.t_categoria WHERE {' AND '.join(condiciones)} LIMIT 1;"
        res = db.execute_query(query, tuple(params), fetchone=True)
        return bool(res)
    finally:
        db.close_connection()

def crear_categoria_db(
    nombre: str,
    descripcion: str,
    id_padre: Optional[int],
    id_empresa: Optional[int],
    imagen_url: Optional[str] = None,
    imagen_public_id: Optional[str] = None,
    activo: bool = True
) -> Optional[int]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_categoria (
                nombre, descripcion, id_padre, id_empresa, imagen_url, imagen_public_id, activo, estado
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_categoria;
        """
        resultado = db.execute_query(
            query,
            (
                nombre.strip(),
                descripcion.strip() if descripcion else "",
                id_padre,
                id_empresa,
                imagen_url.strip() if imagen_url else None,
                imagen_public_id.strip() if imagen_public_id else None,
                activo,
                activo
            ),
            fetchone=True,
            commit=True
        )
        return resultado[0] if resultado else None
    finally:
        db.close_connection()

def actualizar_categoria_db(
    id_categoria: int,
    nombre: str,
    descripcion: str,
    id_padre: Optional[int],
    id_empresa: Optional[int],
    imagen_url: Optional[str] = None,
    imagen_public_id: Optional[str] = None,
    activo: bool = True
) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_categoria
            SET nombre = %s,
                descripcion = %s,
                id_padre = %s,
                id_empresa = %s,
                imagen_url = COALESCE(%s, imagen_url),
                imagen_public_id = COALESCE(%s, imagen_public_id),
                activo = %s,
                estado = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_categoria = %s;
        """
        filas = db.execute_query(
            query,
            (
                nombre.strip(),
                descripcion.strip() if descripcion else "",
                id_padre,
                id_empresa,
                imagen_url.strip() if imagen_url else None,
                imagen_public_id.strip() if imagen_public_id else None,
                activo,
                activo,
                id_categoria
            ),
            commit=True
        )
        return filas > 0
    finally:
        db.close_connection()

def cambiar_estado_categoria_db(id_categoria: int, activo: bool) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_categoria
            SET activo = %s, estado = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id_categoria = %s;
        """
        filas = db.execute_query(query, (activo, activo, id_categoria), commit=True)
        return filas > 0
    finally:
        db.close_connection()

def contar_productos_por_categoria(id_categoria: int) -> int:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"SELECT COUNT(*) FROM {schema}.t_producto WHERE id_categoria = %s;"
        res = db.execute_query(query, (id_categoria,), fetchone=True)
        return int(res[0]) if res else 0
    finally:
        db.close_connection()

def contar_subcategorias(id_categoria: int) -> int:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"SELECT COUNT(*) FROM {schema}.t_categoria WHERE id_padre = %s;"
        res = db.execute_query(query, (id_categoria,), fetchone=True)
        return int(res[0]) if res else 0
    finally:
        db.close_connection()

def eliminar_categoria_fisico_db(id_categoria: int) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        # Desvincular subcategorías si las hubiere
        db.execute_query(f"UPDATE {schema}.t_categoria SET id_padre = NULL WHERE id_padre = %s;", (id_categoria,), commit=True)
        # Eliminar
        query = f"DELETE FROM {schema}.t_categoria WHERE id_categoria = %s;"
        filas = db.execute_query(query, (id_categoria,), commit=True)
        return filas > 0
    finally:
        db.close_connection()

def es_ancestro_o_ciclo(id_categoria: int, nuevo_id_padre: int) -> bool:
    """Verifica si nuevo_id_padre es descendiente de id_categoria (para evitar ciclos)."""
    if id_categoria == nuevo_id_padre:
        return True

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        # Consulta recursiva para encontrar todos los descendientes de id_categoria
        query = f"""
            WITH RECURSIVE jerarquia AS (
                SELECT id_categoria FROM {schema}.t_categoria WHERE id_padre = %s
                UNION ALL
                SELECT c.id_categoria FROM {schema}.t_categoria c
                INNER JOIN jerarquia j ON c.id_padre = j.id_categoria
            )
            SELECT 1 FROM jerarquia WHERE id_categoria = %s LIMIT 1;
        """
        res = db.execute_query(query, (id_categoria, nuevo_id_padre), fetchone=True)
        return bool(res)
    finally:
        db.close_connection()
