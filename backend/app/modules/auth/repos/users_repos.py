from typing import Optional, List, Dict, Any
from app.core.postgres import PostgreSQL
from app.core.config import Config

# --- LEER USUARIOS ---
def obtener_todos_los_usuarios() -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                u.id_usuario, u.username, u.correo, u.nombre, u.apellido,
                u.telefono, u.estado, u.id_empresa, e.nombre_empresa,
                r.nombre AS nombre_rol, r.id_rol,
                COUNT(DISTINCT up.id_permiso) AS permisos_directos_count,
                u.direccion, u.ciudad, u.fecha_registro,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT us.id_sucursal), NULL) AS ids_sucursales,
                STRING_AGG(DISTINCT s.nombre, ', ') AS nombres_sucursales
            FROM {schema}.t_usuario u
            LEFT JOIN {schema}.empresa e ON e.id_empresa = u.id_empresa
            LEFT JOIN {schema}.t_usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN {schema}.t_rol r ON r.id_rol = ur.id_rol
            LEFT JOIN {schema}.t_usuario_permiso up ON up.id_usuario = u.id_usuario AND up.activo = TRUE
            LEFT JOIN {schema}.t_usuario_sucursal us ON us.id_usuario = u.id_usuario
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = us.id_sucursal
            GROUP BY u.id_usuario, u.username, u.correo, u.nombre, u.apellido, u.telefono, u.estado, u.id_empresa, e.nombre_empresa, r.nombre, r.id_rol, u.direccion, u.ciudad, u.fecha_registro
            ORDER BY u.id_usuario ASC;
        """
        resultados = db.execute_query(query, fetchall=True)
        
        usuarios = []
        if resultados:
            for r in resultados:
                suc_ids = r[15] if r[15] else []
                usuarios.append({
                    "nro_usuario": r[0],
                    "id_usuario": r[0],
                    "nombre_usuario": r[1],
                    "username": r[1],
                    "correo": r[2],
                    "nombre": r[3],
                    "apellido": r[4],
                    "nombre_completo": f"{r[3] or ''} {r[4] or ''}".strip(),
                    "telefono": r[5] or "Sin teléfono",
                    "estado": "ACTIVO" if r[6] else "INACTIVO",
                    "id_empresa": r[7],
                    "nombre_empresa": r[8] or ("Plataforma Global" if r[7] is None else f"Tenant #{r[7]}"),
                    "nombre_rol": r[9] or "CLIENTE",
                    "id_rol": r[10] or 2,
                    "nro_rol": r[10] or 2,
                    "permisos_directos_count": r[11] or 0,
                    "direccion": r[12] or "Sin dirección registrada",
                    "ciudad": r[13] or "No especificada",
                    "fecha_registro": r[14].strftime('%Y-%m-%d %H:%M') if r[14] else "Reciente",
                    "ids_sucursales": suc_ids,
                    "id_sucursal": suc_ids[0] if suc_ids else None,
                    "sucursal_nombre": r[16] or "",
                    "sucursales_nombres": r[16] or ""
                })
        return usuarios
    finally:
        db.close_connection()

def obtener_usuarios_por_empresa(id_empresa: int) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                u.id_usuario, u.username, u.correo, u.nombre, u.apellido,
                u.telefono, u.estado, u.id_empresa, e.nombre_empresa,
                r.nombre AS nombre_rol, r.id_rol,
                COUNT(DISTINCT up.id_permiso) AS permisos_directos_count,
                u.direccion, u.ciudad, u.fecha_registro,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT us.id_sucursal), NULL) AS ids_sucursales,
                STRING_AGG(DISTINCT s.nombre, ', ') AS nombres_sucursales
            FROM {schema}.t_usuario u
            LEFT JOIN {schema}.empresa e ON e.id_empresa = u.id_empresa
            LEFT JOIN {schema}.t_usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN {schema}.t_rol r ON r.id_rol = ur.id_rol
            LEFT JOIN {schema}.t_usuario_permiso up ON up.id_usuario = u.id_usuario AND up.activo = TRUE
            LEFT JOIN {schema}.t_usuario_sucursal us ON us.id_usuario = u.id_usuario
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = us.id_sucursal
            WHERE u.id_empresa = %s
            GROUP BY u.id_usuario, u.username, u.correo, u.nombre, u.apellido, u.telefono, u.estado, u.id_empresa, e.nombre_empresa, r.nombre, r.id_rol, u.direccion, u.ciudad, u.fecha_registro
            ORDER BY u.id_usuario ASC;
        """
        resultados = db.execute_query(query, (id_empresa,), fetchall=True)
        
        usuarios = []
        if resultados:
            for r in resultados:
                suc_ids = r[15] if r[15] else []
                usuarios.append({
                    "nro_usuario": r[0],
                    "id_usuario": r[0],
                    "nombre_usuario": r[1],
                    "username": r[1],
                    "correo": r[2],
                    "nombre": r[3],
                    "apellido": r[4],
                    "nombre_completo": f"{r[3] or ''} {r[4] or ''}".strip(),
                    "telefono": r[5] or "Sin teléfono",
                    "estado": "ACTIVO" if r[6] else "INACTIVO",
                    "id_empresa": r[7],
                    "nombre_empresa": r[8] or f"Tenant #{r[7]}",
                    "nombre_rol": r[9] or "CLIENTE",
                    "id_rol": r[10] or 2,
                    "nro_rol": r[10] or 2,
                    "permisos_directos_count": r[11] or 0,
                    "direccion": r[12] or "Sin dirección registrada",
                    "ciudad": r[13] or "No especificada",
                    "fecha_registro": r[14].strftime('%Y-%m-%d %H:%M') if r[14] else "Reciente",
                    "ids_sucursales": suc_ids,
                    "id_sucursal": suc_ids[0] if suc_ids else None,
                    "sucursal_nombre": r[16] or "",
                    "sucursales_nombres": r[16] or ""
                })
        return usuarios
    finally:
        db.close_connection()

