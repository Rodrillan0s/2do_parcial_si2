from typing import Optional, List, Dict, Any
from app.core.postgres import PostgreSQL
from app.core.config import Config

# --- JERARQUÍA DE ROLES (NIVEL NUMÉRICO: 1 ES MÁXIMA AUTORIDAD) ---
NIVELES_JERARQUIA = {
    'SUPERADMIN': 1,
    'ADMINISTRADOR': 2,
    'ADMINISTRADOR_TIENDA': 3,
    'ENCARGADO': 4,
    'ENCARGADO_SUCURSAL': 4,
    'EMPLEADO': 5,
    'CAJERO': 5,
    'CLIENTE': 6,
    'PROVEEDOR': 7
}

def obtener_nivel_autoridad(nombre_rol: str, id_empresa: Optional[int] = None) -> int:
    rol_clean = (nombre_rol or '').strip().upper()
    if rol_clean in ('ADMINISTRADOR', 'SUPERADMIN') and id_empresa is None:
        return 1  # SUPERADMIN
    if rol_clean == 'ADMINISTRADOR':
        return 2  # ADMINISTRADOR
    return NIVELES_JERARQUIA.get(rol_clean, 6)

# --- OBTENER PERMISOS EFECTIVOS DEL USUARIO (HEREDADOS + DIRECTOS) ---
def obtener_permisos_efectivos_usuario(id_usuario: int) -> List[str]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        # 1. Comprobar si el usuario es SuperAdmin (id_rol 1 o rol ADMINISTRADOR sin empresa)
        check_admin = f"""SELECT 1 FROM {schema}.t_usuario u
            JOIN {schema}.t_usuario_rol ur ON ur.id_usuario=u.id_usuario JOIN {schema}.t_rol r ON r.id_rol=ur.id_rol
            WHERE u.id_usuario=%s AND u.estado AND u.id_empresa IS NULL AND r.activo
              AND r.nombre IN ('ADMINISTRADOR','SUPERADMIN') LIMIT 1"""
        if db.execute_query(check_admin, (id_usuario,), fetchone=True):
            rows = db.execute_query(f"SELECT codigo FROM {schema}.t_permiso WHERE activo ORDER BY codigo", fetchall=True)
            return [r[0] for r in rows]

        # 2. Unión de Permisos Heredados de Roles Activos + Permisos Directos
        query = f"""
            SELECT DISTINCT p.codigo
            FROM (
                -- Permisos heredados de roles
                SELECT rp.id_permiso
                FROM {schema}.t_usuario_rol ur
                INNER JOIN {schema}.t_rol r ON r.id_rol = ur.id_rol
                INNER JOIN {schema}.t_rol_permiso rp ON rp.id_rol = ur.id_rol
                WHERE ur.id_usuario = %s AND r.activo = TRUE
                UNION
                -- Permisos directos asignados al usuario
                SELECT up.id_permiso
                FROM {schema}.t_usuario_permiso up
                WHERE up.id_usuario = %s AND up.activo = TRUE
            ) sub
            INNER JOIN {schema}.t_permiso p ON p.id_permiso = sub.id_permiso
            WHERE p.activo = TRUE
            ORDER BY p.codigo ASC;
        """
        res = db.execute_query(query, (id_usuario, id_usuario), fetchall=True)
        if not res:
            return []
        return [r[0] for r in res]
    finally:
        db.close_connection()

# --- OBTENER PERMISOS DIRECTOS ASIGNADOS AL USUARIO ---
def obtener_permisos_directos_usuario(id_usuario: int) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT p.id_permiso, p.codigo, p.nombre, p.descripcion, p.modulo, up.activo, up.created_at
            FROM {schema}.t_usuario_permiso up
            INNER JOIN {schema}.t_permiso p ON p.id_permiso = up.id_permiso
            WHERE up.id_usuario = %s
            ORDER BY p.modulo ASC, p.codigo ASC;
        """
        res = db.execute_query(query, (id_usuario,), fetchall=True)
        if not res:
            return []
        return [{
            "id_permiso": r[0],
            "codigo": r[1],
            "nombre": r[2],
            "descripcion": r[3],
            "modulo": r[4],
            "activo": r[5],
            "created_at": r[6].isoformat() if r[6] else None
        } for r in res]
    finally:
        db.close_connection()

# --- OBTENER PERMISOS HEREDADOS DE ROLES DEL USUARIO ---
def obtener_permisos_heredados_usuario(id_usuario: int) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT DISTINCT p.id_permiso, p.codigo, p.nombre, p.descripcion, p.modulo
            FROM {schema}.t_usuario_rol ur
            INNER JOIN {schema}.t_rol r ON r.id_rol = ur.id_rol
            INNER JOIN {schema}.t_rol_permiso rp ON rp.id_rol = ur.id_rol
            INNER JOIN {schema}.t_permiso p ON p.id_permiso = rp.id_permiso
            WHERE ur.id_usuario = %s AND r.activo = TRUE AND p.activo = TRUE
            ORDER BY p.modulo ASC, p.codigo ASC;
        """
        res = db.execute_query(query, (id_usuario,), fetchall=True)
        if not res:
            return []
        return [{
            "id_permiso": r[0],
            "codigo": r[1],
            "nombre": r[2],
            "descripcion": r[3],
            "modulo": r[4]
        } for r in res]
    finally:
        db.close_connection()

