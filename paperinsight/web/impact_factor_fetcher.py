from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from paperinsight.web.journal_resolver import MJLJournalCandidate


@dataclass(frozen=True)
class ImpactFactorLookupResult:
    status: str
    source_name: str
    source_url: str
    impact_factor: Optional[float] = None
    year: Optional[int] = None
    error_message: Optional[str] = None


class MJLImpactFactorFetcher:
    PROFILE_API_URL = "https://mjl.clarivate.com/api/mjl/jprof/restricted/seqno/{seqno}"
    JCR_DEEP_LINK_URL = "https://mjl.clarivate.com/api/censub/restricted/jcr-deep-link/{seqno}"

    def __init__(
        self,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        )
        self.session.headers.setdefault("Accept", "application/json, text/plain, */*")
        self.session.headers.setdefault("Referer", "https://mjl.clarivate.com/search-results")
        self.session.headers.setdefault("Authorization", "Bearer")
        self.session.headers.setdefault("x-1p-appid", "mjl")

    def lookup(self, candidate: MJLJournalCandidate) -> ImpactFactorLookupResult:
        profile_url = self._build_profile_api_url(candidate)
        response = self.session.get(profile_url, timeout=self.timeout)

        if response.status_code in {401, 403}:
            return ImpactFactorLookupResult(
                status="NO_ACCESS",
                source_name="MJL_PROFILE_API",
                source_url=profile_url,
                error_message="Profile endpoint requires an authenticated MJL session.",
            )
        if response.status_code == 404:
            return ImpactFactorLookupResult(
                status="NO_MATCH",
                source_name="MJL_PROFILE_API",
                source_url=profile_url,
            )
        if response.status_code >= 400:
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="MJL_PROFILE_API",
                source_url=profile_url,
                error_message=f"HTTP {response.status_code}",
            )

        data = response.json()
        parsed = self._extract_impact_factor(data)
        if parsed is not None:
            year, impact_factor = parsed
            return ImpactFactorLookupResult(
                status="OK",
                source_name="MJL_PROFILE_API",
                source_url=profile_url,
                impact_factor=impact_factor,
                year=year,
            )

        return ImpactFactorLookupResult(
            status="NOT_VISIBLE",
            source_name="MJL_PROFILE_API",
            source_url=profile_url,
        )

    def _build_profile_api_url(self, candidate: MJLJournalCandidate) -> str:
        base_url = self.PROFILE_API_URL.format(seqno=candidate.publication_seq_no)
        if not candidate.search_identifier:
            return base_url
        return f"{base_url}?{urlencode({'searchIdentifier': candidate.search_identifier})}"

    def _extract_impact_factor(self, payload: Any) -> Optional[tuple[Optional[int], float]]:
        matches = self._walk_for_impact_factor(payload)
        if not matches:
            return None
        matches.sort(key=lambda item: (item[0] or 0, item[1]), reverse=True)
        return matches[0]

    def _walk_for_impact_factor(self, payload: Any) -> list[tuple[Optional[int], float]]:
        matches: list[tuple[Optional[int], float]] = []
        if isinstance(payload, dict):
            matches.extend(self._extract_impact_factor_from_dict(payload))
            for value in payload.values():
                matches.extend(self._walk_for_impact_factor(value))
        elif isinstance(payload, list):
            for item in payload:
                matches.extend(self._walk_for_impact_factor(item))
        return matches

    def _extract_impact_factor_from_dict(self, item: dict[str, Any]) -> list[tuple[Optional[int], float]]:
        matches: list[tuple[Optional[int], float]] = []
        year = self._coerce_year(
            item.get("citationReportYear")
            or item.get("reportYear")
            or item.get("year")
            or item.get("jifYear")
        )

        for key, value in item.items():
            key_lower = key.lower()
            numeric_value = self._coerce_float(value)
            if numeric_value is None:
                continue
            if not 0.1 <= numeric_value <= 200:
                continue

            if key_lower in {"journalimpactfactor", "impactfactor", "jif", "jifvalue"}:
                matches.append((year, numeric_value))
                continue

            if key_lower.startswith("jif"):
                key_year = self._extract_year_from_key(key_lower)
                matches.append((key_year or year, numeric_value))
                continue

            if "impactfactor" in key_lower:
                key_year = self._extract_year_from_key(key_lower)
                matches.append((key_year or year, numeric_value))

        return matches

    @staticmethod
    def _extract_year_from_key(key: str) -> Optional[int]:
        match = re.search(r"(20\d{2})", key)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _coerce_year(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            year = int(str(value))
        except (TypeError, ValueError):
            return None
        return year if 2000 <= year <= 2100 else None

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if value in (None, ""):
            return None
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(value))
        if not match:
            return None
        return float(match.group(1))
