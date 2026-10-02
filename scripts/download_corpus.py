import csv
import json
import sys
import time
from pathlib import Path

import requests


MANIFEST_PATH = Path("data/sources_manifest.csv")
RAW_DIR = Path("data/raw")

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MIN_FILE_SIZE_BYTES = 500


def is_probably_pdf(content: bytes, content_type: str) -> bool:
    return (
        content.startswith(b"%PDF")
        or "application/pdf" in content_type.lower()
    )


def is_probably_html(content: bytes, content_type: str) -> bool:
    sample = content[:1000].lower()

    return (
        "text/html" in content_type.lower()
        or b"<html" in sample
        or b"<!doctype html" in sample
    )


def is_probably_json(content: bytes) -> bool:
    try:
        json.loads(content.decode("utf-8"))
        return True
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False


def download_with_retries(url: str) -> requests.Response:
    headers = {

    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            last_error = exc

            if attempt < MAX_RETRIES:
                wait_seconds = attempt * 2

                print(
                    f"    Retry {attempt}/{MAX_RETRIES - 1} "
                    f"after error: {exc}"
                )

                time.sleep(wait_seconds)

    raise RuntimeError(
        f"Download failed after {MAX_RETRIES} attempts: "
        f"{last_error}"
    )


def validate_download(
    response: requests.Response,
    expected_type: str,
) -> tuple[bool, str]:
    content = response.content

    if len(content) < MIN_FILE_SIZE_BYTES:
        return (
            False,
            f"File too small ({len(content)} bytes)",
        )

    content_type = response.headers.get(
        "Content-Type",
        "",
    )

    if expected_type == "PDF":
        if not is_probably_pdf(
            content,
            content_type,
        ):
            return (
                False,
                (
                    "Expected PDF but received "
                    f"Content-Type={content_type!r}"
                ),
            )

    elif expected_type == "HTML":
        if not is_probably_html(
            content,
            content_type,
        ):
            return (
                False,
                (
                    "Expected HTML but received "
                    f"Content-Type={content_type!r}"
                ),
            )

    elif expected_type == "JSON":
        if not is_probably_json(content):
            return (
                False,
                "Expected JSON but received invalid JSON content",
            )

    else:
        return (
            False,
            f"Unsupported document_type: {expected_type}",
        )

    return True, "OK"


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(
            f"ERROR: Manifest not found: "
            f"{MANIFEST_PATH}"
        )
        return 1

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with MANIFEST_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    print(
        f"Loaded {len(rows)} sources "
        f"from manifest."
    )
    print()

    success_count = 0
    failure_count = 0

    for index, row in enumerate(
        rows,
        start=1,
    ):
        source_id = row[
            "source_id"
        ].strip()

        url = row[
            "download_url"
        ].strip()

        file_name = row[
            "file_name"
        ].strip()

        document_type = row[
            "document_type"
        ].strip().upper()

        destination = RAW_DIR / file_name

        print(
            f"[{index}/{len(rows)}] "
            f"{source_id} -> {file_name}"
        )

        try:
            # Resume support:
            # If the file already exists and is valid,
            # do not download it again.
            if destination.exists():
                existing_content = destination.read_bytes()

                if document_type == "PDF":
                    existing_valid = is_probably_pdf(
                        existing_content,
                        "application/pdf",
                    )

                elif document_type == "HTML":
                    existing_valid = is_probably_html(
                        existing_content,
                        "text/html",
                    )

                elif document_type == "JSON":
                    existing_valid = is_probably_json(
                        existing_content,
                    )

                else:
                    existing_valid = False

                if (
                    existing_valid
                    and len(existing_content)
                    >= MIN_FILE_SIZE_BYTES
                ):
                    size_kb = (
                        len(existing_content) / 1024
                    )

                    print(
                        "    SKIPPED: already "
                        "downloaded and valid "
                        f"({size_kb:.1f} KB)"
                    )

                    success_count += 1
                    continue

                print(
                    "    Existing file is invalid. "
                    "Re-downloading..."
                )

            response = download_with_retries(
                url
            )

            valid, message = validate_download(
                response,
                document_type,
            )

            if not valid:
                raise RuntimeError(
                    message
                )

            destination.write_bytes(
                response.content
            )

            size_kb = (
                len(response.content)
                / 1024
            )

            print(
                f"    SUCCESS "
                f"({size_kb:.1f} KB)"
            )

            success_count += 1

        except Exception as exc:
            print(
                f"    FAILED: {exc}"
            )

            failure_count += 1

    print()
    print("Download summary")
    print("----------------")
    print(
        f"Successful: {success_count}"
    )
    print(
        f"Failed:     {failure_count}"
    )
    print(
        f"Total:      {len(rows)}"
    )

    if success_count < 20:
        print()
        print(
            "ERROR: Fewer than 20 sources "
            "were downloaded successfully."
        )

        return 1

    if failure_count > 0:
        print()
        print(
            "WARNING: Some sources failed. "
            "Review failures before continuing."
        )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )