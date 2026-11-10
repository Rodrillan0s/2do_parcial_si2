from typing import Optional
import copy
import re
import random
import threading
import time
import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import Config
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from werkzeug.security import generate_password_hash, check_password_hash

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)

_AUTH_CONTEXT_CACHE = {}
_AUTH_CACHE_LOCK = threading.Lock()
_AUTH_CACHE_TTL_SECONDS = 20.0


def invalidar_cache_contexto(id_usuario: Optional[int] = None) -> None:
    """Invalida el caché en memoria del contexto de autorización (total o por usuario)."""
    with _AUTH_CACHE_LOCK:
        if id_usuario is None:
            _AUTH_CONTEXT_CACHE.clear()
        else:
            uid_int = int(id_usuario)
            keys_to_remove = [k for k in _AUTH_CONTEXT_CACHE if k[1] == uid_int]
            for k in keys_to_remove:
                _AUTH_CONTEXT_CACHE.pop(k, None)


# Valida que la contraseña tenga al menos 8 caracteres y 1 carácter especial.
def validar_password(password: str) -> bool:
    if not password or len(password) < 8:
        return False
    # Al menos un carácter especial
    pattern = r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]'
    return bool(re.search(pattern, password))

# Genera un hash seguro para la contraseña del usuario.
def hash_password(password: str) -> str:
    return generate_password_hash(password)

# Comprueba si una contraseña en texto plano coincide con su hash almacenado.
def verificar_password_hash(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)

# Genera un código numérico aleatorio de 6 dígitos para verificaciones o recuperación.
def generar_codigo_seguridad() -> str:
    return str(random.randint(100000, 999999))

def _get_jwt_secret() -> str:
    secret_key = Config.TOKEN_KEY or Config.SECRET_KEY
    if not secret_key:
        raise RuntimeError("TOKEN_KEY o SECRET_KEY debe estar configurada para firmar JWT.")
    return secret_key

# Genera el token JWT de acceso para la sesión del usuario con sus claims RBAC.
def create_access_token(nro_usuario, username, id_rol, id_empresa, nombre, apellido, roles=None, permisos=None, sucursales=None, nombre_empresa=None, nombre_rol=None, minutes=120):
    roles_list = roles or []
    from app.core.tenant_guard import obtener_alcance_usuario
    alcance = obtener_alcance_usuario({'roles': roles_list, 'id_empresa': id_empresa})

    rol_final = nombre_rol or (roles_list[0] if roles_list else 'CLIENTE')

    payload = {
        'nro_usuario': nro_usuario,
        'id_usuario': nro_usuario,
        'username': username,
        'id_rol': id_rol,
        'nombre_rol': rol_final,
        'id_empresa': id_empresa,
        'nombre_empresa': nombre_empresa,
        'nombre': nombre,
        'apellido': apellido,
        'roles': roles_list,
        'permisos': permisos or [],
        'sucursales': sucursales or [],
        'alcance': alcance,
        'exp': datetime.now(timezone.utc) + timedelta(minutes=minutes),
        'iat': datetime.now(timezone.utc)
    }
    secret_key = _get_jwt_secret()
    return jwt.encode(payload, secret_key, algorithm="HS256")

# Decodifica y valida la firma del token JWT recibido.
def decode_access_token(token: str):
    try:
        secret_key = _get_jwt_secret()
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return {
            'success': True,
            'message': 'TOKEN VALIDO',
            'payload': payload
        }
    except jwt.ExpiredSignatureError:
        return {
            'success': False,
            'message': 'Su sesión ha expirado. Por favor, inicie sesión nuevamente.'
        }
    except jwt.InvalidTokenError:
        return {
            'success': False,
            'message': 'Token de acceso inválido o corrupto.'
        }

