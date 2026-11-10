from app.core.postgres import PostgreSQL
from app.core.config import Config
from datetime import datetime

# Comprueba si el correo o nombre de usuario ya está registrado en el sistema.
def existe_usuario(correo: str, username: str) -> bool:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 1 FROM {schema}.t_usuario 
            WHERE LOWER(correo) = LOWER(%s) OR LOWER(username) = LOWER(%s);
        """
        res = db.execute_query(query, (correo, username), fetchone=True)
        return bool(res)
    finally:
        db.close_connection()

# Registra un nuevo usuario cliente junto a su estado de seguridad y dispositivo inicial.
def crear_cliente(datos_usuario: dict, fingerprint: str = None, nombre_dispositivo: str = None) -> int:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        
        # 1. Insertar usuario en t_usuario
        query_usuario = f"""
            INSERT INTO {schema}.t_usuario 
            (correo, username, password_hash, nombre, apellido, telefono, estado, id_rol)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
            RETURNING id_usuario;
        """
        params_usuario = (
            datos_usuario.get('correo'),
            datos_usuario.get('nombre_usuario') or datos_usuario.get('username'),
            datos_usuario.get('password_hash'),
            datos_usuario.get('nombre'),
            datos_usuario.get('apellido'),
            datos_usuario.get('telefono'),
            datos_usuario.get('id_rol', 2)
        )

        
        res = db.execute_query(query_usuario, params_usuario, fetchone=True)
        if not res:
            raise ValueError("No se pudo insertar el usuario.")
        
        id_usuario = res[0]
        
        # 2. Inicializar seguridad usuario
        query_seguridad = f"""
            INSERT INTO {schema}.t_seguridad_usuario (id_usuario, intentos_fallidos)
            VALUES (%s, 0)
            ON CONFLICT (id_usuario) DO NOTHING;
        """
        db.execute_query(query_seguridad, (id_usuario,))
        
        # 3. Registrar dispositivo si se proporcionó
        if fingerprint:
            query_dispositivo = f"""
                INSERT INTO {schema}.t_dispositivo_usuario 
                (id_usuario, device_fingerprint, nombre_dispositivo, verificado)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (id_usuario, device_fingerprint) DO UPDATE 
                SET ultima_conexion = CURRENT_TIMESTAMP;
            """
            db.execute_query(query_dispositivo, (id_usuario, fingerprint, nombre_dispositivo))
            
        if db.conn:
            db.conn.commit()
            
        return id_usuario
    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise ValueError(f"Error al crear cliente: {str(e)}")
    finally:
        db.close_connection()

# Obtiene las credenciales necesarias para autenticar al cliente y verificar el estado de su cuenta.
def obtener_credenciales_cliente(identificador: str) -> dict:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT u.id_usuario, u.correo, u.username, u.password_hash, u.estado, 
                   u.nombre, u.apellido, u.id_rol, r.nombre AS nombre_rol,
                   COALESCE(s.intentos_fallidos, 0) AS intentos_fallidos, s.bloqueado_hasta,
                   u.id_empresa, e.nombre_empresa
            FROM {schema}.t_usuario u
            LEFT JOIN {schema}.t_rol r ON u.id_rol = r.id_rol
            LEFT JOIN {schema}.t_seguridad_usuario s ON u.id_usuario = s.id_usuario
            LEFT JOIN {schema}.empresa e ON u.id_empresa = e.id_empresa
            WHERE LOWER(u.correo) = LOWER(%s) OR LOWER(u.username) = LOWER(%s);
        """
        r = db.execute_query(query, (identificador, identificador), fetchone=True)
        if not r:
            return None
            
        return {
            "id_usuario": r[0],
            "nro_usuario": r[0],
            "correo": r[1],
            "username": r[2],
            "nombre_usuario": r[2],
            "password_hash": r[3],
            "estado": r[4],
            "nombre": r[5],
            "apellido": r[6],
            "id_rol": r[7],
            "nombre_rol": r[8],
            "id_empresa": r[11],
            "nombre_empresa": r[12],
            "intentos_fallidos": r[9],
            "bloqueado_hasta": r[10]
        }

    finally:
        db.close_connection()

