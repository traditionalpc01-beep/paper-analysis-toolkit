"""核心模块。"""

__all__ = ["CacheManager", "AnalysisPipeline", "DataExtractor", "ReportGenerator"]


def __getattr__(name: str):
    if name == "CacheManager":
        from paperinsight.core.cache import CacheManager
        return CacheManager
    if name == "AnalysisPipeline":
        from paperinsight.core.pipeline import AnalysisPipeline
        return AnalysisPipeline
    if name == "DataExtractor":
        from paperinsight.core.extractor import DataExtractor
        return DataExtractor
    if name == "ReportGenerator":
        from paperinsight.core.reporter import ReportGenerator
        return ReportGenerator
    raise AttributeError(name)
