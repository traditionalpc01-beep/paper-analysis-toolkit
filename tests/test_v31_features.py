from pathlib import Path

from typer.testing import CliRunner

from paperinsight.cleaner.section_filter import clean_paper_content
from paperinsight.cli import app
from paperinsight.core.extractor import DataExtractor
from paperinsight.core.pipeline import AnalysisPipeline
from paperinsight.models.schemas import PaperData, PaperInfo
from paperinsight.parser.base import ParseResult


runner = CliRunner()


def test_v31_cleaner_keeps_hits_neighbors_and_anchored_tables():
    markdown = """# Abstract

The device achieved a maximum EQE of 20.5%.

# Results and Discussion

The champion device uses ITO/PEDOT:PSS/EML/TPBi/LiF/Al.

| Device | EQE |
| --- | --- |
| A | 20.5% |

Figure 1 The device shows stable emission.

# References

1. prior work with EQE 10%.
"""

    cleaned = clean_paper_content(
        markdown,
        {
            "enabled": True,
            "block_window": 1,
            "max_input_chars": 8000,
            "max_blocks": 20,
            "min_block_score": 3.0,
        },
    )

    extraction_text = cleaned.get_text_for_extraction()
    assert "## Anchored Tables" in extraction_text
    assert "[TABLE_0001]" in extraction_text
    assert "maximum EQE of 20.5%" in extraction_text
    assert "ITO/PEDOT:PSS/EML/TPBi/LiF/Al" in extraction_text
    assert "prior work with EQE 10%." not in extraction_text


def test_extractor_prefers_subject_journal_hint_over_science_keyword():
    extractor = DataExtractor(config={"llm": {"enabled": False}})
    parse_result = ParseResult(
        success=True,
        markdown="",
        metadata={"subject": "Advanced Materials 2024.36:2404480"},
    )

    raw_journal_title, raw_issn, raw_eissn = extractor._extract_raw_journal_metadata(
        "University of Science and Technology of China",
        parse_result,
    )

    assert raw_journal_title == "Advanced Materials"
    assert raw_issn is None
    assert raw_eissn is None


def test_extractor_uses_domain_hint_and_avoids_university_of_science_false_match():
    extractor = DataExtractor(config={"llm": {"enabled": False}})
    text = """
    Small www.small-journal.com RESEARCH ARTICLE
    Overcoming Exciton Quenching at the ZnMgO/InP Quantum Dot Interface for Stable LEDs
    Department of Applied Chemistry, University of Science and Technology of China
    """

    assert extractor._extract_journal_name(text) == "Small"


def test_extractor_maps_subject_abbreviations_without_falling_back_to_small_keyword():
    extractor = DataExtractor(config={"llm": {"enabled": False}})
    parse_result = ParseResult(
        success=True,
        markdown="",
        metadata={"subject": "Chem. Mater. 2023.35:822-836"},
    )

    raw_journal_title, _, _ = extractor._extract_raw_journal_metadata(
        "InP quantum dots have a small bandgap and high covalency.",
        parse_result,
    )

    assert raw_journal_title == "Chemistry of Materials"


def test_extractor_maps_jacs_subject_abbreviation():
    extractor = DataExtractor(config={"llm": {"enabled": False}})
    parse_result = ParseResult(
        success=True,
        markdown="",
        metadata={"subject": "J. Am. Chem. Soc. 2026.148:3501-3512"},
    )

    raw_journal_title, _, _ = extractor._extract_raw_journal_metadata(
        "Colloidal quantum dots were studied in solution.",
        parse_result,
    )

    assert raw_journal_title == "Journal of the American Chemical Society"


