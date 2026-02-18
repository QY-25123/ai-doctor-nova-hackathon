"""
Unit tests for apply_guardrails. English-only.
Any red flag -> risk_level EMERGENCY + hard override (summary, when_to_seek_care, red_flags). Never downgrade EMERGENCY.
"""

import pytest

from app.llm.clinical_flow import FinalAssessmentResponse
from app.safety.policy import EMERGENCY_DISCLAIMER, EMERGENCY_OVERRIDE_SUMMARY, apply_guardrails, GuardrailResult


def _assessment(risk_level: str) -> FinalAssessmentResponse:
    return FinalAssessmentResponse(
        risk_level=risk_level,
        summary=["Point one", "Point two", "Point three"],
        possible_causes=[],
        home_care=[],
        when_to_seek_care=[],
        red_flags=[],
        sources_query=[],
    )


def test_severe_chest_pain_cold_sweats_trouble_breathing_emergency():
    """Input: severe chest pain, cold sweats, trouble breathing -> risk_level EMERGENCY."""
    user_text = "I suddenly developed severe chest pain, cold sweats, and trouble breathing."
    out = apply_guardrails(user_text, _assessment("ROUTINE"))
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message == EMERGENCY_DISCLAIMER
    assert out.assessment.summary == EMERGENCY_OVERRIDE_SUMMARY
    assert len(out.matched_terms) >= 1


def test_shortness_of_breath_emergency():
    """Shortness of breath alone triggers EMERGENCY."""
    user_text = "shortness of breath"
    out = apply_guardrails(user_text, _assessment("SELF_CARE"))
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message == EMERGENCY_DISCLAIMER


def test_english_chest_pain_forces_emergency():
    user_text = "I have chest pain and left arm pain"
    model_result = _assessment("ROUTINE")
    out = apply_guardrails(user_text, model_result)
    assert isinstance(out, GuardrailResult)
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message == EMERGENCY_DISCLAIMER


def test_pressure_in_chest_forces_emergency():
    user_text = "I have pressure in my chest"
    out = apply_guardrails(user_text, _assessment("URGENT"))
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message is not None


def test_difficulty_breathing_english_forces_emergency():
    user_text = "Having difficulty breathing since an hour ago"
    out = apply_guardrails(user_text, _assessment("SELF_CARE"))
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message == EMERGENCY_DISCLAIMER


def test_suicidal_english_forces_emergency():
    user_text = "I have been having suicidal thoughts"
    out = apply_guardrails(user_text, _assessment("ROUTINE"))
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message == EMERGENCY_DISCLAIMER


def test_no_red_flag_preserves_model_result():
    user_text = "I have a mild cold and runny nose"
    model_result = _assessment("SELF_CARE")
    out = apply_guardrails(user_text, model_result)
    assert out.assessment.risk_level == "SELF_CARE"
    assert out.emergency_message is None
    assert out.assessment.summary == model_result.summary
    assert out.matched_terms == []


def test_severe_bleeding_forces_emergency():
    user_text = "There is severe bleeding and I cannot stop it"
    out = apply_guardrails(user_text, _assessment("URGENT"))
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message == EMERGENCY_DISCLAIMER


def test_poisoning_overdose_forces_emergency():
    user_text = "I think I overdosed on medication"
    out = apply_guardrails(user_text, _assessment("ROUTINE"))
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message is not None


def test_red_flag_overrides_model_urgent_to_emergency():
    """Model says URGENT but user has red flag -> EMERGENCY + hard override."""
    user_text = "I have chest pain and trouble breathing"
    model_result = _assessment("URGENT")
    out = apply_guardrails(user_text, model_result)
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message == EMERGENCY_DISCLAIMER
    assert out.assessment.summary == EMERGENCY_OVERRIDE_SUMMARY


def test_emergency_never_downgraded():
    """If model already says EMERGENCY, guardrails do not downgrade."""
    user_text = "I have a mild headache"
    model_result = _assessment("EMERGENCY")
    out = apply_guardrails(user_text, model_result)
    assert out.assessment.risk_level == "EMERGENCY"
    assert out.emergency_message is None
