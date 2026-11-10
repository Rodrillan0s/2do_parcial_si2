from app.core.config import Config
from app.core.postgres import PostgreSQL

def get_profile(id_usuario: int):
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'

        query = f"""
            SELECT 
                u.id_usuario,
                COALESCE(u.username, '') AS username,
                COALESCE(u.nombre, '') AS nombre,
                COALESCE(u.apellido, '') AS apellido,
                TRIM(CONCAT(COALESCE(u.nombre, ''), ' ', COALESCE(u.apellido, ''))) AS nombre_completo,
                COALESCE(u.correo, '') AS correo,
                COALESCE(u.telefono, '') AS telefono,
                COALESCE(c.ci, '') AS ci,
                COALESCE(c.direccion, u.direccion, '') AS direccion,
                COALESCE(c.ciudad, u.ciudad, 'Santa Cruz') AS ciudad,
                CASE WHEN u.estado IS TRUE THEN 'ACTIVO' ELSE 'INACTIVO' END AS estado,
                TO_CHAR(u.fecha_registro, 'YYYY-MM-DD"T"HH24:MI:SS') AS fecha_registro,
                COALESCE(u.id_rol, 2) AS id_rol,
                COALESCE(r.nombre, 'CLIENTE') AS nombre_rol,
                u.id_empresa,
                COALESCE(e.nombre_empresa, 'AURA Atelier') AS nombre_empresa
            FROM {schema}.t_usuario u
            LEFT JOIN {schema}.t_rol r ON u.id_rol = r.id_rol
            LEFT JOIN {schema}.empresa e ON u.id_empresa = e.id_empresa
            LEFT JOIN {schema}.t_cliente c ON u.id_usuario = c.id_usuario
            WHERE u.id_usuario = %s;
        """

        user = db.execute_query(query, (id_usuario,), fetchone=True)
        if not user:
            return None

        columns = [col[0] for col in db.cur.description]
        return dict(zip(columns, user))

    except Exception as e:
        raise ValueError(f"Error al obtener perfil: {str(e)}")
    finally:
        db.close_connection()

def update_profile(id_usuario: int, data: dict):
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'

        # 1. Extraer campos con fallback a datos existentes
        nombre = data.get('nombre')
        apellido = data.get('apellido')
        telefono = data.get('telefono')
        correo = data.get('correo')
        direccion = data.get('direccion')
        ciudad = data.get('ciudad')
        ci = data.get('ci')
        password_hash = data.get('password_hash')

        # 2. Actualizar t_usuario
        query_usuario = f"""
            UPDATE {schema}.t_usuario
            SET 
                nombre = COALESCE(%s, nombre),
                apellido = COALESCE(%s, apellido),
                telefono = COALESCE(%s, telefono),
                correo = COALESCE(%s, correo),
                direccion = COALESCE(%s, direccion),
                ciudad = COALESCE(%s, ciudad)
            WHERE id_usuario = %s;
        """
        db.execute_query(query_usuario, (nombre, apellido, telefono, correo, direccion, ciudad, id_usuario), commit=True)

        # 3. Actualizar contraseña si se proporcionó nuevo hash
        if password_hash:
            query_pass = f"""
                UPDATE {schema}.t_usuario
                SET password_hash = %s
                WHERE id_usuario = %s;
            """
            db.execute_query(query_pass, (password_hash, id_usuario), commit=True)

        # 4. Sincronizar t_cliente
        query_cliente_update = f"""
            UPDATE {schema}.t_cliente
            SET 
                ci = COALESCE(%s, ci),
                direccion = COALESCE(%s, direccion),
                ciudad = COALESCE(%s, ciudad)
            WHERE id_usuario = %s;
        """
        filas = db.execute_query(query_cliente_update, (ci, direccion, ciudad, id_usuario), commit=True)

        if filas == 0 and (ci or direccion or ciudad):
            query_cliente_insert = f"""
                INSERT INTO {schema}.t_cliente (id_usuario, ci, direccion, ciudad)
                VALUES (%s, %s, %s, %s);
            """
            db.execute_query(query_cliente_insert, (id_usuario, ci or '', direccion or '', ciudad or 'Santa Cruz'), commit=True)

        return {
            'success': True,
            'message': 'Perfil actualizado exitosamente.'
        }

    except Exception as e:
        raise ValueError(f"Error al actualizar perfil: {str(e)}")
    finally:
        db.close_connection()

def update_password(id_usuario: int, password_hash: str):
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"UPDATE {schema}.t_usuario SET password_hash = %s WHERE id_usuario = %s;"
        db.execute_query(query, (password_hash, id_usuario), commit=True)
        return True
    finally:
        db.close_connection()