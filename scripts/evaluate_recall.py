from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import (
    BM25_TOP_K,
    COHERE_RERANK_MODEL,
    EMBEDDING_MODEL,
    TOP_N,
    VECTOR_TOP_K,
)
from src.retrieval import (
    RRF_K,
    get_bm25_index,
    get_chroma_collection,
    hybrid_retrieve,
)
from src.reranker import rerank_top_evidence


GOLDEN_QUESTIONS_PATH = Path(
    "data/eval/golden_questions.json"
)

REPORT_PATH = Path(
    "data/eval/recall_report.json"
)

CHECKPOINT_PATH = Path(
    "data/eval/recall_checkpoint.json"
)

EXPECTED_QUESTION_IDS = [
    f"q{i:02d}"
    for i in range(1, 31)
]

EXPECTED_QUESTION_COUNT = 30

# The project requirement is Recall@5 > 80%.
# With 30 questions:
# 24/30 = 80.00% -> NOT enough.
# 25/30 = 83.33% -> passes.
REQUIRED_MIN_HITS = 25


def load_json(
    path: Path,
) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json_atomic(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")

    temporary_path.replace(
        path
    )


def sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def load_golden_questions() -> list[dict]:
    if not GOLDEN_QUESTIONS_PATH.exists():
        raise FileNotFoundError(
            "Golden questions file not found: "
            f"{GOLDEN_QUESTIONS_PATH}"
        )

    data = load_json(
        GOLDEN_QUESTIONS_PATH
    )

    if not isinstance(
        data,
        list,
    ):
        raise TypeError(
            "golden_questions.json must contain "
            "a top-level JSON list."
        )

    return data


def validate_question_structure(
    questions: list[dict],
) -> None:
    if len(questions) != EXPECTED_QUESTION_COUNT:
        raise RuntimeError(
            "Expected exactly "
            f"{EXPECTED_QUESTION_COUNT} questions, "
            f"found {len(questions)}."
        )

    question_ids = [
        question.get("id")
        for question in questions
    ]

    if question_ids != EXPECTED_QUESTION_IDS:
        raise RuntimeError(
            "Question IDs must be exactly "
            "q01 through q30 in order."
        )

    if len(
        set(question_ids)
    ) != EXPECTED_QUESTION_COUNT:
        raise RuntimeError(
            "Golden question IDs are not unique."
        )

    for question in questions:
        question_id = question.get(
            "id",
            "<unknown>",
        )

        question_text = str(
            question.get(
                "question",
                "",
            )
        ).strip()

        if not question_text:
            raise RuntimeError(
                f"{question_id}: empty question text."
            )

        gold_source_ids = question.get(
            "gold_source_ids",
            [],
        )

        if not isinstance(
            gold_source_ids,
            list,
        ) or not gold_source_ids:
            raise RuntimeError(
                f"{question_id}: "
                "gold_source_ids must be a "
                "non-empty list."
            )

        gold_chunk_ids = question.get(
            "gold_chunk_ids",
            [],
        )

        if not isinstance(
            gold_chunk_ids,
            list,
        ) or not gold_chunk_ids:
            raise RuntimeError(
                f"{question_id}: "
                "gold_chunk_ids must be a "
                "non-empty list."
            )

        if len(
            gold_chunk_ids
        ) != len(
            set(gold_chunk_ids)
        ):
            raise RuntimeError(
                f"{question_id}: duplicate "
                "gold_chunk_ids."
            )


def validate_indexes_and_gold(
    questions: list[dict],
) -> dict:
    collection = get_chroma_collection()

    chroma_count = collection.count()

    bm25_index = get_bm25_index()

    bm25_chunks = bm25_index.get(
        "chunks",
        [],
    )

    bm25_count = len(
        bm25_chunks
    )

    if chroma_count != bm25_count:
        raise RuntimeError(
            "Chroma and BM25 counts do not match: "
            f"{chroma_count} vs {bm25_count}."
        )

    bm25_ids = {
        chunk["chunk_id"]
        for chunk in bm25_chunks
    }

    all_gold_ids = sorted(
        {
            chunk_id
            for question in questions
            for chunk_id in question[
                "gold_chunk_ids"
            ]
        }
    )

    chroma_result = collection.get(
        ids=all_gold_ids,
        include=[
            "metadatas",
        ],
    )

    chroma_ids = chroma_result.get(
        "ids",
        [],
    )

    chroma_metadatas = chroma_result.get(
        "metadatas",
        [],
    )

    chroma_map = {
        chunk_id: metadata or {}
        for chunk_id, metadata
        in zip(
            chroma_ids,
            chroma_metadatas,
        )
    }

    problems = []

    for question in questions:
        question_id = question[
            "id"
        ]

        gold_sources = set(
            question[
                "gold_source_ids"
            ]
        )

        for chunk_id in question[
            "gold_chunk_ids"
        ]:
            if chunk_id not in chroma_map:
                problems.append(
                    f"{question_id}: "
                    "Gold chunk missing from "
                    f"Chroma: {chunk_id}"
                )

                continue

            if chunk_id not in bm25_ids:
                problems.append(
                    f"{question_id}: "
                    "Gold chunk missing from "
                    f"BM25: {chunk_id}"
                )

            metadata = chroma_map[
                chunk_id
            ]

            source_id = metadata.get(
                "source_id",
                "",
            )

            if (
                source_id
                and source_id
                not in gold_sources
            ):
                problems.append(
                    f"{question_id}: "
                    "Gold source mismatch for "
                    f"{chunk_id}: {source_id}"
                )

    if problems:
        message = (
            "Golden/index validation failed:\n"
            + "\n".join(
                f"- {problem}"
                for problem in problems
            )
        )

        raise RuntimeError(
            message
        )

    return {
        "chroma_count": chroma_count,
        "bm25_count": bm25_count,
        "bm25_ids": bm25_ids,
        "unique_gold_ids": len(
            all_gold_ids
        ),
    }


def run_metric_logic_self_test() -> None:
    cases = [
        {
            "gold": [
                "gold-a",
            ],
            "retrieved": [
                "gold-a",
                "x",
                "y",
                "z",
                "w",
            ],
            "expected": True,
        },
        {
            "gold": [
                "gold-a",
            ],
            "retrieved": [
                "a",
                "b",
                "c",
                "d",
                "e",
            ],
            "expected": False,
        },
        {
            "gold": [
                "gold-a",
                "gold-b",
            ],
            "retrieved": [
                "x",
                "gold-b",
                "y",
                "z",
                "w",
            ],
            "expected": True,
        },
    ]

    for index, case in enumerate(
        cases,
        start=1,
    ):
        matched = [
            gold_id
            for gold_id in case["gold"]
            if gold_id
            in case["retrieved"]
        ]

        actual = bool(
            matched
        )

        if actual != case["expected"]:
            raise RuntimeError(
                "Metric logic self-test failed "
                f"for case {index}."
            )


def build_evaluation_signature(
    questions: list[dict],
    bm25_ids: set[str],
) -> str:
    golden_payload = json.dumps(
        questions,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    index_payload = "\n".join(
        sorted(
            bm25_ids
        )
    )

    configuration_payload = json.dumps(
        {
            "vector_top_k":
                VECTOR_TOP_K,
            "bm25_top_k":
                BM25_TOP_K,
            "rrf_k":
                RRF_K,
            "top_n":
                TOP_N,
            "embedding_model":
                EMBEDDING_MODEL,
            "rerank_model":
                COHERE_RERANK_MODEL,
        },
        sort_keys=True,
    )

    combined = (
        golden_payload
        + "\n---INDEX---\n"
        + index_payload
        + "\n---CONFIG---\n"
        + configuration_payload
    )

    return sha256_text(
        combined
    )


def compute_match(
    gold_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
) -> tuple[bool, list[str]]:
    matched_gold_ids = [
        gold_id
        for gold_id in gold_chunk_ids
        if gold_id
        in retrieved_chunk_ids
    ]

    return (
        bool(
            matched_gold_ids
        ),
        matched_gold_ids,
    )


def safe_int(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def safe_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def get_result_field(
    item: dict,
    key: str,
) -> Any:
    if key in item:
        return item.get(
            key
        )

    metadata = item.get(
        "metadata"
    )

    if isinstance(
        metadata,
        dict,
    ):
        return metadata.get(
            key
        )

    return None


def serialize_evidence(
    item: dict,
) -> dict:
    return {
        "chunk_id":
            item.get(
                "chunk_id"
            ),
        "source_id":
            get_result_field(
                item,
                "source_id",
            ),
        "page":
            get_result_field(
                item,
                "page",
            ),
        "section_id":
            get_result_field(
                item,
                "section_id",
            ),
        "vector_rank":
            safe_int(
                item.get(
                    "vector_rank"
                )
            ),
        "bm25_rank":
            safe_int(
                item.get(
                    "bm25_rank"
                )
            ),
        "rrf_rank":
            safe_int(
                item.get(
                    "rrf_rank"
                )
            ),
        "rrf_score":
            safe_float(
                item.get(
                    "rrf_score"
                )
            ),
        "rerank_rank":
            safe_int(
                item.get(
                    "rerank_rank"
                )
            ),
        "rerank_score":
            safe_float(
                item.get(
                    "rerank_score"
                )
            ),
    }


RERANK_MIN_INTERVAL_SECONDS = 7.0
RERANK_RATE_LIMIT_BACKOFF_SECONDS = 65.0
RERANK_MAX_ATTEMPTS = 2

_last_rerank_request_started_at: float | None = None


def _is_rate_limit_error(
    exc: Exception,
) -> bool:
    status_code = getattr(
        exc,
        "status_code",
        None,
    )

    if status_code == 429:
        return True

    response = getattr(
        exc,
        "response",
        None,
    )

    if getattr(
        response,
        "status_code",
        None,
    ) == 429:
        return True

    message = str(exc).lower()

    markers = (
        "429",
        "too many requests",
        "rate limit",
        "rate-limit",
    )

    return any(
        marker in message
        for marker in markers
    )


def _rerank_top_evidence_with_guard(
    *,
    query: str,
    candidates: list[dict],
) -> list[dict]:
    global _last_rerank_request_started_at

    for attempt in range(
        1,
        RERANK_MAX_ATTEMPTS + 1,
    ):
        if (
            _last_rerank_request_started_at
            is not None
        ):
            elapsed = (
                time.monotonic()
                - _last_rerank_request_started_at
            )

            wait_seconds = (
                RERANK_MIN_INTERVAL_SECONDS
                - elapsed
            )

            if wait_seconds > 0:
                print(
                    "  Cohere rate-limit guard: "
                    f"waiting {wait_seconds:.1f}s..."
                )
                time.sleep(
                    wait_seconds
                )

        _last_rerank_request_started_at = (
            time.monotonic()
        )

        try:
            return rerank_top_evidence(
                query=query,
                candidates=candidates,
            )

        except Exception as exc:
            if not _is_rate_limit_error(
                exc
            ):
                raise

            if (
                attempt
                >= RERANK_MAX_ATTEMPTS
            ):
                raise RuntimeError(
                    "Cohere Rerank remained "
                    "rate-limited after the "
                    "protected retry. "
                    "The completed-question "
                    "checkpoint is preserved; "
                    "rerun the evaluator without "
                    "--force to resume."
                ) from exc

            print(
                "  Cohere HTTP 429 / rate "
                "limit detected."
            )
            print(
                "  Waiting "
                f"{RERANK_RATE_LIMIT_BACKOFF_SECONDS:.0f}"
                "s before one protected retry..."
            )

            time.sleep(
                RERANK_RATE_LIMIT_BACKOFF_SECONDS
            )

    raise RuntimeError(
        "Unexpected rerank retry state."
    )


def evaluate_question(
    question: dict,
) -> dict:
    question_id = question[
        "id"
    ]

    query = question[
        "question"
    ].strip()

    candidates = hybrid_retrieve(
        query=query,
        vector_top_k=VECTOR_TOP_K,
        bm25_top_k=BM25_TOP_K,
    )

    if not candidates:
        raise RuntimeError(
            f"{question_id}: hybrid retrieval "
            "returned no candidates."
        )

    final_evidence = _rerank_top_evidence_with_guard(
        query=query,
        candidates=candidates,
    )

    expected_evidence_count = min(
        TOP_N,
        len(candidates),
    )

    if len(
        final_evidence
    ) != expected_evidence_count:
        raise RuntimeError(
            f"{question_id}: expected "
            f"{expected_evidence_count} final "
            "evidence chunks, found "
            f"{len(final_evidence)}."
        )

    retrieved_chunk_ids = [
        item.get(
            "chunk_id"
        )
        for item in final_evidence
    ]

    if any(
        not chunk_id
        for chunk_id
        in retrieved_chunk_ids
    ):
        raise RuntimeError(
            f"{question_id}: final evidence "
            "contains a missing chunk_id."
        )

    if len(
        retrieved_chunk_ids
    ) != len(
        set(
            retrieved_chunk_ids
        )
    ):
        raise RuntimeError(
            f"{question_id}: final Top "
            "evidence contains duplicate "
            "chunk IDs."
        )

    hit, matched_gold_ids = compute_match(
        gold_chunk_ids=question[
            "gold_chunk_ids"
        ],
        retrieved_chunk_ids=
            retrieved_chunk_ids,
    )

    return {
        "id":
            question_id,
        "question":
            query,
        "topic":
            question.get(
                "topic"
            ),
        "gold_source_ids":
            question.get(
                "gold_source_ids",
                [],
            ),
        "gold_chunk_ids":
            question[
                "gold_chunk_ids"
            ],
        "fused_candidate_count":
            len(
                candidates
            ),
        "final_top_k":
            len(
                final_evidence
            ),
        "retrieved_chunk_ids":
            retrieved_chunk_ids,
        "matched_gold_chunk_ids":
            matched_gold_ids,
        "hit":
            hit,
        "final_evidence": [
            serialize_evidence(
                item
            )
            for item
            in final_evidence
        ],
    }


def load_checkpoint(
    signature: str,
) -> dict[str, dict]:
    if not CHECKPOINT_PATH.exists():
        return {}

    checkpoint = load_json(
        CHECKPOINT_PATH
    )

    checkpoint_signature = (
        checkpoint.get(
            "evaluation_signature"
        )
    )

    if checkpoint_signature != signature:
        raise RuntimeError(
            "A Recall checkpoint exists, but "
            "it belongs to a different Golden "
            "Set, index, or retrieval "
            "configuration. Do not reuse it."
        )

    results = checkpoint.get(
        "results",
        []
    )

    completed = {}

    for result in results:
        question_id = result.get(
            "id"
        )

        if (
            question_id
            in EXPECTED_QUESTION_IDS
        ):
            completed[
                question_id
            ] = result

    return completed


def save_checkpoint(
    signature: str,
    completed_results: dict[str, dict],
) -> None:
    ordered_results = [
        completed_results[
            question_id
        ]
        for question_id
        in EXPECTED_QUESTION_IDS
        if question_id
        in completed_results
    ]

    checkpoint = {
        "status":
            "in_progress",
        "evaluation_signature":
            signature,
        "completed_questions":
            len(
                ordered_results
            ),
        "results":
            ordered_results,
    }

    save_json_atomic(
        CHECKPOINT_PATH,
        checkpoint,
    )


def build_final_report(
    signature: str,
    results: list[dict],
    chroma_count: int,
    bm25_count: int,
) -> dict:
    hits = sum(
        1
        for result in results
        if result[
            "hit"
        ]
    )

    misses = (
        EXPECTED_QUESTION_COUNT
        - hits
    )

    recall_at_5 = (
        hits
        / EXPECTED_QUESTION_COUNT
    )

    passed = (
        hits
        >= REQUIRED_MIN_HITS
    )

    missed_question_ids = [
        result[
            "id"
        ]
        for result in results
        if not result[
            "hit"
        ]
    ]

    return {
        "project":
            "SentinelRAG",
        "metric":
            "Recall@5",
        "metric_definition":
            (
                "Question-level hit rate. A "
                "Golden Question is a hit when "
                "at least one gold_chunk_id "
                "appears in the final reranked "
                "Top 5 evidence."
            ),
        "created_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "evaluation_signature":
            signature,
        "configuration": {
            "questions":
                EXPECTED_QUESTION_COUNT,
            "vector_top_k":
                VECTOR_TOP_K,
            "bm25_top_k":
                BM25_TOP_K,
            "rrf_k":
                RRF_K,
            "rerank_top_n":
                TOP_N,
            "embedding_model":
                EMBEDDING_MODEL,
            "rerank_model":
                COHERE_RERANK_MODEL,
            "chroma_chunks":
                chroma_count,
            "bm25_chunks":
                bm25_count,
        },
        "summary": {
            "hits":
                hits,
            "misses":
                misses,
            "questions":
                EXPECTED_QUESTION_COUNT,
            "recall_at_5":
                recall_at_5,
            "recall_at_5_percent":
                round(
                    recall_at_5
                    * 100.0,
                    2,
                ),
            "required_min_hits":
                REQUIRED_MIN_HITS,
            "requirement":
                "Recall@5 > 80%",
            "passed":
                passed,
            "missed_question_ids":
                missed_question_ids,
        },
        "results":
            results,
    }


def validate_only() -> int:
    questions = (
        load_golden_questions()
    )

    validate_question_structure(
        questions
    )

    index_info = (
        validate_indexes_and_gold(
            questions
        )
    )

    run_metric_logic_self_test()

    print(
        "=" * 80
    )
    print(
        "RECALL EVALUATOR VALIDATION"
    )
    print(
        "=" * 80
    )
    print(
        "Questions:",
        len(
            questions
        ),
    )
    print(
        "Unique Gold chunk IDs:",
        index_info[
            "unique_gold_ids"
        ],
    )
    print(
        "Chroma chunks:",
        index_info[
            "chroma_count"
        ],
    )
    print(
        "BM25 chunks:",
        index_info[
            "bm25_count"
        ],
    )
    print(
        "Vector Top-K:",
        VECTOR_TOP_K,
    )
    print(
        "BM25 Top-K:",
        BM25_TOP_K,
    )
    print(
        "RRF k:",
        RRF_K,
    )
    print(
        "Final Top-N:",
        TOP_N,
    )
    print(
        "Required hits:",
        REQUIRED_MIN_HITS,
        "/",
        EXPECTED_QUESTION_COUNT,
    )
    print(
        "Metric logic self-test: PASSED"
    )
    print(
        "Golden/index validation: PASSED"
    )
    print(
        "Cohere API calls: 0"
    )
    print(
        "RAGAS calls: 0"
    )
    print(
        "=" * 80
    )

    return 0


def run_full_evaluation(
    force: bool = False,
) -> int:
    if (
        REPORT_PATH.exists()
        and not force
    ):
        print(
            "A completed Recall report already "
            "exists:"
        )
        print(
            REPORT_PATH
        )
        print()
        print(
            "Refusing to run another 30-question "
            "evaluation automatically."
        )
        print(
            "Use --force only when a new full "
            "evaluation is intentionally needed."
        )
        print(
            "Cohere API calls made: 0"
        )

        return 2

    if force:
        if REPORT_PATH.exists():
            REPORT_PATH.unlink()

        if CHECKPOINT_PATH.exists():
            CHECKPOINT_PATH.unlink()

    questions = (
        load_golden_questions()
    )

    validate_question_structure(
        questions
    )

    index_info = (
        validate_indexes_and_gold(
            questions
        )
    )

    run_metric_logic_self_test()

    signature = (
        build_evaluation_signature(
            questions=questions,
            bm25_ids=index_info[
                "bm25_ids"
            ],
        )
    )

    completed = load_checkpoint(
        signature
    )

    remaining_questions = [
        question
        for question in questions
        if question[
            "id"
        ]
        not in completed
    ]

    print(
        "=" * 80
    )
    print(
        "SentinelRAG Recall@5 Evaluation"
    )
    print(
        "=" * 80
    )
    print(
        "Questions:",
        len(
            questions
        ),
    )
    print(
        "Already completed from checkpoint:",
        len(
            completed
        ),
    )
    print(
        "Remaining questions:",
        len(
            remaining_questions
        ),
    )
    print(
        "Planned Cohere rerank calls:",
        len(
            remaining_questions
        ),
    )
    print(
        "RAGAS calls: 0"
    )
    print(
        "=" * 80
    )
    print()

    for position, question in enumerate(
        questions,
        start=1,
    ):
        question_id = question[
            "id"
        ]

        if question_id in completed:
            print(
                f"[{position}/"
                f"{EXPECTED_QUESTION_COUNT}] "
                f"{question_id} - "
                "checkpoint hit, skipping API call."
            )
            continue

        print(
            f"[{position}/"
            f"{EXPECTED_QUESTION_COUNT}] "
            f"{question_id} - evaluating..."
        )

        result = evaluate_question(
            question
        )

        completed[
            question_id
        ] = result

        save_checkpoint(
            signature=signature,
            completed_results=completed,
        )

        status = (
            "HIT"
            if result[
                "hit"
            ]
            else "MISS"
        )

        print(
            f"    {status}"
        )

    ordered_results = [
        completed[
            question_id
        ]
        for question_id
        in EXPECTED_QUESTION_IDS
    ]

    if len(
        ordered_results
    ) != EXPECTED_QUESTION_COUNT:
        raise RuntimeError(
            "Evaluation ended without results "
            "for all 30 questions."
        )

    report = build_final_report(
        signature=signature,
        results=ordered_results,
        chroma_count=index_info[
            "chroma_count"
        ],
        bm25_count=index_info[
            "bm25_count"
        ],
    )

    save_json_atomic(
        REPORT_PATH,
        report,
    )

    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    summary = report[
        "summary"
    ]

    print()
    print(
        "=" * 80
    )
    print(
        "RECALL@5 FINAL RESULT"
    )
    print(
        "=" * 80
    )
    print(
        "Hits:",
        summary[
            "hits"
        ],
        "/",
        summary[
            "questions"
        ],
    )
    print(
        "Misses:",
        summary[
            "misses"
        ],
    )
    print(
        "Recall@5:",
        f"{summary['recall_at_5_percent']:.2f}%",
    )
    print(
        "Required:",
        "> 80%",
    )
    print(
        "Minimum passing hits:",
        REQUIRED_MIN_HITS,
        "/",
        EXPECTED_QUESTION_COUNT,
    )
    print(
        "Passed:",
        summary[
            "passed"
        ],
    )

    if summary[
        "missed_question_ids"
    ]:
        print(
            "Missed questions:",
            ", ".join(
                summary[
                    "missed_question_ids"
                ]
            ),
        )

    print(
        "Report:",
        REPORT_PATH,
    )
    print(
        "=" * 80
    )

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate SentinelRAG question-level "
            "Recall@5 using the full hybrid "
            "retrieval and Cohere reranking "
            "pipeline."
        )
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "Validate the Golden Set, indexes, "
            "configuration, and metric logic "
            "without making Cohere API calls."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Intentionally discard an existing "
            "completed report/checkpoint and run "
            "a fresh full evaluation."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.validate_only:
        return validate_only()

    return run_full_evaluation(
        force=args.force
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )