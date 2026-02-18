import os
import time
from typing import TypeVar

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ValidationError

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
DEFAULT_TIMEOUT_SEC = 60
MAX_RETRIES = 3
INITIAL_BACKOFF_SEC = 1.0

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            config=Config(
                connect_timeout=10,
                read_timeout=DEFAULT_TIMEOUT_SEC,
                retries={"mode": "standard", "max_attempts": 0},
            ),
        )
    return _client


def _messages_to_bedrock(messages: list[dict]) -> list[dict]:
    """Convert [{"role": "user"|"assistant", "content": "..."}] to Bedrock Converse format."""
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, str):
            content = [{"text": content}]
        out.append({"role": role, "content": content})
    return out


def invoke_nova(
    messages: list[dict],
    system_prompt: str,
    *,
    model_id: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """
    Invoke Bedrock Nova (or configured model) via Converse API.
    messages: list of {"role": "user"|"assistant", "content": "..."}
    Returns the assistant text response.
    """
    model_id = model_id or BEDROCK_MODEL_ID
    client = _get_client()
    bedrock_messages = _messages_to_bedrock(messages)
    system = [{"text": system_prompt}]

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.converse(
                modelId=model_id,
                messages=bedrock_messages,
                system=system,
                inferenceConfig={"maxTokens": 4096, "temperature": 0.7},
            )
            # Converse response: output.message.content[].text
            output = response.get("output", {})
            msg = output.get("message", {})
            content_blocks = msg.get("content", [])
            if not content_blocks:
                return ""
            text = content_blocks[0].get("text", "")
            return text.strip()
        except (ClientError, BotoCoreError, OSError) as e:
            # OSError includes read timeout and connection errors
            last_error = e
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
    Raises ValidationError if the response is not valid JSON or does not match the model.
    """
    json_instruction = (
        "Respond only with a single valid JSON object. "
        "No markdown, no code fences, no explanation before or after."
    )
    full_system = f"{system_prompt}\n\n{json_instruction}"
    raw = invoke_nova(messages, full_system, model_id=model_id, timeout_sec=timeout_sec)
    # Strip possible markdown code block
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
