import csv
import json
import sys
import time
from pathlib import Path

import chromadb
import pymupdf
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from src.chunking import chunk_text
from src.embeddings import embed_passages
from src.bm25_index import (
    BM25_INDEX_PATH,
    build_bm25,
    save_bm25_index,
)


MANIFEST_PATH = Path(
    "data/sources_manifest.csv"
)

RAW_DIR = Path(
    "data/raw"
)

INDEX_DIR = Path(
    "data/index"
)

CHROMA_COLLECTION_NAME = (
    "sentinelrag_chunks"
)

EMBEDDING_BATCH_SIZE = 32


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest not found: "
            f"{MANIFEST_PATH}"
        )

    with MANIFEST_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    return rows


def extract_pdf(
    file_path: Path,
    source_id: str,
    title: str,
) -> list[dict]:
    units = []

    document = pymupdf.open(
        file_path
    )

    try:
        for page_index, page in enumerate(
            document,
            start=1,
        ):
            text = page.get_text(
                "text"
            ).strip()

            if not text:
                continue

            units.append(
                {
                    "source_id": source_id,
                    "source": file_path.name,
                    "title": title,
                    "document_type": "PDF",
                    "page": page_index,
                    "section_id": "",
                    "text": text,
                }
            )

    finally:
        document.close()

    return units


def extract_html(
    file_path: Path,
    source_id: str,
    title: str,
) -> list[dict]:
    html = file_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # Remove non-content elements.
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "form",
            "button",
            "iframe",
            "nav",
            "header",
            "footer",
        ]
    ):
        tag.decompose()

    # Remove common navigation and breadcrumb
    # containers.
    unwanted_selectors = [
        ".breadcrumb",
        ".breadcrumbs",
        ".usa-breadcrumb",
        ".usa-header",
        ".usa-footer",
        ".usa-nav",
        "[role='navigation']",
        "[aria-label='Breadcrumb']",
        "[aria-label='breadcrumb']",
        "[aria-label='Primary navigation']",
    ]

    for selector in unwanted_selectors:
        for element in soup.select(
            selector
        ):
            element.decompose()

    content_root = (
        soup.find("main")
        or soup.find("article")
        or soup.body
        or soup
    )

    text = content_root.get_text(
        separator="\n",
        strip=True,
    )

    # Remove heading permalink artifacts used
    # by documentation sites such as OWASP.
    text = text.replace(
        "¶",
        "",
    )

    # Prefer starting from the first main page
    # heading to remove residual navigation text.
    first_h1 = content_root.find(
        "h1"
    )

    if first_h1:
        heading_text = first_h1.get_text(
            separator=" ",
            strip=True,
        )

        if heading_text:
            heading_position = text.find(
                heading_text
            )

            if heading_position >= 0:
                text = text[
                    heading_position:
                ].strip()

    if not text:
        return []

    return [
        {
            "source_id": source_id,
            "source": file_path.name,
            "title": title,
            "document_type": "HTML",
            "page": None,
            "section_id": "",
            "text": text,
        }
    ]


def get_attack_external_id(
    obj: dict,
) -> str:
    references = obj.get(
        "external_references",
        [],
    )

    for reference in references:
        if (
            reference.get("source_name")
            == "mitre-attack"
        ):
            external_id = reference.get(
                "external_id"
            )

            if external_id:
                return external_id

    return ""


def format_attack_pattern(
    obj: dict,
) -> str:
    name = obj.get(
        "name",
        "",
    ).strip()

    description = obj.get(
        "description",
        "",
    ).strip()

    external_id = (
        get_attack_external_id(
            obj
        )
    )

    kill_chain_phases = []

    for phase in obj.get(
        "kill_chain_phases",
        [],
    ):
        phase_name = phase.get(
            "phase_name"
        )

        if phase_name:
            kill_chain_phases.append(
                phase_name
            )

    parts = []

    if external_id:
        parts.append(
            f"Technique ID: "
            f"{external_id}"
        )

    if name:
        parts.append(
            f"Technique Name: "
            f"{name}"
        )

    if kill_chain_phases:
        parts.append(
            "Tactics / Kill Chain Phases: "
            + ", ".join(
                kill_chain_phases
            )
        )

    if description:
        parts.append(
            f"Description:\n"
            f"{description}"
        )

    return "\n\n".join(
        parts
    ).strip()


def format_detection_strategy(
    obj: dict,
) -> str:
    name = obj.get(
        "name",
        "",
    ).strip()

    description = obj.get(
        "description",
        "",
    ).strip()

    parts = []

    if name:
        parts.append(
            f"Detection Strategy: "
            f"{name}"
        )

    if description:
        parts.append(
            f"Description:\n"
            f"{description}"
        )

    return "\n\n".join(
        parts
    ).strip()


