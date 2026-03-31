"""
数据提取器模块 v3.0

功能：
1. 使用 LLM 进行语义化数据提取
2. 嵌套式 JSON Schema 输出
3. Pydantic 数据校验
4. 正则表达式兜底方案
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Type

from pydantic import ValidationError

from paperinsight.models.schemas import (
    DeviceData,
    PaperData,
    PaperInfo,
    ExtractionResult,
    DataSourceReference,
    OptimizationInfo,
    PAPER_DATA_JSON_SCHEMA,
)
from paperinsight.parser.base import ParseResult
from paperinsight.llm.base import BaseLLM
from paperinsight.llm import create_llm_client
from paperinsight.llm.prompt_templates import (
    format_bilingual_postprocess_prompt,
    format_extraction_prompt_v3,
    format_lite_paper_info_backfill_prompt,
)
from paperinsight.utils.logger import setup_logger
from paperinsight.utils.pdf_utils import PDFProcessor


class DataExtractor:
    """
    v3.0 数据提取器

    支持两种提取模式：
    - LLM 模式：语义化提取，输出嵌套 JSON
    - Regex 模式：正则表达式提取（兜底）
    """

    JOURNAL_DOMAIN_HINTS = {
        "www.afm-journal.de": "Advanced Functional Materials",
        "afm-journal.de": "Advanced Functional Materials",
        "www.advmat.de": "Advanced Materials",
        "advmat.de": "Advanced Materials",
        "www.advopticalmat.de": "Advanced Optical Materials",
        "advopticalmat.de": "Advanced Optical Materials",
        "www.small-journal.com": "Small",
        "small-journal.com": "Small",
        "www.lpr-journal.org": "Laser & Photonics Reviews",
        "lpr-journal.org": "Laser & Photonics Reviews",
    }

    JOURNAL_TITLE_ALIASES = {
        "adv funct materials": "Advanced Functional Materials",
        "adv funct mater": "Advanced Functional Materials",
        "adv. funct. mater.": "Advanced Functional Materials",
        "adv. funct. materials": "Advanced Functional Materials",
        "advanced materials": "Advanced Materials",
        "adv materials": "Advanced Materials",
        "adv. mater.": "Advanced Materials",
        "advanced optical materials": "Advanced Optical Materials",
        "adv. opt. mater.": "Advanced Optical Materials",
        "adv opt mater": "Advanced Optical Materials",
        "laser & photonics reviews": "Laser & Photonics Reviews",
        "laser photonics reviews": "Laser & Photonics Reviews",
        "laser photonics review": "Laser & Photonics Reviews",
        "laser photon. rev.": "Laser & Photonics Reviews",
        "small": "Small",
        "nano lett.": "Nano Letters",
        "nano lett": "Nano Letters",
        "chem. mater.": "Chemistry of Materials",
        "chem. mater": "Chemistry of Materials",
        "j. am. chem. soc.": "Journal of the American Chemical Society",
        "j am chem soc": "Journal of the American Chemical Society",
        "nat. commun.": "Nature Communications",
        "nature communications": "Nature Communications",
        "nano res.": "Nano Research",
        "nano research": "Nano Research",
        "chemical engineering journal": "Chemical Engineering Journal",
        "chem eng j": "Chemical Engineering Journal",
        "chem eng j ": "Chemical Engineering Journal",
        "chem. eng. j.": "Chemical Engineering Journal",
        "journal of photochemistry photobiology c photochemistry reviews": "Journal of Photochemistry & Photobiology, C: Photochemistry Reviews",
        "journal of photochemistry and photobiology c photochemistry reviews": "Journal of Photochemistry & Photobiology, C: Photochemistry Reviews",
        "j photochem photobiol c photochem rev": "Journal of Photochemistry & Photobiology, C: Photochemistry Reviews",
        "j photochem photobiol c photochemistry reviews": "Journal of Photochemistry & Photobiology, C: Photochemistry Reviews",
    }

    JOURNAL_LINE_PATTERNS = [
        r"\bNature\s+(?:Communications|Photonics|Materials|Nanotechnology|Energy)\b",
        r"\bAdvanced\s+(?:Materials|Functional\s+Materials|Optical\s+Materials|Energy\s+Materials)\b",
        r"\bAdvanced Functional Materials\b",
        r"\bAdvanced Materials\b",
        r"\bAdvanced Optical Materials\b",
        r"\bLaser\s*(?:&|and)?\s*Photonics\s+Reviews\b",
        r"\bACS\s+(?:Nano|Applied\s+Materials|Energy\s+Letters|Photonics)\b",
        r"\bNano\s+(?:Letters|Today|Research|Energy)\b",
        r"\bJournal\s+of\s+the\s+American\s+Chemical\s+Society\b",
        r"\bScience\s+Advances\b",
        r"\bCell(?:\s+Reports)?\b",
        r"\bAngewandte\s+Chemie\b",
        r"\bChemical\s+Science\b",
        r"\bPhysical\s+Review\s+(?:Letters|Applied)\b",
    ]

    TITLE_STOP_PATTERNS = [
        r"^(?:abstract|a\s*b\s*s\s*t\s*r\s*a\s*c\s*t)\b",
        r"^(?:keywords?|key words?)\b",
        r"^(?:article info|a\s*r\s*t\s*i\s*c\s*l\s*e\s*i\s*n\s*f\s*o)\b",
        r"^(?:introduction|results(?: and discussion)?|experimental(?: section)?|materials?(?: and methods?)?)\b",
        r"^(?:received|accepted|published|available online|copyright)\b",
        r"^(?:doi|https?://|www\.)\b",
        r"^(?:corresponding author|e-?mail)\b",
    ]

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        use_llm: Optional[bool] = None,
    ):
        """
        初始化数据提取器

        Args:
            config: 配置字典，包含 LLM 配置等
        """
        if use_llm is not None:
            config = dict(config or {})
            config.setdefault("llm", {})
            config["llm"]["enabled"] = bool(use_llm)

        self.config = config or {}
        if "use_llm" in self.config:
            self.config.setdefault("llm", {})
            self.config["llm"]["enabled"] = bool(self.config["use_llm"])
        self.llm_config = self.config.get("llm", {})
        self.logger = setup_logger("paperinsight.extractor")

        # 初始化 LLM 客户端
        self.llm: Optional[BaseLLM] = None
        self.lite_backfill_llm: Optional[BaseLLM] = None
        self._init_llm_client()

    def _init_llm_client(self) -> None:
        """初始化 LLM 客户端"""
        if not self.llm_config.get("enabled", True):
            self.logger.info("[LLM] disabled; using regex fallback")
            return

        try:
            self.llm = create_llm_client(self.llm_config)
            provider = self.llm_config.get("provider", "unknown")
            self.lite_backfill_llm = self._init_lite_backfill_client()

            if self.llm:
                try:
                    available = self.llm.is_available()
                except Exception as e:
                    self.logger.warning(f"[LLM] connectivity check raised an error; will try extraction directly: {e}")
                    available = True

                if available:
                    self.logger.info(f"[LLM] client ready: {provider}")
                else:
                    self.logger.warning(f"[LLM] connectivity check failed for {provider}; extraction will still be attempted")
            else:
                self.logger.warning(f"[LLM] could not create client: {provider}")

        except Exception as e:
            self.logger.warning(f"[LLM] client initialization failed: {e}")
            self.llm = None
            self.lite_backfill_llm = None

    def _init_lite_backfill_client(self) -> Optional[BaseLLM]:
        provider = str(self.llm_config.get("provider", "")).lower()
        if provider != "longcat":
            return None

        longcat_config = self.llm_config.get("longcat", {})
        if not longcat_config.get("enable_lite_backfill", True):
            return None

        api_key = str(self.llm_config.get("api_key", "")).strip()
        if not api_key:
            return None

        lite_config = dict(self.llm_config)
        lite_longcat_config = dict(longcat_config)
        lite_longcat_config["model"] = lite_longcat_config.get("backfill_model", "LongCat-Flash-Lite")
        lite_config["longcat"] = lite_longcat_config

        try:
            client = create_llm_client(lite_config)
            if client:
                self.logger.info(f"[LLM] lite backfill model ready: {lite_longcat_config['model']}")
            return client
        except Exception as e:
            self.logger.warning(f"[LLM] lite backfill model init failed: {e}")
            return None

    def extract(
        self,
        markdown_text: str,
        cleaned_text: str,
        parse_result: Optional[ParseResult] = None,
    ) -> ExtractionResult:
        """
        提取论文结构化数据

        Args:
            markdown_text: 原始 Markdown 文本
            cleaned_text: 清洗后的文本（用于提取）
            parse_result: 解析结果（包含元数据）

        Returns:
            提取结果
        """
        start_time = time.time()

        # 优先使用 LLM 提取
        if self.llm:
            self.logger.info(f"[LLM] extracting structured data with {self.llm_config.get('provider', 'unknown')}")
            result = self._extract_with_llm(cleaned_text, parse_result)
            if result.success and result.data:
                result.processing_time = time.time() - start_time
                result.extraction_method = "llm"
                result.llm_model = self.llm_config.get("provider", "unknown")
                self.logger.info(f"[LLM] extraction succeeded: {result.llm_model}")
                return result
            self.logger.warning(f"[LLM] extraction failed; falling back to regex: {result.error_message}")

        # 回退到正则提取
        self.logger.info("[Regex] using regex fallback extraction")
        result = self._extract_with_regex(markdown_text, parse_result)
        result.processing_time = time.time() - start_time
        result.extraction_method = "regex"

        return result

    def _extract_with_llm(
        self,
        text: str,
        parse_result: Optional[ParseResult],
    ) -> ExtractionResult:
        """使用 LLM 提取"""
        try:
            prepared_text = self._prepare_llm_input(text)

            # 构建 Prompt
            prompt = format_extraction_prompt_v3(prepared_text)

            # 调用 LLM
            self.logger.info(f"[LLM] sending request with text length {len(prepared_text)} chars")
            llm_kwargs: Dict[str, Any] = {}
            if self._supports_strict_schema():
                llm_kwargs.update(
                    {
                        "json_schema": PAPER_DATA_JSON_SCHEMA,
                        "schema_name": "paperinsight_paper_data",
                    }
                )
            response = self.llm.generate_json(prompt, temperature=0.2, **llm_kwargs)

            # 解析并校验
            paper_data = self._parse_and_validate(response)

            if paper_data:
                paper_data = self._backfill_paper_info_from_text(paper_data, prepared_text, parse_result)
                paper_data = self._merge_inferred_devices(paper_data, prepared_text)
                paper_data = self._sanitize_devices(paper_data)
                paper_data = self._ensure_bilingual_text_fields(paper_data)
                return ExtractionResult(
                    success=True,
                    data=paper_data,
                    source_file=parse_result.source_file if parse_result else None,
                )
            else:
                return ExtractionResult(
                    success=False,
                    error_message="LLM response validation failed",
                )

        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"LLM extraction failed: {str(e)}",
            )

    def _ensure_bilingual_text_fields(self, paper_data: PaperData) -> PaperData:
        """对标题之后的自然语言字段补齐中英对照。"""
        output_config = self.config.get("output", {})
        if not output_config.get("bilingual_text", True):
            return paper_data

        if not self.llm:
            return paper_data

        try:
            self.logger.info("[LLM] running bilingual post-processing")
            prompt = format_bilingual_postprocess_prompt(paper_data.model_dump())
            llm_kwargs: Dict[str, Any] = {}
            if self._supports_strict_schema():
                llm_kwargs.update(
                    {
                        "json_schema": PAPER_DATA_JSON_SCHEMA,
                        "schema_name": "paperinsight_bilingual_paper_data",
                    }
                )
            response = self.llm.generate_json(prompt, temperature=0.1, **llm_kwargs)
            bilingual_data = self._parse_and_validate(response)

            if bilingual_data:
                self.logger.info("[LLM] bilingual post-processing complete")
                return bilingual_data

            self.logger.warning("[LLM] bilingual post-processing validation failed; keeping initial extraction")
            return paper_data

        except Exception as e:
            self.logger.warning(f"[LLM] bilingual post-processing failed; keeping initial extraction: {e}")
            return paper_data

    def _supports_strict_schema(self) -> bool:
        provider = self.llm_config.get("provider", "").lower()
        return provider == "openai"

    def _prepare_llm_input(self, text: str) -> str:
        """准备 LLM 输入，优先相信 cleaner 的预算控制，仅在极端情况下兜底截断。"""
        if not text:
            return ""

        max_chars = (
            self.config.get("cleaner", {}).get("max_input_chars")
            or self.llm_config.get("max_input_chars")
            or 0
        )
        if not max_chars or len(text) <= max_chars:
            return text

        self.logger.warning(
            f"[LLM] cleaned text still exceeds budget; truncating at boundary: {len(text)} -> {max_chars}"
        )
        truncated = text[:max_chars]
        boundary = max(truncated.rfind("\n\n"), truncated.rfind("\n### "), truncated.rfind("\n## "))
        if boundary > max_chars * 0.6:
            return truncated[:boundary].strip()
        return truncated.strip()

    def _parse_and_validate(self, response: Dict[str, Any]) -> Optional[PaperData]:
        """解析并校验 LLM 响应"""
        try:
            # 构建嵌套结构
            paper_info_data = response.get("paper_info", {})
            devices_data = response.get("devices", [])
            data_source_data = response.get("data_source", {})
            optimization_data = response.get("optimization", {})
            raw_journal_title = paper_info_data.get("raw_journal_title")
            matched_journal_title = paper_info_data.get("matched_journal_title")

            # 构建 PaperInfo
            paper_info = PaperInfo(
                title=paper_info_data.get("title"),
                authors=paper_info_data.get("authors"),
                journal_name=paper_info_data.get("journal_name") or matched_journal_title or raw_journal_title,
                raw_journal_title=raw_journal_title,
                raw_issn=paper_info_data.get("raw_issn"),
                raw_eissn=paper_info_data.get("raw_eissn"),
                matched_journal_title=matched_journal_title,
                matched_issn=paper_info_data.get("matched_issn"),
                match_method=paper_info_data.get("match_method"),
                journal_profile_url=paper_info_data.get("journal_profile_url"),
                impact_factor=paper_info_data.get("impact_factor"),
                impact_factor_year=paper_info_data.get("impact_factor_year"),
                impact_factor_source=paper_info_data.get("impact_factor_source"),
                impact_factor_status=paper_info_data.get("impact_factor_status"),
                year=paper_info_data.get("year"),
                optimization_strategy=paper_info_data.get("optimization_strategy"),
                best_eqe=paper_info_data.get("best_eqe"),
                research_type=paper_info_data.get("research_type"),
                emitter_type=paper_info_data.get("emitter_type"),
            )

            # 构建 Devices 列表
            devices = []
            for device_data in devices_data:
                if isinstance(device_data, dict):
                    device = DeviceData(
                        device_label=device_data.get("device_label"),
                        structure=device_data.get("structure"),
                        eqe=device_data.get("eqe"),
                        cie=device_data.get("cie"),
                        lifetime=device_data.get("lifetime"),
                        luminance=device_data.get("luminance"),
                        current_efficiency=device_data.get("current_efficiency"),
                        power_efficiency=device_data.get("power_efficiency"),
                        notes=device_data.get("notes"),
                    )
                    devices.append(device)

            # 构建 DataSourceReference
            data_source = DataSourceReference(
                eqe_source=data_source_data.get("eqe_source"),
                cie_source=data_source_data.get("cie_source"),
                lifetime_source=data_source_data.get("lifetime_source"),
                structure_source=data_source_data.get("structure_source"),
            )

            # 构建 OptimizationInfo
            optimization = None
            if optimization_data:
                optimization = OptimizationInfo(
                    level=optimization_data.get("level"),
                    strategy=optimization_data.get("strategy"),
                    key_findings=optimization_data.get("key_findings"),
                )

            # 构建完整的 PaperData
            paper_data = PaperData(
                paper_info=paper_info,
                devices=devices,
                data_source=data_source,
                optimization=optimization,
            )
            paper_data = self._sanitize_devices(paper_data)

            return paper_data

        except ValidationError as e:
            self.logger.warning(f"[ValidationFailed] {e}")
            return None
        except Exception as e:
            self.logger.warning(f"[ParseFailed] {e}")
            return None

    def _extract_with_regex(
        self,
        text: str,
        parse_result: Optional[ParseResult],
    ) -> ExtractionResult:
        """使用正则表达式提取（兜底方案）"""
        try:
            # 提取基本信息
            raw_journal_title, raw_issn, raw_eissn = self._extract_raw_journal_metadata(text, parse_result)
            paper_info = PaperInfo(
                title=self._extract_title(text, parse_result),
                authors=self._extract_authors(text, parse_result),
                journal_name=raw_journal_title,
                raw_journal_title=raw_journal_title,
                raw_issn=raw_issn,
                raw_eissn=raw_eissn,
                impact_factor=self._extract_impact_factor(text),
                year=self._extract_year(text),
                research_type=self._detect_research_type(text),
                emitter_type=self._detect_emitter_type(text),
            )

            # 提取器件数据
            devices = self._extract_devices(text)

            # 提取数据溯源
            data_source = DataSourceReference(
                eqe_source=self._extract_metric_source(text, "eqe"),
                cie_source=self._extract_metric_source(text, "cie"),
                lifetime_source=self._extract_metric_source(text, "lifetime"),
                structure_source=self._extract_metric_source(text, "structure"),
            )

            # 提取优化信息
            optimization = OptimizationInfo(
                level=self._extract_optimization_level(text),
                strategy=self._extract_optimization_strategy(text),
            )

            # 构建 PaperData
            paper_data = PaperData(
                paper_info=paper_info,
                devices=devices,
                data_source=data_source,
                optimization=optimization,
            )
            paper_data = self._backfill_paper_info_from_text(paper_data, text, parse_result)
            paper_data = self._merge_inferred_devices(paper_data, text)
            paper_data = self._sanitize_devices(paper_data)

            return ExtractionResult(
                success=True,
                data=paper_data,
                source_file=parse_result.source_file if parse_result else None,
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"Regex extraction failed: {str(e)}",
            )

    def _backfill_paper_info_from_text(
        self,
        paper_data: PaperData,
        text: str,
        parse_result: Optional[ParseResult],
    ) -> PaperData:
        paper_info = paper_data.paper_info
        raw_journal_title, raw_issn, raw_eissn = self._extract_raw_journal_metadata(text, parse_result)
        extracted_title = self._extract_title(text, parse_result)

        normalized_existing_title = self._normalize_title_candidate(paper_info.title)
        if extracted_title and (
            not normalized_existing_title or self._is_bad_title_candidate(normalized_existing_title)
        ):
            paper_info.title = extracted_title
        elif normalized_existing_title and normalized_existing_title != paper_info.title:
            paper_info.title = normalized_existing_title

        if raw_journal_title and not paper_info.raw_journal_title:
            paper_info.raw_journal_title = raw_journal_title
        if raw_journal_title and not paper_info.journal_name:
            paper_info.journal_name = raw_journal_title
        if raw_issn and not paper_info.raw_issn:
            paper_info.raw_issn = raw_issn
        if raw_eissn and not paper_info.raw_eissn:
            paper_info.raw_eissn = raw_eissn
        if paper_info.impact_factor in (None, 0):
            extracted_if = self._extract_impact_factor(text)
            if extracted_if:
                paper_info.impact_factor = extracted_if
        return paper_data

    def lite_backfill_paper_info(
        self,
        paper_data: PaperData,
        text: str,
        parse_result: Optional[ParseResult],
    ) -> PaperData:
        if not self.lite_backfill_llm:
            return paper_data

        if not self._needs_lite_backfill(paper_data):
            return paper_data

        try:
            snippet = self._prepare_lite_backfill_input(text)
            prompt = format_lite_paper_info_backfill_prompt(
                paper_text=snippet,
                source_file=parse_result.source_file if parse_result else None,
                metadata=parse_result.metadata if parse_result else {},
            )
            response = self.lite_backfill_llm.generate_json(prompt, temperature=0.1)
            self.logger.info(
                "[LLM] lite backfill response: "
                f"title={bool(response.get('title'))}, "
                f"authors={bool(response.get('authors'))}, "
                f"journal_name={bool(response.get('journal_name'))}, "
                f"raw_journal_title={bool(response.get('raw_journal_title'))}, "
                f"year={response.get('year')!r}"
            )
            self._merge_lite_backfill_result(paper_data, response)
            return self._backfill_paper_info_from_text(paper_data, text, parse_result)
        except Exception as e:
            self.logger.warning(f"[LLM] lite backfill failed: {e}")
            return paper_data

    def _needs_lite_backfill(self, paper_data: PaperData) -> bool:
        paper_info = paper_data.paper_info
        return not all(
            [
                paper_info.title,
                paper_info.journal_name or paper_info.raw_journal_title,
                paper_info.year,
            ]
        )

    def _prepare_lite_backfill_input(self, text: str) -> str:
        if not text:
            return ""
        max_chars = 6000
        snippet = text[:max_chars].strip()
        boundary = max(snippet.rfind("\n\n"), snippet.rfind(". "), snippet.rfind("\n"))
        if boundary > max_chars * 0.6:
            return snippet[:boundary].strip()
        return snippet

    def _merge_lite_backfill_result(self, paper_data: PaperData, response: Dict[str, Any]) -> None:
        paper_info = paper_data.paper_info
        title = self._coerce_metadata_value(response.get("title"))
        authors = self._coerce_metadata_value(response.get("authors"))
        journal_name = self._normalize_journal_title_candidate(
            self._coerce_metadata_value(response.get("journal_name"))
        )
        raw_journal_title = self._normalize_journal_title_candidate(
            self._coerce_metadata_value(response.get("raw_journal_title"))
        )
        year_value = response.get("year")

        if title and not paper_info.title:
            paper_info.title = title
        if authors and not paper_info.authors:
            paper_info.authors = authors
        if raw_journal_title and not paper_info.raw_journal_title:
            paper_info.raw_journal_title = raw_journal_title
        if journal_name and not paper_info.journal_name:
            paper_info.journal_name = journal_name
        if year_value not in (None, "") and not paper_info.year:
            try:
                year = int(year_value)
            except (TypeError, ValueError):
                year = None
            if year and 1900 <= year <= 2100:
                paper_info.year = year

        self.logger.info(
            "[LLM] lite backfill merged: "
            f"title={bool(paper_info.title)}, "
            f"authors={bool(paper_info.authors)}, "
            f"journal={paper_info.journal_name or paper_info.raw_journal_title!r}, "
            f"year={paper_info.year!r}"
        )

    # ============== 正则提取方法 ==============

    def _extract_title(self, text: str, parse_result: Optional[ParseResult]) -> Optional[str]:
        """提取论文标题"""
        # 1. 优先从PDF元数据提取（增强优先级）
        if parse_result:
            # 直接从PDF元数据提取
            source_metadata = self._extract_pdf_metadata_from_source(parse_result)
            pdf_title = self._coerce_metadata_value(source_metadata.get("title"))
            if pdf_title:
                normalized = self._normalize_title_candidate(pdf_title)
                if normalized and not self._is_bad_title_candidate(normalized):
                    return normalized
            
            # 从parse_result.metadata提取
            metadata_candidates = []
            metadata_candidates.extend(
                filter(
                    None,
                    [
                        self._coerce_metadata_value(parse_result.metadata.get("title")),
                        self._coerce_metadata_value(parse_result.metadata.get("dc:title")),
                        self._coerce_metadata_value(source_metadata.get("subject")),
                    ],
                )
            )

            for candidate in metadata_candidates:
                normalized = self._normalize_title_candidate(candidate)
                if normalized and not self._is_bad_title_candidate(normalized):
                    return normalized

        # 2. ScienceDirect格式特殊处理
        sciencedirect_title = self._extract_sciencedirect_title(text)
        if sciencedirect_title:
            return sciencedirect_title

        # 3. 从文本行提取
        line_candidates = self._extract_title_candidates_from_lines(parse_result, text)
        if line_candidates:
            return line_candidates[0]

        return None

    def _extract_title_candidates_from_lines(
        self,
        parse_result: Optional[ParseResult],
        text: str,
    ) -> List[str]:
        line_sources: List[str] = []
        if parse_result and parse_result.markdown:
            line_sources.append(parse_result.markdown)
        if parse_result and parse_result.raw_text:
            line_sources.append(parse_result.raw_text)
        if text:
            line_sources.append(text)

        candidates: List[tuple[int, str]] = []
        seen: set[str] = set()

        for source in line_sources:
            lines = source.splitlines()[:40]
            filtered = [self._normalize_title_candidate(line) for line in lines]
            filtered = [line for line in filtered if line]

            for index, line in enumerate(filtered[:20]):
                if self._is_bad_title_candidate(line):
                    continue
                score = self._score_title_candidate(line, index=index, heading_hint=lines[index].lstrip().startswith("#") if index < len(lines) else False)
                if score <= 0 or line in seen:
                    continue
                seen.add(line)
                candidates.append((score, line))

            for block in self._build_title_blocks(filtered[:8]):
                if block in seen or self._is_bad_title_candidate(block):
                    continue
                score = self._score_title_candidate(block, index=0, heading_hint=True) + 2
                if score > 0:
                    seen.add(block)
                    candidates.append((score, block))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in candidates]

    def _build_title_blocks(self, lines: List[str]) -> List[str]:
        blocks: List[str] = []
        current: List[str] = []

        for line in lines:
            if self._is_bad_title_candidate(line):
                if current:
                    break
                continue
            if len(current) >= 3:
                break
            current.append(line)
            joined = " ".join(current).strip()
            if 20 <= len(joined) <= 260:
                blocks.append(joined)
        return blocks

    def _normalize_title_candidate(self, value: Optional[str]) -> Optional[str]:
        if value in (None, ""):
            return None

        candidate = str(value).strip()
        candidate = re.sub(r"^[#*\-\s]+", "", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip(" \"'`|")
        candidate = re.sub(r"^(?:title|article title)\s*[:\-]\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*\[[^\]]+\]\s*$", "", candidate).strip()
        candidate = re.sub(r"\s*\(\s*(?:article|review|communication)\s*\)\s*$", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"\s*doi\s*:\s*10\.\S+$", "", candidate, flags=re.IGNORECASE).strip(" ,.;")
        candidate = re.sub(r"\s*[•·]\s*$", "", candidate).strip()
        return candidate or None

    def _is_bad_title_candidate(self, candidate: str) -> bool:
        lowered = candidate.lower().strip()
        if not lowered:
            return True
        if len(candidate) < 15 or len(candidate) > 300:
            return True
        if any(re.match(pattern, lowered, re.IGNORECASE) for pattern in self.TITLE_STOP_PATTERNS):
            return True
        if "@" in candidate or "http" in lowered or "www." in lowered:
            return True
        if lowered.endswith(".pdf"):
            return True
        if re.fullmatch(r"[a-z]\s*(?:[a-z]\s*){4,}", lowered):
            return True
        if re.search(r"\b(?:university|college|institute|school|laboratory|department)\b", lowered):
            return True
        if re.fullmatch(
            r"(?:[A-Z][a-zA-Z'`-]+(?:\s+[A-Z][a-zA-Z'`-]+){0,2}\s*[,*]?\s*){3,}",
            candidate,
        ):
            return True
        if candidate.count(",") >= 3 and not re.search(r"[:;]", candidate):
            return True
        if re.search(r"\b(?:figure|table)\s+\d+\b", lowered):
            return True
        if re.search(r"\b(?:orcid|supporting information)\b", lowered):
            return True
        if re.search(r"\b(?:j\.\s*[a-z]|adv\.|nano lett\.|chem\.)\b", lowered) and len(candidate.split()) <= 6:
            return True
        if sum(ch.isdigit() for ch in candidate) > max(4, len(candidate) // 8):
            return True
        return False

    def _score_title_candidate(self, candidate: str, *, index: int, heading_hint: bool) -> int:
        score = 0
        word_count = len(candidate.split())
        alpha_count = sum(ch.isalpha() for ch in candidate)
        upper_ratio = sum(ch.isupper() for ch in candidate if ch.isalpha()) / max(alpha_count, 1)

        if heading_hint:
            score += 5
        if index == 0:
            score += 4
        elif index <= 2:
            score += 2

        if 6 <= word_count <= 28:
            score += 4
        if 40 <= len(candidate) <= 180:
            score += 4
        if alpha_count >= max(20, len(candidate) * 0.45):
            score += 3
        if upper_ratio < 0.45:
            score += 2
        if ":" in candidate:
            score += 1
        if candidate.endswith("."):
            score -= 2

        return score

    def _extract_sciencedirect_title(self, text: str) -> Optional[str]:
        """提取ScienceDirect格式论文的标题"""
        # ScienceDirect论文通常有特定格式，标题可能在特定位置
        # 1. 查找包含 ScienceDirect 特征的模式
        sciencedirect_patterns = [
            r'\bScienceDirect\b',
            r'\bElsevier\b',
            r'1-s2\.0-',  # ScienceDirect文件格式
        ]
        
        # 检查是否是ScienceDirect论文
        is_sciencedirect = any(pattern in text[:10000] for pattern in sciencedirect_patterns)
        if not is_sciencedirect:
            return None
        
        # 2. 尝试从文本中提取标题
        # 常见的ScienceDirect标题格式：标题通常在文档开头，可能有特殊标记
        lines = text.split('\n')
        
        # 寻找可能的标题行
        for i, line in enumerate(lines[:50]):  # 检查前50行
            line = line.strip()
            if not line:
                continue
            
            # 标题通常长度适中，首字母大写，不含数字和特殊符号
            if (20 <= len(line) <= 200 and 
                line[0].isupper() and 
                not line.startswith('Abstract') and
                not line.startswith('Keywords') and
                not line.startswith('Received') and
                not line.startswith('Accepted') and
                not line.startswith('Published') and
                not '@' in line and
                not 'www.' in line and
                not 'http' in line):
                
                # 检查下一行是否是作者行（通常包含逗号和多个名字）
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and (',' in next_line or 'and' in next_line):
                        normalized = self._normalize_title_candidate(line)
                        if normalized and not self._is_bad_title_candidate(normalized):
                            return normalized
        
        return None

    def _extract_sciencedirect_authors(self, text: str) -> Optional[str]:
        """提取ScienceDirect格式论文的作者"""
        # 1. 检查是否是ScienceDirect论文
        sciencedirect_patterns = [
            r'\bScienceDirect\b',
            r'\bElsevier\b',
            r'1-s2\.0-',
        ]
        
        is_sciencedirect = any(pattern in text[:10000] for pattern in sciencedirect_patterns)
        if not is_sciencedirect:
            return None
        
        # 2. 寻找作者行
        lines = text.split('\n')
        
        for i, line in enumerate(lines[:60]):  # 检查前60行
            line = line.strip()
            if not line:
                continue
            
            # 作者行通常包含多个名字，用逗号或and分隔
            # 检查是否包含多个大写字母开头的单词（可能是名字）
            words = line.split()
            capital_words = [word for word in words if word[0].isupper() and len(word) > 1]
            
            # 作者行特征：包含多个名字，可能有逗号，可能有and
            if (len(capital_words) >= 2 and 
                (',' in line or 'and' in line.lower()) and
                not line.startswith('Abstract') and
                not line.startswith('Keywords') and
                not line.startswith('Received') and
                not line.startswith('Accepted') and
                not line.startswith('Published') and
                not '@' in line and
                not 'www.' in line):
                
                # 提取作者名字
                # 简单处理：提取所有大写开头的单词组合
                authors = []
                current_author = []
                
                for word in words:
                    if word[0].isupper() and len(word) > 1:
                        current_author.append(word)
                    elif current_author:
                        authors.append(' '.join(current_author))
                        current_author = []
                
                if current_author:
                    authors.append(' '.join(current_author))
                
                # 过滤掉可能不是名字的词
                filtered_authors = [author for author in authors if len(author.split()) >= 2]
                
                if filtered_authors:
                    return ", ".join(filtered_authors[:10])
        
        return None

    def _extract_authors(self, text: str, parse_result: Optional[ParseResult]) -> Optional[str]:
        """提取作者"""
        # 1. 优先从PDF元数据提取
        if parse_result:
            source_metadata = self._extract_pdf_metadata_from_source(parse_result)
            pdf_authors = self._coerce_metadata_value(source_metadata.get("author"))
            if pdf_authors:
                parts = [p.strip() for p in re.split(r"[;,\n]+", pdf_authors) if p.strip()]
                return ", ".join(parts[:10])
        
        # 2. 从parse_result.metadata提取
        if parse_result and parse_result.metadata.get("author"):
            authors = parse_result.metadata["author"]
            parts = [p.strip() for p in re.split(r"[;,\n]+", authors) if p.strip()]
            return ", ".join(parts[:10])  # 限制作者数量

        # 3. ScienceDirect格式特殊处理
        sciencedirect_authors = self._extract_sciencedirect_authors(text)
        if sciencedirect_authors:
            return sciencedirect_authors

        # 4. 正则匹配
        name_pattern = r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'
        matches = re.findall(name_pattern, text[:5000])

        if matches:
            unique_names = list(dict.fromkeys(matches))[:10]
            return ", ".join(unique_names)

        return None

    def _extract_raw_journal_metadata(
        self,
        text: str,
        parse_result: Optional[ParseResult],
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """提取期刊原始标题、ISSN 和 eISSN。"""
        metadata = dict(parse_result.metadata) if parse_result else {}
        source_metadata = self._extract_pdf_metadata_from_source(parse_result)
        for key, value in source_metadata.items():
            metadata.setdefault(key, value)

        raw_journal_title = self._first_non_empty(
            self._normalize_journal_title_candidate(self._coerce_metadata_value(metadata.get("journal_name"))),
            self._normalize_journal_title_candidate(self._coerce_metadata_value(metadata.get("journal"))),
            self._normalize_journal_title_candidate(self._coerce_metadata_value(metadata.get("publication_name"))),
            self._normalize_journal_title_candidate(self._coerce_metadata_value(metadata.get("publication_title"))),
            self._normalize_journal_title_candidate(self._coerce_metadata_value(metadata.get("container_title"))),
            self._extract_journal_name_from_subject(metadata),
            self._extract_journal_name_from_filename(parse_result),
            self._extract_journal_name(text),
        )

        raw_issn = self._first_non_empty(
            self._coerce_metadata_value(metadata.get("issn")),
            self._coerce_metadata_value(metadata.get("print_issn")),
            self._coerce_metadata_value(metadata.get("pissn")),
            self._coerce_metadata_value(metadata.get("issn_print")),
        )
        raw_eissn = self._first_non_empty(
            self._coerce_metadata_value(metadata.get("eissn")),
            self._coerce_metadata_value(metadata.get("electronic_issn")),
            self._coerce_metadata_value(metadata.get("online_issn")),
            self._coerce_metadata_value(metadata.get("issn_electronic")),
        )

        text_issn, text_eissn = self._extract_issn_from_text(text)
        return raw_journal_title, raw_issn or text_issn, raw_eissn or text_eissn

    def _extract_pdf_metadata_from_source(self, parse_result: Optional[ParseResult]) -> Dict[str, Any]:
        if not parse_result or not parse_result.source_file:
            return {}

        try:
            with PDFProcessor(parse_result.source_file) as processor:
                return processor._extract_metadata(processor._open())
        except Exception:
            return {}

    def _extract_issn_from_text(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """从文章前部文本提取 ISSN/eISSN。"""
        head_text = text[:5000]
        issn_pattern = r"(\d{4}-?\d{3}[\dXx])"

        eissn_match = re.search(
            rf"\b(?:e-?issn|electronic\s+issn|online\s+issn)\b[^0-9A-Za-z]{{0,10}}{issn_pattern}",
            head_text,
            re.IGNORECASE,
        )
        issn_match = re.search(
            rf"\b(?:p-?issn|print\s+issn|issn\s*\(print\)|issn)\b[^0-9A-Za-z]{{0,10}}{issn_pattern}",
            head_text,
            re.IGNORECASE,
        )

        generic_matches = re.findall(r"\b\d{4}-?\d{3}[\dXx]\b", head_text)
        raw_issn = issn_match.group(1) if issn_match else None
        raw_eissn = eissn_match.group(1) if eissn_match else None

        if not raw_issn and generic_matches:
            raw_issn = generic_matches[0]
        if not raw_eissn and len(generic_matches) > 1:
            for candidate in generic_matches:
                if candidate != raw_issn:
                    raw_eissn = candidate
                    break

        return raw_issn, raw_eissn

    @staticmethod
    def _coerce_metadata_value(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, (list, tuple)):
            for item in value:
                coerced = DataExtractor._coerce_metadata_value(item)
                if coerced:
                    return coerced
            return None
        return str(value).strip() or None

    @staticmethod
    def _first_non_empty(*values: Optional[str]) -> Optional[str]:
        for value in values:
            if value not in (None, ""):
                return value
        return None

    def _extract_journal_name(self, text: str) -> Optional[str]:
        """提取期刊名称"""
        head_text = text[:5000]
        head_lower = head_text.lower()

        for domain, journal_name in self.JOURNAL_DOMAIN_HINTS.items():
            if domain in head_lower:
                return journal_name

        candidate_lines = []
        for line in head_text.splitlines():
            cleaned = re.sub(r"\s+", " ", line).strip()
            if cleaned:
                candidate_lines.append(cleaned)

        for line in candidate_lines[:40]:
            normalized_line = self._normalize_journal_title_candidate(line)
            if normalized_line:
                return normalized_line

            for pattern in self.JOURNAL_LINE_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    normalized_match = self._normalize_journal_title_candidate(match.group(0))
                    if normalized_match:
                        return normalized_match

        return None

    def _extract_journal_name_from_subject(self, metadata: Dict[str, Any]) -> Optional[str]:
        subject = self._coerce_metadata_value(metadata.get("subject"))
        if not subject:
            return None

        normalized_subject = re.sub(r"\s+", " ", subject).strip()
        normalized_subject = re.sub(r"\bdoi\s*:\s*10\.\S+$", "", normalized_subject, flags=re.IGNORECASE).strip(" ,.;")

        subject_candidates = [normalized_subject]
        volume_patterns = [
            r"^(.+?)(?:,\s*\d+\s*\((?:19|20)\d{2}\).*)$",
            r"^(.+?)(?:\s+\d+\s*\((?:19|20)\d{2}\).*)$",
            r"^(.+?)(?:\s+(?:19|20)\d{2}[,.:; ].*)$",
            r"^(.+?)(?:\s+(?:19|20)\d{2}\.\d+.*)$",
        ]
        for pattern in volume_patterns:
            match = re.match(pattern, normalized_subject, re.IGNORECASE)
            if match:
                subject_candidates.insert(0, match.group(1).strip(" ,.;"))

        for candidate_text in subject_candidates:
            candidate = self._normalize_journal_title_candidate(candidate_text)
            if candidate:
                return candidate

        return None

    def _extract_journal_name_from_filename(
        self,
        parse_result: Optional[ParseResult],
    ) -> Optional[str]:
        if not parse_result or not parse_result.source_file:
            return None

        filename = str(parse_result.source_file).split("/")[-1].split("\\")[-1]
        filename = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)

        candidates = [filename]
        split_candidates = re.split(r"\s+-\s+", filename)
        if split_candidates:
            candidates.append(split_candidates[0])
            if len(split_candidates) >= 2:
                candidates.append(" - ".join(split_candidates[:2]))

        for candidate in candidates:
            normalized = self._normalize_journal_title_candidate(candidate)
            if normalized:
                return normalized

        return None

    def _normalize_journal_title_candidate(self, value: Optional[str]) -> Optional[str]:
        if value in (None, ""):
            return None

        candidate = re.sub(r"\s+", " ", str(value)).strip()
        candidate = re.sub(r"^(?:cite\s+this|available\s+online)\b[:\s-]*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"^(?:review|research article|article)\b[:\s-]*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\bdoi\s*:\s*10\.\S+$", "", candidate, flags=re.IGNORECASE).strip(" -|,;.")
        candidate = re.sub(r"\bwww\.[^\s]+", "", candidate, flags=re.IGNORECASE).strip(" -|,;")
        candidate = re.sub(r"\(\d+\)$", "", candidate).strip()
        candidate = re.sub(r"\b(19|20)\d{2}\b.*$", "", candidate).strip(" -|,;")
        candidate = re.sub(r"^[0-9A-Za-z_.-]+-main(?:\s*\(\d+\))?$", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"\s*\([^)]*\)$", "", candidate).strip(" -|,;.")

        lower_candidate = candidate.lower()
        if any(token in lower_candidate for token in ("university of science", "school of materials science")):
            return None

        alias = self.JOURNAL_TITLE_ALIASES.get(lower_candidate)
        if alias:
            return alias

        simplified_candidate = re.sub(r"[^a-z0-9]+", " ", lower_candidate).strip()
        alias = self.JOURNAL_TITLE_ALIASES.get(simplified_candidate)
        if alias:
            return alias

        for pattern in self.JOURNAL_LINE_PATTERNS:
            full_match = re.fullmatch(pattern, candidate, re.IGNORECASE)
            if full_match:
                return full_match.group(0)

        return None

    def _extract_impact_factor(self, text: str) -> Optional[float]:
        """提取影响因子"""
        patterns = [
            r'impact\s+factor[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)',
            r'\bIF[^0-9]{0,10}([0-9]+(?:\.[0-9]+)?)\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    if 0.1 < value < 200:
                        return value
                except ValueError:
                    continue

        return None

    def _extract_year(self, text: str) -> Optional[int]:
        """提取发表年份"""
        # 查找年份模式
        patterns = [
            # 从出版信息中提取
            r'(?:published|accepted|received|online|available)[^0-9]{0,20}(20[1-2][0-9])',
            # 从版权信息中提取
            r'©?\s*(20[1-2][0-9])\s+(?:The\s+Author|Elsevier|Nature|Science|Wiley|Springer|ACS|Taylor\s+&\s+Francis)',
            # 从标题中提取（例如：2024, 2023等）
            r'\b(20[1-2][0-9])\b',
            # 从卷号/期号中提取（例如：Vol. 123, 2024）
            r'\b(?:vol|volume|issue|no)\.?\s*\d+[^0-9]{0,10}(20[1-2][0-9])',
            # 从DOI中提取
            r'\b10\.\S+/(?:20[1-2][0-9])\b',
            # 从引用格式中提取
            r'\b(20[1-2][0-9])\b[^0-9]{0,20}(?:doi|pmid|arxiv)',
        ]

        # 存储所有找到的年份候选
        year_candidates = []

        # 搜索文本的不同部分
        search_sections = [
            text[:3000],  # 开头部分
            text[-3000:],  # 结尾部分
        ]

        for section in search_sections:
            for pattern in patterns:
                matches = re.findall(pattern, section, re.IGNORECASE)
                for match in matches:
                    try:
                        year = int(match)
                        # 验证年份的合理性（2010-2026）
                        if 2010 <= year <= 2026:
                            year_candidates.append(year)
                    except ValueError:
                        continue

        # 如果有多个候选年份，选择最常见的那个
        if year_candidates:
            # 统计每个年份的出现次数
            year_counts = {}
            for year in year_candidates:
                year_counts[year] = year_counts.get(year, 0) + 1
            # 按出现次数排序
            sorted_years = sorted(year_counts.items(), key=lambda x: x[1], reverse=True)
            # 返回出现次数最多的年份
            return sorted_years[0][0]

        return None

    def _detect_research_type(self, text: str) -> Optional[str]:
        """检测研究类型"""
        types = {
            "OLED": [r'\bOLED\b', r'organic\s+light.emitting\s+diode'],
            "PLED": [r'\bPLED\b', r'polymer\s+light.emitting\s+diode'],
            "QLED": [r'\bQLED\b', r'quantum\s+dot\s+LED'],
            "PeLED": [r'\bPeLED\b', r'perovskite\s+LED'],
            "LED": [r'\bLED\b', r'light.emitting\s+diode'],
        }

        text_lower = text.lower()
        for rtype, patterns in types.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return rtype

        return None

    def _detect_emitter_type(self, text: str) -> Optional[str]:
        """检测发光材料类型"""
        types = {
            "TADF": [r'\bTADF\b', r'thermally\s+activated\s+delayed\s+fluorescence'],
            "Phosphorescent": [r'phosphorescen', r'\bIr\([^)]+\)', r'\bPt\([^)]+\)'],
            "Fluorescent": [r'\bfluorescen(?!\s+delayed)', r'traditional\s+fluorescen'],
            "Perovskite": [r'perovskite', r'\bCsPb[^,]*,', r'\bMAPb'],
        }

        text_lower = text.lower()
        for etype, patterns in types.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return etype

        return None

    def _extract_devices(self, text: str) -> List[DeviceData]:
        """提取器件数据"""
        candidate_devices = self._extract_candidate_devices(text)
        if candidate_devices:
            return candidate_devices

        structures = self._extract_all_structures(text)
        eqes = self._extract_all_eqe(text)
        cies = self._extract_all_cie(text)
        lifetimes = self._extract_all_lifetime(text)

        if structures or eqes or cies or lifetimes:
            return [
                DeviceData(
                    structure=structures[0] if structures else None,
                    eqe=eqes[0] if eqes else None,
                    cie=cies[0] if cies else None,
                    lifetime=lifetimes[0] if lifetimes else None,
                )
            ]

        return []

    def _extract_candidate_devices(self, text: str) -> List[DeviceData]:
        """按段落/候选片段提取多器件信息。"""
        segments = self._build_device_segments(text)
        devices: List[DeviceData] = []
        seen_signatures: set[tuple] = set()

        for segment in segments:
            structure = self._extract_first_structure(segment)
            eqe = self._extract_first_eqe(segment)
            cie = self._extract_first_cie(segment)
            lifetime = self._extract_first_lifetime(segment)
            luminance = self._extract_first_luminance(segment)
            current_efficiency = self._extract_first_current_efficiency(segment)
            power_efficiency = self._extract_first_power_efficiency(segment)
            label = self._extract_device_label(segment)

            # 降低信号阈值：只要有任何一个关键参数就认为是器件信息
            has_signal = bool(structure or eqe or cie or lifetime or luminance or current_efficiency or power_efficiency)
            if not has_signal:
                continue

            signature = (label or "", structure or "", eqe or "", cie or "", lifetime or "")
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            devices.append(
                DeviceData(
                    device_label=label,
                    structure=structure,
                    eqe=eqe,
                    cie=cie,
                    lifetime=lifetime,
                    luminance=luminance,
                    current_efficiency=current_efficiency,
                    power_efficiency=power_efficiency,
                    notes=self._clean_device_notes(segment),
                )
            )

        return devices[:6]

    def _build_device_segments(self, text: str) -> List[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        segments: List[str] = []

        for paragraph in paragraphs:
            if self._segment_signal_score(paragraph) >= 2:
                segments.append(paragraph)

        sentence_chunks = re.split(r"(?<=[.!?])\s+", text)
        window: List[str] = []
        for sentence in sentence_chunks:
            sentence = sentence.strip()
            if not sentence:
                continue
            if self._segment_signal_score(sentence) > 0:
                window.append(sentence)
            else:
                if window:
                    segments.append(" ".join(window))
                    window = []
        if window:
            segments.append(" ".join(window))

        deduped: List[str] = []
        seen: set[str] = set()
        for segment in segments:
            normalized = re.sub(r"\s+", " ", segment)
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(segment)
        return deduped[:20]

    def _segment_signal_score(self, text: str) -> int:
        score = 0
        if self._extract_first_structure(text):
            score += 2
        if self._extract_first_eqe(text):
            score += 2
        if self._extract_first_cie(text):
            score += 1
        if self._extract_first_lifetime(text):
            score += 1
        if self._extract_device_label(text):
            score += 1
        return score

    def _extract_first_structure(self, text: str) -> Optional[str]:
        structures = self._extract_all_structures(text)
        return structures[0] if structures else None

    def _extract_first_eqe(self, text: str) -> Optional[str]:
        values = self._extract_all_eqe(text)
        return values[0] if values else None

    def _extract_first_cie(self, text: str) -> Optional[str]:
        values = self._extract_all_cie(text)
        return values[0] if values else None

    def _extract_first_lifetime(self, text: str) -> Optional[str]:
        values = self._extract_all_lifetime(text)
        return values[0] if values else None

    def _extract_device_label(self, text: str) -> Optional[str]:
        patterns = [
            r"\b(champion device|best device|optimized device|control device|reference device)\b",
            r"\b(device\s*[A-Z0-9])\b",
            r"\b(sample\s*[A-Z0-9])\b",
            r"\b(QLED[-\s]*[A-Z0-9]+)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return " ".join(match.group(1).split())
        return None

    def _build_device_notes(self, text: str) -> Optional[str]:
        compact = " ".join(text.split())
        if len(compact) <= 220:
            return compact
        return compact[:217].rstrip() + "..."

    def _clean_device_notes(self, text: str) -> Optional[str]:
        """清洗器件notes字段中的噪声"""
        if not text:
            return None
        
        # 1. 去除期刊信息
        journal_patterns = [
            r'Research Article',
            r'RESEARCH ARTICLE',
            r'www\.afm-journal\.de',
            r'www\.small-journal\.com',
            r'www\.advancedsciencenews\.com',
        ]
        
        cleaned = text
        for pattern in journal_patterns:
            cleaned = re.sub(pattern, '', cleaned)
        
        # 2. 去除图说明
        cleaned = re.sub(r'Figure \d+\..*?(?=\s|$)', '', cleaned)
        cleaned = re.sub(r'Fig\. \d+\..*?(?=\s|$)', '', cleaned)
        
        # 3. 去除参考文献引用
        cleaned = re.sub(r'\[\d+(?:-\d+)?\]', '', cleaned)
        
        # 4. 去除多余空白
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 5. 限制长度
        if len(cleaned) > 220:
            cleaned = cleaned[:217].rstrip() + "..."
        
        return cleaned if cleaned else None

    def _extract_first_luminance(self, text: str) -> Optional[str]:
        """提取第一个亮度值"""
        values = self._extract_all_luminance(text)
        return values[0] if values else None

    def _extract_all_luminance(self, text: str) -> List[str]:
        """提取所有亮度值"""
        patterns = [
            r'(?:luminance|brightness)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?(?:\s*×\s*10\^\d+)?\s*(?:cd/m²|cd/m2|cd\s*/\s*m\s*²|nits))',
            r'([0-9]+(?:\.[0-9]+)?(?:\s*×\s*10\^\d+)?\s*(?:cd/m²|cd/m2|cd\s*/\s*m\s*²|nits))\s*(?:luminance|brightness)?',
        ]
        
        results = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            results.extend(matches)
        
        return list(dict.fromkeys(results))

    def _extract_first_current_efficiency(self, text: str) -> Optional[str]:
        """提取第一个电流效率值"""
        values = self._extract_all_current_efficiency(text)
        return values[0] if values else None

    def _extract_all_current_efficiency(self, text: str) -> List[str]:
        """提取所有电流效率值"""
        patterns = [
            r'(?:current\s*efficiency|CE)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?\s*cd/A)',
            r'([0-9]+(?:\.[0-9]+)?\s*cd/A)\s*(?:current\s*efficiency|CE)?',
        ]
        
        results = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            results.extend(matches)
        
        return list(dict.fromkeys(results))

    def _extract_first_power_efficiency(self, text: str) -> Optional[str]:
        """提取第一个功率效率值"""
        values = self._extract_all_power_efficiency(text)
        return values[0] if values else None

    def _extract_all_power_efficiency(self, text: str) -> List[str]:
        """提取所有功率效率值"""
        patterns = [
            r'(?:power\s*efficiency|PE)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?\s*lm/W)',
            r'([0-9]+(?:\.[0-9]+)?\s*lm/W)\s*(?:power\s*efficiency|PE)?',
        ]
        
        results = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            results.extend(matches)
        
        return list(dict.fromkeys(results))

    def _merge_inferred_devices(self, paper_data: PaperData, text: str) -> PaperData:
        """用本地启发式补强器件列表，优先修补空器件或单器件缺字段场景。"""
        inferred_devices = self._extract_candidate_devices(text)
        if not inferred_devices:
            return paper_data

        existing_devices = list(paper_data.devices)
        if not existing_devices:
            paper_data.devices = inferred_devices
            self._refresh_best_eqe(paper_data)
            return paper_data

        if len(existing_devices) == 1 and self._device_signal_score(existing_devices[0]) <= 1:
            paper_data.devices = inferred_devices
            self._refresh_best_eqe(paper_data)
            return paper_data

        merged = list(existing_devices)
        seen = {self._device_signature(device) for device in merged}
        for device in inferred_devices:
            signature = self._device_signature(device)
            if signature in seen:
                continue
            seen.add(signature)
            merged.append(device)

        paper_data.devices = merged[:6]
        self._refresh_best_eqe(paper_data)
        return paper_data

    def _device_signal_score(self, device: DeviceData) -> int:
        return sum(
            1
            for value in [device.device_label, device.structure, device.eqe, device.cie, device.lifetime]
            if value
        )

    def _device_signature(self, device: DeviceData) -> tuple:
        return (
            (device.device_label or "").lower(),
            (device.structure or "").lower(),
            (device.eqe or "").lower(),
            (device.cie or "").lower(),
            (device.lifetime or "").lower(),
        )

    def _refresh_best_eqe(self, paper_data: PaperData) -> None:
        if paper_data.paper_info.best_eqe:
            return

        best_value = -1.0
        best_label = None
        for device in paper_data.devices:
            if not device.eqe:
                continue
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)", device.eqe)
            if not match:
                continue
            value = float(match.group(1))
            if value > best_value:
                best_value = value
                best_label = device.eqe

        if best_label:
            paper_data.paper_info.best_eqe = best_label

    def _sanitize_devices(self, paper_data: PaperData) -> PaperData:
        cleaned_devices: List[DeviceData] = []
        seen: set[tuple] = set()

        for device in paper_data.devices:
            normalized = self._sanitize_device(device)
            if normalized is None:
                continue
            signature = self._device_signature(normalized)
            if signature in seen:
                continue
            seen.add(signature)
            cleaned_devices.append(normalized)

        cleaned_devices.sort(
            key=lambda item: (
                self._device_signal_score(item),
                1 if item.eqe else 0,
                1 if item.lifetime else 0,
                1 if item.structure else 0,
            ),
            reverse=True,
        )
        paper_data.devices = cleaned_devices[:6]

        if paper_data.paper_info.best_eqe and not any(
            device.eqe == paper_data.paper_info.best_eqe for device in paper_data.devices
        ):
            paper_data.paper_info.best_eqe = None
        self._refresh_best_eqe(paper_data)
        return paper_data

    def _sanitize_device(self, device: DeviceData) -> Optional[DeviceData]:
        structure = device.structure
        if structure:
            structure = re.sub(r"\s+", " ", structure).strip(" .;")
            if len(structure) > 220 or structure.count(".") > 1:
                structure = self._extract_first_structure(structure)

        notes = device.notes
        if notes:
            notes = re.sub(r"\s+", " ", notes).strip()
            if len(notes) > 280:
                notes = notes[:277].rstrip() + "..."

        normalized = DeviceData(
            device_label=device.device_label,
            structure=structure,
            eqe=device.eqe,
            cie=device.cie,
            lifetime=device.lifetime,
            luminance=device.luminance,
            current_efficiency=device.current_efficiency,
            power_efficiency=device.power_efficiency,
            notes=notes,
        )

        score = self._device_signal_score(normalized)
        has_key_metric = bool(normalized.eqe or normalized.cie or normalized.lifetime)
        if score == 0:
            return None
        if score <= 1 and not has_key_metric:
            return None
        return normalized

    def _extract_all_structures(self, text: str) -> List[str]:
        """提取所有器件结构"""
        patterns = [
            r'((?:ITO|Glass)\s*/\s*[A-Za-z0-9:+()._\-\s]{1,40}(?:\s*/\s*[A-Za-z0-9:+()._\-\s]{1,40}){2,8})',
        ]

        structures = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                cleaned = re.sub(r"\s+", " ", m).strip(" .;,)(")
                if len(cleaned) > 10 and cleaned not in structures:
                    structures.append(cleaned)

        return structures[:3]  # 限制数量

    def _extract_all_eqe(self, text: str) -> List[str]:
        """提取所有 EQE 值"""
        patterns = [
            r'EQE[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
            r'external quantum efficiency[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
            r'max(?:imum)?\s+EQE[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
        ]

        values = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                try:
                    v = float(m)
                    if 0.1 < v < 80:  # EQE 合理范围
                        formatted = f"{v:.2f}%"
                        if formatted not in values:
                            values.append(formatted)
                except ValueError:
                    pass

        return values[:5]  # 限制数量

    def _extract_all_cie(self, text: str) -> List[str]:
        """提取所有 CIE 坐标"""
        patterns = [
            r'CIE[^0-9]*?\(([0-9]?\.[0-9]+)\s*[,，]\s*([0-9]?\.[0-9]+)\)',
            r'\(([0-9]?\.[0-9]+)\s*[,，]\s*([0-9]?\.[0-9]+)\)[^)]*CIE',
            r'色度坐标[^0-9]*?\(([0-9]?\.[0-9]+)\s*[,，]\s*([0-9]?\.[0-9]+)\)',
            r'color\s*coordinates?[^0-9]*?\(([0-9]?\.[0-9]+)\s*[,，]\s*([0-9]?\.[0-9]+)\)',
            r'\b(?:x|y)\s*=\s*([0-9]?\.[0-9]+)\s*,?\s*(?:x|y)\s*=\s*([0-9]?\.[0-9]+)',
        ]

        values = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                try:
                    x, y = float(m[0]), float(m[1])
                    if 0 < x < 1 and 0 < y < 1:
                        formatted = f"({x:.4f}, {y:.4f})"
                        if formatted not in values:
                            values.append(formatted)
                except (ValueError, IndexError):
                    pass

        return values[:5]

    def _extract_all_lifetime(self, text: str) -> List[str]:
        """提取所有寿命值"""
        patterns = [
            r'T[⑤5]0[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hr|hrs|hour|hours)',
            r'LT[⑤5]0[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hr|hrs|hour|hours)',
            r'lifetime[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hour|hours)',
        ]

        values = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                try:
                    v = float(m[0])
                    if 1 < v < 50000:
                        formatted = f"{v:.1f} h"
                        if formatted not in values:
                            values.append(formatted)
                except (ValueError, IndexError):
                    pass

        return values[:5]

    def _extract_optimization_level(self, text: str) -> Optional[str]:
        """提取优化层级"""
        levels = []
        level_keywords = {
            "材料合成": ["synthesis", "material design", "precursor"],
            "核壳结构": ["core-shell", "core/shell", "shell growth"],
            "表面处理": ["surface treatment", "surface modification", "passivation"],
            "配体工程": ["ligand engineering", "ligand exchange"],
            "器件结构": ["device architecture", "device structure"],
            "工艺优化": ["annealing", "thermal treatment"],
        }

        text_lower = text.lower()
        for level, keywords in level_keywords.items():
            if any(kw in text_lower for kw in keywords):
                levels.append(level)

        return "、".join(levels) if levels else None

    def _extract_optimization_strategy(self, text: str) -> Optional[str]:
        """提取优化策略"""
        strategies = []
        strategy_keywords = {
            "表面钝化": ["passivation", "defect passivation"],
            "配体交换": ["ligand exchange", "ligand replacement"],
            "核壳工程": ["core-shell", "shell growth"],
            "界面工程": ["interface engineering"],
            "退火处理": ["annealing", "thermal treatment"],
        }

        text_lower = text.lower()
        for strategy, keywords in strategy_keywords.items():
            if any(kw in text_lower for kw in keywords):
                strategies.append(strategy)

        if strategies:
            return f"采用{', '.join(strategies)}等方法优化器件性能。"

        return None

    def _extract_metric_source(self, text: str, metric: str) -> Optional[str]:
        """提取指标原文"""
        sentence_patterns = {
            "eqe": [
                r'[^.!?\n]*?(?:EQE|external quantum efficiency)[^.!?\n]*?[0-9]+(?:\.[0-9]+)?\s*%[^.!?\n]*[.!?]?',
            ],
            "cie": [
                r'[^.!?\n]*?CIE[^.!?\n]*?\([0-9]\.[0-9]+\s*[,，]\s*[0-9]\.[0-9]+\)[^.!?\n]*[.!?]?',
            ],
            "lifetime": [
                r'[^.!?\n]*?(?:T[⑤5]0|LT[⑤5]0|lifetime)[^.!?\n]*?[0-9]+(?:\.[0-9]+)?\s*(?:h|hr|hrs|hour|hours)[^.!?\n]*[.!?]?',
            ],
            "structure": [
                r'[^.!?\n]*?(?:device\s+structure|architecture)[^.!?\n]*?ITO[^.!?\n]*[.!?]?',
            ],
        }

        for pattern in sentence_patterns.get(metric, []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return " ".join(match.group(0).split())

        return None
