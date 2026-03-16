"""
围绕 PRD 的关键回归测试。
"""

from pathlib import Path

from paperinsight.core.extractor import DataExtractor
from paperinsight.core.reporter import ReportGenerator
from paperinsight.ocr.base import BaseOCR
from paperinsight.utils.config import normalize_config
from paperinsight.utils.file_renamer import FileRenamer
from paperinsight.utils.pdf_utils import PDFProcessor, extract_text_with_fallback


class DummyOCR(BaseOCR):
    def extract_text_from_pdf(self, pdf_path, max_pages=None):
        return "ocr text", "ocr front", {}

    def extract_text_from_image(self, image_path):
        return "ocr image text"

    def is_available(self):
        return True


def test_normalize_flat_config_is_backward_compatible():
    config = normalize_config(
        {
            "use_paddlex": True,
            "paddlex_token": "paddlex-token",
            "use_llm": True,
            "llm_provider": "openai",
            "llm_api_key": "llm-key",
            "llm_model": "gpt-4o",
            "use_web_search": False,
        }
    )

    assert config["paddlex"]["enabled"] is True
    assert config["paddlex"]["token"] == "paddlex-token"
    assert config["llm"]["enabled"] is True
    assert config["llm"]["provider"] == "openai"
    assert config["llm"]["api_key"] == "llm-key"
    assert config["web_search"]["enabled"] is False


def test_reporter_maps_extractor_fields_to_report_columns(tmp_path):
    result = {
        "journal_name": "Nature Communications",
        "影响因子": 12.3,
        "authors": "Alice, Bob",
        "title": "Test Title",
        "device_structure": "ITO/HTL/EML",
        "experimental_params": {
            "eqe": ["20.50%"],
            "cie": ["(0.2100, 0.3200)"],
            "lifetime": ["150.0 h"],
        },
        "data_source": {
            "eqe_source": "max EQE of 20.5%.",
            "cie_source": "CIE coordinates were (0.21, 0.32).",
            "lifetime_source": "T50 was 150 h.",
        },
        "optimization": {
            "level": "材料合成",
            "strategy": "通过界面工程优化器件性能。",
        },
        "File": "paper.pdf",
        "URL": "file:///tmp/paper.pdf",
    }

    reporter = ReportGenerator(tmp_path)

    assert reporter._format_cell_value(result, "期刊名称") == "Nature Communications"
    assert reporter._format_cell_value(result, "作者") == "Alice, Bob"
    assert reporter._format_cell_value(result, "论文标题") == "Test Title"
    assert reporter._format_cell_value(result, "器件结构") == "ITO/HTL/EML"
    assert reporter._format_cell_value(result, "优化层级") == "材料合成"
    assert reporter._format_cell_value(result, "优化策略") == "通过界面工程优化器件性能。"
    assert reporter._sort_key_by_if(result) == 12.3


def test_extract_text_with_fallback_prefers_native_text(monkeypatch, tmp_path):
    pdf_path = tmp_path / "native.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nnative")

    def fake_extract_text(self, max_pages=None, min_text_ratio=0.01):
        return "native text", "native front", {"title": "Native"}

    monkeypatch.setattr(PDFProcessor, "extract_text", fake_extract_text)

    full_text, front_text, metadata = extract_text_with_fallback(pdf_path, ocr_engine=DummyOCR())

    assert full_text == "native text"
    assert front_text == "native front"
    assert metadata["_text_source"] == "native"


def test_extract_text_with_fallback_uses_ocr_for_garbled_native_text(monkeypatch, tmp_path):
    pdf_path = tmp_path / "garbled.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ngarbled")

    def fake_extract_text(self, max_pages=None, min_text_ratio=0.01):
        return "\ufffd" * 100, "", {"title": "Garbled"}

    monkeypatch.setattr(PDFProcessor, "extract_text", fake_extract_text)

    full_text, front_text, metadata = extract_text_with_fallback(pdf_path, ocr_engine=DummyOCR())

    assert full_text == "ocr text"
    assert front_text == "ocr front"
    assert metadata["_text_source"] == "ocr"


def test_regex_extractor_adds_impact_factor_and_data_source():
    text = (
        "Nature Communications Impact Factor 12.3. "
        "The device achieved a max EQE of 20.5%. "
        "The CIE coordinates were (0.21, 0.32). "
        "The T50 was 150 h."
    )

    result = DataExtractor(use_llm=False).extract(text, text, {})

    assert result["影响因子"] == 12.3
    assert "EQE" in result["data_source"]["eqe_source"]
    assert "CIE" in result["data_source"]["cie_source"]
    assert "T50" in result["data_source"]["lifetime_source"]


def test_file_renamer_uses_impact_factor_placeholder():
    renamer = FileRenamer()
    new_name = renamer.generate_new_name(
        "example.pdf",
        {
            "year": 2024,
            "影响因子": 12.3,
            "journal_name": "Nature Communications",
            "title": "High efficiency emitters",
        },
    )

    assert "IF12.3" in new_name
    assert new_name.endswith(".pdf")
