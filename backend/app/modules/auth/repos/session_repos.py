"""Current authorization state; JWT supplies identity, never current authority."""
from app.core.postgres import PostgreSQL
from app.core.config import Config


def obtener_contexto_actual(id_usuario):
    db = PostgreSQL()
    db.create_connection()
    try:
        if db.conn is None:
            from fastapi import HTTPException
            raise HTTPException(503, detail='No se pudo verificar la sesión. Intente nuevamente.')
        s = Config.SCHEMA or 'comercio'
        row = db.execute_query(f'''
            SELECT u.id_usuario,u.id_empresa,u.estado,(SELECT r.id_rol FROM {s}.t_usuario_rol ur JOIN {s}.t_rol r USING(id_rol)
                    WHERE ur.id_usuario=u.id_usuario AND r.activo ORDER BY (r.id_rol=u.id_rol) DESC,r.id_rol LIMIT 1),e.estado,
                ARRAY(SELECT r.nombre FROM {s}.t_usuario_rol ur JOIN {s}.t_rol r USING(id_rol)
                      WHERE ur.id_usuario=u.id_usuario AND r.activo ORDER BY r.id_rol),
                ARRAY(SELECT us.id_sucursal FROM {s}.t_usuario_sucursal us JOIN {s}.t_sucursal b USING(id_sucursal)
                      WHERE us.id_usuario=u.id_usuario AND b.id_empresa=u.id_empresa AND b.activo ORDER BY us.id_sucursal),
                u.username,u.nombre,u.apellido,e.nombre_empresa,
                CASE 
                    WHEN u.id_empresa IS NULL AND EXISTS (
                        SELECT 1 FROM {s}.t_usuario_rol ur JOIN {s}.t_rol r USING(id_rol)
                        WHERE ur.id_usuario=u.id_usuario AND r.activo AND r.nombre IN ('ADMINISTRADOR', 'SUPERADMIN')
                    ) THEN ARRAY(SELECT codigo FROM {s}.t_permiso WHERE activo ORDER BY codigo)
                    ELSE ARRAY(
                        SELECT DISTINCT p.codigo
                        FROM (
                            SELECT rp.id_permiso
                            FROM {s}.t_usuario_rol ur
                            INNER JOIN {s}.t_rol r ON r.id_rol = ur.id_rol
                            INNER JOIN {s}.t_rol_permiso rp ON rp.id_rol = ur.id_rol
                            WHERE ur.id_usuario = u.id_usuario AND r.activo = TRUE
                            UNION
                            SELECT up.id_permiso
                            FROM {s}.t_usuario_permiso up
                            WHERE up.id_usuario = u.id_usuario AND up.activo = TRUE
                        ) sub
                        INNER JOIN {s}.t_permiso p ON p.id_permiso = sub.id_permiso
                        WHERE p.activo = TRUE
                        ORDER BY p.codigo
                    )
                END AS permisos
            FROM {s}.t_usuario u LEFT JOIN {s}.empresa e USING(id_empresa)
            WHERE u.id_usuario=%s
        ''', (id_usuario,), fetchone=True)
        if not row:
            return None
        return dict(zip(('id_usuario','id_empresa','activo','id_rol','estado_empresa','roles','sucursales',
                         'username','nombre','apellido','nombre_empresa','permisos'), row))
    finally:
        db.close_connection()
