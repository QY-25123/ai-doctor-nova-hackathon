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
    reply: str = ""
    conversation_id: int
    follow_up_questions: list[str] | None = None
    final_markdown: str | None = None
    risk_level: str | None = None


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

    follow_up_questions: list[str] | None = None
    final_markdown: str | None = None
    reply = ""
    risk_level: str | None = None
    red_flag_hits = 0
    rag_k: int | None = None
    model_tokens_est = 0

    # EARLY-EXIT red-flag gate: very first thing, before follow-ups and before any Nova calls
    from app.safety.red_flags import detect_red_flags
    from app.safety.early_exit import build_emergency_response

    flags = detect_red_flags(request.message)
    red_flag_hits = len(flags["matched_terms"])
    if flags["is_self_harm"] or flags["is_emergency_medical"]:
        result = build_emergency_response(flags)
        from app.llm.clinical_flow import FinalAssessmentResponse
        from app.llm.renderer import render_assessment_markdown
        from repo import save_assessment

        assessment = FinalAssessmentResponse(**result, citations=[])
        final_markdown = render_assessment_markdown(assessment)
        reply = "Here is information based on your description. This is not medical advice."
        add_message(conv_id, "assistant", reply)
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
            rag_k=rag_k,
            model_tokens_est=_estimate_tokens((reply or "") + (final_markdown or "")),
        )
        return ChatResponse(
            reply=reply,
            conversation_id=conv_id,
            final_markdown=final_markdown,
            risk_level=risk_level,
            follow_up_questions=[],
        )

    # First turn: return follow-up questions (or placeholder)
    if len([m for m in messages if m["role"] == "user"]) == 1:
        try:
            from app.llm.clinical_flow import generate_followups
            follow_up_questions = generate_followups(messages)
            reply = "Choose a follow-up question below or describe your situation in your own words."
            model_tokens_est = _estimate_tokens(reply + " ".join(follow_up_questions or []))
        except Exception:
            follow_up_questions = ["How long have your symptoms lasted?", "Do you have a fever?", "Any other symptoms?"]
            reply = "Choose a question below or type your own."
        add_message(conv_id, "assistant", reply)
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(
            request_id=request_id,
            conversation_id=conv_id,
            latency_ms=latency_ms,
            risk_level=risk_level,
            red_flag_hits=red_flag_hits,
            rag_k=rag_k,
            model_tokens_est=model_tokens_est,
        )
        return ChatResponse(reply=reply, conversation_id=conv_id, follow_up_questions=follow_up_questions, risk_level=risk_level)

    # Second turn onward: model inference -> guardrails -> rendering (red-flag early exit already done at top)
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
        # 3. Render only after guardrails (so risk_level/summary/etc. are final)
        final_markdown = render_assessment_markdown(
            result.assessment,
            emergency_message=result.emergency_message,
        )
        reply = "Here is information based on your description. This is not medical advice."
        add_message(conv_id, "assistant", reply)
        model_tokens_est = _estimate_tokens((reply or "") + (final_markdown or ""))
    except Exception:
        reply = (
            "This is general information only, not medical advice. "
            "Consult a healthcare provider for your situation."
        )
        final_markdown = (
            "## Disclaimer\n\nThis is general information only, not medical advice. "
            "This system does not diagnose or prescribe. Always consult a qualified healthcare provider.\n\n"
            "## Risk level\n\n**ROUTINE** — A routine doctor visit is recommended when convenient.\n\n"
            "## When to seek care\n\n- If symptoms worsen or last more than a few days, see a doctor."
        )
        add_message(conv_id, "assistant", reply)
        risk_level = "ROUTINE"
        model_tokens_est = _estimate_tokens(reply + final_markdown)

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        request_id=request_id,
        conversation_id=conv_id,
        latency_ms=latency_ms,
        risk_level=risk_level,
        red_flag_hits=red_flag_hits,
        rag_k=rag_k,
        model_tokens_est=model_tokens_est,
    )
    return ChatResponse(reply=reply, conversation_id=conv_id, final_markdown=final_markdown, risk_level=risk_level)


@app.get("/conversations/{conversation_id}/history")
def conversation_history(conversation_id: int) -> list[dict]:
    """Return message history for a conversation."""
    return get_conversation_history(conversation_id)
