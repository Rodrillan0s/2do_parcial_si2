"""
Adaptador para DeepSeek (deepseek-chat, deepseek-reasoner) bajo el contrato común BaseAIProvider.
"""

import json
import time
import logging
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

logger = logging.getLogger(__name__)


class DeepSeekAdapter(BaseAIProvider):
    def complete(self, request: AIRequest) -> AIResponse:
        if not self.is_configured():
            raise AIProviderUnavailableError("DeepSeek API Key no configurada.", provider="deepseek", code="NO_API_KEY")

        t0 = time.perf_counter()
        messages_payload: List[Dict[str, Any]] = []

        existing_sys_parts: List[str] = []
        if request.system_prompt:
            existing_sys_parts.append(request.system_prompt)
        for msg in request.messages:
            if msg.role == "system" and msg.content:
                existing_sys_parts.append(msg.content)

        sys_prompt = "\n\n".join(existing_sys_parts)
        use_native_tools = bool(request.tools and self.capabilities.supports_function_calling)

        if request.tools and not self.capabilities.supports_function_calling:
            sys_prompt = (sys_prompt + "\n\n" + self.build_structured_tool_prompt(request.tools)).strip()

        if sys_prompt:
            if self.capabilities.supports_system_prompt:
                messages_payload.append({"role": "system", "content": sys_prompt})
            else:
                messages_payload.append({"role": "user", "content": f"[INSTRUCCIONES DE SISTEMA]\n{sys_prompt}"})

        for msg in request.messages:
            if msg.role == "system":
                continue
            if not use_native_tools:
                # Modelos como deepseek-reasoner no aceptan role="tool" ni tool_calls en el historial
                if msg.role == "tool":
                    messages_payload.append({
                        "role": "user",
                        "content": f"[RESULTADO DE HERRAMIENTA {msg.name or 'sistema'}]:\n{msg.content}\n\nCon base en estos datos reales de Aurora Store, redacta la respuesta final para el usuario en español (sin bloques JSON de tool_calls)."
                    })
                    continue
                if msg.role == "assistant" and msg.tool_calls:
                    tc_summary = json.dumps(msg.tool_calls, ensure_ascii=False)
                    messages_payload.append({
                        "role": "assistant",
                        "content": msg.content or f"Consultando herramientas del sistema: {tc_summary}"
                    })
                    continue
            messages_payload.append(msg.to_openai_dict())

        # DeepSeek Reasoner requiere que los mensajes user/assistant alternen y que el último sea user
        if not use_native_tools and len(messages_payload) > 1:
            normalized_msgs: List[Dict[str, Any]] = []
            for m in messages_payload:
                if normalized_msgs and m["role"] == normalized_msgs[-1]["role"] and m["role"] in ("user", "assistant"):
                    normalized_msgs[-1]["content"] = f"{normalized_msgs[-1]['content']}\n\n{m['content']}"
                else:
                    normalized_msgs.append(m)
            messages_payload = normalized_msgs

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

        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
        timeout_sec = request.timeout or self.config.timeout
        if "reasoner" in (self.config.model or "").lower() or "r1" in (self.config.model or "").lower():
            timeout_sec = max(timeout_sec, 45)

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_sec)
        except requests.Timeout as e:
            raise AITimeoutError(f"Timeout al consultar DeepSeek ({timeout_sec}s): {e}", provider="deepseek")
        except requests.RequestException as e:
            raise AIProviderUnavailableError(f"Error de red al conectar con DeepSeek: {e}", provider="deepseek")

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        if resp.status_code in (401, 403):
            raise AIAuthenticationError(f"Error de autenticación en DeepSeek ({resp.status_code}).", provider="deepseek")
        if resp.status_code >= 500 or resp.status_code == 429:
            raise AIProviderUnavailableError(f"DeepSeek no disponible temporalmente (HTTP {resp.status_code}).", provider="deepseek")
        if resp.status_code != 200:
            raise AIProviderUnavailableError(f"Respuesta inesperada de DeepSeek (HTTP {resp.status_code}).", provider="deepseek")

        try:
            data = resp.json()
            choice_obj = data["choices"][0]
            message_obj = choice_obj["message"]
        except Exception as e:
            raise AIInvalidResponseError(f"Respuesta JSON inválida de DeepSeek: {e}", provider="deepseek")

        content_text = message_obj.get("content") or ""
        reasoning_text = message_obj.get("reasoning_content") or ""
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
                    raise AIInvalidResponseError(f"Argumentos JSON inválidos en tool_call '{fn_name}'.", provider="deepseek")
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                parsed_args = {}

            if fn_name:
                parsed_tool_calls.append(AIToolCall(
                    id=tc.get("id") or f"call_ds_{idx + 1}",
                    name=fn_name,
                    arguments=parsed_args
                ))

        # Si el modelo no soporta Function Calling nativo pero devolvió JSON estructurado de herramientas
        if not parsed_tool_calls and request.tools and not self.capabilities.supports_function_calling:
            struct_calls = self.parse_structured_tool_calls_from_text(content_text or reasoning_text)
            if struct_calls:
                parsed_tool_calls = struct_calls
                content_text = ""

        if not content_text and not parsed_tool_calls and reasoning_text:
            content_text = reasoning_text

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
            provider="deepseek",
            model=self.config.model or data.get("model") or "deepseek-chat",
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=finish_reason
        )
