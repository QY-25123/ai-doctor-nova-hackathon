#!/usr/bin/env python3
"""
Load docs/medical_kb markdown files, chunk, embed via Bedrock, save FAISS index to .data/.
Run from repo root or set MEDICAL_KB_PATH. Requires network for embeddings.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Ensure services/api is on path so app.rag and app.rag.embeddings resolve
SCRIPT_DIR = Path(__file__).resolve().parent
API_ROOT = SCRIPT_DIR.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import numpy as np

from app.rag.embeddings import embed_text


def find_kb_path(env_path: str | None, default_relative: str = "docs/medical_kb") -> Path:
    """Resolve medical_kb directory: env MEDICAL_KB_PATH or repo_root/docs/medical_kb."""
    if env_path and os.path.isabs(env_path):
        return Path(env_path)
    if env_path:
        return (API_ROOT / env_path).resolve()
    # Repo root: one level up from services/api
    repo_root = API_ROOT.parent
    return (repo_root / default_relative).resolve()


def chunk_markdown(content: str, source: str, title: str, url: str, max_chars: int = 1200, overlap: int = 100) -> list[dict]:
    """Split by ## sections first; then by size with overlap. Each chunk = {source, title, url, content}."""
    chunks = []
    # Section split by ## or ###
    sections = re.split(r"\n(?=#{2,3}\s)", content.strip())
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        # First line may be header
        lines = sec.split("\n")
        sec_title = title
        if lines and re.match(r"^#{2,3}\s", lines[0]):
            sec_title = re.sub(r"^#{2,3}\s*", "", lines[0]).strip()
        text = "\n".join(lines).strip()
        if len(text) <= max_chars:
            if text:
                chunks.append({"source": source, "title": sec_title, "url": url, "content": text})
        else:
            # Fixed-size windows with overlap
            start = 0
            while start < len(text):
                end = min(start + max_chars, len(text))
                snippet = text[start:end]
                if snippet.strip():
                    chunks.append({"source": source, "title": sec_title, "url": url, "content": snippet.strip()})
                start = end - overlap
                if start >= len(text):
                    break
    return chunks


def load_md_files(kb_path: Path) -> list[tuple[str, str, str, str]]:
    """Return list of (file_path, title, url, content). title from first # line or filename."""
    if not kb_path.is_dir():
        return []
    out = []
    for path in sorted(kb_path.rglob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Skip {path}: {e}", file=sys.stderr)
            continue
        title = path.stem
        for line in raw.split("\n"):
            m = re.match(r"^#\s+(.+)$", line.strip())
            if m:
                title = m.group(1).strip()
                break
        # URL: relative path for offline (e.g. docs/medical_kb/foo.md)
        try:
            rel = path.relative_to(kb_path)
            url = f"docs/medical_kb/{rel.as_posix()}"
        except ValueError:
            url = path.name
        out.append((path.name, title, url, raw))
    return out


def main():
    parser = argparse.ArgumentParser(description="Ingest docs/medical_kb into FAISS index")
    parser.add_argument("--kb-path", default=os.getenv("MEDICAL_KB_PATH"), help="Override medical_kb directory")
    parser.add_argument("--output-dir", default=None, help="Override .data output dir (default: services/api/.data)")
    args = parser.parse_args()

    kb_path = find_kb_path(args.kb_path)
    if not kb_path.is_dir():
        print(f"KB path not found: {kb_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else API_ROOT / ".data"
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "faiss.index"
    meta_path = output_dir / "faiss_meta.json"

    files = load_md_files(kb_path)
    if not files:
        print("No .md files found under", kb_path, file=sys.stderr)
        sys.exit(0)

    all_chunks = []
    for source, title, url, content in files:
        all_chunks.extend(chunk_markdown(content, source, title, url))

    if not all_chunks:
        print("No chunks produced.", file=sys.stderr)
        sys.exit(0)

    print(f"Embedding {len(all_chunks)} chunks via Bedrock...", file=sys.stderr)
    vectors = []
    for i, ch in enumerate(all_chunks):
        vec = embed_text(ch["content"])
        vectors.append(vec)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(all_chunks)}", file=sys.stderr)

    matrix = np.array(vectors, dtype=np.float32)
    dim = matrix.shape[1]
    faiss = __import__("faiss")
    index = faiss.IndexFlatL2(dim)
    index.add(matrix)

    faiss.write_index(index, str(index_path))
    meta_list = [
        {"source": c["source"], "title": c["title"], "url": c["url"], "content": c["content"]}
        for c in all_chunks
    ]
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False, indent=0)

    print(f"Wrote {index_path} and {meta_path} ({len(all_chunks)} chunks)", file=sys.stderr)


if __name__ == "__main__":
    main()
