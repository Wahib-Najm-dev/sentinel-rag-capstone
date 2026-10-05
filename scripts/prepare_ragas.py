"""Offline RAGAS input preparation. No model, API, or Chroma client imports.

Default: print an unscored plan. --prepare-review exports exact gold evidence
from read-only SQLite. --check-reviewed validates human-reviewed references.
This is NOT the paid RAGAS evaluator and never creates evaluation scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_BLOB = "c908c6dce6434f7259db3af8991da7d8b41c563d"
COLLECTION = "sentinelrag_chunks"
SEED = "sentinelrag-ragas20-v1"
SAMPLE_COUNT = 20
PROTOCOL = "ragas20-reference-review-v1"


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_golden(path: Path, expected_blob: str = GOLDEN_BLOB) -> list[dict]:
    # Normalize only checkout line endings for comparison to the frozen Git blob.
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != expected_blob:
        raise ValueError("Golden Set differs from the frozen Git snapshot; review it explicitly.")
    rows = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(rows, list) or len(rows) != 30:
        raise ValueError("Expected exactly 30 Golden Questions.")
    if {row.get("id") for row in rows} != {f"q{i:02d}" for i in range(1, 31)}:
        raise ValueError("Question IDs must be unique q01 through q30.")
    for row in rows:
        if not isinstance(row.get("question"), str) or not row["question"].strip():
            raise ValueError("Every question needs nonempty text.")
        for field in ("gold_chunk_ids", "gold_source_ids"):
            values = row.get(field)
            if (not isinstance(values, list) or not values
                    or any(not isinstance(v, str) or not v for v in values)
                    or len(values) != len(set(values))):
                raise ValueError(f"Invalid {field} in {row['id']}.")
    return rows


def select_questions(rows: list[dict]) -> list[dict]:
    # Frozen ID-only sampling: never inspect previous hit/miss/score reports.
    ranked = sorted(rows, key=lambda row: (
        hashlib.sha256((SEED + "\0" + row["id"]).encode()).hexdigest(), row["id"]
    ))
    return sorted(ranked[:SAMPLE_COUNT], key=lambda row: row["id"])


def budget_plan(question_count: int = SAMPLE_COUNT, contexts: int = 5) -> dict:
    if question_count <= 0 or contexts <= 0:
        raise ValueError("Counts must be positive.")
    per_question = {"faithfulness": 2, "answer_relevancy_strictness_3": 3,
                    "context_precision_with_reference": contexts, "context_recall": 1}
    judge = question_count * sum(per_question.values())
    return {
        "status": "planning_estimate_not_usage_or_invoice",
        "ragas_version_under_review": "0.4.3",
        "question_count": question_count,
        "retrieved_contexts_per_question": contexts,
        "rerank_requests": question_count,
        "application_answer_requests": question_count,
        "judge_requests_by_metric": {k: v * question_count for k, v in per_question.items()},
        "judge_requests_total": judge,
        "cohere_requests_baseline": 2 * question_count + judge,
        "additional_reference_writing_api_requests": 0,
        "retries_and_failed_requests_included": False,
        "assumptions": "Fresh end-to-end answers, 5 contexts each; no cached answers or retries. Paid pilot must count toward the 20, not add extra questions.",
        "account_quota_remaining": None,
        "estimated_invoice_usd": None,
        "quota_note": "Inspect actual account usage before approval; do not assume previous remaining quota is current.",
    }


def read_gold_evidence(database: Path, questions: list[dict]) -> tuple[dict, str]:
    if not database.is_file():
        raise FileNotFoundError(database)
    before = digest_file(database)
    # mode=ro prevents writes and creation of a missing database.
    uri = database.resolve().as_uri() + "?mode=ro"
    wanted = sorted({cid for row in questions for cid in row["gold_chunk_ids"]})
    chunks: dict[str, dict] = {}
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        expected = {
            "collections": {"id", "name"}, "segments": {"id", "collection"},
            "embeddings": {"id", "segment_id", "embedding_id"},
            "embedding_metadata": {"id", "key", "string_value", "int_value"},
        }
        for table, columns in expected.items():
            found = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if not columns.issubset(found):
                raise ValueError(f"Unsupported SQLite schema in {table}; no writes performed.")
        collections = conn.execute("SELECT id FROM collections WHERE name=?", (COLLECTION,)).fetchall()
        if len(collections) != 1:
            raise ValueError("Expected one sentinelrag_chunks collection.")
        marks = ",".join("?" for _ in wanted)
        query = f"""SELECT e.id,e.embedding_id,m.key,m.string_value,m.int_value
          FROM embeddings e JOIN segments s ON s.id=e.segment_id
          JOIN embedding_metadata m ON m.id=e.id
          WHERE s.collection=? AND e.embedding_id IN ({marks})"""
        row_ids: dict[str, int] = {}
        for record_id, cid, key, string_value, int_value in conn.execute(query, (collections[0][0], *wanted)):
            if cid in row_ids and row_ids[cid] != record_id:
                raise ValueError(f"Ambiguous duplicate chunk: {cid}")
            row_ids[cid] = record_id
            chunks.setdefault(cid, {})[key] = string_value if string_value is not None else int_value
    if digest_file(database) != before:
        raise RuntimeError("Database bytes changed during review; stop and investigate.")
    for cid in wanted:
        row = chunks.get(cid, {})
        if not isinstance(row.get("chroma:document"), str) or not row["chroma:document"].strip():
            raise ValueError(f"Missing nonempty gold evidence: {cid}")
    for question in questions:
        for cid in question["gold_chunk_ids"]:
            if chunks[cid].get("source_id") not in question["gold_source_ids"]:
                raise ValueError(f"Gold source mismatch: {question['id']}/{cid}")
    return chunks, before


def make_packet(rows: list[dict], database: Path) -> dict:
    selected = select_questions(rows)
    chunks, database_sha = read_gold_evidence(database, selected)
    questions = []
    for row in selected:
        evidence = []
        for cid in row["gold_chunk_ids"]:
            chunk = chunks[cid]
            evidence.append({
                "chunk_id": cid, "source_id": chunk.get("source_id"),
                "title": chunk.get("title"), "page": chunk.get("page"),
                "section_id": chunk.get("section_id"), "text": chunk["chroma:document"],
                "text_sha256": hashlib.sha256(chunk["chroma:document"].encode()).hexdigest(),
            })
        questions.append({
            "id": row["id"], "user_input": row["question"], "topic": row.get("topic"),
            "gold_chunk_ids": row["gold_chunk_ids"], "gold_source_ids": row["gold_source_ids"],
            "gold_evidence": evidence, "reference": "", "review_status": "pending",
            "reviewed_by": "", "review_notes": "",
        })
    return {"protocol": PROTOCOL, "status": "needs_reference_review",
            "selection_seed": SEED, "golden_git_blob": GOLDEN_BLOB,
            "golden_semantic_sha256": canonical_digest(rows), "index_sha256": database_sha,
            "questions": questions, "budget_plan": budget_plan(),
            "scores": None, "api_calls_performed": 0}


def validate_review(packet: dict, rows: list[dict]) -> list[str]:
    expected = select_questions(rows)
    if packet.get("protocol") != PROTOCOL:
        raise ValueError("Wrong review protocol.")
    if packet.get("golden_semantic_sha256") != canonical_digest(rows):
        raise ValueError("Golden snapshot does not match the packet.")
    actual = packet.get("questions", [])
    if [r.get("id") for r in actual] != [r["id"] for r in expected]:
        raise ValueError("Selection must remain frozen at exactly the selected 20 IDs.")
    blockers = []
    for saved, original in zip(actual, expected):
        if saved.get("user_input") != original["question"] or any(
            saved.get(k) != original[k] for k in ("gold_chunk_ids", "gold_source_ids")
        ):
            raise ValueError("Question text and Golden Labels must not change.")
        evidence = saved.get("gold_evidence", [])
        if [e.get("chunk_id") for e in evidence] != original["gold_chunk_ids"]:
            raise ValueError("Reference evidence IDs changed.")
        for chunk in evidence:
            if hashlib.sha256(chunk["text"].encode()).hexdigest() != chunk.get("text_sha256"):
                raise ValueError("Reference evidence text changed.")
        if (not isinstance(saved.get("reference"), str) or not saved["reference"].strip()
                or saved.get("review_status") != "approved"
                or not isinstance(saved.get("reviewed_by"), str) or not saved["reviewed_by"].strip()):
            blockers.append(saved["id"])
    return blockers


def export_packet(packet: dict, output: Path) -> None:
    if output.exists():
        raise FileExistsError("Output exists; preserve reviewed work instead of overwriting it.")
    if output.resolve().is_relative_to((ROOT / "data/index").resolve()):
        raise ValueError("Do not export into the index directory.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="ragas-review-", dir=output.parent))
    try:
        (temp / "ragas20_reference_review.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md = ["# RAGAS 20-question reference review", "", "NOT a score report. No API calls made.",
              "Write and review references using only the frozen gold evidence below.",
              "Do not use the application answer or a previous retrieval score as ground truth.", ""]
        for row in packet["questions"]:
            md.extend([f"## {row['id']}: {row['user_input']}", "", "Reference: **PENDING HUMAN REVIEW**", ""])
            for evidence in row["gold_evidence"]:
                md.extend([f"### {evidence['chunk_id']}",
                           f"Source: {evidence['source_id']} | Page: {evidence['page']} | Section: {evidence['section_id']}",
                           "", evidence["text"], ""])
        (temp / "ragas20_reference_review.md").write_text("\n".join(md), encoding="utf-8")
        temp.rename(output)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=ROOT / "data/eval/golden_questions.json")
    parser.add_argument("--index", type=Path, default=ROOT / "data/index/chroma.sqlite3")
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/ragas-review")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-review", action="store_true")
    mode.add_argument("--check-reviewed", type=Path)
    args = parser.parse_args()
    rows = load_golden(args.golden)
    selected = select_questions(rows)
    print("SELECTED_IDS=" + ",".join(r["id"] for r in selected))
    print("QUESTIONS=20; COHERE_CALLS=0; RAGAS_SCORES=NOT_RUN")
    if args.check_reviewed:
        packet = json.loads(args.check_reviewed.read_text(encoding="utf-8"))
        blockers = validate_review(packet, rows)
        print("REFERENCES_PENDING=" + str(len(blockers)))
        if blockers:
            print("BLOCKED_IDS=" + ",".join(blockers))
            return 2
        print("REFERENCE_STRUCTURE=PASSED; SEMANTIC_APPROVAL_IS_HUMAN_RESPONSIBILITY")
    elif args.prepare_review:
        packet = make_packet(rows, args.index)
        export_packet(packet, args.output)
        print("REFERENCE_EVIDENCE_EXTRACTED=YES; SQLITE_MODE=READ_ONLY; DATABASE_BYTES_UNCHANGED=YES")
        print("REFERENCES_PENDING=20; SCORES=NOT_CREATED")
        print("OUTPUT=" + str(args.output))
    else:
        print(json.dumps(budget_plan(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
