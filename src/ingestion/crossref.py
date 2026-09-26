from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import Settings
from core.utils import ensure_parent, normalize_whitespace, read_json, write_json


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


class _PlainText(HTMLParser):
    """Keep inline text intact and separate paragraph-like HTML/JATS elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.rsplit(":", 1)[-1] in {"p", "br", "div", "sec", "title", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        self.handle_starttag(tag, [])

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    parser = _PlainText()
    parser.feed(value)
    parser.close()
    return normalize_whitespace("".join(parser.parts))


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _date(value: object) -> str:
    """ISO date; missing month/day default to 1, missing/invalid dates to ''."""
    if not isinstance(value, dict):
        return ""
    parts = _list(value.get("date-parts"))
    if not parts or not isinstance(parts[0], list) or not 1 <= len(parts[0]) <= 3:
        return ""
    components = parts[0]
    if any(type(part) is not int for part in components):
        return ""
    try:
        return date(*(components + [1] * (3 - len(components)))).isoformat()
    except ValueError:
        return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Extract records without mutating the source; skip items missing DOI/title.

    Optional absent text/lists remain empty. Publication dates use published,
    published-online, published-print, then issued (never deposit/creation dates).
    """
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("items"), list):
        raise ValueError("Expected Crossref payload with message.items list.")

    records = []
    for item in message["items"]:
        if not isinstance(item, dict):
            continue
        doi = item.get("DOI")
        if not isinstance(doi, str):
            continue
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi.strip(), flags=re.I).lower()
        titles = item.get("title")
        titles = [titles] if isinstance(titles, str) else _list(titles)
        title = next((text for value in titles if (text := _text(value))), "")
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or not title:
            continue

        authors = []
        for author in _list(item.get("author")):
            if isinstance(author, dict):
                name = _text(author.get("name")) or normalize_whitespace(
                    f"{_text(author.get('given'))} {_text(author.get('family'))}"
                )
                if name:
                    authors.append(name)
        categories = list(dict.fromkeys(
            text for value in _list(item.get("subject")) if (text := _text(value))
        ))
        published = next((
            parsed for key in ("published", "published-online", "published-print", "issued")
            if (parsed := _date(item.get(key)))
        ), "")
        updated = _date(item.get("deposited")) or published
        pdf_url = next((
            link["URL"].strip() for link in _list(item.get("link"))
            if isinstance(link, dict) and link.get("content-type") == "application/pdf"
            and isinstance(link.get("URL"), str) and link["URL"].strip()
        ), "")
        records.append(PaperRecord(
            paper_id=doi,
            title=title,
            summary=_text(item.get("abstract")),
            authors=authors,
            categories=categories,
            primary_category=categories[0] if categories else "",
            published=published,
            updated=updated,
            abs_url=f"https://doi.org/{doi}",
            pdf_url=pdf_url,
            comment=f"Crossref record {doi}",
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch one public API response and save its exact JSON body plus records."""
    if not 1 <= settings.max_results <= 1000:
        raise ValueError("max_results must be between 1 and 1000 for a single response.")
    params: dict[str, str | int] = {"rows": settings.max_results}
    if settings.source_query:
        params["query"] = settings.source_query
    if settings.source_filter:
        params["filter"] = settings.source_filter

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        response = session.get(
            "https://api.crossref.org/works",
            params=params,
            headers={"Accept": "application/json", "User-Agent": "DataObservabilityLab/0.1"},
            timeout=(10, 60),
        )
        response.raise_for_status()
        records = parse_crossref_payload(response.json())
        # Do not reserialize: retain whitespace, escaping, and all source fields.
        ensure_parent(settings.paths.raw_api_response)
        settings.paths.raw_api_response.write_bytes(response.content)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Reload the extracted snapshot for offline pipeline runs."""
    return [PaperRecord(**record) for record in read_json(path)]
