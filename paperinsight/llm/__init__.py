"""
LLM 模块

提供多种 LLM 客户端支持：
- OpenAI GPT
- DeepSeek
- 百度文心一言

配置示例：
```yaml
llm:
  enabled: true
  provider: "deepseek"  # openai | deepseek | wenxin
  api_key: "your-api-key"
  model: "deepseek-chat"
```
"""

from paperinsight.llm.base import BaseLLM
from paperinsight.llm.prompt_templates import (
    format_extraction_prompt,
    format_extraction_prompt_v3,
    format_journal_prompt,
    format_optimization_prompt,
)

__all__ = [
    "BaseLLM",
    "format_extraction_prompt",
    "format_extraction_prompt_v3",
    "format_journal_prompt",
    "format_optimization_prompt",
]


def create_llm_client(config: dict) -> BaseLLM | None:
    """
    工厂函数：根据配置创建 LLM 客户端

    Args:
        config: LLM 配置字典

    Returns:
        LLM 客户端实例，或 None（如果配置无效）
    """
    if not config.get("enabled", True):
        return None

    provider = config.get("provider", "deepseek")

    try:
        if provider == "openai":
            from paperinsight.llm.openai_client import OpenAIClient

            return OpenAIClient(
                api_key=config.get("api_key", ""),
                model=config.get("openai", {}).get("model", "gpt-4o"),
                base_url=config.get("base_url", ""),
                timeout=config.get("timeout", 120),
            )

        elif provider == "deepseek":
            from paperinsight.llm.deepseek_client import DeepSeekClient

            return DeepSeekClient(
                api_key=config.get("api_key", ""),
                model=config.get("deepseek", {}).get("model", "deepseek-chat"),
                base_url=config.get("base_url", ""),
                timeout=config.get("timeout", 120),
            )

        elif provider == "wenxin":
            from paperinsight.llm.wenxin_client import WenxinClient

            wenxin_config = config.get("wenxin", {})
            return WenxinClient(
                client_id=wenxin_config.get("client_id", ""),
                client_secret=wenxin_config.get("client_secret", ""),
                model=wenxin_config.get("model", "ernie-4.0-8k"),
                timeout=config.get("timeout", 120),
            )

        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    except Exception as e:
        print(f"[警告] LLM 客户端创建失败: {e}")
        return None
