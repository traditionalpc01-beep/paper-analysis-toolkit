"""
LLM 基类模块
功能: 定义 LLM 客户端的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseLLM(ABC):
    """LLM 客户端基类"""
    
    @abstractmethod
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
            **kwargs: 其他参数
        
        Returns:
            生成的文本
        """
        pass
    
    @abstractmethod
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
            **kwargs: 其他参数
        
        Returns:
            JSON 字典
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        检查 LLM 是否可用
        
        Returns:
            是否可用
        """
        pass
    
    def extract_paper_info(
        self,
        paper_text: str,
        prompt_template: str,
    ) -> dict:
        """
        提取论文信息
        
        Args:
            paper_text: 论文文本
            prompt_template: Prompt 模板
        
        Returns:
            提取的结构化信息
        """
        prompt = prompt_template.format(paper_text=paper_text)
        return self.generate_json(prompt, temperature=0.2)
