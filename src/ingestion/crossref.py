from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

logger = logging.getLogger(__name__)


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
    """Parse Crossref payload thanh list PaperRecord.

    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        paper_id = str(item.get("DOI", "")).strip()
        if not paper_id:
            continue

        raw_title = item.get("title", "")
        if isinstance(raw_title, list):
            raw_title = raw_title[0] if raw_title else ""
        title = normalize_whitespace(re.sub(r"<[^>]+>", " ", str(raw_title)))
        if not title:
            continue

        raw_abstract = str(item.get("abstract", ""))
        summary = normalize_whitespace(re.sub(r"<[^>]+>", " ", raw_abstract))
        if not summary:
            continue

        authors: list[str] = []
        for author in item.get("author", []):
            if isinstance(author, dict):
                given = str(author.get("given", "")).strip()
                family = str(author.get("family", "")).strip()
                name = normalize_whitespace(f"{given} {family}".strip() or str(author.get("name", "")).strip())
                if name:
                    authors.append(name)
            elif isinstance(author, str):
                name = normalize_whitespace(author)
                if name:
                    authors.append(name)

        categories: list[str] = []
        for subj in item.get("subject", []):
            cat = normalize_whitespace(str(subj))
            if cat:
                categories.append(cat)

        primary_category = categories[0] if categories else "Unknown"

        date_parts = item.get("published", {}).get("date-parts", [[None]])[0]
        if len(date_parts) >= 3 and all(p is not None for p in date_parts[:3]):
            published = f"{int(date_parts[0]):04d}-{int(date_parts[1]):02d}-{int(date_parts[2]):02d}"
        elif len(date_parts) >= 1 and date_parts[0] is not None:
            published = f"{int(date_parts[0]):04d}-01-01"
        else:
            published = "1970-01-01"

        updated = published
        url = str(item.get("URL", f"https://doi.org/{paper_id}")).strip()
        abs_url = url
        pdf_url = url
        comment = f"Crossref record {paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records.

    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    payload: dict[str, Any] | None = None

    if not settings.refresh_source and settings.paths.raw_api_response.exists():
        try:
            payload = read_json(settings.paths.raw_api_response)
        except Exception as exc:
            logger.warning("Failed to read cached raw response: %s", exc)

    if payload is None:
        url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }
        headers = {
            "User-Agent": "DataPipelineObservabilityLab/1.0 (mailto:student@vinuni.edu.vn)"
        }
        max_retries = 3
        backoff_seconds = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=15)
                if response.status_code in {429, 503}:
                    logger.warning(
                        "Rate limit or service unavailable (%d) on attempt %d/%d, retrying...",
                        response.status_code,
                        attempt,
                        max_retries,
                    )
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                response.raise_for_status()
                payload = response.json()
                write_json(settings.paths.raw_api_response, payload)
                break
            except Exception as exc:
                logger.warning(
                    "Attempt %d/%d failed to fetch from Crossref API: %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                else:
                    if settings.paths.raw_api_response.exists():
                        logger.info("Falling back to local raw response snapshot.")
                        payload = read_json(settings.paths.raw_api_response)
                    else:
                        raise RuntimeError(
                            f"Failed to fetch Crossref data and no local snapshot found: {exc}"
                        ) from exc

    if payload is None:
        if settings.paths.raw_api_response.exists():
            payload = read_json(settings.paths.raw_api_response)
        else:
            raise RuntimeError("No raw payload available.")

    records = parse_crossref_payload(payload)

    raw_dicts = [asdict(r) for r in records]
    write_json(settings.paths.raw_records_json, raw_dicts)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    data = read_json(path)
    return [PaperRecord(**item) for item in data]