# --- ASIGNAR PERMISOS DIRECTOS A USUARIO ---
def asignar_permisos_directos_a_usuario(id_usuario: int, ids_permisos: List[int]) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        # 1. Eliminar asignaciones directas actuales
        query_delete = f"DELETE FROM {schema}.t_usuario_permiso WHERE id_usuario = %s;"
        db.execute_query(query_delete, (id_usuario,))

        # 2. Insertar nuevas asignaciones directas
        if ids_permisos:
            for id_permiso in ids_permisos:
                query_insert = f"""
                    INSERT INTO {schema}.t_usuario_permiso (id_usuario, id_permiso, activo)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (id_usuario, id_permiso) DO UPDATE SET activo = TRUE;
                """
                db.execute_query(query_insert, (id_usuario, id_permiso))

        if db.conn:
            db.commit()
        return True
    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise ValueError(f"Error al asignar permisos directos al usuario: {str(e)}")
    finally:
        db.close_connection()

# --- OBTENER ROLES ASIGNADOS AL USUARIO ---
def obtener_roles_usuario(id_usuario: int) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT r.id_rol, r.nombre, r.descripcion, r.activo
            FROM {schema}.t_usuario_rol ur
            INNER JOIN {schema}.t_rol r ON r.id_rol = ur.id_rol
            WHERE ur.id_usuario = %s AND r.activo = TRUE
            ORDER BY r.nombre ASC;
        """
        res = db.execute_query(query, (id_usuario,), fetchall=True)
        if not res:
            return []
        return [{"id_rol": r[0], "nombre": r[1], "descripcion": r[2], "activo": r[3]} for r in res]
    finally:
        db.close_connection()

# --- OBTENER SUCURSALES AUTORIZADAS DEL USUARIO ---
def obtener_sucursales_usuario(id_usuario: int) -> List[int]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT us.id_sucursal
            FROM {schema}.t_usuario_sucursal us
            INNER JOIN {schema}.t_sucursal s ON s.id_sucursal = us.id_sucursal
            WHERE us.id_usuario = %s AND s.activo = TRUE;
        """
        res = db.execute_query(query, (id_usuario,), fetchall=True)
        if not res:
            return []
        return [r[0] for r in res]
    finally:
        db.close_connection()

# --- CRUD ROLES ---
def obtener_todos_los_roles(solo_activos: bool = False) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        where_clause = "WHERE activo = TRUE" if solo_activos else ""
        query = f"""
            SELECT id_rol, nombre, descripcion, activo, created_at
            FROM {schema}.t_rol
            {where_clause}
            ORDER BY id_rol ASC;
        """
        resultados = db.execute_query(query, fetchall=True)
        roles = []
        if resultados:
            for r in resultados:
                roles.append({
                    "id_rol": r[0],
                    "nombre": r[1],
                    "descripcion": r[2],
                    "activo": r[3],
                    "created_at": r[4].strftime("%Y-%m-%d %H:%M:%S") if r[4] else None
                })
        return roles
    finally:
        db.close_connection()

def crear_rol(nombre: str, descripcion: str) -> Optional[int]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_rol (nombre, descripcion, activo)
            VALUES (%s, %s, TRUE)
            RETURNING id_rol;
        """
        res = db.execute_query(query, (nombre, descripcion), fetchone=True, commit=True)
        return res[0] if res else None
    finally:
        db.close_connection()

def actualizar_rol(id_rol: int, nombre: str, descripcion: str, activo: bool = True) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.t_rol
            SET nombre = %s, descripcion = %s, activo = %s
            WHERE id_rol = %s;
        """
        filas = db.execute_query(query, (nombre, descripcion, activo, id_rol), commit=True)
        return filas > 0
    finally:
        db.close_connection()

def desactivar_rol(id_rol: int) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"UPDATE {schema}.t_rol SET activo = FALSE WHERE id_rol = %s;"
        filas = db.execute_query(query, (id_rol,), commit=True)
        return filas > 0
    finally:
        db.close_connection()

