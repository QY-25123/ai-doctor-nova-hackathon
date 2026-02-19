"""
Structured JSON logging and in-memory metrics for hackathon.
One JSON line per request; /metrics returns counters as JSON.
"""

import json
import sys
import time
import uuid
from typing import Any

# In-memory counters for /metrics
_metrics: dict[str, int | dict[str, int]] = {
    "requests_total": 0,
    "red_flag_hits_total": 0,
    "by_risk_level": {},
    "rag_retrievals_total": 0,
    "model_tokens_est_total": 0,
}


def _ensure_key(d: dict[str, Any], key: str, default: int = 0) -> None:
    if d.get(key) is None:
        d[key] = default


def log_request(
    *,
    request_id: str,
    conversation_id: int | None,
    latency_ms: float,
    risk_level: str | None = None,
    red_flag_hits: int = 0,
    nova_called: bool = False,
    rag_k: int | None = None,
    model_tokens_est: int = 0,
    nova_risk_level: str | None = None,
    nova_model: str | None = None,
) -> None:
    """Emit one JSON log line and update in-memory metrics. risk_level is final (after guardrails); nova_risk_level is what Nova returned; nova_model is the model used when nova_called is True."""
    payload = {
        "request_id": request_id,
        "conversation_id": conversation_id,
        "latency_ms": round(latency_ms, 2),
        "risk_level": risk_level,
        "red_flag_hits": red_flag_hits,
        "nova_called": nova_called,
        "rag_k": rag_k,
        "model_tokens_est": model_tokens_est,
        "nova_risk_level": nova_risk_level,
        "nova_model": nova_model,
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)

    _metrics["requests_total"] = (_metrics["requests_total"] or 0) + 1
    if red_flag_hits:
        _metrics["red_flag_hits_total"] = (_metrics["red_flag_hits_total"] or 0) + red_flag_hits
    if risk_level:
        by_level = _metrics.setdefault("by_risk_level", {})
        _ensure_key(by_level, risk_level)
        by_level[risk_level] = (by_level[risk_level] or 0) + 1
    if rag_k is not None:
        _metrics["rag_retrievals_total"] = (_metrics["rag_retrievals_total"] or 0) + 1
    if model_tokens_est:
        _metrics["model_tokens_est_total"] = (_metrics["model_tokens_est_total"] or 0) + model_tokens_est


def get_metrics() -> dict[str, Any]:
    """Return current counters as JSON-serializable dict."""
    return {
        "requests_total": _metrics.get("requests_total", 0),
        "red_flag_hits_total": _metrics.get("red_flag_hits_total", 0),
        "by_risk_level": dict(_metrics.get("by_risk_level") or {}),
        "rag_retrievals_total": _metrics.get("rag_retrievals_total", 0),
        "model_tokens_est_total": _metrics.get("model_tokens_est_total", 0),
    }


def generate_request_id() -> str:
    return str(uuid.uuid4())


def log_guardrail_trigger(
    *,
    request_id: str,
    matched_terms: list[str],
    final_risk_level: str,
) -> None:
    """Log when guardrails trigger (red flag hit)."""
    payload = {
        "event": "guardrail_trigger",
        "request_id": request_id,
        "matched_terms": matched_terms,
        "final_risk_level": final_risk_level,
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)


def log_nova_response_parse_failed(
    *,
    response_snippet: str,
) -> None:
    """Log when Nova response had no extractable text or JSON validation failed."""
    payload = {
        "event": "nova_response_parse_failed",
        "response_snippet": response_snippet,
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)


def log_nova_parse_failed_first_pass(
    *,
    response_snippet: str,
) -> None:
    """Log when first-pass parse of Nova JSON failed (before repair retry)."""
    payload = {
        "event": "nova_parse_failed_first_pass",
        "response_snippet": response_snippet,
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)


def log_nova_parse_repaired() -> None:
    """Log when repair retry succeeded and output parsed into schema."""
    payload = {"event": "nova_parse_repaired"}
    print(json.dumps(payload), file=sys.stderr, flush=True)


def log_nova_parse_failed_final(
    *,
    response_snippet: str,
) -> None:
    """Log when repair retry still failed to produce valid schema."""
    payload = {
        "event": "nova_parse_failed_final",
        "response_snippet": response_snippet,
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)
