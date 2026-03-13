"""LLM 模块"""

from paperinsight.llm.base import BaseLLM
from paperinsight.llm.openai_client import OpenAIClient
from paperinsight.llm.deepseek_client import DeepSeekClient
from paperinsight.llm.prompt_templates import EXTRACTION_PROMPT

__all__ = ["BaseLLM", "OpenAIClient", "DeepSeekClient", "EXTRACTION_PROMPT"]
