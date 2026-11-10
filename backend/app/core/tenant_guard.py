from typing import Optional, List, Dict, Any
import threading
import time
from fastapi import HTTPException, status
from app.core.postgres import PostgreSQL
from app.core.config import Config

_TENANT_CACHE_LOCK = threading.Lock()
_SUCURSALES_EMPRESA_CACHE: Dict[tuple, tuple] = {}
_ESTADO_EMPRESA_CACHE: Dict[tuple, tuple] = {}
_TENANT_CACHE_TTL_SECONDS = 20.0


def invalidar_cache_tenant() -> None:
    """Invalida los cachés en memoria de estado de empresa y sucursales activas."""
    with _TENANT_CACHE_LOCK:
        _SUCURSALES_EMPRESA_CACHE.clear()
        _ESTADO_EMPRESA_CACHE.clear()


def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'


def obtener_sucursales_autorizadas(payload: dict) -> Optional[List[int]]:
    """Obtiene sucursales vigentes desde BD, no desde una lista stale del JWT."""
    alcance = obtener_alcance_usuario(payload)
    if alcance == 'PLATAFORMA':
        return None

    id_empresa = payload.get('id_empresa')
    id_usuario = payload.get('id_usuario') or payload.get('nro_usuario')
    if not id_empresa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El usuario no tiene empresa autorizada.")

    if alcance == 'SUCURSAL' and payload.get('_permisos_vigentes') and 'sucursales' in payload and payload.get('sucursales') is not None:
        return [int(sid) for sid in payload.get('sucursales') or []]

    schema = _get_schema()
    now = time.monotonic()
    if alcance != 'SUCURSAL':
        cache_key = (schema, int(id_empresa))
        with _TENANT_CACHE_LOCK:
            cached = _SUCURSALES_EMPRESA_CACHE.get(cache_key)
            if cached is not None and (now - cached[0]) < _TENANT_CACHE_TTL_SECONDS:
                return list(cached[1])

    db = PostgreSQL()
    db.create_connection()
    try:
        if alcance == 'SUCURSAL':
            query = f"""
                SELECT us.id_sucursal
                FROM {schema}.t_usuario_sucursal us
                INNER JOIN {schema}.t_sucursal s ON s.id_sucursal = us.id_sucursal
                WHERE us.id_usuario = %s AND s.id_empresa = %s AND s.activo = TRUE
                ORDER BY us.id_sucursal;
            """
            rows = db.execute_query(query, (id_usuario, id_empresa), fetchall=True) or []
            return [row[0] for row in rows]
        else:
            query = f"""
                SELECT id_sucursal
                FROM {schema}.t_sucursal
                WHERE id_empresa = %s AND activo = TRUE
                ORDER BY id_sucursal;
            """
            rows = db.execute_query(query, (id_empresa,), fetchall=True) or []
            result = [row[0] for row in rows]
            with _TENANT_CACHE_LOCK:
                _SUCURSALES_EMPRESA_CACHE[(schema, int(id_empresa))] = (now, tuple(result))
            return result
    finally:
        db.close_connection()


def resolver_sucursal_autorizada(payload: dict, id_sucursal_solicitada: Optional[int] = None) -> Optional[int]:
    """Valida una sucursal solicitada y resuelve la predeterminada de alcance sucursal."""
    autorizadas = obtener_sucursales_autorizadas(payload)
    if autorizadas is None:
        return id_sucursal_solicitada
    if id_sucursal_solicitada is not None:
        if id_sucursal_solicitada not in autorizadas:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene autorización sobre esta sucursal.")
        return id_sucursal_solicitada
    if payload.get('alcance') == 'SUCURSAL':
        if not autorizadas:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El usuario no tiene sucursales autorizadas.")
        return autorizadas[0]
    return None

# --- IDENTIFICACIÓN DE ALCANCE Y ROLES ---

def obtener_alcance_usuario(payload: dict) -> str:
    """
    Determina el alcance de seguridad del usuario autenticado:
    - 'PLATAFORMA': Administrador global / Superadmin sin empresa fija.
    - 'EMPRESA': Administrador de tienda o usuario acotado a un Tenant específico.
    - 'SUCURSAL': Encargado o cajero acotado a sucursal(es).
    """
    roles = {str(r).upper() for r in payload.get('roles', [])}
    # Current role names from DB; legacy numeric IDs are not authority.
    if not payload.get('id_empresa'):
        return 'PLATAFORMA' if roles.intersection({'ADMINISTRADOR', 'SUPERADMIN'}) else 'CLIENTE'
    if 'CLIENTE' in roles and not roles.intersection({'ADMINISTRADOR', 'ADMINISTRADOR_TIENDA', 'SUPERADMIN', 'CAJERO', 'ENCARGADO_SUCURSAL', 'EMPLEADO'}):
        return 'CLIENTE'
    if roles.intersection({'ADMINISTRADOR', 'ADMINISTRADOR_TIENDA', 'SUPERADMIN'}):
        return 'EMPRESA'
    return 'SUCURSAL'


