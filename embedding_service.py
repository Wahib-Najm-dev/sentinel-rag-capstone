"""Private, single-worker E5 service using a prebuilt OpenVINO IR.

No downloading, conversion, PyTorch, Transformers, or ONNX Runtime at runtime.
Run: python -m uvicorn embedding_service:app --host 0.0.0.0 --port 8000 --workers 1
Check locally: python embedding_service.py --smoke-test
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import threading
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

# Allocator settings such as MALLOC_ARENA_MAX should also be set in Railway
# Variables, before the Python process starts.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
import openvino as ov
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from tokenizers import Tokenizer

MODEL_ID = "intfloat/multilingual-e5-small"
DIMENSION = 384
OPENVINO_VERSION = "2026.4.1"
MODEL_DIR = Path(__file__).resolve().parent / "models" / "e5_openvino_fp16"
EXPECTED_BIN_SHA256 = "0862247181afba7ed18801ddd725094bd6786915441cda628aafbcf5af040f90"
BACKEND = "openvino-fp16-weights-f32-inference"
BLOCK_SIZE = 1024 * 1024
MAX_QUERY_CHARS = 16000
logger = logging.getLogger("uvicorn.error")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def memory_snapshot() -> dict:
    """Linux process/cgroup measurements; omitted where unavailable."""
    out = {}
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            key = line.split(":", 1)[0]
            if key in ("VmRSS", "VmHWM"):
                out[key + "_MiB"] = round(int(line.split()[1]) / 1024, 2)
    except (OSError, ValueError, IndexError):
        pass
    for name in ("memory.current", "memory.peak", "memory.max"):
        try:
            value = (Path("/sys/fs/cgroup") / name).read_text().strip()
            if value.isdigit():
                out[name + "_MiB"] = round(int(value) / 1048576, 2)
        except OSError:
            pass
    return out


def log_stage(name: str) -> None:
    logger.info("E5 stage=%s pid=%s memory=%s", name, os.getpid(), memory_snapshot())


def prepare_artifacts() -> tuple[Path, str]:
    """Verify and assemble the weights in 1 MiB blocks, never one large bytes object."""
    manifest_path = MODEL_DIR / "manifest.json"
    with manifest_path.open("r", encoding="utf-8-sig") as stream:
        manifest = json.load(stream)
    if manifest.get("model") != MODEL_ID or manifest.get("dimension") != DIMENSION:
        raise RuntimeError("Model identity/dimension mismatch in manifest.")
    if manifest.get("format") != "openvino-ir-fp16":
        raise RuntimeError("Unexpected artifact format.")
    expected_hash = manifest.get("model_bin_sha256")
    if expected_hash != EXPECTED_BIN_SHA256:
        raise RuntimeError("Model checksum does not match the approved artifact.")
    expected_size = manifest.get("model_bin_size_bytes")
    if type(expected_size) is not int or expected_size <= 0:
        raise RuntimeError("Invalid model size in manifest.")

    for name in ("model.xml", "tokenizer.json"):
        path = MODEL_DIR / name
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Missing model asset: {name}")
        expected = manifest.get("files_sha256", {}).get(name)
        if expected and file_sha256(path) != expected:
            raise RuntimeError(f"Asset checksum mismatch: {name}")

    weights = MODEL_DIR / "model.bin"
    if (weights.is_file() and weights.stat().st_size == expected_size
            and file_sha256(weights) == expected_hash):
        log_stage("weights-already-verified")
        return MODEL_DIR / "model.xml", expected_hash

    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("No model parts listed in manifest.")
    total_size = 0
    for index, part in enumerate(parts, 1):
        name = part.get("name", "")
        if name != f"model.bin.part{index:03d}" or not re.fullmatch(r"model\.bin\.part\d{3}", name):
            raise RuntimeError("Invalid or out-of-order model part.")
        size = part.get("size_bytes")
        if type(size) is not int or size <= 0:
            raise RuntimeError(f"Invalid model part size: {name}")
        path = MODEL_DIR / name
        if not path.is_file() or path.stat().st_size != size:
            raise RuntimeError(f"Missing/truncated model part: {name}")
        total_size += size
    if total_size != expected_size:
        raise RuntimeError("Model part sizes do not add up to the expected total.")

    log_stage("assembling-weights")
    fd, temp_name = tempfile.mkstemp(prefix="model.bin.", suffix=".tmp", dir=MODEL_DIR)
    temp_path = Path(temp_name)
    digest = hashlib.sha256()
    written = 0
    try:
        with os.fdopen(fd, "wb") as output:
            for part in parts:
                with (MODEL_DIR / part["name"]).open("rb") as source:
                    for block in iter(lambda: source.read(BLOCK_SIZE), b""):
                        output.write(block)
                        digest.update(block)
                        written += len(block)
            output.flush()
            os.fsync(output.fileno())
        if written != expected_size or digest.hexdigest() != expected_hash:
            raise RuntimeError("Assembled weights failed size/SHA-256 verification.")
        os.replace(temp_path, weights)
    finally:
        temp_path.unlink(missing_ok=True)
    log_stage("weights-sha256-verified")
    return MODEL_DIR / "model.xml", expected_hash


def cpu_compile_config(core) -> dict:
    """Use CPU-supported settings only; never silently change inference precision.

    COMPILATION_NUM_THREADS is not accepted by the CPU plugin used here.
    INFERENCE_NUM_THREADS limits inference threads, not compilation threads.
    """
    config = {
        "PERFORMANCE_HINT": "LATENCY",
        "NUM_STREAMS": 1,
        "INFERENCE_NUM_THREADS": 1,
        "INFERENCE_PRECISION_HINT": ov.Type.f32,
    }
    supported = {str(name) for name in core.get_property("CPU", "SUPPORTED_PROPERTIES")}
    missing = sorted(set(config) - supported)
    if missing:
        raise RuntimeError(
            "CPU plugin does not support required settings: "
            + ", ".join(missing)
            + ". No precision fallback was applied."
        )
    return config


class ServiceBusyError(RuntimeError):
    pass


class E5Runtime:
    """One compiled model and one inference request per worker."""
    def __init__(self) -> None:
        if version("openvino") != OPENVINO_VERSION:
            raise RuntimeError(f"This artifact requires openvino=={OPENVINO_VERSION}.")
        # Validate CPU-specific properties before assembling/loading E5.
        self.core = ov.Core()
        compile_config = cpu_compile_config(self.core)
        self.core.set_property({"ENABLE_MMAP": True})
        print("CPU_CONFIG_CHECK=PASSED", flush=True)
        xml_path, self.model_sha256 = prepare_artifacts()
        self.lock = threading.Lock()
        self.tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=512)
        log_stage("compiling-model")
        # Direct path compilation avoids retaining an additional Python Model object.
        # FP16 describes stored weights. f32 prevents CPU-dependent BF16 selection.
        self.compiled = self.core.compile_model(str(xml_path), "CPU", compile_config)
        self.input_names = {port.get_any_name() for port in self.compiled.inputs}
        allowed = {"input_ids", "attention_mask", "token_type_ids"}
        if not {"input_ids", "attention_mask"}.issubset(self.input_names) or not self.input_names.issubset(allowed):
            raise RuntimeError("Unexpected model input names.")
        self.request = self.compiled.create_infer_request()
        log_stage("model-compiled")

    def embed(self, text: str) -> np.ndarray:
        text = text.strip()
        if not text or len(text) > MAX_QUERY_CHARS:
            raise ValueError("Query must contain 1 to 16000 characters.")
        if not self.lock.acquire(blocking=False):
            raise ServiceBusyError("Embedding worker is busy.")
        try:
            encoded = self.tokenizer.encode(f"query: {text}", add_special_tokens=True)
            ids = np.asarray([encoded.ids], dtype=np.int64)
            attention = np.asarray([encoded.attention_mask], dtype=np.int64)
            inputs = {"input_ids": ids, "attention_mask": attention}
            if "token_type_ids" in self.input_names:
                inputs["token_type_ids"] = np.asarray([encoded.type_ids], dtype=np.int64)
            self.request.infer(inputs)
            tokens = np.asarray(self.request.get_output_tensor(0).data, dtype=np.float32)
            if tokens.ndim != 3 or tokens.shape != (1, ids.shape[1], DIMENSION):
                raise RuntimeError("Unexpected token-embedding output shape.")
            mask = attention[..., None].astype(np.float32)
            pooled = (tokens * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            if not np.isfinite(norms).all() or np.any(norms < 1e-12):
                raise RuntimeError("Invalid embedding norm.")
            vector = (pooled / norms)[0].astype(np.float32, copy=True)
            if vector.shape != (DIMENSION,) or not np.isfinite(vector).all():
                raise RuntimeError("Invalid embedding vector.")
            return vector
        finally:
            self.lock.release()


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.runtime = None
    log_stage("startup")
    runtime = E5Runtime()
    runtime.embed("startup readiness check")
    application.state.runtime = runtime
    log_stage("ready-after-real-inference")
    try:
        yield
    finally:
        application.state.runtime = None


app = FastAPI(title="SentinelRAG Embedding Service", version="3.0.0", lifespan=lifespan)


class EmbedQueryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)


@app.get("/health")
def health() -> dict:
    runtime = getattr(app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Embedding model is not ready.")
    return {
        "status": "ok", "model": MODEL_ID, "backend": BACKEND,
        "dimension": DIMENSION, "model_sha256": runtime.model_sha256,
        "openvino_version": version("openvino"), "pid": os.getpid(),
    }


@app.post("/embed-query")
def embed_query(request: EmbedQueryRequest) -> dict:
    runtime = getattr(app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Embedding model is not ready.")
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Query text cannot be empty.")
    try:
        vector = runtime.embed(request.text)
    except ServiceBusyError:
        raise HTTPException(status_code=429, detail="Embedding worker is busy.", headers={"Retry-After": "1"}) from None
    except Exception:
        # Do not return model paths, query content, or stack traces to callers.
        logger.error("E5 inference failed; pid=%s memory=%s", os.getpid(), memory_snapshot())
        raise HTTPException(status_code=500, detail="Embedding inference failed.") from None
    return {
        "dimension": DIMENSION, "dtype": "float32", "normalized": True,
        "backend": BACKEND,
        "embedding_b64": base64.b64encode(vector.astype("<f4", copy=False).tobytes()).decode("ascii"),
    }


async def smoke_test() -> None:
    async with lifespan(app):
        status = health()
        payload = embed_query(EmbedQueryRequest(text="What information from logs helps investigate an incident?"))
        vector = np.frombuffer(base64.b64decode(payload["embedding_b64"], validate=True), dtype="<f4")
        if vector.shape != (DIMENSION,) or not np.isfinite(vector).all():
            raise RuntimeError("Smoke test failed: invalid vector.")
        if abs(float(np.linalg.norm(vector)) - 1.0) > 1e-5:
            raise RuntimeError("Smoke test failed: vector not normalized.")
        forbidden = [name for name in ("torch", "sentence_transformers", "transformers", "onnxruntime") if name in sys.modules]
        if forbidden:
            raise RuntimeError("Unexpected heavy runtime imports: " + ", ".join(forbidden))
        print("OPENVINO_VERSION=", status["openvino_version"])
        print("MODEL_SHA256=", status["model_sha256"])
        print("BACKEND=", payload["backend"])
        print("HEALTH=", status["status"])
        print("DIM=", vector.size)
        print("NORM=", round(float(np.linalg.norm(vector)), 6))
        for name in ("torch", "sentence_transformers", "transformers", "onnxruntime"):
            print(name + "_loaded=", name in sys.modules)
        print("MEMORY_LOCAL=", memory_snapshot())
        print("COHERE_CALLS=0")
        print("LOCAL_SMOKE_TEST=PASSED")


if __name__ == "__main__":
    if sys.argv[1:] != ["--smoke-test"]:
        raise SystemExit("Use --smoke-test, or start with uvicorn embedding_service:app.")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(smoke_test())