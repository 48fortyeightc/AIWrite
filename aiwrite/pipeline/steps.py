"""
Pipeline 步骤实现
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

import yaml
from rich.console import Console

from ..llm import LLMProvider
from ..models import Paper, Section, PaperStatus, PipelineStep, PipelineContext, LLMOptions, Figure
from ..prompts import (
    build_outline_prompt, 
    build_chapter_draft_prompt, 
    build_section_refine_prompt,
    build_abstract_prompt,
    build_abstract_en_prompt,
    build_image_analysis_prompt,
)

if TYPE_CHECKING:
    from ..llm import VisionProvider


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


class ChapterDraftStep(PipelineStep):
    """
    章节草稿写作步骤（按章节级别生成）
    
    使用写作模型为每个主章节（level=1）生成完整内容
    一次性生成包含所有小节的章节内容
    """

    def __init__(self, writing_provider: LLMProvider):
        self.writing_provider = writing_provider

    @property
    def name(self) -> str:
        return "chapter_draft"

    @property
    def description(self) -> str:
        return "为论文章节生成草稿内容（按章节整体生成）"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行章节草稿生成"""
        import time
        
        paper = context.paper
        options = context.llm_options or LLMOptions()

        console.print("[bold blue]✍️ 正在生成章节草稿（按章节整体生成）...[/bold blue]")

        # 只处理主章节（level=1），不再展平到子章节
        main_chapters = [s for s in paper.sections if s.level == 1]
        total = len(main_chapters)
        
        previous_summaries: list[str] = []
        total_start = time.time()

        for i, chapter in enumerate(main_chapters, 1):
            # 跳过摘要、参考文献等特殊章节
            if self._should_skip_section(chapter):
                continue

            # 跳过已有草稿的章节
            if chapter.draft_latex:
                console.print(f"[dim]跳过 [{i}/{total}] {chapter.title} (已有草稿)[/dim]")
                # 提取摘要用于后续章节
                previous_summaries.append(self._extract_summary(chapter.title, chapter.draft_latex))
                continue

            # 计算本章目标字数
            chapter_words = self._calculate_chapter_words(chapter)
            console.print(f"[cyan]📝 [{i}/{total}] 正在撰写: {chapter.title} (目标 {chapter_words} 字)[/cyan]")

            chapter_start = time.time()
            prompt = build_chapter_draft_prompt(paper, chapter, previous_summaries if previous_summaries else None)
            response = await self.writing_provider.invoke(
                prompt=prompt,
                options=options,
            )

            chapter_elapsed = time.time() - chapter_start
            if chapter_elapsed >= 60:
                time_str = f"{int(chapter_elapsed // 60)}分{int(chapter_elapsed % 60)}秒"
            else:
                time_str = f"{chapter_elapsed:.1f}秒"

            if response.content:
                chapter.draft_latex = self._clean_latex_response(response.content)
                actual_chars = len(chapter.draft_latex)
                console.print(f"[green]  ✓ 完成 ({actual_chars} 字符, 用时 {time_str})[/green]")
                
                # 提取摘要用于后续章节上下文
                previous_summaries.append(self._extract_summary(chapter.title, chapter.draft_latex))
            else:
                console.print(f"[red]  ✗ 生成失败 (用时 {time_str})[/red]")

        paper.status = PaperStatus.DRAFT
        context.paper = paper
        
        total_elapsed = time.time() - total_start
        if total_elapsed >= 60:
            total_time_str = f"{int(total_elapsed // 60)}分{int(total_elapsed % 60)}秒"
        else:
            total_time_str = f"{total_elapsed:.1f}秒"
        console.print(f"[bold green]✓ 所有章节草稿生成完成 (总用时 {total_time_str})[/bold green]")

        return context

    def _calculate_chapter_words(self, chapter: Section) -> int:
        """计算章节目标字数"""
        if chapter.target_words:
            return chapter.target_words
        # 从子章节累加
        if chapter.children:
            return sum(c.target_words or 500 for c in chapter.children)
        return 2000

    def _extract_summary(self, title: str, content: str, max_chars: int = 200) -> str:
        """提取章节内容摘要（用于给后续章节提供上下文）"""
        # 简单提取前200字作为摘要
        clean_content = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", content)
        clean_content = re.sub(r"\\[a-zA-Z]+", "", clean_content)
        clean_content = re.sub(r"\s+", " ", clean_content).strip()
        summary = clean_content[:max_chars] + "..." if len(clean_content) > max_chars else clean_content
        return f"{title}: {summary}"

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


