"""
CLI 启动引导相关测试。
"""

from typer.testing import CliRunner

from paperinsight.cli import app


runner = CliRunner()


def test_root_command_shows_startup_guide():
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "启动引导" in result.stdout
    assert "paperinsight config" in result.stdout
    assert "paperinsight analyze ./pdfs" in result.stdout


def test_analyze_help_keeps_command_usage_clean():
    result = runner.invoke(app, ["analyze", "--help"])

    assert result.exit_code == 0
    assert "启动引导" not in result.stdout
    assert "分析 PDF 论文并生成报告" in result.stdout
    assert "--rename-pdfs" in result.stdout
