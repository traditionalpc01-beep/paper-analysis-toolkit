"""
MinerU 解析器实现

MinerU 是一个高性能 PDF 解析工具，可以将 PDF 转换为结构化 Markdown。
支持两种运行模式：
1. CLI 模式：本地命令行调用（需要安装 MinerU）
2. API 模式：云端 API 调用

官方文档：https://mineru.net/apiManage/docs
GitHub：https://github.com/opendatalab/MinerU
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

import requests

from paperinsight.parser.base import BaseParser, ParseResult, TableData, Section


class MinerUParser(BaseParser):
    """
    MinerU PDF 解析器

    支持命令行和 API 两种模式，自动选择最佳方式。
    """

    # CLI 命令名
    CLI_COMMAND = "magic-pdf"

    # API 端点
    API_BASE_URL = "https://mineru.net/api"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 MinerU 解析器

        Args:
            config: 配置字典，支持以下键：
                - mode: "cli" | "api"
                - token: API Token（API 模式需要）
                - api_url: API 端点（可选）
                - timeout: 超时时间（秒）
                - output_format: 输出格式（markdown/json）
                - extract_tables: 是否提取表格
                - method: 解析方法（auto/txt/ocr）
        """
        super().__init__(config)

        self.mode = self.config.get("mode", "cli")
        self.token = self.config.get("token", "")
        self.api_url = self.config.get("api_url", self.API_BASE_URL)
        self.timeout = self.config.get("timeout", 600)
        self.output_format = self.config.get("output_format", "markdown")
        self.extract_tables = self.config.get("extract_tables", True)
        self.method = self.config.get("method", "auto")

    @property
    def name(self) -> str:
        return "MinerU"

    def is_available(self) -> bool:
        """
        检查 MinerU 是否可用

        CLI 模式：检查命令是否存在
        API 模式：检查 Token 是否配置
        """
        if self._is_available is not None:
            return self._is_available

        if self.mode == "cli":
            self._is_available = self._check_cli_available()
        else:
            self._is_available = bool(self.token)

        return self._is_available

    def _check_cli_available(self) -> bool:
        """检查 CLI 命令是否可用"""
        # 检查 magic-pdf 命令是否存在
        result = shutil.which(self.CLI_COMMAND)
        return result is not None

    def parse(self, file_path: Path) -> ParseResult:
        """
        解析 PDF 文件

        Args:
            file_path: PDF 文件路径

        Returns:
            解析结果
        """
        start_time = time.time()
        result = ParseResult(
            source_file=str(file_path),
            parser_name=self.name,
        )

        try:
            self._validate_file(file_path)

            if self.mode == "cli":
                result = self._parse_via_cli(file_path, result)
            else:
                result = self._parse_via_api(file_path, result)

            result.processing_time = time.time() - start_time
            result.success = True

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            result.processing_time = time.time() - start_time

        return result

    def _parse_via_cli(self, file_path: Path, result: ParseResult) -> ParseResult:
        """
        通过 CLI 命令解析 PDF

        MinerU CLI 命令格式：
        magic-pdf -p <pdf_path> -o <output_dir> -m <method>
        """
        # 创建临时输出目录
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # 构建命令
            cmd = [
                self.CLI_COMMAND,
                "-p", str(file_path),
                "-o", str(output_dir),
                "-m", self.method,
            ]

            # 执行命令
            try:
                process_result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                if process_result.returncode != 0:
                    raise RuntimeError(f"MinerU CLI 执行失败: {process_result.stderr}")

            except subprocess.TimeoutExpired:
                raise RuntimeError(f"MinerU CLI 执行超时（>{self.timeout}秒）")
            except FileNotFoundError:
                raise RuntimeError(f"MinerU CLI 未安装，请先安装: pip install magic-pdf[full]")

            # 查找输出文件
            # MinerU 输出目录结构：<output_dir>/<pdf_name>/auto/<pdf_name>.md
            pdf_name = file_path.stem
            md_file = output_dir / pdf_name / self.method / f"{pdf_name}.md"

            if not md_file.exists():
                # 尝试其他可能的路径
                possible_paths = [
                    output_dir / pdf_name / "auto" / f"{pdf_name}.md",
                    output_dir / pdf_name / f"{pdf_name}.md",
                    output_dir / f"{pdf_name}.md",
                ]
                for path in possible_paths:
                    if path.exists():
                        md_file = path
                        break
                else:
                    raise FileNotFoundError(f"找不到 MinerU 输出文件: {md_file}")

            # 读取 Markdown 内容
            result.markdown = md_file.read_text(encoding="utf-8")
            result.raw_text = self._markdown_to_text(result.markdown)
            result.word_count = self._calculate_word_count(result.markdown)

            # 解析表格（如果输出中有表格文件）
            if self.extract_tables:
                result.tables = self._extract_tables_from_output(output_dir / pdf_name)

            # 解析章节结构
            result.sections = self._parse_sections(result.markdown)

            # 获取页数（从 metadata.json 如果存在）
            metadata_file = output_dir / pdf_name / self.method / "metadata.json"
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    result.page_count = metadata.get("page_count", 0)
                    result.metadata.update(metadata)
                except Exception:
                    pass

        return result

    def _parse_via_api(self, file_path: Path, result: ParseResult) -> ParseResult:
        """
        通过 API 解析 PDF

        API 流程：
        1. 上传文件获取 task_id
        2. 轮询任务状态
        3. 下载结果
        """
        if not self.token:
            raise ValueError("API 模式需要配置 Token")

        headers = {
            "Authorization": f"Bearer {self.token}",
        }

        # Step 1: 上传文件
        upload_url = f"{self.api_url}/v1/file/upload"

        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            data = {
                "method": self.method,
                "output_format": self.output_format,
            }

            response = requests.post(
                upload_url,
                headers=headers,
                files=files,
                data=data,
                timeout=self.timeout,
            )

        if response.status_code != 200:
            raise RuntimeError(f"上传失败: {response.text}")

        upload_result = response.json()
        task_id = upload_result.get("data", {}).get("task_id")

        if not task_id:
            raise RuntimeError(f"获取 task_id 失败: {upload_result}")

        # Step 2: 轮询任务状态
        status_url = f"{self.api_url}/v1/task/status"
        poll_interval = 5
        max_polls = self.timeout // poll_interval

        for _ in range(max_polls):
            response = requests.get(
                f"{status_url}?task_id={task_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code != 200:
                raise RuntimeError(f"查询状态失败: {response.text}")

            status_result = response.json()
            status = status_result.get("data", {}).get("status")

            if status == "completed":
                break
            elif status == "failed":
                error = status_result.get("data", {}).get("error", "未知错误")
                raise RuntimeError(f"任务失败: {error}")

            time.sleep(poll_interval)
        else:
            raise RuntimeError("任务超时")

        # Step 3: 下载结果
        download_url = f"{self.api_url}/v1/file/download"
        response = requests.get(
            f"{download_url}?task_id={task_id}&format=markdown",
            headers=headers,
            timeout=self.timeout,
        )

        if response.status_code != 200:
            raise RuntimeError(f"下载失败: {response.text}")

        result.markdown = response.text
        result.raw_text = self._markdown_to_text(result.markdown)
        result.word_count = self._calculate_word_count(result.markdown)

        # 解析章节
        result.sections = self._parse_sections(result.markdown)

        return result

    def _extract_tables_from_output(self, output_dir: Path) -> List[TableData]:
        """
        从 MinerU 输出目录提取表格

        MinerU 可能在 tables 子目录中输出表格数据
        """
        tables = []
        tables_dir = output_dir / "tables"

        if not tables_dir.exists():
            return tables

        for table_file in tables_dir.glob("*.csv"):
            try:
                table = self._parse_csv_table(table_file)
                if table:
                    tables.append(table)
            except Exception:
                continue

        return tables

    def _parse_csv_table(self, csv_file: Path) -> Optional[TableData]:
        """解析 CSV 格式的表格文件"""
        import csv

        try:
            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                return None

            # 第一行作为表头
            return TableData(
                headers=rows[0],
                rows=rows[1:],
                caption=csv_file.stem,
            )

        except Exception:
            return None

    def _parse_sections(self, markdown: str) -> List[Section]:
        """
        解析 Markdown 中的章节结构

        识别标题层级，构建章节树
        """
        sections = []
        current_section = None
        content_lines = []

        for line in markdown.split("\n"):
            # 检测标题
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if header_match:
                # 保存当前章节内容
                if current_section:
                    current_section.content = "\n".join(content_lines).strip()
                    sections.append(current_section)

                # 开始新章节
                level = len(header_match.group(1))
                title = header_match.group(2).strip()

                current_section = Section(
                    title=title,
                    content="",
                    level=level,
                )
                content_lines = []
            else:
                if current_section:
                    content_lines.append(line)

        # 保存最后一个章节
        if current_section:
            current_section.content = "\n".join(content_lines).strip()
            sections.append(current_section)

        return sections

    def _markdown_to_text(self, markdown: str) -> str:
        """将 Markdown 转换为纯文本"""
        # 移除代码块
        text = re.sub(r"```[\s\S]*?```", "", markdown)
        # 移除链接
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        # 移除图片
        text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", "", text)
        # 移除标题标记
        text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
        # 移除粗体/斜体
        text = re.sub(r"[*_]+([^*_]+)[*_]+", r"\1", text)
        # 移除多余空白
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


def check_mineru_installation() -> Dict[str, Any]:
    """
    检查 MinerU 安装状态

    返回安装信息和可用功能
    """
    info = {
        "cli_available": False,
        "version": None,
        "install_command": None,
    }

    # 检查 CLI
    cli_path = shutil.which(MinerUParser.CLI_COMMAND)
    if cli_path:
        info["cli_available"] = True
        try:
            result = subprocess.run(
                [MinerUParser.CLI_COMMAND, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            info["version"] = result.stdout.strip()
        except Exception:
            pass

    # 提供安装命令
    info["install_command"] = "pip install magic-pdf[full]"

    return info
