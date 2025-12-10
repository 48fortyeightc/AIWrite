"""
数据模型模块
"""

from .paper import Paper, PaperStatus, Section, Figure, FigureType, Table
from .pipeline import LLMOptions, PipelineContext, PipelineStep

__all__ = [
    "Paper",
    "PaperStatus", 
    "Section",
    "Figure",
    "FigureType",
    "Table",
    "LLMOptions",
    "PipelineContext",
    "PipelineStep",
]
