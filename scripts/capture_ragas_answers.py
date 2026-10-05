"""Capture genuine SentinelRAG outputs for the frozen RAGAS-20 sample.

Default mode performs validation only and makes zero model/provider calls.
Live capture is explicit, resumable, and never reads reference answers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_ragas import GOLDEN_BLOB, load_golden, select_questions
from scripts.ragas_execution import IDS, canonical, digest

PIPELINE_COMMIT = "8309d67b917945f75692931aca77c68915a72c19"
INDEX_SHA256 = "bab9519517382c1161d05fe0d68857d02b0123c099c1615486e159921d22064c"
REFERENCE_HASH = "5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39"
RETRIEVAL_CONFIG = {"vector_top_k": 25, "bm25_top_k": 20, "rrf_k": 60, "top_n": 5}
RUNTIME_PATHS = (
    "src/rag_pipeline.py", "src/retrieval.py", "src/reranker.py", "src/llm.py",
    "src/config.py", "src/embedding_client.py", "src/bm25_index.py",
)
APPROVAL_PROTOCOL = "ragas20-reference-approval-v1"


class CaptureUncertain(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_reference_approval(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "protocol": APPROVAL_PROTOCOL,
        "status": "approved",
        "reference_set_sha256": REFERENCE_HASH,
        "approved_by": "project_owner",
        "scope": "reference_answers_only",
        "human_expert_review_claimed": False,
        "paid_or_trial_api_execution_authorized": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise ValueError("Invalid reference approval field: " + key)
    if value.get("approval_message") != "يعتمد" or value.get("approval_timestamp_utc") != "2026-10-05T05:05:55Z":
        raise ValueError("Approval record does not match the explicit user approval.")
    return value


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True)


def verify_runtime_source() -> dict:
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        raise ValueError("Capture must run from a Git checkout.")
    if git("cat-file", "-e", PIPELINE_COMMIT + "^{commit}").returncode != 0:
        raise ValueError("Frozen pipeline commit is unavailable in this checkout.")
    changed = git("diff", "--name-only", PIPELINE_COMMIT, "--", *RUNTIME_PATHS)
    if changed.returncode != 0 or changed.stdout.strip():
        raise ValueError("Runtime source differs from the frozen pipeline snapshot: " + changed.stdout.strip())
    unstaged = git("diff", "--name-only", "--", *RUNTIME_PATHS)
    staged = git("diff", "--cached", "--name-only", "--", *RUNTIME_PATHS)
    if unstaged.stdout.strip() or staged.stdout.strip():
        raise ValueError("Uncommitted runtime-source changes are not allowed during capture.")
    return {"pipeline_commit": PIPELINE_COMMIT, "runtime_paths": list(RUNTIME_PATHS)}


def atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = canonical(value) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != body:
            raise ValueError("Refusing to overwrite existing capture data: " + str(path))
        return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(body, encoding="utf-8")
    temp.replace(path)


def stage_file(state_dir: Path, qid: str, stage: str) -> Path:
    return state_dir / "stages" / f"{qid}.{stage}.json"


def reserve_stage(state_dir: Path, qid: str, stage: str, fingerprint: str) -> None:
    path = stage_file(state_dir, qid, stage)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") != fingerprint:
            raise ValueError("Capture stage fingerprint changed: " + str(path))
        if old.get("status") == "complete":
            return
        raise CaptureUncertain("Previous reserved/failed capture stage requires manual reconciliation: " + str(path))
    atomic_write(path, {
        "protocol": "sentinelrag-capture-stage-v1", "id": qid, "stage": stage,
        "fingerprint": fingerprint, "status": "reserved", "started_unix": time.time(),
    })


def complete_stage(state_dir: Path, qid: str, stage: str, fingerprint: str, result: dict) -> None:
    path = stage_file(state_dir, qid, stage)
    old = json.loads(path.read_text(encoding="utf-8"))
    if old.get("status") != "reserved" or old.get("fingerprint") != fingerprint:
        raise ValueError("Stage is not the expected reservation.")
    body = {
        "protocol": "sentinelrag-capture-stage-v1", "id": qid, "stage": stage,
        "fingerprint": fingerprint, "status": "complete", "started_unix": old["started_unix"],
        "finished_unix": time.time(), "result": result, "result_sha256": digest(result),
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(canonical(body) + "\n", encoding="utf-8")
    temp.replace(path)


def fail_stage(state_dir: Path, qid: str, stage: str, fingerprint: str, exc: BaseException) -> None:
    path = stage_file(state_dir, qid, stage)
    if not path.exists():
        return
    old = json.loads(path.read_text(encoding="utf-8"))
    if old.get("fingerprint") != fingerprint or old.get("status") != "reserved":
        return
    old.update({"status": "failed", "finished_unix": time.time(), "error_type": type(exc).__name__})
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(canonical(old) + "\n", encoding="utf-8")
    temp.replace(path)


def read_complete(state_dir: Path, qid: str, stage: str, fingerprint: str):
    path = stage_file(state_dir, qid, stage)
    if not path.exists():
        return None
    row = json.loads(path.read_text(encoding="utf-8"))
    if row.get("fingerprint") != fingerprint:
        raise ValueError("Capture stage fingerprint changed.")
    if row.get("status") != "complete":
        raise CaptureUncertain("Previous reserved/failed capture stage requires manual reconciliation: " + str(path))
    if digest(row["result"]) != row.get("result_sha256"):
        raise ValueError("Captured stage checksum mismatch.")
    return row["result"]


def validate_evidence(evidence: list[dict]) -> None:
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 5:
        raise ValueError("Expected one to five ranked evidence passages.")
    ids = []
    for rank, item in enumerate(evidence, 1):
        if not isinstance(item, dict) or not str(item.get("text", "")).strip() or not str(item.get("chunk_id", "")).strip():
            raise ValueError("Invalid captured evidence.")
        ids.append(item["chunk_id"])
        if item.get("rerank_rank") not in (None, rank):
            raise ValueError("Evidence rank does not match final order.")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate final evidence chunk IDs.")


def capture_one(qid: str, question: str, state_dir: Path, retrieve, generate) -> dict:
    retrieval_fp = digest({"qid": qid, "question": question, "stage": "retrieve", "config": RETRIEVAL_CONFIG})
    saved = read_complete(state_dir, qid, "retrieve", retrieval_fp)
    if saved is None:
        reserve_stage(state_dir, qid, "retrieve", retrieval_fp)
        try:
            evidence, candidate_count = retrieve(question)
            validate_evidence(evidence)
            saved = {"candidate_count": int(candidate_count), "evidence": evidence}
            complete_stage(state_dir, qid, "retrieve", retrieval_fp, saved)
        except BaseException as exc:
            fail_stage(state_dir, qid, "retrieve", retrieval_fp, exc)
            raise

    evidence = saved["evidence"]
    generation_fp = digest({
        "qid": qid, "question": question, "stage": "generate",
        "chunk_ids": [x["chunk_id"] for x in evidence],
        "evidence_sha256": [hashlib.sha256(x["text"].encode()).hexdigest() for x in evidence],
    })
    generated = read_complete(state_dir, qid, "generate", generation_fp)
    if generated is None:
        reserve_stage(state_dir, qid, "generate", generation_fp)
        try:
            generated = generate(question, evidence)
            if not isinstance(generated, dict) or not str(generated.get("answer", "")).strip():
                raise ValueError("Missing genuine generated answer.")
            if not isinstance(generated.get("citations", []), list):
                raise ValueError("Invalid citation structure.")
            complete_stage(state_dir, qid, "generate", generation_fp, generated)
        except BaseException as exc:
            fail_stage(state_dir, qid, "generate", generation_fp, exc)
            raise

    return {
        "id": qid,
        "user_input": question,
        "response": generated["answer"],
        "retrieved_contexts": [x["text"] for x in evidence],
        "retrieved_chunk_ids": [x["chunk_id"] for x in evidence],
        "retrieved_evidence": [
            {k: x.get(k) for k in ("chunk_id", "source_id", "title", "page", "section_id", "rerank_rank", "rerank_score")}
            for x in evidence
        ],
        "citations": generated.get("citations", []),
        "candidate_count": saved["candidate_count"],
    }


def build_package(records: list[dict], provenance: dict) -> dict:
    return {
        "protocol": "sentinelrag-recorded-answers-v1",
        "provenance": provenance,
        "questions": records,
        "references_injected_into_capture": False,
        "scores": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=ROOT / ".cache/ragas-capture")
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/ragas-capture/recorded_answers.json")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--limit", type=int, choices=range(1, 21), default=1)
    args = parser.parse_args()

    approval = check_reference_approval(args.approval)
    source = verify_runtime_source()
    golden = load_golden(ROOT / "data/eval/golden_questions.json")
    selected = select_questions(golden)
    if tuple(row["id"] for row in selected) != IDS:
        raise ValueError("Frozen RAGAS sample changed.")
    index = ROOT / "data/index/chroma.sqlite3"
    if sha256_file(index) != INDEX_SHA256:
        raise ValueError("Index snapshot changed.")

    provenance = {
        **source,
        "index_sha256": INDEX_SHA256,
        "golden_git_blob": GOLDEN_BLOB,
        "reference_set_sha256": REFERENCE_HASH,
        "reference_approval_timestamp_utc": approval["approval_timestamp_utc"],
        "generator_model": "command-r7b-12-2024",
        "reranker_model": "rerank-v3.5",
        "retrieval_config": RETRIEVAL_CONFIG,
        "capture_method": "frozen-pipeline-direct-v1",
    }

    print("REFERENCE_APPROVAL=PASSED")
    print("PIPELINE_AND_INDEX_PROVENANCE=PASSED")
    print("CAPTURE_RANGE=" + ",".join(x["id"] for x in selected[:args.limit]))
    if not args.run:
        print("MODE=VALIDATION_ONLY; COHERE_CALLS=0; APPLICATION_OUTPUTS_NOT_CAPTURED")
        return 0

    if os.getenv("RAILWAY_SERVICE_ID"):
        raise ValueError("Do not run the evaluation capture job inside the production Railway service.")
    if not os.getenv("COHERE_API_KEY", "").strip():
        raise ValueError("COHERE_API_KEY must be supplied privately for explicit live capture.")

    # Import provider/runtime code only after all offline validation gates pass.
    from src.config import (BM25_TOP_K, COHERE_MODEL, COHERE_RERANK_MODEL, TOP_N, VECTOR_TOP_K)
    from src.rag_pipeline import retrieve_top_evidence
    from src.llm import generate_grounded_response
    if (VECTOR_TOP_K, BM25_TOP_K, TOP_N, COHERE_MODEL, COHERE_RERANK_MODEL) != (
        25, 20, 5, "command-r7b-12-2024", "rerank-v3.5"
    ):
        raise ValueError("Runtime retrieval/model configuration changed.")

    records = []
    for row in selected[:args.limit]:
        records.append(capture_one(
            row["id"], row["question"], args.state_dir,
            retrieve_top_evidence, generate_grounded_response,
        ))
        atomic_write(args.state_dir / "records" / (row["id"] + ".json"), records[-1])

    package = build_package(records, provenance)
    atomic_write(args.output, package)
    print("CAPTURED_QUESTIONS=" + str(len(records)))
    print("EXPECTED_COHERE_REQUESTS_ON_CLEAN_SUCCESS=" + str(2 * len(records)))
    print("RAGAS_SCORES=NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