def test_pipeline_can_correct_existing_impact_factor_when_web_result_differs(tmp_path):
    pipeline = AnalysisPipeline(
        output_dir=tmp_path,
        config={
            "cache": {"enabled": False},
            "mineru": {"enabled": False},
            "llm": {"enabled": False},
            "web_search": {
                "enabled": True,
                "resolve_journal_metadata": True,
                "fetch_official_impact_factor": True,
                "correct_existing_impact_factor": True,
            },
        },
    )

    class DummyResolver:
        SEARCH_RESULTS_URL = "https://mjl.clarivate.com/search-results"

        def resolve(self, journal_title=None, issn=None, eissn=None):
            from paperinsight.web.journal_resolver import MJLJournalCandidate, MJLJournalResolution

            return MJLJournalResolution(
                status="OK",
                match_method="exact_title",
                search_value=journal_title,
                candidate=MJLJournalCandidate(
                    publication_seq_no="12345J",
                    publication_title="NATURE COMMUNICATIONS",
                    publication_title_iso="Nature Communications",
                    issn="2041-1723",
                    eissn="2041-1723",
                    publisher_name="Nature Portfolio",
                    search_identifier="search-id-1",
                    search_url="https://mjl.clarivate.com/search-results?issn=2041-1723",
                    profile_url="https://mjl.clarivate.com/journal-profile",
                ),
            )

    class DummyFetcher:
        def lookup(self, candidate):
            from paperinsight.web.impact_factor_fetcher import ImpactFactorLookupResult

            return ImpactFactorLookupResult(
                status="OK",
                source_name="MJL_PROFILE_API",
                source_url="https://mjl.clarivate.com/api/mjl/jprof/restricted/seqno/12345J?searchIdentifier=search-id-1",
                impact_factor=18.9,
                year=2023,
            )

    pipeline.journal_resolver = DummyResolver()
    pipeline.if_fetcher = DummyFetcher()
    paper_data = PaperData(
        paper_info=PaperInfo(
            journal_name="Nature Communications",
            raw_journal_title="Nature Communications",
            impact_factor=1.0,
        )
    )

    resolution = pipeline._resolve_journal_metadata(paper_data)
    pipeline._supplement_impact_factor(paper_data, resolution)

    assert paper_data.paper_info.journal_name == "Nature Communications"
    assert paper_data.paper_info.matched_journal_title == "Nature Communications"
    assert paper_data.paper_info.matched_issn == "2041-1723"
    assert paper_data.paper_info.match_method == "exact_title"
    assert paper_data.paper_info.impact_factor == 18.9
    assert paper_data.paper_info.impact_factor_year == 2023
    assert paper_data.paper_info.impact_factor_source == "MJL_PROFILE_API"
    assert paper_data.paper_info.impact_factor_status == "OK"


def test_pipeline_marks_no_access_when_official_if_requires_login(tmp_path):
    pipeline = AnalysisPipeline(
        output_dir=tmp_path,
        config={
            "cache": {"enabled": False},
            "mineru": {"enabled": False},
            "llm": {"enabled": False},
            "web_search": {
                "enabled": True,
                "resolve_journal_metadata": True,
                "fetch_official_impact_factor": True,
                "correct_existing_impact_factor": True,
            },
        },
    )

    class DummyResolver:
        SEARCH_RESULTS_URL = "https://mjl.clarivate.com/search-results"

        def resolve(self, journal_title=None, issn=None, eissn=None):
            from paperinsight.web.journal_resolver import MJLJournalCandidate, MJLJournalResolution

            return MJLJournalResolution(
                status="OK",
                match_method="issn",
                search_value=issn,
                candidate=MJLJournalCandidate(
                    publication_seq_no="70884J",
                    publication_title="NATURE",
                    publication_title_iso="Nature",
                    issn="0028-0836",
                    eissn="1476-4687",
                    publisher_name="Nature Portfolio",
                    search_identifier="search-id-1",
                    search_url="https://mjl.clarivate.com/search-results?issn=1476-4687",
                    profile_url="https://mjl.clarivate.com/journal-profile",
                ),
            )

    class DummyFetcher:
        def lookup(self, candidate):
            from paperinsight.web.impact_factor_fetcher import ImpactFactorLookupResult

            return ImpactFactorLookupResult(
                status="NO_ACCESS",
                source_name="MJL_PROFILE_API",
                source_url="https://mjl.clarivate.com/api/mjl/jprof/restricted/seqno/70884J?searchIdentifier=search-id-1",
            )

    pipeline.journal_resolver = DummyResolver()
    pipeline.if_fetcher = DummyFetcher()
    paper_data = PaperData(
        paper_info=PaperInfo(
            journal_name="Nature",
            raw_journal_title="Nature",
            raw_eissn="1476-4687",
        )
    )

    resolution = pipeline._resolve_journal_metadata(paper_data)
    pipeline._supplement_impact_factor(paper_data, resolution)

    assert paper_data.paper_info.matched_journal_title == "Nature"
    assert paper_data.paper_info.impact_factor is None
    assert paper_data.paper_info.impact_factor_source == "MJL_PROFILE_API"
    assert paper_data.paper_info.impact_factor_status == "NO_ACCESS"


