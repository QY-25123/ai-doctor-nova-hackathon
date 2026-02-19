"""
Nova API via official OpenAI-compatible client. English-only.
Strict JSON mode, extraction, and repair retry for schema outputs.
"""

import json
import os
import re
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

_client: OpenAI | None = None

NOVA_API_KEY = (os.getenv("NOVA_API_KEY") or "").strip()
NOVA_API_BASE_URL = (os.getenv("NOVA_API_BASE_URL") or "https://api.nova.amazon.com/v1").rstrip("/")
NOVA_MODEL_ID = os.getenv("NOVA_MODEL_ID", "nova-2-pro-v1")


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not NOVA_API_KEY:
            raise ValueError(
                "NOVA_API_KEY is required. Set it in the environment or .env."
            )
        _client = OpenAI(
            api_key=NOVA_API_KEY,
            base_url=NOVA_API_BASE_URL,
        )
    return _client


def _build_messages(messages: list[dict], system_prompt: str | None) -> list[dict]:
    """Build messages: optional system first, then conversation."""
    full_messages: list[dict] = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        full_messages.append({"role": role, "content": str(content)})
    return full_messages


def invoke_nova(
    messages: list[dict],
    system_prompt: str | None = None,
    *,
    model_id: str | None = None,
    timeout_sec: int | None = None,
    response_format: dict | None = None,
    temperature: float | None = None,
) -> str:
    """
    Call Nova API (OpenAI-compatible). Returns the assistant text.
    messages: list of {"role": "user"|"assistant", "content": "..."}
    response_format: e.g. {"type": "json_object"} for strict JSON when supported.
    """
    client = _get_client()
    full_messages = _build_messages(messages, system_prompt)
    model = model_id or NOVA_MODEL_ID
    kwargs: dict = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature if temperature is not None else 0.2,
        "stream": False,
    }
    if timeout_sec is not None:
        kwargs["timeout"] = timeout_sec
    if response_format is not None:
        kwargs["response_format"] = response_format
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as e:
        # Fallback if API does not support response_format (e.g. 400)
        if response_format is not None and "response_format" in str(e).lower():
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
        else:
            raise
    content = response.choices[0].message.content
    return (content or "").strip()


def extract_json_from_text(text: str) -> str:
    """
    Extract a JSON string from model output: strip whitespace, strip code fences,
    or take substring from first "{" to last "}".
    """
    text = (text or "").strip()
    if not text:
        return ""

    # Code block: ```json ... ``` or ``` ... ```
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if code_block:
        return code_block.group(1).strip()

    # Embedded JSON: first "{" to last "}"
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return text[start : end + 1]

    return text


# Schema description for repair prompt (FinalAssessmentResponse) with substantive minimums
FINAL_ASSESSMENT_SCHEMA_DESC = (
    "JSON object with exactly these keys and minimum content: "
    '"risk_level" (one of: SELF_CARE, ROUTINE, URGENT, EMERGENCY); '
    '"summary" (array of 3-6 strings: what it might be, what info is missing, what to do next); '
    '"possible_causes" (at least 3 strings); '
    '"home_care" (at least 5 concrete steps, e.g. fluids, rest, OTC, triggers to avoid); '
    '"when_to_seek_care" (at least 5 items including red flags); '
    '"red_flags" (at least 3 items tailored to the symptom); '
    'optional "sources_query" (array of strings). '
    "No generic filler; no repeated disclaimers."
)

REPAIR_SYSTEM = (
    "You are a clinical triage assistant. Produce complete, specific guidance. Output JSON only. "
    "No markdown, no code fences, no explanation."
)


def _repair_user_message(original_model_output: str, user_symptom: str | None = None) -> str:
    parts = [
        "Required JSON schema: " + FINAL_ASSESSMENT_SCHEMA_DESC,
        "",
        "If the previous model output was generic or incomplete, regenerate a full triage response from scratch based on the user's symptom. Otherwise convert the output below to valid JSON matching the schema.",
        "",
    ]
    if user_symptom:
        parts.extend(["User's symptom(s):", user_symptom.strip(), ""])
    parts.extend(["Previous model output:", original_model_output])
    return "\n".join(parts)


T = TypeVar("T", bound=BaseModel)


def invoke_nova_json(
    messages: list[dict],
    system_prompt: str,
    response_model: type[T],
    *,
    model_id: str | None = None,
    timeout_sec: int | None = None,
    user_symptom_for_repair: str | None = None,
) -> T:
    """
    Call Nova with strict JSON mode (response_format + temperature=0), extract
    JSON from response (strip fences / embedded object), validate with Pydantic.
    On first parse failure: retry once with a repair call (includes user symptom and
    "regenerate from scratch if generic"); log first_pass / repaired / failed_final.
    """
    from app.logging_structured import (
        log_nova_parse_failed_first_pass,
        log_nova_parse_failed_final,
        log_nova_parse_repaired,
    )

    json_instruction = (
        "Respond only with a single valid JSON object. "
        "No markdown, no code fences, no explanation before or after."
    )
    full_system = f"{system_prompt}\n\n{json_instruction}"

    # Initial call: strict JSON mode + determinism
    raw = invoke_nova(
        messages,
        full_system,
        model_id=model_id,
        timeout_sec=timeout_sec,
        response_format={"type": "json_object"},
        temperature=0,
    )
    text = extract_json_from_text(raw)

    def parse(text_to_parse: str) -> T:
        cleaned = extract_json_from_text(text_to_parse)
        if not cleaned:
            raise ValueError("No JSON extracted from response")
        return response_model.model_validate_json(cleaned)

    try:
        return parse(text)
    except (ValueError, ValidationError, json.JSONDecodeError):
        log_nova_parse_failed_first_pass(response_snippet=(text or raw)[:500])
        # Retry once with repair: include user symptom and regenerate-if-generic instruction
        repair_messages = [
            {"role": "system", "content": REPAIR_SYSTEM},
            {"role": "user", "content": _repair_user_message(raw, user_symptom_for_repair)},
        ]
        repair_raw = invoke_nova(
            repair_messages,
            system_prompt=None,
            model_id=model_id,
            timeout_sec=timeout_sec,
            response_format={"type": "json_object"},
            temperature=0,
        )
        try:
            repaired = parse(repair_raw)
            log_nova_parse_repaired()
            return repaired
        except (ValueError, ValidationError, json.JSONDecodeError) as e2:
            log_nova_parse_failed_final(response_snippet=(repair_raw or "")[:500])
            raise ValueError(f"LLM response did not match schema after repair: {e2}") from e2


def repair_final_assessment_for_quality(
    user_symptom: str,
    system_prompt: str,
    response_model: type[T],
    *,
    model_id: str | None = None,
    timeout_sec: int | None = None,
) -> T:
    """
    One-shot Nova call to produce a substantive triage response for the given
    user symptom (used when first-pass output failed quality check). Uses same
    schema constraints and temperature=0, response_format=json_object.
    """
    messages = [{"role": "user", "content": user_symptom.strip()}]
    return invoke_nova_json(
        messages,
        system_prompt,
        response_model,
        model_id=model_id,
        timeout_sec=timeout_sec,
    )