# Registra un intento fallido de autenticación y aplica el bloqueo si corresponde.
def registrar_intento_fallido(id_usuario: int, intentos: int, bloqueado_hasta: datetime = None):
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_seguridad_usuario (id_usuario, intentos_fallidos, bloqueado_hasta, fecha_actualizacion)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id_usuario) DO UPDATE 
            SET intentos_fallidos = %s, bloqueado_hasta = %s, fecha_actualizacion = CURRENT_TIMESTAMP;
        """
        db.execute_query(query, (id_usuario, intentos, bloqueado_hasta, intentos, bloqueado_hasta), commit=True)
    finally:
        db.close_connection()

# Restablece el contador de intentos fallidos tras una autenticación exitosa.
def reiniciar_intentos(id_usuario: int):
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_seguridad_usuario (id_usuario, intentos_fallidos, bloqueado_hasta, fecha_actualizacion)
            VALUES (%s, 0, NULL, CURRENT_TIMESTAMP)
            ON CONFLICT (id_usuario) DO UPDATE 
            SET intentos_fallidos = 0, bloqueado_hasta = NULL, fecha_actualizacion = CURRENT_TIMESTAMP;
        """
        db.execute_query(query, (id_usuario,), commit=True)
    finally:
        db.close_connection()

# Comprueba si un dispositivo ya ha sido verificado para el usuario.
def es_dispositivo_conocido(id_usuario: int, fingerprint: str) -> bool:
    if not fingerprint:
        return True
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT verificado FROM {schema}.t_dispositivo_usuario 
            WHERE id_usuario = %s AND device_fingerprint = %s;
        """
        res = db.execute_query(query, (id_usuario, fingerprint), fetchone=True)
        return bool(res and res[0] is True)
    finally:
        db.close_connection()

# Genera un código de verificación temporal para autorizar un nuevo dispositivo.
def guardar_codigo_dispositivo(id_usuario: int, codigo: str, expira_at: datetime):
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_seguridad_usuario 
            (id_usuario, codigo_verificacion_dispositivo, codigo_dispositivo_expira, fecha_actualizacion)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id_usuario) DO UPDATE 
            SET codigo_verificacion_dispositivo = %s, codigo_dispositivo_expira = %s, fecha_actualizacion = CURRENT_TIMESTAMP;
        """
        db.execute_query(query, (id_usuario, codigo, expira_at, codigo, expira_at), commit=True)
    finally:
        db.close_connection()

def validar_codigo_dispositivo(id_usuario: int, codigo: str) -> bool:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT codigo_verificacion_dispositivo, codigo_dispositivo_expira
            FROM {schema}.t_seguridad_usuario
            WHERE id_usuario = %s;
        """
        res = db.execute_query(query, (id_usuario,), fetchone=True)
        if not res or res[0] != codigo:
            raise ValueError("El código de verificación del dispositivo es inválido.")
        if res[1] and datetime.now() > res[1]:
            raise ValueError("El código de verificación del dispositivo ha expirado.")

        db.execute_query(
            f"""
            UPDATE {schema}.t_seguridad_usuario
            SET codigo_verificacion_dispositivo = NULL,
                codigo_dispositivo_expira = NULL,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_usuario = %s;
            """,
            (id_usuario,),
            commit=True
        )
        return True
    finally:
        db.close_connection()

# Registra un nuevo dispositivo como verificado para el usuario.
def guardar_dispositivo_verificado(id_usuario: int, fingerprint: str, nombre_dispositivo: str = None) -> bool:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_dispositivo_usuario 
            (id_usuario, device_fingerprint, nombre_dispositivo, verificado, ultima_conexion)
            VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (id_usuario, device_fingerprint) DO UPDATE 
            SET verificado = TRUE, ultima_conexion = CURRENT_TIMESTAMP;
        """
        db.execute_query(query, (id_usuario, fingerprint, nombre_dispositivo), commit=True)
        return True
    finally:
        db.close_connection()

