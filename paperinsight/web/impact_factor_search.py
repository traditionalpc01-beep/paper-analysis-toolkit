"""
影响因子搜索模块
功能: 通过 Web 搜索补全期刊影响因子
"""

import re
import time
from typing import Optional

import requests


class ImpactFactorSearcher:
    """影响因子搜索器"""
    
    # 常用期刊影响因子查询网站
    SEARCH_URLS = [
        "https://www.resurchify.com/info/impact-factor-of-{journal}",
        "https://www.scijournal.org/impact-factor-of-{journal}.shtml",
    ]
    
    # 缓存
    _cache: dict[str, float] = {}
    
    def __init__(self, timeout: int = 30):
        """
        初始化搜索器
        
        Args:
            timeout: 请求超时时间(秒)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    
    def search_impact_factor(
        self,
        journal_name: str,
        use_cache: bool = True,
    ) -> Optional[float]:
        """
        搜索期刊影响因子
        
        Args:
            journal_name: 期刊名称
            use_cache: 是否使用缓存
        
        Returns:
            影响因子值(如果找到)
        """
        # 检查缓存
        if use_cache and journal_name in self._cache:
            return self._cache[journal_name]
        
        # 清理期刊名称
        clean_name = self._clean_journal_name(journal_name)
        if not clean_name:
            return None
        
        # 尝试搜索
        for url_template in self.SEARCH_URLS:
            try:
                url = url_template.format(journal=clean_name.replace(" ", "-"))
                response = self.session.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    if_value = self._parse_impact_factor(response.text)
                    if if_value:
                        # 缓存结果
                        self._cache[journal_name] = if_value
                        return if_value
                
                time.sleep(1)  # 避免请求过快
            
            except Exception:
                continue
        
        return None
    
    def _clean_journal_name(self, name: str) -> str:
        """
        清理期刊名称
        
        Args:
            name: 原始期刊名称
        
        Returns:
            清理后的名称
        """
        # 移除特殊字符
        name = re.sub(r'[^\w\s\-:]', '', name)
        # 标准化空格
        name = ' '.join(name.split())
        return name.strip()
    
    def _parse_impact_factor(self, html: str) -> Optional[float]:
        """
        从 HTML 中解析影响因子
        
        Args:
            html: HTML 文本
        
        Returns:
            影响因子值
        """
        # 常见的影响因子模式
        patterns = [
            r'Impact\s*Factor[:\s]*([0-9]+\.?[0-9]*)',
            r'IF[:\s]*([0-9]+\.?[0-9]*)',
            r'([0-9]+\.[0-9]+)\s*Impact\s*Factor',
            r'impact\s*factor\s*of\s*([0-9]+\.?[0-9]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    if 0.1 < value < 200:  # 合理范围
                        return value
                except ValueError:
                    continue
        
        return None
    
    def batch_search(
        self,
        journal_names: list[str],
        use_cache: bool = True,
    ) -> dict[str, Optional[float]]:
        """
        批量搜索影响因子
        
        Args:
            journal_names: 期刊名称列表
            use_cache: 是否使用缓存
        
        Returns:
            期刊名 -> 影响因子 的字典
        """
        results = {}
        
        for name in journal_names:
            if_value = self.search_impact_factor(name, use_cache)
            results[name] = if_value
            time.sleep(2)  # 避免请求过快
        
        return results
    
    @classmethod
    def add_to_cache(cls, journal_name: str, impact_factor: float):
        """
        添加到缓存
        
        Args:
            journal_name: 期刊名称
            impact_factor: 影响因子值
        """
        cls._cache[journal_name] = impact_factor
    
    @classmethod
    def get_cache(cls) -> dict[str, float]:
        """
        获取缓存
        
        Returns:
            缓存字典
        """
        return cls._cache.copy()