def es_administrador_global(payload: dict) -> bool:
    """Retorna True solo si el usuario tiene alcance global/multitenant."""
    return obtener_alcance_usuario(payload) == 'PLATAFORMA'

def es_administrador_tienda(payload: dict) -> bool:
    """Retorna True si el usuario es Administrador de Tienda (acotado a su empresa)."""
    id_rol = payload.get('id_rol')
    roles = [str(r).upper() for r in payload.get('roles', [])]
    nombre_rol = str(payload.get('nombre_rol', '')).upper()
    return id_rol == 3 or 'ADMINISTRADOR_TIENDA' in roles or nombre_rol == 'ADMINISTRADOR_TIENDA'

# --- RESOLUCIÓN Y VALIDACIÓN DE TENANT EFECTIVO ---

def resolver_tenant_operacion(
    payload: dict,
    id_empresa_solicitado: Optional[int] = None,
    permitir_global: bool = False
) -> Optional[int]:
    """
    Determina el ID de empresa obligatorio para una operación:
    - Para ADMINISTRADOR_TIENDA (o usuarios con empresa):
      FUERZA estrictamente su propio id_empresa. Si envió un id_empresa diferente en el cuerpo o query,
      lo rechaza con 403 Forbidden. Nunca permite operar sin tenant.
    - Para ADMINISTRADOR global:
      Permite indicar explícitamente el tenant deseado (validando que exista en la BD).
      Si no se envía tenant y 'permitir_global' es False (e.g. crear productos, sucursales, etc.),
      exige seleccionar un tenant con 400 Bad Request.
    """
    es_global = es_administrador_global(payload)
    id_empresa_sesion = payload.get('id_empresa')

    if not es_global:
        # Monotenant estricto
        if not id_empresa_sesion:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: El usuario no tiene asignado un Tenant (empresa) válido."
            )
        id_empresa_sesion = int(id_empresa_sesion)
        if id_empresa_solicitado is not None and int(id_empresa_solicitado) != id_empresa_sesion:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Violación de Tenant: No tiene autorización para consultar o gestionar recursos de otra empresa (Solicitado: #{id_empresa_solicitado}, Autorizado: #{id_empresa_sesion})."
            )
        return id_empresa_sesion

    # Es ADMINISTRADOR Global / Multi-tenant
    if id_empresa_solicitado is not None and int(id_empresa_solicitado) > 0:
        empresa_id = int(id_empresa_solicitado)
        schema = _get_schema()
        now = time.monotonic()
        cache_key = (schema, empresa_id)
        with _TENANT_CACHE_LOCK:
            cached = _ESTADO_EMPRESA_CACHE.get(cache_key)
            if cached is not None and (now - cached[0]) < _TENANT_CACHE_TTL_SECONDS:
                estado_cached = cached[1]
                if estado_cached is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El Tenant seleccionado con ID #{empresa_id} no existe en el sistema."
                    )
                if estado_cached != 'ACTIVO':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El Tenant #{empresa_id} se encuentra inactivo."
                    )
                return empresa_id

        # Validar existencia de la empresa en la BD
        db = PostgreSQL()
        db.create_connection()
        try:
            row = db.execute_query(
                f"SELECT id_empresa, estado FROM {schema}.empresa WHERE id_empresa = %s;",
                (empresa_id,),
                fetchone=True
            )
            with _TENANT_CACHE_LOCK:
                _ESTADO_EMPRESA_CACHE[cache_key] = (now, row[1] if row else None)
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El Tenant seleccionado con ID #{empresa_id} no existe en el sistema."
                )
            if row[1] == 'PENDIENTE':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        'code': 'EMPRESA_PENDIENTE_PAGO',
                        'message': f"Tu tienda se encuentra en espera de confirmación de pago para su activación comercial. Completa el pago en Suscripciones para comenzar a operar."
                    }
                )
            if row[1] != 'ACTIVO':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El Tenant #{empresa_id} se encuentra inactivo."
                )
            return empresa_id
        finally:
            db.close_connection()

    if not permitir_global:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Como Administrador Global, debe seleccionar o identificar explícitamente el Tenant correspondiente para esta operación."
        )

    return None

