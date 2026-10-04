import base64
import time

import numpy as np
import requests

from src.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_PROVIDER,
    EMBEDDING_SERVICE_TIMEOUT_SECONDS,
    EMBEDDING_SERVICE_URL,
)


def _embed_query_local(text: str) -> np.ndarray:
    """
    Local fallback used for development and evaluation.

    Import is intentionally lazy so Railway production
    does not import sentence-transformers or PyTorch when
    EMBEDDING_PROVIDER=remote.
    """
    from src.embeddings import embed_query

    return embed_query(text)


def _embed_query_remote(text: str) -> np.ndarray:
    """
    Request a query embedding from the private embedding
    service and reconstruct the exact float32 vector.
    """
    if not EMBEDDING_SERVICE_URL:
        raise RuntimeError(
            "EMBEDDING_SERVICE_URL is not configured."
        )

    url = (
        EMBEDDING_SERVICE_URL.rstrip("/")
        + "/embed-query"
    )

    last_error = None

    for attempt in range(2):
        try:
            response = requests.post(
                url,
                json={"text": text},
                timeout=EMBEDDING_SERVICE_TIMEOUT_SECONDS,
            )

            response.raise_for_status()

            payload = response.json()

            dimension = int(
                payload.get("dimension", 0)
            )

            if dimension != EMBEDDING_DIMENSION:
                raise RuntimeError(
                    "Embedding service returned "
                    f"dimension {dimension}; expected "
                    f"{EMBEDDING_DIMENSION}."
                )

            encoded = payload.get(
                "embedding_b64",
                "",
            )

            if not encoded:
                raise RuntimeError(
                    "Embedding service returned an "
                    "empty embedding."
                )

            raw = base64.b64decode(
                encoded,
                validate=True,
            )

            embedding = np.frombuffer(
                raw,
                dtype="<f4",
            ).copy()

            if embedding.shape != (
                EMBEDDING_DIMENSION,
            ):
                raise RuntimeError(
                    "Embedding service returned an "
                    "invalid vector length."
                )

            if not np.isfinite(
                embedding
            ).all():
                raise RuntimeError(
                    "Embedding service returned "
                    "non-finite values."
                )

            return embedding

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ) as exc:
            last_error = exc

            if attempt == 0:
                time.sleep(1.0)

    raise RuntimeError(
        "Remote embedding service request failed."
    ) from last_error


def embed_query_runtime(
    text: str,
) -> np.ndarray:
    """
    Generate one normalized E5 query embedding using
    either the local model or the Railway embedding
    service.
    """
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Query text cannot be empty."
        )

    if EMBEDDING_PROVIDER == "local":
        return _embed_query_local(
            cleaned_text
        )

    if EMBEDDING_PROVIDER == "remote":
        return _embed_query_remote(
            cleaned_text
        )

    raise ValueError(
        "Unsupported EMBEDDING_PROVIDER: "
        f"{EMBEDDING_PROVIDER}"
    )
