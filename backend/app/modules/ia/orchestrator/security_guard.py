"""
Guardia de seguridad del Asistente Inteligente Aurora Advisor:
1. Resolución autoritativa de Tenant (empresa) y Sucursal desde PostgreSQL y JWT.
2. Verificación RBAC independiente del LLM antes de ejecutar cualquier herramienta.
3. Detección y neutralización de ataques de Prompt Injection directos e indirectos (en BD).
4. Validación de historial conversacional contra falsificación de roles.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from app.core.postgres import PostgreSQL
from app.core.config import Config
from app.core.tenant_guard import (
    obtener_alcance_usuario,
    obtener_sucursales_autorizadas,
    es_administrador_global
)
from app.modules.ia.ai.exceptions.ai_exceptions import (
    AISecurityViolationError,
    AIPromptInjectionError,
    AIDatabaseError
)

logger = logging.getLogger(__name__)


@dataclass
class AssistantSecurityContext:
    id_usuario: Optional[int] = None
    id_cliente: Optional[int] = None
    nombre_usuario: str = "estimado visitante"
    id_empresa: int = 1
    nombre_empresa: str = "Aurora Store"
    slug_empresa: Optional[str] = None
    alcance: str = "PUBLIC"  # PUBLIC | CLIENTE | SUCURSAL | EMPRESA | PLATAFORMA
    roles: List[str] = field(default_factory=list)
    permisos: List[str] = field(default_factory=list)
    sucursales_autorizadas: Optional[List[int]] = None  # None = todas las de la empresa
    sucursal_nombres_autorizados: Optional[List[str]] = None
    es_admin: bool = False
    token_data: Optional[Dict[str, Any]] = None

    @property
    def is_admin(self) -> bool:
        return self.es_admin

    @property
    def id_sucursal(self) -> Optional[int]:
        if self.sucursales_autorizadas:
            return self.sucursales_autorizadas[0]
        return None



# Patrones de Prompt Injection directo
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignora\s+(todas\s+)?(tus\s+|las\s+)?instrucciones(\s+anteriores|\s+previas)?", re.IGNORECASE),
    re.compile(r"olvida\s+(todas\s+)?(tus\s+|las\s+)?(reglas|instrucciones|directrices)", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|system)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"(revela|muestra|dime|imprime|print|reveal|show)\s+(tu\s+|el\s+|your\s+)?(system\s*prompt|prompt\s+del\s+sistema|instrucciones\s+internas|instrucciones\s+ocultas)", re.IGNORECASE),
    re.compile(r"(actua|actúa|comportate|compórtate|asume\s+el\s+rol)\s+como\s+(superadmin|administrador\s+global|root|dba|desarrollador\s+sin\s+restricciones)", re.IGNORECASE),
    re.compile(r"(cambia|elevar|cambiar|modificar)\s+mi\s+(rol|alcance|permiso)\s+a\s+(admin|administrador|superadmin|plataforma)", re.IGNORECASE),
    re.compile(r"<\s*\|\s*(im_start|system|endoftext)\s*\|\s*>", re.IGNORECASE),
    re.compile(r"\[\s*(SYSTEM\s*OVERRIDE|ADMIN\s*OVERRIDE|SUDO\s*MODE|JAILBREAK)\s*\]", re.IGNORECASE),
    re.compile(r"\b(DROP\s+TABLE|TRUNCATE\s+TABLE|DELETE\s+FROM\s+comercio|UPDATE\s+comercio\.t_usuario\s+SET)\b", re.IGNORECASE),
]

# Patrones de intento de acceso a datos de terceros en lenguaje natural
_CROSS_USER_PATTERNS = [
    re.compile(r"\b(pedidos?|reservas?|compras?|datos|historial)\s+(de(l)?\s+(cliente|usuario)\s+#?\d+|de\s+otra\s+persona|de\s+otro\s+cliente|de\s+todos\s+los\s+clientes)\b", re.IGNORECASE),
]

# Patrones maliciosos embebidos en descripciones de productos o datos de BD (Indirect Prompt Injection)
_INDIRECT_INJECTION_PATTERNS = [
    re.compile(r"(ignore\s+previous\s+instructions|ignora\s+las\s+instrucciones\s+anteriores)[^.]*\.?", re.IGNORECASE),
    re.compile(r"(system\s*prompt|instruccion\s+oculta|ejecuta\s+la\s+herramienta|call\s+function)[^.]*\.?", re.IGNORECASE),
    re.compile(r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>", re.IGNORECASE),
]


def detect_prompt_injection(mensaje: str) -> None:
    """Verifica si el mensaje del usuario contiene ataques de Prompt Injection."""
    if not mensaje:
        return
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(mensaje):
            logger.warning(f"Prompt injection bloqueado: {mensaje[:120]}")
            raise AIPromptInjectionError(
                "Por razones de seguridad, no puedo procesar instrucciones que intenten modificar mis directrices internas, roles o permisos del sistema."
            )


def detect_cross_user_access_attempt(mensaje: str, ctx: AssistantSecurityContext) -> None:
    """Bloquea intentos explícitos de un cliente o visitante de consultar pedidos/reservas de otra persona."""
    if not mensaje:
        return
    if not ctx.es_admin:
        for pattern in _CROSS_USER_PATTERNS:
            if pattern.search(mensaje):
                raise AISecurityViolationError(
                    "Acceso denegado: Solo puedes consultar tus propios pedidos y reservas personales.",
                    status_code=403,
                    code="CROSS_USER_ACCESS_DENIED"
                )


def sanitize_untrusted_db_content(value: Any) -> Any:
    """
    Limpia cadenas provenientes de PostgreSQL (ej. descripciones de productos, notas, nombres)
    para neutralizar ataques de Prompt Injection indirecto antes de enviarlas al LLM o al cliente.
    """
    if isinstance(value, str):
        cleaned = value
        for pat in _INDIRECT_INJECTION_PATTERNS:
            cleaned = pat.sub("[contenido filtrado por seguridad]", cleaned)
        return cleaned
    elif isinstance(value, list):
        return [sanitize_untrusted_db_content(item) for item in value]
    elif isinstance(value, dict):
        return {k: sanitize_untrusted_db_content(v) for k, v in value.items()}
    return value


def validate_and_sanitize_history(historial: Optional[List[Dict[str, Any]]], max_items: int = 8) -> List[Dict[str, str]]:
    """
    Valida el historial enviado desde el frontend.
    Elimina cualquier rol falsificado ('system', 'tool', 'developer') y neutraliza inyecciones.
    """
    if not historial or not isinstance(historial, list):
        return []

    valid_messages: List[Dict[str, str]] = []
    for item in historial[-max_items:]:
        if not isinstance(item, dict):
            continue
        raw_role = str(item.get("role") or "").strip().lower()
        # Nunca permitir que el cliente inyecte mensajes con rol 'system' o 'tool'
        if raw_role not in ("user", "assistant"):
            logger.warning(f"Rol falsificado en historial rechazado: {raw_role}")
            raise AISecurityViolationError(
                f"Historial inválido: el rol '{raw_role}' no está permitido desde el cliente.",
                status_code=400,
                code="INVALID_HISTORY_ROLE"
            )
        raw_content = str(item.get("content") or "").strip()
        if not raw_content:
            continue
        # Verificar que un mensaje de historial no contenga prompt injection
        detect_prompt_injection(raw_content)
        valid_messages.append({
            "role": raw_role,
            "content": raw_content[:2000]
        })

    return valid_messages


def resolve_assistant_context(
    token_data: Optional[Dict[str, Any]] = None,
    slug_tienda: Optional[str] = None,
    id_empresa_solicitado: Optional[int] = None
) -> AssistantSecurityContext:
    """
    Resuelve de manera autoritativa la identidad, el tenant (empresa), el alcance y las sucursales
    autorizadas del usuario o visitante desde PostgreSQL.
    """
    schema = Config.SCHEMA or "comercio"
    db = PostgreSQL()
    try:
        db.create_connection()
    except Exception as e:
        logger.error(f"Error de conexión a PostgreSQL en resolve_assistant_context: {e}")
        raise AIDatabaseError("El servicio de base de datos no está disponible en este momento.")

    try:
        # CASO 1: VISITANTE NO AUTENTICADO (PUBLIC)
        if not token_data:
            if id_empresa_solicitado is not None and not slug_tienda:
                # Validar que la empresa exista y esté ACTIVA; si un visitante intenta forzar un tenant inválido, rechazar
                row_emp = db.execute_query(
                    f"SELECT id_empresa, nombre_empresa, slug, estado FROM {schema}.empresa WHERE id_empresa = %s LIMIT 1;",
                    (int(id_empresa_solicitado),),
                    fetchone=True
                )
                if not row_emp or str(row_emp[3]).upper() != "ACTIVO":
                    raise AISecurityViolationError(
                        "La tienda solicitada no existe o no se encuentra activa.",
                        status_code=403,
                        code="INVALID_VISITOR_TENANT"
                    )
                return AssistantSecurityContext(
                    id_usuario=None,
                    id_cliente=None,
                    nombre_usuario="estimado visitante",
                    id_empresa=int(row_emp[0]),
                    nombre_empresa=str(row_emp[1] or "Aurora Store"),
                    slug_empresa=row_emp[2],
                    alcance="PUBLIC",
                    roles=["VISITANTE"],
                    permisos=["catalogo.consultar"],
                    es_admin=False,
                    token_data=None
                )

            if slug_tienda:
                slug_clean = str(slug_tienda).strip().lower()
                row_emp = db.execute_query(
                    f"SELECT id_empresa, nombre_empresa, slug, estado FROM {schema}.empresa WHERE LOWER(slug) = %s LIMIT 1;",
                    (slug_clean,),
                    fetchone=True
                )
                if not row_emp or str(row_emp[3]).upper() != "ACTIVO":
                    raise AISecurityViolationError(
                        f"La tienda '{slug_clean}' no existe o no está activa.",
                        status_code=404,
                        code="STORE_NOT_FOUND"
                    )
                return AssistantSecurityContext(
                    id_usuario=None,
                    id_cliente=None,
                    nombre_usuario="estimado visitante",
                    id_empresa=int(row_emp[0]),
                    nombre_empresa=str(row_emp[1] or "Aurora Store"),
                    slug_empresa=row_emp[2],
                    alcance="PUBLIC",
                    roles=["VISITANTE"],
                    permisos=["catalogo.consultar"],
                    es_admin=False,
                    token_data=None
                )

            # Fallback a la primera tienda activa
            row_default = db.execute_query(
                f"SELECT id_empresa, nombre_empresa, slug FROM {schema}.empresa WHERE estado = 'ACTIVO' ORDER BY id_empresa ASC LIMIT 1;",
                fetchone=True
            )
            emp_id = int(row_default[0]) if row_default else 1
            emp_nom = str(row_default[1]) if row_default else "Aurora Store"
            emp_slug = row_default[2] if row_default else None
            return AssistantSecurityContext(
                id_usuario=None,
                id_cliente=None,
                nombre_usuario="estimado visitante",
                id_empresa=emp_id,
                nombre_empresa=emp_nom,
                slug_empresa=emp_slug,
                alcance="PUBLIC",
                roles=["VISITANTE"],
                permisos=["catalogo.consultar"],
                es_admin=False,
                token_data=None
            )

        # CASO 2: USUARIO AUTENTICADO
        id_usuario = token_data.get("id_usuario") or token_data.get("nro_usuario")
        roles = [str(r).upper() for r in (token_data.get("roles") or [])]
        if token_data.get("nombre_rol"):
            nr = str(token_data["nombre_rol"]).upper()
            if nr not in roles:
                roles.append(nr)

        alcance = obtener_alcance_usuario(token_data)
        permisos = list(token_data.get("permisos") or [])
        nombre_usr = str(token_data.get("nombre") or token_data.get("username") or "estimado usuario")

        es_admin_role = bool(set(roles).intersection({
            "ADMINISTRADOR", "SUPERADMIN", "ADMINISTRADOR_TIENDA",
            "ENCARGADO", "ENCARGADO_SUCURSAL", "CAJERO", "EMPLEADO"
        })) and alcance in ("PLATAFORMA", "EMPRESA", "SUCURSAL")

        # Resolver empresa según alcance
        id_empresa_sesion = token_data.get("id_empresa")

        if alcance == "PLATAFORMA":
            target_emp = id_empresa_solicitado or id_empresa_sesion
            if slug_tienda and not target_emp:
                row_s = db.execute_query(
                    f"SELECT id_empresa FROM {schema}.empresa WHERE LOWER(slug) = %s AND estado = 'ACTIVO' LIMIT 1;",
                    (slug_tienda.strip().lower(),),
                    fetchone=True
                )
                if row_s:
                    target_emp = int(row_s[0])
            if not target_emp:
                row_first = db.execute_query(
                    f"SELECT id_empresa FROM {schema}.empresa WHERE estado = 'ACTIVO' ORDER BY id_empresa ASC LIMIT 1;",
                    fetchone=True
                )
                target_emp = int(row_first[0]) if row_first else 1
            else:
                row_check = db.execute_query(
                    f"SELECT id_empresa, estado FROM {schema}.empresa WHERE id_empresa = %s LIMIT 1;",
                    (int(target_emp),),
                    fetchone=True
                )
                if not row_check or str(row_check[1]).upper() != "ACTIVO":
                    raise AISecurityViolationError(
                        f"El Tenant #{target_emp} no existe o está inactivo.",
                        status_code=400,
                        code="INVALID_TENANT"
                    )
            id_empresa_final = int(target_emp)

        elif alcance in ("EMPRESA", "SUCURSAL"):
            if not id_empresa_sesion:
                raise AISecurityViolationError("El usuario administrativo no tiene empresa asignada.", status_code=403)
            if id_empresa_solicitado is not None and int(id_empresa_solicitado) != int(id_empresa_sesion):
                raise AISecurityViolationError(
                    f"Violación de aislamiento multitenant: No tiene autorización para consultar la empresa #{id_empresa_solicitado}.",
                    status_code=403,
                    code="CROSS_TENANT_ACCESS_DENIED"
                )
            if slug_tienda:
                row_s = db.execute_query(
                    f"SELECT id_empresa FROM {schema}.empresa WHERE LOWER(slug) = %s LIMIT 1;",
                    (slug_tienda.strip().lower(),),
                    fetchone=True
                )
                if row_s and int(row_s[0]) != int(id_empresa_sesion):
                    raise AISecurityViolationError(
                        "Violación de aislamiento multitenant: No puede operar sobre otra tienda.",
                        status_code=403,
                        code="CROSS_TENANT_ACCESS_DENIED"
                    )
            id_empresa_final = int(id_empresa_sesion)

        else:
            # Alcance CLIENTE
            target_emp = id_empresa_sesion
            if slug_tienda:
                row_s = db.execute_query(
                    f"SELECT id_empresa, estado FROM {schema}.empresa WHERE LOWER(slug) = %s LIMIT 1;",
                    (slug_tienda.strip().lower(),),
                    fetchone=True
                )
                if not row_s or str(row_s[1]).upper() != "ACTIVO":
                    raise AISecurityViolationError("La tienda solicitada no existe o no está activa.", status_code=404)
                target_emp = int(row_s[0])
            elif id_empresa_solicitado is not None:
                row_s = db.execute_query(
                    f"SELECT id_empresa, estado FROM {schema}.empresa WHERE id_empresa = %s LIMIT 1;",
                    (int(id_empresa_solicitado),),
                    fetchone=True
                )
                if not row_s or str(row_s[1]).upper() != "ACTIVO":
                    raise AISecurityViolationError("La tienda solicitada no existe o no está activa.", status_code=403)
                target_emp = int(row_s[0])

            id_empresa_final = int(target_emp) if target_emp else 1

        # Obtener nombre de la empresa
        row_emp_info = db.execute_query(
            f"SELECT nombre_empresa, slug FROM {schema}.empresa WHERE id_empresa = %s LIMIT 1;",
            (id_empresa_final,),
            fetchone=True
        )
        nombre_emp = str(row_emp_info[0]) if row_emp_info and row_emp_info[0] else "Aurora Store"
        slug_emp = row_emp_info[1] if row_emp_info else None

        # Obtener id_cliente si existe
        id_cliente = None
        if id_usuario:
            row_cli = db.execute_query(
                f"SELECT id_cliente FROM {schema}.t_cliente WHERE id_usuario = %s LIMIT 1;",
                (int(id_usuario),),
                fetchone=True
            )
            if row_cli:
                id_cliente = int(row_cli[0])

        # Obtener sucursales autorizadas cuando el alcance es SUCURSAL
        sucs_autorizadas: Optional[List[int]] = None
        sucs_nombres: Optional[List[str]] = None
        if alcance == "SUCURSAL":
            try:
                sucs_autorizadas = obtener_sucursales_autorizadas(token_data)
            except Exception:
                sucs_autorizadas = token_data.get("sucursales") or []
            if sucs_autorizadas:
                placeholders = ",".join(["%s"] * len(sucs_autorizadas))
                rows_sn = db.execute_query(
                    f"SELECT id_sucursal, nombre FROM {schema}.t_sucursal WHERE id_empresa = %s AND id_sucursal IN ({placeholders});",
                    tuple([id_empresa_final] + list(sucs_autorizadas)),
                    fetchall=True
                ) or []
                sucs_nombres = [str(r[1]) for r in rows_sn]
            else:
                sucs_nombres = []

        return AssistantSecurityContext(
            id_usuario=int(id_usuario) if id_usuario else None,
            id_cliente=id_cliente,
            nombre_usuario=nombre_usr,
            id_empresa=id_empresa_final,
            nombre_empresa=nombre_emp,
            slug_empresa=slug_emp,
            alcance=alcance,
            roles=roles,
            permisos=permisos,
            sucursales_autorizadas=sucs_autorizadas,
            sucursal_nombres_autorizados=sucs_nombres,
            es_admin=es_admin_role,
            token_data=token_data
        )
    finally:
        db.close_connection()


def verify_branch_access(ctx: AssistantSecurityContext, sucursal_filtro: Optional[str] = None, id_sucursal: Optional[int] = None) -> Optional[str]:
    """
    Si el usuario tiene alcance limitado a SUCURSAL (ej. Encargado de Sucursal o Cajero),
    verifica que no esté consultando otra sucursal no autorizada.
    Retorna el filtro de sucursal efectivo que debe aplicarse a la consulta.
    """
    if ctx.alcance != "SUCURSAL":
        return sucursal_filtro

    if not ctx.sucursales_autorizadas:
        raise AISecurityViolationError(
            "Acceso denegado: No tiene sucursales autorizadas asignadas.",
            status_code=403,
            code="NO_AUTHORIZED_BRANCHES"
        )

    if id_sucursal is not None and int(id_sucursal) not in ctx.sucursales_autorizadas:
        raise AISecurityViolationError(
            f"Acceso denegado: No tiene autorización sobre la sucursal #{id_sucursal}.",
            status_code=403,
            code="UNAUTHORIZED_BRANCH_ACCESS"
        )

    nombres_aut = ctx.sucursal_nombres_autorizados or []
    if sucursal_filtro and sucursal_filtro.strip():
        req_lower = sucursal_filtro.strip().lower()
        # Comprobar si coincide con alguna de sus sucursales autorizadas
        matched = [n for n in nombres_aut if req_lower in n.lower() or n.lower() in req_lower]
        if not matched:
            raise AISecurityViolationError(
                f"Acceso denegado: Su rol de sucursal no tiene autorización para consultar la sucursal '{sucursal_filtro}'.",
                status_code=403,
                code="UNAUTHORIZED_BRANCH_ACCESS"
            )
        return matched[0]

    # Si no especificó sucursal, restringir por defecto a su primera sucursal autorizada
    return nombres_aut[0] if nombres_aut else None
