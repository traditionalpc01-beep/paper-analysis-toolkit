"""
影响因子搜索模块。

说明：公开、稳定且免费的官方 JCR Impact Factor 接口并不可得，
这里采用多步的网络校正策略：
1. 规范化期刊名称
2. 通过 SCI Journal 的搜索页定位期刊详情页
3. 解析详情页中的最新可用 Impact Factor 历史值

该值用于修复缺失或明显异常的影响因子列，属于 best-effort 校正。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import quote

import requests


@dataclass
class ImpactFactorMatch:
    journal_name: str
    impact_factor: float
    source_url: str
    source_name: str
    year: Optional[int] = None
    similarity: float = 0.0


class ImpactFactorSearcher:
    """影响因子搜索器。"""

    SEARCH_BASE_URL = "https://www.scijournal.org/search.html?search={query}"
    DIRECT_URL = "https://www.scijournal.org/impact-factor-of-{slug}.shtml"

    _cache: dict[str, ImpactFactorMatch] = {}

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            }
        )

    def search_impact_factor(
        self,
        journal_name: str,
        use_cache: bool = True,
    ) -> Optional[float]:
        match = self.lookup_impact_factor(journal_name, use_cache=use_cache)
        return match.impact_factor if match else None

    def lookup_impact_factor(
        self,
        journal_name: str,
        use_cache: bool = True,
    ) -> Optional[ImpactFactorMatch]:
        cache_key = self._normalize_name(journal_name)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        cleaned_name = self._clean_journal_name(journal_name)
        if not cleaned_name:
            return None

        candidates = self._collect_candidate_urls(cleaned_name)
        best_match: Optional[ImpactFactorMatch] = None

        for candidate_url in candidates:
            try:
                response = self.session.get(candidate_url, timeout=self.timeout)
                if response.status_code != 200:
                    continue

                page_title = self._extract_page_title(response.text)
                similarity = self._compute_similarity(cleaned_name, page_title or cleaned_name)
                parsed = self._parse_scijournal_impact_factor(response.text)
                if not parsed:
                    continue

                year, impact_factor = parsed
                match = ImpactFactorMatch(
                    journal_name=page_title or cleaned_name,
                    impact_factor=impact_factor,
                    source_url=candidate_url,
                    source_name="scijournal",
                    year=year,
                    similarity=similarity,
                )
                if self._is_better_match(match, best_match):
                    best_match = match
                time.sleep(0.4)
            except Exception:
                continue

        if best_match and use_cache:
            self._cache[cache_key] = best_match
        return best_match

    def _collect_candidate_urls(self, journal_name: str) -> list[str]:
        urls: list[str] = []
        slug = self._slugify_name(journal_name)
        if slug:
            urls.append(self.DIRECT_URL.format(slug=slug))

        search_url = self.SEARCH_BASE_URL.format(query=quote(journal_name))
        try:
            response = self.session.get(search_url, timeout=self.timeout)
            if response.status_code == 200:
                urls.extend(self._extract_candidate_links(response.text))
        except Exception:
            pass

        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped[:12]

    def _extract_candidate_links(self, html: str) -> list[str]:
        pattern = re.compile(r"https://www\.scijournal\.org/impact-factor-of-[^\s\"'<>]+")
        return pattern.findall(html)

    def _extract_page_title(self, html: str) -> str:
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if not title_match:
            return ""
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
        title = title.replace("- SCI Journal", "").replace("Impact Factor", "").strip(" -")
        return title

    def _parse_scijournal_impact_factor(self, html: str) -> Optional[tuple[int, float]]:
        history_pattern = re.compile(
            r">(20\d{2})\s+Impact\s+Factor</div>\s*<div[^>]*>\s*<span[^>]*>\s*([0-9]+(?:\.[0-9]+)?)\s*</span>",
            re.IGNORECASE,
        )
        history_values = []
        for year_text, value_text in history_pattern.findall(html):
            try:
                year = int(year_text)
                value = float(value_text)
            except ValueError:
                continue
            if 0.1 <= value <= 200:
                history_values.append((year, value))

        if history_values:
            history_values.sort(key=lambda item: item[0], reverse=True)
            return history_values[0]

        chart_pattern = re.compile(
            r"chartData=\{labels:\[(.*?)\],datasets:\[\{[^\]]*data:\[(.*?)\]\}\]\};",
            re.IGNORECASE | re.DOTALL,
        )
        chart_match = chart_pattern.search(html)
        if chart_match:
            labels = [label.strip(" \"'") for label in chart_match.group(1).split(",")]
            values = [value.strip() for value in chart_match.group(2).split(",")]
            pairs = []
            for label, value_text in zip(labels, values):
                if not re.fullmatch(r"20\d{2}", label):
                    continue
                if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value_text):
                    continue
                value = float(value_text)
                if 0.1 <= value <= 200:
                    pairs.append((int(label), value))
            if pairs:
                pairs.sort(key=lambda item: item[0], reverse=True)
                return pairs[0]

        return None

    def _clean_journal_name(self, name: str) -> str:
        name = re.sub(r"[|｜].*$", "", name)
        name = re.sub(r"[^\w\s\-:&/]+", " ", name)
        name = re.sub(r"\s+", " ", name)
        return name.strip()

    def _slugify_name(self, name: str) -> str:
        normalized = self._normalize_name(name)
        return normalized.replace(" ", "-")

    def _normalize_name(self, name: str) -> str:
        name = name.lower().replace("&", " and ")
        name = re.sub(r"[^a-z0-9\s]+", " ", name)
        return re.sub(r"\s+", " ", name).strip()

    def _compute_similarity(self, query: str, title: str) -> float:
        normalized_query = self._normalize_name(query)
        normalized_title = self._normalize_name(title)
        return SequenceMatcher(None, normalized_query, normalized_title).ratio()

    def _is_better_match(
        self,
        candidate: ImpactFactorMatch,
        current: Optional[ImpactFactorMatch],
    ) -> bool:
        if current is None:
            return candidate.similarity >= 0.45
        if candidate.similarity > current.similarity + 0.05:
            return True
        if abs(candidate.similarity - current.similarity) <= 0.05:
            return (candidate.year or 0) > (current.year or 0)
        return False

    def batch_search(
        self,
        journal_names: list[str],
        use_cache: bool = True,
    ) -> dict[str, Optional[float]]:
        results = {}
        for name in journal_names:
            results[name] = self.search_impact_factor(name, use_cache=use_cache)
            time.sleep(0.8)
        return results

    @classmethod
    def add_to_cache(cls, journal_name: str, impact_factor: float):
        cache_key = re.sub(r"\s+", " ", journal_name.strip().lower())
        cls._cache[cache_key] = ImpactFactorMatch(
            journal_name=journal_name,
            impact_factor=impact_factor,
            source_url="cache://manual",
            source_name="cache",
        )

    @classmethod
    def get_cache(cls) -> dict[str, float]:
        return {key: value.impact_factor for key, value in cls._cache.items()}
