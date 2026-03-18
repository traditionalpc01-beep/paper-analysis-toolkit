"""
PaperInsight CLI - 智能科研论文分析工具

版本: 3.0
特性:
  - MinerU 高性能 PDF 解析
  - 文本降噪（自动过滤噪声章节）
  - LLM 语义提取（支持 DeepSeek/OpenAI/文心一言）
  - Pydantic 数据校验
  - 缓存机制（避免重复解析）
"""

import warnings

warnings.filterwarnings(
    "ignore",
    message=r".*urllib3 .* doesn't match a supported version!.*",
)

__version__ = "3.0.4"
__author__ = "WorkBuddy AI Assistant"

__all__ = ["app", "__version__"]


def __getattr__(name: str):
    if name == "app":
        from paperinsight.cli import app
        return app
    raise AttributeError(name)