def extract_mitre_json(
    file_path: Path,
    source_id: str,
    title: str,
) -> list[dict]:
    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    objects = data.get(
        "objects",
        [],
    )

    units = []

    technique_count = 0
    detection_count = 0

    for obj in objects:
        object_type = obj.get(
            "type",
            "",
        )

        if obj.get(
            "revoked",
            False,
        ):
            continue

        if obj.get(
            "x_mitre_deprecated",
            False,
        ):
            continue

        if object_type == "attack-pattern":
            text = format_attack_pattern(
                obj
            )

            if not text:
                continue

            external_id = (
                get_attack_external_id(
                    obj
                )
            )

            section_id = (
                external_id
                or obj.get(
                    "id",
                    "",
                )
            )

            units.append(
                {
                    "source_id": source_id,
                    "source": file_path.name,
                    "title": title,
                    "document_type": "JSON",
                    "page": None,
                    "section_id": section_id,
                    "text": text,
                }
            )

            technique_count += 1

        elif (
            object_type
            == "x-mitre-detection-strategy"
        ):
            text = (
                format_detection_strategy(
                    obj
                )
            )

            if not text:
                continue

            section_id = obj.get(
                "id",
                "",
            )

            units.append(
                {
                    "source_id": source_id,
                    "source": file_path.name,
                    "title": title,
                    "document_type": "JSON",
                    "page": None,
                    "section_id": section_id,
                    "text": text,
                }
            )

            detection_count += 1

    print(
        "    MITRE techniques: "
        f"{technique_count}"
    )

    print(
        "    MITRE detection strategies: "
        f"{detection_count}"
    )

    return units


def extract_source(
    row: dict,
) -> list[dict]:
    source_id = row[
        "source_id"
    ].strip()

    title = row[
        "title"
    ].strip()

    file_name = row[
        "file_name"
    ].strip()

    document_type = row[
        "document_type"
    ].strip().upper()

    file_path = (
        RAW_DIR / file_name
    )

    if not file_path.exists():
        raise FileNotFoundError(
            "Source file not found: "
            f"{file_path}"
        )

    if document_type == "PDF":
        return extract_pdf(
            file_path=file_path,
            source_id=source_id,
            title=title,
        )

    if document_type == "HTML":
        return extract_html(
            file_path=file_path,
            source_id=source_id,
            title=title,
        )

    if document_type == "JSON":
        return extract_mitre_json(
            file_path=file_path,
            source_id=source_id,
            title=title,
        )

    raise ValueError(
        "Unsupported document type: "
        f"{document_type}"
    )


def chunk_extracted_units(
    units: list[dict],
) -> list[dict]:
    """
    Convert extracted units into deterministic,
    metadata-rich chunks.
    """
    all_chunks = []

    for unit in units:
        source = unit.get(
            "source",
            "",
        )

        section_id = unit.get(
            "section_id",
            "",
        )

        chunk_id_source = source

        if section_id:
            chunk_id_source = (
                f"{source}::{section_id}"
            )

        unit_chunks = chunk_text(
            text=unit.get(
                "text",
                "",
            ),
            source=chunk_id_source,
            page=unit.get(
                "page"
            ),
            title=unit.get(
                "title",
                "",
            ),
        )

        for chunk in unit_chunks:
            chunk["source"] = source

            chunk["source_id"] = (
                unit.get(
                    "source_id",
                    "",
                )
            )

            chunk["document_type"] = (
                unit.get(
                    "document_type",
                    "",
                )
            )

            chunk["section_id"] = (
                section_id
            )

        all_chunks.extend(
            unit_chunks
        )

    return all_chunks


def chunk_to_metadata(
    chunk: dict,
) -> dict:
    """
    Convert chunk metadata into Chroma-compatible
    scalar values.

    Chroma metadata cannot contain None.
    """
    page = chunk.get(
        "page"
    )

    if page is None:
        page = -1

    return {
        "source_id": str(
            chunk.get(
                "source_id",
                "",
            )
        ),
        "source": str(
            chunk.get(
                "source",
                "",
            )
        ),
        "title": str(
            chunk.get(
                "title",
                "",
            )
        ),
        "document_type": str(
            chunk.get(
                "document_type",
                "",
            )
        ),
        "page": int(
            page
        ),
        "section_id": str(
            chunk.get(
                "section_id",
                "",
            )
        ),
        "chunk_index": int(
            chunk.get(
                "chunk_index",
                0,
            )
        ),
        "token_count": int(
            chunk.get(
                "token_count",
                0,
            )
        ),
    }


def create_clean_collection(
    client,
):
    """
    Delete the previous collection if it exists,
    then create a fresh cosine-distance collection.
    """
    try:
        client.get_collection(
            CHROMA_COLLECTION_NAME
        )

    except Exception:
        pass

    else:
        client.delete_collection(
            CHROMA_COLLECTION_NAME
        )

    return client.create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
        },
    )


