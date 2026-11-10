"""
Interfaz abstracta común (BaseAIProvider) para adaptadores de proveedores de IA.
Incluye soporte de selección estructurada de herramientas para modelos que no admiten
Function Calling nativo, validado siempre por el backend.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.modules.ia.ai.configuration.ai_config import AIConfig
from app.modules.ia.ai.core.ai_capabilities import ModelCapabilities, resolve_model_capabilities
from app.modules.ia.ai.core.ai_request import AIRequest, AIMessage
from app.modules.ia.ai.core.ai_response import AIResponse, AIToolCall, AITokenUsage


class BaseAIProvider(ABC):
    def __init__(self, config: AIConfig):
        self.config = config
        self.capabilities: ModelCapabilities = resolve_model_capabilities(config.provider, config.model)

    @property
    def provider_name(self) -> str:
        return self.config.provider

    @property
    def model_name(self) -> str:
        return self.config.model

    def is_configured(self) -> bool:
        return self.config.has_valid_api_key()

    def get_capabilities(self) -> ModelCapabilities:
        return self.capabilities

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        in_cost = (prompt_tokens / 1000.0) * self.capabilities.input_cost_per_1k_usd
        out_cost = (completion_tokens / 1000.0) * self.capabilities.output_cost_per_1k_usd
        return round(in_cost + out_cost, 6)

    def complete(self, request: AIRequest) -> AIResponse:
        """Ejecuta una solicitud de completado o llamada a herramientas contra el proveedor."""
        if hasattr(self, "generate_response"):
            return getattr(self, "generate_response")(request)
        raise NotImplementedError

    def execute(self, request: AIRequest) -> AIResponse:
        """Ejecuta la solicitud y aplica parsing JSON de herramientas si la respuesta viene estructurada en texto."""
        resp = self.complete(request)
        if not resp.has_tool_calls and resp.content:
            parsed_calls = self.parse_structured_tool_calls_from_text(resp.content)
            if parsed_calls:
                resp.tool_calls = parsed_calls
        return resp

    @staticmethod
    def build_structured_tool_prompt(tools: List[Dict[str, Any]]) -> str:
        """
        Para modelos sin Function Calling nativo, inyecta el catálogo de herramientas
        y solicita un bloque JSON estricto si se requiere invocar herramientas.
        """
        if not tools:
            return ""
        compact_tools = []
        for t in tools:
            fn = t.get("function", {})
            compact_tools.append({
                "name": fn.get("name"),
                "description": fn.get("description"),
                "parameters": fn.get("parameters", {})
            })
        tools_json = json.dumps(compact_tools, ensure_ascii=False)
        return (
            "\n\n[MODO DE HERRAMIENTAS ESTRUCTURADAS]\n"
            f"Herramientas disponibles: {tools_json}\n"
            "Si necesitas consultar datos del sistema, responde ÚNICAMENTE con un bloque JSON con formato:\n"
            '{"tool_calls": [{"name": "nombre_herramienta", "arguments": {...}}]}\n'
            "De lo contrario, responde normalmente al usuario."
        )

    @staticmethod
    def parse_structured_tool_calls_from_text(text: str) -> Optional[List[AIToolCall]]:
        """Extrae llamadas de herramientas cuando un modelo sin Function Calling responde en JSON."""
        if not text or ("tool_calls" not in text and '"tool"' not in text):
            return None
        match = re.search(r'\{[\s\S]*("tool_calls"|"tool")[\s\S]*\}', text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and data.get("tool") and "tool_calls" not in data:
                raw_calls = [{"name": data.get("tool"), "arguments": data.get("arguments") or {}}]
            else:
                raw_calls = data.get("tool_calls")
            if not isinstance(raw_calls, list):
                return None
            calls: List[AIToolCall] = []
            for idx, rc in enumerate(raw_calls):
                if isinstance(rc, dict) and rc.get("name"):
                    args = rc.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    calls.append(AIToolCall(
                        id=f"call_struct_{idx + 1}",
                        name=str(rc["name"]),
                        arguments=args if isinstance(args, dict) else {}
                    ))
            return calls if calls else None
        except Exception:
            return None
