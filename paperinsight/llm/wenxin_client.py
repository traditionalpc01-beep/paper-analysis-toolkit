"""
百度文心一言客户端

使用百度智能云千帆大模型平台的 API。
文档参考：https://ai.baidu.com/ai-doc/AISTUDIO/sTm6s7inu
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import requests

from paperinsight.llm.base import BaseLLM


class WenxinClient(BaseLLM):
    """
    百度文心一言客户端

    使用 OAuth 2.0 认证，需要 client_id 和 client_secret。
    支持的模型：
    - ernie-4.0-8k：文心一言 4.0
    - ernie-3.5-8k：文心一言 3.5
    - ernie-speed-8k：文心一言 Speed（快速版）
    """

    # API 端点
    AUTH_URL = "https://aip.baidubce.com/oauth/2.0/token"
    CHAT_URL_TEMPLATE = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model}"

    # 支持的模型映射
    MODEL_ENDPOINTS = {
        "ernie-4.0-8k": "completions_pro",
        "ernie-3.5-8k": "completions",
        "ernie-speed-8k": "ernie_speed",
    }

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        model: str = "ernie-4.0-8k",
        timeout: int = 120,
    ):
        """
        初始化文心一言客户端

        Args:
            client_id: 百度智能云应用的 Client ID
            client_secret: 百度智能云应用的 Client Secret
            model: 模型名称
            timeout: 请求超时时间（秒）
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.model = model
        self.timeout = timeout

        # Access Token 缓存
        self._access_token: Optional[str] = None
        self._token_expire_time: float = 0

        # 验证配置
        self._is_available = bool(client_id and client_secret)

    def is_available(self) -> bool:
        """检查客户端是否可用"""
        return self._is_available

    def _get_access_token(self) -> str:
        """
        获取 Access Token

        Token 有效期 30 天，这里缓存使用。
        """
        # 检查缓存的 token 是否有效
        if self._access_token and time.time() < self._token_expire_time:
            return self._access_token

        # 请求新的 token
        params = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = requests.post(
                self.AUTH_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data.get("access_token")

            # 设置过期时间（提前 1 小时刷新）
            expires_in = data.get("expires_in", 2592000)  # 默认 30 天
            self._token_expire_time = time.time() + expires_in - 3600

            return self._access_token

        except Exception as e:
            raise RuntimeError(f"获取文心一言 Access Token 失败: {e}")

    def _get_chat_url(self) -> str:
        """获取聊天 API URL"""
        endpoint = self.MODEL_ENDPOINTS.get(self.model, "completions_pro")
        return self.CHAT_URL_TEMPLATE.format(model=endpoint)

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
            temperature: 温度参数（0-1）

        Returns:
            生成的文本
        """
        if not self._is_available:
            raise RuntimeError("文心一言客户端未正确配置")

        access_token = self._get_access_token()
        url = f"{self._get_chat_url()}?access_token={access_token}"

        # 构建请求体
        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": min(max(temperature, 0.01), 1.0),
        }

        if max_tokens:
            payload["max_output_tokens"] = max_tokens

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()

            # 检查错误
            if "error_code" in data:
                raise RuntimeError(f"文心一言 API 错误: {data.get('error_msg', '未知错误')}")

            return data.get("result", "")

        except requests.Timeout:
            raise RuntimeError("文心一言 API 请求超时")
        except requests.RequestException as e:
            raise RuntimeError(f"文心一言 API 请求失败: {e}")

    def generate_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.3,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        生成 JSON 格式的输出

        文心一言不支持原生 JSON 模式，需要在 prompt 中强调。

        Args:
            prompt: 输入提示
            max_tokens: 最大 token 数
            temperature: 温度参数

        Returns:
            JSON 字典
        """
        # 增强 prompt，强调 JSON 输出
        enhanced_prompt = f"""{prompt}

重要：请只输出 JSON 格式的数据，不要包含任何其他文字说明。输出必须是有效的 JSON 格式。"""

        response_text = self.generate(
            enhanced_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # 尝试提取 JSON
        return self._extract_json(response_text)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从响应文本中提取 JSON"""
        import re

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        json_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(json_pattern, text)

        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # 尝试提取 { ... } 块
        brace_pattern = r"\{[\s\S]*\}"
        brace_match = re.search(brace_pattern, text)

        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # 解析失败
        raise ValueError(f"无法从响应中提取有效的 JSON: {text[:200]}...")

    def __repr__(self) -> str:
        return f"WenxinClient(model={self.model}, available={self._is_available})"
