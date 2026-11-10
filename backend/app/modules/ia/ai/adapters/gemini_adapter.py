"""
Adaptador para Google Gemini (gemini-2.0-flash, gemini-1.5-pro) bajo el contrato común BaseAIProvider.
Traduce automáticamente mensajes, systemInstruction y functionDeclarations al protocolo de Gemini
y normaliza la respuesta hacia AIResponse.
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


class GeminiAdapter(BaseAIProvider):
    def complete(self, request: AIRequest) -> AIResponse:
        if not self.is_configured():
            raise AIProviderUnavailableError("Gemini API Key no configurada.", provider="gemini", code="NO_API_KEY")

        t0 = time.perf_counter()

        contents: List[Dict[str, Any]] = []
        for msg in request.messages:
            if msg.role == "system":
                continue
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content or ""}]})
            elif msg.role == "assistant":
                parts: List[Dict[str, Any]] = []
                if msg.content:
                    parts.append({"text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        fn = tc.get("function") or {}
                        raw_args = fn.get("arguments") or "{}"
                        try:
                            args_dict = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            args_dict = {}
                        parts.append({
                            "functionCall": {
                                "name": fn.get("name", ""),
                                "args": args_dict
                            }
                        })
                if parts:
                    contents.append({"role": "model", "parts": parts})
            elif msg.role == "tool":
                try:
                    resp_obj = json.loads(msg.content) if msg.content else {}
                except Exception:
                    resp_obj = {"result": msg.content or ""}
                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.name or "tool_result",
                            "response": resp_obj if isinstance(resp_obj, dict) else {"data": resp_obj}
                        }
                    }]
                })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature if request.temperature is not None else self.config.temperature,
                "maxOutputTokens": request.max_tokens or self.config.max_tokens
            }
        }

        if request.system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_prompt}]
            }

        if request.tools and self.capabilities.supports_function_calling:
            declarations = []
            for t in request.tools:
                fn = t.get("function") or {}
                if fn.get("name"):
                    declarations.append({
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "parameters": fn.get("parameters", {"type": "object", "properties": {}})
                    })
            if declarations:
                payload["tools"] = [{"functionDeclarations": declarations}]

        base = self.config.base_url.rstrip("/")
        endpoint = f"{base}/models/{self.config.model}:generateContent?key={self.config.api_key}"
        timeout_sec = request.timeout or self.config.timeout

        try:
            resp = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=timeout_sec
            )
        except requests.Timeout as e:
            raise AITimeoutError(f"Timeout al consultar Gemini ({timeout_sec}s): {e}", provider="gemini")
        except requests.RequestException as e:
            raise AIProviderUnavailableError(f"Error de red al conectar con Gemini: {e}", provider="gemini")

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        if resp.status_code in (401, 403):
            raise AIAuthenticationError(f"Error de autenticación en Gemini ({resp.status_code}).", provider="gemini")
        if resp.status_code >= 500 or resp.status_code == 429:
            raise AIProviderUnavailableError(f"Gemini no disponible temporalmente (HTTP {resp.status_code}).", provider="gemini")
        if resp.status_code != 200:
            raise AIProviderUnavailableError(f"Respuesta inesperada de Gemini (HTTP {resp.status_code}).", provider="gemini")

        try:
            data = resp.json()
            candidate = (data.get("candidates") or [{}])[0]
            parts = (candidate.get("content") or {}).get("parts") or []
        except Exception as e:
            raise AIInvalidResponseError(f"Respuesta JSON inválida de Gemini: {e}", provider="gemini")

        text_chunks: List[str] = []
        parsed_tool_calls: List[AIToolCall] = []

        for idx, part in enumerate(parts):
            if "text" in part and part["text"]:
                text_chunks.append(str(part["text"]))
            if "functionCall" in part and isinstance(part["functionCall"], dict):
                fc = part["functionCall"]
                fn_name = fc.get("name") or ""
                fn_args = fc.get("args")
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        raise AIInvalidResponseError(f"Argumentos inválidos en functionCall '{fn_name}'.", provider="gemini")
                elif not isinstance(fn_args, dict):
                    fn_args = {}
                if fn_name:
                    parsed_tool_calls.append(AIToolCall(
                        id=f"call_gem_{idx + 1}",
                        name=fn_name,
                        arguments=fn_args
                    ))

        usage_meta = data.get("usageMetadata") or {}
        p_tok = int(usage_meta.get("promptTokenCount") or 0)
        c_tok = int(usage_meta.get("candidatesTokenCount") or 0)
        t_tok = int(usage_meta.get("totalTokenCount") or (p_tok + c_tok))

        usage = AITokenUsage(
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=t_tok,
            estimated_cost_usd=self.calculate_cost(p_tok, c_tok)
        )

        return AIResponse(
            content="\n".join(text_chunks).strip(),
            tool_calls=parsed_tool_calls,
            provider="gemini",
            model=self.config.model,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=str(candidate.get("finishReason") or "STOP").lower()
        )
