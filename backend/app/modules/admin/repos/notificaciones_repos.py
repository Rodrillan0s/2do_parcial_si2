from app.core.postgres import PostgreSQL
from app.core.config import Config

#OBTENER USUARIOS POR ROL
def obtener_usuarios_por_roles(roles: list):
    db = PostgreSQL()
    db.create_connection()
    try:
        format_strings = ','.join(['%s'] * len(roles))
        query = f"""
            SELECT u.id_usuario, u.username, r.nombre
            FROM {Config.SCHEMA}.t_usuario u
            INNER JOIN {Config.SCHEMA}.t_rol r ON u.id_rol = r.id_rol
            WHERE UPPER(r.nombre) IN ({format_strings}) AND u.estado = TRUE;
        """
        roles_upper = [rol.upper() for rol in roles]
        resultados = db.execute_query(query, tuple(roles_upper), fetchall=True)
        
        usuarios = []
        if resultados:
            for r in resultados:
                usuarios.append({
                    "nro_usuario": r[0],
                    "nombre_usuario": r[1],
                    "nombre_rol": r[2]
                })
        return usuarios
    except Exception as e:
        print(f"Error en obtener_usuarios_por_roles: {e}")
        return []
    finally:
        db.close_connection()

#OBTENER USUARIOS DE UN TALLER/EMPRESA ESPECIFICO
def obtener_usuarios_por_taller(nro_taller: int):
    return []

#GUARDAR NOTIFICACIÓN EN LA BASE DE DATOS
def guardar_notificacion_db(titulo: str, cuerpo: str, tipo_referencia: str, nro_usuario: int, nro_emergencia: int):
    db = PostgreSQL()
    db.create_connection()
    try:
        query = f"""
            INSERT INTO {Config.SCHEMA}.t_notificacion 
            (titulo, cuerpo, tipo_referencia, nro_usuario, nro_emergencia) 
            VALUES (%s, %s, %s, %s, %s);
        """
        db.execute_query(query, (titulo, cuerpo, tipo_referencia, nro_usuario, nro_emergencia), commit=True)
    finally:
        db.close_connection()


def obtener_notificaciones_por_usuario_db(nro_usuario: int):
    """
    Recupera el historial de alertas del usuario ordenado por las más recientes primero.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        query = f"""
            SELECT id_notificacion, titulo, cuerpo, tipo_referencia, leido, fecha_creacion, nro_emergencia
            FROM {Config.SCHEMA}.t_notificacion
            WHERE nro_usuario = %s
            ORDER BY fecha_creacion DESC;
        """
        resultados = db.execute_query(query, (nro_usuario,), fetchall=True)
        alertas = []
        if resultados:
            for r in resultados:
                alertas.append({
                    "id_notificacion": r[0],
                    "titulo": r[1],
                    "cuerpo": r[2],
                    "tipo_referencia": r[3],
                    "leido": r[4],
                    "fecha_creacion": r[5].strftime("%Y-%m-%d %H:%M:%S") if r[5] else None,
                    "nro_emergencia": r[6]
                })
        return alertas
    finally:
        db.close_connection()

def marcar_notificacion_leida_db(id_notificacion: int, nro_usuario: int):
    """
    Modifica el estado de 'leido' a TRUE para una sola alerta (comprobando pertenencia).
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        query = f"""
            UPDATE {Config.SCHEMA}.t_notificacion
            SET leido = TRUE
            WHERE id_notificacion = %s AND nro_usuario = %s;
        """
        filas_afectadas = db.execute_query(query, (id_notificacion, nro_usuario), commit=True)
        return filas_afectadas > 0
    finally:
        db.close_connection()

def marcar_todas_las_notificaciones_leidas_db(nro_usuario: int):
    """
    Actualiza masivamente todas las alertas de un usuario a leídas (Botón masivo).
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        query = f"""
            UPDATE {Config.SCHEMA}.t_notificacion
            SET leido = TRUE
            WHERE nro_usuario = %s AND leido = FALSE;
        """
        filas_afectadas = db.execute_query(query, (nro_usuario,), commit=True)
        return filas_afectadas
    finally:
        db.close_connection()