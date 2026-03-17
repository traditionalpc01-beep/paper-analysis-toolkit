"""
分析管线模块 v3.0

核心处理流程：
1. PDF 解析（MinerU 优先）
2. 文本降噪（过滤噪声章节）
3. LLM 语义提取（嵌套式 JSON Schema）
4. 数据校验（Pydantic）
5. 报告生成（Excel/JSON）
"""

from __future__ import annotations

import time
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import quote

from tqdm import tqdm

from paperinsight.core.cache import CacheManager
from paperinsight.core.extractor import DataExtractor
from paperinsight.core.reporter import ReportGenerator
from paperinsight.models.schemas import PaperData, ExtractionResult
from paperinsight.parser.mineru import MinerUParser
from paperinsight.parser.base import ParseResult
from paperinsight.cleaner.section_filter import SectionFilter, clean_paper_content
from paperinsight.utils.hash_utils import calculate_md5
from paperinsight.utils.file_renamer import FileRenamer
from paperinsight.utils.logger import ErrorLogger, setup_logger
from paperinsight.utils.pdf_utils import extract_text_with_fallback
from paperinsight.web.impact_factor_fetcher import MJLImpactFactorFetcher
from paperinsight.web.journal_resolver import MJLJournalResolution, MJLJournalResolver


class AnalysisPipeline:
    """
    v3.0 分析管线

    整合 MinerU 解析 + 文本清洗 + LLM 提取的完整流程。
    """

    def __init__(
        self,
        output_dir: Union[str, Path],
        config: Optional[Dict[str, Any]] = None,
        cache_dir: Union[str, Path] = ".cache",
    ):
        """
        初始化分析管线

        Args:
            output_dir: 输出目录
            config: 完整配置字典（包含 mineru, llm, cleaner 等配置）
            cache_dir: 缓存目录
        """
        self.config = config or {}
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = Path(cache_dir)
        self.enable_cache = self.config.get("cache", {}).get("enabled", True)

        # 初始化日志记录器（放在最前面，确保其他初始化可以使用）
        self.logger = setup_logger("paperinsight.pipeline")

        # 初始化缓存管理器
        self.cache_manager = CacheManager(self.cache_dir) if self.enable_cache else None

        # 初始化 MinerU 解析器
        self.parser = self._init_parser()

        # 初始化文本清洗器
        self.cleaner = SectionFilter(self.config.get("cleaner", {}))

        # 初始化数据提取器
        self.extractor = DataExtractor(config=self.config)

        # 初始化 Web 检索器
        web_config = self.config.get("web_search", {})
        timeout = int(web_config.get("timeout", 30))
        web_enabled = bool(web_config.get("enabled", True))
        self.journal_resolver = (
            MJLJournalResolver(timeout=timeout)
            if web_enabled and web_config.get("resolve_journal_metadata", True)
            else None
        )
        self.if_fetcher = (
            MJLImpactFactorFetcher(timeout=timeout)
            if web_enabled and web_config.get("fetch_official_impact_factor", True)
            else None
        )

        # 初始化报告生成器
        self.reporter = ReportGenerator(self.output_dir)

        # 初始化错误日志记录器
        self.error_logger = ErrorLogger(self.output_dir)

    def _init_parser(self) -> Optional[MinerUParser]:
        """初始化文档解析器"""
        mineru_config = self.config.get("mineru", {})

        if not mineru_config.get("enabled", True):
            return None

        try:
            parser = MinerUParser(config=mineru_config)
            if parser.is_available():
                self.logger.info(f"[Parser] 使用 MinerU ({mineru_config.get('mode', 'cli')} 模式)")
                return parser
            else:
                self.logger.warning("[Parser] MinerU 不可用，将使用基础 PDF 解析")
                return None
        except Exception as e:
            self.logger.warning(f"[Parser] MinerU 初始化失败: {e}")
            return None

    def process_pdf(
        self,
        pdf_path: Path,
        max_pages: Optional[int] = None,
        use_cache: bool = True,
    ) -> Tuple[Optional[PaperData], Optional[Dict[str, Any]]]:
        """
        处理单个 PDF 文件（v3.0 流程）

        流程：
        1. 计算文件 MD5，检查缓存
        2. 使用 MinerU 解析 PDF -> Markdown
        3. 文本降噪，提取核心章节
        4. LLM 提取结构化数据
        5. Pydantic 校验

        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大读取页数
            use_cache: 是否使用缓存

        Returns:
            (提取结果, 错误信息)
        """
        start_time = time.time()
        pdf_name = pdf_path.name
        md5 = calculate_md5(pdf_path) if self.enable_cache else ""

        # Step 1: 检查缓存
        if self.enable_cache and use_cache and self.cache_manager.has_data_cache(md5):
            self.logger.info(f"[缓存命中] {pdf_name}")
            cached_result = self.cache_manager.load_data_cache(md5)
            if cached_result:
                try:
                    paper_data = PaperData(**cached_result)
                    return paper_data, None
                except Exception:
                    pass  # 缓存数据格式不兼容，重新处理

        # Step 2: PDF 解析
        parse_result = self._parse_pdf(pdf_path, md5, use_cache)

        if not parse_result.success:
            return None, self._build_error_info(
                pdf_name,
                "ParseFailed",
                parse_result.error_message or "PDF 解析失败",
                "PDF解析",
                pdf_path=str(pdf_path),
            )

        return self._extract_from_parse_result(
            pdf_path=pdf_path,
            parse_result=parse_result,
            md5=md5,
            use_cache=use_cache,
            start_time=start_time,
        )

    def _extract_from_parse_result(
        self,
        pdf_path: Path,
        parse_result: ParseResult,
        md5: str,
        use_cache: bool,
        start_time: Optional[float] = None,
    ) -> Tuple[Optional[PaperData], Optional[Dict[str, Any]]]:
        """对解析后的 Markdown 执行清洗、提取、校验与缓存。"""
        pdf_name = pdf_path.name
        start_time = start_time or time.time()

        self.logger.info(
            f"[调试] 解析结果 markdown 长度: {len(parse_result.markdown) if parse_result.markdown else 0}"
        )
        cleaned_content = self.cleaner.clean(parse_result.markdown)
        extraction_text = cleaned_content.get_text_for_extraction()
        self.logger.info(
            f"[调试] 清洗后提取文本长度: {len(extraction_text) if extraction_text else 0}"
        )
        self.logger.info(
            f"[调试] full_text={len(cleaned_content.full_text) if cleaned_content.full_text else 0}, "
            f"abstract={len(cleaned_content.abstract) if cleaned_content.abstract else 0}, "
            f"introduction={len(cleaned_content.introduction) if cleaned_content.introduction else 0}, "
            f"experimental={len(cleaned_content.experimental) if cleaned_content.experimental else 0}, "
            f"results={len(cleaned_content.results) if cleaned_content.results else 0}"
        )

        if not extraction_text.strip():
            return None, self._build_error_info(
                pdf_name,
                "NoContentAfterCleaning",
                "清洗后无有效内容",
                "文本清洗",
                pdf_path=str(pdf_path),
            )

        extraction_result = self.extractor.extract(
            markdown_text=parse_result.markdown,
            cleaned_text=extraction_text,
            parse_result=parse_result,
        )

        if not extraction_result.success or not extraction_result.data:
            return None, self._build_error_info(
                pdf_name,
                "ExtractionFailed",
                extraction_result.error_message or "数据提取失败",
                "数据提取",
                pdf_path=str(pdf_path),
            )

        paper_data = extraction_result.data

        journal_resolution = self._resolve_journal_metadata(paper_data)
        if self.if_fetcher:
            self._supplement_impact_factor(paper_data, journal_resolution)

        if self.enable_cache and use_cache:
            self.cache_manager.save_data_cache(md5, paper_data.model_dump())

        processing_time = time.time() - start_time
        self.logger.info(f"[完成] {pdf_name} ({processing_time:.1f}s)")

        return paper_data, None

    def _parse_pdf(
        self,
        pdf_path: Path,
        md5: str,
        use_cache: bool,
    ) -> ParseResult:
        """
        解析 PDF 文件

        优先使用 MinerU，失败则回退到基础解析。
        """
        # 检查 Markdown 缓存
        if self.enable_cache and use_cache and self.cache_manager.has_markdown_cache(md5):
            cached_text = self.cache_manager.load_markdown_cache(md5) or ""
            return ParseResult(
                markdown=cached_text,
                raw_text=cached_text,
                success=True,
                parser_name="cache",
            )

        # 使用 MinerU 解析
        if self.parser and self.parser.is_available():
            try:
                result = self.parser.parse(pdf_path)
                if result.success and result.markdown:
                    # 保存 Markdown 缓存
                    if self.enable_cache:
                        self.cache_manager.save_markdown_cache(md5, result.markdown)
                    return result
            except Exception as e:
                self.logger.warning(f"[MinerU] 解析失败: {e}, 回退到基础解析")

        # 回退到基础 PDF 解析
        text_ratio_threshold = self.config.get("pdf", {}).get("text_ratio_threshold", 0.1)
        full_text, front_text, metadata = extract_text_with_fallback(
            pdf_path,
            min_text_ratio=text_ratio_threshold,
        )

        return ParseResult(
            markdown=full_text,
            raw_text=full_text,
            success=bool(full_text),
            parser_name="pymupdf",
            metadata=metadata,
        )

    def _resolve_journal_metadata(self, paper_data: PaperData) -> Optional[MJLJournalResolution]:
        """补全期刊标准信息。"""
        if not self.journal_resolver:
            return None

        paper_info = paper_data.paper_info
        raw_journal_title = paper_info.raw_journal_title or paper_info.journal_name
        raw_issn = paper_info.raw_issn
        raw_eissn = paper_info.raw_eissn

        if not any((raw_journal_title, raw_issn, raw_eissn)):
            return None

        try:
            resolution = self.journal_resolver.resolve(
                journal_title=raw_journal_title,
                issn=raw_issn,
                eissn=raw_eissn,
            )
        except Exception as e:
            self.logger.warning(f"[期刊解析] 失败: {e}")
            return None

        if raw_journal_title and not paper_info.raw_journal_title:
            paper_info.raw_journal_title = raw_journal_title

        if resolution.match_method:
            paper_info.match_method = resolution.match_method

        if resolution.candidate:
            paper_info.matched_journal_title = resolution.matched_journal_title
            paper_info.matched_issn = resolution.matched_issn
            paper_info.journal_profile_url = resolution.candidate.search_url
            paper_info.journal_name = resolution.matched_journal_title or paper_info.journal_name
        elif resolution.search_value and not paper_info.journal_profile_url:
            search_value = resolution.search_value
            if "-" in search_value and len(search_value) == 9:
                paper_info.journal_profile_url = (
                    f"{self.journal_resolver.SEARCH_RESULTS_URL}?issn={quote(search_value)}"
                )
            else:
                paper_info.journal_profile_url = (
                    f"{self.journal_resolver.SEARCH_RESULTS_URL}?search={quote(search_value)}"
                )

        return resolution

    def _supplement_impact_factor(
        self,
        paper_data: PaperData,
        journal_resolution: Optional[MJLJournalResolution] = None,
    ) -> None:
        """补全影响因子。"""
        paper_info = paper_data.paper_info
        journal_name = paper_info.journal_name or paper_info.raw_journal_title
        if not any((journal_name, paper_info.raw_issn, paper_info.raw_eissn)):
            return

        try:
            current_if = paper_info.impact_factor
            web_config = self.config.get("web_search", {})
            should_correct_existing = bool(web_config.get("correct_existing_impact_factor", True))
            fetch_official_impact_factor = bool(web_config.get("fetch_official_impact_factor", True))

            if current_if and not should_correct_existing and 0.1 <= current_if <= 200 and not fetch_official_impact_factor:
                return

            resolution = journal_resolution or self._resolve_journal_metadata(paper_data)
            if resolution is None:
                return

            if resolution.status != "OK" or not resolution.candidate:
                paper_info.impact_factor_source = "MJL_RESOLVER"
                paper_info.impact_factor_status = resolution.status
                return

            if not fetch_official_impact_factor:
                return

            fetch_result = self.if_fetcher.lookup(resolution.candidate)
            paper_info.impact_factor_source = fetch_result.source_name
            paper_info.impact_factor_status = fetch_result.status

            if fetch_result.source_url:
                paper_info.journal_profile_url = fetch_result.source_url

            if fetch_result.status != "OK" or fetch_result.impact_factor is None:
                return

            paper_info.impact_factor_year = fetch_result.year

            if current_if is None or current_if <= 0:
                paper_info.impact_factor = fetch_result.impact_factor
                return

            if current_if < 0.1 or current_if > 200:
                paper_info.impact_factor = fetch_result.impact_factor
                return

            if should_correct_existing and abs(current_if - fetch_result.impact_factor) >= 0.5:
                paper_info.impact_factor = fetch_result.impact_factor
        except Exception as e:
            self.logger.warning(f"[IF搜索] 失败: {e}")

    def process_batch(
        self,
        pdf_files: List[Path],
        max_pages: Optional[int] = None,
        use_cache: bool = True,
        batch_size: int = 1,
    ) -> Tuple[List[PaperData], List[Dict[str, Any]], List[Tuple[Path, PaperData]]]:
        """
        批量处理 PDF 文件

        Args:
            pdf_files: PDF 文件列表
            max_pages: 最大读取页数
            use_cache: 是否使用缓存

        Returns:
            (成功结果列表, 错误列表, 处理项列表)
        """
        results: List[PaperData] = []
        errors: List[Dict[str, Any]] = []
        processed_items: List[Tuple[Path, PaperData]] = []

        pending_files: List[Tuple[Path, str]] = []

        with tqdm(total=len(pdf_files), desc="处理 PDF") as progress_bar:
            for pdf_path in pdf_files:
                md5 = calculate_md5(pdf_path) if self.enable_cache else ""
                if self.enable_cache and use_cache and self.cache_manager.has_data_cache(md5):
                    self.logger.info(f"[缓存命中] {pdf_path.name}")
                    cached_result = self.cache_manager.load_data_cache(md5)
                    if cached_result:
                        try:
                            paper_data = PaperData(**cached_result)
                            results.append(paper_data)
                            processed_items.append((pdf_path, paper_data))
                            progress_bar.update(1)
                            continue
                        except Exception:
                            pass
                pending_files.append((pdf_path, md5))

            use_mineru_batch = (
                bool(pending_files)
                and self.parser
                and isinstance(self.parser, MinerUParser)
                and self.parser.mode == "api"
                and batch_size > 1
                and len(pending_files) > 1
                and hasattr(self.parser, "parse_batch")
            )

            if use_mineru_batch:
                total_batches = ceil(len(pending_files) / batch_size)
                for batch_index, batch_items in enumerate(self._chunk_items(pending_files, batch_size), start=1):
                    batch_paths = [pdf_path for pdf_path, _ in batch_items]
                    self.logger.info(
                        f"[MinerU 批量] 第 {batch_index}/{total_batches} 批，文件数 {len(batch_paths)}"
                    )
                    try:
                        parse_results = self.parser.parse_batch(
                            batch_paths,
                            progress_callback=lambda info, batch_index=batch_index, total_batches=total_batches:
                                progress_bar.set_postfix_str(
                                    f"批次 {batch_index}/{total_batches} | 完成 {info.get('done', 0)}/{info.get('total', 0)} | 运行中 {info.get('running', 0)}"
                                ),
                        )
                    except Exception as e:
                        self.logger.warning(f"[MinerU 批量] 批量解析失败，回退逐篇处理: {e}")
                        parse_results = {}

                    for pdf_path, md5 in batch_items:
                        parse_result = parse_results.get(pdf_path)
                        if parse_result and parse_result.success:
                            paper_data, error_info = self._extract_from_parse_result(
                                pdf_path=pdf_path,
                                parse_result=parse_result,
                                md5=md5,
                                use_cache=use_cache,
                            )
                        else:
                            paper_data, error_info = self.process_pdf(pdf_path, max_pages, use_cache)

                        self._collect_batch_item_result(
                            pdf_path,
                            paper_data,
                            error_info,
                            results,
                            errors,
                            processed_items,
                        )
                        progress_bar.update(1)
            else:
                for pdf_path, _ in pending_files:
                    paper_data, error_info = self.process_pdf(pdf_path, max_pages, use_cache)
                    self._collect_batch_item_result(
                        pdf_path,
                        paper_data,
                        error_info,
                        results,
                        errors,
                        processed_items,
                    )
                    progress_bar.update(1)

        return results, errors, processed_items

    def run(
        self,
        pdf_dir: Union[str, Path],
        recursive: bool = False,
        max_pages: Optional[int] = None,
        use_cache: bool = True,
        sort_by_if: bool = True,
        rename_pdfs: bool = False,
        rename_template: Optional[str] = None,
        pdf_files: Optional[List[Path]] = None,
        batch_size: int = 1,
    ) -> Dict[str, Any]:
        """
        运行分析管线

        Args:
            pdf_dir: PDF 目录
            recursive: 是否递归扫描
            max_pages: 最大读取页数
            use_cache: 是否使用缓存
            sort_by_if: 是否按影响因子排序
            rename_pdfs: 是否重命名 PDF
            rename_template: 重命名模板

        Returns:
            运行统计信息
        """
        pdf_dir = Path(pdf_dir)

        # 收集 PDF 文件
        if pdf_files is None:
            if recursive:
                pdf_files = list(pdf_dir.rglob("*.pdf"))
            else:
                pdf_files = list(pdf_dir.glob("*.pdf"))

        pdf_files = [Path(f) for f in pdf_files if Path(f).is_file()]
        self.logger.info(f"找到 {len(pdf_files)} 个 PDF 文件")

        if not pdf_files:
            self.logger.warning("未找到 PDF 文件")
            return {"status": "no_files", "pdf_count": 0}

        # 批量处理
        results, errors, processed_items = self.process_batch(
            pdf_files, max_pages, use_cache, batch_size=batch_size
        )

        # 重命名 PDF
        renamed_count = 0
        if rename_pdfs and processed_items:
            renamed_count = self._rename_pdfs(
                processed_items, rename_template or "[{year}_{impact_factor}_{journal}]_{title}.pdf"
            )

        # 生成报告
        report_files = self._generate_reports(processed_items, errors, sort_by_if)

        # 保存错误日志
        if self.error_logger.errors:
            error_log_path = self.error_logger.save()
            if error_log_path:
                report_files["error_log"] = str(error_log_path)
                self.logger.info(f"[错误日志] 已保存: {error_log_path}")

        # 统计信息
        stats = {
            "status": "completed",
            "pdf_count": len(pdf_files),
            "success_count": len(results),
            "error_count": len(errors),
            "report_files": report_files,
            "renamed_count": renamed_count,
            "timestamp": datetime.now().isoformat(),
        }

        # 输出统计
        self._print_summary(stats)

        return stats

    def _rename_pdfs(
        self,
        processed_items: List[Tuple[Path, PaperData]],
        rename_template: str,
    ) -> int:
        """重命名 PDF 文件"""
        renamer = FileRenamer(output_dir=None, dry_run=False)

        # 转换为旧格式以兼容 FileRenamer
        old_format_items = []
        for pdf_path, paper_data in processed_items:
            old_result = paper_data.to_excel_row()
            old_result["_cache_md5"] = calculate_md5(pdf_path)
            old_format_items.append((pdf_path, old_result))

        rename_results = renamer.batch_rename(old_format_items, format_template=rename_template)

        renamed_count = 0
        for index, (_, new_path) in enumerate(rename_results):
            if new_path is None:
                continue
            renamed_count += 1
            # 更新缓存
            if self.enable_cache:
                paper_data = processed_items[index][1]
                md5 = calculate_md5(processed_items[index][0])
                self.cache_manager.save_data_cache(md5, paper_data.model_dump())

        return renamed_count

    def _generate_reports(
        self,
        processed_items: List[Tuple[Path, PaperData]],
        errors: List[Dict[str, Any]],
        sort_by_if: bool,
    ) -> Dict[str, str]:
        """生成报告"""
        report_files = {}

        output_config = self.config.get("output", {})
        formats = output_config.get("format", ["excel"])

        if not processed_items:
            return report_files

        dict_results = []
        json_results = []
        for pdf_path, paper_data in processed_items:
            row = paper_data.to_excel_row()
            row["File"] = pdf_path.name
            row["URL"] = pdf_path.resolve().as_uri()
            row["processing_status"] = self._build_processing_summary(paper_data)
            dict_results.append(row)

            json_row = paper_data.model_dump()
            json_row["File"] = pdf_path.name
            json_row["URL"] = pdf_path.resolve().as_uri()
            json_row["processing_status"] = row["processing_status"]
            json_results.append(json_row)

        for error in errors:
            error_row = {
                "File": error.get("pdf_name", ""),
                "URL": Path(error["pdf_path"]).resolve().as_uri() if error.get("pdf_path") else "",
                "processing_status": self._build_error_summary(error),
                "标题": "",
                "期刊": "",
                "影响因子": "",
                "作者": "",
                "器件结构": "",
                "EQE": "",
                "CIE": "",
                "寿命": "",
                "最高EQE": "",
                "优化层级": "",
                "优化策略": "",
                "优化详情": "",
                "关键发现": "",
                "EQE原文": "",
                "CIE原文": "",
                "寿命原文": "",
                "结构原文": "",
            }
            dict_results.append(error_row)

            json_results.append(
                {
                    "File": error.get("pdf_name", ""),
                    "URL": Path(error["pdf_path"]).resolve().as_uri() if error.get("pdf_path") else "",
                    "processing_status": error_row["processing_status"],
                    "error": error,
                }
            )

        # 生成 Excel
        if "excel" in formats:
            excel_path = self.reporter.generate_excel_report(dict_results, sort_by_if=sort_by_if)
            if excel_path:
                report_files["excel"] = str(excel_path)

        # 生成 JSON
        if "json" in formats:
            json_path = self.reporter.generate_json_report(json_results, sort_by_if=sort_by_if)
            if json_path:
                report_files["json"] = str(json_path)

        return report_files

    def _print_summary(self, stats: Dict[str, Any]) -> None:
        """打印处理摘要"""
        self.logger.info("=" * 70)
        self.logger.info("处理完成!")
        self.logger.info(f"总文件数: {stats['pdf_count']}")
        self.logger.info(f"成功: {stats['success_count']}")
        self.logger.info(f"失败: {stats['error_count']}")
        self.logger.info("=" * 70)

    @staticmethod
    def _build_error_info(
        pdf_name: str,
        error_type: str,
        error_message: str,
        context: str = "PDF处理",
        pdf_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """构建错误信息"""
        return {
            "pdf_name": pdf_name,
            "pdf_path": pdf_path,
            "error_type": error_type,
            "error_message": error_message,
            "context": context,
        }

    @staticmethod
    def _build_processing_summary(paper_data: PaperData) -> str:
        info = paper_data.paper_info
        missing = []
        if not info.journal_name:
            missing.append("期刊")
        if info.impact_factor in (None, 0):
            missing.append("影响因子")
        if not paper_data.devices:
            missing.append("器件数据")
        else:
            best_device = paper_data.get_best_device()
            if not best_device or not best_device.eqe:
                missing.append("EQE")
            if not best_device or not best_device.structure:
                missing.append("结构")

        if not missing:
            return "处理成功：核心字段解析完整"

        if len(missing) >= 4:
            return "部分解析异常：缺少 " + "、".join(missing[:5])
        return "处理成功：待补充 " + "、".join(missing)

    @staticmethod
    def _build_error_summary(error: Dict[str, Any]) -> str:
        context = error.get("context", "处理流程")
        message = error.get("error_message", "未知错误").strip()
        if len(message) > 70:
            message = message[:67].rstrip() + "..."
        return f"处理失败：{context} - {message}"

    def _collect_batch_item_result(
        self,
        pdf_path: Path,
        paper_data: Optional[PaperData],
        error_info: Optional[Dict[str, Any]],
        results: List[PaperData],
        errors: List[Dict[str, Any]],
        processed_items: List[Tuple[Path, PaperData]],
    ) -> None:
        """收集批量处理单个文件的结果。"""
        if paper_data:
            results.append(paper_data)
            processed_items.append((pdf_path, paper_data))
            return

        if error_info:
            errors.append(error_info)
            self.error_logger.log_error(
                error_info["pdf_name"],
                Exception(error_info["error_message"]),
                context=error_info.get("context", "PDF处理"),
            )

    @staticmethod
    def _chunk_items(items: List[Tuple[Path, str]], chunk_size: int) -> List[List[Tuple[Path, str]]]:
        """按批次切分列表。"""
        if chunk_size <= 0:
            chunk_size = 1
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    def cleanup_temp_files(self):
        """清理临时文件"""
        temp_extensions = [".tmp", ".temp"]
        temp_files = []

        for ext in temp_extensions:
            temp_files.extend(self.output_dir.glob(f"*{ext}"))
            temp_files.extend(Path(".").glob(f"*{ext}"))

        for temp_file in temp_files:
            try:
                temp_file.unlink()
                self.logger.info(f"已清理临时文件: {temp_file}")
            except Exception as e:
                self.logger.warning(f"清理临时文件失败: {temp_file}, {e}")
