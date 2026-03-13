"""OCR 模块"""

from paperinsight.ocr.base import BaseOCR
from paperinsight.ocr.baidu_api import BaiduOCRAPI
from paperinsight.ocr.local import LocalOCR

__all__ = ["BaseOCR", "BaiduOCRAPI", "LocalOCR"]
