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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
from paperinsight.web.impact_factor_search import ImpactFactorSearcher


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

        # 初始化缓存管理器
        self.cache_manager = CacheManager(self.cache_dir) if self.enable_cache else None

        # 初始化 MinerU 解析器
        self.parser = self._init_parser()

        # 初始化文本清洗器
        self.cleaner = SectionFilter(self.config.get("cleaner", {}))

        # 初始化数据提取器
        self.extractor = DataExtractor(config=self.config)

        # 初始化 Web 搜索器
        web_config = self.config.get("web_search", {})
        self.if_searcher = ImpactFactorSearcher() if web_config.get("enabled", True) else None

        # 初始化报告生成器
        self.reporter = ReportGenerator(self.output_dir)

        # 初始化错误日志记录器
        self.error_logger = ErrorLogger(self.output_dir)

        # 初始化日志记录器
        self.logger = setup_logger("paperinsight.pipeline")

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
            )

        # Step 3: 文本清洗
        cleaned_content = self.cleaner.clean(parse_result.markdown)
        extraction_text = cleaned_content.get_text_for_extraction()

        if not extraction_text.strip():
            return None, self._build_error_info(
                pdf_name,
                "NoContentAfterCleaning",
                "清洗后无有效内容",
                "文本清洗",
            )

        # Step 4: LLM 提取
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
            )

        paper_data = extraction_result.data

        # Step 5: 补全影响因子
        if self.if_searcher:
            self._supplement_impact_factor(paper_data)

        # Step 6: 保存缓存
        if self.enable_cache and use_cache:
            self.cache_manager.save_data_cache(md5, paper_data.model_dump())

        # 记录处理时间
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
        # 检查 OCR 缓存
        if self.enable_cache and use_cache and self.cache_manager.has_ocr_cache(md5):
            cached_text = self.cache_manager.load_ocr_cache(md5) or ""
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
                    # 保存 OCR 缓存
                    if self.enable_cache:
                        self.cache_manager.save_ocr_cache(md5, result.markdown)
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

    def _supplement_impact_factor(self, paper_data: PaperData) -> None:
        """补全影响因子"""
        if paper_data.paper_info.impact_factor:
            return

        journal_name = paper_data.paper_info.journal_name
        if not journal_name:
            return

        try:
            if_value = self.if_searcher.search_impact_factor(journal_name)
            if if_value:
                paper_data.paper_info.impact_factor = if_value
        except Exception as e:
            self.logger.warning(f"[IF搜索] 失败: {e}")

    def process_batch(
        self,
        pdf_files: List[Path],
        max_pages: Optional[int] = None,
        use_cache: bool = True,
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

        for pdf_path in tqdm(pdf_files, desc="处理 PDF"):
            paper_data, error_info = self.process_pdf(pdf_path, max_pages, use_cache)

            if paper_data:
                results.append(paper_data)
                processed_items.append((pdf_path, paper_data))
            elif error_info:
                errors.append(error_info)
                self.error_logger.log_error(
                    error_info["pdf_name"],
                    Exception(error_info["error_message"]),
                    context=error_info.get("context", "PDF处理"),
                )

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
        if recursive:
            pdf_files = list(pdf_dir.rglob("*.pdf"))
        else:
            pdf_files = list(pdf_dir.glob("*.pdf"))

        pdf_files = [f for f in pdf_files if f.is_file()]
        self.logger.info(f"找到 {len(pdf_files)} 个 PDF 文件")

        if not pdf_files:
            self.logger.warning("未找到 PDF 文件")
            return {"status": "no_files", "pdf_count": 0}

        # 批量处理
        results, errors, processed_items = self.process_batch(
            pdf_files, max_pages, use_cache
        )

        # 重命名 PDF
        renamed_count = 0
        if rename_pdfs and processed_items:
            renamed_count = self._rename_pdfs(
                processed_items, rename_template or "[{year}_{impact_factor}_{journal}]_{title}.pdf"
            )

        # 生成报告
        report_files = self._generate_reports(results, sort_by_if)

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
        results: List[PaperData],
        sort_by_if: bool,
    ) -> Dict[str, str]:
        """生成报告"""
        report_files = {}

        output_config = self.config.get("output", {})
        formats = output_config.get("format", ["excel"])

        if not results:
            return report_files

        # 转换为字典格式
        dict_results = [r.to_excel_row() for r in results]

        # 生成 Excel
        if "excel" in formats:
            excel_path = self.reporter.generate_excel_report(dict_results, sort_by_if=sort_by_if)
            if excel_path:
                report_files["excel"] = str(excel_path)

        # 生成 JSON
        if "json" in formats:
            json_results = [r.model_dump() for r in results]
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
    ) -> Dict[str, Any]:
        """构建错误信息"""
        return {
            "pdf_name": pdf_name,
            "error_type": error_type,
            "error_message": error_message,
            "context": context,
        }

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
