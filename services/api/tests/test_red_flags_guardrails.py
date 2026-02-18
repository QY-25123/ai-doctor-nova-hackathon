"""
Early-exit red-flag gate: detect_red_flags, build_emergency_response, POST /chat.
Tests: chest pain => EMERGENCY + follow_up_questions empty; hurt myself => EMERGENCY + 988; Nova not called.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.safety.red_flags import detect_red_flags
from app.safety.early_exit import build_emergency_response
from app.llm.clinical_flow import FinalAssessmentResponse
from app.llm.renderer import render_assessment_markdown


def test_detect_red_flags_hurt_myself():
    flags = detect_red_flags("hurt myself")
    assert flags["is_self_harm"] is True
    assert "hurt myself" in flags["matched_terms"]
    assert flags["matched_terms"] == sorted(list(set(flags["matched_terms"])))


def test_detect_red_flags_chest_pain():
    flags = detect_red_flags("chest pain")
    assert flags["is_emergency_medical"] is True
    assert "chest pain" in flags["matched_terms"]


def test_build_emergency_response_self_harm_includes_988():
    flags = detect_red_flags("hurt myself")
    result = build_emergency_response(flags)
    assert result["risk_level"] == "EMERGENCY"
    assert "988" in " ".join(result["summary"])
    assert result["when_to_seek_care"]
    assert result["red_flags"] == ["self-harm risk detected"]


def test_build_emergency_response_emergency_medical():
    flags = detect_red_flags("chest pain")
    result = build_emergency_response(flags)
    assert result["risk_level"] == "EMERGENCY"
    assessment = FinalAssessmentResponse(**result, citations=[])
    markdown = render_assessment_markdown(assessment)
    assert "EMERGENCY" in markdown
    assert "911" in markdown or "emergency" in markdown.lower()


def test_detect_red_flags_no_match():
    flags = detect_red_flags("I have a mild headache")
    assert flags["is_self_harm"] is False
    assert flags["is_emergency_medical"] is False
    assert flags["matched_terms"] == []


def test_detect_red_flags_empty():
    out = detect_red_flags("")
    assert out["is_self_harm"] is False
    assert out["is_emergency_medical"] is False
    assert out["matched_terms"] == []


def test_chat_chest_pain_returns_emergency_and_empty_follow_up_questions():
    """POST /chat with 'chest pain' must return risk_level==EMERGENCY and follow_up_questions empty."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        r = client.post("/chat", json={"message": "chest pain"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("risk_level") == "EMERGENCY"
    assert data.get("final_markdown"), "early exit should return final_markdown"
    assert "EMERGENCY" in (data.get("final_markdown") or "")
    assert data.get("follow_up_questions") == [], "early exit must return follow_up_questions as empty list"


def test_chat_hurt_myself_returns_emergency_and_includes_988():
    """POST /chat with 'hurt myself' must return risk_level==EMERGENCY and include 988."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        r = client.post("/chat", json={"message": "hurt myself"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("risk_level") == "EMERGENCY"
    assert data.get("final_markdown"), "early exit should return final_markdown"
    assert "EMERGENCY" in (data.get("final_markdown") or "")
    assert "988" in (data.get("final_markdown") or "")


def test_chat_early_exit_does_not_call_nova_client():
    """For early-exit paths (e.g. 'chest pain'), Nova client must NOT be called."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app

    with patch("app.llm.nova_client.invoke_nova_json", MagicMock()) as mock_nova:
        with TestClient(app) as client:
            r = client.post("/chat", json={"message": "chest pain"})
        mock_nova.assert_not_called()
    assert r.status_code == 200
    assert r.json().get("risk_level") == "EMERGENCY"


def test_chat_hurt_myself_does_not_call_nova_client():
    """For 'hurt myself' early exit, Nova client must NOT be called."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app

    with patch("app.llm.nova_client.invoke_nova_json", MagicMock()) as mock_nova:
        with TestClient(app) as client:
            r = client.post("/chat", json={"message": "hurt myself"})
        mock_nova.assert_not_called()
    assert r.status_code == 200
    assert r.json().get("risk_level") == "EMERGENCY"
    assert "988" in (r.json().get("final_markdown") or "")
