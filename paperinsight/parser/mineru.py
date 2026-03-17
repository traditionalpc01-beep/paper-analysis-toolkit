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

import io
import json
import hashlib
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
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
    API_BASE_URL = "https://mineru.net/api/v4"

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
        self.api_url = self._normalize_api_url(self.config.get("api_url", self.API_BASE_URL))
        self.timeout = self.config.get("timeout", 600)
        self.output_format = self.config.get("output_format", "markdown")
        self.extract_tables = self.config.get("extract_tables", True)
        self.method = self.config.get("method", "auto")
        self.model_version = self.config.get("model_version", "vlm")
        self.language = self.config.get("language")
        self.no_cache = self.config.get("no_cache", False)

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

    def _normalize_api_url(self, api_url: str) -> str:
        """标准化 MinerU API 根路径，兼容旧配置。"""
        normalized = (api_url or self.API_BASE_URL).rstrip("/")
        replacements = {
            "https://mineru.net/api": self.API_BASE_URL,
            "https://mineru.net/open/api": self.API_BASE_URL,
            "https://mineru.net/open/api/v4": self.API_BASE_URL,
        }
        return replacements.get(normalized, normalized)

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
        1. 申请文件上传链接（v4/file-urls/batch）
        2. PUT 上传本地 PDF（上传完成后服务端自动提交任务）
        3. 轮询批量任务状态（v4/extract-results/batch/{batch_id}）
        4. 下载结果压缩包并读取 full.md
        """
        if not self.token:
            raise ValueError("API 模式需要配置 Token")

        headers = self._get_api_headers()

        # Step 1: 申请上传链接
        upload_url = f"{self.api_url}/file-urls/batch"
        request_payload = self._build_api_upload_payload(file_path)
        response = requests.post(
            upload_url,
            headers=headers,
            json=request_payload,
            timeout=min(self.timeout, 60),
        )

        upload_result = self._parse_api_response(response, "申请上传链接失败")
        batch_id = upload_result.get("batch_id")
        file_urls = upload_result.get("file_urls") or []

        if not batch_id or not file_urls:
            raise RuntimeError(f"MinerU 未返回 batch_id 或上传链接: {upload_result}")

        # Step 2: 上传文件
        with file_path.open("rb") as f:
            upload_response = requests.put(
                file_urls[0],
                data=f,
                timeout=self.timeout,
            )

        if upload_response.status_code not in (200, 201):
            raise RuntimeError(
                f"文件上传失败: HTTP {upload_response.status_code} {upload_response.text[:300]}"
            )

        # Step 3: 轮询任务状态
        status_url = f"{self.api_url}/extract-results/batch/{batch_id}"
        poll_interval = 5
        max_polls = max(1, self.timeout // poll_interval)
        extract_result = None

        for _ in range(max_polls):
            response = requests.get(
                status_url,
                headers=headers,
                timeout=30,
            )

            status_result = self._parse_api_response(response, "查询解析状态失败")
            results = status_result.get("extract_result") or []
            if not results:
                time.sleep(poll_interval)
                continue

            extract_result = self._match_extract_result(results, file_path.name)
            status = extract_result.get("state")

            if status == "done":
                break
            if status == "failed":
                error = extract_result.get("err_msg") or "未知错误"
                raise RuntimeError(f"任务失败: {error}")

            time.sleep(poll_interval)
        else:
            raise RuntimeError("任务超时")

        if not extract_result:
            raise RuntimeError("任务完成但未找到对应的解析结果")

        self._populate_result_from_extract_result(result, batch_id, extract_result)

        return result

    def parse_batch(
        self,
        file_paths: List[Path],
        progress_callback=None,
    ) -> Dict[Path, ParseResult]:
        """
        使用 MinerU v4 批量 API 解析多个本地文件。

        Args:
            file_paths: PDF 文件路径列表
            progress_callback: 进度回调，参数为统计字典

        Returns:
            每个文件对应的 ParseResult
        """
        if self.mode != "api":
            raise RuntimeError("批量解析仅支持 MinerU API 模式")
        if not file_paths:
            return {}
        if not self.token:
            raise ValueError("API 模式需要配置 Token")

        normalized_paths = [Path(path) for path in file_paths]
        for path in normalized_paths:
            self._validate_file(path)

        headers = self._get_api_headers()
        response = requests.post(
            f"{self.api_url}/file-urls/batch",
            headers=headers,
            json=self._build_batch_api_upload_payload(normalized_paths),
            timeout=min(self.timeout, 60),
        )
        upload_result = self._parse_api_response(response, "申请批量上传链接失败")
        batch_id = upload_result.get("batch_id")
        file_urls = upload_result.get("file_urls") or []

        if not batch_id or len(file_urls) != len(normalized_paths):
            raise RuntimeError(f"批量上传链接返回异常: {upload_result}")

        for path, upload_url in zip(normalized_paths, file_urls):
            with path.open("rb") as f:
                upload_response = requests.put(upload_url, data=f, timeout=self.timeout)
            if upload_response.status_code not in (200, 201):
                raise RuntimeError(
                    f"文件上传失败: {path.name} HTTP {upload_response.status_code} {upload_response.text[:300]}"
                )

        results_by_name = self._poll_batch_extract_results(
            batch_id=batch_id,
            file_names=[path.name for path in normalized_paths],
            headers=headers,
            progress_callback=progress_callback,
        )

        parse_results: Dict[Path, ParseResult] = {}
        for path in normalized_paths:
            extract_result = results_by_name.get(path.name)
            parse_result = ParseResult(source_file=str(path), parser_name=self.name)
            if not extract_result:
                parse_result.success = False
                parse_result.error_message = "未获取到批量解析结果"
                parse_results[path] = parse_result
                continue

            if extract_result.get("state") != "done":
                parse_result.success = False
                parse_result.error_message = extract_result.get("err_msg") or "批量解析未完成"
                parse_results[path] = parse_result
                continue

            try:
                self._populate_result_from_extract_result(parse_result, batch_id, extract_result)
                parse_result.success = True
            except Exception as e:
                parse_result.success = False
                parse_result.error_message = str(e)
            parse_results[path] = parse_result

        return parse_results

    def _get_api_headers(self) -> Dict[str, str]:
        """获取 MinerU API 请求头。"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _build_batch_api_upload_payload(self, file_paths: List[Path]) -> Dict[str, Any]:
        """构建 v4 批量上传请求体。"""
        payload = self._build_api_common_payload()
        payload["files"] = [self._build_api_file_item(path) for path in file_paths]
        return payload

    def _build_api_common_payload(self) -> Dict[str, Any]:
        """构建批量与单文件共用的 API 参数。"""
        payload: Dict[str, Any] = {
            "model_version": self.model_version,
            "enable_table": self.extract_tables,
            "enable_formula": self.config.get("enable_formula", True),
        }
        if self.language:
            payload["language"] = self.language
        if self.no_cache:
            payload["no_cache"] = True
        return payload

    def _build_api_file_item(self, file_path: Path) -> Dict[str, Any]:
        """构建单个文件的 API 参数。"""
        file_item: Dict[str, Any] = {
            "name": file_path.name,
            "data_id": self._build_data_id(file_path),
        }
        if self.method == "ocr":
            file_item["is_ocr"] = True
        elif self.method == "txt":
            file_item["is_ocr"] = False

        page_ranges = self.config.get("page_ranges")
        if page_ranges:
            file_item["page_ranges"] = page_ranges
        return file_item

    def _build_data_id(self, file_path: Path) -> str:
        """构建符合 MinerU 长度限制的 data_id。"""
        stem = file_path.stem.strip() or "paper"
        normalized = re.sub(r"[^0-9A-Za-z._-]+", "-", stem).strip("-._")
        if not normalized:
            normalized = "paper"

        digest = hashlib.md5(str(file_path).encode("utf-8")).hexdigest()[:12]
        max_length = 128
        reserved = len(digest) + 1
        if len(normalized) > max_length - reserved:
            normalized = normalized[: max_length - reserved]
        return f"{normalized}-{digest}"

    def _poll_batch_extract_results(
        self,
        batch_id: str,
        file_names: List[str],
        headers: Dict[str, str],
        progress_callback=None,
    ) -> Dict[str, Dict[str, Any]]:
        """轮询批量解析结果直至全部完成。"""
        status_url = f"{self.api_url}/extract-results/batch/{batch_id}"
        poll_interval = 5
        max_polls = max(1, self.timeout // poll_interval)
        terminal_states = {"done", "failed"}

        for _ in range(max_polls):
            response = requests.get(status_url, headers=headers, timeout=30)
            status_result = self._parse_api_response(response, "查询批量解析状态失败")
            results = status_result.get("extract_result") or []
            results_by_name = {
                item.get("file_name"): item for item in results if item.get("file_name")
            }

            done = sum(
                1
                for file_name in file_names
                if results_by_name.get(file_name, {}).get("state") == "done"
            )
            failed = sum(
                1
                for file_name in file_names
                if results_by_name.get(file_name, {}).get("state") == "failed"
            )
            running = sum(
                1
                for file_name in file_names
                if results_by_name.get(file_name, {}).get("state") in {"running", "converting"}
            )
            pending = len(file_names) - done - failed - running

            if progress_callback:
                progress_callback(
                    {
                        "batch_id": batch_id,
                        "total": len(file_names),
                        "done": done,
                        "failed": failed,
                        "running": running,
                        "pending": pending,
                    }
                )

            if all(
                results_by_name.get(file_name, {}).get("state") in terminal_states
                for file_name in file_names
                if file_name in results_by_name
            ) and len(results_by_name) >= len(file_names):
                return results_by_name

            time.sleep(poll_interval)

        raise RuntimeError("批量解析任务超时")

    def _populate_result_from_extract_result(
        self,
        result: ParseResult,
        batch_id: str,
        extract_result: Dict[str, Any],
    ) -> None:
        """从单个解析结果对象填充 ParseResult。"""
        full_zip_url = extract_result.get("full_zip_url")
        if not full_zip_url:
            raise RuntimeError(f"任务已完成但缺少 full_zip_url: {extract_result}")

        archive_response = requests.get(full_zip_url, timeout=self.timeout)
        if archive_response.status_code != 200:
            raise RuntimeError(
                f"下载结果压缩包失败: HTTP {archive_response.status_code} {archive_response.text[:300]}"
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_dir = Path(temp_dir)
            with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
                archive.extractall(extract_dir)

            md_file = self._find_markdown_output(extract_dir)
            if not md_file:
                raise FileNotFoundError("MinerU 结果压缩包中未找到 full.md")

            result.markdown = md_file.read_text(encoding="utf-8")
            if self.extract_tables:
                result.tables = self._extract_tables_from_output(extract_dir)

        result.raw_text = self._markdown_to_text(result.markdown)
        result.word_count = self._calculate_word_count(result.markdown)
        result.sections = self._parse_sections(result.markdown)
        result.metadata.update(
            {
                "batch_id": batch_id,
                "model_version": self.model_version,
                "state": extract_result.get("state"),
                "data_id": extract_result.get("data_id"),
                "full_zip_url": full_zip_url,
            }
        )

    def _build_api_upload_payload(self, file_path: Path) -> Dict[str, Any]:
        """构建 v4 本地文件上传请求体。"""
        payload = self._build_api_common_payload()
        payload["files"] = [self._build_api_file_item(file_path)]
        return payload

    def _parse_api_response(self, response: requests.Response, action: str) -> Dict[str, Any]:
        """统一解析 MinerU API 响应。"""
        if response.status_code != 200:
            if response.status_code == 413:
                raise RuntimeError(
                    f"{action}(413): 文件可能超过服务限制，请检查文件大小或 Token 权限"
                )
            raise RuntimeError(f"{action}: HTTP {response.status_code} {response.text[:500]}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"{action}: 响应不是合法 JSON") from exc

        if payload.get("code") not in (0, None):
            message = payload.get("msg") or payload.get("message") or "未知错误"
            raise RuntimeError(f"{action}: {message}")

        data = payload.get("data")
        if data is None:
            raise RuntimeError(f"{action}: 响应缺少 data 字段")
        return data

    def _match_extract_result(self, results: List[Dict[str, Any]], file_name: str) -> Dict[str, Any]:
        """从批量结果中匹配当前文件。"""
        for item in results:
            if item.get("file_name") == file_name:
                return item
        return results[0]

    def _find_markdown_output(self, output_dir: Path) -> Optional[Path]:
        """在 MinerU 输出目录中查找 Markdown 主文件。"""
        preferred_names = ("full.md",)
        for name in preferred_names:
            for path in output_dir.rglob(name):
                if path.is_file():
                    return path

        for path in output_dir.rglob("*.md"):
            if path.is_file():
                return path

        return None

    def _extract_tables_from_output(self, output_dir: Path) -> List[TableData]:
        """
        从 MinerU 输出目录提取表格

        MinerU 可能在 tables 子目录中输出表格数据
        """
        tables = []
        table_files = []
        direct_tables_dir = output_dir / "tables"

        if direct_tables_dir.exists():
            table_files.extend(direct_tables_dir.glob("*.csv"))

        if not table_files:
            table_files.extend(output_dir.rglob("*.csv"))

        for table_file in table_files:
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
