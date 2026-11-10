from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from werkzeug.security import generate_password_hash
from app.modules.auth.repos import users_repos
from app.modules.auth.repos import rbac_repos
from app.core.postgres import atomic, transaction
from app.modules.auth.services import asignaciones_services
from app.modules.saas.services.saas_services import auditar
from app.modules.admin.services import bitacora_services
from app.modules.auth.services import rbac_services
from app.core.tenant_guard import (
    es_administrador_global,
    resolver_tenant_operacion,
    validar_acceso_recurso_tenant
)

def _validar_ids_entrada(data):
    for field in ('ids_permisos', 'ids_sucursales'):
        if field in data:
            asignaciones_services.validar_ids(data[field])
    if 'id_sucursal' in data and data['id_sucursal'] is not None:
        asignaciones_services.validar_ids([data['id_sucursal']])


def is_global_admin(payload: dict) -> bool:
    return es_administrador_global(payload)

def listar_usuarios(payload: dict, id_empresa_filtro: Optional[int] = None) -> Dict[str, Any]:
    empresa_efectiva = resolver_tenant_operacion(payload, id_empresa_filtro, permitir_global=True)
    
    if empresa_efectiva is not None:
        usuarios = users_repos.obtener_usuarios_por_empresa(empresa_efectiva)
    else:
        usuarios = users_repos.obtener_todos_los_usuarios()
        
    from app.core.tenant_guard import obtener_alcance_usuario, obtener_sucursales_autorizadas
    if obtener_alcance_usuario(payload) == 'SUCURSAL':
        permitidas = set(obtener_sucursales_autorizadas(payload))
        usuarios = [u for u in usuarios if u.get('ids_sucursales') and set(u['ids_sucursales']).issubset(permitidas)]
    return {
        "success": True,
        "message": "Usuarios recuperados exitosamente",
        "data": usuarios
    }

def obtener_usuario_detalle(id_usuario: int, payload: dict) -> Dict[str, Any]:
    if id_usuario <= 0:
        raise HTTPException(status_code=400, detail="ID de usuario no válido.")

    user_db = users_repos.obtener_usuario_por_id(id_usuario)
    if not user_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    with transaction() as db:
        asignaciones_services.usuario_autorizado(db, id_usuario, payload)

    return {
        "success": True,
        "data": user_db
    }

