#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = [
#   "pypdf==6.15.0",
# ]
# ///
"""Download and extract the official rule sources used by this project.

Generated PDFs and text are working copies. They are written outside the
repository by default and must not be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError


MANIFEST_PATH = Path(__file__).with_name("official-rule-sources.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    Path(tempfile.gettempdir()) / "dune-imperium-official-rules"
)
USER_AGENT = "Dune-Imperium-rules-research/1.0"
SOURCE_FIELDS = {
    "label",
    "url",
    "sha256",
    "pdf_filename",
    "text_filename",
}


class RulePreparationError(RuntimeError):
    """An expected source, validation, or output error."""


@dataclass(frozen=True, slots=True)
class OfficialSource:
    """One pinned official rule source."""

    slug: str
    label: str
    url: str
    sha256: str
    pdf_filename: str
    text_filename: str


def parse_source(slug: Any, value: Any) -> OfficialSource:
    """Validate and construct one manifest entry."""
    if not isinstance(slug, str) or not isinstance(value, dict):
        raise RulePreparationError("invalid source manifest entry")

    missing = SOURCE_FIELDS - value.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise RulePreparationError(f"source {slug!r} is missing: {names}")
    if set(value) != SOURCE_FIELDS:
        extras = ", ".join(sorted(set(value) - SOURCE_FIELDS))
        raise RulePreparationError(
            f"source {slug!r} has unsupported fields: {extras}"
        )

    invalid_fields = [
        field
        for field in sorted(SOURCE_FIELDS)
        if not isinstance(value[field], str) or not value[field]
    ]
    if invalid_fields:
        names = ", ".join(invalid_fields)
        raise RulePreparationError(
            f"source {slug!r} has invalid string fields: {names}"
        )

    source = OfficialSource(slug=slug, **value)
    hexadecimal = set("0123456789abcdef")
    if len(source.sha256) != 64 or not set(source.sha256) <= hexadecimal:
        raise RulePreparationError(
            f"source {slug!r} has an invalid SHA-256 value"
        )
    if not source.url.startswith("https://"):
        raise RulePreparationError(
            f"source {slug!r} must use an HTTPS official URL"
        )
    if Path(source.pdf_filename).name != source.pdf_filename:
        raise RulePreparationError(
            f"source {slug!r} has an invalid PDF filename"
        )
    if Path(source.text_filename).name != source.text_filename:
        raise RulePreparationError(
            f"source {slug!r} has an invalid text filename"
        )
    return source


def load_sources(path: Path = MANIFEST_PATH) -> dict[str, OfficialSource]:
    """Load and validate the machine-readable official source manifest."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RulePreparationError(
            f"cannot read source manifest {path}: {error}"
        ) from error

    if not isinstance(raw, dict) or not raw:
        raise RulePreparationError(
            "source manifest must be a non-empty object"
        )

    sources: dict[str, OfficialSource] = {}
    for slug, value in raw.items():
        source = parse_source(slug, value)
        sources[slug] = source

    pdf_filenames = {source.pdf_filename for source in sources.values()}
    text_filenames = {source.text_filename for source in sources.values()}
    if len(pdf_filenames) != len(sources):
        raise RulePreparationError(
            "source manifest has duplicate PDF filenames"
        )
    if len(text_filenames) != len(sources):
        raise RulePreparationError(
            "source manifest has duplicate text filenames"
        )
    return sources


