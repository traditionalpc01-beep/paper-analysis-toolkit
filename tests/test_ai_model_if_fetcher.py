"""
测试 AI 模型影响因子获取模块
"""

import pytest
from paperinsight.web.ai_model_if_fetcher import (
    AIModelImpactFactorFetcher,
    BatchAIModelIFFetcher,
)


class TestAIModelImpactFactorFetcher:
    """测试 AI 模型影响因子获取器"""
    
    def test_extract_if_from_text(self):
        """测试从文本提取影响因子"""
        test_cases = [
            ("这篇论文的影响因子是 12.5", 12.5),
            ("IF: 8.3", 8.3),
            ("Impact Factor: 15.2", 15.2),
            ("IF 9.8 (2023)", 9.8),
            ("影响因子：7.4", 7.4),
            ("", None),
            ("没有影响因子信息", None),
            ("IF: 250", None),  # 超出范围
            ("IF: 0.05", None),  # 超出范围
        ]
        
        for text, expected in test_cases:
            result = AIModelImpactFactorFetcher._extract_if_from_text(text)
            assert result == expected, f"文本 '{text}' 期望 {expected}, 实际 {result}"
    
    def test_init(self):
        """测试初始化"""
        fetcher = AIModelImpactFactorFetcher(timeout=60, headless=True)
        assert fetcher.timeout == 60
        assert fetcher.headless is True
        assert fetcher.browser is None
        assert fetcher.playwright is None


class TestBatchAIModelIFFetcher:
    """测试批量影响因子获取器"""
    
    def test_init(self):
        """测试初始化"""
        fetcher = BatchAIModelIFFetcher(timeout=60, headless=True, delay=3.0)
        assert fetcher.timeout == 60
        assert fetcher.headless is True
        assert fetcher.delay == 3.0


@pytest.mark.skip(reason="需要浏览器环境，手动运行")
def test_lookup_qianwen():
    """测试通义千问查询（需要浏览器）"""
    with AIModelImpactFactorFetcher(timeout=60, headless=False) as fetcher:
        result = fetcher.lookup("Highly Efficient Perovskite Light-Emitting Diodes")
        print(f"结果: {result}")
        assert result is not None


@pytest.mark.skip(reason="需要浏览器环境，手动运行")
def test_lookup_kimi():
    """测试 Kimi 查询（需要浏览器）"""
    with AIModelImpactFactorFetcher(timeout=60, headless=False) as fetcher:
        # 直接测试 Kimi
        result = fetcher._try_kimi("Highly Efficient Perovskite Light-Emitting Diodes")
        print(f"结果: {result}")
        assert result is not None


@pytest.mark.skip(reason="需要浏览器环境，手动运行")
def test_lookup_xmol():
    """测试 X-MOL 查询（需要浏览器）"""
    with AIModelImpactFactorFetcher(timeout=60, headless=False) as fetcher:
        result = fetcher._try_xmol("Highly Efficient Perovskite Light-Emitting Diodes")
        print(f"结果: {result}")
        assert result is not None


if __name__ == "__main__":
    # 运行不需要浏览器的测试
    print("测试文本提取功能...")
    test = TestAIModelImpactFactorFetcher()
    test.test_extract_if_from_text()
    print("✓ 文本提取测试通过")
    
    test.test_init()
    print("✓ 初始化测试通过")
    
    print("\n所有单元测试通过！")
    print("\n注意：浏览器自动化测试需要手动运行：")
    print("  pytest tests/test_ai_model_if_fetcher.py::test_lookup_qianwen -v")
