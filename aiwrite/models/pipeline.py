"""
流水线相关数据模型
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from .paper import Paper


class LLMOptions(BaseModel):
    """LLM 调用选项"""
    max_tokens: int = Field(default=4096, description="最大 Token 数")
    temperature: float = Field(default=0.3, description="温度参数")
    top_p: float = Field(default=0.9, description="Top-P 采样")
    timeout: float = Field(default=300.0, description="超时时间（秒），思考模型需要更长时间")


class PipelineContext(BaseModel):
    """流水线执行上下文"""
    paper: Paper = Field(..., description="论文对象")
    working_dir: str | None = Field(default=None, description="工作目录")
    config: dict[str, Any] = Field(default_factory=dict, description="配置信息")
    llm_options: LLMOptions | None = Field(default=None, description="LLM 选项")
    
    class Config:
        arbitrary_types_allowed = True


class PipelineStep(ABC):
    """流水线步骤抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """步骤名称"""
        pass

    @property
    def description(self) -> str:
        """步骤描述（可选覆盖）"""
        return self.name

    @abstractmethod
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        执行步骤，返回更新后的上下文
        
        Args:
            context: 执行上下文（包含 Paper 和 LLM 选项）
            
        Returns:
            更新后的 PipelineContext
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
