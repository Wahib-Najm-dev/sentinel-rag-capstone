import base64
import os
from functools import lru_cache

# Reduce unnecessary CPU-thread memory before importing
# sentence-transformers / PyTorch.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("MALLOC_ARENA_MAX", "2")

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from src.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
)


app = FastAPI(
    title="SentinelRAG Embedding Service",
    version="1.0.0",
)


class EmbedQueryRequest(BaseModel):
    text: str


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """
    Load exactly one copy of the same E5 model used
    by SentinelRAG local ingestion and evaluation.
    """
    return SentenceTransformer(
        EMBEDDING_MODEL,
        device="cpu",
        model_kwargs={
            "low_cpu_mem_usage": True,
        },
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": EMBEDDING_MODEL,
        "dimension": EMBEDDING_DIMENSION,
    }


@app.post("/embed-query")
def embed_query(
    request: EmbedQueryRequest,
) -> dict:
    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Query text cannot be empty.",
        )

    model = get_model()

    embedding = model.encode(
        [f"query: {text}"],
        batch_size=1,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].astype(
        np.float32,
        copy=False,
    )

    if embedding.shape != (
        EMBEDDING_DIMENSION,
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected embedding dimension: "
                f"{embedding.shape}"
            ),
        )

    # Force a stable little-endian float32 representation
    # before sending the vector over Railway private network.
    embedding_bytes = embedding.astype(
        "<f4",
        copy=False,
    ).tobytes()

    return {
        "dimension": EMBEDDING_DIMENSION,
        "dtype": "float32",
        "normalized": True,
        "embedding_b64": base64.b64encode(
            embedding_bytes
        ).decode("ascii"),
    }
