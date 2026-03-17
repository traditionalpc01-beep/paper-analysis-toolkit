from paperinsight.utils.journal_metadata import (
    build_journal_match_keys,
    canonicalize_journal_title,
    normalize_issn,
)


def test_normalize_issn_accepts_compact_and_hyphenated_values():
    assert normalize_issn("14764660") == "1476-4660"
    assert normalize_issn("1476-4660") == "1476-4660"
    assert normalize_issn("2041-172X") == "2041-172X"


def test_normalize_issn_rejects_malformed_values():
    assert normalize_issn("1476-466") is None
    assert normalize_issn("abcd-efgh") is None
    assert normalize_issn(None) is None


def test_canonicalize_journal_title_normalizes_spacing_punctuation_and_and():
    assert canonicalize_journal_title("Research & Development Letters") == (
        canonicalize_journal_title("Research and Development Letters")
    )
    assert canonicalize_journal_title("Nature-Materials") == "nature materials"
    assert canonicalize_journal_title("  Nature   Materials  ") == "nature materials"


def test_build_journal_match_keys_returns_explicit_priority_order():
    match_keys = build_journal_match_keys(
        journal_title="Nature Materials",
        issn="1476-1122",
        eissn="1476-4660",
    )

    assert match_keys.prioritized_items() == [
        ("issn", "1476-1122"),
        ("eissn", "1476-4660"),
        ("exact_title", "Nature Materials"),
        ("canonical_title", "nature materials"),
    ]
