import json
from pathlib import Path

import openpyxl
from typer.testing import CliRunner

from paperinsight.agentflow.pipeline import AgentPreparePipeline
from paperinsight.cli import app
from paperinsight.models.schemas import PaperData, PaperInfo
from paperinsight.parser.base import ParseResult


runner = CliRunner()


class FakeMinerUParser:
    def is_available(self):
        return True

    def parse(self, file_path: Path) -> ParseResult:
        markdown = (
            "# High Efficiency Blue OLEDs\n\n"
            "DOI: 10.1000/xyz123\n\n"
            "Published in 2025.\n"
        )
        return ParseResult(
            markdown=markdown,
            raw_text=markdown,
            success=True,
            parser_name="fake-mineru",
            metadata={"title": "High Efficiency Blue OLEDs", "year": 2025},
        )


def test_agent_prepare_pipeline_writes_run_dir_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(AgentPreparePipeline, "_init_parser", lambda self: FakeMinerUParser())

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    pdf_path = pdf_dir / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nsample")

    pipeline = AgentPreparePipeline(
        output_dir=tmp_path / "agent_runs",
        config={"mineru": {"enabled": True}, "cache": {"enabled": False}},
    )
    stats = pipeline.prepare(pdf_dir)

    run_dir = Path(stats["run_dir"])
    manifest_path = Path(stats["manifest_path"])
    jobs_path = Path(stats["identity_jobs_path"])
    results_path = Path(stats["identity_results_path"])
    prompt_path = Path(stats["identity_prompt_path"])

    assert stats["status"] == "completed"
    assert stats["success_count"] == 1
    assert run_dir.exists()
    assert manifest_path.exists()
    assert jobs_path.exists()
    assert results_path.exists()
    assert prompt_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper = manifest["papers"][0]
    assert paper["status"] == "prepared"
    assert paper["title_hint"] == "High Efficiency Blue OLEDs"
    assert paper["doi_hint"] == "10.1000/xyz123"

    job = json.loads(Path(paper["identity_job_path"]).read_text(encoding="utf-8"))
    assert job["query"]["paper_identifier"] == "10.1000/xyz123"
    assert job["query"]["title"] == "High Efficiency Blue OLEDs"
    assert Path(paper["markdown_path"]).read_text(encoding="utf-8").startswith("# High Efficiency Blue OLEDs")

    lines = jobs_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    packed_job = json.loads(lines[0])
    assert packed_job["paper_key"] == paper["paper_key"]


def test_agent_prepare_cli_prints_run_paths(monkeypatch, tmp_path):
    class DummyPreparePipeline:
        def __init__(self, output_dir, config=None, cache_dir=".cache"):
            self.output_dir = output_dir

        def prepare(self, pdf_dir, **kwargs):
            run_dir = Path(self.output_dir) / "run_20260319_120000"
            return {
                "status": "completed",
                "pdf_count": 1,
                "success_count": 1,
                "error_count": 0,
                "run_dir": str(run_dir),
                "manifest_path": str(run_dir / "manifest.json"),
                "identity_jobs_path": str(run_dir / "jobs" / "identity_jobs.jsonl"),
                "identity_results_path": str(run_dir / "jobs" / "identity_results.jsonl"),
                "identity_prompt_path": str(run_dir / "jobs" / "identity_prompt.md"),
            }

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "sample.pdf").write_bytes(b"%PDF-1.4\nsample")

    monkeypatch.setattr("paperinsight.cli.load_config", lambda: {"mineru": {"enabled": True}, "cache": {"enabled": False}})
    monkeypatch.setattr("paperinsight.cli.AgentPreparePipeline", DummyPreparePipeline)

    result = runner.invoke(app, ["agent", "prepare", str(pdf_dir)])

    assert result.exit_code == 0
    assert "Agent Prepare Complete" in result.stdout
    assert "Identity jobs:" in result.stdout
    assert "identity_results.jsonl" in result.stdout