# 保留旧的 SectionDraftStep 用于向后兼容，但实际委托给 ChapterDraftStep
class SectionDraftStep(PipelineStep):
    """
    章节草稿写作步骤（向后兼容，实际使用 ChapterDraftStep）
    
    使用写作模型为每个章节生成草稿内容
    """

    def __init__(self, writing_provider: LLMProvider):
        self.writing_provider = writing_provider
        self._chapter_step = ChapterDraftStep(writing_provider)

    @property
    def name(self) -> str:
        return "section_draft"

    @property
    def description(self) -> str:
        return "为论文章节生成草稿内容"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行章节草稿生成（委托给 ChapterDraftStep）"""
        return await self._chapter_step.execute(context)


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
        """执行章节润色（按主章节整体润色）"""
        import time
        
        paper = context.paper
        options = context.llm_options or LLMOptions()

        console.print("[bold blue]✨ 正在润色章节...[/bold blue]")

        # 只处理主章节（level=1），跳过摘要等特殊章节
        main_chapters = [s for s in paper.sections if s.level == 1]
        total = len(main_chapters)
        total_start = time.time()

        for i, chapter in enumerate(main_chapters, 1):
            # 跳过没有草稿的章节
            if not chapter.draft_latex:
                continue

            # 跳过已润色的章节
            if chapter.final_latex:
                console.print(f"[dim]跳过 [{i}/{total}] {chapter.title} (已润色)[/dim]")
                continue

            console.print(f"[cyan]✨ [{i}/{total}] 正在润色: {chapter.title}[/cyan]")

            chapter_start = time.time()
            prompt = build_section_refine_prompt(paper, chapter, chapter.draft_latex)
            response = await self.writing_provider.invoke(
                prompt=prompt,
                options=options,
            )

            chapter_elapsed = time.time() - chapter_start
            if chapter_elapsed >= 60:
                time_str = f"{int(chapter_elapsed // 60)}分{int(chapter_elapsed % 60)}秒"
            else:
                time_str = f"{chapter_elapsed:.1f}秒"

            if response.content:
                chapter.final_latex = self._clean_latex_response(response.content)
                console.print(f"[green]  ✓ 完成 ({len(chapter.final_latex)} 字符, 用时 {time_str})[/green]")
            else:
                # 如果润色失败，使用草稿
                chapter.final_latex = chapter.draft_latex
                console.print(f"[yellow]  ⚠ 润色失败，使用草稿 (用时 {time_str})[/yellow]")

        paper.status = PaperStatus.FINAL
        context.paper = paper
        
        total_elapsed = time.time() - total_start
        if total_elapsed >= 60:
            total_time_str = f"{int(total_elapsed // 60)}分{int(total_elapsed % 60)}秒"
        else:
            total_time_str = f"{total_elapsed:.1f}秒"
        console.print(f"[bold green]✓ 所有章节润色完成 (总用时 {total_time_str})[/bold green]")

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


class AbstractGenerateStep(PipelineStep):
    """
    摘要生成步骤
    
    在全文内容完成后，使用思考模型生成摘要
    """

    def __init__(self, thinking_provider: LLMProvider, writing_provider: LLMProvider | None = None):
        """
        初始化摘要生成步骤
        
        Args:
            thinking_provider: 思考模型（用于生成中文摘要）
            writing_provider: 写作模型（用于生成英文摘要，可选）
        """
        self.thinking_provider = thinking_provider
        self.writing_provider = writing_provider or thinking_provider

    @property
    def name(self) -> str:
        return "abstract_generate"

    @property
    def description(self) -> str:
        return "根据全文内容生成摘要"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行摘要生成"""
        paper = context.paper
        options = context.llm_options or LLMOptions()

        console.print("[bold blue]📋 正在生成摘要...[/bold blue]")

        # 收集全文内容
        full_content = self._collect_full_content(paper)
        if not full_content:
            console.print("[yellow]⚠ 论文内容为空，无法生成摘要[/yellow]")
            return context

        # 查找摘要章节
        abstract_section = self._find_abstract_section(paper)
        abstract_en_section = self._find_abstract_en_section(paper)

        # 生成中文摘要
        if abstract_section and not abstract_section.final_latex:
            console.print("[cyan]📝 正在生成中文摘要...[/cyan]")
            
            prompt = build_abstract_prompt(paper, full_content)
            response = await self.thinking_provider.invoke(
                prompt=prompt,
                options=options,
            )

            if response.content:
                abstract_section.draft_latex = response.content
                abstract_section.final_latex = response.content
                console.print(f"[green]  ✓ 中文摘要完成 ({len(response.content)} 字符)[/green]")
                
                # 如果有思考过程，显示
                if response.reasoning_content:
                    console.print("[dim]  (思考模型分析了全文结构)[/dim]")

        # 生成英文摘要
        if abstract_en_section and abstract_section and abstract_section.final_latex:
            if not abstract_en_section.final_latex:
                console.print("[cyan]📝 正在生成英文摘要...[/cyan]")
                
                prompt = build_abstract_en_prompt(paper, abstract_section.final_latex)
                response = await self.writing_provider.invoke(
                    prompt=prompt,
                    options=options,
                )

                if response.content:
                    abstract_en_section.draft_latex = response.content
                    abstract_en_section.final_latex = response.content
                    console.print(f"[green]  ✓ 英文摘要完成 ({len(response.content)} 字符)[/green]")

        context.paper = paper
        console.print("[bold green]✓ 摘要生成完成[/bold green]")

        return context

    def _collect_full_content(self, paper: Paper) -> str:
        """收集论文全文内容（用于生成摘要）"""
        content_parts = []
        for section in paper.sections:
            # 跳过摘要和参考文献
            if self._is_abstract_section(section) or self._is_reference_section(section):
                continue
            
            content = section.final_latex or section.draft_latex
            if content:
                content_parts.append(f"## {section.title}\n{content}")
        
        return "\n\n".join(content_parts)

    def _find_abstract_section(self, paper: Paper) -> Section | None:
        """查找中文摘要章节"""
        for section in paper.sections:
            title_lower = section.title.lower()
            if "摘要" in title_lower and "abstract" not in title_lower:
                return section
        return None

    def _find_abstract_en_section(self, paper: Paper) -> Section | None:
        """查找英文摘要章节"""
        for section in paper.sections:
            title_lower = section.title.lower()
            if "abstract" in title_lower:
                return section
        return None

    def _is_abstract_section(self, section: Section) -> bool:
        """判断是否是摘要章节"""
        title_lower = section.title.lower()
        return "摘要" in title_lower or "abstract" in title_lower

    def _is_reference_section(self, section: Section) -> bool:
        """判断是否是参考文献章节"""
        title_lower = section.title.lower()
        return "参考文献" in title_lower or "references" in title_lower


