"""
文档解析模块

提供 PDF 文档解析功能，支持多种解析方式：
- MinerU：高精度 PDF 转 Markdown
- PyMuPDF：基础 PDF 文本提取（兜底方案）
"""

from .base import BaseParser, ParseResult
from .mineru import MinerUParser

__all__ = [
    "BaseParser",
    "ParseResult",
    "MinerUParser",
]
