from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from app.core.security import verificar_token_opcional, verificar_token
from app.modules.ia.services import asistente_services
from app.modules.ia.ai.exceptions.ai_exceptions import (
    AIPromptInjectionError,
    AISecurityViolationError,
    AIRateLimitExceededError,
    AIDatabaseError,
)
from app.modules.ia.orchestrator.observability import GLOBAL_OBSERVABILITY_TRACKER
from app.modules.ia.ai.configuration.ai_config import AIConfig
from app.modules.ia.ai.core.ai_capabilities import get_model_capabilities, MODEL_REGISTRY

router = APIRouter(prefix="/api/asistente", tags=["Asistente Inteligente Aurora Advisor (W13 / Iter 2-3)"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="Rol del emisor: 'user' o 'assistant'")
    content: str = Field(..., description="Texto del mensaje")


class ChatRequest(BaseModel):
    mensaje: str = Field(..., min_length=1, max_length=2000, description="Mensaje o comando del usuario")
    historial: Optional[List[ChatMessage]] = Field(default=[], description="Historial reciente de la sesión")
    conversation_id: Optional[str] = Field(default=None, description="ID de sesión conversacional")
    slug_tienda: Optional[str] = Field(default=None, description="Slug de tienda pública si el usuario es visitante")
    id_empresa: Optional[int] = Field(default=None, description="ID de empresa solicitado (solo válido para SuperAdmin o verificado contra el token)")
    modelo: Optional[str] = Field(default=None, description="Variante de modelo DeepSeek seleccionada ('deepseek-chat' o 'deepseek-reasoner')")


@router.post("/chat", summary="Conversar con Aurora Advisor (Orquestador Multi-Proveedor + RBAC + Memoria)")
def chat_asistente(
    request: ChatRequest,
    http_request: Request,
    token_data: Optional[dict] = Depends(verificar_token_opcional),
):
    """
    Orquesta consultas conversacionales en lenguaje natural complejo, multi-intención y contextual.
    Aplica aislamiento multitenant estricto desde PostgreSQL, control RBAC por herramienta,
    protección contra Prompt Injection y fallback inteligente cuando el proveedor externo no está disponible.
    """
    try:
        client_host = http_request.client.host if http_request and http_request.client else "local"
        user_id = (token_data or {}).get("id_usuario") or (token_data or {}).get("sub") or client_host
        empresa_id = (token_data or {}).get("id_empresa") or request.id_empresa or 1
        rate_limit_key = f"{empresa_id}:{user_id}"

        historial_dicts = [h.model_dump() for h in (request.historial or [])]
        resultado = asistente_services.procesar_mensaje_chat(
            mensaje=request.mensaje,
            historial=historial_dicts,
            token_data=token_data,
            conversation_id=request.conversation_id,
            slug_tienda=request.slug_tienda,
            id_empresa_solicitado=request.id_empresa,
            rate_limit_key=rate_limit_key,
            modelo=request.modelo,
        )
        return resultado

    except AIPromptInjectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "code": e.code,
                "respuesta": e.message,
                "mensaje": e.message,
                "tipo": "error",
            },
        )
    except AISecurityViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "code": e.code,
                "respuesta": e.message,
                "mensaje": e.message,
                "tipo": "error",
            },
        )
    except AIRateLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "success": False,
                "code": e.code,
                "respuesta": e.message,
                "mensaje": e.message,
                "tipo": "error",
            },
        )
    except AIDatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "code": e.code,
                "respuesta": e.message,
                "mensaje": e.message,
                "tipo": "error",
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "code": "INVALID_REQUEST",
                "respuesta": str(e),
                "mensaje": str(e),
                "tipo": "error",
            },
        )
    except Exception as e:
        return {
            "success": False,
            "conversation_id": request.conversation_id or "error",
            "mensaje": "El asistente no está disponible temporalmente. Las demás funciones de Aurora Store continúan funcionando normalmente.",
            "respuesta": "El asistente no está disponible temporalmente. Las demás funciones de Aurora Store continúan funcionando normalmente.",
            "tipo": "texto",
            "datos": None,
            "herramientas_usadas": [],
            "error": str(e),
        }


@router.get("/metricas", summary="Obtener métricas de observabilidad y costos de Aurora Advisor")
def obtener_metricas_asistente(token_data: dict = Depends(verificar_token)):
    """
    Devuelve métricas agregadas de latencia, tokens, costos estimados, uso de herramientas y tasa de fallback.
    Restringido a personal administrativo para su propio tenant (o global para SuperAdmin).
    """
    roles = [str(r).upper() for r in (token_data.get("roles") or [])]
    alcance = str(token_data.get("alcance") or "").upper()
    id_rol = token_data.get("id_rol")
    if id_rol not in (1, 3, 4) and not any(
        r in roles for r in ("ADMINISTRADOR", "ADMINISTRADOR_TIENDA", "ENCARGADO")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el personal administrativo puede consultar métricas de observabilidad de IA.",
        )

    id_empresa = None if alcance == "PLATAFORMA" else (token_data.get("id_empresa") or 1)
    return {
        "success": True,
        "metricas": GLOBAL_OBSERVABILITY_TRACKER.get_summary(id_empresa=id_empresa),
    }


@router.get("/capacidades", summary="Consultar configuración activa y capacidades de modelos soportados")
def obtener_capacidades_ia():
    """
    Informa el proveedor y modelo configurados actualmente (sin exponer API keys)
    junto con las capacidades técnicas registradas en el ModelRouter.
    """
    cfg = AIConfig.from_env()
    caps = get_model_capabilities(cfg.provider, cfg.model)
    return {
        "success": True,
        "proveedor_activo": cfg.provider,
        "modelo_activo": cfg.model,
        "api_key_configurada": cfg.has_valid_key(),
        "capacidades_activas": {
            "supports_function_calling": caps.supports_function_calling,
            "supports_structured_json": caps.supports_structured_json,
            "supports_streaming": caps.supports_streaming,
            "max_context_tokens": caps.max_context_tokens,
        },
        "modelos_soportados": ["deepseek-chat", "deepseek-reasoner"],
        "variantes_deepseek": [
            {
                "id": "deepseek-chat",
                "nombre": "DeepSeek Chat (V3)",
                "descripcion": "Conversacional rápido con Function Calling nativo",
            },
            {
                "id": "deepseek-reasoner",
                "nombre": "DeepSeek Reasoner (R1)",
                "descripcion": "Razonamiento profundo y análisis comercial",
            },
        ],
    }
