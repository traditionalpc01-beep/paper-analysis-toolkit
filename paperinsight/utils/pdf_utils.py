"""
PDF 处理工具模块
功能: PDF 文本提取和预处理
"""

import re
from pathlib import Path
from typing import Optional, Tuple, Union

import fitz  # PyMuPDF


class PDFProcessor:
    """PDF 处理器"""
    
    def __init__(self, pdf_path: Union[str, Path]):
        """
        初始化 PDF 处理器
        
        Args:
            pdf_path: PDF 文件路径
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
        
        self._doc = None
    
    def _open(self):
        """打开 PDF 文档"""
        if self._doc is None:
            self._doc = fitz.open(self.pdf_path)
        return self._doc
    
    def close(self):
        """关闭 PDF 文档"""
        if self._doc is not None:
            self._doc.close()
            self._doc = None
    
    def __enter__(self):
        self._open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def extract_text(
        self,
        max_pages: Optional[int] = None,
        min_text_ratio: float = 0.001,
    ) -> Tuple[str, str, dict]:
        """
        提取 PDF 文本
        
        Args:
            max_pages: 最大读取页数(None 表示不限制)
            min_text_ratio: 最小文本密度比例(低于此值视为扫描版 PDF)
                         计算公式: 文本字符数 / (页面宽度 * 页面高度 / 100)
        
        Returns:
            (full_text, front_text, metadata)
            - full_text: 全文
            - front_text: 首页文本
            - metadata: PDF 元数据
        """
        doc = self._open()
        metadata = self._extract_metadata(doc)
        
        texts = []
        front_text = ""
        total_area = 0  # 页面总面积
        
        total_pages = len(doc)
        pages_to_read = total_pages if max_pages is None else min(max_pages, total_pages)
        
        for page_idx in range(pages_to_read):
            page = doc[page_idx]
            page_text = page.get_text()
            
            # 清理文本
            page_text = self._clean_text(page_text)
            
            if page_text:
                texts.append(page_text)
                if not front_text:
                    front_text = page_text
            
            # 累加页面面积 (用于计算文本密度)
            rect = page.rect
            total_area += rect.width * rect.height
        
        full_text = "\n\n".join(texts)
        
        # 检测是否为扫描版 PDF
        # 计算文本密度: 字符数 / (页面总面积 / 100)
        if full_text and total_area > 0:
            text_density = len(full_text) / (total_area / 100)
            if text_density < min_text_ratio:
                # 文本密度过低,可能是扫描版
                return "", "", metadata
        elif not full_text:
            # 完全没有提取到文本,视为扫描版
            return "", "", metadata
        
        return full_text, front_text, metadata
    
    def _extract_metadata(self, doc) -> dict:
        """提取 PDF 元数据"""
        metadata = doc.metadata or {}
        
        result = {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "keywords": metadata.get("keywords", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "creation_date": metadata.get("creationDate", ""),
            "modification_date": metadata.get("modDate", ""),
        }
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = re.sub(r"\s+", " ", text)
        text = text.strip()
        
        # 移除特殊字符
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        
        return text
    
    def is_scanned(self, text_ratio_threshold: float = 0.1) -> bool:
        """
        判断是否为扫描版 PDF
        
        Args:
            text_ratio_threshold: 文本比例阈值
        
        Returns:
            是否为扫描版 PDF
        """
        full_text, _, _ = self.extract_text(max_pages=5)
        
        if not full_text:
            return True
        
        # 计算有效字符比例
        doc = self._open()
        total_pages = min(5, len(doc))
        
        total_chars = 0
        for page_idx in range(total_pages):
            page = doc[page_idx]
            total_chars += page.rect.width * page.rect.height / 100  # 估算
        
        text_ratio = len(full_text) / max(total_chars, 1)
        
        return text_ratio < text_ratio_threshold
    
    def get_page_count(self) -> int:
        """获取页数"""
        doc = self._open()
        return len(doc)
    
    def get_first_page_text(self) -> str:
        """获取首页文本"""
        doc = self._open()
        if len(doc) == 0:
            return ""
        
        page = doc[0]
        return self._clean_text(page.get_text())


def extract_text_with_fallback(
    pdf_path: Union[str, Path],
    max_pages: Optional[int] = None,
    ocr_engine=None,
    min_text_ratio: float = 0.001,
) -> Tuple[str, str, dict]:
    """
    提取 PDF 文本(带回退机制)
    
    Args:
        pdf_path: PDF 文件路径
        max_pages: 最大读取页数
        ocr_engine: OCR 引擎(可选,用于扫描版 PDF)
    
    Returns:
        (full_text, front_text, metadata)
    """
    processor = PDFProcessor(pdf_path)
    
    try:
        full_text, front_text, metadata = processor.extract_text(
            max_pages=max_pages,
            min_text_ratio=min_text_ratio,
        )
        metadata["_text_source"] = "native"
        
        # 如果提取到文本,直接返回
        if full_text and not _looks_garbled(full_text):
            return full_text, front_text, metadata
        
        # 如果没有文本且提供了 OCR 引擎,使用 OCR
        if ocr_engine is not None:
            from paperinsight.ocr.base import BaseOCR
            if isinstance(ocr_engine, BaseOCR):
                ocr_text, ocr_front_text, ocr_metadata = ocr_engine.extract_text_from_pdf(
                    pdf_path,
                    max_pages,
                )
                merged_metadata = metadata.copy()
                merged_metadata.update(ocr_metadata or {})
                merged_metadata["_text_source"] = "ocr"
                return ocr_text, ocr_front_text, merged_metadata
        
        return "", "", metadata
    
    finally:
        processor.close()


def _looks_garbled(text: str) -> bool:
    """使用保守规则判断提取文本是否明显乱码。"""
    if not text:
        return True

    stripped = "".join(text.split())
    if len(stripped) < 80:
        return False

    replacement_count = text.count("\ufffd")
    if replacement_count:
        return True

    valid_chars = sum(
        1
        for ch in stripped
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff" or ch in ".,;:!?()[]/%+-_=<>"
    )
    return (valid_chars / len(stripped)) < 0.6
