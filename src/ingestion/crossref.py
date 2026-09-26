from __future__ import annotations

from dataclasses import asdict, dataclass
from html import unescape
import json
from pathlib import Path
import re
import time

import requests

from core.config import Settings


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Convert a Crossref ``/works`` response into valid :class:`PaperRecord`s.

    Crossref returns several fields as optional arrays or nested objects.  This
    parser deliberately skips records without a DOI, title, or abstract: those
    records cannot be traced or embedded reliably later in the pipeline.
    """
    items = payload.get("message", {}).get("items", [])
    if not isinstance(items, list):
        raise ValueError("Crossref payload must contain message.items as a list.")

    def clean_text(value: object) -> str:
        text = unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def first_text(value: object) -> str:
        if isinstance(value, list):
            return clean_text(value[0]) if value else ""
        return clean_text(value)

    def date_from(value: object) -> str:
        if not isinstance(value, dict):
            return ""
        parts = value.get("date-parts", [])
        if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
            return ""
        numbers = parts[0]
        try:
            year = int(numbers[0])
            month = int(numbers[1]) if len(numbers) > 1 else 1
            day = int(numbers[2]) if len(numbers) > 2 else 1
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (TypeError, ValueError, IndexError):
            return ""

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = clean_text(item.get("DOI"))
        title = first_text(item.get("title"))
        summary = clean_text(item.get("abstract"))
        if not (paper_id and title and summary):
            continue

        authors: list[str] = []
        for author in item.get("author", []):
            if not isinstance(author, dict):
                continue
            name = clean_text(" ".join(
                part for part in (author.get("given"), author.get("family")) if part
            ))
            if name:
                authors.append(name)

        categories = [clean_text(subject) for subject in item.get("subject", [])]
        categories = [subject for subject in categories if subject]
        published = (
            date_from(item.get("published"))
            or date_from(item.get("published-print"))
            or date_from(item.get("published-online"))
            or date_from(item.get("issued"))
        )
        updated = clean_text(item.get("created", {}).get("date-time"))[:10]
        url = clean_text(item.get("URL")) or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated or published,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref data, or reliably fall back to the bundled raw snapshot.

    A normal lab run uses the snapshot, giving all team members the same 24
    records.  Set ``REFRESH_SOURCE=true`` to request Crossref.  Network errors,
    rate limiting, and malformed API responses then fall back to that snapshot.
    """
    raw_path = settings.paths.raw_api_response
    records_path = settings.paths.raw_records_json
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.parent.mkdir(parents=True, exist_ok=True)

    def read_snapshot() -> dict:
        if not raw_path.exists():
            raise RuntimeError(
                "Crossref request failed and no local snapshot exists at "
                f"{raw_path}."
            )
        with raw_path.open(encoding="utf-8") as file:
            snapshot = json.load(file)
        if not isinstance(snapshot, dict):
            raise ValueError("The local Crossref snapshot must be a JSON object.")
        return snapshot

    payload: dict
    if not settings.refresh_source:
        payload = read_snapshot()
    else:
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
            "select": "DOI,title,abstract,author,subject,published,published-print,published-online,issued,created,URL",
        }
        try:
            response = None
            for attempt in range(3):
                response = requests.get(
                    "https://api.crossref.org/works",
                    params=params,
                    headers={"User-Agent": "vinuni-data-observability-lab/1.0"},
                    timeout=20,
                )
                if response.status_code not in {429, 503}:
                    response.raise_for_status()
                    break
                if attempt < 2:
                    time.sleep(2**attempt)
            else:
                raise requests.HTTPError(
                    f"Crossref remained unavailable: HTTP {response.status_code if response else 'unknown'}"
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Crossref API did not return a JSON object.")
        except (requests.RequestException, ValueError, json.JSONDecodeError):
            payload = read_snapshot()

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError("Crossref payload did not contain any valid records.")

    # Persist the exact source response before storing its derived representation.
    with raw_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    with records_path.open("w", encoding="utf-8") as file:
        json.dump([asdict(record) for record in records], file, ensure_ascii=False, indent=2)
        file.write("\n")
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the derived raw-record artifact back into typed records."""
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"Raw records at {path} must be a JSON list.")
    try:
        return [PaperRecord(**item) for item in data if isinstance(item, dict)]
    except TypeError as exc:
        raise ValueError(f"Raw records at {path} do not match PaperRecord schema.") from exc
