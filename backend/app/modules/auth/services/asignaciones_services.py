"""CU43W uses P1 t_usuario_sucursal; no new employee entity."""
from fastapi import HTTPException
from app.core.postgres import transaction
from app.core.config import Config
from app.modules.saas.services.saas_services import auditar
from app.core.tenant_guard import validar_acceso_recurso_tenant, obtener_sucursales_autorizadas, obtener_alcance_usuario


def validar_ids(ids):
    if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids):
        raise HTTPException(422, detail='Se requiere una lista de IDs enteros positivos.')
    return sorted(set(ids))


def usuario_autorizado(db, usuario, actor, nuevo=False):
    s = Config.SCHEMA or 'comercio'
    row = db.execute_query(f'SELECT id_empresa FROM {s}.t_usuario WHERE id_usuario=%s FOR UPDATE', (usuario,), fetchone=True)
    if not row:
        raise HTTPException(404, detail='Usuario inexistente.')
    validar_acceso_recurso_tenant(actor, row[0], 'usuario')
    if obtener_alcance_usuario(actor) == 'SUCURSAL':
        permitidas = obtener_sucursales_autorizadas(actor)
        ajena = db.execute_query(f'SELECT 1 FROM {s}.t_usuario_sucursal WHERE id_usuario=%s AND NOT (id_sucursal=ANY(%s)) LIMIT 1', (usuario, permitidas), fetchone=True)
        comun = db.execute_query(f'SELECT 1 FROM {s}.t_usuario_sucursal WHERE id_usuario=%s AND id_sucursal=ANY(%s) LIMIT 1', (usuario, permitidas), fetchone=True)
        if ajena or (not comun and not nuevo):
            raise HTTPException(403, detail='Usuario fuera de las sucursales autorizadas.')
    return row[0]


def validar_jerarquia_usuario(usuario, actor):
    from app.modules.auth.repos import rbac_repos
    from app.modules.auth.services.rbac_services import obtener_nivel_actor
    nivel = obtener_nivel_actor(actor)
    roles = rbac_repos.obtener_roles_usuario(usuario)
    if any(rbac_repos.obtener_nivel_autoridad(r['nombre'], actor.get('id_empresa')) < nivel for r in roles):
        raise HTTPException(403, detail='No puede modificar a un usuario con mayor autoridad.')


def validar_sucursales(db, empresa, ids, actor):
    ids = validar_ids(ids)
    if ids and empresa is None:
        raise HTTPException(403, detail='Un empleado asignado debe tener empresa.')
    s = Config.SCHEMA or 'comercio'
    if ids:
        rows = db.execute_query(f'SELECT id_sucursal FROM {s}.t_sucursal WHERE id_sucursal=ANY(%s) AND id_empresa=%s AND activo FOR SHARE', (ids, empresa), fetchall=True)
        if {r[0] for r in rows} != set(ids):
            raise HTTPException(403, detail='Sucursales inexistentes, inactivas o de otra empresa.')
    if obtener_alcance_usuario(actor) == 'SUCURSAL':
        if not set(ids).issubset(set(obtener_sucursales_autorizadas(actor))):
            raise HTTPException(403, detail='No puede asignar sucursales fuera de su alcance.')
    return ids


def consultar(usuario, actor):
    with transaction() as db:
        usuario_autorizado(db, usuario, actor)
        return [r[0] for r in db.execute_query(f'SELECT id_sucursal FROM {Config.SCHEMA or "comercio"}.t_usuario_sucursal WHERE id_usuario=%s ORDER BY id_sucursal', (usuario,), fetchall=True)]


def asignar(usuario, ids, actor, nuevo=False):
    with transaction() as db:
        empresa = usuario_autorizado(db, usuario, actor, nuevo=nuevo)
        validar_jerarquia_usuario(usuario, actor)
        ids = validar_sucursales(db, empresa, ids, actor)
        s = Config.SCHEMA or 'comercio'
        anteriores = [r[0] for r in db.execute_query(f'SELECT id_sucursal FROM {s}.t_usuario_sucursal WHERE id_usuario=%s', (usuario,), fetchall=True)]
        db.execute_query(f'DELETE FROM {s}.t_usuario_sucursal WHERE id_usuario=%s', (usuario,))
        for sid in ids:
            db.execute_query(f'INSERT INTO {s}.t_usuario_sucursal(id_usuario,id_sucursal) VALUES (%s,%s)', (usuario, sid))
        auditar(db, actor, empresa, 'EMPLEADO_SUCURSALES_ASIGNADAS', {'id_usuario': usuario, 'anteriores': anteriores, 'ids_sucursales': ids})
    return {'success': True, 'message': 'Sucursales asignadas correctamente.', 'id_usuario': usuario, 'sucursales': ids}
