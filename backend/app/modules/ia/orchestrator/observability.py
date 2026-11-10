"""
Observability, Rate Limiting, and Cost Tracking for Aurora Advisor.
Tracks provider, model, tenant, user/visitor, latency, token usage, tools executed,
tool timings, fallback activation, and estimated cost per conversation turn.
"""
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from app.modules.ia.ai.exceptions.ai_exceptions import AIRateLimitExceededError
from app.modules.ia.ai.core.ai_capabilities import get_model_capabilities


@dataclass
class TurnMetrics:
    conversation_id: str
    timestamp: float
    provider: str
    model: str
    id_empresa: int
    id_usuario: Optional[int]
    alcance: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    tools_executed: List[str] = field(default_factory=list)
    tool_timings_ms: Dict[str, float] = field(default_factory=dict)
    used_fallback: bool = False
    error_code: Optional[str] = None


class RateLimiter:
    """
    Sliding-window rate limiter per user / visitor / IP key.
    Protects AI endpoints from excessive consumption or DoS bursts.
    """

    def __init__(self, max_requests_per_window: int = 30, window_seconds: float = 60.0):
        self.max_requests = max_requests_per_window
        self.window_seconds = window_seconds
        self._buckets: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def check_and_record(self, key: str) -> None:
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                raise AIRateLimitExceededError(
                    "Has enviado demasiadas consultas en poco tiempo. Por favor espera unos segundos antes de continuar."
                )
            bucket.append(now)

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key:
                self._buckets.pop(key, None)
            else:
                self._buckets.clear()


class ObservabilityTracker:
    """
    In-memory ring-buffer observability tracker for Aurora Advisor interactions.
    Stores recent turn metrics and computes aggregated KPIs per tenant and provider.
    """

    def __init__(self, max_records: int = 500):
        self.max_records = max_records
        self._records: deque[TurnMetrics] = deque(maxlen=max_records)
        self._lock = threading.Lock()

    def record_turn(
        self,
        conversation_id: str,
        provider: str,
        model: str,
        id_empresa: int,
        id_usuario: Optional[int],
        alcance: str,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        tools_executed: Optional[List[str]] = None,
        tool_timings_ms: Optional[Dict[str, float]] = None,
        used_fallback: bool = False,
        error_code: Optional[str] = None,
    ) -> TurnMetrics:
        caps = get_model_capabilities(provider, model)
        cost_usd = round(
            (prompt_tokens / 1000.0) * caps.cost_per_1k_input_usd
            + (completion_tokens / 1000.0) * caps.cost_per_1k_output_usd,
            6,
        )
        metrics = TurnMetrics(
            conversation_id=conversation_id,
            timestamp=time.time(),
            provider=provider,
            model=model,
            id_empresa=id_empresa,
            id_usuario=id_usuario,
            alcance=alcance,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=cost_usd,
            tools_executed=list(tools_executed or []),
            tool_timings_ms=dict(tool_timings_ms or {}),
            used_fallback=used_fallback,
            error_code=error_code,
        )
        with self._lock:
            self._records.append(metrics)
        return metrics

    def get_summary(self, id_empresa: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            items = [
                r for r in self._records
                if id_empresa is None or r.id_empresa == id_empresa
            ]

        if not items:
            return {
                "total_interacciones": 0,
                "latencia_promedio_ms": 0.0,
                "tokens_totales": 0,
                "costo_estimado_usd": 0.0,
                "tasa_fallback_pct": 0.0,
                "herramientas_frecuentes": {},
                "proveedores": {},
            }

        total = len(items)
        avg_latency = round(sum(i.latency_ms for i in items) / total, 2)
        total_tokens = sum(i.total_tokens for i in items)
        total_cost = round(sum(i.estimated_cost_usd for i in items), 6)
        fallbacks = sum(1 for i in items if i.used_fallback)
        tool_counts: Dict[str, int] = {}
        provider_counts: Dict[str, int] = {}

        for item in items:
            prov_key = f"{item.provider}:{item.model}"
            provider_counts[prov_key] = provider_counts.get(prov_key, 0) + 1
            for t in item.tools_executed:
                tool_counts[t] = tool_counts.get(t, 0) + 1

        return {
            "total_interacciones": total,
            "latencia_promedio_ms": avg_latency,
            "tokens_totales": total_tokens,
            "costo_estimado_usd": total_cost,
            "tasa_fallback_pct": round((fallbacks / total) * 100.0, 1),
            "herramientas_frecuentes": tool_counts,
            "proveedores": provider_counts,
        }


GLOBAL_RATE_LIMITER = RateLimiter(max_requests_per_window=40, window_seconds=60.0)
GLOBAL_OBSERVABILITY_TRACKER = ObservabilityTracker(max_records=500)
