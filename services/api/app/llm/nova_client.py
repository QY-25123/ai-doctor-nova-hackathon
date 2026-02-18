"""
Nova API (HTTP) client. API key auth; OpenAI-compatible chat completions.
"""

import os
import time
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

NOVA_API_KEY = os.getenv("NOVA_API_KEY")
NOVA_MODEL_ID = os.getenv("NOVA_MODEL_ID", "nova-2-pro-v1")
NOVA_API_BASE_URL = (os.getenv("NOVA_API_BASE_URL") or "https://api.nova.amazon.com").rstrip("/")
DEFAULT_TIMEOUT_SEC = 60
MAX_RETRIES = 3
INITIAL_BACKOFF_SEC = 1.0


def _check_config() -> None:
    if not (NOVA_API_KEY and NOVA_API_KEY.strip()):
        raise ValueError(
            "NOVA_API_KEY is required. Set it in the environment or .env."
        )


def _build_messages(messages: list[dict], system_prompt: str) -> list[dict]:
    """Build OpenAI-style messages: system first, then conversation."""
    out = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        out.append({"role": role, "content": str(content)})
    return out


def invoke_nova(
    messages: list[dict],
    system_prompt: str,
    *,
    model_id: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """
    Call Nova API (OpenAI-compatible chat completions).
    messages: list of {"role": "user"|"assistant", "content": "..."}
    Returns the assistant text response.
    """
    _check_config()
    model_id = model_id or NOVA_MODEL_ID
    url = f"{NOVA_API_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NOVA_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_id,
        "messages": _build_messages(messages, system_prompt),
        "max_tokens": 4096,
        "temperature": 0.7,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=timeout_sec,
            )
            if resp.status_code == 401:
                raise ValueError(
                    "Nova API 401 Unauthorized. Check NOVA_API_KEY is correct and not expired."
                )
            if resp.status_code == 403:
                raise ValueError(
                    "Nova API 403 Forbidden. Check API key has access to the requested model and region."
                )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message") or {}
            text = message.get("content") or ""
            return text.strip()
        except requests.exceptions.RequestException as e:
            last_error = e
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code in (401, 403):
                if resp.status_code == 401:
                    raise ValueError(
                        "Nova API 401 Unauthorized. Check NOVA_API_KEY is correct and not expired."
                    ) from e
                raise ValueError(
                    "Nova API 403 Forbidden. Check API key has access to the requested model and region."
                ) from e
            if attempt < MAX_RETRIES - 1:
                backoff = INITIAL_BACKOFF_SEC * (2**attempt)
                time.sleep(backoff)
            else:
                raise
    if last_error is not None:
        raise last_error
    return ""


T = TypeVar("T", bound=BaseModel)


def invoke_nova_json(
    messages: list[dict],
    system_prompt: str,
    response_model: type[T],
    *,
    model_id: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> T:
    """
    Call invoke_nova with a system prompt that forces JSON output, then parse
    and validate the response with the given Pydantic model.
    """
    json_instruction = (
        "Respond only with a single valid JSON object. "
        "No markdown, no code fences, no explanation before or after."
    )
    full_system = f"{system_prompt}\n\n{json_instruction}"
    raw = invoke_nova(messages, full_system, model_id=model_id, timeout_sec=timeout_sec)
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return response_model.model_validate_json(text)
    except ValidationError as e:
        raise ValueError(f"LLM response did not match schema: {e}") from e
