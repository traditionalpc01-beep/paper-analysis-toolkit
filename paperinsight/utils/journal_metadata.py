from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


ISSN_BODY_PATTERN = re.compile(r"^\d{7}[\dX]$")


@dataclass(frozen=True)
class JournalMatchKeys:
    issn: Optional[str]
    eissn: Optional[str]
    exact_title: Optional[str]
    canonical_title: Optional[str]

    def prioritized_items(self) -> list[tuple[str, str]]:
        ordered_keys = [
            ("issn", self.issn),
            ("eissn", self.eissn),
            ("exact_title", self.exact_title),
            ("canonical_title", self.canonical_title),
        ]
        return [(key, value) for key, value in ordered_keys if value]


def normalize_issn(value: object) -> Optional[str]:
    if value in (None, ""):
        return None

    compact = re.sub(r"[^0-9Xx]", "", str(value)).upper()
    if not ISSN_BODY_PATTERN.fullmatch(compact):
        return None
    return f"{compact[:4]}-{compact[4:]}"


def normalize_exact_journal_title(title: object) -> Optional[str]:
    if title in (None, ""):
        return None

    normalized = re.sub(r"\s+", " ", str(title)).strip()
    return normalized or None


def canonicalize_journal_title(title: object) -> Optional[str]:
    exact_title = normalize_exact_journal_title(title)
    if not exact_title:
        return None

    canonical = exact_title.replace("&", " and ")
    canonical = re.sub(r"[^0-9A-Za-z]+", " ", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip().lower()
    return canonical or None


def build_journal_match_keys(
    journal_title: object,
    issn: object = None,
    eissn: object = None,
) -> JournalMatchKeys:
    return JournalMatchKeys(
        issn=normalize_issn(issn),
        eissn=normalize_issn(eissn),
        exact_title=normalize_exact_journal_title(journal_title),
        canonical_title=canonicalize_journal_title(journal_title),
    )
