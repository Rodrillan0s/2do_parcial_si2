"""
Configuración centralizada y agnóstica de proveedor para Aurora Advisor.
Permite cambiar entre DeepSeek, OpenAI, Gemini o cualquier proveedor compatible
mediante variables de entorno sin modificar la lógica de negocio ni las herramientas.
"""

import os
from dataclasses import dataclass
from typing import Optional
from app.core.config import Config


@dataclass
class AIConfig:
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com"
    timeout: int = 25
    max_tokens: int = 1500
    temperature: float = 0.3

    @classmethod
    def from_env(cls, override_provider: Optional[str] = None, override_model: Optional[str] = None) -> "AIConfig":
        provider = (override_provider or os.getenv("AI_PROVIDER") or getattr(Config, "AI_PROVIDER", "deepseek") or "deepseek").strip().lower()

        if provider == "openai":
            default_model = "gpt-4o-mini"
            default_url = os.getenv("OPENAI_BASE_URL") or getattr(Config, "OPENAI_BASE_URL", "https://api.openai.com/v1")
            api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or getattr(Config, "OPENAI_API_KEY", None)
        elif provider == "gemini":
            default_model = "gemini-2.0-flash"
            default_url = os.getenv("GEMINI_BASE_URL") or getattr(Config, "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
            api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY") or getattr(Config, "GEMINI_API_KEY", None)
        else:
            provider = "deepseek"
            default_model = os.getenv("DEEPSEEK_MODEL") or getattr(Config, "DEEPSEEK_MODEL", "deepseek-chat")
            default_url = os.getenv("DEEPSEEK_BASE_URL") or getattr(Config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            api_key = os.getenv("AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or getattr(Config, "DEEPSEEK_API_KEY", None)

        raw_model = (override_model or os.getenv("AI_MODEL") or default_model).strip()
        if provider == "deepseek":
            low_m = raw_model.lower()
            if low_m in ("deepseek-v3", "v3", "chat", "deepseek-chat"):
                model = "deepseek-chat"
            elif low_m in ("deepseek-r1", "r1", "reasoner", "deepseek-reasoner"):
                model = "deepseek-reasoner"
            else:
                model = raw_model
        else:
            model = raw_model
        base_url = (os.getenv("AI_BASE_URL") or default_url).strip().rstrip("/")

        try:
            timeout = int(os.getenv("AI_TIMEOUT") or getattr(Config, "AI_TIMEOUT", 25))
        except (ValueError, TypeError):
            timeout = 25

        try:
            max_tokens = int(os.getenv("AI_MAX_TOKENS") or getattr(Config, "AI_MAX_TOKENS", 1500))
        except (ValueError, TypeError):
            max_tokens = 1500

        try:
            temperature = float(os.getenv("AI_TEMPERATURE") or getattr(Config, "AI_TEMPERATURE", 0.3))
        except (ValueError, TypeError):
            temperature = 0.3

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=max(5, min(timeout, 120)),
            max_tokens=max(128, min(max_tokens, 8000)),
            temperature=max(0.0, min(temperature, 1.5))
        )

    def has_valid_api_key(self) -> bool:
        if not self.api_key:
            return False
        cleaned = self.api_key.strip().lower()
        if not cleaned or "your_" in cleaned or cleaned in ("none", "null", "placeholder", "sk-xxx"):
            return False
        return True

    def has_valid_key(self) -> bool:
        return self.has_valid_api_key()

