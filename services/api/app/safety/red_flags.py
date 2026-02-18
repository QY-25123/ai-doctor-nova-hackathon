"""
English-only red-flag detection. EMERGENCY only: self-harm and emergency medical terms.
Case-insensitive. Used to decide whether to bypass Nova (early exit) or call Nova for full assessment.
"""

SELF_HARM_TERMS = [
    "hurt myself",
    "kill myself",
    "suicide",
    "suicidal",
    "self harm",
    "self-harm",
    "end my life",
    "want to die",
]

EMERGENCY_TERMS = [
    "chest pain",
    "severe chest pain",
    "pressure in chest",
    "shortness of breath",
    "difficulty breathing",
    "trouble breathing",
    "cold sweats",
    "passed out",
    "fainting",
    "coughing blood",
    "severe bleeding",
]


def detect_red_flags(text: str) -> dict:
    """
    Check text (case-insensitive) for EMERGENCY red flags: self-harm or emergency medical.
    Returns dict with is_self_harm, is_emergency_medical, and matched_terms.
    """
    t = (text or "").lower().strip()
    matched = []
    for p in SELF_HARM_TERMS + EMERGENCY_TERMS:
        if p in t:
            matched.append(p)
    return {
        "is_self_harm": any(p in t for p in SELF_HARM_TERMS),
        "is_emergency_medical": any(p in t for p in EMERGENCY_TERMS),
        "matched_terms": sorted(list(set(matched))),
    }
