"""
工具模块测试
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from paperinsight.utils.hash_utils import calculate_md5, calculate_text_md5
from paperinsight.utils.pdf_utils import PDFProcessor


class TestHashUtils:
    """哈希工具测试"""
    
    def test_calculate_text_md5(self):
        """测试文本 MD5 计算"""
        text = "Hello, World!"
        md5 = calculate_text_md5(text)
        
        assert len(md5) == 32
        assert md5 == "65a8e27d8879283831b664bd8b7f0ad4"
    
    def test_calculate_md5_file(self):
        """测试文件 MD5 计算"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            md5 = calculate_md5(temp_path)
            assert len(md5) == 32
        finally:
            temp_path.unlink()
    
    def test_calculate_md5_not_exists(self):
        """测试不存在的文件"""
        with pytest.raises(FileNotFoundError):
            calculate_md5("/nonexistent/file.pdf")


class TestPDFUtils:
    """PDF 工具测试"""
    
    @patch("fitz.open")
    def test_extract_text(self, mock_open):
        """测试文本提取"""
        # Mock PDF 文档
        mock_doc = Mock()
        mock_doc.metadata = {"title": "Test Paper", "author": "Test Author"}
        mock_doc.__len__ = Mock(return_value=1)
        
        mock_page = Mock()
        mock_page.get_text.return_value = "Test content from PDF"
        mock_page.rect.width = 600
        mock_page.rect.height = 800
        
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_open.return_value = mock_doc
        
        # 创建临时 PDF 文件
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pdf") as f:
            f.write(b"%PDF-1.4\ntest")
            temp_path = Path(f.name)
        
        try:
            processor = PDFProcessor(temp_path)
            full_text, front_text, metadata = processor.extract_text()
            
            assert "Test content" in full_text
            assert metadata["title"] == "Test Paper"
        finally:
            temp_path.unlink()


class TestCacheManager:
    """缓存管理器测试"""
    
    def test_save_and_load(self, tmp_path):
        """测试保存和加载缓存"""
        from paperinsight.core.cache import CacheManager
        
        cache_manager = CacheManager(tmp_path / ".cache")
        
        # 测试数据
        test_data = {
            "journal_name": "Nature",
            "title": "Test Paper",
        }
        md5 = "abc123"
        
        # 保存
        cache_manager.save_data_cache(md5, test_data)
        
        # 加载
        loaded = cache_manager.load_data_cache(md5)
        
        assert loaded is not None
        assert loaded["journal_name"] == "Nature"
        assert loaded["title"] == "Test Paper"
    
    def test_cache_exists(self, tmp_path):
        """测试缓存存在检查"""
        from paperinsight.core.cache import CacheManager
        
        cache_manager = CacheManager(tmp_path / ".cache")
        
        assert not cache_manager.has_data_cache("nonexistent")
        
        cache_manager.save_data_cache("test123", {"data": "test"})
        assert cache_manager.has_data_cache("test123")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