def test_pipeline_can_fetch_if_status_with_issn_only_metadata(tmp_path):
    pipeline = AnalysisPipeline(
        output_dir=tmp_path,
        config={
            "cache": {"enabled": False},
            "mineru": {"enabled": False},
            "llm": {"enabled": False},
            "web_search": {
                "enabled": True,
                "resolve_journal_metadata": True,
                "fetch_official_impact_factor": True,
                "correct_existing_impact_factor": True,
            },
        },
    )

    class DummyResolver:
        SEARCH_RESULTS_URL = "https://mjl.clarivate.com/search-results"

        def resolve(self, journal_title=None, issn=None, eissn=None):
            from paperinsight.web.journal_resolver import MJLJournalCandidate, MJLJournalResolution

            return MJLJournalResolution(
                status="OK",
                match_method="issn",
                search_value=issn,
                candidate=MJLJournalCandidate(
                    publication_seq_no="C6855J",
                    publication_title="MATERIALS TODAY",
                    publication_title_iso="Mater. Today",
                    issn="1369-7021",
                    eissn="1873-4103",
                    publisher_name="Elsevier",
                    search_identifier="search-id-1",
                    search_url="https://mjl.clarivate.com/search-results?issn=1369-7021",
                    profile_url="https://mjl.clarivate.com/journal-profile",
                ),
            )

    class DummyFetcher:
        def lookup(self, candidate):
            from paperinsight.web.impact_factor_fetcher import ImpactFactorLookupResult

            return ImpactFactorLookupResult(
                status="NO_ACCESS",
                source_name="MJL_PROFILE_API",
                source_url="https://mjl.clarivate.com/api/mjl/jprof/restricted/seqno/C6855J?searchIdentifier=search-id-1",
            )

    pipeline.journal_resolver = DummyResolver()
    pipeline.if_fetcher = DummyFetcher()
    paper_data = PaperData(
        paper_info=PaperInfo(
            raw_issn="1369-7021",
        )
    )

    resolution = pipeline._resolve_journal_metadata(paper_data)
    pipeline._supplement_impact_factor(paper_data, resolution)

    assert paper_data.paper_info.journal_name == "Mater. Today"
    assert paper_data.paper_info.match_method == "issn"
    assert paper_data.paper_info.impact_factor_source == "MJL_PROFILE_API"
    assert paper_data.paper_info.impact_factor_status == "NO_ACCESS"


