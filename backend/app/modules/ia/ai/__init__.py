"""Capa agnóstica de proveedores y modelos de IA para Aurora Advisor."""
from app.modules.ia.ai.configuration.ai_config import AIConfig
from app.modules.ia.ai.core.ai_capabilities import ModelCapabilities, resolve_model_capabilities
from app.modules.ia.ai.core.ai_request import AIRequest, AIMessage
from app.modules.ia.ai.core.ai_response import AIResponse, AIToolCall, AITokenUsage
from app.modules.ia.ai.core.ai_provider import BaseAIProvider
from app.modules.ia.ai.core.model_router import ModelRouter

__all__ = [
    "AIConfig",
    "ModelCapabilities",
    "resolve_model_capabilities",
    "AIRequest",
    "AIMessage",
    "AIResponse",
    "AIToolCall",
    "AITokenUsage",
    "BaseAIProvider",
    "ModelRouter",
]
