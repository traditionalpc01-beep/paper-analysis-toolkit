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
from paperinsight.llm.prompt_templates import format_extraction_prompt_v3


class DataExtractor:
    """
    v3.0 数据提取器

    支持两种提取模式：
    - LLM 模式：语义化提取，输出嵌套 JSON
    - Regex 模式：正则表达式提取（兜底）
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据提取器

        Args:
            config: 配置字典，包含 LLM 配置等
        """
        self.config = config or {}
        self.llm_config = self.config.get("llm", {})

        # 初始化 LLM 客户端
        self.llm: Optional[BaseLLM] = None
        self._init_llm_client()

    def _init_llm_client(self) -> None:
        """初始化 LLM 客户端"""
        if not self.llm_config.get("enabled", True):
            return

        provider = self.llm_config.get("provider", "deepseek")

        try:
            if provider == "openai":
                from paperinsight.llm.openai_client import OpenAIClient

                self.llm = OpenAIClient(
                    api_key=self.llm_config.get("api_key", ""),
                    model=self.llm_config.get("openai", {}).get("model", "gpt-4o"),
                    base_url=self.llm_config.get("base_url", ""),
                    timeout=self.llm_config.get("timeout", 120),
                )

            elif provider == "deepseek":
                from paperinsight.llm.deepseek_client import DeepSeekClient

                self.llm = DeepSeekClient(
                    api_key=self.llm_config.get("api_key", ""),
                    model=self.llm_config.get("deepseek", {}).get("model", "deepseek-chat"),
                    base_url=self.llm_config.get("base_url", ""),
                    timeout=self.llm_config.get("timeout", 120),
                )

            elif provider == "wenxin":
                from paperinsight.llm.wenxin_client import WenxinClient

                wenxin_config = self.llm_config.get("wenxin", {})
                self.llm = WenxinClient(
                    client_id=wenxin_config.get("client_id", ""),
                    client_secret=wenxin_config.get("client_secret", ""),
                    model=wenxin_config.get("model", "ernie-4.0-8k"),
                    timeout=self.llm_config.get("timeout", 120),
                )

            if self.llm and not self.llm.is_available():
                self.llm = None

        except Exception as e:
            print(f"[警告] LLM 客户端初始化失败: {e}")
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
            result = self._extract_with_llm(cleaned_text, parse_result)
            if result.success and result.data:
                result.processing_time = time.time() - start_time
                result.extraction_method = "llm"
                result.llm_model = self.llm_config.get("provider", "unknown")
                return result

        # 回退到正则提取
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
            # 限制文本长度
            max_chars = 15000
            truncated_text = text[:max_chars] if len(text) > max_chars else text

            # 构建 Prompt
            prompt = format_extraction_prompt_v3(truncated_text)

            # 调用 LLM
            response = self.llm.generate_json(prompt, temperature=0.2)

            # 解析并校验
            paper_data = self._parse_and_validate(response)

            if paper_data:
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

    def _parse_and_validate(self, response: Dict[str, Any]) -> Optional[PaperData]:
        """解析并校验 LLM 响应"""
        try:
            # 构建嵌套结构
            paper_info_data = response.get("paper_info", {})
            devices_data = response.get("devices", [])
            data_source_data = response.get("data_source", {})
            optimization_data = response.get("optimization", {})

            # 构建 PaperInfo
            paper_info = PaperInfo(
                title=paper_info_data.get("title"),
                authors=paper_info_data.get("authors"),
                journal_name=paper_info_data.get("journal_name"),
                impact_factor=paper_info_data.get("impact_factor"),
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
            paper_info = PaperInfo(
                title=self._extract_title(text, parse_result),
                authors=self._extract_authors(text, parse_result),
                journal_name=self._extract_journal_name(text),
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
        devices = []

        # 提取器件结构
        structures = self._extract_all_structures(text)

        # 提取 EQE 值
        eqes = self._extract_all_eqe(text)

        # 提取 CIE 坐标
        cies = self._extract_all_cie(text)

        # 提取寿命
        lifetimes = self._extract_all_lifetime(text)

        # 如果只有一组数据，创建单个器件
        if structures or eqes or cies or lifetimes:
            device = DeviceData(
                structure=structures[0] if structures else None,
                eqe=eqes[0] if eqes else None,
                cie=cies[0] if cies else None,
                lifetime=lifetimes[0] if lifetimes else None,
            )
            devices.append(device)

        return devices

    def _extract_all_structures(self, text: str) -> List[str]:
        """提取所有器件结构"""
        patterns = [
            r'(ITO\s*/[^/\n]+(?:/[^/\n]+)+)',
            r'(Glass\s*/[^/\n]+(?:/[^/\n]+)+)',
        ]

        structures = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                cleaned = m.strip()
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
