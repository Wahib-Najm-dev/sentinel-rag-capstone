import base64
import os
from functools import lru_cache

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("MALLOC_ARENA_MAX", "2")

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from huggingface_hub import hf_hub_download
from pydantic import BaseModel
from tokenizers import Tokenizer

from src.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL


ONNX_FILENAME = "onnx/model.onnx"
TOKENIZER_FILENAME = "tokenizer.json"


class EmbedQueryRequest(BaseModel):
    text: str


@lru_cache(maxsize=1)
def get_tokenizer():
    tokenizer_path = hf_hub_download(
        repo_id=EMBEDDING_MODEL,
        filename=TOKENIZER_FILENAME,
    )

    tokenizer = Tokenizer.from_file(
        tokenizer_path
    )

    tokenizer.enable_truncation(
        max_length=512
    )

    return tokenizer


@lru_cache(maxsize=1)
def get_session():
    model_path = hf_hub_download(
        repo_id=EMBEDDING_MODEL,
        filename=ONNX_FILENAME,
    )

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False

    return ort.InferenceSession(
        model_path,
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


app = FastAPI(
    title="SentinelRAG Embedding Service",
    version="2.0.0",
)


def make_embedding(text: str) -> np.ndarray:
    tokenizer = get_tokenizer()
    session = get_session()

    encoded = tokenizer.encode(
        f"query: {text}",
        add_special_tokens=True,
    )

    input_ids = np.asarray(
        [encoded.ids],
        dtype=np.int64,
    )

    attention_mask = np.asarray(
        [encoded.attention_mask],
        dtype=np.int64,
    )

    type_ids = np.asarray(
        [encoded.type_ids],
        dtype=np.int64,
    )

    required_inputs = {
        item.name
        for item in session.get_inputs()
    }

    inputs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
    }

    if "token_type_ids" in required_inputs:
        inputs["token_type_ids"] = type_ids

    token_embeddings = session.run(
        None,
        inputs,
    )[0].astype(np.float32)

    mask = attention_mask[
        ..., None
    ].astype(np.float32)

    pooled = (
        token_embeddings * mask
    ).sum(axis=1) / np.clip(
        mask.sum(axis=1),
        1e-9,
        None,
    )

    pooled /= np.clip(
        np.linalg.norm(
            pooled,
            axis=1,
            keepdims=True,
        ),
        1e-12,
        None,
    )

    return pooled[0].astype(
        np.float32,
        copy=False,
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": EMBEDDING_MODEL,
        "backend": "onnxruntime-fp32",
        "dimension": EMBEDDING_DIMENSION,
    }


@app.post("/embed-query")
def embed_query(request: EmbedQueryRequest):
    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Query text cannot be empty.",
        )

    embedding = make_embedding(text)

    if embedding.shape != (EMBEDDING_DIMENSION,):
        raise HTTPException(
            status_code=500,
            detail="Unexpected embedding dimension.",
        )

    if not np.isfinite(embedding).all():
        raise HTTPException(
            status_code=500,
            detail="Embedding contains non-finite values.",
        )

    raw = embedding.astype(
        "<f4",
        copy=False,
    ).tobytes()

    return {
        "dimension": EMBEDDING_DIMENSION,
        "dtype": "float32",
        "normalized": True,
        "backend": "onnxruntime-fp32",
        "embedding_b64": base64.b64encode(
            raw
        ).decode("ascii"),
    }
