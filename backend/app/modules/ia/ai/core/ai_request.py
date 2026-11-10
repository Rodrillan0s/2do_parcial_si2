"""
Modelos comunes de solicitud (AIRequest) para la capa de abstracción de IA.
El orquestador construye objetos AIRequest agnósticos del proveedor.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class AIMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    raw_tool_calls: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        if self.raw_tool_calls and not self.tool_calls:
            self.tool_calls = self.raw_tool_calls

    def to_openai_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "role": self.role,
            "content": self.content or ""
        }
        if self.name:
            payload["name"] = self.name
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            payload["tool_calls"] = self.tool_calls
        return payload


@dataclass
class AIRequest:
    messages: List[AIMessage]
    system_prompt: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: str = "auto"
    temperature: float = 0.3
    max_tokens: int = 1500
    timeout: int = 25
    metadata: Dict[str, Any] = field(default_factory=dict)
