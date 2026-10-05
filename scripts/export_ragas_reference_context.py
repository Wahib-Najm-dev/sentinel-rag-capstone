"""Export reference-review context from two frozen sources, without retrieval or APIs."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_SHA256 = "bab9519517382c1161d05fe0d68857d02b0123c099c1615486e159921d22064c"
SOURCE_IDS = ("owasp_logging", "owasp_forgot_password")


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_sources(database: Path) -> list[dict]:
    if not database.is_file() or digest_file(database) != INDEX_SHA256:
        raise ValueError("Expected the unchanged frozen index snapshot.")
    uri = database.resolve().as_uri() + "?mode=ro"
    records: dict[int, dict] = {}
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        query = """SELECT e.id, e.embedding_id, m.key, m.string_value, m.int_value
            FROM embeddings e JOIN segments s ON s.id=e.segment_id
            JOIN collections c ON c.id=s.collection
            JOIN embedding_metadata m ON m.id=e.id
            WHERE c.name=? AND EXISTS (
                SELECT 1 FROM embedding_metadata src WHERE src.id=e.id
                AND src.key='source_id' AND src.string_value IN (?,?)
            )"""
        for rid, cid, key, string_value, int_value in connection.execute(query, ("sentinelrag_chunks", *SOURCE_IDS)):
            row = records.setdefault(rid, {"chunk_id": cid})
            row[key] = string_value if string_value is not None else int_value
    if digest_file(database) != INDEX_SHA256:
        raise RuntimeError("Database bytes changed during the read.")
    chunks = []
    for row in records.values():
        text = row.get("chroma:document")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Missing source text.")
        chunks.append({"chunk_id": row["chunk_id"], "source_id": row["source_id"],
                       "title": row.get("title"), "page": row.get("page"),
                       "section_id": row.get("section_id"), "chunk_index": row.get("chunk_index"),
                       "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    if len({r["chunk_id"] for r in chunks}) != len(chunks):
        raise ValueError("Duplicate source chunks.")
    if {r["source_id"] for r in chunks} != set(SOURCE_IDS):
        raise ValueError("Missing source.")
    return sorted(chunks, key=lambda r: (r["source_id"], str(r["chunk_index"]), r["chunk_id"]))


def main() -> None:
    output = ROOT / ".cache/ragas-reference-context.json"
    if output.exists():
        raise FileExistsError("Preserve existing review evidence; do not overwrite it.")
    chunks = read_sources(ROOT / "data/index/chroma.sqlite3")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"index_sha256": INDEX_SHA256,
        "purpose": "Reference-answer coverage review only; not replacement Golden Labels or retrieval results.",
        "source_ids": list(SOURCE_IDS), "chunks": chunks,
        "golden_labels_changed": False, "api_calls": 0}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("SOURCE_CONTEXT_CHUNKS=" + str(len(chunks)))
    print("SQLITE=READ_ONLY; GOLDEN_LABELS=UNCHANGED; COHERE_CALLS=0")


if __name__ == "__main__":
    main()
