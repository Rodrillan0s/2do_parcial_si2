"""
Descripción formal de capacidades de cada modelo y proveedor de IA.
Permite al orquestador saber si el modelo soporta Function Calling nativo, JSON estructurado,
temperatura o mensajes de sistema, adaptando la petición automáticamente.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModelCapabilities:
    provider: str
    model: str
    supports_function_calling: bool = True
    supports_parallel_tool_calls: bool = True
    supports_structured_json: bool = True
    supports_system_prompt: bool = True
    supports_temperature: bool = True
    supports_streaming: bool = True
    supports_vision: bool = False
    max_context_tokens: int = 64000
    input_cost_per_1k_usd: float = 0.00014
    output_cost_per_1k_usd: float = 0.00028

    @property
    def cost_per_1k_input_usd(self) -> float:
        return self.input_cost_per_1k_usd

    @property
    def cost_per_1k_output_usd(self) -> float:
        return self.output_cost_per_1k_usd


MODEL_CAPABILITY_REGISTRY: Dict[str, ModelCapabilities] = {
    "deepseek-chat": ModelCapabilities(
        provider="deepseek",
        model="deepseek-chat",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=True,
        supports_streaming=True,
        supports_vision=False,
        max_context_tokens=64000,
        input_cost_per_1k_usd=0.00014,
        output_cost_per_1k_usd=0.00028
    ),
    "deepseek-reasoner": ModelCapabilities(
        provider="deepseek",
        model="deepseek-reasoner",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=False,
        supports_streaming=True,
        supports_vision=False,
        max_context_tokens=64000,
        input_cost_per_1k_usd=0.00055,
        output_cost_per_1k_usd=0.00219
    ),
    "deepseek-v3": ModelCapabilities(
        provider="deepseek",
        model="deepseek-chat",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=True,
        supports_streaming=True,
        supports_vision=False,
        max_context_tokens=64000,
        input_cost_per_1k_usd=0.00014,
        output_cost_per_1k_usd=0.00028
    ),
    "deepseek-r1": ModelCapabilities(
        provider="deepseek",
        model="deepseek-reasoner",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=False,
        supports_streaming=True,
        supports_vision=False,
        max_context_tokens=64000,
        input_cost_per_1k_usd=0.00055,
        output_cost_per_1k_usd=0.00219
    ),
    "gpt-4o": ModelCapabilities(
        provider="openai",
        model="gpt-4o",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=128000,
        input_cost_per_1k_usd=0.0025,
        output_cost_per_1k_usd=0.0100
    ),
    "gpt-4o-mini": ModelCapabilities(
        provider="openai",
        model="gpt-4o-mini",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=128000,
        input_cost_per_1k_usd=0.00015,
        output_cost_per_1k_usd=0.00060
    ),
    "gemini-2.0-flash": ModelCapabilities(
        provider="gemini",
        model="gemini-2.0-flash",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=1000000,
        input_cost_per_1k_usd=0.00010,
        output_cost_per_1k_usd=0.00040
    ),
    "gemini-1.5-pro": ModelCapabilities(
        provider="gemini",
        model="gemini-1.5-pro",
        supports_function_calling=True,
        supports_parallel_tool_calls=True,
        supports_structured_json=True,
        supports_system_prompt=True,
        supports_temperature=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=1000000,
        input_cost_per_1k_usd=0.00125,
        output_cost_per_1k_usd=0.00500
    ),
}


def resolve_model_capabilities(provider: str, model: str) -> ModelCapabilities:
    key = (model or "").strip().lower()
    if key in MODEL_CAPABILITY_REGISTRY:
        return MODEL_CAPABILITY_REGISTRY[key]

    prov = (provider or "deepseek").strip().lower()
    if prov == "gemini":
        return ModelCapabilities(provider="gemini", model=model, supports_vision=True, max_context_tokens=1000000)
    if prov == "openai":
        supports_temp = not key.startswith(("o1", "o3"))
        supports_fc = not key.startswith("o1-mini")
        return ModelCapabilities(
            provider="openai",
            model=model,
            supports_function_calling=supports_fc,
            supports_temperature=supports_temp,
            max_context_tokens=128000
        )
    return ModelCapabilities(provider=prov, model=model)


get_model_capabilities = resolve_model_capabilities
MODEL_REGISTRY = MODEL_CAPABILITY_REGISTRY