class ImageAnalyzeStep(PipelineStep):
    """
    图片识别步骤
    
    使用视觉模型分析论文中的图片，生成描述信息
    """

    def __init__(self, vision_provider: "VisionProvider", base_path: str = ""):
        from ..llm import VisionProvider
        self.vision_provider: VisionProvider = vision_provider
        self.base_path = base_path  # 图片的基础路径

    @property
    def name(self) -> str:
        return "image_analyze"

    @property
    def description(self) -> str:
        return "分析论文中的图片，生成描述"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行图片识别"""
        from pathlib import Path
        from ..prompts import build_image_analysis_prompt

        paper = context.paper
        console.print("[bold blue]🖼️ 正在分析图片...[/bold blue]")

        # 收集所有图片
        all_figures = self._collect_all_figures(paper)
        
        if not all_figures:
            console.print("[yellow]未发现需要分析的图片[/yellow]")
            return context

        console.print(f"[dim]发现 {len(all_figures)} 张图片需要分析[/dim]")

        options = context.llm_options or LLMOptions()

        for section, figure in all_figures:
            # 构建图片完整路径
            if self.base_path:
                image_path = Path(self.base_path) / figure.path
            else:
                image_path = Path(figure.path)

            if not image_path.exists():
                console.print(f"[yellow]⚠ 图片不存在: {image_path}[/yellow]")
                continue

            console.print(f"[dim]  分析图片: {figure.caption}[/dim]")

            # 构建分析提示词
            prompt = build_image_analysis_prompt(
                paper_title=paper.title,
                figure_caption=figure.caption,
                section_title=section.title,
            )

            try:
                # 调用视觉模型
                response = await self.vision_provider.analyze_image(
                    image_path=str(image_path),
                    prompt=prompt,
                    options=options,
                )

                if response.content:
                    figure.description = response.content
                    console.print(f"[green]  ✓ {figure.caption} 分析完成[/green]")
                else:
                    console.print(f"[yellow]  ⚠ {figure.caption} 分析无结果[/yellow]")

            except Exception as e:
                console.print(f"[red]  ✗ {figure.caption} 分析失败: {e}[/red]")

        context.paper = paper
        console.print("[bold green]✓ 图片分析完成[/bold green]")

        return context

    def _collect_all_figures(self, paper: Paper) -> list[tuple[Section, "Figure"]]:
        """收集所有章节中的图片"""
        from ..models import Figure
        
        results: list[tuple[Section, Figure]] = []

        def collect_from_section(section: Section):
            for figure in section.figures:
                results.append((section, figure))
            for child in section.children:
                collect_from_section(child)

        for section in paper.sections:
            collect_from_section(section)

        return results

