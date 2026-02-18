"""
English-only keyword and pattern rules for emergency symptoms. Conservative: any hit triggers EMERGENCY.
Case-insensitive with simple regex variants. Returns matched terms for override red_flags and logging.
"""

import re
from typing import NamedTuple

# (phrase, label for red_flags)
_CHEST = [
    "chest pain",
    "severe chest pain",
    "pressure in chest",
    "chest pressure",
    "pain in chest",
    "crushing chest",
]
_BREATHING = [
    "shortness of breath",
    "difficulty breathing",
    "trouble breathing",
    "cannot breathe",
    "can't breathe",
    "can not breathe",
]
_COLD_SWEAT_CHEST = [
    "cold sweat",
    "cold sweats",
    "sweating and chest",
    "sweat and chest",
]
_UNCONSCIOUS = [
    "fainting",
    "passed out",
    "loss of consciousness",
    "unconscious",
    "collapse",
    "collapsed",
]
_STROKE = [
    "face droop",
    "arm weakness",
    "slurred speech",
    "drooping face",
    "weakness in arm",
]
_BLEEDING = [
    "severe bleeding",
    "coughing blood",
    "vomiting blood",
    "heavy bleeding",
    "bleeding heavily",
]
_SUICIDE_SELF_HARM = [
    "suicidal thoughts",
    "suicidal thought",
    "self-harm",
    "self harm",
    "hurt myself",
    "kill myself",
    "want to die",
    "end my life",
]
_OVERDOSE_POISONING = [
    "overdose",
    "overdosed",
    "poisoning",
    "poisoned",
]

# Flat list of keywords (lowercase for matching)
_ALL_KEYWORDS: list[str] = []
_LABEL_BY_KEY: dict[str, str] = {}
for _group in (_CHEST, _BREATHING, _COLD_SWEAT_CHEST, _UNCONSCIOUS, _STROKE, _BLEEDING, _SUICIDE_SELF_HARM, _OVERDOSE_POISONING):
    for _p in _group:
        _k = _p.lower()
        _ALL_KEYWORDS.append(_k)
        _LABEL_BY_KEY[_k] = _p

# Regex patterns (case-insensitive); capture group or use label from first group
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"chest\s+pain", re.I), "chest pain"),
    (re.compile(r"pressure\s+in\s+(?:my\s+)?chest", re.I), "pressure in chest"),
    (re.compile(r"shortness\s+of\s+breath", re.I), "shortness of breath"),
    (re.compile(r"difficult(y|ies)\s+breathing", re.I), "difficulty breathing"),
    (re.compile(r"trouble\s+breathing", re.I), "trouble breathing"),
    (re.compile(r"can'?t\s+breathe", re.I), "trouble breathing"),
    (re.compile(r"cold\s+sweat(s)?", re.I), "cold sweat(s)"),
    (re.compile(r"sweat(ing)?\s+.*chest|chest.*sweat", re.I), "sweating + chest pain"),
    (re.compile(r"passed\s+out", re.I), "passed out"),
    (re.compile(r"loss\s+of\s+consciousness", re.I), "loss of consciousness"),
    (re.compile(r"face\s+droop|droop(ing)?\s+face", re.I), "face droop"),
    (re.compile(r"arm\s+weakness|weakness\s+in\s+arm", re.I), "arm weakness"),
    (re.compile(r"slurred\s+speech", re.I), "slurred speech"),
    (re.compile(r"severe\s+bleeding", re.I), "severe bleeding"),
    (re.compile(r"coughing\s+blood|vomiting\s+blood", re.I), "coughing/vomiting blood"),
    (re.compile(r"suicidal\s+thoughts?", re.I), "suicidal thoughts"),
    (re.compile(r"self[\s\-]harm", re.I), "self-harm"),
    (re.compile(r"overdose(d)?", re.I), "overdose"),
    (re.compile(r"poison(ed|ing)?", re.I), "poisoning"),
]


class RedFlagMatch(NamedTuple):
    hit: bool
    matched_terms: list[str]


def check_red_flags(text: str) -> RedFlagMatch:
    """
    Return (hit, matched_terms). hit is True if any emergency keyword/pattern matches.
    matched_terms are human-readable labels for red_flags and logging. Case-insensitive.
    """
    if not text or not text.strip():
        return RedFlagMatch(False, [])
    lower = text.lower().strip()
    matched: list[str] = []
    seen: set[str] = set()

    for kw in _ALL_KEYWORDS:
        if kw in lower:
            label = _LABEL_BY_KEY.get(kw, kw)
            if label not in seen:
                seen.add(label)
                matched.append(label)

    for pat, label in _PATTERNS:
        if pat.search(text) or pat.search(lower):
            if label not in seen:
                seen.add(label)
                matched.append(label)

    return RedFlagMatch(len(matched) > 0, matched)