# --- VALIDACIÓN DE ACCESO A UN RECURSO ESPECÍFICO ---

def validar_acceso_recurso_tenant(
    payload: dict,
    id_empresa_recurso: Optional[int],
    nombre_recurso: str = "recurso"
):
    """
    Verifica que el recurso pertenezca al Tenant del usuario.
    Si el usuario es Administrador Global, se le permite el acceso.
    Si el usuario es Monotenant y el recurso es de otra empresa, lanza 403 Forbidden.
    """
    if es_administrador_global(payload):
        return  # Administrador global autorizado

    id_empresa_sesion = payload.get('id_empresa')
    if not id_empresa_sesion:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acceso denegado: Usuario sin empresa asignada para acceder a este {nombre_recurso}."
        )

    if id_empresa_recurso is None or int(id_empresa_recurso) != int(id_empresa_sesion):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acceso denegado: El {nombre_recurso} pertenece a otro Tenant o no tiene permisos para acceder a él."
        )

# --- VALIDACIÓN DE RELACIONES ENTRE ENTIDADES (NO MEZCLAR TENANTS) ---

def validar_relaciones_tenant(
    id_empresa: int,
    id_categoria: Optional[int] = None,
    tallas_ids: Optional[List[int]] = None,
    colores_ids: Optional[List[int]] = None,
    id_ciudad: Optional[int] = None
):
    """
    Garantiza que ninguna de las entidades foráneas vinculadas a una operación
    pertenezca a un Tenant diferente.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # 1. Validar Categoría
        if id_categoria:
            row_cat = db.execute_query(
                f"SELECT id_empresa, activo, nombre FROM {schema}.t_categoria WHERE id_categoria = %s;",
                (id_categoria,),
                fetchone=True
            )
            if not row_cat:
                raise HTTPException(status_code=400, detail=f"La categoría #{id_categoria} no existe.")
            if row_cat[0] is not None and int(row_cat[0]) != int(id_empresa):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"La categoría '{row_cat[2]}' pertenece a otro Tenant y no puede asociarse a este recurso."
                )

        # 2. Validar Tallas en lote (1 query en lugar de N)
        if tallas_ids:
            tallas_unicas = list(dict.fromkeys(int(t) for t in tallas_ids if t is not None))
            if tallas_unicas:
                rows_t = db.execute_query(
                    f"SELECT id_talla, id_empresa, activo, nombre FROM {schema}.t_talla WHERE id_talla = ANY(%s);",
                    (tallas_unicas,),
                    fetchall=True
                ) or []
                mapa_tallas = {int(r[0]): r for r in rows_t}
                for t_id in tallas_unicas:
                    row_t = mapa_tallas.get(t_id)
                    if not row_t:
                        raise HTTPException(status_code=400, detail=f"La talla #{t_id} no existe.")
                    if row_t[1] is not None and int(row_t[1]) != int(id_empresa):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"La talla '{row_t[3]}' pertenece a otro Tenant."
                        )

        # 3. Validar Colores en lote (1 query en lugar de N)
        if colores_ids:
            colores_unicos = list(dict.fromkeys(int(c) for c in colores_ids if c is not None))
            if colores_unicos:
                rows_c = db.execute_query(
                    f"SELECT id_color, id_empresa, activo, nombre FROM {schema}.t_color WHERE id_color = ANY(%s);",
                    (colores_unicos,),
                    fetchall=True
                ) or []
                mapa_colores = {int(r[0]): r for r in rows_c}
                for c_id in colores_unicos:
                    row_c = mapa_colores.get(c_id)
                    if not row_c:
                        raise HTTPException(status_code=400, detail=f"El color #{c_id} no existe.")
                    if row_c[1] is not None and int(row_c[1]) != int(id_empresa):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"El color '{row_c[3]}' pertenece a otro Tenant."
                        )

        # 4. Validar Ciudad (referencia geográfica)
        if id_ciudad:
            row_ciu = db.execute_query(
                f"SELECT activo, nombre FROM {schema}.t_ciudad WHERE id_ciudad = %s;",
                (id_ciudad,),
                fetchone=True
            )
            if not row_ciu:
                raise HTTPException(status_code=400, detail="La ciudad seleccionada no existe.")
            if not row_ciu[0]:
                raise HTTPException(status_code=400, detail=f"La ciudad '{row_ciu[1]}' se encuentra inactiva.")

    finally:
        db.close_connection()
