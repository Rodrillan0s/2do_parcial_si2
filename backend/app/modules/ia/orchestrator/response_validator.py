"""
Response Validator and Sanitizer for Aurora Advisor.
Guarantees structured output contracts, strips unsafe HTML/scripts/event handlers,
validates image URLs, and normalizes widget payloads before returning to Angular.
"""
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


SUPPORTED_RESPONSE_TYPES = {
    "texto",
    "productos",
    "tabla",
    "indicadores",
    "reporte",
    "comparacion",
    "grafico",
    "outfit",
    "alertas",
    "predicciones",
    "recomendaciones",
    "seguimiento_pedido",
    "error",
}


class AssistantMetadata(BaseModel):
    provider: str = "local"
    model: str = "heuristic"
    alcance: str = "PUBLIC"
    id_empresa: int = 1
    id_sucursal: Optional[int] = None
    latency_ms: float = 0.0
    used_fallback: bool = False
    intenciones_detectadas: List[str] = Field(default_factory=list)
    es_inicio_frio: Optional[bool] = None
    referencia_contextual: Optional[str] = None


class AssistantChatResponse(BaseModel):
    success: bool = True
    conversation_id: str
    mensaje: str
    respuesta: str  # Kept for 100% backward compatibility with existing Angular AssistantService
    tipo: str = "texto"
    datos: Optional[Any] = None
    herramientas_usadas: List[str] = Field(default_factory=list)
    metadata: AssistantMetadata


_UNSAFE_HTML_PATTERN = re.compile(
    r"(<\s*script[^>]*>.*?<\s*/\s*script\s*>|<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>|"
    r"<\s*object[^>]*>.*?<\s*/\s*object\s*>|<\s*embed[^>]*>|"
    r"\bon[a-z]+\s*=\s*['\"][^'\"]*['\"]|\bon[a-z]+\s*=\s*[^\s>]+|"
    r"javascript\s*:|vbscript\s*:|data\s*:\s*text/html)",
    re.IGNORECASE | re.DOTALL,
)


def sanitize_message_text(text: str) -> str:
    """Removes XSS vectors, script tags, and inline event handlers while preserving safe markdown."""
    if not text:
        return ""
    cleaned = _UNSAFE_HTML_PATTERN.sub("", str(text))
    # Also escape raw <script or <img onerror tags if unclosed
    cleaned = re.sub(r"<\s*/?\s*(script|iframe|object|embed|style|link|meta)[^>]*>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def sanitize_image_url(url: Any) -> Optional[str]:
    """Ensures product/outfit image URLs use only safe http(s) or relative paths."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    lower = u.lower()
    if lower.startswith(("javascript:", "vbscript:", "data:text/html")):
        return None
    if lower.startswith(("http://", "https://", "/", "assets/")):
        return u
    return None


def _sanitize_data_payload(data: Any) -> Any:
    """Recursively sanitizes strings and image URLs in widget payloads."""
    if data is None:
        return None
    if isinstance(data, str):
        return sanitize_message_text(data)
    if isinstance(data, list):
        return [_sanitize_data_payload(item) for item in data[:50]]
    if isinstance(data, dict):
        cleaned_dict: Dict[str, Any] = {}
        for k, v in data.items():
            key_str = str(k)
            if key_str in ("imagen", "imagen_url", "foto", "url_imagen"):
                cleaned_dict[key_str] = sanitize_image_url(v)
            else:
                cleaned_dict[key_str] = _sanitize_data_payload(v)
        return cleaned_dict
    return data


class ResponseValidator:
    """Validates and normalizes the orchestrator response before returning to FastAPI."""

    @staticmethod
    def validate_and_build(
        conversation_id: str,
        mensaje: str,
        tipo: str,
        datos: Any,
        herramientas_usadas: List[str],
        metadata: Dict[str, Any],
        success: bool = True,
    ) -> Dict[str, Any]:
        normalized_tipo = (tipo or "texto").strip().lower()
        if normalized_tipo not in SUPPORTED_RESPONSE_TYPES:
            normalized_tipo = "texto"

        clean_msg = sanitize_message_text(mensaje)
        if not clean_msg:
            clean_msg = "He procesado tu consulta. Aquí tienes los resultados:"

        clean_datos = _sanitize_data_payload(datos)

        # If a rich widget type has empty data, gracefully downgrade to 'texto'
        if normalized_tipo != "texto" and normalized_tipo != "error":
            if clean_datos is None or (isinstance(clean_datos, (list, dict)) and len(clean_datos) == 0):
                normalized_tipo = "texto"

        meta_obj = AssistantMetadata(
            provider=str(metadata.get("provider") or "local"),
            model=str(metadata.get("model") or "heuristic"),
            alcance=str(metadata.get("alcance") or "PUBLIC"),
            id_empresa=int(metadata.get("id_empresa") or 1),
            id_sucursal=metadata.get("id_sucursal"),
            latency_ms=float(metadata.get("latency_ms") or 0.0),
            used_fallback=bool(metadata.get("used_fallback", False)),
            intenciones_detectadas=list(metadata.get("intenciones_detectadas") or []),
            es_inicio_frio=metadata.get("es_inicio_frio"),
            referencia_contextual=metadata.get("referencia_contextual"),
        )

        resp = AssistantChatResponse(
            success=success,
            conversation_id=conversation_id,
            mensaje=clean_msg,
            respuesta=clean_msg,
            tipo=normalized_tipo,
            datos=clean_datos,
            herramientas_usadas=list(dict.fromkeys(herramientas_usadas or [])),
            metadata=meta_obj,
        )
        return resp.model_dump()
