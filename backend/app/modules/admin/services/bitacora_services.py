from fastapi import Request
import uuid
import json
import logging
from app.modules.admin.repos import bitacora_repos
from datetime import datetime
logger = logging.getLogger(__name__)

# Keys to remove from payloads to avoid leaking sensitive data
SENSITIVE_KEYS = {'password', 'password_hash', 'token', 'access_token', 'refresh_token', 'secret', 'api_key', 'credentials'}

def sanitizar_dict(data: dict) -> dict:
    if not data or not isinstance(data, dict):
        return data
        
    sanitized = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_KEYS:
            continue
        if isinstance(v, dict):
            sanitized[k] = sanitizar_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitizar_dict(item) if isinstance(item, dict) else item for item in v]
        elif isinstance(v, datetime):
            sanitized[k] = v.isoformat()
        else:
            sanitized[k] = v
    return sanitized

def get_scope_level(payload: dict) -> str:
    from app.core.tenant_guard import obtener_alcance_usuario
    return obtener_alcance_usuario(payload)


def registrar_accion(
    modulo: str,
    accion: str,
    nivel: str,
    resultado: str,
    payload_jwt: dict = None,
    entidad: str = None,
    id_entidad: str = None,
    descripcion: str = None,
    datos_anteriores: dict = None,
    datos_nuevos: dict = None,
    metadatos: dict = None,
    request: Request = None
):
    try:
        payload = payload_jwt or {}
        id_usuario = payload.get("id_usuario")
        usuario_nombre = payload.get("username")
        
        # Determine scopes from context if not available in payload
        # Generally we just take what's in the JWT for id_empresa, unless an explicit context was given.
        id_empresa = payload.get("id_empresa")
        id_sucursal = None # Sucursal can be determined if needed, JWT doesn't always have it depending on the system
        
        ip = None
        user_agent = None
        request_id = None
        
        if request:
            # Extract real IP and user agent
            # Handles X-Forwarded-For if behind a proxy
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
            else:
                ip = request.client.host if request.client else None
                
            user_agent = request.headers.get("user-agent")
            
            # Simple unique ID for the request if not injected via middleware
            request_id = str(uuid.uuid4())
            
        sanitized_anteriores = sanitizar_dict(datos_anteriores)
        sanitized_nuevos = sanitizar_dict(datos_nuevos)
        sanitized_metadatos = sanitizar_dict(metadatos)

        bitacora_repos.registrar_evento_db(
            id_usuario=id_usuario,
            usuario_nombre=usuario_nombre,
            usuario_email=None,  # We may not have email in payload directly
            id_empresa=id_empresa,
            id_sucursal=id_sucursal,
            modulo=modulo,
            accion=accion,
            entidad=entidad,
            id_entidad=str(id_entidad) if id_entidad else None,
            descripcion=descripcion,
            resultado=resultado,
            nivel=nivel,
            ip=ip,
            user_agent=user_agent,
            datos_anteriores=sanitized_anteriores,
            datos_nuevos=sanitized_nuevos,
            metadatos=sanitized_metadatos,
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Error al registrar acción en bitácora: {e}")

def obtener_eventos(
    payload: dict,
    filtros: dict,
    page: int = 1,
    limit: int = 25
):
    # RBAC & Scope enforcement
    scope = get_scope_level(payload)
    
    id_empresa_filtro = None
    id_sucursal_filtro = None
    
    from app.core.tenant_guard import resolver_tenant_operacion, obtener_sucursales_autorizadas
    from fastapi import HTTPException
    if scope == 'CLIENTE':
        raise HTTPException(403, detail='Bitacora reservada al personal autorizado.')
    id_empresa_filtro = resolver_tenant_operacion(payload, filtros.get('id_empresa'), permitir_global=True)
    id_sucursal_filtro = filtros.get('id_sucursal')
    if id_sucursal_filtro is not None:
        from app.modules.inventario.repos.sucursales_repos import obtener_sucursal_por_id
        branch = obtener_sucursal_por_id(id_sucursal_filtro)
        if not branch or (id_empresa_filtro is not None and branch['id_empresa'] != id_empresa_filtro):
            raise HTTPException(403, detail='Sucursal fuera del contexto autorizado.')
    filtros = dict(filtros)
    if scope == 'SUCURSAL':
        permitidas = obtener_sucursales_autorizadas(payload)
        if id_sucursal_filtro is not None and id_sucursal_filtro not in permitidas:
            raise HTTPException(403, detail='Sucursal no autorizada.')
        filtros['_sucursales_autorizadas'] = permitidas

    offset = (page - 1) * limit
    
    res = bitacora_repos.obtener_eventos_db(
        id_empresa_filtro=id_empresa_filtro,
        id_sucursal_filtro=id_sucursal_filtro,
        filtros=filtros,
        limit=limit,
        offset=offset
    )
    
    total = res['total']
    pages = (total + limit - 1) // limit
    
    return {
        "success": True,
        "data": res['items'],
        "page": page,
        "limit": limit,
        "total": total,
        "pages": pages
    }

def obtener_detalle_evento(id_bitacora: int, payload: dict):
    evento = bitacora_repos.obtener_detalle_evento_db(id_bitacora)
    
    if not evento:
        raise ValueError("Evento no encontrado.")
        
    from app.core.tenant_guard import validar_acceso_recurso_tenant, obtener_sucursales_autorizadas
    from fastapi import HTTPException
    validar_acceso_recurso_tenant(payload, evento['id_empresa'], 'evento')
    if get_scope_level(payload) == 'SUCURSAL' and evento.get('id_sucursal') not in obtener_sucursales_autorizadas(payload):
        raise HTTPException(403, detail='Evento fuera de las sucursales autorizadas.')

    return {
        "success": True,
        "data": evento
    }
