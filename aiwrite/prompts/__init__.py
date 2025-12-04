"""
Prompt 模板模块
"""

from .templates import (
    OUTLINE_SUGGESTION_PROMPT,
    SECTION_DRAFT_PROMPT,
    SECTION_REFINE_PROMPT,
    build_outline_prompt,
    build_section_draft_prompt,
    build_section_refine_prompt,
)

__all__ = [
    "OUTLINE_SUGGESTION_PROMPT",
    "SECTION_DRAFT_PROMPT",
    "SECTION_REFINE_PROMPT",
    "build_outline_prompt",
    "build_section_draft_prompt",
    "build_section_refine_prompt",
]
