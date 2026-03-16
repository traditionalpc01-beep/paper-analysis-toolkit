"""
数据提取器模块
功能: 从论文文本中提取结构化数据
"""

import re
from typing import Optional

from paperinsight.llm.base import BaseLLM
from paperinsight.llm.prompt_templates import format_extraction_prompt


class DataExtractor:
    """数据提取器"""
    
    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        use_llm: bool = True,
    ):
        """
        初始化数据提取器
        
        Args:
            llm: LLM 客户端(可选)
            use_llm: 是否使用 LLM 提取
        """
        self.llm = llm
        self.use_llm = use_llm and llm is not None
    
    def extract(
        self,
        full_text: str,
        front_text: str = "",
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        提取论文信息
        
        Args:
            full_text: 全文文本
            front_text: 首页文本
            metadata: PDF 元数据
        
        Returns:
            提取的结构化数据
        """
        metadata = metadata or {}
        
        if self.use_llm:
            return self._extract_with_llm(full_text, front_text, metadata)
        else:
            return self._extract_with_regex(full_text, front_text, metadata)
    
    def _extract_with_llm(
        self,
        full_text: str,
        front_text: str,
        metadata: dict,
    ) -> dict:
        """使用 LLM 提取"""
        try:
            prompt = format_extraction_prompt(full_text[:15000])  # 限制文本长度
            result = self.llm.generate_json(prompt, temperature=0.2)
            
            # 验证和清理结果
            return self._validate_result(result)
        
        except Exception as e:
            print(f"[LLM 提取失败] {e}, 回退到正则提取")
            return self._extract_with_regex(full_text, front_text, metadata)
    
    def _extract_with_regex(
        self,
        full_text: str,
        front_text: str,
        metadata: dict,
    ) -> dict:
        """使用正则表达式提取"""
        result = {
            "journal_name": self._extract_journal_name(front_text or full_text),
            "影响因子": self._extract_impact_factor(front_text or full_text),
            "title": self._extract_title(front_text or full_text, metadata),
            "authors": self._extract_authors(front_text or full_text, metadata),
            "device_structure": self._extract_device_structure(full_text),
            "experimental_params": {
                "eqe": self._extract_eqe(full_text),
                "cie": self._extract_cie(full_text),
                "lifetime": self._extract_lifetime(full_text),
            },
            "data_source": {
                "eqe_source": self._extract_metric_source(full_text, "eqe"),
                "cie_source": self._extract_metric_source(full_text, "cie"),
                "lifetime_source": self._extract_metric_source(full_text, "lifetime"),
            },
            "optimization": {
                "level": self._extract_optimization_level(full_text),
                "strategy": self._extract_optimization_strategy(full_text),
            },
        }
        
        return result

    def _extract_impact_factor(self, text: str) -> float:
        """从论文首页文本中提取影响因子。"""
        patterns = [
            r'impact\s+factor[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)',
            r'\bIF[^0-9]{0,10}([0-9]+(?:\.[0-9]+)?)\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            try:
                value = float(match.group(1))
            except ValueError:
                continue

            if 0.1 < value < 200:
                return value

        return 0.0
    
    def _validate_result(self, result: dict) -> dict:
        """验证和清理结果"""
        # 确保所有必需字段存在
        defaults = {
            "journal_name": "",
            "影响因子": 0.0,
            "title": "",
            "authors": "",
            "device_structure": "",
            "experimental_params": {
                "eqe": [],
                "cie": [],
                "lifetime": [],
            },
            "data_source": {
                "eqe_source": "",
                "cie_source": "",
                "lifetime_source": "",
            },
            "optimization": {
                "level": "",
                "strategy": "",
            },
        }
        
        for key, default_value in defaults.items():
            if key not in result:
                result[key] = default_value
            elif isinstance(default_value, dict):
                for sub_key, sub_default in default_value.items():
                    if sub_key not in result.get(key, {}):
                        result[key][sub_key] = sub_default

        result["影响因子"] = self._coerce_impact_factor(result.get("影响因子"))
        
        return result

    def _coerce_impact_factor(self, value) -> float:
        """标准化影响因子为浮点数。"""
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            match = re.search(r'([0-9]+(?:\.[0-9]+)?)', value)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return 0.0

        return 0.0
    
    def _extract_journal_name(self, text: str) -> str:
        """提取期刊名称"""
        # 常见期刊名称模式
        journal_patterns = [
            r'Nature\s+(Communications|Photonics|Materials|Nanotechnology)',
            r'Advanced\s+(Materials|Functional\s+Materials|Optical\s+Materials)',
            r'ACS\s+(Nano|Applied\s+Materials)',
            r'Nano\s+(Letters|Today|Research)',
            r'Journal\s+of\s+the\s+American\s+Chemical\s+Society',
            r'Science',
        ]
        
        for pattern in journal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return "未知期刊"
    
    def _extract_title(self, text: str, metadata: dict) -> str:
        """提取论文标题"""
        # 先从元数据提取
        if metadata.get("title"):
            return metadata["title"]
        
        # 从文本前几行提取
        lines = text.split("\n")[:20]
        for line in lines:
            line = line.strip()
            # 标题通常较长且不含特殊字符
            if 30 < len(line) < 200 and not any(c in line for c in ["@", "http", "www"]):
                return line
        
        return "未提取到标题"
    
    def _extract_authors(self, text: str, metadata: dict) -> str:
        """提取作者"""
        if metadata.get("author"):
            authors = metadata["author"]
            parts = [p.strip() for p in re.split(r"[;,\n]+", authors) if p.strip()]
            return ", ".join(parts)

        name_pattern = r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'
        matches = re.findall(name_pattern, text[:5000])

        if matches:
            unique_names = list(dict.fromkeys(matches))
            return ", ".join(unique_names)

        return "未提取"
    
    def _extract_device_structure(self, text: str) -> str:
        """提取器件结构"""
        # 常见器件结构模式
        patterns = [
            r'(ITO\s*/[^/\n]+(?:/[^/\n]+)+)',
            r'(Glass\s*/[^/\n]+(?:/[^/\n]+)+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_eqe(self, text: str) -> list[str]:
        """提取 EQE 值"""
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
                        values.append(f"{v:.2f}%")
                except ValueError:
                    pass
        
        return list(dict.fromkeys(values))  # 去重保持顺序
    
    def _extract_cie(self, text: str) -> list[str]:
        """提取 CIE 坐标"""
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
                        values.append(f"({x:.4f}, {y:.4f})")
                except (ValueError, IndexError):
                    pass
        
        return list(dict.fromkeys(values))
    
    def _extract_lifetime(self, text: str) -> list[str]:
        """提取寿命"""
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
                    if 1 < v < 50000:  # 合理范围
                        values.append(f"{v:.1f} h")
                except (ValueError, IndexError):
                    pass
        
        return list(dict.fromkeys(values))
    
    def _extract_optimization_level(self, text: str) -> str:
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
        
        return "、".join(levels)
    
    def _extract_optimization_strategy(self, text: str) -> str:
        """提取优化策略(简化版)"""
        # 使用正则提取策略关键词
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
        
        return ""

    def _extract_metric_source(self, text: str, metric: str) -> str:
        """提取指标所在句子，作为简易数据溯源。"""
        sentence_patterns = {
            "eqe": [
                r'[^.!?\n]*?(?:EQE|external quantum efficiency)[^.!?\n]*?[0-9]+(?:\.[0-9]+)?\s*%[^.!?\n]*[.!?]?',
            ],
            "cie": [
                r'[^.!?\n]*?CIE[^.!?\n]*?\([0-9]\.[0-9]+\s*[,，]\s*[0-9]\.[0-9]+\)[^.!?\n]*[.!?]?',
                r'[^.!?\n]*?\([0-9]\.[0-9]+\s*[,，]\s*[0-9]\.[0-9]+\)[^.!?\n]*?CIE[^.!?\n]*[.!?]?',
            ],
            "lifetime": [
                r'[^.!?\n]*?(?:T[⑤5]0|LT[⑤5]0|lifetime)[^.!?\n]*?[0-9]+(?:\.[0-9]+)?\s*(?:h|hr|hrs|hour|hours)[^.!?\n]*[.!?]?',
            ],
        }

        for pattern in sentence_patterns.get(metric, []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return " ".join(match.group(0).split())

        return ""
