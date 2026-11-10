"""
Gestor de Contexto y Memoria Conversacional (ContextManager) para Aurora Advisor.
Garantiza:
1. Aislamiento estricto por usuario y tenant (empresa). Prohibida la reutilización cruzada de memoria.
2. Memoria de sesión para preferencias expresadas en el diálogo (talla, colores, colores excluidos,
   presupuesto, categoría, ocasión, sucursal).
3. Registro de los últimos productos mostrados para resolver referencias contextuales ('ese', 'el segundo',
   'el más barato', 'el más caro', 'algo parecido').
4. Concurrencia segura mediante locks por sesión.
"""

import uuid
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from app.modules.ia.orchestrator.security_guard import (
    AssistantSecurityContext,
    validate_and_sanitize_history
)
from app.modules.ia.ai.exceptions.ai_exceptions import AISecurityViolationError


@dataclass
class ConversationSession:
    conversation_id: str
    id_empresa: int
    id_usuario: Optional[int]
    alcance: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: List[Dict[str, str]] = field(default_factory=list)
    slots: Dict[str, Any] = field(default_factory=dict)
    last_products: List[Dict[str, Any]] = field(default_factory=list)
    last_tool_name: Optional[str] = None
    last_tool_args: Dict[str, Any] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class ContextManager:
    _SESSIONS: Dict[str, ConversationSession] = {}
    _GLOBAL_LOCK = threading.RLock()
    _MAX_SESSIONS = 1500
    _SESSION_TTL_SECONDS = 3600 * 4  # 4 horas

    @classmethod
    def get_or_create_session(
        cls,
        ctx: AssistantSecurityContext,
        conversation_id: Optional[str] = None,
        client_history: Optional[List[Dict[str, Any]]] = None
    ) -> ConversationSession:
        sanitized_history = validate_and_sanitize_history(client_history)

        with cls._GLOBAL_LOCK:
            cls._cleanup_expired_unlocked()

            if conversation_id and conversation_id.strip():
                cid = conversation_id.strip()
                existing = cls._SESSIONS.get(cid)
                if existing is not None:
                    # Verificar aislamiento estricto de memoria: mismo tenant y mismo usuario
                    if existing.id_empresa != ctx.id_empresa:
                        raise AISecurityViolationError(
                            "Violación de aislamiento de memoria: La conversación pertenece a otra empresa.",
                            status_code=403,
                            code="MEMORY_TENANT_MISMATCH"
                        )
                    if existing.id_usuario != ctx.id_usuario:
                        raise AISecurityViolationError(
                            "Violación de aislamiento de memoria: No puede reutilizar la conversación de otro usuario.",
                            status_code=403,
                            code="MEMORY_USER_MISMATCH"
                        )
                    if existing.alcance != ctx.alcance:
                        raise AISecurityViolationError(
                            "Violación de aislamiento de memoria: Cambio de alcance no autorizado en la conversación.",
                            status_code=403,
                            code="MEMORY_SCOPE_MISMATCH"
                        )
                    existing.updated_at = time.time()
                    if sanitized_history and not existing.messages:
                        existing.messages = list(sanitized_history)
                    return existing
            else:
                cid = f"conv_{ctx.id_empresa}_{ctx.id_usuario or 'anon'}_{uuid.uuid4().hex[:10]}"

            session = ConversationSession(
                conversation_id=cid,
                id_empresa=ctx.id_empresa,
                id_usuario=ctx.id_usuario,
                alcance=ctx.alcance,
                messages=list(sanitized_history)
            )
            cls._SESSIONS[cid] = session
            return session

    @classmethod
    def update_session_after_turn(
        cls,
        session: ConversationSession,
        user_message: str,
        assistant_response: str,
        extracted_slots: Optional[Dict[str, Any]] = None,
        products_shown: Optional[List[Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None
    ) -> None:
        with session.lock:
            session.updated_at = time.time()
            session.messages.append({"role": "user", "content": user_message[:2000]})
            session.messages.append({"role": "assistant", "content": assistant_response[:3000]})
            if len(session.messages) > 16:
                session.messages = session.messages[-16:]

            if extracted_slots:
                for k, v in extracted_slots.items():
                    if v is not None and v != "" and v != []:
                        session.slots[k] = v

            if products_shown and isinstance(products_shown, list):
                valid_prods = [p for p in products_shown if isinstance(p, dict) and ("id_producto" in p or "nombre" in p)]
                if valid_prods:
                    session.last_products = valid_prods[:12]

            if tool_name:
                session.last_tool_name = tool_name
            if tool_args and isinstance(tool_args, dict):
                session.last_tool_args = dict(tool_args)

    @classmethod
    def build_context_summary_for_prompt(cls, session: ConversationSession) -> str:
        """Construye un bloque compacto con la memoria de sesión activa para el LLM."""
        parts: List[str] = []
        if session.slots:
            slot_desc = []
            if session.slots.get("categoria"):
                slot_desc.append(f"categoría='{session.slots['categoria']}'")
            if session.slots.get("talla"):
                slot_desc.append(f"talla='{session.slots['talla']}'")
            if session.slots.get("colores"):
                slot_desc.append(f"colores preferidos={session.slots['colores']}")
            if session.slots.get("colores_excluidos"):
                slot_desc.append(f"colores excluidos={session.slots['colores_excluidos']}")
            if session.slots.get("presupuesto_max"):
                slot_desc.append(f"presupuesto máx=Bs. {session.slots['presupuesto_max']}")
            if session.slots.get("ocasion"):
                slot_desc.append(f"ocasión='{session.slots['ocasion']}'")
            if session.slots.get("sucursal"):
                slot_desc.append(f"sucursal='{session.slots['sucursal']}'")
            if slot_desc:
                parts.append("Preferencias recordadas en esta sesión: " + ", ".join(slot_desc) + ".")

        if session.last_products:
            prod_lines = []
            for idx, p in enumerate(session.last_products[:6], start=1):
                p_id = p.get("id_producto", "")
                p_nom = p.get("nombre") or p.get("producto") or "Prenda"
                p_prec = p.get("precio", 0)
                prod_lines.append(f"#{idx} [ID:{p_id}] {p_nom} (Bs. {p_prec})")
            parts.append("Últimas prendas mostradas al usuario: " + "; ".join(prod_lines) + ".")

        return "\n".join(parts)

    @classmethod
    def clear_all_sessions(cls) -> None:
        with cls._GLOBAL_LOCK:
            cls._SESSIONS.clear()

    @classmethod
    def _cleanup_expired_unlocked(cls) -> None:
        now = time.time()
        expired = [
            cid for cid, s in cls._SESSIONS.items()
            if (now - s.updated_at) > cls._SESSION_TTL_SECONDS
        ]
        for cid in expired:
            cls._SESSIONS.pop(cid, None)
        if len(cls._SESSIONS) > cls._MAX_SESSIONS:
            sorted_keys = sorted(cls._SESSIONS.keys(), key=lambda k: cls._SESSIONS[k].updated_at)
            for k in sorted_keys[: len(cls._SESSIONS) - cls._MAX_SESSIONS]:
                cls._SESSIONS.pop(k, None)
