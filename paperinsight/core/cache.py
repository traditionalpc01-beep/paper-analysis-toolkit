"""
缓存管理模块
功能: MD5 指纹缓存、断点续传
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from paperinsight.utils.hash_utils import calculate_md5


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: Union[str, Path] = ".cache"):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_pdf_md5(self, pdf_path: Union[str, Path]) -> str:
        """
        获取 PDF 文件的 MD5 哈希值
        
        Args:
            pdf_path: PDF 文件路径
        
        Returns:
            MD5 哈希值
        """
        return calculate_md5(pdf_path)
    
    def get_data_cache_path(self, md5: str) -> Path:
        """
        获取完整数据缓存路径
        
        Args:
            md5: MD5 哈希值
        
        Returns:
            缓存文件路径
        """
        return self.cache_dir / f"{md5}_data.json"
    
    def get_ocr_cache_path(self, md5: str) -> Path:
        """
        获取 OCR 文本缓存路径
        
        Args:
            md5: MD5 哈希值
        
        Returns:
            缓存文件路径
        """
        return self.cache_dir / f"{md5}_ocr.md"
    
    def has_data_cache(self, md5: str) -> bool:
        """
        检查是否存在完整数据缓存
        
        Args:
            md5: MD5 哈希值
        
        Returns:
            是否存在缓存
        """
        return self.get_data_cache_path(md5).exists()
    
    def has_ocr_cache(self, md5: str) -> bool:
        """
        检查是否存在 OCR 文本缓存
        
        Args:
            md5: MD5 哈希值
        
        Returns:
            是否存在缓存
        """
        return self.get_ocr_cache_path(md5).exists()
    
    def load_data_cache(self, md5: str) -> Optional[dict]:
        """
        加载完整数据缓存
        
        Args:
            md5: MD5 哈希值
        
        Returns:
            缓存数据(如果存在)
        """
        cache_path = self.get_data_cache_path(md5)
        if not cache_path.exists():
            return None
        
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[警告] 缓存文件损坏: {cache_path}, 错误: {e}")
            return None
    
    def save_data_cache(self, md5: str, data: dict) -> Path:
        """
        保存完整数据缓存
        
        Args:
            md5: MD5 哈希值
            data: 要缓存的数据
        
        Returns:
            缓存文件路径
        """
        cache_path = self.get_data_cache_path(md5)
        
        # 添加缓存时间戳
        data["_cache_timestamp"] = datetime.now().isoformat()
        data["_cache_md5"] = md5
        
        with cache_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return cache_path
    
    def load_ocr_cache(self, md5: str) -> Optional[str]:
        """
        加载 OCR 文本缓存
        
        Args:
            md5: MD5 哈希值
        
        Returns:
            OCR 文本(如果存在)
        """
        cache_path = self.get_ocr_cache_path(md5)
        if not cache_path.exists():
            return None
        
        try:
            return cache_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"[警告] OCR 缓存文件读取失败: {cache_path}, 错误: {e}")
            return None
    
    def save_ocr_cache(self, md5: str, text: str) -> Path:
        """
        保存 OCR 文本缓存
        
        Args:
            md5: MD5 哈希值
            text: OCR 文本
        
        Returns:
            缓存文件路径
        """
        cache_path = self.get_ocr_cache_path(md5)
        cache_path.write_text(text, encoding="utf-8")
        return cache_path
    
    def clear_cache(self, md5: Optional[str] = None):
        """
        清除缓存
        
        Args:
            md5: 指定的 MD5 哈希值(如果为 None,则清除所有缓存)
        """
        if md5 is None:
            # 清除所有缓存
            for cache_file in self.cache_dir.glob("*_data.json"):
                cache_file.unlink()
            for cache_file in self.cache_dir.glob("*_ocr.md"):
                cache_file.unlink()
        else:
            # 清除指定 MD5 的缓存
            data_cache = self.get_data_cache_path(md5)
            if data_cache.exists():
                data_cache.unlink()
            
            ocr_cache = self.get_ocr_cache_path(md5)
            if ocr_cache.exists():
                ocr_cache.unlink()
    
    def get_cache_stats(self) -> dict:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        data_caches = list(self.cache_dir.glob("*_data.json"))
        ocr_caches = list(self.cache_dir.glob("*_ocr.md"))
        
        total_size = sum(f.stat().st_size for f in data_caches + ocr_caches)
        
        return {
            "data_cache_count": len(data_caches),
            "ocr_cache_count": len(ocr_caches),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