def sha256_bytes(data: bytes) -> str:
    """Return the lower-case SHA-256 digest for data."""
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    """Replace a generated file atomically after all bytes are available."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def validate_pdf(
    source: OfficialSource,
    data: bytes,
    *,
    allow_hash_mismatch: bool,
) -> str:
    """Validate a PDF signature and its pinned digest."""
    if not data.startswith(b"%PDF-"):
        raise RulePreparationError(
            f"{source.slug}: downloaded content is not a PDF"
        )

    actual_hash = sha256_bytes(data)
    if actual_hash != source.sha256:
        message = (
            f"{source.slug}: SHA-256 changed\n"
            f"  expected: {source.sha256}\n"
            f"  actual:   {actual_hash}"
        )
        if not allow_hash_mismatch:
            raise RulePreparationError(
                f"{message}\n"
                "Recheck the official resource page, then rerun with "
                "--allow-hash-mismatch only for deliberate inspection."
            )
        print(f"warning: {message}", file=sys.stderr)
    return actual_hash


def download(source: OfficialSource) -> bytes:
    """Download one official source without writing a partial file."""
    request = urllib.request.Request(
        source.url,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as error:
        raise RulePreparationError(
            f"{source.slug}: download failed: {error}"
        ) from error


def obtain_pdf(
    source: OfficialSource,
    output_dir: Path,
    *,
    offline: bool,
    refresh: bool,
    allow_hash_mismatch: bool,
) -> tuple[Path, str]:
    """Reuse a valid cached PDF or download and validate a fresh copy."""
    pdf_path = output_dir / source.pdf_filename

    if pdf_path.exists() and not refresh:
        try:
            cached_data = pdf_path.read_bytes()
            actual_hash = validate_pdf(
                source,
                cached_data,
                allow_hash_mismatch=allow_hash_mismatch,
            )
        except RulePreparationError:
            if offline:
                raise
        else:
            return pdf_path, actual_hash

    if offline:
        raise RulePreparationError(
            f"{source.slug}: no valid cached PDF at {pdf_path}"
        )

    downloaded_data = download(source)
    actual_hash = validate_pdf(
        source,
        downloaded_data,
        allow_hash_mismatch=allow_hash_mismatch,
    )
    try:
        atomic_write(pdf_path, downloaded_data)
    except OSError as error:
        raise RulePreparationError(
            f"{source.slug}: cannot write {pdf_path}: {error}"
        ) from error
    return pdf_path, actual_hash


def extract_text(
    source: OfficialSource,
    pdf_path: Path,
    actual_hash: str,
    output_dir: Path,
) -> tuple[Path, int]:
    """Extract page-indexed text and add provenance outside the PDF text."""
    try:
        reader = PdfReader(pdf_path)
        page_sections = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").rstrip()
            page_sections.append(
                f"=== PDF PAGE {page_number} ===\n\n{text}\n"
            )
    except (OSError, PdfReadError) as error:
        raise RulePreparationError(
            f"{source.slug}: text extraction failed: {error}"
        ) from error

    header = (
        "GENERATED WORKING COPY - DO NOT COMMIT\n"
        f"Official source: {source.url}\n"
        f"SHA-256: {actual_hash}\n\n"
    )
    text_path = output_dir / source.text_filename
    encoded = (header + "\n".join(page_sections)).encode("utf-8")
    try:
        atomic_write(text_path, encoded)
    except OSError as error:
        raise RulePreparationError(
            f"{source.slug}: cannot write {text_path}: {error}"
        ) from error
    return text_path, len(reader.pages)


def ensure_external_output_dir(output_dir: Path) -> Path:
    """Prevent generated copyrighted working copies entering the repository."""
    resolved = output_dir.expanduser().resolve()
    if resolved == REPOSITORY_ROOT or REPOSITORY_ROOT in resolved.parents:
        raise RulePreparationError(
            "--output-dir must be outside the repository; use /tmp or another "
            "working directory"
        )
    return resolved


def build_parser(
    sources: dict[str, OfficialSource],
) -> argparse.ArgumentParser:
    """Build the command-line interface after manifest validation."""
    parser = argparse.ArgumentParser(
        description=(
            "Download pinned official Uprising rule PDFs and extract "
            "page-indexed text outside the repository."
        )
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=tuple(sources),
        dest="selected_sources",
        help="prepare one source; repeat for multiple sources (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "working directory outside the repository "
            f"(default: {DEFAULT_OUTPUT_DIR})"
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use only valid PDFs already present in the output directory",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="redownload selected PDFs even if valid cached files exist",
    )
    parser.add_argument(
        "--allow-hash-mismatch",
        action="store_true",
        help="inspect a changed official file after an explicit warning",
    )
    return parser


def run(arguments: list[str] | None = None) -> int:
    """Run the command and return a process exit status."""
    sources = load_sources()
    parser = build_parser(sources)
    options = parser.parse_args(arguments)
    if options.offline and options.refresh:
        parser.error("--offline and --refresh cannot be used together")

    try:
        output_dir = ensure_external_output_dir(options.output_dir)
        requested = options.selected_sources or list(sources)
        selected = [sources[slug] for slug in dict.fromkeys(requested)]

        for source in selected:
            pdf_path, actual_hash = obtain_pdf(
                source,
                output_dir,
                offline=options.offline,
                refresh=options.refresh,
                allow_hash_mismatch=options.allow_hash_mismatch,
            )
            text_path, page_count = extract_text(
                source,
                pdf_path,
                actual_hash,
                output_dir,
            )
            print(
                f"{source.slug}: {page_count} pages, {actual_hash}\n"
                f"  PDF:  {pdf_path}\n"
                f"  text: {text_path}"
            )
    except RulePreparationError as error:
        parser.exit(1, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
