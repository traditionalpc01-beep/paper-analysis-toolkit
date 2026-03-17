"""Web 搜索模块"""

from paperinsight.web.impact_factor_fetcher import MJLImpactFactorFetcher
from paperinsight.web.journal_resolver import MJLJournalResolver

__all__ = ["MJLJournalResolver", "MJLImpactFactorFetcher"]
