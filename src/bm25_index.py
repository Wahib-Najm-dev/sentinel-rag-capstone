import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.config import (
    BM25_TOP_K,
    INDEX_DIR,
)


BM25_INDEX_PATH = (
    Path(INDEX_DIR)
    / "bm25_index.pkl"
)

BM25_INDEX_VERSION = 1


def tokenize(text: str) -> list[str]:
    """
    Lightweight lexical tokenizer for cybersecurity text.

    Preserves useful compound identifiers such as:
        T1055.011
        CVE-2025-1234
        oauth/token
        command-and-control

    while normalizing text to lowercase.
    """
    if not text:
        return []

    normalized = text.lower()

    tokens = re.findall(
        r"[a-z0-9]+"
        r"(?:[._:/-][a-z0-9]+)*",
        normalized,
    )

    return tokens


def build_bm25(
    chunks: list[dict],
) -> dict:
    """
    Build a BM25Okapi lexical index over the same
    chunks used by the vector index.
    """
    if not chunks:
        raise ValueError(
            "Cannot build BM25 index from an empty chunk list"
        )

    tokenized_corpus = []

    for chunk in chunks:
        text = chunk.get(
            "text",
            "",
        )

        tokens = tokenize(
            text
        )

        tokenized_corpus.append(
            tokens
        )

    if not any(tokenized_corpus):
        raise ValueError(
            "All BM25 documents are empty after tokenization"
        )

    model = BM25Okapi(
        tokenized_corpus
    )

    return {
        "version": BM25_INDEX_VERSION,
        "chunks": chunks,
        "tokenized_corpus": tokenized_corpus,
        "model": model,
    }


def save_bm25_index(
    index_data: dict,
    path: Path = BM25_INDEX_PATH,
) -> None:
    """
    Persist the generated lexical index locally.
    """
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "wb"
    ) as file:
        pickle.dump(
            index_data,
            file,
            protocol=pickle.HIGHEST_PROTOCOL,
        )


def load_bm25_index(
    path: Path = BM25_INDEX_PATH,
) -> dict:
    """
    Load a previously generated BM25 index.

    Only load indexes generated locally by SentinelRAG.
    Pickle files should never be accepted from users.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"BM25 index not found: {path}"
        )

    with path.open(
        "rb"
    ) as file:
        index_data = pickle.load(
            file
        )

    version = index_data.get(
        "version"
    )

    if version != BM25_INDEX_VERSION:
        raise RuntimeError(
            "Unsupported BM25 index version: "
            f"{version}"
        )

    required_keys = {
        "chunks",
        "tokenized_corpus",
        "model",
    }

    missing_keys = (
        required_keys
        - set(index_data)
    )

    if missing_keys:
        raise RuntimeError(
            "BM25 index is missing keys: "
            f"{sorted(missing_keys)}"
        )

    return index_data


def search_bm25(
    index_data: dict,
    query: str,
    top_k: int = BM25_TOP_K,
) -> list[dict]:
    """
    Search the BM25 index and return ranked chunks.

    Results are sorted deterministically by:
        1. BM25 score descending
        2. chunk_id ascending
    """
    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than 0"
        )

    query_tokens = tokenize(
        query
    )

    if not query_tokens:
        return []

    model = index_data[
        "model"
    ]

    chunks = index_data[
        "chunks"
    ]

    scores = model.get_scores(
        query_tokens
    )

    ranked = []

    for position, (
        chunk,
        score,
    ) in enumerate(
        zip(
            chunks,
            scores,
        )
    ):
        result = dict(
            chunk
        )

        result[
            "bm25_score"
        ] = float(
            score
        )

        result[
            "_corpus_position"
        ] = position

        ranked.append(
            result
        )

    ranked.sort(
        key=lambda item: (
            -item[
                "bm25_score"
            ],
            item.get(
                "chunk_id",
                "",
            ),
        )
    )

    results = ranked[
        : min(
            top_k,
            len(ranked),
        )
    ]

    for rank, result in enumerate(
        results,
        start=1,
    ):
        result[
            "bm25_rank"
        ] = rank

        result.pop(
            "_corpus_position",
            None,
        )

    return results