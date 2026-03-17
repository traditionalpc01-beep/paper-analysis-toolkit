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
)
from paperinsight.utils.logger import setup_logger


class DataExtractor:
    """
    v3.0 数据提取器

    支持两种提取模式：
    - LLM 模式：语义化提取，输出嵌套 JSON
    - Regex 模式：正则表达式提取（兜底）
    """

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
        self._init_llm_client()

    def _init_llm_client(self) -> None:
        """初始化 LLM 客户端"""
        if not self.llm_config.get("enabled", True):
            self.logger.info("[LLM] 已禁用，使用正则兜底")
            return

        try:
            self.llm = create_llm_client(self.llm_config)
            provider = self.llm_config.get("provider", "unknown")

            if self.llm:
                try:
                    available = self.llm.is_available()
                except Exception as e:
                    self.logger.warning(f"[LLM] {provider} 连通性检查异常，将在提取时直接尝试: {e}")
                    available = True

                if available:
                    self.logger.info(f"[LLM] 客户端已就绪: {provider}")
                else:
                    self.logger.warning(f"[LLM] {provider} 连通性检查失败，仍将尝试正式提取调用")
            else:
                self.logger.warning(f"[LLM] 未能创建客户端: {provider}")

        except Exception as e:
            self.logger.warning(f"[LLM] 客户端初始化失败: {e}")
            self.llm = None

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
            self.logger.info(f"[LLM] 开始使用 {self.llm_config.get('provider', 'unknown')} 提取结构化数据")
            result = self._extract_with_llm(cleaned_text, parse_result)
            if result.success and result.data:
                result.processing_time = time.time() - start_time
                result.extraction_method = "llm"
                result.llm_model = self.llm_config.get("provider", "unknown")
                self.logger.info(f"[LLM] 提取成功: {result.llm_model}")
                return result
            self.logger.warning(f"[LLM] 提取失败，回退正则: {result.error_message}")

        # 回退到正则提取
        self.logger.info("[Regex] 启用正则兜底提取")
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
            self.logger.info(f"[LLM] 发送请求，文本长度 {len(prepared_text)} 字符")
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
                    error_message="LLM 返回数据校验失败",
                )

        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"LLM 提取失败: {str(e)}",
            )

    def _ensure_bilingual_text_fields(self, paper_data: PaperData) -> PaperData:
        """对标题之后的自然语言字段补齐中英对照。"""
        output_config = self.config.get("output", {})
        if not output_config.get("bilingual_text", True):
            return paper_data

        if not self.llm:
            return paper_data

        try:
            self.logger.info("[LLM] 启用中英对照后处理，补齐标题及后续文本列")
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
                self.logger.info("[LLM] 中英对照后处理完成")
                return bilingual_data

            self.logger.warning("[LLM] 中英对照后处理返回数据校验失败，保留首次提取结果")
            return paper_data

        except Exception as e:
            self.logger.warning(f"[LLM] 中英对照后处理失败，保留首次提取结果: {e}")
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
            f"[LLM] 清洗后文本仍超过预算，执行边界截断: {len(text)} -> {max_chars}"
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
            print(f"[校验失败] {e}")
            return None
        except Exception as e:
            print(f"[解析失败] {e}")
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
                error_message=f"正则提取失败: {str(e)}",
            )

    # ============== 正则提取方法 ==============

    def _extract_title(self, text: str, parse_result: Optional[ParseResult]) -> Optional[str]:
        """提取论文标题"""
        # 从解析结果获取
        if parse_result and parse_result.metadata.get("title"):
            return parse_result.metadata["title"]

        # 从文本前几行提取
        lines = text.split("\n")[:20]
        for line in lines:
            line = line.strip()
            # 标题通常较长且不含特殊字符
            if 30 < len(line) < 200 and not any(c in line for c in ["@", "http", "www"]):
                return line

        return None

    def _extract_authors(self, text: str, parse_result: Optional[ParseResult]) -> Optional[str]:
        """提取作者"""
        if parse_result and parse_result.metadata.get("author"):
            authors = parse_result.metadata["author"]
            parts = [p.strip() for p in re.split(r"[;,\n]+", authors) if p.strip()]
            return ", ".join(parts[:10])  # 限制作者数量

        # 正则匹配
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
        metadata = parse_result.metadata if parse_result else {}
        raw_journal_title = self._first_non_empty(
            self._coerce_metadata_value(metadata.get("journal_name")),
            self._coerce_metadata_value(metadata.get("journal")),
            self._coerce_metadata_value(metadata.get("publication_name")),
            self._coerce_metadata_value(metadata.get("publication_title")),
            self._coerce_metadata_value(metadata.get("container_title")),
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
        journal_patterns = [
            r'Nature\s+(Communications|Photonics|Materials|Nanotechnology|Energy)',
            r'Advanced\s+(Materials|Functional\s+Materials|Optical\s+Materials|Energy\s+Materials)',
            r'ACS\s+(Nano|Applied\s+Materials|Energy\s+Letters|Photonics)',
            r'Nano\s+(Letters|Today|Research|Energy)',
            r'Journal\s+of\s+the\s+American\s+Chemical\s+Society',
            r'Science\s+(Advances)?',
            r'Cell\s+(Reports)?',
            r'Angewandte\s+Chemie',
            r'Chemical\s+Science',
            r'Physical\s+Review\s+(Letters|Applied)',
        ]

        for pattern in journal_patterns:
            match = re.search(pattern, text[:5000], re.IGNORECASE)
            if match:
                return match.group(0)

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
            r'(?:published|accepted|received)[^0-9]{0,20}(20[1-2][0-9])',
            r'©?\s*(20[1-2][0-9])\s+(?:The\s+Author|Elsevier|Nature|Science|Wiley)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue

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
            label = self._extract_device_label(segment)

            has_signal = bool(structure or eqe or cie or lifetime)
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
                    notes=self._build_device_notes(segment),
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
            r'CIE[^0-9]*?\(([0-9]\.[0-9]+)\s*[,，]\s*([0-9]\.[0-9]+)\)',
            r'\(([0-9]\.[0-9]+)\s*[,，]\s*([0-9]\.[0-9]+)\)[^)]*CIE',
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
