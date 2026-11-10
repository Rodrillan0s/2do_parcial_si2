"""
Contrato común de respuesta (AIResponse) para cualquier proveedor de IA (DeepSeek, OpenAI, Gemini, etc.).
El orquestador recibe esta estructura normalizada sin depender del formato nativo del proveedor.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class AIToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_openai_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False)
            }
        }


@dataclass
class AITokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class AIResponse:
    content: str = ""
    tool_calls: List[AIToolCall] = field(default_factory=list)
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    usage: AITokenUsage = field(default_factory=AITokenUsage)
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
