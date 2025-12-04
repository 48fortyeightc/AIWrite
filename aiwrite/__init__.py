"""
AIWrite: 自动化论文写作流水线
从「题目 + 章节大纲」到「LaTeX 论文源码 + Word 终稿」
"""

__version__ = "0.1.0"

from .models import Paper, Section, PaperStatus, PipelineStep, PipelineContext, LLMOptions
from .llm import LLMProvider, LLMPurpose, LLMResponse, create_provider
from .config import load_config, load_outline, save_outline, AppConfig
from .pipeline import OutlineSuggestStep, SectionDraftStep, SectionRefineStep, PipelineExecutor
from .render import LatexRenderer, WordExporter

__all__ = [
    # 版本
    "__version__",
    # 模型
    "Paper",
    "Section",
    "PaperStatus",
    "PipelineStep",
    "PipelineContext",
    "LLMOptions",
    # LLM
    "LLMProvider",
    "LLMPurpose",
    "LLMResponse",
    "create_provider",
    # 配置
    "load_config",
    "load_outline",
    "save_outline",
    "AppConfig",
    # Pipeline
    "OutlineSuggestStep",
    "SectionDraftStep",
    "SectionRefineStep",
    "PipelineExecutor",
    # 渲染
    "LatexRenderer",
    "WordExporter",
]
