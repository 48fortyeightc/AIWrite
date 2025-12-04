"""
Prompt 模板定义

包含大纲生成、章节写作、润色等提示词模板
"""

from __future__ import annotations

from ..models import Paper, Section

# ============================================================================
# 大纲生成 Prompt
# ============================================================================

OUTLINE_SUGGESTION_PROMPT = """你是一个学术论文大纲规划专家。你的任务是根据用户提供的论文标题和主要章节，生成详细的小节结构。

## 用户输入

**论文标题**：{title}

**主要章节**：
{major_sections}

## 任务

请为每个主要章节（除摘要/Abstract/参考文献外）生成合理的小节结构。

## 输出格式

请严格按照以下 YAML 格式输出，不要添加额外说明：

```yaml
sections:
  - id: ch1
    title: 第一章 绪论
    children:
      - id: ch1.1
        title: 研究背景
        target_words: 800
        notes: 介绍研究领域的背景和现状
      - id: ch1.2
        title: 研究意义
        target_words: 600
        notes: 阐述研究的理论和实践意义
      # ... 更多小节
  - id: ch2
    title: 第二章 文献综述
    children:
      # ... 小节
```

## 注意事项

1. 每个小节需要有 id（如 ch1.1）、title、target_words（建议字数）和 notes（写作提示）
2. 根据论文标题主题，生成符合学术规范的小节结构
3. 小节数量适中，通常每章 3-6 个小节
4. 摘要、Abstract、致谢、参考文献等特殊章节不需要细分小节
5. 确保输出是有效的 YAML 格式
"""

# ============================================================================
# 章节草稿写作 Prompt
# ============================================================================

SECTION_DRAFT_PROMPT = """你是一个专业的学术论文写作专家。你的任务是撰写论文的指定章节内容。

## 论文信息

**标题**：{paper_title}
**关键词**：{keywords}
**写作风格**：{style}

## 当前章节

**章节标题**：{section_title}
**目标字数**：{target_words}
**写作要求**：{notes}

## 论文大纲（供参考）

{outline_context}

## 任务

请撰写该章节的完整内容。使用 LaTeX 格式输出。

## 输出格式

请直接输出 LaTeX 格式的章节内容，不要包含 \\begin{{document}} 等文档结构命令。

例如：
```latex
\\section{{章节标题}}

正文内容...

\\subsection{{小节标题}}

小节内容...
```

## 写作要求

1. 语言规范，符合学术论文标准
2. 逻辑清晰，论述严谨
3. 适当使用学术术语
4. 确保内容与论文主题相关
5. 字数应接近目标字数
6. 使用有效的 LaTeX 语法
"""

# ============================================================================
# 章节润色 Prompt
# ============================================================================

SECTION_REFINE_PROMPT = """你是一个学术论文润色专家。你的任务是润色和改进论文章节的内容质量。

## 论文信息

**标题**：{paper_title}
**写作风格**：{style}

## 当前章节

**章节标题**：{section_title}

## 章节草稿（LaTeX 格式）

{draft_content}

## 任务

请对草稿进行润色，提升学术写作质量。主要改进方向：

1. 语言表达：修正语法错误，使表达更加规范、流畅
2. 逻辑结构：优化段落组织，增强论述的逻辑性
3. 学术规范：确保符合学术写作规范
4. 内容充实：在保持原意的基础上，适当补充论述

## 输出格式

请直接输出润色后的 LaTeX 格式内容，不要添加解释或说明。
"""


def build_outline_prompt(paper: Paper) -> str:
    """
    构建大纲生成 Prompt
    
    Args:
        paper: 论文对象（包含标题和主要章节）
        
    Returns:
        完整的 Prompt 字符串
    """
    # 格式化主要章节列表
    major_sections_lines = []
    for i, section in enumerate(paper.sections, 1):
        major_sections_lines.append(f"{i}. {section.title}")
    major_sections = "\n".join(major_sections_lines)

    return OUTLINE_SUGGESTION_PROMPT.format(
        title=paper.title,
        major_sections=major_sections,
    )


def build_section_draft_prompt(
    paper: Paper,
    section: Section,
    outline_context: str | None = None,
) -> str:
    """
    构建章节草稿写作 Prompt
    
    Args:
        paper: 论文对象
        section: 要写作的章节
        outline_context: 论文大纲上下文（可选）
        
    Returns:
        完整的 Prompt 字符串
    """
    if outline_context is None:
        # 生成简单的大纲上下文
        outline_lines = []
        for s in paper.sections:
            outline_lines.append(f"- {s.title}")
            for child in s.children:
                outline_lines.append(f"  - {child.title}")
        outline_context = "\n".join(outline_lines)

    return SECTION_DRAFT_PROMPT.format(
        paper_title=paper.title,
        keywords=", ".join(paper.keywords) if paper.keywords else "无",
        style=paper.style or "academic",
        section_title=section.title,
        target_words=section.target_words or 1000,
        notes=section.notes or "按照学术规范撰写",
        outline_context=outline_context,
    )


def build_section_refine_prompt(
    paper: Paper,
    section: Section,
    draft_content: str,
) -> str:
    """
    构建章节润色 Prompt
    
    Args:
        paper: 论文对象
        section: 要润色的章节
        draft_content: 章节草稿内容
        
    Returns:
        完整的 Prompt 字符串
    """
    return SECTION_REFINE_PROMPT.format(
        paper_title=paper.title,
        style=paper.style or "academic",
        section_title=section.title,
        draft_content=draft_content,
    )
