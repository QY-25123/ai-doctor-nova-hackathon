"""
Tests for Nova JSON parsing: extraction, repair retry, and FinalAssessmentResponse.
"""

import json
from unittest.mock import patch

import pytest

from app.llm.clinical_flow import FinalAssessmentResponse
from app.llm.nova_client import extract_json_from_text, invoke_nova_json


VALID_FINAL_ASSESSMENT_JSON = {
    "risk_level": "ROUTINE",
    "summary": ["Mild headache described.", "No red flags.", "Self-care may be sufficient."],
    "possible_causes": ["Tension or dehydration."],
    "home_care": ["Rest.", "Stay hydrated."],
    "when_to_seek_care": ["If headache worsens or lasts days, see a doctor."],
    "red_flags": [],
    "sources_query": [],
}

# Substantive assessment: >=3 possible_causes, >=5 home_care, >=5 when_to_seek_care, >=3 red_flags
SUBSTANTIVE_HEADACHE_JSON = {
    "risk_level": "SELF_CARE",
    "summary": [
        "Could be tension-type or mild dehydration-related headache.",
        "Missing: duration, location, fever, other symptoms.",
        "Try self-care below; if no improvement in 24–48 hours or new symptoms, seek care.",
    ],
    "possible_causes": [
        "Tension or muscle tension in neck/scalp.",
        "Dehydration or skipped meals.",
        "Eye strain or screen use.",
    ],
    "home_care": [
        "Rest in a quiet, dark room.",
        "Stay hydrated; drink water regularly.",
        "Over-the-counter pain relief (e.g. acetaminophen or ibuprofen per label) if no contraindications.",
        "Avoid triggers: bright screens, loud noise, skipping meals.",
        "Apply cold or warm compress to forehead or neck as comfortable.",
    ],
    "when_to_seek_care": [
        "Headache is severe or sudden (worst of your life).",
        "Fever, stiff neck, or confusion with headache.",
        "Headache after head injury.",
        "Headache that worsens or does not improve after 24–48 hours.",
        "New or different headache pattern.",
    ],
    "red_flags": [
        "Sudden worst headache of life.",
        "Fever with stiff neck.",
        "Head injury or confusion.",
    ],
    "sources_query": [],
}


def test_extract_json_from_text_strip_whitespace():
    text = '   \n  {"risk_level": "SELF_CARE"}  \n  '
    assert extract_json_from_text(text) == '{"risk_level": "SELF_CARE"}'


def test_extract_json_from_text_code_fence_json():
    text = 'Here is the result:\n```json\n{"risk_level": "ROUTINE", "summary": ["a","b","c"]}\n```'
    out = extract_json_from_text(text)
    assert '"risk_level"' in out and '"ROUTINE"' in out


def test_extract_json_from_text_code_fence_no_lang():
    text = '```\n{"risk_level": "URGENT"}\n```'
    assert extract_json_from_text(text) == '{"risk_level": "URGENT"}'


def test_extract_json_from_text_embedded_object():
    text = 'Some preface. {"risk_level": "EMERGENCY", "summary": ["a","b","c"]} Some trailing.'
    out = extract_json_from_text(text)
    assert out.startswith("{") and out.endswith("}")
    assert "EMERGENCY" in out


def test_plain_text_nova_output_repair_produces_final_assessment():
    """Simulate plain-text Nova output; repair call returns valid JSON -> FinalAssessmentResponse."""
    plain_text = (
        "The patient reports a mild headache. This could be tension or dehydration. "
        "Recommend rest and fluids. If symptoms worsen, they should see a doctor."
    )
    valid_json_str = json.dumps(VALID_FINAL_ASSESSMENT_JSON)

    with patch("app.llm.nova_client.invoke_nova", side_effect=[plain_text, valid_json_str]) as m_invoke:
        messages = [{"role": "user", "content": "I have a headache"}]
        result = invoke_nova_json(
            messages,
            "You are a medical triage assistant.",
            FinalAssessmentResponse,
        )
        assert m_invoke.call_count == 2
        assert isinstance(result, FinalAssessmentResponse)
        assert result.risk_level == "ROUTINE"
        assert len(result.summary) >= 3
        assert result.possible_causes is not None
        assert result.home_care is not None
        assert result.when_to_seek_care is not None


# --- Substantive content and context hygiene ---


def test_headache_produces_at_least_three_home_care_and_possible_causes():
    """Input 'headache' should produce >=3 home_care and >=3 possible_causes when Nova returns substantive JSON."""
    from app.llm.clinical_flow import FinalAssessmentResponse, final_assessment

    substantive = FinalAssessmentResponse(**SUBSTANTIVE_HEADACHE_JSON)
    with patch("app.llm.clinical_flow.invoke_nova_json", return_value=substantive):
        result = final_assessment([{"role": "user", "content": "headache"}])
    assert len(result.home_care) >= 3, "headache assessment should have at least 3 home_care items"
    assert len(result.possible_causes) >= 3, "headache assessment should have at least 3 possible_causes"
    assert result.risk_level == "SELF_CARE"


def test_build_final_assessment_messages_only_user_no_assistant():
    """Context hygiene: only user message(s) are sent; no prior assistant messages."""
    from app.llm.clinical_flow import _build_final_assessment_messages

    messages = [
        {"role": "user", "content": "I have a headache"},
        {"role": "assistant", "content": "This is general information only, not medical advice."},
        {"role": "user", "content": "It's been two days"},
    ]
    reduced = _build_final_assessment_messages(messages)
    assert len(reduced) == 1
    assert reduced[0]["role"] == "user"
    assert "two days" in reduced[0]["content"]
    assert "Prior" in reduced[0]["content"] or "headache" in reduced[0]["content"]


def test_is_substantive_rejects_generic_summary():
    from app.llm.clinical_flow import FinalAssessmentResponse, _is_substantive

    r = FinalAssessmentResponse(
        risk_level="ROUTINE",
        summary=["General guidance provided based on description.", "Point 2", "Point 3"],
        possible_causes=["a", "b", "c"],
        home_care=["1", "2", "3", "4", "5"],
        when_to_seek_care=["1", "2", "3", "4", "5"],
        red_flags=["x", "y", "z"],
    )
    assert _is_substantive(r) is False


def test_is_substantive_accepts_sufficient_content():
    from app.llm.clinical_flow import FinalAssessmentResponse, _is_substantive

    r = FinalAssessmentResponse(**SUBSTANTIVE_HEADACHE_JSON)
    assert _is_substantive(r) is True


def test_substantive_across_repeated_messages():
    """Final assessment with multiple user messages uses reduced context (no assistant) and returns substantive result."""
    from app.llm.clinical_flow import FinalAssessmentResponse, final_assessment

    substantive = FinalAssessmentResponse(**SUBSTANTIVE_HEADACHE_JSON)
    messages = [
        {"role": "user", "content": "I have a headache"},
        {"role": "assistant", "content": "Disclaimer and generic text."},
        {"role": "user", "content": "Still headache after two days"},
    ]
    with patch("app.llm.clinical_flow.invoke_nova_json", return_value=substantive) as m:
        result = final_assessment(messages)
    assert m.call_count == 1
    reduced_msgs = m.call_args[0][0]
    assert len(reduced_msgs) >= 1
    assert all(m.get("role") == "user" for m in reduced_msgs)
    content = reduced_msgs[0].get("content", "")
    assert "two days" in content or "headache" in content
    assert len(result.home_care) >= 3 and len(result.possible_causes) >= 3
