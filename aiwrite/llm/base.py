"""
LLM Provider 抽象基类
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncIterator

from pydantic import BaseModel, Field

from ..models.pipeline import LLMOptions


class LLMPurpose(str, Enum):
    """模型用途"""
    THINKING = "thinking"    # 思考/规划（大纲生成）
    WRITING = "writing"      # 写作（正文生成）
    POLISHING = "polishing"  # 润色


class LLMResponse(BaseModel):
    """LLM 响应"""
    content: str = Field(..., description="生成的内容")
    model: str = Field(..., description="使用的模型名称")
    usage: dict[str, int] = Field(default_factory=dict, description="Token 使用情况")
    reasoning_content: str | None = Field(default=None, description="思考过程内容（仅思考模型）")
    

class LLMProvider(ABC):
    """LLM Provider 抽象基类"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        purpose: LLMPurpose = LLMPurpose.WRITING,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.purpose = purpose

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    async def invoke(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        options: LLMOptions | None = None,
    ) -> LLMResponse:
        """
        调用 LLM 生成内容
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            options: 调用选项
            
        Returns:
            LLM 响应
        """
        pass

    async def invoke_stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        options: LLMOptions | None = None,
    ) -> AsyncIterator[str]:
        """
        流式调用 LLM（默认实现：直接返回完整响应）
        """
        response = await self.invoke(prompt, system_prompt=system_prompt, options=options)
        yield response.content

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} ({self.model})>"
