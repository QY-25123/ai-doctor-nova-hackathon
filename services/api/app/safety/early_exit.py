"""
Early-exit emergency response builder. English-only. Used when red flags are detected before any Nova/LLM call.
"""


def build_emergency_response(flags: dict) -> dict:
    """
    Build an assessment-like dict for immediate EMERGENCY return.
    Includes all fields required by the renderer: summary, when_to_seek_care, red_flags,
    possible_causes, home_care, sources_query. risk_level is always EMERGENCY.
    """
    if flags.get("is_self_harm"):
        return {
            "risk_level": "EMERGENCY",
            "summary": [
                "You may be in immediate danger.",
                "If you are in the U.S., call or text 988 (Suicide & Crisis Lifeline) now.",
                "If you are in immediate danger, call 911 or your local emergency number.",
            ],
            "when_to_seek_care": [
                "Call 911 (or your local emergency number) now if you might act on these thoughts.",
                "Reach out to someone you trust and do not stay alone.",
            ],
            "red_flags": ["self-harm risk detected"],
            "possible_causes": [],
            "home_care": [],
            "sources_query": [],
        }
    # Emergency medical (chest pain, breathing, fainting, bleeding, etc.)
    return {
        "risk_level": "EMERGENCY",
        "summary": [
            "Chest pain or breathing problems can be a medical emergency.",
            "Seek emergency evaluation immediately.",
            "Do not wait.",
        ],
        "when_to_seek_care": [
            "Call 911 (or your local emergency number) now or go to the nearest emergency department.",
            "Do not drive yourself if you feel faint or short of breath.",
        ],
        "red_flags": [f"emergency symptom: {', '.join(flags.get('matched_terms', []))}"],
        "possible_causes": [],
        "home_care": [],
        "sources_query": [],
    }
