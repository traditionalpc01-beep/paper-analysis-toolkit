"""
分析管线模块
功能: 主处理流程
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from tqdm import tqdm

from paperinsight.core.cache import CacheManager
from paperinsight.core.extractor import DataExtractor
from paperinsight.core.reporter import ReportGenerator
from paperinsight.ocr.local import LocalOCR
from paperinsight.ocr.paddlex_api import PaddleXAPI
from paperinsight.utils.hash_utils import calculate_md5
from paperinsight.utils.file_renamer import FileRenamer
from paperinsight.utils.logger import ErrorLogger, setup_logger
from paperinsight.utils.pdf_utils import extract_text_with_fallback
from paperinsight.web.impact_factor_search import ImpactFactorSearcher


class AnalysisPipeline:
    """分析管线"""
    
    def __init__(
        self,
        output_dir: Union[str, Path],
        cache_dir: Union[str, Path] = ".cache",
        use_paddlex: bool = False,
        paddlex_token: Optional[str] = None,
        paddlex_config: Optional[dict] = None,
        use_llm: bool = False,
        llm_client=None,
        use_web_search: bool = False,
        enable_cache: bool = True,
        text_ratio_threshold: float = 0.1,
    ):
        """
        初始化分析管线
        
        Args:
            output_dir: 输出目录
            cache_dir: 缓存目录
            use_paddlex: 是否使用 PaddleX API
            paddlex_token: PaddleX Token
            paddlex_config: PaddleX 配置
            use_llm: 是否使用 LLM
            llm_client: LLM 客户端
            use_web_search: 是否使用 Web 搜索补全 IF
            enable_cache: 是否启用缓存
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_dir = Path(cache_dir)
        self.enable_cache = enable_cache
        self.text_ratio_threshold = text_ratio_threshold
        
        # 初始化缓存管理器
        self.cache_manager = CacheManager(self.cache_dir) if enable_cache else None
        
        # 初始化 OCR 引擎
        self.ocr_engine = None
        if use_paddlex and paddlex_token:
            try:
                config = paddlex_config or {}
                self.ocr_engine = PaddleXAPI(
                    api_key=paddlex_token,
                    model=config.get("model", "PaddleOCR-VL-1.5"),
                    timeout=config.get("timeout", 300),
                    poll_interval=config.get("poll_interval", 5),
                    use_doc_orientation=config.get("use_doc_orientation", False),
                    use_doc_unwarping=config.get("use_doc_unwarping", False),
                    use_layout_detection=config.get("use_layout_detection", True),
                    use_chart_recognition=config.get("use_chart_recognition", False),
                )
                print("[OCR] 使用 PaddleX API (百度AI Studio)")
            except Exception as e:
                print(f"[警告] PaddleX 初始化失败: {e}, 将使用本地 OCR")
                self.ocr_engine = LocalOCR()
        elif use_paddlex:
            print("[警告] 未提供 PaddleX Token, 将使用本地 OCR")
            self.ocr_engine = LocalOCR()
        
        # 初始化数据提取器
        self.extractor = DataExtractor(
            llm=llm_client,
            use_llm=use_llm,
        )
        
        # 初始化 Web 搜索器
        self.if_searcher = ImpactFactorSearcher() if use_web_search else None
        
        # 初始化报告生成器
        self.reporter = ReportGenerator(self.output_dir)
        
        # 初始化错误日志记录器
        self.error_logger = ErrorLogger(self.output_dir)
        
        # 初始化日志记录器
        self.logger = setup_logger("paperinsight.pipeline")
    
    @staticmethod
    def _build_error_info(
        pdf_name: str,
        error_type: str,
        error_message: str,
        context: str = "PDF处理",
    ) -> dict:
        return {
            "pdf_name": pdf_name,
            "error_type": error_type,
            "error_message": error_message,
            "context": context,
        }

    def process_pdf(
        self,
        pdf_path: Path,
        max_pages: Optional[int] = None,
        use_cache: bool = True,
    ) -> tuple[Optional[dict], Optional[dict]]:
        """
        处理单个 PDF 文件
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大读取页数
            use_cache: 是否使用缓存
        
        Returns:
            提取结果(如果成功)
        """
        pdf_name = pdf_path.name
        md5 = calculate_md5(pdf_path) if self.enable_cache else ""
        
        # 检查缓存
        if self.enable_cache and use_cache and self.cache_manager.has_data_cache(md5):
            self.logger.info(f"[缓存命中] {pdf_name}")
            cached_result = self.cache_manager.load_data_cache(md5) or {}
            cached_result["File"] = pdf_name
            cached_result["URL"] = pdf_path.resolve().as_uri()
            return cached_result, None
        
        try:
            if self.enable_cache and use_cache and self.cache_manager.has_ocr_cache(md5):
                full_text = self.cache_manager.load_ocr_cache(md5) or ""
                front_text = full_text.split("\n\n", 1)[0] if full_text else ""
                metadata = {"_text_source": "ocr_cache"}
            else:
                full_text, front_text, metadata = extract_text_with_fallback(
                    pdf_path,
                    max_pages=max_pages,
                    ocr_engine=self.ocr_engine,
                    min_text_ratio=self.text_ratio_threshold,
                )
                if (
                    full_text
                    and self.enable_cache
                    and metadata.get("_text_source") == "ocr"
                ):
                    self.cache_manager.save_ocr_cache(md5, full_text)
            
            # 如果没有文本,跳过
            if not full_text:
                self.logger.warning(f"[跳过] {pdf_name}: 未提取到文本")
                return None, self._build_error_info(
                    pdf_name,
                    "NoTextExtracted",
                    "未提取到文本",
                )
            
            # 提取结构化数据
            result = self.extractor.extract(full_text, front_text, metadata)
            
            # 添加文件信息
            result["File"] = pdf_name
            result["URL"] = pdf_path.resolve().as_uri()
            
            # 补全影响因子
            if self.if_searcher and not result.get("影响因子"):
                journal_name = result.get("journal_name", "")
                if journal_name and journal_name != "未知期刊":
                    if_value = self.if_searcher.search_impact_factor(journal_name)
                    if if_value:
                        result["影响因子"] = if_value
            
            # 保存缓存
            if self.enable_cache:
                self.cache_manager.save_data_cache(md5, result)
            
            return result, None
        
        except Exception as e:
            self.logger.error(f"[错误] {pdf_name}: {e}")
            return None, self._build_error_info(
                pdf_name,
                type(e).__name__,
                str(e),
            )
    
    def process_batch(
        self,
        pdf_files: list[Path],
        max_pages: Optional[int] = None,
        use_cache: bool = True,
    ) -> tuple[list[dict], list[dict], list[tuple[Path, dict]]]:
        """
        批量处理 PDF 文件
        
        Args:
            pdf_files: PDF 文件列表
            max_pages: 最大读取页数
            use_cache: 是否使用缓存
        
        Returns:
            (成功结果列表, 错误列表)
        """
        results = []
        errors = []
        processed_items = []
        
        for pdf_path in tqdm(pdf_files, desc="处理 PDF"):
            result, error_info = self.process_pdf(pdf_path, max_pages, use_cache)
            if result:
                results.append(result)
                processed_items.append((pdf_path, result))
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
        generate_excel: bool = True,
        generate_json: bool = False,
        sort_by_if: bool = True,
        rename_pdfs: bool = False,
        rename_template: Optional[str] = None,
    ) -> dict:
        """
        运行分析管线
        
        Args:
            pdf_dir: PDF 目录
            recursive: 是否递归扫描
            max_pages: 最大读取页数
            use_cache: 是否使用缓存
            generate_excel: 是否生成 Excel
            generate_json: 是否生成 JSON
        
        Returns:
            运行统计信息
        """
        pdf_dir = Path(pdf_dir)
        
        # 收集 PDF 文件
        if recursive:
            pdf_files = list(pdf_dir.rglob("*.pdf"))
        else:
            pdf_files = list(pdf_dir.glob("*.pdf"))
        
        # 过滤非文件
        pdf_files = [f for f in pdf_files if f.is_file()]
        
        self.logger.info(f"找到 {len(pdf_files)} 个 PDF 文件")
        
        if not pdf_files:
            self.logger.warning("未找到 PDF 文件")
            return {"status": "no_files", "pdf_count": 0}
        
        # 批量处理
        results, errors, processed_items = self.process_batch(pdf_files, max_pages, use_cache)
        
        renamed_count = 0
        if rename_pdfs and processed_items:
            renamer = FileRenamer(output_dir=None, dry_run=False)
            rename_results = renamer.batch_rename(
                processed_items,
                format_template=rename_template or "[{year}_{impact_factor}_{journal}]_{title}.pdf",
            )
            for index, (_, new_path) in enumerate(rename_results):
                if new_path is None:
                    continue
                renamed_count += 1
                result = processed_items[index][1]
                result["File"] = new_path.name
                result["URL"] = new_path.resolve().as_uri()
                if self.enable_cache:
                    md5 = result.get("_cache_md5")
                    if md5:
                        self.cache_manager.save_data_cache(md5, result)

        # 生成报告
        report_files = {}
        
        if generate_excel and results:
            excel_path = self.reporter.generate_excel_report(results, sort_by_if=sort_by_if)
            report_files["excel"] = str(excel_path)
        
        if generate_json and results:
            json_path = self.reporter.generate_json_report(results, sort_by_if=sort_by_if)
            report_files["json"] = str(json_path)
        
        # 保存错误日志
        if errors or self.error_logger.errors:
            error_log_path = self.error_logger.save()
            if error_log_path:
                report_files["error_log"] = str(error_log_path)
        
        # 统计信息
        stats = {
            "status": "completed",
            "pdf_count": len(pdf_files),
            "success_count": len(results),
            "error_count": len(pdf_files) - len(results),
            "report_files": report_files,
            "renamed_count": renamed_count,
            "timestamp": datetime.now().isoformat(),
        }
        
        # 输出统计
        self.logger.info("=" * 70)
        self.logger.info("处理完成!")
        self.logger.info(f"总文件数: {len(pdf_files)}")
        self.logger.info(f"成功: {len(results)}")
        self.logger.info(f"失败: {len(pdf_files) - len(results)}")
        self.logger.info("=" * 70)

        return stats

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
