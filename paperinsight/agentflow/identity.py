from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from paperinsight.models.schemas import PaperData


DOI_PATTERN = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(20\d{2}|19\d{2})\b")
TITLE_STOP_PATTERNS = (
    re.compile(r"^(abstract|keywords?|introduction|results?( and discussion)?|references)\b", re.IGNORECASE),
    re.compile(r"^(received|accepted|published|available online|copyright)\b", re.IGNORECASE),
    re.compile(r"^(doi|https?://|www\.)\b", re.IGNORECASE),
    )


class IdentityResultRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    paper_key: str
    matched: bool
    paper_identifier: Optional[str] = None
    matched_title: Optional[str] = None
    journal_name: Optional[str] = None
    impact_factor: Optional[float] = None
    impact_factor_year: Optional[int] = None
    impact_factor_source: Optional[str] = None
    impact_factor_status: str = Field(default="ERROR")
    evidence_urls: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("impact_factor")
    @classmethod
    def _validate_impact_factor(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if not 0.0 <= float(value) <= 200.0:
            raise ValueError("impact_factor must be between 0 and 200")
        return float(value)

    @field_validator("impact_factor_year")
    @classmethod
    def _validate_impact_factor_year(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if not 1900 <= int(value) <= 2100:
            raise ValueError("impact_factor_year must be between 1900 and 2100")
        return int(value)

    @field_validator("impact_factor_status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        normalized = (value or "ERROR").strip().upper()
        if normalized not in {"OK", "NO_MATCH", "NO_ACCESS", "ERROR"}:
            raise ValueError("impact_factor_status must be one of OK, NO_MATCH, NO_ACCESS, ERROR")
        return normalized


def extract_identity_hints(
    markdown: str,
    metadata: Optional[dict[str, Any]],
    source_pdf: Path,
) -> dict[str, Any]:
    metadata = metadata or {}
    doi = _extract_doi(markdown) or _extract_doi_from_metadata(metadata)
    title = _extract_title(markdown, metadata) or source_pdf.stem
    year = _extract_year(markdown, metadata)

    return {
        "paper_identifier": doi or title,
        "doi": doi,
        "title": title,
        "year": year,
        "source_filename": source_pdf.name,
    }


def build_identity_job(
    *,
    paper_key: str,
    source_pdf: Path,
    markdown_path: Path,
    identity_hints: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "paper_key": paper_key,
        "source_pdf": str(source_pdf.resolve()),
        "markdown_path": str(markdown_path.resolve()),
        "query": identity_hints,
        "instructions": {
            "goal": "Match the exact paper and return the latest available journal impact factor.",
            "rules": [
                "Prefer DOI for exact matching. If DOI is missing, use title and year together.",
                "Return the matched journal name for the paper itself, not only the publisher page.",
                "Return the latest available impact factor and its actual report year.",
                "Do not assume the latest year from the current calendar year.",
                "Keep evidence URLs for the matched paper and the impact-factor source.",
            ],
            "response_schema": {
                "paper_key": "string",
                "matched": "boolean",
                "paper_identifier": "string|null",
                "matched_title": "string|null",
                "journal_name": "string|null",
                "impact_factor": "number|null",
                "impact_factor_year": "integer|null",
                "impact_factor_source": "string|null",
                "impact_factor_status": "OK|NO_MATCH|NO_ACCESS|ERROR",
                "evidence_urls": ["string"],
                "notes": "string|null",
            },
        },
    }


def build_paper_data_payload(
    *,
    identity_job: dict[str, Any],
    identity_result: IdentityResultRecord,
) -> dict[str, Any]:
    query = identity_job.get("query", {})
    title = identity_result.matched_title or query.get("title")
    year = _coerce_year(query.get("year"))
    journal_name = identity_result.journal_name or None
    evidence_urls = [url for url in identity_result.evidence_urls if url]

    paper_data = PaperData()
    paper_info = paper_data.paper_info
    paper_info.title = title
    paper_info.year = year
    paper_info.journal_name = journal_name
    paper_info.raw_journal_title = journal_name
    paper_info.matched_journal_title = journal_name
    paper_info.match_method = "agent_identity" if journal_name else None
    paper_info.journal_profile_url = evidence_urls[0] if evidence_urls else None
    paper_info.impact_factor = identity_result.impact_factor
    paper_info.impact_factor_year = identity_result.impact_factor_year
    paper_info.impact_factor_source = identity_result.impact_factor_source
    paper_info.impact_factor_status = identity_result.impact_factor_status

    return paper_data.model_dump()


def _extract_doi(text: str) -> Optional[str]:
    match = DOI_PATTERN.search(text or "")
    if not match:
        return None
    return match.group(1).rstrip(").,;")


def _extract_doi_from_metadata(metadata: dict[str, Any]) -> Optional[str]:
    for key in ("doi", "dc:identifier", "identifier"):
        value = metadata.get(key)
        if not value:
            continue
        doi = _extract_doi(str(value))
        if doi:
            return doi
    return None


def _extract_title(markdown: str, metadata: dict[str, Any]) -> Optional[str]:
    for key in ("title", "dc:title"):
        value = metadata.get(key)
        normalized = _normalize_title_candidate(value)
        if normalized:
            return normalized

    lines = markdown.splitlines()[:40]
    normalized_lines = [_normalize_title_candidate(line) for line in lines]
    normalized_lines = [line for line in normalized_lines if line]

    block_candidates: list[str] = []
    current: list[str] = []
    for line in normalized_lines[:8]:
        if _is_bad_title_candidate(line):
            if current:
                break
            continue
        current.append(line)
        joined = " ".join(current).strip()
        if 20 <= len(joined) <= 280:
            block_candidates.append(joined)
        if len(current) >= 3:
            break

    for candidate in block_candidates + normalized_lines:
        if not _is_bad_title_candidate(candidate):
            return candidate
    return None


def _extract_year(markdown: str, metadata: dict[str, Any]) -> Optional[int]:
    for key in ("year", "publication_year", "citationReportYear"):
        value = metadata.get(key)
        year = _coerce_year(value)
        if year:
            return year

    for key in ("subject", "keywords"):
        value = metadata.get(key)
        if not value:
            continue
        match = YEAR_PATTERN.search(str(value))
        if match:
            return _coerce_year(match.group(1))

    match = YEAR_PATTERN.search(markdown[:4000])
    if not match:
        return None
    return _coerce_year(match.group(1))


def _normalize_title_candidate(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None

    text = str(value).strip()
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" -|")
    return text or None


def _is_bad_title_candidate(value: str) -> bool:
    lowered = value.lower()
    if len(value) < 20 or len(value) > 280:
        return True
    if DOI_PATTERN.search(value):
        return True
    if value.count("/") > 4:
        return True
    if sum(ch.isalpha() for ch in value) < 8:
        return True
    if lowered == lowered.upper() and sum(ch.islower() for ch in value) == 0 and len(value.split()) <= 2:
        return True
    return any(pattern.search(value) for pattern in TITLE_STOP_PATTERNS)


def _coerce_year(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        year = int(str(value))
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None
