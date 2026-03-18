"""
实验性影响因子获取模块。

当前实现优先使用可直接核查的 Web/API 路径：
1. Crossref 反查期刊
2. 本地缓存
3. LetPub 搜索页
4. 通义千问 / Kimi API 兜底

文件中保留了少量兼容接口，用于兼容旧测试和旧调用方式。
"""

from __future__ import annotations

import re
import time
from typing import Iterable, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from paperinsight.web.impact_factor_fetcher import ImpactFactorLookupResult


class LetPubFetcher:
    """LetPub网站获取期刊影响因子"""
    
    BASE_URL = "https://letpub.com.cn"
    SEARCH_URL = "https://letpub.com.cn/index.php?page=search&name={}&searchsubmit=true"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
    
    def lookup_by_journal(self, journal_name: str) -> ImpactFactorLookupResult:
        """
        通过期刊名称查询影响因子
        
        Args:
            journal_name: 期刊名称
            
        Returns:
            ImpactFactorLookupResult: 查询结果
        """
        if not journal_name or journal_name == 'nan' or journal_name == 'NaN':
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="LETPUB",
                source_url="",
                error_message="期刊名称无效",
            )
        
        try:
            # 搜索期刊
            search_url = self.SEARCH_URL.format(quote(journal_name))
            response = self.session.get(search_url, timeout=self.timeout)
            response.raise_for_status()
            
            # 解析搜索结果
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找影响因子
            if_value = self._extract_if_from_search_page(soup, journal_name)
            
            if if_value:
                return ImpactFactorLookupResult(
                    status="OK",
                    source_name="LETPUB",
                    source_url=search_url,
                    impact_factor=if_value,
                    year=None,
                )
            else:
                return ImpactFactorLookupResult(
                    status="NOT_FOUND",
                    source_name="LETPUB",
                    source_url=search_url,
                    error_message=f"未找到期刊 {journal_name} 的影响因子",
                )
                
        except requests.RequestException as e:
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="LETPUB",
                source_url="",
                error_message=f"网络请求失败: {str(e)}",
            )
        except Exception as e:
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="LETPUB",
                source_url="",
                error_message=f"解析失败: {str(e)}",
            )
    
    def _extract_if_from_search_page(self, soup: BeautifulSoup, journal_name: str) -> Optional[float]:
        """从LetPub搜索页面提取影响因子"""
        # 查找表格中的影响因子
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    cell_text = cells[0].get_text().strip()
                    # 检查是否匹配期刊名称
                    if journal_name.lower() in cell_text.lower():
                        # 在后续单元格中查找IF
                        for cell in cells[1:]:
                            text = cell.get_text().strip()
                            # 匹配IF值
                            match = re.search(r'(\d+\.?\d*)', text)
                            if match:
                                try:
                                    value = float(match.group(1))
                                    if 0.1 <= value <= 300:
                                        return value
                                except ValueError:
                                    continue
        
        # 备用：直接在整个页面搜索IF值
        page_text = soup.get_text()
        patterns = [
            r'影响因子[^\d]*(\d+\.?\d*)',
            r'IF[^\d]*(\d+\.?\d*)',
            r'(\d+\.\d+)[^\d]*(?:影响因子|IF)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                try:
                    value = float(match)
                    if 0.1 <= value <= 300:
                        return value
                except ValueError:
                    continue
        
        return None


class JournalIFCache:
    """期刊影响因子缓存"""
    
    # 常用期刊的IF值缓存（2024年数据）
    CACHE = {
        # 顶级期刊
        "nature": 50.5,
        "science": 44.7,
        "cell": 45.5,
        # 材料科学
        "advanced materials": 26.8,
        "adv. mater.": 26.8,
        "advanced functional materials": 18.5,
        "adv. funct. mater.": 18.5,
        "nano letters": 10.8,
        "nano lett.": 10.8,
        "acs nano": 16.0,
        # 化学期刊
        "journal of the american chemical society": 15.6,
        "j. am. chem. soc.": 15.6,
        "jacs": 15.6,
        "angewandte chemie": 16.1,
        "angew. chem.": 16.1,
        "chemical reviews": 52.8,
        "chem. rev.": 52.8,
        # 物理期刊
        "physical review letters": 8.1,
        "phys. rev. lett.": 8.1,
        "prl": 8.1,
        # 光学期刊
        "light: science & applications": 20.6,
        "laser & photonics reviews": 9.8,
        "acs photonics": 6.8,
        # 纳米期刊
        "small": 13.0,
        "nanoscale": 5.8,
        "nano research": 9.9,
        "nano res.": 9.9,
        "journal of materials chemistry a": 10.7,
        "j. mater. chem. a": 10.7,
        # 量子点相关
        "journal of physical chemistry c": 3.7,
        "j. phys. chem. c": 3.7,
        # 半导体
        "applied physics letters": 3.5,
        "appl. phys. lett.": 3.5,
        # 能源
        "journal of power sources": 8.1,
        # 其他
        "not specified in text": None,
    }
    
    @classmethod
    def get(cls, journal_name: str) -> Optional[float]:
        """获取缓存的影响因子"""
        if not journal_name:
            return None
        
        # 标准化期刊名称
        normalized = journal_name.lower().strip()
        
        # 直接匹配
        if normalized in cls.CACHE:
            return cls.CACHE[normalized]
        
        # 模糊匹配
        for key, value in cls.CACHE.items():
            if key in normalized or normalized in key:
                return value
        
        return None


class CrossrefFetcher:
    """通过Crossref API查询论文元数据"""
    
    API_URL = "https://api.crossref.org/works"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PaperInsight/1.0 (mailto:research@example.com)',
        })
    
    def lookup_journal_by_title(self, paper_title: str) -> Optional[str]:
        """通过论文标题查询期刊名称"""
        try:
            params = {
                'query.title': paper_title,
                'rows': 1,
            }
            response = self.session.get(
                self.API_URL, 
                params=params, 
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            items = data.get('message', {}).get('items', [])
            
            if items:
                return items[0].get('container-title', [None])[0]
            
            return None
            
        except Exception:
            return None


class XMOLFetcher:
    """X-MOL网站爬虫获取影响因子（通过论文搜索）"""
    
    BASE_URL = "https://www.x-mol.com"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
    
    def lookup_by_title(self, paper_title: str) -> ImpactFactorLookupResult:
        """通过论文标题在X-MOL搜索（可能被反爬拦截）"""
        # X-MOL有反爬机制，这个方法作为备选
        return ImpactFactorLookupResult(
            status="ERROR",
            source_name="XMOL",
            source_url="",
            error_message="X-MOL有反爬机制，暂时不可用",
        )


class QianwenAPIFetcher:
    """通义千问API获取影响因子（兜底）"""
    
    API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        self.api_key = api_key
        self.timeout = timeout
    
    def lookup(self, paper_title: str, journal_name: Optional[str] = None) -> ImpactFactorLookupResult:
        """通过通义千问API查询影响因子"""
        if not self.api_key:
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="QIANWEN_API",
                source_url="",
                error_message="未配置API Key",
            )
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
            
            if journal_name:
                prompt = f"请查询期刊「{journal_name}」的影响因子（IF），只返回数值，不要其他解释。"
            else:
                prompt = f"请查询论文「{paper_title}」所在期刊的影响因子（IF），只返回数值，不要其他解释。"
            
            data = {
                "model": "qwen-turbo",
                "input": {"prompt": prompt},
                "parameters": {}
            }
            
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return ImpactFactorLookupResult(
                    status="ERROR",
                    source_name="QIANWEN_API",
                    source_url="",
                    error_message=f"API调用失败: {response.status_code}",
                )
            
            result = response.json()
            output_text = result.get('output', {}).get('text', '')
            
            # 提取IF值
            if_value = self._extract_if_from_text(output_text)
            
            if if_value:
                return ImpactFactorLookupResult(
                    status="OK",
                    source_name="QIANWEN_API",
                    source_url="",
                    impact_factor=if_value,
                    year=None,
                )
            else:
                return ImpactFactorLookupResult(
                    status="NOT_FOUND",
                    source_name="QIANWEN_API",
                    source_url="",
                    error_message=f"未能解析IF值: {output_text[:100]}",
                )
                
        except Exception as e:
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="QIANWEN_API",
                source_url="",
                error_message=f"查询异常: {str(e)}",
            )
    
    def _extract_if_from_text(self, text: str) -> Optional[float]:
        """从文本中提取IF值"""
        patterns = [
            r'([0-9]+(?:\.[0-9]+)?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    value = float(match)
                    if 0.1 <= value <= 300:
                        return value
                except ValueError:
                    continue
        return None


class KimiAPIFetcher:
    """Kimi API获取影响因子（兜底）"""
    
    API_URL = "https://api.moonshot.cn/v1/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        self.api_key = api_key
        self.timeout = timeout
    
    def lookup(self, paper_title: str, journal_name: Optional[str] = None) -> ImpactFactorLookupResult:
        """通过Kimi API查询影响因子"""
        if not self.api_key:
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="KIMI_API",
                source_url="",
                error_message="未配置API Key",
            )
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
            
            if journal_name:
                prompt = f"请查询期刊「{journal_name}」的影响因子（IF），只返回数值，不要其他解释。"
            else:
                prompt = f"请查询论文「{paper_title}」所在期刊的影响因子（IF），只返回数值，不要其他解释。"
            
            data = {
                "model": "moonshot-v1-8k",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return ImpactFactorLookupResult(
                    status="ERROR",
                    source_name="KIMI_API",
                    source_url="",
                    error_message=f"API调用失败: {response.status_code}",
                )
            
            result = response.json()
            output_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            if_value = self._extract_if_from_text(output_text)
            
            if if_value:
                return ImpactFactorLookupResult(
                    status="OK",
                    source_name="KIMI_API",
                    source_url="",
                    impact_factor=if_value,
                    year=None,
                )
            else:
                return ImpactFactorLookupResult(
                    status="NOT_FOUND",
                    source_name="KIMI_API",
                    source_url="",
                    error_message=f"未能解析IF值: {output_text[:100]}",
                )
                
        except Exception as e:
            return ImpactFactorLookupResult(
                status="ERROR",
                source_name="KIMI_API",
                source_url="",
                error_message=f"查询异常: {str(e)}",
            )
    
    def _extract_if_from_text(self, text: str) -> Optional[float]:
        """从文本中提取IF值"""
        patterns = [r'([0-9]+(?:\.[0-9]+)?)']
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    value = float(match)
                    if 0.1 <= value <= 300:
                        return value
                except ValueError:
                    continue
        return None


class AIModelImpactFactorFetcher:
    """
    综合影响因子获取器
    
    优先级：
    1. 本地缓存（最快）
    2. LetPub网站爬虫（期刊名称查询）
    3. AI API兜底（需要配置API Key）
    """
    
    def __init__(
        self, 
        timeout: int = 30,
        headless: bool = True,
        qianwen_api_key: Optional[str] = None,
        kimi_api_key: Optional[str] = None,
    ):
        self.timeout = timeout
        self.headless = headless
        self.browser = None
        self.playwright = None
        self.letpub_fetcher = LetPubFetcher(timeout=timeout)
        self.crossref_fetcher = CrossrefFetcher(timeout=timeout)
        self.xmol_fetcher = XMOLFetcher(timeout=timeout)
        self.qianwen_fetcher = QianwenAPIFetcher(api_key=qianwen_api_key, timeout=timeout)
        self.kimi_fetcher = KimiAPIFetcher(api_key=kimi_api_key, timeout=timeout)
        
        # 常用期刊标题关键词映射
        self._title_journal_hints = {
            "advanced materials": "Advanced Materials",
            "adv. mater.": "Advanced Materials",
            "nature": "Nature",
            "science": "Science",
            "acs nano": "ACS Nano",
            "nano letters": "Nano Letters",
            "j. am. chem. soc.": "J. Am. Chem. Soc.",
            "journal of the american chemical society": "J. Am. Chem. Soc.",
            "angewandte chemie": "Angewandte Chemie",
            "small": "Small",
            "advanced functional materials": "Advanced Functional Materials",
        }

    def __enter__(self) -> "AIModelImpactFactorFetcher":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    @staticmethod
    def _extract_if_from_text(text: str) -> Optional[float]:
        if not text:
            return None

        patterns = [
            r"(?:impact\s*factor|影响因子|^|\bif\b)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
            r"([0-9]+(?:\.[0-9]+)?)\s*(?:\(?(?:impact\s*factor|影响因子|if)\)?)",
            r"([0-9]+(?:\.[0-9]+)?)",
        ]

        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                try:
                    value = float(match)
                except ValueError:
                    continue
                if 0.1 <= value <= 200:
                    return value
        return None
    
    def _infer_journal_from_title(self, paper_title: str) -> Optional[str]:
        """从论文标题推断可能的期刊（标题中可能包含期刊名）"""
        title_lower = paper_title.lower()
        for hint, journal in self._title_journal_hints.items():
            if hint in title_lower:
                return journal
        return None

    def _try_qianwen(
        self,
        paper_title: str,
        journal_name: Optional[str] = None,
    ) -> ImpactFactorLookupResult:
        return self.qianwen_fetcher.lookup(paper_title, journal_name)

    def _try_kimi(
        self,
        paper_title: str,
        journal_name: Optional[str] = None,
    ) -> ImpactFactorLookupResult:
        return self.kimi_fetcher.lookup(paper_title, journal_name)

    def _try_xmol(self, paper_title: str) -> ImpactFactorLookupResult:
        return self.xmol_fetcher.lookup_by_title(paper_title)
    
    def lookup(self, paper_title: str, journal_name: Optional[str] = None) -> ImpactFactorLookupResult:
        """
        查询影响因子
        
        Args:
            paper_title: 论文标题
            journal_name: 期刊名称（可选）
            
        Returns:
            ImpactFactorLookupResult: 查询结果
        """
        # 如果没有期刊名称，尝试通过Crossref查询
        if not journal_name and paper_title:
            journal_name = self.crossref_fetcher.lookup_journal_by_title(paper_title)
        
        # 如果还是没有，尝试从标题推断
        if not journal_name and paper_title:
            journal_name = self._infer_journal_from_title(paper_title)
        
        # 1. 优先使用本地缓存
        if journal_name:
            cached_if = JournalIFCache.get(journal_name)
            if cached_if:
                return ImpactFactorLookupResult(
                    status="OK",
                    source_name="LOCAL_CACHE",
                    source_url="",
                    impact_factor=cached_if,
                    year=None,
                )
        
        # 2. LetPub网站查询
        if journal_name:
            result = self.letpub_fetcher.lookup_by_journal(journal_name)
            if result.status == "OK":
                return result
        
        # 3. AI API兜底
        result = self.qianwen_fetcher.lookup(paper_title, journal_name)
        if result.status == "OK":
            return result
        
        result = self.kimi_fetcher.lookup(paper_title, journal_name)
        if result.status == "OK":
            return result
        
        # 全部失败
        return ImpactFactorLookupResult(
            status="ERROR",
            source_name="ALL_SOURCES_FAILED",
            source_url="",
            error_message="所有查询源均失败",
        )


class BatchAIModelIFFetcher:
    """批量包装器，复用单篇 IF 获取逻辑。"""

    def __init__(
        self,
        timeout: int = 30,
        headless: bool = True,
        delay: float = 2.0,
        qianwen_api_key: Optional[str] = None,
        kimi_api_key: Optional[str] = None,
    ) -> None:
        self.timeout = timeout
        self.headless = headless
        self.delay = delay
        self.fetcher = AIModelImpactFactorFetcher(
            timeout=timeout,
            headless=headless,
            qianwen_api_key=qianwen_api_key,
            kimi_api_key=kimi_api_key,
        )

    def lookup_many(
        self,
        items: Iterable[tuple[str, Optional[str]]],
    ) -> list[ImpactFactorLookupResult]:
        results: list[ImpactFactorLookupResult] = []
        for index, (paper_title, journal_name) in enumerate(items):
            if index:
                time.sleep(self.delay)
            results.append(self.fetcher.lookup(paper_title=paper_title, journal_name=journal_name))
        return results
