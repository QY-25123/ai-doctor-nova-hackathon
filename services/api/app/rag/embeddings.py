"""
Bedrock embeddings for RAG. Configurable model via BEDROCK_EMBED_MODEL_ID.
Only this module (and LLM client) need network; FAISS and file I/O are local.
"""

import json
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

BEDROCK_EMBED_MODEL_ID = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
_embed_client = None


def _get_embed_client():
    global _embed_client
    if _embed_client is None:
        _embed_client = boto3.client(
            "bedrock-runtime",
            config=Config(connect_timeout=10, read_timeout=30),
        )
    return _embed_client


def embed_text(text: str, *, model_id: str | None = None) -> list[float]:
    """
    Return embedding vector for one text via Bedrock Titan (or configured model).
    Raises on network/API errors.
    """
    model_id = model_id or BEDROCK_EMBED_MODEL_ID
    client = _get_embed_client()
    body = json.dumps({"inputText": text})
    response = client.invoke_model(modelId=model_id, body=body, contentType="application/json")
    result = json.loads(response["body"].read())
    return result["embedding"]
