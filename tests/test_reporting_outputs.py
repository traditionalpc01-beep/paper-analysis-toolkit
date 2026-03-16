import openpyxl

from paperinsight.core.reporter import ReportGenerator


def test_report_generator_uses_bilingual_headers_and_unique_filename(tmp_path):
    reporter = ReportGenerator(tmp_path)
    results = [
        {
            "File": "paper.pdf",
            "URL": "file:///tmp/paper.pdf",
            "期刊": "Nature",
            "影响因子": 12.3,
            "作者": "Alice",
            "标题": "中文：示例标题\nEnglish: Sample Title",
            "器件结构": "ITO/EML/Al",
            "EQE": "20.5%",
            "CIE": "(0.21, 0.32)",
            "寿命": "120 h",
            "最高EQE": "20.5%",
            "优化层级": "界面工程",
            "优化策略": "中文：中文总结\nEnglish: English summary",
        }
    ]

    first_path = reporter.generate_excel_report(results)
    second_path = reporter.generate_excel_report(results)

    assert first_path.name.startswith("论文分析报告_")
    assert second_path.name.startswith("论文分析报告_")
    assert first_path != second_path

    workbook = openpyxl.load_workbook(first_path)
    sheet = workbook.active
    headers = [sheet.cell(row=1, column=idx).value for idx in range(1, 6)]
    headers_extended = [sheet.cell(row=1, column=idx).value for idx in range(1, 7)]
    values = [sheet.cell(row=2, column=idx).value for idx in range(1, 8)]

    assert headers == [
        "文件名 File",
        "文件地址 URL",
        "期刊名称 Journal",
        "影响因子 Impact Factor",
        "作者 Authors",
    ]
    assert headers_extended[5] == "处理结果/简述 Processing Status"
    assert values[:3] == ["paper.pdf", "file:///tmp/paper.pdf", "Nature"]
    assert values[6] == "中文：示例标题\nEnglish: Sample Title"


def test_report_generator_highlights_rows_with_many_missing_fields(tmp_path):
    reporter = ReportGenerator(tmp_path)
    results = [
        {
            "File": "bad.pdf",
            "URL": "file:///tmp/bad.pdf",
            "处理结果/简述": "处理失败：数据提取 - 返回空结果",
            "标题": "",
            "期刊": "",
            "影响因子": "",
            "作者": "",
            "器件结构": "",
            "EQE": "",
            "CIE": "",
            "寿命": "",
            "最高EQE": "",
            "优化策略": "",
        }
    ]

    path = reporter.generate_excel_report(results)
    workbook = openpyxl.load_workbook(path)
    sheet = workbook.active
    assert sheet["A2"].fill.start_color.rgb in {"00FFF9EF", "FFFFF9EF"}
