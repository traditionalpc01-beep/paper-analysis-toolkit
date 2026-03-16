"""
Longcat 客户端模块
功能: 调用 Longcat API 进行文本生成
文档: https://longcat.chat/platform/docs/zh/
"""

import json
import re
from typing import Optional

import requests

from paperinsight.llm.base import BaseLLM


class LongcatClient(BaseLLM):
    """Longcat API 客户端"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "LongCat-Flash-Chat",
        base_url: str = "https://api.longcat.chat/openai",
        timeout: int = 120,
    ):
        """
        初始化 Longcat 客户端
        
        Args:
            api_key: Longcat API Key
            model: 模型名称 (LongCat-Flash-Chat / LongCat-Flash-Thinking / LongCat-Flash-Lite)
            base_url: API 基础 URL
            timeout: 请求超时时间(秒)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
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
            
            except ImportError:
                self._client = None
        
        return self._client

    def _build_payload(
        self,
        prompt: str,
        max_tokens: Optional[int],
        temperature: float,
        stream: bool = False,
        **kwargs,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)
        return payload

    def _request_via_http(self, payload: dict, stream: bool = False):
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
            stream=stream,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
        return response

    def _extract_content_from_http_response(self, response: requests.Response) -> str:
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    
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
            if client is not None:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                return response.choices[0].message.content

            payload = self._build_payload(prompt, max_tokens, temperature, **kwargs)
            response = self._request_via_http(payload, stream=False)
            return self._extract_content_from_http_response(response)
        
        except Exception as e:
            raise RuntimeError(f"Longcat API 调用失败: {e}") from e
    
    def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs,
    ):
        """
        流式生成文本
        
        Args:
            prompt: 输入提示
            max_tokens: 最大 token 数
            temperature: 温度参数
        
        Yields:
            生成的文本片段
        """
        client = self._get_client()
        
        try:
            if client is not None:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                    **kwargs,
                )
                
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return

            payload = self._build_payload(prompt, max_tokens, temperature, stream=True, **kwargs)
            response = self._request_via_http(payload, stream=True)
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                data = raw_line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if content:
                    yield content
        
        except Exception as e:
            raise RuntimeError(f"Longcat API 流式调用失败: {e}") from e
    
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
            content = ""
            if client is not None:
                try:
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        response_format={"type": "json_object"},
                        **kwargs,
                    )
                except Exception:
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **kwargs,
                    )

                content = response.choices[0].message.content or ""
            else:
                payload = self._build_payload(
                    prompt,
                    max_tokens,
                    temperature,
                    response_format={"type": "json_object"},
                    **kwargs,
                )
                try:
                    response = self._request_via_http(payload, stream=False)
                except Exception:
                    fallback_payload = self._build_payload(prompt, max_tokens, temperature, **kwargs)
                    response = self._request_via_http(fallback_payload, stream=False)
                content = self._extract_content_from_http_response(response)
            
            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            
            raise ValueError(f"无法从响应中提取 JSON: {content[:200]}")
        
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Longcat API 调用失败: {e}") from e
    
    def is_available(self) -> bool:
        """检查 API 是否可用"""
        try:
            client = self._get_client()
            if client is not None:
                client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5,
                )
            else:
                payload = self._build_payload("test", max_tokens=5, temperature=0.1)
                self._request_via_http(payload, stream=False)
            return True
        except Exception:
            return False
