"""
2-stage clinical flow: generate_followups and final_assessment (strict JSON). English only.
Uses prompt templates and Pydantic validation; does not diagnose.
Citations are added after LLM response via RAG (optional).
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.llm.nova_client import invoke_nova_json
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


def final_assessment(messages: list[dict]) -> FinalAssessmentResponse:
    """
    Returns a strict JSON assessment: risk_level, summary, possible_causes,
    home_care, when_to_seek_care, red_flags, sources_query, plus citations from RAG. English only.
    messages: full conversation [{"role": "user"|"assistant", "content": "..."}]
    """
    resp = invoke_nova_json(messages, PROMPT_FINAL_ASSESSMENT, FinalAssessmentResponse)
    citations = _get_citations_for_assessment(resp.sources_query)
    return resp.model_copy(update={"citations": citations})
