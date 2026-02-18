"""
Render validated assessment JSON to markdown. Deterministic section order.
References only from retrieved citations (no hallucinated links).
"""

from app.llm.clinical_flow import Citation, FinalAssessmentResponse

DISCLAIMER = (
    "This is general information only, not medical advice. "
    "This system does not diagnose or prescribe. Always consult a qualified healthcare provider for your situation."
)

RISK_LEVEL_MEANINGS = {
    "EMERGENCY": "May be life-threatening. Seek emergency care immediately (call emergency services or go to the nearest emergency department).",
    "URGENT": "Should be evaluated by a doctor soon. Do not delay if symptoms worsen.",
    "ROUTINE": "A routine doctor visit is recommended when convenient.",
    "SELF_CARE": "General self-care information may be appropriate; see “When to seek care” if symptoms change or worsen.",
}


def _section(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    return f"## {title}\n\n" + "\n".join(f"- {line}" for line in lines) + "\n\n"


def _ref_line(c: Citation) -> str:
    """One reference line. Only use source and url from citation (no hallucinated links)."""
    label = c.source or "Source"
    url = (c.url or "").strip()
    if url:
        return f"- [{label}]({url})"
    return f"- {label}"


def render_assessment_markdown(
    assessment: FinalAssessmentResponse,
    *,
    emergency_message: str | None = None,
) -> str:
    """
    Convert validated assessment to markdown string. Deterministic order.
    References section uses only assessment.citations (no other URLs).
    """
    parts: list[str] = []

    # 0. Emergency (if present)
    if emergency_message and emergency_message.strip():
        parts.append(f"## Emergency warning\n\n{emergency_message.strip()}\n\n")

    # 1. Disclaimer (always)
    parts.append(f"## Disclaimer\n\n{DISCLAIMER}\n\n")

    # 2. Risk Level + what it means
    level = assessment.risk_level
    meaning = RISK_LEVEL_MEANINGS.get(level, "")
    parts.append(f"## Risk level\n\n**{level}** — {meaning}\n\n")

    # 3. Key Summary bullets
    if assessment.summary:
        parts.append(_section("Summary", assessment.summary))

    # 4. Possible Causes (cautious)
    if assessment.possible_causes:
        parts.append(_section("Possible causes", assessment.possible_causes))

    # 5. What you can do now
    if assessment.home_care:
        parts.append(_section("What you can do now", assessment.home_care))

    # 6. When to seek care (with red flags highlighted)
    when_lines: list[str] = []
    when_lines.extend(assessment.when_to_seek_care or [])
    if assessment.red_flags:
        when_lines.append("**Red flags — seek care promptly:**")
        when_lines.extend(f"**{f}**" for f in assessment.red_flags)
    if when_lines:
        parts.append(_section("When to seek care", when_lines))

    # 7. References (only from retrieved chunks; no hallucinated links)
    refs = [c for c in assessment.citations if c.source or c.url]
    if refs:
        ref_lines = [_ref_line(c) for c in refs]
        parts.append("## References\n\n" + "\n".join(ref_lines) + "\n")

    return "".join(parts).strip()