def obtener_usuario_por_id(id_usuario: int) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                u.id_usuario, u.username, u.correo, u.nombre, u.apellido,
                u.telefono, u.estado, u.id_empresa, e.nombre_empresa,
                r.nombre AS nombre_rol, r.id_rol,
                COUNT(DISTINCT up.id_permiso) AS permisos_directos_count,
                u.direccion, u.ciudad, u.fecha_registro,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT us.id_sucursal), NULL) AS ids_sucursales,
                STRING_AGG(DISTINCT s.nombre, ', ') AS nombres_sucursales
            FROM {schema}.t_usuario u
            LEFT JOIN {schema}.empresa e ON e.id_empresa = u.id_empresa
            LEFT JOIN {schema}.t_usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN {schema}.t_rol r ON r.id_rol = ur.id_rol
            LEFT JOIN {schema}.t_usuario_permiso up ON up.id_usuario = u.id_usuario AND up.activo = TRUE
            LEFT JOIN {schema}.t_usuario_sucursal us ON us.id_usuario = u.id_usuario
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = us.id_sucursal
            WHERE u.id_usuario = %s
            GROUP BY u.id_usuario, u.username, u.correo, u.nombre, u.apellido, u.telefono, u.estado, u.id_empresa, e.nombre_empresa, r.nombre, r.id_rol, u.direccion, u.ciudad, u.fecha_registro;
        """
        r = db.execute_query(query, (id_usuario,), fetchone=True)
        
        if r:
            suc_ids = r[15] if r[15] else []
            return {
                "nro_usuario": r[0],
                "id_usuario": r[0],
                "nombre_usuario": r[1],
                "username": r[1],
                "correo": r[2],
                "nombre": r[3],
                "apellido": r[4],
                "nombre_completo": f"{r[3] or ''} {r[4] or ''}".strip(),
                "telefono": r[5] or "Sin teléfono",
                "estado": "ACTIVO" if r[6] else "INACTIVO",
                "id_empresa": r[7],
                "nombre_empresa": r[8] or ("Plataforma Global" if r[7] is None else f"Tenant #{r[7]}"),
                "nombre_rol": r[9] or "CLIENTE",
                "id_rol": r[10] or 2,
                "nro_rol": r[10] or 2,
                "permisos_directos_count": r[11] or 0,
                "direccion": r[12] or "Sin dirección registrada",
                "ciudad": r[13] or "No especificada",
                "fecha_registro": r[14].strftime('%Y-%m-%d %H:%M') if r[14] else "Reciente",
                "ids_sucursales": suc_ids,
                "id_sucursal": suc_ids[0] if suc_ids else None,
                "sucursal_nombre": r[16] or "",
                "sucursales_nombres": r[16] or ""
            }
        return None
    finally:
        db.close_connection()

# --- CREAR USUARIO ---
def crear_usuario_db(ci: Optional[str], datos_usuario: dict) -> int:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        id_empresa = datos_usuario.get('id_empresa')
        if id_empresa in (0, '0', '', None):
            id_empresa = None

        query = f"""
            INSERT INTO {schema}.t_usuario (username, correo, password_hash, nombre, apellido, telefono, id_empresa, estado, id_rol)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
            RETURNING id_usuario;
        """
        params = (
            datos_usuario.get('username'),
            datos_usuario.get('correo'),
            datos_usuario.get('password_hash'),
            datos_usuario.get('nombre'),
            datos_usuario.get('apellido'),
            datos_usuario.get('telefono'),
            id_empresa, datos_usuario.get('id_rol')
        )
        res = db.execute_query(query, params, fetchone=True, commit=True)
        nuevo_id = res[0] if res else None
        
        # Asignar rol inicial
        if nuevo_id and datos_usuario.get('id_rol'):
            query_rol = f"""
                INSERT INTO {schema}.t_usuario_rol (id_usuario, id_rol)
                VALUES (%s, %s)
                ON CONFLICT (id_usuario, id_rol) DO NOTHING;
            """
            db.execute_query(query_rol, (nuevo_id, int(datos_usuario['id_rol'])), commit=True)
            
        return nuevo_id
    finally:
        db.close_connection()

# --- ACTUALIZAR USUARIO ---
def actualizar_usuario_db(id_usuario: int, ci: Optional[str], rol: Optional[int], datos_usuario: dict, cambiar_password: bool = False):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        id_empresa = datos_usuario.get('id_empresa')
        if id_empresa in (0, '0', '', None):
            id_empresa = None

        set_clauses = [
            "username = %s", "correo = %s", "nombre = %s", "apellido = %s",
            "telefono = %s", "id_empresa = %s", "id_rol = %s"
        ]
        params = [
            datos_usuario.get('username'),
            datos_usuario.get('correo'),
            datos_usuario.get('nombre'),
            datos_usuario.get('apellido'),
            datos_usuario.get('telefono'),
            id_empresa, datos_usuario.get('id_rol')
        ]

        if cambiar_password and datos_usuario.get('password_hash'):
            set_clauses.append("password_hash = %s")
            params.append(datos_usuario.get('password_hash'))

        if 'estado' in datos_usuario:
            estado_bool = datos_usuario['estado'] if isinstance(datos_usuario['estado'], bool) else (datos_usuario['estado'] == 'ACTIVO')
            set_clauses.append("estado = %s")
            params.append(estado_bool)

        params.append(id_usuario)

        query = f"""
            UPDATE {schema}.t_usuario
            SET {', '.join(set_clauses)}
            WHERE id_usuario = %s;
        """
        db.execute_query(query, tuple(params), commit=True)

        # Actualizar rol si se proveyó
        if datos_usuario.get('id_rol'):
            id_rol_nuevo = int(datos_usuario['id_rol'])
            db.execute_query(f"DELETE FROM {schema}.t_usuario_rol WHERE id_usuario = %s;", (id_usuario,))
            db.execute_query(
                f"INSERT INTO {schema}.t_usuario_rol (id_usuario, id_rol) VALUES (%s, %s);",
                (id_usuario, id_rol_nuevo),
                commit=True
            )
        return True
    finally:
        db.close_connection()

# --- ELIMINAR / DESACTIVAR USUARIO ---
def eliminar_usuario_db(id_usuario: int):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"UPDATE {schema}.t_usuario SET estado = FALSE WHERE id_usuario = %s;"
        db.execute_query(query, (id_usuario,), commit=True)
        return True
    finally:
        db.close_connection()

def cambiar_estado_usuario_db(id_usuario: int, estado: bool) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"UPDATE {schema}.t_usuario SET estado = %s WHERE id_usuario = %s;"
        filas = db.execute_query(query, (estado, id_usuario), commit=True)
        return filas > 0
    finally:
        db.close_connection()