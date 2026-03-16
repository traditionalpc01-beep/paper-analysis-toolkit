from pathlib import Path

from typer.testing import CliRunner

from paperinsight.cleaner.section_filter import clean_paper_content
from paperinsight.cli import app
from paperinsight.core.extractor import DataExtractor
from paperinsight.core.pipeline import AnalysisPipeline
from paperinsight.models.schemas import PaperData, PaperInfo
from paperinsight.web.impact_factor_search import ImpactFactorSearcher


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


def test_impact_factor_searcher_parses_latest_available_history_value():
    html = """
    <title>Nature Communications - SCI Journal</title>
    <div style=width:60%>2024 Impact Factor</div><div style=display:inline-flex;width:40%><span>#N/A</span></div>
    <div style=width:60%>2023 Impact Factor</div><div style=display:inline-flex;width:40%><span>16.6</span></div>
    <div style=width:60%>2022 Impact Factor</div><div style=display:inline-flex;width:40%><span>15.7</span></div>
    """

    searcher = ImpactFactorSearcher()
    parsed = searcher._parse_scijournal_impact_factor(html)

    assert parsed == (2023, 16.6)


def test_pipeline_can_correct_existing_impact_factor_when_web_result_differs(tmp_path):
    pipeline = AnalysisPipeline(
        output_dir=tmp_path,
        config={
            "cache": {"enabled": False},
            "mineru": {"enabled": False},
            "llm": {"enabled": False},
            "web_search": {"enabled": True, "correct_existing_impact_factor": True},
        },
    )

    class DummySearcher:
        def lookup_impact_factor(self, journal_name, use_cache=True):
            from paperinsight.web.impact_factor_search import ImpactFactorMatch

            return ImpactFactorMatch(
                journal_name=journal_name,
                impact_factor=18.9,
                source_url="https://example.com",
                source_name="test",
                year=2023,
                similarity=0.99,
            )

    pipeline.if_searcher = DummySearcher()
    paper_data = PaperData(paper_info=PaperInfo(journal_name="Nature Communications", impact_factor=1.0))

    pipeline._supplement_impact_factor(paper_data)

    assert paper_data.paper_info.impact_factor == 18.9


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
