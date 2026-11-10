"""
Enrutador de modelos y proveedores de IA (ModelRouter) con Circuit Breaker integrado.
Permite cambiar entre DeepSeek, OpenAI, Gemini o adaptadores registrados dinámicamente
según la configuración o la complejidad de la solicitud.
"""

import time
import threading
from typing import Dict, Type, Optional
from app.modules.ia.ai.configuration.ai_config import AIConfig
from app.modules.ia.ai.core.ai_provider import BaseAIProvider
from app.modules.ia.ai.core.ai_request import AIRequest
from app.modules.ia.ai.core.ai_response import AIResponse
from app.modules.ia.ai.adapters.deepseek_adapter import DeepSeekAdapter
from app.modules.ia.ai.adapters.openai_adapter import OpenAIAdapter
from app.modules.ia.ai.adapters.gemini_adapter import GeminiAdapter
from app.modules.ia.ai.exceptions.ai_exceptions import AIProviderUnavailableError


class CircuitBreakerState:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0.0
        self.lock = threading.Lock()

    def allow_request(self) -> bool:
        with self.lock:
            if self.failures < self.failure_threshold:
                return True
            if (time.monotonic() - self.last_failure_time) >= self.recovery_timeout:
                return True
            return False

    def record_success(self) -> None:
        with self.lock:
            self.failures = 0

    def record_failure(self) -> None:
        with self.lock:
            self.failures += 1
            self.last_failure_time = time.monotonic()

    def reset(self) -> None:
        with self.lock:
            self.failures = 0
            self.last_failure_time = 0.0


class ModelRouter:
    _ADAPTERS: Dict[str, Type[BaseAIProvider]] = {
        "deepseek": DeepSeekAdapter,
        "openai": OpenAIAdapter,
        "gemini": GeminiAdapter
    }
    _CIRCUITS: Dict[str, CircuitBreakerState] = {}
    _CUSTOM_INSTANCES: Dict[str, BaseAIProvider] = {}

    def __init__(self, config: Optional[AIConfig] = None):
        self.config: AIConfig = config or AIConfig.from_env()
        self._local_instances: Dict[str, BaseAIProvider] = {}

    def register_provider_instance(self, provider_name: str, instance: BaseAIProvider) -> None:
        self._local_instances[provider_name.strip().lower()] = instance

    @classmethod
    def register_adapter(cls, provider_name: str, adapter_cls: Type[BaseAIProvider]) -> None:
        cls._ADAPTERS[provider_name.strip().lower()] = adapter_cls

    @classmethod
    def register_instance(cls, provider_name: str, instance: BaseAIProvider) -> None:
        cls._CUSTOM_INSTANCES[provider_name.strip().lower()] = instance

    @classmethod
    def clear_custom_instances(cls) -> None:
        cls._CUSTOM_INSTANCES.clear()
        for c in cls._CIRCUITS.values():
            c.reset()

    def get_active_provider(
        self,
        override_provider: Optional[str] = None,
        override_model: Optional[str] = None,
    ) -> BaseAIProvider:
        prov_key = (override_provider or self.config.provider).strip().lower()
        if prov_key in self._local_instances:
            return self._local_instances[prov_key]
        if prov_key in self._CUSTOM_INSTANCES:
            return self._CUSTOM_INSTANCES[prov_key]
        cfg = self.config if not (override_provider or override_model) else AIConfig.from_env(
            override_provider=override_provider,
            override_model=override_model,
        )
        adapter_cls = self._ADAPTERS.get(prov_key, DeepSeekAdapter)
        return adapter_cls(cfg)

    @classmethod
    def get_provider(
        cls,
        override_provider: Optional[str] = None,
        override_model: Optional[str] = None,
        task_complexity: str = "contextual_chat"
    ) -> BaseAIProvider:
        config = AIConfig.from_env(override_provider=override_provider, override_model=override_model)
        provider_key = config.provider.lower()

        if provider_key in cls._CUSTOM_INSTANCES:
            return cls._CUSTOM_INSTANCES[provider_key]

        adapter_cls = cls._ADAPTERS.get(provider_key, DeepSeekAdapter)
        return adapter_cls(config)

    def execute(
        self,
        request: AIRequest,
        override_provider: Optional[str] = None,
        override_model: Optional[str] = None,
        task_complexity: str = "contextual_chat"
    ) -> AIResponse:
        provider = self.get_active_provider(
            override_provider=override_provider,
            override_model=override_model,
        )
        p_name = provider.config.provider

        if p_name not in self._CIRCUITS:
            self._CIRCUITS[p_name] = CircuitBreakerState()
        circuit = self._CIRCUITS[p_name]

        if not circuit.allow_request():
            raise AIProviderUnavailableError(
                f"Circuit breaker activo para el proveedor '{p_name}'.",
                provider=p_name,
                code="CIRCUIT_OPEN"
            )

        try:
            response = provider.execute(request)
            circuit.record_success()
            return response
        except AIProviderUnavailableError:
            circuit.record_failure()
            raise
