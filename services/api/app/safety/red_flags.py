"""
English-only red-flag detection for early exit. Used before any follow-ups or Nova/LLM calls.
"""


def detect_red_flags(text: str) -> dict:
    """
    Check text (case-insensitive, stripped) for self-harm and emergency medical terms.
    Returns dict with is_self_harm, is_emergency_medical, and sorted unique matched_terms.
    """
    t = (text or "").lower().strip()
    self_harm_terms = [
        "hurt myself",
        "kill myself",
        "suicide",
        "suicidal",
        "self harm",
        "self-harm",
        "end my life",
        "want to die",
        "don't want to live",
    ]
    emergency_terms = [
        "chest pain",
        "severe chest pain",
        "pressure in chest",
        "shortness of breath",
        "difficulty breathing",
        "trouble breathing",
        "cold sweat",
        "cold sweats",
        "fainting",
        "passed out",
        "loss of consciousness",
        "coughing blood",
        "severe bleeding",
    ]
    matched = []
    for p in self_harm_terms + emergency_terms:
        if p in t:
            matched.append(p)
    return {
        "is_self_harm": any(p in t for p in self_harm_terms),
        "is_emergency_medical": any(p in t for p in emergency_terms),
        "matched_terms": sorted(list(set(matched))),
    }
