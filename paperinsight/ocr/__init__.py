"""OCR 模块"""

from paperinsight.ocr.base import BaseOCR
from paperinsight.ocr.local import LocalOCR
from paperinsight.ocr.paddlex_api import PaddleXAPI

__all__ = ["BaseOCR", "LocalOCR", "PaddleXAPI"]
