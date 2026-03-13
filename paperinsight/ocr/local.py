"""
本地 PaddleOCR 模块
功能: 使用本地 PaddleOCR 进行文本识别(兜底方案)
"""

import os
from pathlib import Path
from typing import Optional, Tuple, Union

from paperinsight.ocr.base import BaseOCR

# 设置环境变量解决 Windows 兼容性问题
os.environ["ONEDNN_VERBOSE"] = "0"
os.environ["PADDLE_DISABLE_ONEDNN"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # 禁用 GPU


class LocalOCR(BaseOCR):
    """本地 PaddleOCR 引擎"""
    
    def __init__(
        self,
        lang: str = "en",
        use_gpu: bool = False,
        enable_hpi: bool = False,
    ):
        """
        初始化本地 OCR 引擎
        
        Args:
            lang: 语言设置 ('en', 'ch', 'japan', 'korean' 等)
            use_gpu: 是否使用 GPU
            enable_hpi: 是否启用高性能推理
        """
        self.lang = lang
        self.use_gpu = use_gpu
        self.enable_hpi = enable_hpi
        self._ocr = None
    
    def _get_ocr_instance(self):
        """延迟初始化 OCR 实例"""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                import paddle
                
                # 设置设备
                paddle.set_device('gpu' if self.use_gpu else 'cpu')
                
                print("[OCR] 初始化本地 PaddleOCR 引擎...")
                self._ocr = PaddleOCR(
                    lang=self.lang,
                    use_gpu=self.use_gpu,
                    enable_hpi=self.enable_hpi,
                    show_log=False,
                )
                print("[OCR] OCR 引擎初始化完成")
            
            except ImportError as e:
                raise ImportError(
                    "未安装 PaddleOCR,请运行: pip install paddlepaddle paddleocr"
                ) from e
        
        return self._ocr
    
    def extract_text_from_pdf(
        self,
        pdf_path: Union[str, Path],
        max_pages: Optional[int] = None,
    ) -> Tuple[str, str, dict]:
        """
        从 PDF 提取文本
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大读取页数
        
        Returns:
            (full_text, front_text, metadata)
        """
        ocr = self._get_ocr_instance()
        pdf_path = Path(pdf_path)
        
        try:
            # 使用 PaddleOCR 处理 PDF
            result = ocr.ocr(str(pdf_path), cls=True)
            
            if not result:
                return "", "", {}
            
            full_text_parts = []
            front_text = ""
            
            for idx, page_result in enumerate(result):
                if max_pages is not None and idx >= max_pages:
                    break
                
                if page_result is None:
                    continue
                
                # 提取页面文本
                page_text_parts = []
                for line in page_result:
                    if line and len(line) >= 2:
                        text = line[1][0] if isinstance(line[1], tuple) else str(line[1])
                        page_text_parts.append(text)
                
                page_text = "\n".join(page_text_parts)
                if page_text:
                    full_text_parts.append(page_text)
                    if not front_text:
                        front_text = page_text
            
            full_text = "\n\n".join(full_text_parts)
            return full_text, front_text, {}
        
        except Exception as e:
            print(f"[OCR] PDF 处理失败: {e}")
            return "", "", {}
    
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
        ocr = self._get_ocr_instance()
        image_path = Path(image_path)
        
        try:
            result = ocr.ocr(str(image_path), cls=True)
            
            if not result or not result[0]:
                return ""
            
            # 提取文本
            text_parts = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], tuple) else str(line[1])
                    text_parts.append(text)
            
            return "\n".join(text_parts)
        
        except Exception as e:
            print(f"[OCR] 图片处理失败: {e}")
            return ""
    
    def is_available(self) -> bool:
        """检查 OCR 引擎是否可用"""
        try:
            import paddleocr
            return True
        except ImportError:
            return False
