import os

import numpy as np

from src.config import (
    EMBEDDING_MODEL,
    TOKENIZERS_PARALLELISM,
)


# Apply tokenizer runtime configuration before
# loading the SentenceTransformer model.
os.environ.setdefault(
    "TOKENIZERS_PARALLELISM",
    TOKENIZERS_PARALLELISM,
)


from sentence_transformers import SentenceTransformer


_model = None


def get_embedding_model() -> SentenceTransformer:
    """
    Load and cache the multilingual E5 embedding model.

    The model is kept in memory after the first load so
    repeated retrieval and ingestion operations do not
    reload it unnecessarily.

    CPU is used explicitly for Railway compatibility.
    """
    global _model

    if _model is None:
        _model = SentenceTransformer(
            EMBEDDING_MODEL,
            device="cpu",
        )

    return _model


def prepare_passage(text: str) -> str:
    """
    Apply the E5 passage prefix required for document
    embeddings.
    """
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Passage text cannot be empty"
        )

    return f"passage: {cleaned_text}"


def prepare_query(text: str) -> str:
    """
    Apply the E5 query prefix required for search queries.
    """
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Query text cannot be empty"
        )

    return f"query: {cleaned_text}"


def embed_passages(
    texts: list[str],
    batch_size: int = 32,
    show_progress_bar: bool = False,
) -> np.ndarray:
    """
    Generate normalized E5 embeddings for document
    passages.

    Returns:
        NumPy array with shape:
        (number_of_passages, embedding_dimension)
    """
    if not texts:
        return np.empty(
            (0, 0),
            dtype=np.float32,
        )

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than 0"
        )

    prepared_texts = [
        prepare_passage(text)
        for text in texts
    ]

    model = get_embedding_model()

    embeddings = model.encode(
        prepared_texts,
        batch_size=batch_size,
        show_progress_bar=show_progress_bar,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return embeddings.astype(
        np.float32,
        copy=False,
    )


def embed_query(
    text: str,
) -> np.ndarray:
    """
    Generate one normalized E5 embedding for a user query.

    Returns:
        One-dimensional NumPy vector.
    """
    prepared_text = prepare_query(
        text
    )

    model = get_embedding_model()

    embedding = model.encode(
        [prepared_text],
        batch_size=1,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return embedding[
        0
    ].astype(
        np.float32,
        copy=False,
    )


def embedding_dimension() -> int:
    """
    Return the output embedding dimension of the model.
    """
    model = get_embedding_model()

    dimension = (
        model.get_embedding_dimension()
    )

    if dimension is None:
        raise RuntimeError(
            "Could not determine embedding dimension"
        )

    return int(
        dimension
    )