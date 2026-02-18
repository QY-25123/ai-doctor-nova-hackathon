import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import init_db
from repo import add_message, create_conversation, get_conversation_history
from app.logging_structured import generate_request_id, get_metrics, log_guardrail_trigger, log_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Doctor API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    """Basic counters as JSON (no Prometheus)."""
    return get_metrics()


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    """Only conversation_id, risk_level, and final_markdown. No follow_up_questions."""

    conversation_id: int
    risk_level: str | None = None
    final_markdown: str | None = None


def _build_messages(conv_id: int) -> list[dict]:
    history = get_conversation_history(conv_id)
    return [{"role": h["role"], "content": h["content"]} for h in history]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (chars / 4)."""
    return max(0, len(text) // 4)


RAG_K = 5


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    request_id = generate_request_id()
    start = time.perf_counter()

    if request.conversation_id is not None:
        conv_id = request.conversation_id
        messages = _build_messages(conv_id)
    else:
        conv_id = create_conversation()
        messages = []

    add_message(conv_id, "user", request.message)
    messages.append({"role": "user", "content": request.message})

    final_markdown: str | None = None
    risk_level: str | None = None
    red_flag_hits = 0
    rag_k: int | None = None
    model_tokens_est = 0

    # 1) Run red-flag detection FIRST (English-only, case-insensitive)
    from app.safety.red_flags import detect_red_flags
    from app.safety.early_exit import build_emergency_response

    flags = detect_red_flags(request.message)
    red_flag_hits = len(flags["matched_terms"])
    is_emergency = flags["is_self_harm"] or flags["is_emergency_medical"]

    # 2) EARLY EXIT ONLY if EMERGENCY: fixed safe result, no Nova
    if is_emergency:
        result = build_emergency_response(flags)
        from app.llm.clinical_flow import FinalAssessmentResponse
        from app.llm.renderer import render_assessment_markdown
        from repo import save_assessment

        assessment = FinalAssessmentResponse(**result, citations=[])
        final_markdown = render_assessment_markdown(assessment)
        add_message(conv_id, "assistant", "Here is information based on your description. This is not medical advice.")
        risk_level = "EMERGENCY"
        try:
            save_assessment(
                conversation_id=conv_id,
                risk_level=risk_level,
                summary=json.dumps(result["summary"]),
                red_flags_json=json.dumps(result["red_flags"]),
                sources_json=json.dumps(result.get("sources_query", [])),
            )
        except Exception:
            pass
        if flags["matched_terms"]:
            log_guardrail_trigger(
                request_id=request_id,
                matched_terms=flags["matched_terms"],
                final_risk_level=risk_level,
            )
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(
            request_id=request_id,
            conversation_id=conv_id,
            latency_ms=latency_ms,
            risk_level=risk_level,
            red_flag_hits=red_flag_hits,
            nova_called=False,
            rag_k=rag_k,
            model_tokens_est=_estimate_tokens(final_markdown or ""),
        )
        return ChatResponse(conversation_id=conv_id, risk_level=risk_level, final_markdown=final_markdown)

    # 3) ALL NON-EMERGENCY: do NOT generate follow-ups; ALWAYS call Nova once for final assessment
    try:
        from app.llm.clinical_flow import final_assessment
        from app.llm.renderer import render_assessment_markdown
        from app.safety.policy import apply_guardrails

        model_result = final_assessment(messages)
        result = apply_guardrails(request.message, model_result)
        risk_level = result.assessment.risk_level
        if result.matched_terms:
            log_guardrail_trigger(
                request_id=request_id,
                matched_terms=result.matched_terms,
                final_risk_level=risk_level,
            )
        rag_k = RAG_K
        final_markdown = render_assessment_markdown(
            result.assessment,
            emergency_message=result.emergency_message,
        )
        add_message(conv_id, "assistant", "Here is information based on your description. This is not medical advice.")
        model_tokens_est = _estimate_tokens(final_markdown or "")
    except Exception:
        final_markdown = (
            "## Disclaimer\n\nThis is general information only, not medical advice. "
            "This system does not diagnose or prescribe. Always consult a qualified healthcare provider.\n\n"
            "## Risk level\n\n**ROUTINE** — A routine doctor visit is recommended when convenient.\n\n"
            "## When to seek care\n\n- If symptoms worsen or last more than a few days, see a doctor."
        )
        add_message(conv_id, "assistant", "This is general information only, not medical advice. Consult a healthcare provider for your situation.")
        risk_level = "ROUTINE"
        model_tokens_est = _estimate_tokens(final_markdown)

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        request_id=request_id,
        conversation_id=conv_id,
        latency_ms=latency_ms,
        risk_level=risk_level,
        red_flag_hits=red_flag_hits,
        nova_called=True,
        rag_k=rag_k,
        model_tokens_est=model_tokens_est,
    )
    return ChatResponse(conversation_id=conv_id, risk_level=risk_level, final_markdown=final_markdown)


@app.get("/conversations/{conversation_id}/history")
def conversation_history(conversation_id: int) -> list[dict]:
    """Return message history for a conversation."""
    return get_conversation_history(conversation_id)
