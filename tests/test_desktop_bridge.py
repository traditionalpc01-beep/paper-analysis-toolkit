from pathlib import Path

from paperinsight.desktop_bridge import _build_runtime_config, _build_stats, _collect_pdf_files
from paperinsight.models.schemas import DeviceData, PaperData, PaperInfo
from paperinsight.utils.config import DEFAULT_CONFIG, normalize_config


def test_build_runtime_config_regex_disables_online_features():
    config = normalize_config(DEFAULT_CONFIG)
    runtime_config, selected_mode = _build_runtime_config(
        config,
        {
            "mode": "regex",
            "exportJson": True,
            "renamePdfs": True,
            "bilingual": True,
            "pdfDir": "/tmp/input",
            "outputDir": "/tmp/output",
        },
    )

    assert selected_mode == "regex"
    assert runtime_config["llm"]["enabled"] is False
    assert runtime_config["paddlex"]["enabled"] is False
    assert "json" in runtime_config["output"]["format"]
    assert runtime_config["output"]["rename_pdfs"] is True
    assert runtime_config["output"]["bilingual_text"] is True
    assert runtime_config["desktop"]["ui"]["last_pdf_dir"] == "/tmp/input"
    assert runtime_config["desktop"]["ui"]["last_output_dir"] == "/tmp/output"


def test_collect_pdf_files_respects_recursive_flag(tmp_path: Path):
    root_pdf = tmp_path / "root.pdf"
    nested_dir = tmp_path / "nested"
    nested_pdf = nested_dir / "child.pdf"
    nested_dir.mkdir()
    root_pdf.write_text("root")
    nested_pdf.write_text("child")

    direct = _collect_pdf_files(tmp_path, recursive=False)
    recursive = _collect_pdf_files(tmp_path, recursive=True)

    assert direct == [root_pdf]
    assert set(recursive) == {root_pdf, nested_pdf}


def test_normalize_config_keeps_desktop_defaults():
    config = normalize_config({})

    assert config["desktop"]["engine"]["mode"] == "bundled"
    assert config["desktop"]["ui"]["remember_last_paths"] is True
    assert config["desktop"]["ui"]["onboarding_completed"] is False


def test_build_stats_includes_success_and_error_items(tmp_path: Path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("dummy")

    paper = PaperData(
        paper_info=PaperInfo(title="Test Paper", journal_name="Nature", impact_factor=12.3),
        devices=[DeviceData(device_label="A", eqe="22.5%", structure="ITO/PVK/EML")],
    )

    stats = _build_stats(
        pdf_files=[pdf_path],
        results=[paper],
        errors=[{"pdf_name": "bad.pdf", "pdf_path": str(tmp_path / "bad.pdf"), "error_message": "解析失败", "context": "PDF解析", "error_type": "ParseFailed"}],
        report_files={"excel": str(tmp_path / "report.xlsx")},
        renamed_count=1,
        processed_items=[(pdf_path, paper)],
    )

    assert stats["successItems"][0]["file"] == "paper.pdf"
    assert stats["successItems"][0]["journal"] == "Nature"
    assert stats["successItems"][0]["bestEqe"] == "22.5%"
    assert stats["errorItems"][0]["file"] == "bad.pdf"
    assert stats["reportFiles"]["excel"].endswith("report.xlsx")
