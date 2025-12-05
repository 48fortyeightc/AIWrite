"""
Prompt 模板模块
"""

from .templates import (
    OUTLINE_SUGGESTION_PROMPT,
    CHAPTER_DRAFT_PROMPT,
    SECTION_DRAFT_PROMPT,
    SECTION_REFINE_PROMPT,
    ABSTRACT_GENERATE_PROMPT,
    ABSTRACT_EN_GENERATE_PROMPT,
    IMAGE_ANALYSIS_PROMPT,
    OUTLINE_INIT_PROMPT,
    MERMAID_GENERATION_PROMPT,
    build_outline_prompt,
    build_chapter_draft_prompt,
    build_section_draft_prompt,
    build_section_refine_prompt,
    build_abstract_prompt,
    build_abstract_en_prompt,
    build_image_analysis_prompt,
    build_outline_init_prompt,
    build_mermaid_generation_prompt,
)

__all__ = [
    "OUTLINE_SUGGESTION_PROMPT",
    "CHAPTER_DRAFT_PROMPT",
    "SECTION_DRAFT_PROMPT",
    "SECTION_REFINE_PROMPT",
    "ABSTRACT_GENERATE_PROMPT",
    "ABSTRACT_EN_GENERATE_PROMPT",
    "IMAGE_ANALYSIS_PROMPT",
    "OUTLINE_INIT_PROMPT",
    "MERMAID_GENERATION_PROMPT",
    "build_outline_prompt",
    "build_chapter_draft_prompt",
    "build_section_draft_prompt",
    "build_section_refine_prompt",
    "build_abstract_prompt",
    "build_abstract_en_prompt",
    "build_image_analysis_prompt",
    "build_outline_init_prompt",
    "build_mermaid_generation_prompt",
]