# --- CRUD PERMISOS ---
def obtener_todos_los_permisos() -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT id_permiso, codigo, nombre, descripcion, modulo, activo
            FROM {schema}.t_permiso
            WHERE activo = TRUE
            ORDER BY modulo ASC, codigo ASC;
        """
        resultados = db.execute_query(query, fetchall=True)
        permisos = []
        if resultados:
            for r in resultados:
                permisos.append({
                    "id_permiso": r[0],
                    "codigo": r[1],
                    "nombre": r[2],
                    "descripcion": r[3],
                    "modulo": r[4],
                    "activo": r[5]
                })
        return permisos
    finally:
        db.close_connection()

def crear_permiso(codigo: str, nombre: str, descripcion: str, modulo: str) -> Optional[int]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_permiso (codigo, nombre, descripcion, modulo, activo)
            VALUES (%s, %s, %s, %s, TRUE)
            RETURNING id_permiso;
        """
        res = db.execute_query(query, (codigo, nombre, descripcion, modulo), fetchone=True, commit=True)
        return res[0] if res else None
    finally:
        db.close_connection()

# --- ASIGNACIÓN DE PERMISOS A ROL ---
def obtener_permisos_de_rol(id_rol: int) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT p.id_permiso, p.codigo, p.nombre, p.modulo
            FROM {schema}.t_rol_permiso rp
            INNER JOIN {schema}.t_permiso p ON p.id_permiso = rp.id_permiso
            WHERE rp.id_rol = %s AND p.activo = TRUE
            ORDER BY p.codigo ASC;
        """
        res = db.execute_query(query, (id_rol,), fetchall=True)
        if not res:
            return []
        return [{"id_permiso": r[0], "codigo": r[1], "nombre": r[2], "modulo": r[3]} for r in res]
    finally:
        db.close_connection()

def asignar_permisos_a_rol(id_rol: int, ids_permisos: List[int]) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query_delete = f"DELETE FROM {schema}.t_rol_permiso WHERE id_rol = %s;"
        db.execute_query(query_delete, (id_rol,))

        if ids_permisos:
            for id_permiso in ids_permisos:
                query_insert = f"""
                    INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
                    SELECT %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.t_rol_permiso WHERE id_rol = %s AND id_permiso = %s
                    );
                """
                db.execute_query(query_insert, (id_rol, id_permiso, id_rol, id_permiso))

        if db.conn:
            db.commit()
        return True
    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise ValueError(f"Error al asignar permisos al rol: {str(e)}")
    finally:
        db.close_connection()

# --- ASIGNACIÓN DE ROLES A USUARIO ---
def asignar_roles_a_usuario(id_usuario: int, ids_roles: List[int]) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        db.execute_query(f"UPDATE {schema}.t_usuario SET id_rol=%s WHERE id_usuario=%s;", (ids_roles[0] if ids_roles else None, id_usuario))
        query_delete = f"DELETE FROM {schema}.t_usuario_rol WHERE id_usuario = %s;"
        db.execute_query(query_delete, (id_usuario,))

        if ids_roles:
            for id_rol in ids_roles:
                query_insert = f"""
                    INSERT INTO {schema}.t_usuario_rol (id_usuario, id_rol)
                    SELECT %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.t_usuario_rol WHERE id_usuario = %s AND id_rol = %s
                    );
                """
                db.execute_query(query_insert, (id_usuario, id_rol, id_usuario, id_rol))

        if db.conn:
            db.commit()
        return True
    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise ValueError(f"Error al asignar roles al usuario: {str(e)}")
    finally:
        db.close_connection()

# --- ASIGNACIÓN DE SUCURSALES A USUARIO ---
def asignar_sucursales_a_usuario(id_usuario: int, ids_sucursales: List[int]) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query_delete = f"DELETE FROM {schema}.t_usuario_sucursal WHERE id_usuario = %s;"
        db.execute_query(query_delete, (id_usuario,))

        if ids_sucursales:
            for id_sucursal in ids_sucursales:
                query_insert = f"""
                    INSERT INTO {schema}.t_usuario_sucursal (id_usuario, id_sucursal)
                    SELECT %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.t_usuario_sucursal WHERE id_usuario = %s AND id_sucursal = %s
                    );
                """
                db.execute_query(query_insert, (id_usuario, id_sucursal, id_usuario, id_sucursal))

        if db.conn:
            db.commit()
        return True
    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise ValueError(f"Error al asignar sucursales al usuario: {str(e)}")
    finally:
        db.close_connection()

# --- CONSULTA DE SUCURSALES ---
def obtener_todas_las_sucursales() -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"SELECT id_sucursal, nombre, direccion, activo FROM {schema}.t_sucursal WHERE activo = TRUE ORDER BY id_sucursal ASC;"
        res = db.execute_query(query, fetchall=True)
        if not res:
            return []
        return [{"id_sucursal": r[0], "nombre": r[1], "direccion": r[2], "activo": r[3]} for r in res]
    finally:
        db.close_connection()