def test_cli_prompts_for_bilingual_choice_each_run(monkeypatch, tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "paper.pdf").write_bytes(b"%PDF-1.4\n")

    captured = {}

    monkeypatch.setattr("paperinsight.cli.load_config", lambda: {
        "llm": {"enabled": True, "provider": "openai", "api_key": "test", "openai": {"model": "gpt-4o"}},
        "mineru": {"enabled": False},
        "paddlex": {"enabled": False},
        "web_search": {"enabled": False},
        "cache": {"enabled": False, "directory": ".cache"},
        "output": {"format": ["excel"], "sort_by_if": True, "bilingual_text": False, "rename_pdfs": False},
        "pdf": {"max_pages": 0},
        "cleaner": {"enabled": True},
    })
    monkeypatch.setattr("paperinsight.cli._get_pdf_directory", lambda path: Path(path))
    monkeypatch.setattr("paperinsight.cli._collect_pdf_files", lambda path, recursive: [path / "paper.pdf"])
    monkeypatch.setattr("paperinsight.cli._select_mode", lambda config, mode_arg=None: "api")

    answers = iter([True, True])
    monkeypatch.setattr("paperinsight.cli.Confirm.ask", lambda *args, **kwargs: next(answers))

    class DummyPipeline:
        def __init__(self, output_dir, config, cache_dir):
            captured["config"] = config

        def run(self, **kwargs):
            return {
                "status": "completed",
                "pdf_count": 1,
                "success_count": 1,
                "error_count": 0,
                "report_files": {},
            }

    monkeypatch.setattr("paperinsight.cli.AnalysisPipeline", DummyPipeline)

    result = runner.invoke(app, ["analyze", str(pdf_dir), "--skip-checks", "--mode", "api"])

    assert result.exit_code == 0
    assert captured["config"]["output"]["bilingual_text"] is True


def test_extractor_only_uses_strict_schema_for_openai(monkeypatch):
    captured = {}

    class DummyLLM:
        def is_available(self):
            return True

        def generate_json(self, prompt, max_tokens=None, temperature=0.3, **kwargs):
            captured["kwargs"] = kwargs
            return {"paper_info": {}, "devices": [], "data_source": {}, "optimization": {}}

    monkeypatch.setattr("paperinsight.core.extractor.create_llm_client", lambda config: DummyLLM())

    extractor = DataExtractor(
        config={
            "llm": {"enabled": True, "provider": "longcat", "api_key": "demo"},
            "output": {"bilingual_text": False},
        }
    )
    result = extractor.extract(markdown_text="text", cleaned_text="text")

    assert result.success is True
    assert "json_schema" not in captured["kwargs"]
    assert "schema_name" not in captured["kwargs"]


def test_regex_device_inference_can_extract_multiple_devices():
    text = """
    Device A used the structure ITO/PEDOT:PSS/QDs/ZnO/Al and achieved an EQE of 12.5%.

    The champion device used ITO/PEDOT:PSS/QDs/ZnMgO/Al with a maximum EQE of 18.9% and CIE (0.63, 0.36).

    Control device showed LT50 = 120 h.
    """

    extractor = DataExtractor(use_llm=False)
    result = extractor.extract(markdown_text=text, cleaned_text=text)

    assert result.success is True
    assert len(result.data.devices) >= 2
    assert any(device.eqe == "18.90%" for device in result.data.devices if device.eqe)
    assert result.data.paper_info.best_eqe == "18.90%"


def test_regex_extractor_uses_parse_metadata_for_raw_journal_fields():
    text = "This paper studies emissive materials."
    parse_result = ParseResult(
        markdown=text,
        raw_text=text,
        metadata={
            "journal": "Nature Materials",
            "issn": "1476-1122",
            "eissn": "1476-4660",
        },
    )

    extractor = DataExtractor(use_llm=False)
    result = extractor.extract(markdown_text=text, cleaned_text=text, parse_result=parse_result)

    assert result.success is True
    assert result.data.paper_info.journal_name == "Nature Materials"
    assert result.data.paper_info.raw_journal_title == "Nature Materials"
    assert result.data.paper_info.raw_issn == "1476-1122"
    assert result.data.paper_info.raw_eissn == "1476-4660"


def test_regex_extractor_falls_back_to_front_matter_issn_patterns():
    text = """
    Nature Communications
    Print ISSN 2041-1723
    Online ISSN 2041-1723

    The device achieved an EQE of 22.5%.
    """

    extractor = DataExtractor(use_llm=False)
    result = extractor.extract(markdown_text=text, cleaned_text=text)

    assert result.success is True
    assert result.data.paper_info.journal_name == "Nature Communications"
    assert result.data.paper_info.raw_journal_title == "Nature Communications"
    assert result.data.paper_info.raw_issn == "2041-1723"
    assert result.data.paper_info.raw_eissn == "2041-1723"
