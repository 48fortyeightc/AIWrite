"""
Pipeline 步骤实现
"""

from __future__ import annotations

import re
from typing import Any

import yaml
from rich.console import Console

from ..llm import LLMProvider
from ..models import Paper, Section, PaperStatus, PipelineStep, PipelineContext, LLMOptions
from ..prompts import build_outline_prompt, build_section_draft_prompt, build_section_refine_prompt


console = Console()


class OutlineSuggestStep(PipelineStep):
    """
    大纲生成步骤
    
    使用思考模型为主要章节生成小节结构
    """

    def __init__(self, thinking_provider: LLMProvider):
        self.thinking_provider = thinking_provider

    @property
    def name(self) -> str:
        return "outline_suggest"

    @property
    def description(self) -> str:
        return "生成论文大纲的详细小节结构"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行大纲生成"""
        paper = context.paper

        console.print("[bold blue]📝 正在生成大纲小节...[/bold blue]")

        # 构建 Prompt
        prompt = build_outline_prompt(paper)

        # 调用思考模型
        options = context.llm_options or LLMOptions()
        response = await self.thinking_provider.invoke(
            prompt=prompt,
            options=options,
        )

        if response.content:
            # 解析生成的大纲
            updated_sections = self._parse_outline_response(response.content, paper.sections)
            paper.sections = updated_sections
            paper.status = PaperStatus.PENDING_OUTLINE  # 等待用户确认

            console.print(f"[green]✓ 大纲生成完成，共 {len(updated_sections)} 个主要章节[/green]")

            # 显示思考过程（如果有）
            if response.reasoning_content:
                console.print("\n[dim]思考过程:[/dim]")
                console.print(f"[dim]{response.reasoning_content[:500]}...[/dim]")
        else:
            console.print("[red]✗ 大纲生成失败[/red]")

        context.paper = paper
        return context

    def _parse_outline_response(self, content: str, original_sections: list[Section]) -> list[Section]:
        """解析 LLM 返回的大纲 YAML"""
        # 提取 YAML 代码块
        yaml_match = re.search(r"```yaml\s*(.*?)\s*```", content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            # 尝试直接解析
            yaml_content = content

        try:
            data = yaml.safe_load(yaml_content)
            if not data or "sections" not in data:
                console.print("[yellow]警告: 无法解析大纲，保留原始结构[/yellow]")
                return original_sections

            # 将解析的小节合并到原始章节
            section_map = {s["id"]: s for s in data["sections"]}

            updated_sections = []
            for orig in original_sections:
                if orig.id in section_map:
                    parsed = section_map[orig.id]
                    children = []
                    for child_data in parsed.get("children", []):
                        child = Section(
                            id=child_data["id"],
                            title=child_data["title"],
                            level=2,
                            target_words=child_data.get("target_words"),
                            notes=child_data.get("notes"),
                        )
                        children.append(child)
                    orig.children = children
                updated_sections.append(orig)

            return updated_sections

        except yaml.YAMLError as e:
            console.print(f"[yellow]警告: YAML 解析失败: {e}[/yellow]")
            return original_sections


class SectionDraftStep(PipelineStep):
    """
    章节草稿写作步骤
    
    使用写作模型为每个章节生成草稿内容
    """

    def __init__(self, writing_provider: LLMProvider):
        self.writing_provider = writing_provider

    @property
    def name(self) -> str:
        return "section_draft"

    @property
    def description(self) -> str:
        return "为论文章节生成草稿内容"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行章节草稿生成"""
        paper = context.paper
        options = context.llm_options or LLMOptions()

        console.print("[bold blue]✍️ 正在生成章节草稿...[/bold blue]")

        # 遍历所有需要写作的章节
        all_sections = self._flatten_sections(paper.sections)
        total = len(all_sections)

        for i, section in enumerate(all_sections, 1):
            # 跳过摘要、参考文献等特殊章节
            if self._should_skip_section(section):
                continue

            # 跳过已有草稿的章节
            if section.draft_latex:
                console.print(f"[dim]跳过 [{i}/{total}] {section.title} (已有草稿)[/dim]")
                continue

            console.print(f"[cyan]📝 [{i}/{total}] 正在撰写: {section.title}[/cyan]")

            prompt = build_section_draft_prompt(paper, section)
            response = await self.writing_provider.invoke(
                prompt=prompt,
                options=options,
            )

            if response.content:
                section.draft_latex = self._clean_latex_response(response.content)
                console.print(f"[green]  ✓ 完成 ({len(section.draft_latex)} 字符)[/green]")
            else:
                console.print(f"[red]  ✗ 生成失败[/red]")

        paper.status = PaperStatus.DRAFT
        context.paper = paper
        console.print("[bold green]✓ 所有章节草稿生成完成[/bold green]")

        return context

    def _flatten_sections(self, sections: list[Section]) -> list[Section]:
        """展平所有章节（包括子章节）"""
        result = []
        for s in sections:
            result.append(s)
            if s.children:
                result.extend(self._flatten_sections(s.children))
        return result

    def _should_skip_section(self, section: Section) -> bool:
        """判断是否应该跳过该章节"""
        skip_keywords = ["摘要", "abstract", "参考文献", "references", "致谢", "acknowledgment"]
        title_lower = section.title.lower()
        return any(kw in title_lower for kw in skip_keywords)

    def _clean_latex_response(self, content: str) -> str:
        """清理 LLM 返回的 LaTeX 内容"""
        # 移除代码块标记
        content = re.sub(r"```latex\s*", "", content)
        content = re.sub(r"```\s*$", "", content)
        return content.strip()


