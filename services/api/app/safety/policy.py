"""
Guardrails policy: if any red flag in user text, force EMERGENCY and hard override.
Never allow EMERGENCY to be downgraded by the model.
"""

from pydantic import BaseModel

from app.llm.clinical_flow import FinalAssessmentResponse
from app.safety.red_flag_rules import check_red_flags

EMERGENCY_DISCLAIMER = (
    "This may be a medical emergency. Please call emergency services "
    "(e.g. 911 / your local emergency number) or go to the nearest emergency department immediately. "
    "This system cannot provide emergency care."
)

EMERGENCY_OVERRIDE_SUMMARY = [
    "Your symptoms may indicate a medical emergency.",
    "Seek emergency care immediately.",
]
EMERGENCY_OVERRIDE_WHEN_TO_SEEK = [
    "Call emergency services (911) now or go to the nearest emergency department.",
    "Do not drive yourself if you feel faint or short of breath.",
]

# For minimal red_flags.py early exit and emergency-medical overwrite
SELF_HARM_988_MARKDOWN = """## Emergency warning

If you are in crisis or having thoughts of self-harm, please reach out now:
- **988** Suicide & Crisis Lifeline (US): call or text **988**
- Your local emergency number (e.g. 911) or go to the nearest emergency department.

You are not alone. This system cannot provide emergency care.

## Disclaimer

This is general information only, not medical advice. This system does not diagnose or prescribe. Always consult a qualified healthcare provider for your situation.

## Risk level

**EMERGENCY** — May be life-threatening. Seek emergency care immediately (call emergency services or go to the nearest emergency department).

## When to seek care

- Call 988 (US) or your local crisis line now.
- Call emergency services (911) or go to the nearest emergency department if you are in danger."""

EMERGENCY_MEDICAL_MESSAGE = "Call 911 or go to the nearest emergency department immediately."

RED_FLAG_EMERGENCY_SUMMARY = [
    "Your symptoms may indicate a medical emergency.",
    "Seek emergency care immediately.",
    "Call 911 or go to the nearest emergency department.",
]
RED_FLAG_EMERGENCY_WHEN_TO_SEEK = [
    "Call 911 or go to the nearest emergency department immediately.",
]


def early_exit_response(flags: dict) -> dict | None:
    """
    Return assessment-like dict for early exit (no LLM). Used at the very top of POST /chat.
    Returns None if neither self_harm nor emergency_medical.
    """
    if flags.get("self_harm"):
        return {
            "risk_level": "EMERGENCY",
            "summary": [
                "You may be in immediate danger.",
                "If you are in the U.S., call or text 988 (Suicide & Crisis Lifeline) now.",
                "If you are in immediate danger, call 911 or your local emergency number.",
            ],
            "when_to_seek_care": [
                "Call 911 (or local emergency number) now if you might act on these thoughts.",
                "Reach out to someone you trust and do not stay alone.",
            ],
            "red_flags": ["self-harm risk detected"],
            "possible_causes": [],
            "home_care": [],
            "sources_query": [],
        }
    if flags.get("emergency_medical"):
        return {
            "risk_level": "EMERGENCY",
            "summary": [
                "Chest pain can be a medical emergency.",
                "Seek emergency evaluation immediately.",
                "Do not wait.",
            ],
            "when_to_seek_care": [
                "Call 911 (or local emergency number) now or go to the nearest emergency department.",
                "Do not drive yourself if you feel faint or short of breath.",
            ],
            "red_flags": [f"emergency symptom detected: {', '.join(flags.get('matched_terms', []))}"],
            "possible_causes": [],
            "home_care": [],
            "sources_query": [],
        }
    return None


def build_self_harm_result() -> dict:
    """Return reply and final_markdown for early exit (no LLM). risk_level is EMERGENCY; includes 988 + local emergency."""
    return {
        "reply": "Here is information based on your description. This is not medical advice.",
        "final_markdown": SELF_HARM_988_MARKDOWN,
    }


def build_emergency_medical_result(matched_terms: list[str]) -> FinalAssessmentResponse:
    """Return assessment with risk_level=EMERGENCY and Call 911 / go to ER guidance."""
    return FinalAssessmentResponse(
        risk_level="EMERGENCY",
        summary=RED_FLAG_EMERGENCY_SUMMARY,
        possible_causes=[],
        home_care=[],
        when_to_seek_care=RED_FLAG_EMERGENCY_WHEN_TO_SEEK,
        red_flags=list(matched_terms),
        sources_query=[],
        citations=[],
    )


class GuardrailResult(BaseModel):
    """Result after applying guardrails: assessment (possibly overridden) + optional disclaimer."""

    assessment: FinalAssessmentResponse
    emergency_message: str | None = None
    matched_terms: list[str] = []


def apply_guardrails(user_text: str, model_result: FinalAssessmentResponse) -> GuardrailResult:
    """
    ALWAYS runs. If user_text triggers any red-flag rule:
    - risk_level = "EMERGENCY" (never downgrade if model already said EMERGENCY)
    - summary = hard override (emergency messaging)
    - when_to_seek_care = hard override (911 / ED)
    - red_flags = unique list including the matched red-flag terms
    Otherwise return model_result as-is with emergency_message=None.
    """
    hit, matched_terms = check_red_flags(user_text)

    if not hit:
        return GuardrailResult(assessment=model_result, emergency_message=None, matched_terms=[])

    # Red flag detected: overwrite risk_level and emergency fields. Model's risk_level must not survive.
    print("Guardrails triggered:", matched_terms, flush=True)
    overridden = model_result.model_copy(
        update={
            "risk_level": "EMERGENCY",
            "summary": EMERGENCY_OVERRIDE_SUMMARY,
            "when_to_seek_care": EMERGENCY_OVERRIDE_WHEN_TO_SEEK,
            "red_flags": list(dict.fromkeys(matched_terms + list(model_result.red_flags or []))),
        }
    )
    assert overridden.risk_level == "EMERGENCY", "Guardrails must overwrite risk_level to EMERGENCY when red flags exist"
    return GuardrailResult(
        assessment=overridden,
        emergency_message=EMERGENCY_DISCLAIMER,
        matched_terms=matched_terms,
    )
