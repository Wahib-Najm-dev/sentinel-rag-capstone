import hashlib
import re

from transformers import AutoTokenizer

from src.config import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    EMBEDDING_MODEL,
)


_tokenizer = None


def get_tokenizer():
    global _tokenizer

    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(
            EMBEDDING_MODEL,
            use_fast=True,
        )

    return _tokenizer


def normalize_text(text: str) -> str:
    """
    Perform conservative text cleanup without aggressively
    modifying the original document content.
    """
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    lines = []

    for line in text.split("\n"):
        cleaned_line = re.sub(
            r"[ \t]+",
            " ",
            line,
        ).strip()

        lines.append(cleaned_line)

    text = "\n".join(lines)

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def count_tokens(text: str) -> int:
    tokenizer = get_tokenizer()

    token_ids = tokenizer.encode(
        text,
        add_special_tokens=False,
        truncation=False,
        verbose=False,
    )

    return len(token_ids)


def _split_by_tokens(
    text: str,
    max_tokens: int,
) -> list[str]:
    tokenizer = get_tokenizer()

    token_ids = tokenizer.encode(
        text,
        add_special_tokens=False,
        truncation=False,
        verbose=False,
    )

    pieces = []

    for start in range(
        0,
        len(token_ids),
        max_tokens,
    ):
        piece_ids = token_ids[
            start : start + max_tokens
        ]

        piece = tokenizer.decode(
            piece_ids,
            skip_special_tokens=True,
        ).strip()

        if piece:
            pieces.append(piece)

    return pieces


def _split_long_text(
    text: str,
    max_tokens: int,
) -> list[str]:
    """
    Recursively split text while preferring natural
    document boundaries:

    paragraphs -> lines -> sentences -> token windows
    """
    text = text.strip()

    if not text:
        return []

    if count_tokens(text) <= max_tokens:
        return [text]

    paragraphs = [
        part.strip()
        for part in re.split(
            r"\n{2,}",
            text,
        )
        if part.strip()
    ]

    if len(paragraphs) > 1:
        pieces = []

        for paragraph in paragraphs:
            pieces.extend(
                _split_long_text(
                    paragraph,
                    max_tokens,
                )
            )

        return pieces

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    if len(lines) > 1:
        pieces = []

        for line in lines:
            pieces.extend(
                _split_long_text(
                    line,
                    max_tokens,
                )
            )

        return pieces

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text,
        )
        if sentence.strip()
    ]

    if len(sentences) > 1:
        pieces = []

        for sentence in sentences:
            pieces.extend(
                _split_long_text(
                    sentence,
                    max_tokens,
                )
            )

        return pieces

    return _split_by_tokens(
        text,
        max_tokens,
    )


def _get_overlap_text(
    text: str,
    overlap_tokens: int,
) -> str:
    if overlap_tokens <= 0:
        return ""

    tokenizer = get_tokenizer()

    token_ids = tokenizer.encode(
        text,
        add_special_tokens=False,
        truncation=False,
        verbose=False,
    )

    if not token_ids:
        return ""

    overlap_ids = token_ids[
        -overlap_tokens:
    ]

    return tokenizer.decode(
        overlap_ids,
        skip_special_tokens=True,
    ).strip()


def make_chunk_id(
    source: str,
    page: int | None,
    chunk_index: int,
    text: str,
) -> str:
    """
    Generate a deterministic ID for retrieval evaluation.
    """
    raw_value = (
        f"{source}|"
        f"{page}|"
        f"{chunk_index}|"
        f"{text}"
    )

    digest = hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()

    return digest[:24]


def chunk_text(
    text: str,
    source: str,
    page: int | None = None,
    title: str | None = None,
    chunk_size_tokens: int = CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[dict]:
    """
    Split document text into deterministic,
    metadata-rich chunks.

    Target:
        approximately 350 E5 tokens per chunk

    Overlap:
        approximately 60 E5 tokens
    """
    if chunk_size_tokens <= 0:
        raise ValueError(
            "chunk_size_tokens must be greater than 0"
        )

    if chunk_overlap_tokens < 0:
        raise ValueError(
            "chunk_overlap_tokens cannot be negative"
        )

    if chunk_overlap_tokens >= chunk_size_tokens:
        raise ValueError(
            "chunk_overlap_tokens must be smaller "
            "than chunk_size_tokens"
        )

    cleaned_text = normalize_text(text)

    if not cleaned_text:
        return []

    structural_unit_limit = (
        chunk_size_tokens
        - chunk_overlap_tokens
    )

    units = _split_long_text(
        cleaned_text,
        structural_unit_limit,
    )

    chunk_texts = []
    current_chunk = ""

    for unit in units:
        if not current_chunk:
            current_chunk = unit
            continue

        candidate = (
            f"{current_chunk}\n\n{unit}"
        )

        if (
            count_tokens(candidate)
            <= chunk_size_tokens
        ):
            current_chunk = candidate
            continue

        chunk_texts.append(
            current_chunk.strip()
        )

        overlap_text = _get_overlap_text(
            current_chunk,
            chunk_overlap_tokens,
        )

        if overlap_text:
            candidate = (
                f"{overlap_text}\n\n{unit}"
            )
        else:
            candidate = unit

        if (
            count_tokens(candidate)
            <= chunk_size_tokens
        ):
            current_chunk = candidate

        else:
            current_chunk = unit

    if current_chunk.strip():
        chunk_texts.append(
            current_chunk.strip()
        )

    chunks = []

    for chunk_index, chunk_content in enumerate(
        chunk_texts
    ):
        token_count = count_tokens(
            chunk_content
        )

        chunk = {
            "chunk_id": make_chunk_id(
                source=source,
                page=page,
                chunk_index=chunk_index,
                text=chunk_content,
            ),
            "source": source,
            "page": page,
            "title": title or "",
            "chunk_index": chunk_index,
            "text": chunk_content,
            "token_count": token_count,
        }

        chunks.append(chunk)

    return chunks