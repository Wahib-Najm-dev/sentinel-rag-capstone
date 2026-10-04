from functools import lru_cache

import chromadb

from src.bm25_index import (
    load_bm25_index,
    search_bm25,
)
from src.config import (
    BM25_TOP_K,
    INDEX_DIR,
    VECTOR_TOP_K,
)
from src.embedding_client import embed_query_runtime


CHROMA_COLLECTION_NAME = "sentinelrag_chunks"

# Standard RRF constant.
RRF_K = 60


@lru_cache(maxsize=1)
def get_chroma_client():
    """
    Open and cache the persistent Chroma client.
    """
    return chromadb.PersistentClient(
        path=str(INDEX_DIR)
    )


@lru_cache(maxsize=1)
def get_chroma_collection():
    """
    Open and cache the SentinelRAG Chroma collection.
    """
    client = get_chroma_client()

    return client.get_collection(
        CHROMA_COLLECTION_NAME
    )


@lru_cache(maxsize=1)
def get_bm25_index() -> dict:
    """
    Load and cache the persistent BM25 index.
    """
    return load_bm25_index()


def vector_search(
    query: str,
    top_k: int = VECTOR_TOP_K,
) -> list[dict]:
    """
    Perform semantic retrieval from Chroma using
    an E5 query embedding.
    """
    query = query.strip()

    if not query:
        return []

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than 0"
        )

    collection = get_chroma_collection()

    available = collection.count()

    if available == 0:
        return []

    n_results = min(
        top_k,
        available,
    )

    query_embedding = embed_query_runtime(
        query
    )

    response = collection.query(
        query_embeddings=[
            query_embedding.tolist()
        ],
        n_results=n_results,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    ids = response["ids"][0]
    documents = response["documents"][0]
    metadatas = response["metadatas"][0]
    distances = response["distances"][0]

    results = []

    for rank, (
        chunk_id,
        text,
        metadata,
        distance,
    ) in enumerate(
        zip(
            ids,
            documents,
            metadatas,
            distances,
        ),
        start=1,
    ):
        metadata = metadata or {}

        page = metadata.get(
            "page",
            -1,
        )

        if page == -1:
            page = None

        distance = float(
            distance
        )

        results.append(
            {
                "chunk_id": chunk_id,
                "source_id": metadata.get(
                    "source_id",
                    "",
                ),
                "source": metadata.get(
                    "source",
                    "",
                ),
                "title": metadata.get(
                    "title",
                    "",
                ),
                "document_type": metadata.get(
                    "document_type",
                    "",
                ),
                "page": page,
                "section_id": metadata.get(
                    "section_id",
                    "",
                ),
                "chunk_index": int(
                    metadata.get(
                        "chunk_index",
                        0,
                    )
                ),
                "token_count": int(
                    metadata.get(
                        "token_count",
                        0,
                    )
                ),
                "text": text,
                "vector_rank": rank,
                "vector_distance": distance,
                "vector_similarity": (
                    1.0 - distance
                ),
                "found_by_vector": True,
                "found_by_bm25": False,
            }
        )

    return results


def lexical_search(
    query: str,
    top_k: int = BM25_TOP_K,
) -> list[dict]:
    """
    Perform lexical retrieval using the persistent
    BM25 index.
    """
    query = query.strip()

    if not query:
        return []

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than 0"
        )

    index_data = get_bm25_index()

    results = search_bm25(
        index_data=index_data,
        query=query,
        top_k=top_k,
    )

    for result in results:
        result["found_by_vector"] = False
        result["found_by_bm25"] = True

    return results


def reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    rrf_k: int = RRF_K,
) -> list[dict]:
    """
    Merge vector and BM25 rankings using
    deterministic Reciprocal Rank Fusion.

    Formula:

        RRF(d) = sum(1 / (k + rank))

    where rank begins at 1.
    """
    if rrf_k <= 0:
        raise ValueError(
            "rrf_k must be greater than 0"
        )

    fused = {}

    for result in vector_results:
        chunk_id = result[
            "chunk_id"
        ]

        item = dict(
            result
        )

        item.setdefault(
            "bm25_rank",
            None,
        )

        item.setdefault(
            "bm25_score",
            None,
        )

        item["rrf_score"] = (
            1.0
            / (
                rrf_k
                + result[
                    "vector_rank"
                ]
            )
        )

        fused[
            chunk_id
        ] = item

    for result in bm25_results:
        chunk_id = result[
            "chunk_id"
        ]

        contribution = (
            1.0
            / (
                rrf_k
                + result[
                    "bm25_rank"
                ]
            )
        )

        if chunk_id in fused:
            item = fused[
                chunk_id
            ]

            item[
                "bm25_rank"
            ] = result[
                "bm25_rank"
            ]

            item[
                "bm25_score"
            ] = result[
                "bm25_score"
            ]

            item[
                "found_by_bm25"
            ] = True

            item[
                "rrf_score"
            ] += contribution

        else:
            item = dict(
                result
            )

            item.setdefault(
                "vector_rank",
                None,
            )

            item.setdefault(
                "vector_distance",
                None,
            )

            item.setdefault(
                "vector_similarity",
                None,
            )

            item[
                "found_by_vector"
            ] = False

            item[
                "found_by_bm25"
            ] = True

            item[
                "rrf_score"
            ] = contribution

            fused[
                chunk_id
            ] = item

    results = list(
        fused.values()
    )

    # Deterministic ordering:
    # 1. Highest RRF score
    # 2. chunk_id ascending as a stable tie-breaker
    results.sort(
        key=lambda item: (
            -item[
                "rrf_score"
            ],
            item.get(
                "chunk_id",
                "",
            ),
        )
    )

    for rank, result in enumerate(
        results,
        start=1,
    ):
        result[
            "rrf_rank"
        ] = rank

    return results


def hybrid_retrieve(
    query: str,
    vector_top_k: int = VECTOR_TOP_K,
    bm25_top_k: int = BM25_TOP_K,
) -> list[dict]:
    """
    Execute the complete retrieval stage:

        Question
            â†“
        Vector Top-K
            +
        BM25 Top-K
            â†“
        Reciprocal Rank Fusion

    The returned candidates will later be sent to
    the Cohere reranker.
    """
    query = query.strip()

    if not query:
        return []

    vector_results = vector_search(
        query=query,
        top_k=vector_top_k,
    )

    bm25_results = lexical_search(
        query=query,
        top_k=bm25_top_k,
    )

    return reciprocal_rank_fusion(
        vector_results=vector_results,
        bm25_results=bm25_results,
    )