def add_chunks_to_chroma(
    collection,
    chunks: list[dict],
) -> None:
    """
    Embed and store chunks in manageable batches.
    """
    for start in range(
        0,
        len(chunks),
        EMBEDDING_BATCH_SIZE,
    ):
        batch = chunks[
            start:
            start + EMBEDDING_BATCH_SIZE
        ]

        texts = [
            chunk["text"]
            for chunk in batch
        ]

        embeddings = embed_passages(
            texts,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=False,
        )

        collection.add(
            ids=[
                chunk["chunk_id"]
                for chunk in batch
            ],
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=[
                chunk_to_metadata(
                    chunk
                )
                for chunk in batch
            ],
        )


def main() -> int:
    start_time = time.perf_counter()

    try:
        rows = load_manifest()

        if not rows:
            print(
                "ERROR: Manifest contains "
                "no sources."
            )
            return 1

        INDEX_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            "SentinelRAG ingestion"
        )
        print(
            "====================="
        )
        print(
            f"Manifest sources: "
            f"{len(rows)}"
        )
        print(
            f"Embedding batch size: "
            f"{EMBEDDING_BATCH_SIZE}"
        )
        print()

        client = chromadb.PersistentClient(
            path=str(
                INDEX_DIR
            )
        )

        collection = (
            create_clean_collection(
                client
            )
        )

        documents_processed = 0
        total_units = 0
        total_chunks = 0

        seen_chunk_ids = set()

        # Keep exactly the same chunks used for Chroma
        # so BM25 and vector retrieval cannot drift apart.
        all_chunks = []

        for index, row in enumerate(
            rows,
            start=1,
        ):
            source_id = row[
                "source_id"
            ].strip()

            print(
                f"[{index}/{len(rows)}] "
                f"{source_id}"
            )

            units = extract_source(
                row
            )

            chunks = (
                chunk_extracted_units(
                    units
                )
            )

            if not units:
                raise RuntimeError(
                    "No extracted units for "
                    f"{source_id}"
                )

            if not chunks:
                raise RuntimeError(
                    "No chunks generated for "
                    f"{source_id}"
                )

            for chunk in chunks:
                chunk_id = chunk[
                    "chunk_id"
                ]

                if (
                    chunk_id
                    in seen_chunk_ids
                ):
                    raise RuntimeError(
                        "Duplicate chunk ID "
                        f"detected: {chunk_id}"
                    )

                seen_chunk_ids.add(
                    chunk_id
                )

            # Store vectors in Chroma.
            add_chunks_to_chroma(
                collection,
                chunks,
            )

            # Store the exact same chunks for BM25.
            all_chunks.extend(
                chunks
            )

            documents_processed += 1
            total_units += len(
                units
            )
            total_chunks += len(
                chunks
            )

            print(
                f"    Units: "
                f"{len(units)}"
            )

            print(
                f"    Chunks: "
                f"{len(chunks)}"
            )

            print(
                f"    Collection count: "
                f"{collection.count()}"
            )

        stored_count = (
            collection.count()
        )

        if (
            documents_processed
            != len(rows)
        ):
            raise RuntimeError(
                "Not all manifest sources "
                "were processed."
            )

        if stored_count != total_chunks:
            raise RuntimeError(
                "Chroma count does not match "
                "generated chunks."
            )

        if (
            len(seen_chunk_ids)
            != total_chunks
        ):
            raise RuntimeError(
                "Chunk IDs are not globally unique."
            )

        if len(all_chunks) != total_chunks:
            raise RuntimeError(
                "BM25 source chunk count does not "
                "match generated chunks."
            )

        print()
        print(
            "Building BM25 index..."
        )

        bm25_index = build_bm25(
            all_chunks
        )

        save_bm25_index(
            bm25_index
        )

        bm25_chunk_count = len(
            bm25_index[
                "chunks"
            ]
        )

        if (
            bm25_chunk_count
            != total_chunks
        ):
            raise RuntimeError(
                "BM25 chunk count does not match "
                "generated chunks."
            )

        if not BM25_INDEX_PATH.exists():
            raise RuntimeError(
                "BM25 index file was not created."
            )

        elapsed = (
            time.perf_counter()
            - start_time
        )

        print()
        print(
            "Ingestion summary"
        )
        print(
            "-----------------"
        )
        print(
            "Documents processed: "
            f"{documents_processed}"
        )
        print(
            "Units extracted:      "
            f"{total_units}"
        )
        print(
            "Chunks generated:     "
            f"{total_chunks}"
        )
        print(
            "Chroma chunks stored: "
            f"{stored_count}"
        )
        print(
            "BM25 chunks indexed:  "
            f"{bm25_chunk_count}"
        )
        print(
            "Unique chunk IDs:     "
            f"{len(seen_chunk_ids)}"
        )
        print(
            "BM25 index path:      "
            f"{BM25_INDEX_PATH}"
        )
        print(
            "Elapsed seconds:      "
            f"{elapsed:.2f}"
        )

        print()
        print(
            "Hybrid ingestion PASSED."
        )

        return 0

    except Exception as exc:
        print()
        print(
            "INGESTION FAILED:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 10

    finally:
        if "client" in locals():
            try:
                client.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(
        main()
    )