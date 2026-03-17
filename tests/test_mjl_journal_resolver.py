from __future__ import annotations

from collections import deque

import requests

from paperinsight.web.journal_resolver import MJLJournalResolver


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


class DummySession:
    def __init__(self, responses: list[dict]):
        self.responses = deque(DummyResponse(response) for response in responses)
        self.calls: list[tuple[str, dict]] = []
        self.headers: dict[str, str] = {}

    def post(self, url: str, json: dict, timeout: int):
        self.calls.append((url, json))
        if not self.responses:
            raise AssertionError("No more prepared responses")
        return self.responses.popleft()


def _build_candidate(
    *,
    seq_no: str,
    title: str,
    title_iso: str | None,
    issn: str | None,
    eissn: str | None,
    publisher: str = "Nature Portfolio",
    search_identifier: str = "search-id-1",
) -> dict:
    return {
        "searchIdentifier": search_identifier,
        "journalProfiles": [
            {
                "relevance": 10000.0,
                "journalProfile": {
                    "publicationSeqNo": seq_no,
                    "publicationTitle": title,
                    "publicationTitleISO": title_iso,
                    "issn": issn,
                    "eissn": eissn,
                    "publisherName": publisher,
                },
            }
        ]
    }


def test_mjl_search_payload_matches_observed_site_request_shape():
    resolver = MJLJournalResolver()

    payload = resolver._build_search_payload("1476-4687")

    assert payload["searchValue"] == "1476-4687"
    assert payload["pageNum"] == 1
    assert payload["pageSize"] == 10
    assert payload["sortOrder"] == [{"name": "RELEVANCE", "order": "DESC"}]
    assert payload["filters"][0] == {
        "filterName": "COVERED_LATEST_JEDI",
        "matchType": "BOOLEAN_EXACT",
        "caseSensitive": False,
        "values": [{"type": "VALUE", "value": "true"}],
    }
    assert payload["filters"][1]["filterName"] == "PRODUCT_CODE"
    assert [item["value"] for item in payload["filters"][1]["values"]] == ["D", "J", "SS", "H", "EX"]
    assert isinstance(payload["searchIdentifier"], str) and payload["searchIdentifier"]
    assert resolver.session.headers["Authorization"] == "Bearer"
    assert resolver.session.headers["x-1p-appid"] == "mjl"


def test_resolve_prefers_issn_match_and_uses_iso_title():
    session = DummySession(
        [
            _build_candidate(
                seq_no="70884J",
                title="NATURE",
                title_iso="Nature",
                issn="0028-0836",
                eissn="1476-4687",
            )
        ]
    )
    resolver = MJLJournalResolver(session=session)

    resolution = resolver.resolve(journal_title="Nature", eissn="1476-4687")

    assert resolution.status == "OK"
    assert resolution.match_method == "eissn"
    assert resolution.matched_journal_title == "Nature"
    assert resolution.matched_issn == "0028-0836"
    assert resolution.candidate is not None
    assert resolution.candidate.publication_seq_no == "70884J"
    assert resolution.candidate.search_identifier == "search-id-1"
    assert resolution.candidate.search_url.endswith("?issn=1476-4687")
    assert session.calls[0][0] == MJLJournalResolver.SEARCH_API_URL


def test_resolve_falls_back_to_title_when_issn_queries_do_not_match():
    session = DummySession(
        [
            {"journalProfiles": []},
            _build_candidate(
                seq_no="12345J",
                title="NATURE MATERIALS",
                title_iso="Nature Materials",
                issn="1476-1122",
                eissn="1476-4660",
            ),
        ]
    )
    resolver = MJLJournalResolver(session=session)

    resolution = resolver.resolve(journal_title="Nature Materials", issn="0000-0000")

    assert resolution.status == "OK"
    assert resolution.match_method == "exact_title"
    assert resolution.matched_journal_title == "Nature Materials"
    assert len(session.calls) == 2
    assert session.calls[1][1]["searchValue"] == "Nature Materials"


def test_resolve_marks_multi_match_for_ambiguous_titles():
    session = DummySession(
        [
            {
                "journalProfiles": [
                    {
                        "journalProfile": {
                            "publicationSeqNo": "1J",
                            "publicationTitle": "NATURE REVIEWS DRUG DISCOVERY",
                            "publicationTitleISO": "Nature Reviews Drug Discovery",
                            "issn": "1474-1776",
                            "eissn": "1474-1784",
                            "publisherName": "Nature Portfolio",
                        }
                    },
                    {
                        "journalProfile": {
                            "publicationSeqNo": "2J",
                            "publicationTitle": "NATURE REVIEWS DRUG DISCOVERY",
                            "publicationTitleISO": "Nature Reviews Drug Discovery",
                            "issn": "1474-1776",
                            "eissn": "1474-1784",
                            "publisherName": "Nature Portfolio",
                        }
                    },
                ]
            }
        ]
    )
    resolver = MJLJournalResolver(session=session)

    resolution = resolver.resolve(journal_title="Nature Reviews Drug Discovery")

    assert resolution.status == "MULTI_MATCH"
    assert resolution.match_method == "exact_title"
    assert len(resolution.candidates) == 2


def test_resolve_returns_no_match_when_all_strategies_fail():
    session = DummySession(
        [
            {"journalProfiles": []},
            {"journalProfiles": []},
        ]
    )
    resolver = MJLJournalResolver(session=session)

    resolution = resolver.resolve(journal_title="Unknown Journal", issn="1111-1111")

    assert resolution.status == "NO_MATCH"
    assert resolution.candidate is None
