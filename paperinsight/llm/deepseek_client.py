"""
DeepSeek 客户端模块
功能: 调用 DeepSeek API 进行文本生成
"""

import json
import re
from typing import Optional

from paperinsight.llm.base import BaseLLM


class DeepSeekClient(BaseLLM):
    """DeepSeek API 客户端"""
    
    # DeepSeek API 基础 URL
    BASE_URL = "https://api.deepseek.com/v1"
    
    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        初始化 DeepSeek 客户端
        
        Args:
            api_key: DeepSeek API Key
            model: 模型名称
            timeout: 请求超时时间(秒)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self._client = None
    
    def _get_client(self):
        """获取 OpenAI 兼容客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
            
            except ImportError as e:
                raise ImportError("The `openai` package is not installed. Run: pip install openai") from e
        
        return self._client
    
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        生成文本
        
        Args:
            prompt: 输入提示
            max_tokens: 最大 token 数
            temperature: 温度参数
        
        Returns:
            生成的文本
        """
        client = self._get_client()
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            raise RuntimeError(f"DeepSeek API call failed: {e}") from e
    
    def generate_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.3,
        **kwargs,
    ) -> dict:
        """
        生成 JSON 格式的输出
        
        Args:
            prompt: 输入提示
            max_tokens: 最大 token 数
            temperature: 温度参数
        
        Returns:
            JSON 字典
        """
        client = self._get_client()
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            
            content = response.choices[0].message.content
            
            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            
            raise ValueError(f"Could not extract JSON from response: {content[:200]}")
        
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse failed: {e}") from e
        except Exception as e:
            raise RuntimeError(f"DeepSeek API call failed: {e}") from e
    
    def is_available(self) -> bool:
        """检查 API 是否可用"""
        try:
            client = self._get_client()
            client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False