def test_agent_import_identity_writes_paper_data_and_updates_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(AgentPreparePipeline, "_init_parser", lambda self: FakeMinerUParser())

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "sample.pdf").write_bytes(b"%PDF-1.4\nsample")

    pipeline = AgentPreparePipeline(
        output_dir=tmp_path / "agent_runs",
        config={"mineru": {"enabled": True}, "cache": {"enabled": False}},
    )
    prepare_stats = pipeline.prepare(pdf_dir)
    results_path = Path(prepare_stats["identity_results_path"])
    manifest_path = Path(prepare_stats["manifest_path"])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper_key = manifest["papers"][0]["paper_key"]
    results_path.write_text(
        json.dumps(
            {
                "paper_key": paper_key,
                "matched": True,
                "paper_identifier": "10.1000/xyz123",
                "matched_title": "High Efficiency Blue OLEDs",
                "journal_name": "Advanced Functional Materials",
                "impact_factor": 19.0,
                "impact_factor_year": 2025,
                "impact_factor_source": "IDE_WEB_SEARCH",
                "impact_factor_status": "OK",
                "evidence_urls": ["https://example.test/paper", "https://example.test/journal"],
                "notes": "matched by DOI",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    import_stats = pipeline.import_identity_results(prepare_stats["run_dir"])

    assert import_stats["imported_count"] == 1
    assert import_stats["invalid_count"] == 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper = manifest["papers"][0]
    assert paper["status"] == "identity_imported"
    assert paper["journal_name"] == "Advanced Functional Materials"
    assert paper["impact_factor"] == 19.0
    assert paper["impact_factor_year"] == 2025
    assert paper["impact_factor_status"] == "OK"

    identity_result = json.loads(Path(paper["identity_result_path"]).read_text(encoding="utf-8"))
    assert identity_result["paper_key"] == paper_key

    paper_data = json.loads(Path(paper["paper_data_path"]).read_text(encoding="utf-8"))
    assert paper_data["paper_info"]["title"] == "High Efficiency Blue OLEDs"
    assert paper_data["paper_info"]["journal_name"] == "Advanced Functional Materials"
    assert paper_data["paper_info"]["impact_factor"] == 19.0
    assert paper_data["paper_info"]["impact_factor_year"] == 2025
    assert paper_data["paper_info"]["impact_factor_source"] == "IDE_WEB_SEARCH"
    assert identity_result["evidence_urls"] == [
        "https://example.test/paper",
        "https://example.test/journal",
    ]


def test_agent_import_identity_cli_prints_summary(monkeypatch, tmp_path):
    class DummyPreparePipeline:
        def __init__(self, output_dir, config=None, cache_dir=".cache"):
            self.output_dir = output_dir

        def import_identity_results(self, run_dir, results_path=None):
            return {
                "status": "completed",
                "run_dir": str(run_dir),
                "manifest_path": str(Path(run_dir) / "manifest.json"),
                "summary_path": str(Path(run_dir) / "jobs" / "identity_import_summary.json"),
                "imported_count": 3,
                "invalid_count": 1,
                "unmatched_count": 1,
            }

    run_dir = tmp_path / "agent_runs" / "run_20260319_120000"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr("paperinsight.cli.load_config", lambda: {"cache": {"enabled": False}})
    monkeypatch.setattr("paperinsight.cli.AgentPreparePipeline", DummyPreparePipeline)

    result = runner.invoke(app, ["agent", "import-identity", str(run_dir)])

    assert result.exit_code == 0
    assert "Identity Import Complete" in result.stdout
    assert "Imported:" in result.stdout
    assert "identity_import_summary.json" in result.stdout


def test_agent_extract_metrics_merges_identity_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(AgentPreparePipeline, "_init_parser", lambda self: FakeMinerUParser())

    class FakeExtractor:
        def __init__(self, config=None):
            self.config = config or {}

        def extract(self, markdown_text, cleaned_text, parse_result=None):
            paper_data = PaperData(
                paper_info=PaperInfo(
                    title="LLM Title",
                    authors="Alice, Bob",
                    year=2024,
                    journal_name="Wrong Journal",
                    impact_factor=1.2,
                    impact_factor_year=2024,
                    impact_factor_source="LLM",
                    impact_factor_status="OK",
                    best_eqe="21.0%",
                )
            )
            return type(
                "ExtractionResultStub",
                (),
                {
                    "success": True,
                    "data": paper_data,
                    "error_message": None,
                    "processing_time": 0.5,
                    "extraction_method": "llm",
                    "llm_model": "LongCat-Flash-Chat",
                },
            )()

    monkeypatch.setattr("paperinsight.agentflow.pipeline.DataExtractor", FakeExtractor)

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "sample.pdf").write_bytes(b"%PDF-1.4\nsample")

    pipeline = AgentPreparePipeline(
        output_dir=tmp_path / "agent_runs",
        config={
            "mineru": {"enabled": True},
            "cache": {"enabled": False},
            "llm": {"enabled": True, "provider": "longcat"},
            "cleaner": {"enabled": True},
            "output": {"bilingual_text": False},
        },
    )
    prepare_stats = pipeline.prepare(pdf_dir)
    results_path = Path(prepare_stats["identity_results_path"])
    manifest_path = Path(prepare_stats["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper_key = manifest["papers"][0]["paper_key"]

    results_path.write_text(
        json.dumps(
            {
                "paper_key": paper_key,
                "matched": True,
                "paper_identifier": "10.1000/xyz123",
                "matched_title": "Matched Paper Title",
                "journal_name": "Advanced Functional Materials",
                "impact_factor": 19.0,
                "impact_factor_year": 2025,
                "impact_factor_source": "IDE_WEB_SEARCH",
                "impact_factor_status": "OK",
                "evidence_urls": ["https://example.test/paper"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    pipeline.import_identity_results(prepare_stats["run_dir"])

    stats = pipeline.extract_metrics(prepare_stats["run_dir"])
    assert stats["processed_count"] == 1
    assert stats["failed_count"] == 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper = manifest["papers"][0]
    assert paper["status"] == "metrics_extracted"
    assert paper["journal_name"] == "Advanced Functional Materials"
    assert paper["impact_factor"] == 19.0
    assert paper["impact_factor_year"] == 2025
    assert paper["best_eqe"] == "21.0%"

    metrics_payload = json.loads(Path(paper["metrics_result_path"]).read_text(encoding="utf-8"))
    assert metrics_payload["paper_info"]["title"] == "Matched Paper Title"
    assert metrics_payload["paper_info"]["authors"] == "Alice, Bob"
    assert metrics_payload["paper_info"]["journal_name"] == "Advanced Functional Materials"
    assert metrics_payload["paper_info"]["impact_factor"] == 19.0
    assert metrics_payload["paper_info"]["impact_factor_source"] == "IDE_WEB_SEARCH"


def test_agent_extract_metrics_cli_prints_summary(monkeypatch, tmp_path):
    class DummyPreparePipeline:
        def __init__(self, output_dir, config=None, cache_dir=".cache"):
            self.output_dir = output_dir

        def extract_metrics(self, run_dir, force=False):
            return {
                "status": "completed",
                "run_dir": str(run_dir),
                "manifest_path": str(Path(run_dir) / "manifest.json"),
                "summary_path": str(Path(run_dir) / "jobs" / "metrics_summary.json"),
                "processed_count": 2,
                "failed_count": 1,
                "skipped_count": 0,
            }

    run_dir = tmp_path / "agent_runs" / "run_20260319_120000"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "paperinsight.cli.load_config",
        lambda: {"cache": {"enabled": False}, "llm": {"enabled": True}, "cleaner": {}, "output": {}},
    )
    monkeypatch.setattr("paperinsight.cli.AgentPreparePipeline", DummyPreparePipeline)

    result = runner.invoke(app, ["agent", "extract-metrics", str(run_dir)])

    assert result.exit_code == 0
    assert "Metrics Extraction Complete" in result.stdout
    assert "Processed:" in result.stdout
    assert "metrics_summary.json" in result.stdout


def test_agent_finalize_writes_excel_and_updates_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(AgentPreparePipeline, "_init_parser", lambda self: FakeMinerUParser())

    class FakeExtractor:
        def __init__(self, config=None):
            self.config = config or {}

        def extract(self, markdown_text, cleaned_text, parse_result=None):
            paper_data = PaperData(
                paper_info=PaperInfo(
                    title="LLM Title",
                    authors="Alice, Bob",
                    year=2024,
                    best_eqe="21.0%",
                )
            )
            return type(
                "ExtractionResultStub",
                (),
                {
                    "success": True,
                    "data": paper_data,
                    "error_message": None,
                    "processing_time": 0.5,
                    "extraction_method": "llm",
                    "llm_model": "LongCat-Flash-Chat",
                },
            )()

    monkeypatch.setattr("paperinsight.agentflow.pipeline.DataExtractor", FakeExtractor)

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "sample.pdf").write_bytes(b"%PDF-1.4\nsample")

    pipeline = AgentPreparePipeline(
        output_dir=tmp_path / "agent_runs",
        config={
            "mineru": {"enabled": True},
            "cache": {"enabled": False},
            "llm": {"enabled": True, "provider": "longcat"},
            "cleaner": {"enabled": True},
            "output": {"bilingual_text": False, "sort_by_if": True},
        },
    )
    prepare_stats = pipeline.prepare(pdf_dir)
    manifest_path = Path(prepare_stats["manifest_path"])
    results_path = Path(prepare_stats["identity_results_path"])
    paper_key = json.loads(manifest_path.read_text(encoding="utf-8"))["papers"][0]["paper_key"]
    results_path.write_text(
        json.dumps(
            {
                "paper_key": paper_key,
                "matched": True,
                "paper_identifier": "10.1000/xyz123",
                "matched_title": "Matched Paper Title",
                "journal_name": "Advanced Functional Materials",
                "impact_factor": 19.0,
                "impact_factor_year": 2025,
                "impact_factor_source": "IDE_WEB_SEARCH",
                "impact_factor_status": "OK",
                "evidence_urls": ["https://example.test/paper"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    pipeline.import_identity_results(prepare_stats["run_dir"])
    pipeline.extract_metrics(prepare_stats["run_dir"])

    finalize_stats = pipeline.finalize(prepare_stats["run_dir"], export_json=True)

    excel_path = Path(finalize_stats["report_files"]["excel"])
    json_path = Path(finalize_stats["report_files"]["json"])
    assert excel_path.exists()
    assert json_path.exists()

    workbook = openpyxl.load_workbook(excel_path)
    sheet = workbook.active
    assert sheet["A2"].value == "sample.pdf"
    assert sheet["C2"].value == "Advanced Functional Materials"
    assert sheet["D2"].value == 19.0
    assert sheet["E2"].value == "Alice, Bob"
    assert sheet["G2"].value == "Matched Paper Title"
    assert sheet["L2"].value == "21.0%"

    exported_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported_json[0]["paper_info"]["impact_factor_year"] == 2025
    assert exported_json[0]["paper_info"]["impact_factor_source"] == "IDE_WEB_SEARCH"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paper = manifest["papers"][0]
    assert paper["status"] == "finalized"
    assert Path(paper["final_paper_data_path"]).exists()
    assert manifest["finalize"]["report_files"]["excel"] == str(excel_path)


def test_agent_finalize_cli_prints_report_paths(monkeypatch, tmp_path):
    class DummyPreparePipeline:
        def __init__(self, output_dir, config=None, cache_dir=".cache"):
            self.output_dir = output_dir

        def finalize(self, run_dir, output_dir=None, sort_by_if=True, export_json=False):
            report_dir = Path(output_dir) if output_dir else Path(run_dir) / "reports"
            return {
                "status": "completed",
                "manifest_path": str(Path(run_dir) / "manifest.json"),
                "summary_path": str(Path(run_dir) / "jobs" / "finalize_summary.json"),
                "finalized_count": 2,
                "incomplete_count": 0,
                "report_files": {
                    "excel": str(report_dir / "论文分析报告_20260319_120000.xlsx"),
                },
            }

    run_dir = tmp_path / "agent_runs" / "run_20260319_120000"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr("paperinsight.cli.load_config", lambda: {"cache": {"enabled": False}, "output": {"sort_by_if": True}})
    monkeypatch.setattr("paperinsight.cli.AgentPreparePipeline", DummyPreparePipeline)

    result = runner.invoke(app, ["agent", "finalize", str(run_dir)])

    assert result.exit_code == 0
    assert "Agent Finalize Complete" in result.stdout
    assert "Excel report:" in result.stdout
    assert ".xlsx" in result.stdout
