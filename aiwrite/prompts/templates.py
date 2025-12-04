"""
Prompt 模板定义

包含大纲生成、章节写作、润色、摘要生成等提示词模板
"""

from __future__ import annotations

from ..models import Paper, Section

# ============================================================================
# 大纲生成 Prompt
# ============================================================================

OUTLINE_SUGGESTION_PROMPT = """你是一个学术论文大纲规划专家。你的任务是根据用户提供的论文标题和主要章节，生成详细的小节结构。

## 用户输入

**论文标题**：{title}
**目标总字数**：{target_words} 字

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
3. 小节数量适中，通常每章 3-5 个小节
4. 各章节字数分配需合理，总和接近目标字数 {target_words}
5. 摘要、Abstract、致谢、参考文献等特殊章节不需要细分小节
6. 确保输出是有效的 YAML 格式
"""

# ============================================================================
# 章节草稿写作 Prompt（按章节整体生成）
# ============================================================================

CHAPTER_DRAFT_PROMPT = """你是一个专业的学术论文写作专家。你的任务是撰写论文中一个完整章节的内容。

## 论文信息

**标题**：{paper_title}
**关键词**：{keywords}
**总体目标字数**：{total_target_words} 字

## 当前章节

**章节标题**：{chapter_title}
**本章目标字数**：{chapter_target_words} 字

## 本章包含的小节

{subsections_outline}

## 论文整体结构（供参考上下文）

{outline_context}

## 已完成的前序章节摘要

{previous_chapters_summary}

## 任务

请一次性撰写本章节的**完整内容**，包括所有小节。使用 LaTeX 格式输出。

## 输出格式

请直接输出 LaTeX 格式的章节内容，不要包含 \\begin{{document}} 等文档结构命令。

```latex
\\section{{章节标题}}

引言段落...

\\subsection{{小节1标题}}

小节1内容...

\\subsection{{小节2标题}}

小节2内容...
```

## 写作要求【重要】

1. **字数严格控制**：本章内容必须控制在 {chapter_target_words} 字左右，不可大幅超出
2. **一次写完所有小节**：不要分开写，请完整输出本章所有小节内容
3. **禁止使用以下表达**：
   - 禁止使用"首先"、"其次"、"再次"、"最后"、"综上所述"等过渡套话
   - 禁止使用"本章将"、"本节将"、"下面将"等预告性语句
   - 禁止使用"如图X所示"、"如表Y所示"（除非确实有图表）
4. **语言要求**：
   - 使用学术规范的中文表达
   - 句式多样化，避免重复的句型结构
   - 每个段落开头用不同的方式引入
   - 多用具体描述，少用笼统概括
5. **内容要求**：
   - 各小节之间内容不要重复
   - 保持逻辑连贯但避免机械衔接
   - 使用有效的 LaTeX 语法
"""

# 保留旧模板用于向后兼容
SECTION_DRAFT_PROMPT = CHAPTER_DRAFT_PROMPT

# ============================================================================
# 章节润色 Prompt
# ============================================================================

SECTION_REFINE_PROMPT = """你是一个学术论文润色专家。你的任务是润色和改进论文章节的内容质量。

## 论文信息

**标题**：{paper_title}

## 当前章节

**章节标题**：{section_title}

## 章节草稿（LaTeX 格式）

{draft_content}

## 任务

请对草稿进行润色，提升学术写作质量。主要改进方向：

1. 语言表达：修正语法错误，使表达更加规范、流畅
2. 逻辑结构：优化段落组织，增强论述的逻辑性
3. 学术规范：确保符合学术写作规范
4. **去除套话**：删除"首先/其次/最后"、"综上所述"等机械过渡词

## 输出格式

请直接输出润色后的 LaTeX 格式内容，不要添加解释或说明。
"""


# ============================================================================
# 摘要生成 Prompt（全文完成后生成）
# ============================================================================

ABSTRACT_GENERATE_PROMPT = """你是一个学术论文摘要写作专家。你的任务是根据论文全文内容，撰写一个高质量的中文摘要。

## 论文信息

**标题**：{paper_title}
**关键词**：{keywords}
**目标摘要字数**：300-500 字

## 论文完整内容

{full_content}

## 任务

请根据论文全文，撰写一个精炼准确的中文摘要。

## 摘要要求

1. **结构完整**：包含研究背景、研究目的、研究方法、主要结论
2. **语言精炼**：使用学术规范语言，避免口语化表达
3. **内容准确**：准确概括论文核心内容和创新点
4. **字数控制**：300-500字

## 输出格式

直接输出摘要正文，不需要"摘要"标题，使用纯文本格式。
"""


