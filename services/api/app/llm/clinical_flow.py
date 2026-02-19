"""
2-stage clinical flow: generate_followups and final_assessment (strict JSON). English only.
Uses prompt templates and Pydantic validation; does not diagnose.
Citations are added after LLM response via RAG (optional).
Context hygiene: final_assessment sends only system + latest user (and optional prior summary).
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.llm.nova_client import invoke_nova_json, repair_final_assessment_for_quality
from app.llm.prompts import PROMPT_FINAL_ASSESSMENT, PROMPT_FOLLOWUPS

# --- Pydantic models ---


class FollowUpsResponse(BaseModel):
    """3-6 follow-up questions in English."""

    follow_ups: list[str] = Field(..., min_length=3, max_length=6)


RiskLevel = Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]


class Citation(BaseModel):
    """One citation from RAG: source, url, quote."""

    source: str
    url: str
    quote: str


class FinalAssessmentResponse(BaseModel):
    """Strict JSON schema for final assessment. No diagnosis. citations filled by RAG."""

    risk_level: RiskLevel
    summary: list[str] = Field(..., min_length=3, max_length=6)
    possible_causes: list[str] = Field(default_factory=list)
    home_care: list[str] = Field(default_factory=list)
    when_to_seek_care: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    sources_query: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


# --- Stage 1: Follow-ups ---


def generate_followups(messages: list[dict]) -> list[str]:
    """
    Returns 3-6 short, patient-friendly follow-up questions in English.
    messages: conversation so far [{"role": "user"|"assistant", "content": "..."}]
    """
    out = invoke_nova_json(messages, PROMPT_FOLLOWUPS, FollowUpsResponse)
    return out.follow_ups


# --- Stage 2: Final assessment ---


def _build_final_assessment_messages(messages: list[dict]) -> list[dict]:
    """
    Context hygiene: return only the latest user message and optionally a compact
    summary of prior user symptoms. Do NOT include prior assistant messages (e.g. disclaimers).
    """
    user_contents: list[str] = []
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        content = str(content).strip()
        if content:
            user_contents.append(content)
    if not user_contents:
        return [{"role": "user", "content": "I have a health question."}]
    if len(user_contents) == 1:
        return [{"role": "user", "content": user_contents[-1]}]
    prior = " | ".join(user_contents[:-1][-3:])  # up to 3 prior user messages, compact
    latest = user_contents[-1]
    return [{"role": "user", "content": f"Prior symptoms/context: {prior}\n\nLatest: {latest}"}]


def _is_substantive(resp: FinalAssessmentResponse) -> bool:
    """Quality check: sufficient items and no generic filler in summary."""
    summary_text = " ".join(resp.summary or []).lower()
    if "general guidance provided" in summary_text:
        return False
    if len(resp.possible_causes or []) < 2:
        return False
    if len(resp.home_care or []) < 3:
        return False
    return True


def _get_citations_for_assessment(sources_query: list[str], top_k: int = 5) -> list[Citation]:
    """Run RAG on sources_query and return list of Citation. No-op if index missing or no queries."""
    if not sources_query:
        return []
    try:
        from app.rag.rag import retrieve_top_k
    except Exception:
        return []
    seen = set()
    citations = []
    for q in sources_query[:3]:
        chunks = retrieve_top_k(q, top_k)
        for c in chunks:
            key = (c.get("source"), c.get("url"), c.get("content", "")[:80])
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                Citation(
                    source=c.get("source", ""),
                    url=c.get("url", ""),
                    quote=(c.get("content") or "")[:500],
                )
            )
        if len(citations) >= top_k * 2:
            break
    return citations[:15]


def _last_user_content(messages: list[dict]) -> str:
    """Extract the latest user message content."""
    for m in reversed(messages):
        if m.get("role") != "user":
            continue
        c = m.get("content", "")
        c = c[0].get("text", c) if isinstance(c, list) else str(c)
        return (c or "").strip()
    return ""


def final_assessment(messages: list[dict]) -> FinalAssessmentResponse:
    """
    Returns a strict JSON assessment: risk_level, summary, possible_causes,
    home_care, when_to_seek_care, red_flags, sources_query, plus citations from RAG. English only.
    Sends only system + latest user (and optional prior summary); no prior assistant messages.
    Triggers quality repair if output is generic or below minimum item counts.
    """
    reduced = _build_final_assessment_messages(messages)
    last_user = _last_user_content(messages) or "User described symptoms."
    resp = invoke_nova_json(
        reduced,
        PROMPT_FINAL_ASSESSMENT,
        FinalAssessmentResponse,
        user_symptom_for_repair=last_user,
    )
    if not _is_substantive(resp):
        resp = repair_final_assessment_for_quality(
            last_user,
            PROMPT_FINAL_ASSESSMENT,
            FinalAssessmentResponse,
        )
    citations = _get_citations_for_assessment(resp.sources_query)
    return resp.model_copy(update={"citations": citations})
