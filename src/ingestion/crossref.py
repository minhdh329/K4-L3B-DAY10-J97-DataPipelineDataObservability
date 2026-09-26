from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import html
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
    """TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        paper_id = _as_text(item.get("DOI"))
        title = _first_text(item.get("title"))
        summary = _clean_text(item.get("abstract"))
        if not paper_id or not title or not summary:
            continue

        authors = []
        for author in item.get("author", []):
            if not isinstance(author, dict):
                continue
            name = " ".join(
                part for part in (author.get("given"), author.get("family")) if _as_text(part)
            )
            if name:
                authors.append(name)

        categories = [
            _as_text(category)
            for category in item.get("subject", [])
            if _as_text(category)
        ]
        published = _date_from_item(item.get("published"))
        updated = _date_from_item(item.get("created")) or published
        abs_url = _as_text(item.get("URL")) or f"https://doi.org/{paper_id}"
        pdf_url = _pdf_url(item) or abs_url

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=_as_text(item.get("comment")) or f"Crossref record {paper_id}",
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    response = None
    for attempt in range(3):
        try:
            response = requests.get(
                "https://api.crossref.org/works",
                params=params,
                headers={"User-Agent": "data-observability-lab/1.0"},
                timeout=30,
            )
            if response.status_code not in {429, 503}:
                response.raise_for_status()
                break
        except requests.RequestException:
            if attempt == 2:
                break
        if attempt < 2:
            time.sleep(2**attempt)

    if response is None or response.status_code in {429, 503}:
        if settings.paths.raw_api_response.exists():
            return load_raw_records(settings.paths.raw_records_json)
        if response is not None:
            response.raise_for_status()
        raise RuntimeError("Crossref API request failed and no raw snapshot is available.")

    response.raise_for_status()
    payload = response.json()
    settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_api_response.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    records = parse_crossref_payload(payload)
    settings.paths.raw_records_json.write_text(
        json.dumps([record.__dict__ for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """TODO(student): doc JSON snapshot va map thanh `PaperRecord`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [PaperRecord(**record) for record in data if isinstance(record, dict)]


def _as_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _first_text(value: object) -> str:
    if isinstance(value, list):
        return _as_text(value[0]) if value else ""
    return _as_text(value)


def _clean_text(value: object) -> str:
    text = html.unescape(_as_text(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _date_from_item(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        numbers = parts[0]
        try:
            year = int(numbers[0])
            month = int(numbers[1]) if len(numbers) > 1 else 1
            day = int(numbers[2]) if len(numbers) > 2 else 1
            return datetime(year, month, day).date().isoformat()
        except (TypeError, ValueError):
            pass
    date_time = _as_text(value.get("date-time"))
    return date_time[:10] if date_time else ""


def _pdf_url(item: dict) -> str:
    for link in item.get("link", []):
        if isinstance(link, dict) and "pdf" in _as_text(link.get("content-type")).lower():
            return _as_text(link.get("URL"))
    return ""
