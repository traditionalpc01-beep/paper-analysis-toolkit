"""
章节过滤器

自动识别并过滤论文中的噪声章节，保留核心科研内容。

核心功能：
1. 识别论文章节结构
2. 过滤噪声章节（参考文献、鸣谢等）
3. 重点保留实验部分（Abstract, Experimental, Results）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class SectionMatch:
    """匹配到的章节"""
    title: str
    start_pos: int
    end_pos: int
    content: str
    is_noise: bool = False


@dataclass
class CleanedContent:
    """
    清洗后的内容结构

    包含保留的内容和统计信息。
    """
    # 核心内容
    abstract: str = ""
    introduction: str = ""
    experimental: str = ""
    results: str = ""
    discussion: str = ""
    conclusion: str = ""

    # 其他保留内容
    other_sections: Dict[str, str] = field(default_factory=dict)

    # 表格内容（单独保存）
    tables: List[str] = field(default_factory=list)

    # 统计信息
    original_length: int = 0
    cleaned_length: int = 0
    removed_sections: List[str] = field(default_factory=list)

    # 完整合并内容
    full_text: str = ""

    @property
    def reduction_ratio(self) -> float:
        """计算文本压缩率"""
        if self.original_length == 0:
            return 0.0
        return 1 - (self.cleaned_length / self.original_length)

    def get_text_for_extraction(self) -> str:
        """
        获取用于数据提取的文本

        优先级：Experimental > Results > Abstract > Discussion > Introduction
        如果没有识别到任何核心章节，返回完整文本作为后备
        """
        parts = []

        # 按优先级添加
        if self.experimental:
            parts.append("## Experimental Section\n\n" + self.experimental)

        if self.results:
            parts.append("## Results\n\n" + self.results)

        if self.abstract:
            parts.append("## Abstract\n\n" + self.abstract)

        if self.discussion:
            parts.append("## Discussion\n\n" + self.discussion)

        if self.introduction:
            parts.append("## Introduction\n\n" + self.introduction)

        if self.conclusion:
            parts.append("## Conclusion\n\n" + self.conclusion)

        # 添加表格
        if self.tables:
            parts.append("\n## Tables\n")
            parts.extend(self.tables)

        # 后备：如果没有识别到任何核心章节，使用完整文本
        if not parts and self.full_text:
            return self.full_text

        return "\n\n".join(parts)


class SectionFilter:
    """
    章节过滤器

    根据预定义规则识别和过滤论文章节。
    """

    # 噪声章节标题模式（需要移除）
    NOISE_PATTERNS = [
        # 参考文献
        r"references?",
        r"bibliography",
        r"文献",
        # 鸣谢
        r"acknowledg?ments?",
        r"致谢",
        r"资金资助",
        # 作者贡献
        r"author\s*contributions?",
        r"作者贡献",
        # 补充材料
        r"supplementary\s*(material|information|data)",
        r"补充材料",
        r"支持信息",
        # 利益冲突
        r"conflict\s*of\s*interest",
        r"利益冲突",
        # 数据可用性
        r"data\s*availability",
        r"数据可用性",
        # 作者信息
        r"author\s*information",
        r"corresponding\s*author",
        r"通讯作者",
        # 附录
        r"appendix",
        r"appendices",
        r"附录",
    ]

    # 核心章节标题模式（需要保留）
    CORE_PATTERNS = {
        "abstract": [
            r"abstract",
            r"摘要",
        ],
        "introduction": [
            r"introduction",
            r"引言",
            r"background",
            r"背景",
        ],
        "experimental": [
            r"experimental\s*(section|methods?|procedures?)?",
            r"materials?\s*and\s*methods?",
            r"实验(部分|方法)?",
            r"材料与方法",
            r"methodology",
        ],
        "results": [
            r"results(\s*and\s*discussion)?",
            r"结果(与讨论)?",
        ],
        "discussion": [
            r"discussion",
            r"讨论",
        ],
        "conclusion": [
            r"conclusions?",
            r"结论",
            r"summary",
            r"总结",
        ],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化过滤器

        Args:
            config: 配置字典，支持以下键：
                - enabled: 是否启用清洗
                - remove_sections: 要移除的章节列表
                - keep_sections: 要保留的章节列表
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

        # 自定义配置可覆盖默认规则
        custom_remove = self.config.get("remove_sections", [])
        custom_keep = self.config.get("keep_sections", [])

        # 构建正则表达式
        self._noise_regex = self._build_regex(self.NOISE_PATTERNS + custom_remove)
        self._core_regexes = {}
        for section_name, patterns in self.CORE_PATTERNS.items():
            all_patterns = patterns + [
                p for p in custom_keep if p not in patterns
            ]
            self._core_regexes[section_name] = self._build_regex(all_patterns)

    def _build_regex(self, patterns: List[str]) -> re.Pattern:
        """构建章节匹配正则表达式"""
        combined = "|".join(f"({p})" for p in patterns)
        return re.compile(combined, re.IGNORECASE)

    def clean(self, markdown: str) -> CleanedContent:
        """
        清洗 Markdown 内容

        Args:
            markdown: 原始 Markdown 文本

        Returns:
            清洗后的内容结构
        """
        result = CleanedContent()
        result.original_length = len(markdown)

        if not self.enabled:
            result.full_text = markdown
            result.cleaned_length = len(markdown)
            result.tables = []
            return result

        # 提取表格（单独保存）
        markdown, tables = self._extract_tables(markdown)
        result.tables = tables

        # 解析章节结构
        sections = self._parse_sections(markdown)

        # 分类处理章节
        for section in sections:
            is_noise = self._is_noise_section(section["title"])
            section_type = self._identify_section_type(section["title"])

            if is_noise:
                result.removed_sections.append(section["title"])
            elif section_type:
                # 保存到对应字段
                content = section["content"].strip()
                if section_type == "abstract":
                    result.abstract = content
                elif section_type == "introduction":
                    result.introduction = content
                elif section_type == "experimental":
                    result.experimental = content
                elif section_type == "results":
                    result.results = content
                elif section_type == "discussion":
                    result.discussion = content
                elif section_type == "conclusion":
                    result.conclusion = content
            else:
                # 其他章节
                result.other_sections[section["title"]] = section["content"]

        # 设置完整文本（如果没有识别到核心章节，会在 get_text_for_extraction 中使用 markdown 作为后备）
        result.full_text = result.get_text_for_extraction() if any([
            result.abstract, result.introduction, result.experimental,
            result.results, result.discussion, result.conclusion
        ]) else markdown
        result.cleaned_length = len(result.full_text)

        return result

    def _parse_sections(self, markdown: str) -> List[Dict[str, str]]:
        """
        解析 Markdown 章节结构

        识别标题层级，分割内容。
        """
        sections = []
        lines = markdown.split("\n")

        current_title = ""
        current_content = []
        in_section = False

        for line in lines:
            # 检测标题（Markdown 格式：# Title）
            header_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)

            if header_match:
                # 保存当前章节
                if in_section and current_title:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_content).strip(),
                    })

                # 开始新章节
                current_title = header_match.group(2).strip()
                current_content = []
                in_section = True
            elif in_section:
                current_content.append(line)

        # 保存最后一个章节
        if in_section and current_title:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_content).strip(),
            })

        # 如果没有识别到章节，返回整体内容
        if not sections:
            sections.append({
                "title": "Document",
                "content": markdown,
            })

        return sections

    def _is_noise_section(self, title: str) -> bool:
        """判断是否为噪声章节"""
        return bool(self._noise_regex.search(title))

    def _identify_section_type(self, title: str) -> Optional[str]:
        """识别章节类型"""
        for section_type, regex in self._core_regexes.items():
            if regex.search(title):
                return section_type
        return None

    def _extract_tables(self, markdown: str) -> Tuple[str, List[str]]:
        """
        提取表格内容

        将 Markdown 表格单独提取，避免被章节分割打断。
        """
        tables = []

        # Markdown 表格模式
        table_pattern = re.compile(
            r"(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)",
            re.MULTILINE
        )

        for match in table_pattern.finditer(markdown):
            table_text = match.group(1).strip()
            tables.append(table_text)

        # 移除表格（或标记位置）
        cleaned_markdown = table_pattern.sub("\n[TABLE]\n", markdown)

        return cleaned_markdown, tables

    def get_section_priority(self, section_type: str) -> int:
        """
        获取章节优先级（用于 LLM Prompt 构建）

        优先级越高，数值越小。
        """
        priorities = {
            "experimental": 1,
            "results": 2,
            "abstract": 3,
            "discussion": 4,
            "introduction": 5,
            "conclusion": 6,
        }
        return priorities.get(section_type, 10)


def clean_paper_content(markdown: str, config: Optional[Dict[str, Any]] = None) -> CleanedContent:
    """
    便捷函数：清洗论文内容

    Args:
        markdown: Markdown 文本
        config: 配置字典

    Returns:
        清洗后的内容
    """
    filter_instance = SectionFilter(config)
    return filter_instance.clean(markdown)
