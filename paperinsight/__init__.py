"""
PaperInsight CLI - 智能科研论文分析工具
版本: 2.0
作者: WorkBuddy AI Assistant
"""

__version__ = "2.0.0"
__author__ = "WorkBuddy AI Assistant"

__all__ = ["app", "__version__"]


def __getattr__(name: str):
    if name == "app":
        from paperinsight.cli import app
        return app
    raise AttributeError(name)
