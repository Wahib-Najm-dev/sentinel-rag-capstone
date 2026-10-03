from functools import lru_cache

import cohere

from src.config import (
    COHERE_API_KEY,
    COHERE_RERANK_MODEL,
    TOP_N,
)


@lru_cache(maxsize=1)
def get_cohere_client():
    """
    Create and cache a Cohere V2 client.

    The API key must come from the local environment
    and must never be hard-coded in source code.
    """
    if not COHERE_API_KEY:
        raise RuntimeError(
            "COHERE_API_KEY is not configured."
        )

    return cohere.ClientV2(
        api_key=COHERE_API_KEY
    )


def rerank_candidates(
    query: str,
    candidates: list[dict],
    top_n: int = TOP_N,
) -> list[dict]:
    """
    Rerank hybrid retrieval candidates using Cohere.

    The function performs exactly one Cohere rerank
    request for the supplied candidate list.

    It preserves all original retrieval metadata and
    adds:

        rerank_rank
        rerank_score
        pre_rerank_index
    """
    query = query.strip()

    if not query:
        return []

    if not candidates:
        return []

    if top_n <= 0:
        raise ValueError(
            "top_n must be greater than 0"
        )

    documents = []

    for candidate in candidates:
        text = candidate.get(
            "text",
            ""
        ).strip()

        if not text:
            raise ValueError(
                "Candidate contains empty text."
            )

        documents.append(
            text
        )

    actual_top_n = min(
        top_n,
        len(documents),
    )

    client = get_cohere_client()

    response = client.rerank(
        model=COHERE_RERANK_MODEL,
        query=query,
        documents=documents,
        top_n=actual_top_n,
    )

    reranked = []

    for rank, result in enumerate(
        response.results,
        start=1,
    ):
        original_index = int(
            result.index
        )

        if (
            original_index < 0
            or original_index >= len(candidates)
        ):
            raise RuntimeError(
                "Cohere returned an invalid "
                "candidate index."
            )

        item = dict(
            candidates[
                original_index
            ]
        )

        item[
            "pre_rerank_index"
        ] = original_index

        item[
            "rerank_rank"
        ] = rank

        item[
            "rerank_score"
        ] = float(
            result.relevance_score
        )

        reranked.append(
            item
        )

    if len(reranked) != actual_top_n:
        raise RuntimeError(
            "Unexpected number of rerank results."
        )

    return reranked


def rerank_top_evidence(
    query: str,
    candidates: list[dict],
) -> list[dict]:
    """
    Return the final fixed Top-N evidence passages.

    SentinelRAG uses TOP_N = 5 so that the deployed
    system and Recall@5 evaluation use the same
    evidence configuration.
    """
    return rerank_candidates(
        query=query,
        candidates=candidates,
        top_n=TOP_N,
    )