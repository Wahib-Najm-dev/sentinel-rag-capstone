import csv
import json
import sys
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

from src.chunking import chunk_text


MANIFEST_PATH = Path("data/sources_manifest.csv")
RAW_DIR = Path("data/raw")


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest not found: {MANIFEST_PATH}"
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

    # Remove common navigation and breadcrumb containers.
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

    # Remove heading permalink artifacts used by
    # documentation sites such as OWASP.
    text = text.replace(
        "¶",
        "",
    )

    # Prefer starting from the first main page heading.
    # This removes residual navigation or utility text
    # that may appear before the real document content.
    first_h1 = content_root.find("h1")

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
        get_attack_external_id(obj)
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
            f"Technique ID: {external_id}"
        )

    if name:
        parts.append(
            f"Technique Name: {name}"
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
            f"Description:\n{description}"
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
            f"Detection Strategy: {name}"
        )

    if description:
        parts.append(
            f"Description:\n{description}"
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
        data = json.load(file)

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
                or obj.get("id", "")
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
            text = format_detection_strategy(
                obj
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
        "MITRE extraction summary:"
    )
    print(
        f"  Techniques: "
        f"{technique_count}"
    )
    print(
        f"  Detection strategies: "
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
            f"Source file not found: "
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
    Convert extracted document units into deterministic,
    metadata-rich chunks.

    Preserves:
        source_id
        source
        title
        page
        section_id
        document_type

    Chunk size and overlap are controlled by src.config.
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

        # MITRE contains many independent sections inside
        # one JSON file. Include the section ID in the
        # internal deterministic-ID source key so chunks
        # from different ATT&CK objects cannot collide.
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
            # Restore the real filename for citations
            # while keeping the deterministic chunk ID
            # already generated above.
            chunk["source"] = source

            chunk["source_id"] = unit.get(
                "source_id",
                "",
            )

            chunk["document_type"] = unit.get(
                "document_type",
                "",
            )

            chunk["section_id"] = section_id

        all_chunks.extend(
            unit_chunks
        )

    return all_chunks


def main() -> int:
    rows = load_manifest()

    print(
        f"Manifest sources: {len(rows)}"
    )
    print(
        "Extraction module ready."
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )