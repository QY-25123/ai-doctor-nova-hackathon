"""
Local RAG: load FAISS index + metadata from .data/, retrieve_top_k returns chunks.
Runnable offline except embed_text (Bedrock) when querying.
"""

import json
import os
from pathlib import Path

import numpy as np

# Lazy import faiss so rest of app can load without faiss installed for tests
def _faiss():
    import faiss
    return faiss

DATA_DIR = Path(__file__).resolve().parent.parent.parent / ".data"
INDEX_PATH = DATA_DIR / "faiss.index"
META_PATH = DATA_DIR / "faiss_meta.json"


def _load_index_and_meta():
    if not INDEX_PATH.exists() or not META_PATH.exists():
        return None, None
    faiss = _faiss()
    index = faiss.read_index(str(INDEX_PATH))
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta


def retrieve_top_k(
    query: str,
    k: int,
    *,
    embed_fn=None,
) -> list[dict]:
    """
    Return top-k chunks for query. Each chunk: {source, title, url, content}.
    embed_fn(text) -> list[float]; if None, uses app.rag.embeddings.embed_text (requires network).
    """
    index, meta = _load_index_and_meta()
    if index is None or meta is None:
        return []
    if not meta:
        return []

    if embed_fn is None:
        from app.rag.embeddings import embed_text as _embed
        embed_fn = _embed

    query_vec = np.array([embed_fn(query)], dtype=np.float32)
    n = index.ntotal
    k = min(k, n)
    distances, indices = index.search(query_vec, k)

    out = []
    for idx in indices[0]:
        if 0 <= idx < len(meta):
            out.append({**meta[idx]})
    return out
