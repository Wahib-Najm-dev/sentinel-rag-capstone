import csv
import json
import sys
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup


MANIFEST_PATH = Path("data/sources_manifest.csv")
RAW_DIR = Path("data/raw")

SUPPORTED_TYPES = {"PDF", "HTML", "JSON"}
MIN_DOCUMENTS = 20
MIN_TEXT_CHARACTERS = 200


def check_pdf(file_path: Path) -> tuple[bool, str, dict]:
    try:
        document = pymupdf.open(file_path)
    except Exception as exc:
        return False, f"Could not open PDF: {exc}", {}

    try:
        page_count = document.page_count

        if page_count <= 0:
            return False, "PDF contains no pages", {}

        total_characters = 0
        pages_with_text = 0

        for page in document:
            text = page.get_text("text").strip()

            if text:
                pages_with_text += 1
                total_characters += len(text)

        metadata = {
            "pages": page_count,
            "pages_with_text": pages_with_text,
            "characters": total_characters,
        }

        if total_characters < MIN_TEXT_CHARACTERS:
            return (
                False,
                (
                    "PDF contains too little extractable text "
                    f"({total_characters} characters)"
                ),
                metadata,
            )

        return True, "OK", metadata

    finally:
        document.close()


def check_html(file_path: Path) -> tuple[bool, str, dict]:
    try:
        html = file_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return False, f"Could not read HTML: {exc}", {}

    try:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )
    except Exception as exc:
        return False, f"Could not parse HTML: {exc}", {}

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
        ]
    ):
        tag.decompose()

    text = soup.get_text(
        separator=" ",
        strip=True,
    )

    character_count = len(text)

    metadata = {
        "characters": character_count,
        "title": (
            soup.title.get_text(strip=True)
            if soup.title
            else ""
        ),
    }

    if character_count < MIN_TEXT_CHARACTERS:
        return (
            False,
            (
                "HTML contains too little extractable text "
                f"({character_count} characters)"
            ),
            metadata,
        )

    return True, "OK", metadata


def check_json(file_path: Path) -> tuple[bool, str, dict]:
    try:
        with file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        return False, f"Could not parse JSON: {exc}", {}

    metadata = {}

    if isinstance(data, dict):
        metadata["top_level_type"] = "object"
        metadata["top_level_keys"] = len(data)

        objects = data.get("objects")

        if isinstance(objects, list):
            metadata["objects"] = len(objects)

            if len(objects) == 0:
                return (
                    False,
                    "JSON contains an empty objects list",
                    metadata,
                )

        elif len(data) == 0:
            return (
                False,
                "JSON object is empty",
                metadata,
            )

    elif isinstance(data, list):
        metadata["top_level_type"] = "array"
        metadata["items"] = len(data)

        if len(data) == 0:
            return (
                False,
                "JSON array is empty",
                metadata,
            )

    else:
        return (
            False,
            "JSON top-level value is not an object or array",
            metadata,
        )

    return True, "OK", metadata


def check_file(
    file_path: Path,
    document_type: str,
) -> tuple[bool, str, dict]:
    if document_type == "PDF":
        return check_pdf(file_path)

    if document_type == "HTML":
        return check_html(file_path)

    if document_type == "JSON":
        return check_json(file_path)

    return (
        False,
        f"Unsupported document type: {document_type}",
        {},
    )


def format_details(
    document_type: str,
    metadata: dict,
) -> str:
    if document_type == "PDF":
        return (
            f"pages={metadata.get('pages', 0)}, "
            f"text_pages={metadata.get('pages_with_text', 0)}, "
            f"characters={metadata.get('characters', 0)}"
        )

    if document_type == "HTML":
        return (
            f"characters={metadata.get('characters', 0)}"
        )

    if document_type == "JSON":
        if "objects" in metadata:
            return (
                f"objects={metadata['objects']}"
            )

        if "items" in metadata:
            return (
                f"items={metadata['items']}"
            )

        return (
            f"keys={metadata.get('top_level_keys', 0)}"
        )

    return ""


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(
            f"ERROR: Manifest not found: "
            f"{MANIFEST_PATH}"
        )
        return 1

    if not RAW_DIR.exists():
        print(
            f"ERROR: Raw corpus directory not found: "
            f"{RAW_DIR}"
        )
        return 1

    with MANIFEST_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    if not rows:
        print("ERROR: Manifest contains no sources.")
        return 1

    print(
        f"Checking {len(rows)} corpus sources..."
    )
    print()

    manifest_ids = set()
    expected_files = set()

    valid_count = 0
    invalid_count = 0
    missing_count = 0

    pdf_count = 0
    html_count = 0
    json_count = 0

    for index, row in enumerate(
        rows,
        start=1,
    ):
        source_id = row[
            "source_id"
        ].strip()

        file_name = row[
            "file_name"
        ].strip()

        document_type = row[
            "document_type"
        ].strip().upper()

        print(
            f"[{index}/{len(rows)}] "
            f"{source_id} -> {file_name}"
        )

        if source_id in manifest_ids:
            print(
                "    INVALID: duplicate source_id"
            )
            invalid_count += 1
            continue

        manifest_ids.add(source_id)

        if document_type not in SUPPORTED_TYPES:
            print(
                "    INVALID: unsupported type "
                f"{document_type!r}"
            )
            invalid_count += 1
            continue

        file_path = RAW_DIR / file_name
        expected_files.add(file_name)

        if not file_path.exists():
            print(
                "    MISSING: file does not exist"
            )
            missing_count += 1
            continue

        if not file_path.is_file():
            print(
                "    INVALID: path is not a file"
            )
            invalid_count += 1
            continue

        size_bytes = file_path.stat().st_size

        if size_bytes <= 0:
            print(
                "    INVALID: file is empty"
            )
            invalid_count += 1
            continue

        valid, message, metadata = check_file(
            file_path,
            document_type,
        )

        if not valid:
            print(
                f"    INVALID: {message}"
            )
            invalid_count += 1
            continue

        if document_type == "PDF":
            pdf_count += 1

        elif document_type == "HTML":
            html_count += 1

        elif document_type == "JSON":
            json_count += 1

        valid_count += 1

        size_kb = size_bytes / 1024

        details = format_details(
            document_type,
            metadata,
        )

        print(
            f"    VALID "
            f"({size_kb:.1f} KB, {details})"
        )

    actual_files = {
        path.name
        for path in RAW_DIR.iterdir()
        if path.is_file()
    }

    unexpected_files = sorted(
        actual_files - expected_files
    )

    print()
    print("Corpus validation summary")
    print("-------------------------")
    print(
        f"Manifest sources: {len(rows)}"
    )
    print(
        f"Valid:            {valid_count}"
    )
    print(
        f"Invalid:          {invalid_count}"
    )
    print(
        f"Missing:          {missing_count}"
    )
    print(
        f"PDF:              {pdf_count}"
    )
    print(
        f"HTML:             {html_count}"
    )
    print(
        f"JSON:             {json_count}"
    )
    print(
        f"Unexpected files: {len(unexpected_files)}"
    )

    if unexpected_files:
        print()
        print(
            "Files present in data/raw "
            "but not referenced by the manifest:"
        )

        for file_name in unexpected_files:
            print(
                f"  - {file_name}"
            )

    print()

    if valid_count < MIN_DOCUMENTS:
        print(
            "ERROR: Fewer than 20 valid documents "
            "are available."
        )
        return 1

    if invalid_count > 0 or missing_count > 0:
        print(
            "ERROR: Corpus validation failed. "
            "Fix invalid or missing sources "
            "before ingestion."
        )
        return 2

    print(
        "Corpus validation PASSED."
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )