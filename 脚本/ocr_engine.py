#!/usr/bin/env python3
"""
PaddleOCR 引擎封装模块
功能：提供基于 PaddleOCR 的 PDF/图片文本提取能力
"""

import os
from pathlib import Path
from typing import Optional, Tuple

# 设置环境变量禁用ONEDNN优化，解决Windows兼容性问题
os.environ["ONEDNN_VERBOSE"] = "0"
os.environ["PADDLE_DISABLE_ONEDNN"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # 禁用GPU

from paddleocr import PaddleOCR


class OCREngine:
    """PaddleOCR 文本提取引擎"""

    def __init__(
        self,
        lang: str = "en",
        enable_hpi: bool = False,
    ):
        """初始化OCR引擎

        Args:
            lang: 语言设置 ('en', 'ch', 'japan', 'korean' 等)
            enable_hpi: 是否启用高性能推理
        """
        self.lang = lang
        self.enable_hpi = enable_hpi
        self._ocr = None

    def _get_ocr_instance(self) -> PaddleOCR:
        """延迟初始化OCR实例"""
        if self._ocr is None:
            print("[OCR] 初始化 PaddleOCR 引擎...")
            # 禁用ONEDNN优化以解决Windows兼容性问题
            import paddle
            paddle.set_device('cpu')
            
            self._ocr = PaddleOCR(
                lang=self.lang,
                enable_hpi=self.enable_hpi,
            )
            print("[OCR] OCR 引擎初始化完成")
        return self._ocr

    def extract_text_from_pdf(
        self,
        pdf_path: Path,
        max_pages: Optional[int] = None,
    ) -> Tuple[str, str, dict]:
        """从PDF文件中提取文本（使用PaddleOCR）

        Args:
            pdf_path: PDF文件路径
            max_pages: 最大读取页数（None表示全部）

        Returns:
            (full_text, front_text, metadata)
            - full_text: 全部页面拼接后的文本
            - front_text: 第一页文本
            - metadata: 元数据（OCR模式暂无）
        """
        ocr = self._get_ocr_instance()

        try:
            result = ocr.predict(str(pdf_path))

            if not result:
                return "", "", {}

            full_text_parts = []
            front_text = ""

            for idx, page_res in enumerate(result):
                if max_pages is not None and idx >= max_pages:
                    break

                if hasattr(page_res, 'text'):
                    page_text = page_res.text
                elif hasattr(page_res, 'get'):
                    page_text = page_res.get('text', '')
                else:
                    page_text = str(page_res)

                page_text = page_text.strip()
                if page_text:
                    full_text_parts.append(page_text)
                    if not front_text:
                        front_text = page_text

            full_text = "\n\n".join(full_text_parts)

            return full_text, front_text, {}

        except Exception as e:
            print(f"[OCR] 提取文本失败: {e}")
            return "", "", {}

    def extract_text_from_image(
        self,
        image_path: Path,
    ) -> str:
        """从图片文件中提取文本

        Args:
            image_path: 图片文件路径

        Returns:
            提取的文本内容
        """
        ocr = self._get_ocr_instance()

        try:
            result = ocr.predict(str(image_path))

            if not result:
                return ""

            if hasattr(result[0], 'text'):
                return result[0].text
            elif hasattr(result[0], 'get'):
                return result[0].get('text', '')
            else:
                return str(result[0])

        except Exception as e:
            print(f"[OCR] 图片识别失败: {e}")
            return ""


def create_ocr_engine(
    lang: str = "en",
    enable_hpi: bool = False,
) -> OCREngine:
    """创建OCR引擎的工厂函数

    Args:
        lang: 语言设置
        enable_hpi: 是否启用高性能推理

    Returns:
        OCREngine 实例
    """
    return OCREngine(lang=lang, enable_hpi=enable_hpi)
