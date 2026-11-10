"""
Adaptador para OpenAI (gpt-4o, gpt-4o-mini y proveedores compatibles con OpenAI API)
bajo el contrato común BaseAIProvider.
"""

import json
import time
import requests
from typing import List, Dict, Any
from app.modules.ia.ai.core.ai_provider import BaseAIProvider
from app.modules.ia.ai.core.ai_request import AIRequest
from app.modules.ia.ai.core.ai_response import AIResponse, AIToolCall, AITokenUsage
from app.modules.ia.ai.exceptions.ai_exceptions import (
    AIProviderUnavailableError,
    AITimeoutError,
    AIAuthenticationError,
    AIInvalidResponseError
)


class OpenAIAdapter(BaseAIProvider):
    def complete(self, request: AIRequest) -> AIResponse:
        if not self.is_configured():
            raise AIProviderUnavailableError("OpenAI API Key no configurada.", provider="openai", code="NO_API_KEY")

        t0 = time.perf_counter()
        messages_payload: List[Dict[str, Any]] = []

        sys_prompt = request.system_prompt or ""
        use_native_tools = bool(request.tools and self.capabilities.supports_function_calling)

        if request.tools and not self.capabilities.supports_function_calling:
            sys_prompt += self.build_structured_tool_prompt(request.tools)

        if sys_prompt:
            messages_payload.append({"role": "system", "content": sys_prompt})

        for msg in request.messages:
            if msg.role == "system" and sys_prompt:
                continue
            messages_payload.append(msg.to_openai_dict())

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages_payload,
            "max_tokens": request.max_tokens or self.config.max_tokens
        }

        if self.capabilities.supports_temperature:
            payload["temperature"] = request.temperature if request.temperature is not None else self.config.temperature

        if use_native_tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = request.tool_choice or "auto"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        base = self.config.base_url.rstrip("/")
        endpoint = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
        timeout_sec = request.timeout or self.config.timeout

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_sec)
        except requests.Timeout as e:
            raise AITimeoutError(f"Timeout al consultar OpenAI ({timeout_sec}s): {e}", provider="openai")
        except requests.RequestException as e:
            raise AIProviderUnavailableError(f"Error de red al conectar con OpenAI: {e}", provider="openai")

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        if resp.status_code in (401, 403):
            raise AIAuthenticationError(f"Error de autenticación en OpenAI ({resp.status_code}).", provider="openai")
        if resp.status_code >= 500 or resp.status_code == 429:
            raise AIProviderUnavailableError(f"OpenAI no disponible temporalmente (HTTP {resp.status_code}).", provider="openai")
        if resp.status_code != 200:
            raise AIProviderUnavailableError(f"Respuesta inesperada de OpenAI (HTTP {resp.status_code}).", provider="openai")

        try:
            data = resp.json()
            choice_obj = data["choices"][0]
            message_obj = choice_obj["message"]
        except Exception as e:
            raise AIInvalidResponseError(f"Respuesta JSON inválida de OpenAI: {e}", provider="openai")

        content_text = message_obj.get("content") or ""
        finish_reason = choice_obj.get("finish_reason") or "stop"

        parsed_tool_calls: List[AIToolCall] = []
        raw_tool_calls = message_obj.get("tool_calls") or []
        for idx, tc in enumerate(raw_tool_calls):
            fn = tc.get("function") or {}
            fn_name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args) if raw_args.strip() else {}
                except Exception:
                    raise AIInvalidResponseError(f"Argumentos JSON inválidos en tool_call '{fn_name}'.", provider="openai")
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                parsed_args = {}

            if fn_name:
                parsed_tool_calls.append(AIToolCall(
                    id=tc.get("id") or f"call_oa_{idx + 1}",
                    name=fn_name,
                    arguments=parsed_args
                ))

        if not parsed_tool_calls and request.tools and not self.capabilities.supports_function_calling:
            struct_calls = self.parse_structured_tool_calls_from_text(content_text)
            if struct_calls:
                parsed_tool_calls = struct_calls
                content_text = ""

        usage_raw = data.get("usage") or {}
        p_tok = int(usage_raw.get("prompt_tokens") or 0)
        c_tok = int(usage_raw.get("completion_tokens") or 0)
        t_tok = int(usage_raw.get("total_tokens") or (p_tok + c_tok))

        usage = AITokenUsage(
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=t_tok,
            estimated_cost_usd=self.calculate_cost(p_tok, c_tok)
        )

        return AIResponse(
            content=content_text,
            tool_calls=parsed_tool_calls,
            provider="openai",
            model=data.get("model") or self.config.model,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=finish_reason
        )
