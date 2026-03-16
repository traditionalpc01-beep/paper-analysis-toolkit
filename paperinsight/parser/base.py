"""
解析器基类定义

定义统一的文档解析接口，支持 PDF 到 Markdown/文本的转换。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class TableData:
    """表格数据结构"""
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    caption: Optional[str] = None
    page_number: Optional[int] = None

    def to_markdown(self) -> str:
        """转换为 Markdown 表格格式"""
        if not self.headers:
            return ""

        lines = []
        # 表头
        lines.append("| " + " | ".join(self.headers) + " |")
        # 分隔符
        lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        # 数据行
        for row in self.rows:
            # 确保行长度与表头一致
            padded_row = row + [""] * (len(self.headers) - len(row))
            lines.append("| " + " | ".join(padded_row[:len(self.headers)]) + " |")

        return "\n".join(lines)


@dataclass
class Section:
    """文档章节结构"""
    title: str
    content: str
    level: int = 1  # 1 = 标题, 2 = 子标题, etc.
    page_number: Optional[int] = None
    subsections: List[Section] = field(default_factory=list)


@dataclass
class ParseResult:
    """
    解析结果数据结构

    包含从 PDF 解析得到的所有结构化信息。
    """

    # 原始内容
    markdown: str = ""
    raw_text: str = ""

    # 结构化数据
    tables: List[TableData] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)

    # 元信息
    page_count: int = 0
    word_count: int = 0
    file_hash: Optional[str] = None
    source_file: Optional[str] = None

    # 处理状态
    success: bool = True
    error_message: Optional[str] = None
    processing_time: float = 0.0
    parser_name: str = "unknown"

    # 额外元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_section_by_title(self, title_pattern: str, case_sensitive: bool = False) -> Optional[Section]:
        """根据标题模式查找章节"""
        import re
        pattern = title_pattern if case_sensitive else title_pattern.lower()

        for section in self.sections:
            section_title = section.title if case_sensitive else section.title.lower()
            if re.search(pattern, section_title):
                return section

            # 递归搜索子章节
            result = self._search_subsections(section.subsections, pattern, case_sensitive)
            if result:
                return result

        return None

    def _search_subsections(
        self,
        subsections: List[Section],
        pattern: str,
        case_sensitive: bool
    ) -> Optional[Section]:
        """递归搜索子章节"""
        import re
        for section in subsections:
            section_title = section.title if case_sensitive else section.title.lower()
            if re.search(pattern, section_title):
                return section

            result = self._search_subsections(section.subsections, pattern, case_sensitive)
            if result:
                return result

        return None

    def get_all_tables_markdown(self) -> str:
        """获取所有表格的 Markdown 格式"""
        if not self.tables:
            return ""

        parts = []
        for i, table in enumerate(self.tables, 1):
            if table.caption:
                parts.append(f"\n**Table {i}: {table.caption}**\n")
            parts.append(table.to_markdown())
            parts.append("")

        return "\n".join(parts)

    def get_text_for_extraction(self, include_tables: bool = True) -> str:
        """
        获取用于数据提取的文本内容

        Args:
            include_tables: 是否包含表格

        Returns:
            合并后的文本内容
        """
        parts = [self.markdown]

        if include_tables:
            tables_md = self.get_all_tables_markdown()
            if tables_md:
                parts.append("\n\n## Tables\n")
                parts.append(tables_md)

        return "\n".join(parts)


class BaseParser(ABC):
    """
    文档解析器基类

    定义统一的解析接口，所有解析器需要实现此接口。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化解析器

        Args:
            config: 解析器配置
        """
        self.config = config or {}
        self._is_available: Optional[bool] = None

    @property
    def name(self) -> str:
        """解析器名称"""
        return self.__class__.__name__

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """
        解析文档

        Args:
            file_path: 文档路径

        Returns:
            解析结果
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查解析器是否可用

        Returns:
            是否可用
        """
        pass

    def supports_format(self, file_path: Path) -> bool:
        """
        检查是否支持该文件格式

        Args:
            file_path: 文件路径

        Returns:
            是否支持
        """
        supported_extensions = {".pdf", ".PDF"}
        return file_path.suffix in supported_extensions

    def _validate_file(self, file_path: Path) -> None:
        """
        验证文件是否存在且可读

        Args:
            file_path: 文件路径

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不支持
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if not self.supports_format(file_path):
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

    def _calculate_word_count(self, text: str) -> int:
        """计算词数（简单实现）"""
        # 移除 Markdown 标记
        import re
        clean_text = re.sub(r'[#*\[\]()`]', '', text)
        # 分割并计数
        words = clean_text.split()
        return len(words)
