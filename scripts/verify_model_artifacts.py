"""Verify repository model bytes without ML imports, API calls, or index access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

BLOCK_SIZE = 1024 * 1024
APPROVED_WEIGHTS_SHA256 = "0862247181afba7ed18801ddd725094bd6786915441cda628aafbcf5af040f90"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def require_checksum(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Asset checksum mismatch: {path.name}; expected={expected}; actual={actual}")


def verify(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("model") != "intfloat/multilingual-e5-small" or manifest.get("dimension") != 384:
        raise ValueError("Unexpected model identity or dimension")
    if manifest.get("model_bin_sha256") != APPROVED_WEIGHTS_SHA256:
        raise ValueError("Approved weights checksum must not change")
    expected_assets = manifest.get("files_sha256", {})
    if set(expected_assets) != {"model.xml", "tokenizer.json"}:
        raise ValueError("Expected explicit checksums for model.xml and tokenizer.json")
    for name, expected in expected_assets.items():
        require_checksum(root / name, expected)
    parts = manifest.get("parts", [])
    if not parts:
        raise ValueError("Missing weight parts")
    digest = hashlib.sha256()
    total = 0
    for index, part in enumerate(parts, 1):
        name = f"model.bin.part{index:03d}"
        if part.get("name") != name:
            raise ValueError("Weight parts missing or out of order")
        path = root / name
        if path.stat().st_size != part.get("size_bytes"):
            raise ValueError(f"Wrong weight part size: {name}")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(BLOCK_SIZE), b""):
                digest.update(block)
                total += len(block)
    if total != manifest.get("model_bin_size_bytes"):
        raise ValueError("Wrong combined weight size")
    if digest.hexdigest() != APPROVED_WEIGHTS_SHA256:
        raise ValueError("Combined weight checksum mismatch")
    result = {"assets": expected_assets, "weights_sha256": digest.hexdigest(), "weights_bytes": total,
              "parts": len(parts), "verified": True}
    print("MODEL_ARTIFACTS=" + json.dumps(result, sort_keys=True))
    print("MODEL_ARTIFACT_INTEGRITY=PASSED")
    print("COHERE_CALLS=0; RAGAS_CALLS=0; CHROMA_OPENED=NO; MODEL_INFERENCE=NOT_RUN")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "models/e5_openvino_fp16")
    verify(parser.parse_args().root)