# ============================================================================
# 英文摘要生成 Prompt
# ============================================================================

ABSTRACT_EN_GENERATE_PROMPT = """You are an academic abstract writing expert. Your task is to write a high-quality English abstract based on the Chinese abstract.

## Paper Information

**Title**: {paper_title}
**Keywords**: {keywords}

## Chinese Abstract

{chinese_abstract}

## Task

Please translate and adapt the Chinese abstract into a proper English academic abstract.

## Requirements

1. **Academic language**: Use formal academic English
2. **Accurate translation**: Preserve the key information and conclusions
3. **Natural expression**: Not word-for-word translation, but idiomatic academic writing
4. **Word count**: 200-400 words

## Output Format

Output the English abstract directly, without "Abstract" title.
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
        target_words=paper.target_words,
        major_sections=major_sections,
    )


def build_chapter_draft_prompt(
    paper: Paper,
    chapter: Section,
    previous_summaries: list[str] | None = None,
) -> str:
    """
    构建章节草稿写作 Prompt（按章节整体生成）
    
    Args:
        paper: 论文对象
        chapter: 要写作的主章节（level=1）
        previous_summaries: 前序章节的内容摘要列表
        
    Returns:
        完整的 Prompt 字符串
    """
    # 生成论文大纲上下文
    outline_lines = []
    for s in paper.sections:
        outline_lines.append(f"- {s.title}")
        for child in s.children:
            outline_lines.append(f"  - {child.title}")
    outline_context = "\n".join(outline_lines)

    # 生成本章小节结构
    subsections_lines = []
    chapter_target = chapter.target_words or 2000
    for i, child in enumerate(chapter.children, 1):
        child_words = child.target_words or 500
        notes = child.notes or ""
        subsections_lines.append(f"{i}. {child.title}")
        subsections_lines.append(f"   - 目标字数: {child_words} 字")
        if notes:
            subsections_lines.append(f"   - 写作要点: {notes}")
        chapter_target = max(chapter_target, sum(c.target_words or 500 for c in chapter.children))
    subsections_outline = "\n".join(subsections_lines) if subsections_lines else "（本章无细分小节）"

    # 前序章节摘要
    if previous_summaries:
        prev_summary = "\n\n".join([f"【{i+1}】{s}" for i, s in enumerate(previous_summaries)])
    else:
        prev_summary = "（这是论文第一章，无前序内容）"

    return CHAPTER_DRAFT_PROMPT.format(
        paper_title=paper.title,
        keywords=", ".join(paper.keywords) if paper.keywords else "无",
        total_target_words=paper.target_words,
        chapter_title=chapter.title,
        chapter_target_words=chapter_target,
        subsections_outline=subsections_outline,
        outline_context=outline_context,
        previous_chapters_summary=prev_summary,
    )


def build_section_draft_prompt(
    paper: Paper,
    section: Section,
    outline_context: str | None = None,
) -> str:
    """
    构建章节草稿写作 Prompt（向后兼容，调用新的章节级生成）
    
    Args:
        paper: 论文对象
        section: 要写作的章节
        outline_context: 论文大纲上下文（可选）
        
    Returns:
        完整的 Prompt 字符串
    """
    # 向后兼容：调用新的章节级生成
    return build_chapter_draft_prompt(paper, section)


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
        section_title=section.title,
        draft_content=draft_content,
    )


def build_abstract_prompt(paper: Paper, full_content: str) -> str:
    """
    构建摘要生成 Prompt
    
    Args:
        paper: 论文对象
        full_content: 论文全文内容
        
    Returns:
        完整的 Prompt 字符串
    """
    return ABSTRACT_GENERATE_PROMPT.format(
        paper_title=paper.title,
        keywords=", ".join(paper.keywords) if paper.keywords else "无",
        full_content=full_content,
    )


def build_abstract_en_prompt(paper: Paper, chinese_abstract: str) -> str:
    """
    构建英文摘要生成 Prompt
    
    Args:
        paper: 论文对象
        chinese_abstract: 中文摘要内容
        
    Returns:
        完整的 Prompt 字符串
    """
    return ABSTRACT_EN_GENERATE_PROMPT.format(
        paper_title=paper.title,
        keywords=", ".join(paper.keywords) if paper.keywords else "N/A",
        chinese_abstract=chinese_abstract,
    )
