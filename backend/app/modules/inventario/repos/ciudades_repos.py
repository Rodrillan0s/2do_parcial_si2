from typing import Optional, List, Dict, Any
from app.core.postgres import PostgreSQL
from app.core.config import Config

def obtener_todas_ciudades_db(solo_activas: bool = False, busqueda: Optional[str] = None) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        condiciones = []
        params = []

        if solo_activas:
            condiciones.append("estado = TRUE")

        if busqueda and busqueda.strip():
            condiciones.append("(LOWER(nombre) LIKE %s OR LOWER(departamento) LIKE %s)")
            q = f"%{busqueda.strip().lower()}%"
            params.extend([q, q])

        where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""
        query = f"""
            SELECT id_ciudad, nombre, departamento, estado, created_at
            FROM {schema}.t_ciudad
            {where_clause}
            ORDER BY departamento ASC, nombre ASC;
        """
        rows = db.execute_query(query, tuple(params) if params else None, fetchall=True)
        ciudades = []
        if rows:
            for r in rows:
                ciudades.append({
                    "id_ciudad": r[0],
                    "nombre": r[1],
                    "departamento": r[2],
                    "estado": r[3],
                    "created_at": r[4].isoformat() if r[4] else None
                })
        return ciudades
    finally:
        db.close_connection()

def obtener_ciudad_por_id_db(id_ciudad: int) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT id_ciudad, nombre, departamento, estado, created_at
            FROM {schema}.t_ciudad
            WHERE id_ciudad = %s;
        """
        r = db.execute_query(query, (id_ciudad,), fetchone=True)
        if r:
            return {
                "id_ciudad": r[0],
                "nombre": r[1],
                "departamento": r[2],
                "estado": r[3],
                "created_at": r[4].isoformat() if r[4] else None
            }
        return None
    finally:
        db.close_connection()

def existe_ciudad_db(nombre: str, departamento: str, exclude_id: Optional[int] = None) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        if exclude_id:
            query = f"""
                SELECT 1 FROM {schema}.t_ciudad
                WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) 
                  AND LOWER(TRIM(departamento)) = LOWER(TRIM(%s))
                  AND id_ciudad != %s;
            """
            r = db.execute_query(query, (nombre, departamento, exclude_id), fetchone=True)
        else:
            query = f"""
                SELECT 1 FROM {schema}.t_ciudad
                WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) 
                  AND LOWER(TRIM(departamento)) = LOWER(TRIM(%s));
            """
            r = db.execute_query(query, (nombre, departamento), fetchone=True)
        return bool(r)
    finally:
        db.close_connection()

def crear_ciudad_db(nombre: str, departamento: str, estado: bool = True) -> int:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_ciudad (nombre, departamento, estado)
            VALUES (%s, %s, %s)
            RETURNING id_ciudad;
        """
        r = db.execute_query(query, (nombre.strip(), departamento.strip(), estado), fetchone=True, commit=True)
        return r[0] if r else 0
    finally:
        db.close_connection()

def actualizar_ciudad_db(id_ciudad: int, nombre: str, departamento: str, estado: bool) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_ciudad
            SET nombre = %s, departamento = %s, estado = %s
            WHERE id_ciudad = %s;
        """
        filas = db.execute_query(query, (nombre.strip(), departamento.strip(), estado, id_ciudad), commit=True)
        return filas > 0
    finally:
        db.close_connection()

def cambiar_estado_ciudad_db(id_ciudad: int, estado: bool) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_ciudad
            SET estado = %s
            WHERE id_ciudad = %s;
        """
        filas = db.execute_query(query, (estado, id_ciudad), commit=True)
        return filas > 0
    finally:
        db.close_connection()

def obtener_o_crear_ciudad_db(nombre: str, departamento: str) -> int:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query_check = f"""
            SELECT id_ciudad FROM {schema}.t_ciudad
            WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
              AND LOWER(TRIM(departamento)) = LOWER(TRIM(%s))
            LIMIT 1;
        """
        r = db.execute_query(query_check, (nombre, departamento), fetchone=True)
        if r:
            return r[0]

        query_ins = f"""
            INSERT INTO {schema}.t_ciudad (nombre, departamento, estado)
            VALUES (%s, %s, TRUE)
            RETURNING id_ciudad;
        """
        ins = db.execute_query(query_ins, (nombre.strip(), departamento.strip()), fetchone=True, commit=True)
        return ins[0] if ins else 0
    finally:
        db.close_connection()