def _contexto_vigente(payload):
    from app.modules.auth.repos import session_repos
    from app.modules.auth.repos import rbac_repos
    from app.core.tenant_guard import obtener_alcance_usuario
    uid = payload.get('id_usuario') or payload.get('nro_usuario')
    if not uid:
        raise HTTPException(status_code=401, detail="Token sin identidad.")

    actual = session_repos.obtener_contexto_actual(uid)
    if not actual or not actual.pop('activo'):
        raise HTTPException(status_code=401, detail="Usuario inexistente o desactivado.")
    # Rebuild authoritative claims; never merge old permissions/company/roles.
    actual['nro_usuario'] = actual['id_usuario']
    actual['nombre_rol'] = (actual['roles'] or ['CLIENTE'])[0]
    actual['rol'] = actual['nombre_rol']
    actual['alcance'] = obtener_alcance_usuario(actual)
    actual['id_sucursal'] = (actual['sucursales'] or [None])[0]
    if 'permisos' not in actual or actual['permisos'] is None:
        actual['permisos'] = rbac_repos.obtener_permisos_efectivos_usuario(uid)
    actual['_permisos_vigentes'] = True
    return actual


def _contexto_vigente_con_cache(payload: dict) -> dict:
    uid = payload.get('id_usuario') or payload.get('nro_usuario')
    if not uid:
        raise HTTPException(status_code=401, detail="Token sin identidad.")
    schema = Config.SCHEMA or 'comercio'
    cache_key = (schema, int(uid))
    now = time.monotonic()
    with _AUTH_CACHE_LOCK:
        cached = _AUTH_CONTEXT_CACHE.get(cache_key)
        if cached is not None and (now - cached[0]) < _AUTH_CACHE_TTL_SECONDS:
            return copy.deepcopy(cached[1])

    actual = _contexto_vigente(payload)
    with _AUTH_CACHE_LOCK:
        _AUTH_CONTEXT_CACHE[cache_key] = (now, copy.deepcopy(actual))
    return actual


def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    resultado = decode_access_token(credentials.credentials)
    if not resultado.get('success'):
        raise HTTPException(status_code=401, detail=resultado.get('message'))
    return _contexto_vigente_con_cache(resultado['payload'])


def verificar_token_opcional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme)):
    if not credentials:
        return None
    resultado = decode_access_token(credentials.credentials)
    if not resultado.get('success'):
        return None
    try:
        return _contexto_vigente_con_cache(resultado['payload'])
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise


# Dependencia reutilizable FastAPI para autorizar según el permiso requerido (<recurso>.<accion>)
def require_permission(codigo_permiso: str):
    def dependency(payload: dict = Depends(verificar_token)):
        if tiene_permiso(payload, codigo_permiso):
            return payload
        raise HTTPException(status_code=403, detail=f"Acceso denegado. No posee el permiso requerido: '{codigo_permiso}'")
    return dependency

def tiene_permiso(payload: dict, codigo_permiso: str) -> bool:
    if payload.get('_permisos_vigentes'):
        return codigo_permiso in payload.get('permisos', [])

    from app.modules.auth.repos import rbac_repos
    id_usuario = payload.get('nro_usuario') or payload.get('id_usuario')
    if not id_usuario:
        return False
    return codigo_permiso in rbac_repos.obtener_permisos_efectivos_usuario(id_usuario)

# Valida acceso administrativo basándose exclusivamente en el permiso 'admin.acceder'
def verificar_token_admin(payload: dict = Depends(verificar_token)):
    if tiene_permiso(payload, 'admin.acceder'):
        return payload
    raise HTTPException(status_code=403, detail="Acceso denegado. Se requiere el permiso 'admin.acceder'.")


def require_platform_admin(payload: dict = Depends(verificar_token)):
    """Autoriza exclusivamente a un administrador con alcance global."""
    roles = {str(role).upper() for role in payload.get('roles', [])}
    es_admin = bool(roles.intersection({'ADMINISTRADOR', 'SUPERADMIN'}))
    if not es_admin or payload.get('alcance') != 'PLATAFORMA' or payload.get('id_empresa'):
        raise HTTPException(status_code=403, detail="Se requiere una cuenta administradora con alcance PLATAFORMA.")
    return payload
