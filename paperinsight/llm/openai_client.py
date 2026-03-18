"""
OpenAI 客户端模块
功能: 调用 OpenAI API 进行文本生成
"""

import json
import re
from typing import Any, Dict, Optional

from paperinsight.llm.base import BaseLLM


class OpenAIClient(BaseLLM):
    """OpenAI API 客户端"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        初始化 OpenAI 客户端
        
        Args:
            api_key: OpenAI API Key
            model: 模型名称
            base_url: API 基础 URL(可选,用于代理或自定义端点)
            timeout: 请求超时时间(秒)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._client = None
        self.last_usage: Dict[str, Any] = {}
    
    def _get_client(self):
        """获取 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                
                client_kwargs = {"api_key": self.api_key, "timeout": self.timeout}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                
                self._client = OpenAI(**client_kwargs)
            
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
            self._record_usage(response)
            return response.choices[0].message.content
        
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {e}") from e
    
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
        json_schema = kwargs.pop("json_schema", None)
        schema_name = kwargs.pop("schema_name", "paperinsight_schema")

        try:
            if json_schema:
                try:
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": schema_name,
                                "strict": True,
                                "schema": json_schema,
                            },
                        },
                        **kwargs,
                    )
                    self._record_usage(response)
                    content = response.choices[0].message.content
                    return json.loads(content)
                except Exception:
                    pass

            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    **kwargs,
                )
                self._record_usage(response)
                content = response.choices[0].message.content
                return json.loads(content)
            except Exception:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                self._record_usage(response)
                content = response.choices[0].message.content
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    return json.loads(json_match.group())

                raise ValueError(f"Could not extract JSON from response: {content[:200]}")

        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse failed: {e}") from e
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {e}") from e
    
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

    def _record_usage(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            self.last_usage = {}
            return

        usage_data = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
        self.last_usage = usage_data