# Almacena el código temporal de recuperación de contraseña para el usuario.
def guardar_codigo_recuperacion(correo: str, codigo: str, expira_at: datetime) -> bool:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        
        # 1. Asegurar que exista fila en t_seguridad_usuario
        query_ensure = f"""
            INSERT INTO {schema}.t_seguridad_usuario (id_usuario, intentos_fallidos)
            SELECT id_usuario, 0 FROM {schema}.t_usuario 
            WHERE LOWER(correo) = LOWER(%s) OR LOWER(username) = LOWER(%s)
            ON CONFLICT (id_usuario) DO NOTHING;
        """
        db.execute_query(query_ensure, (correo, correo), commit=True)

        # 2. Actualizar código de recuperación
        query = f"""
            UPDATE {schema}.t_seguridad_usuario s
            SET codigo_recuperacion = %s, codigo_recuperacion_expira = %s, fecha_actualizacion = CURRENT_TIMESTAMP
            FROM {schema}.t_usuario u
            WHERE s.id_usuario = u.id_usuario AND (LOWER(u.correo) = LOWER(%s) OR LOWER(u.username) = LOWER(%s));
        """
        rowcount = db.execute_query(query, (codigo, expira_at, correo, correo), commit=True)
        return bool(rowcount and rowcount > 0)
    finally:
        db.close_connection()


# Valida únicamente si el código ingresado existe y se encuentra dentro de su ventana de vigencia.
def validar_codigo_recuperacion(correo: str, codigo: str) -> bool:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        query_valida = f"""
            SELECT u.id_usuario, s.codigo_recuperacion_expira
            FROM {schema}.t_usuario u
            INNER JOIN {schema}.t_seguridad_usuario s ON u.id_usuario = s.id_usuario
            WHERE (LOWER(u.correo) = LOWER(%s) OR LOWER(u.username) = LOWER(%s)) AND s.codigo_recuperacion = %s;
        """
        res = db.execute_query(query_valida, (correo, correo, codigo), fetchone=True)
        if not res:
            raise ValueError("El código de recuperación ingresado es inválido.")
        
        expira_at = res[1]
        if expira_at and datetime.now() > expira_at:
            raise ValueError("El código de recuperación ha expirado. Por favor solicita uno nuevo.")
        return True
    finally:
        db.close_connection()


# Actualiza la contraseña y restablece el estado de seguridad de la cuenta.
def restablecer_contrasena(correo: str, codigo: str, nuevo_password_hash: str) -> bool:
    db = PostgreSQL()
    try:
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        
        # 1. Verificar si existe código activo
        query_valida = f"""
            SELECT u.id_usuario, s.codigo_recuperacion_expira
            FROM {schema}.t_usuario u
            INNER JOIN {schema}.t_seguridad_usuario s ON u.id_usuario = s.id_usuario
            WHERE (LOWER(u.correo) = LOWER(%s) OR LOWER(u.username) = LOWER(%s)) AND s.codigo_recuperacion = %s;
        """
        res = db.execute_query(query_valida, (correo, correo, codigo), fetchone=True)

        if not res:
            raise ValueError("El código de recuperación es inválido.")
            
        id_usuario, expira_at = res[0], res[1]
        if expira_at and datetime.now() > expira_at:
            raise ValueError("El código de recuperación ha expirado.")
            
        # 2. Actualizar clave y reiniciar seguridad
        query_update_user = f"""
            UPDATE {schema}.t_usuario 
            SET password_hash = %s, estado = TRUE
            WHERE id_usuario = %s;
        """
        db.execute_query(query_update_user, (nuevo_password_hash, id_usuario))
        
        query_update_seg = f"""
            UPDATE {schema}.t_seguridad_usuario
            SET intentos_fallidos = 0, bloqueado_hasta = NULL, 
                codigo_recuperacion = NULL, codigo_recuperacion_expira = NULL,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_usuario = %s;
        """
        db.execute_query(query_update_seg, (id_usuario,))
        
        if db.conn:
            db.conn.commit()
        return True
    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise ValueError(str(e))
    finally:
        db.close_connection()