@atomic
def registrar_usuario(data: dict, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    _validar_ids_entrada(data)
    campos_requeridos = ['nombre_completo', 'nombre_usuario', 'password']
    for campo in campos_requeridos:
        if not data.get(campo) or not str(data[campo]).strip():
            raise HTTPException(status_code=400, detail=f"El campo '{campo}' es obligatorio.")

    id_rol = data.get('nro_rol') or data.get('id_rol')
    if not id_rol:
        raise HTTPException(status_code=400, detail="El campo 'id_rol' es obligatorio.")
    id_rol = int(id_rol)

    # 1. Validación de Jerarquía Estricta
    try:
        rbac_services.validar_asignacion_rol(payload, id_rol)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    # 2. Resolución de Tenant Efectivo
    id_empresa_solicitado = data.get('id_empresa')
    if id_empresa_solicitado in (0, '0', '', None):
        id_empresa_solicitado = None
    else:
        id_empresa_solicitado = int(id_empresa_solicitado)

    id_empresa = resolver_tenant_operacion(payload, id_empresa_solicitado, permitir_global=True)
    if id_empresa is None and rbac_services.obtener_nivel_rol_destino(id_rol) not in (2, 6):
        raise HTTPException(422, detail='Un empleado debe pertenecer a una empresa.')

    password_hash = generate_password_hash(data['password'])

    nombre_completo = str(data['nombre_completo']).strip()
    partes = nombre_completo.split(' ', 1)
    nombre = partes[0]
    apellido = partes[1] if len(partes) > 1 else ''

    datos_usuario = {
        'username': str(data.get('nombre_usuario') or data.get('username')).strip().lower(),
        'correo': data.get('correo'),
        'password_hash': password_hash,
        'nombre': nombre,
        'apellido': apellido,
        'telefono': data.get('telefono'),
        'id_empresa': id_empresa,
        'id_rol': id_rol
    }

    nuevo_id = users_repos.crear_usuario_db(None, datos_usuario)

    # 3. Asignación opcional de Permisos Directos iniciales
    ids_permisos = data.get('ids_permisos')
    if ids_permisos and isinstance(ids_permisos, list):
        rbac_services.validar_delegacion_permisos(payload, ids_permisos)
        rbac_repos.asignar_permisos_directos_a_usuario(nuevo_id, ids_permisos)

    # 4. Asignación de Sucursales a Usuario (Encargado / Cajero / etc.)
    ids_sucursales = data.get('ids_sucursales')
    if ids_sucursales is None and data.get('id_sucursal'):
        ids_sucursales = [int(data.get('id_sucursal'))]
    elif isinstance(ids_sucursales, list):
        ids_sucursales = [int(s) for s in ids_sucursales if s]
    
    if ids_sucursales:
        if not is_global_admin(payload) and id_empresa:
            from app.modules.inventario.repos import sucursales_repos
            sucs_empresa = sucursales_repos.obtener_sucursales_por_empresa(id_empresa)
            sucs_validas = {s['id_sucursal'] for s in sucs_empresa}
            for sid in ids_sucursales:
                if sid not in sucs_validas:
                    raise HTTPException(status_code=403, detail="No puede asignar una sucursal ajena a su empresa.")
        asignaciones_services.asignar(nuevo_id, ids_sucursales, payload, nuevo=True)

    with transaction() as db:
        auditar(db, payload, id_empresa, 'USUARIO_GUARDADO', {'id_usuario': locals().get('nuevo_id', locals().get('id_usuario'))})

    # Auditoría
    datos_log = {k: v for k, v in datos_usuario.items() if k != 'password_hash'}
    try:
        bitacora_services.registrar_accion(
            modulo="USUARIOS", 
            accion="USUARIO_CREADO", 
            nivel="INFO", 
            resultado="EXITO",
            payload_jwt=payload, 
            entidad="Usuario", 
            id_entidad=str(nuevo_id),
            descripcion=f"Usuario creado: {nombre_completo} con rol #{id_rol}",
            datos_nuevos=datos_log,
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar usuario: {e}")

    return {
        "success": True,
        "message": "Usuario registrado exitosamente",
        "nro_usuario": nuevo_id,
        "id_usuario": nuevo_id
    }

@atomic
def actualizar_usuario(id_usuario: int, data: dict, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_usuario <= 0:
        raise ValueError("ID de usuario no válido.")
        
    _validar_ids_entrada(data)
    campos_requeridos = ['nombre_completo', 'nombre_usuario']
    for campo in campos_requeridos:
        if not data.get(campo) or not str(data[campo]).strip():
            raise ValueError(f"El campo '{campo}' es obligatorio.")

    user_db_before = users_repos.obtener_usuario_por_id(id_usuario)
    if not user_db_before:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    id_rol = data.get('nro_rol') or data.get('id_rol') or user_db_before.get('id_rol')
    if not id_rol:
        raise ValueError("El campo 'id_rol' es obligatorio.")
    id_rol = int(id_rol)

    # 1. Validación de Jerarquía Estricta
    try:
        rbac_services.validar_asignacion_rol(payload, id_rol)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    nivel_actor = rbac_services.obtener_nivel_actor(payload)
    rol_actual_id = user_db_before.get('id_rol')
    if rol_actual_id:
        nivel_actual = rbac_services.obtener_nivel_rol_destino(rol_actual_id)
        if nivel_actor > nivel_actual:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Violación de jerarquía: No puede modificar a un usuario con mayor autoridad que la suya.")

    # 2. Validación Multi-Tenant
    with transaction() as db:
        asignaciones_services.usuario_autorizado(db, id_usuario, payload)
        asignaciones_services.validar_jerarquia_usuario(id_usuario, payload)

    id_empresa_solicitado = data.get('id_empresa')
    if id_empresa_solicitado in (0, '0', '', None):
        id_empresa_solicitado = None
    else:
        id_empresa_solicitado = int(id_empresa_solicitado)

    if not is_global_admin(payload):
        id_empresa = payload.get('id_empresa')
    else:
        id_empresa = id_empresa_solicitado

    if id_empresa_solicitado is not None and id_empresa_solicitado != user_db_before.get('id_empresa'):
        raise HTTPException(409, detail='Trasladar usuarios entre empresas requiere un proceso especifico.')
    id_empresa = user_db_before.get('id_empresa')

    nombre_completo = data.get('nombre_completo')
    if nombre_completo:
        partes = str(nombre_completo).strip().split(' ', 1)
        nombre = partes[0]
        apellido = partes[1] if len(partes) > 1 else ''
    else:
        nombre = data.get('nombre') or user_db_before.get('nombre') or ''
        apellido = data.get('apellido') or user_db_before.get('apellido') or ''

    datos_usuario = {
        'username': str(data.get('nombre_usuario') or data.get('username') or user_db_before.get('username') or '').strip().lower(),
        'correo': data.get('correo') or user_db_before.get('correo'),
        'nombre': nombre,
        'apellido': apellido,
        'telefono': data.get('telefono') if 'telefono' in data else user_db_before.get('telefono'),
        'id_empresa': id_empresa if id_empresa is not None else user_db_before.get('id_empresa'),
        'id_rol': id_rol if id_rol else user_db_before.get('id_rol'),
        'estado': data.get('estado', user_db_before.get('estado'))
    }

    cambiar_password = False
    if data.get('password') and len(str(data.get('password')).strip()) > 0:
        cambiar_password = True
        datos_usuario['password_hash'] = generate_password_hash(data['password'])

    users_repos.actualizar_usuario_db(id_usuario, data.get('ci'), None, datos_usuario, cambiar_password)

    # 3. Asignación opcional de Permisos Directos si vienen en el payload
    if 'ids_permisos' in data and isinstance(data['ids_permisos'], list):
        rbac_services.validar_delegacion_permisos(payload, data['ids_permisos'])
        rbac_repos.asignar_permisos_directos_a_usuario(id_usuario, data['ids_permisos'])

    # 4. Asignación opcional de Sucursales si vienen en el payload
    if 'ids_sucursales' in data or 'id_sucursal' in data:
        ids_sucursales = data.get('ids_sucursales')
        if ids_sucursales is None and data.get('id_sucursal'):
            ids_sucursales = [int(data.get('id_sucursal'))]
        elif isinstance(ids_sucursales, list):
            ids_sucursales = [int(s) for s in ids_sucursales if s]
        elif ids_sucursales is None:
            ids_sucursales = []

        if ids_sucursales:
            if not is_global_admin(payload) and id_empresa:
                from app.modules.inventario.repos import sucursales_repos
                sucs_empresa = sucursales_repos.obtener_sucursales_por_empresa(id_empresa)
                sucs_validas = {s['id_sucursal'] for s in sucs_empresa}
                for sid in ids_sucursales:
                    if sid not in sucs_validas:
                        raise HTTPException(status_code=403, detail="No puede asignar una sucursal ajena a su empresa.")
        asignaciones_services.asignar(id_usuario, ids_sucursales, payload)

    with transaction() as db:
        auditar(db, payload, id_empresa, 'USUARIO_GUARDADO', {'id_usuario': locals().get('nuevo_id', locals().get('id_usuario'))})

    # Auditoría
    datos_log = {k: v for k, v in datos_usuario.items() if k != 'password_hash'}
    datos_anteriores = {k: v for k, v in user_db_before.items() if k != 'password_hash'}
    try:
        bitacora_services.registrar_accion(
            modulo="USUARIOS", 
            accion="USUARIO_EDITADO", 
            nivel="INFO", 
            resultado="EXITO",
            payload_jwt=payload, 
            entidad="Usuario", 
            id_entidad=str(id_usuario),
            descripcion=f"Usuario editado: {nombre_completo}",
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_log,
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar edición de usuario: {e}")

    return {
        "success": True,
        "message": "Usuario actualizado exitosamente"
    }

@atomic
def eliminar_usuario(id_usuario: int, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_usuario <= 0:
        raise HTTPException(status_code=400, detail="ID de usuario no válido.")
        
    user_db = users_repos.obtener_usuario_por_id(id_usuario)
    if not user_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    with transaction() as db:
        asignaciones_services.usuario_autorizado(db, id_usuario, payload)
        asignaciones_services.validar_jerarquia_usuario(id_usuario, payload)

    nivel_actor = rbac_services.obtener_nivel_actor(payload)
    rol_actual_id = user_db.get('id_rol')
    if rol_actual_id:
        nivel_actual = rbac_services.obtener_nivel_rol_destino(rol_actual_id)
        if nivel_actor > nivel_actual:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Violación de jerarquía: No puede desactivar a un usuario con mayor autoridad que la suya.")

    users_repos.eliminar_usuario_db(id_usuario)
    
    try:
        bitacora_services.registrar_accion(
            modulo="USUARIOS", 
            accion="USUARIO_DESACTIVADO", 
            nivel="WARNING", 
            resultado="EXITO",
            payload_jwt=payload, 
            entidad="Usuario", 
            id_entidad=str(id_usuario),
            descripcion=f"Usuario #{id_usuario} desactivado",
            datos_anteriores={"activo": True},
            datos_nuevos={"activo": False},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar desactivación de usuario: {e}")
    
    return {
        "success": True,
        "message": "Usuario desactivado correctamente."
    }

@atomic
def cambiar_estado_usuario(id_usuario: int, data: dict, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_usuario <= 0:
        raise HTTPException(status_code=400, detail="ID de usuario no válido.")

    user_db = users_repos.obtener_usuario_por_id(id_usuario)
    if not user_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    with transaction() as db:
        asignaciones_services.usuario_autorizado(db, id_usuario, payload)
        asignaciones_services.validar_jerarquia_usuario(id_usuario, payload)

    nivel_actor = rbac_services.obtener_nivel_actor(payload)
    rol_actual_id = user_db.get('id_rol')
    if rol_actual_id:
        nivel_actual = rbac_services.obtener_nivel_rol_destino(rol_actual_id)
        if nivel_actor > nivel_actual:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Violación de jerarquía: No puede modificar el estado de un usuario con mayor autoridad que la suya.")

    nuevo_estado = bool(data.get('activo', data.get('estado', True)))
    exito = users_repos.cambiar_estado_usuario_db(id_usuario, nuevo_estado)
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado del usuario.")

    try:
        bitacora_services.registrar_accion(
            modulo="USUARIOS",
            accion="CAMBIAR_ESTADO_USUARIO",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Usuario",
            id_entidad=str(id_usuario),
            descripcion=f"Estado de usuario #{id_usuario} cambiado a {'ACTIVO' if nuevo_estado else 'INACTIVO'}",
            datos_anteriores={"estado": user_db.get('estado')},
            datos_nuevos={"estado": 'ACTIVO' if nuevo_estado else 'INACTIVO'},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar cambio de estado: {e}")

    return {
        "success": True,
        "message": f"Usuario {'activado' if nuevo_estado else 'desactivado'} correctamente."
    }
