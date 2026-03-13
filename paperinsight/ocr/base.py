"""
OCR 基类模块
功能: 定义 OCR 引擎的统一接口
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Union


class BaseOCR(ABC):
    """OCR 引擎基类"""
    
    @abstractmethod
    def extract_text_from_pdf(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None,
    ) -> Tuple[str, str, dict]:
        """
        从 PDF 提取文本
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大读取页数(None 表示不限制)
        
        Returns:
            (full_text, front_text, metadata)
        """
        pass
    
    @abstractmethod
    def extract_text_from_image(
        self,
        image_path: Union[str, Path],
    ) -> str:
        """
        从图片提取文本
        
        Args:
            image_path: 图片文件路径
        
        Returns:
            提取的文本
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        检查 OCR 引擎是否可用
        
        Returns:
            是否可用
        """
        pass
