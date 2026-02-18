import pytest

from app.safety.red_flag_rules import check_red_flags


def test_empty_or_whitespace_no_hit():
    assert check_red_flags("").hit is False
    assert check_red_flags("   ").hit is False


def test_english_chest_pain_hit():
    r = check_red_flags("I have chest pain since morning")
    assert r.hit is True
    assert "chest pain" in [t.lower() for t in r.matched_terms]
    assert check_red_flags("CHEST PAIN and sweating").hit is True


def test_severe_chest_pain_and_cold_sweats_trouble_breathing():
    """User-requested: severe chest pain + cold sweats + trouble breathing -> EMERGENCY."""
    text = "I suddenly developed severe chest pain, cold sweats, and trouble breathing."
    r = check_red_flags(text)
    assert r.hit is True
    assert len(r.matched_terms) >= 1


def test_shortness_of_breath_triggers():
    """User-requested: shortness of breath alone triggers at least URGENT/EMERGENCY (we use EMERGENCY)."""
    r = check_red_flags("shortness of breath")
    assert r.hit is True
    assert "shortness of breath" in [t.lower() for t in r.matched_terms]


def test_difficulty_breathing_english_hit():
    assert check_red_flags("I can't breathe properly").hit is True
    assert check_red_flags("shortness of breath when walking").hit is True


def test_suicide_self_harm_english_hit():
    assert check_red_flags("I have suicidal thoughts").hit is True
    assert check_red_flags("I want to hurt myself").hit is True


def test_severe_bleeding_hit():
    assert check_red_flags("severe bleeding from the wound").hit is True


def test_coughing_blood_hit():
    assert check_red_flags("I am coughing blood").hit is True


def test_passed_out_loss_of_consciousness():
    assert check_red_flags("I passed out yesterday").hit is True
    assert check_red_flags("loss of consciousness").hit is True


def test_stroke_signs():
    assert check_red_flags("face droop and arm weakness").hit is True
    assert check_red_flags("slurred speech").hit is True


def test_no_red_flag_routine_text():
    assert check_red_flags("I have a mild headache").hit is False
    assert check_red_flags("sore throat for two days").hit is False