class SectionRefineStep(PipelineStep):
    """
    章节润色步骤
    
    使用写作模型润色章节草稿
    """

    def __init__(self, writing_provider: LLMProvider):
        self.writing_provider = writing_provider

    @property
    def name(self) -> str:
        return "section_refine"

    @property
    def description(self) -> str:
        return "润色和改进章节内容"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行章节润色"""
        paper = context.paper
        options = context.llm_options or LLMOptions()

        console.print("[bold blue]✨ 正在润色章节...[/bold blue]")

        all_sections = self._flatten_sections(paper.sections)
        total = len(all_sections)

        for i, section in enumerate(all_sections, 1):
            # 跳过没有草稿的章节
            if not section.draft_latex:
                continue

            # 跳过已润色的章节
            if section.final_latex:
                console.print(f"[dim]跳过 [{i}/{total}] {section.title} (已润色)[/dim]")
                continue

            console.print(f"[cyan]✨ [{i}/{total}] 正在润色: {section.title}[/cyan]")

            prompt = build_section_refine_prompt(paper, section, section.draft_latex)
            response = await self.writing_provider.invoke(
                prompt=prompt,
                options=options,
            )

            if response.content:
                section.final_latex = self._clean_latex_response(response.content)
                console.print(f"[green]  ✓ 完成 ({len(section.final_latex)} 字符)[/green]")
            else:
                # 如果润色失败，使用草稿
                section.final_latex = section.draft_latex
                console.print(f"[yellow]  ⚠ 润色失败，使用草稿[/yellow]")

        paper.status = PaperStatus.FINAL
        context.paper = paper
        console.print("[bold green]✓ 所有章节润色完成[/bold green]")

        return context

    def _flatten_sections(self, sections: list[Section]) -> list[Section]:
        """展平所有章节"""
        result = []
        for s in sections:
            result.append(s)
            if s.children:
                result.extend(self._flatten_sections(s.children))
        return result

    def _clean_latex_response(self, content: str) -> str:
        """清理 LaTeX 响应"""
        content = re.sub(r"```latex\s*", "", content)
        content = re.sub(r"```\s*$", "", content)
        return content.strip()
