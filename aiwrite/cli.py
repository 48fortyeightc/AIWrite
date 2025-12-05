"""
AIWrite CLI 命令行入口

提供三个主要命令：
- suggest-outline: 从用户大纲生成详细小节
- generate-draft: 生成章节草稿
- finalize: 润色并导出 Word
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from .config import (
    load_config,
    load_outline,
    save_outline,
    create_thinking_provider,
    create_writing_provider,
    create_vision_llm_provider,
)
from .models import Paper, PaperStatus, LLMOptions
from .pipeline import OutlineSuggestStep, SectionDraftStep, SectionRefineStep, AbstractGenerateStep, ImageAnalyzeStep, PipelineExecutor
from .pipeline.init_step import OutlineInitializer, run_init_interactive
from .render import LatexRenderer, WordExporter


app = typer.Typer(
    name="aiwrite",
    help="AIWrite - 基于 LLM 的学术论文自动写作系统",
    add_completion=False,
)

console = Console()


@app.command("init")
def init(
    title: str = typer.Option(
        ...,
        "--title", "-t",
        help="论文标题",
    ),
    output_file: Path = typer.Option(
        ...,
        "--output", "-o",
        help="输出的 YAML 配置文件路径",
    ),
    images_dir: Optional[Path] = typer.Option(
        None,
        "--images", "-i",
        help="图片目录路径（用于 AI 自动识别和匹配）",
    ),
    target_words: int = typer.Option(
        10000,
        "--words", "-w",
        help="论文目标字数",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env", "-e",
        help=".env 配置文件路径",
    ),
) -> None:
    """
    从纯文本大纲初始化论文配置

    交互式输入大纲文本，使用 AI 自动：
    1. 扫描并识别图片目录中的所有图片
    2. 将图片自动匹配到合适的章节
    3. 为缺少的图表生成 Mermaid 代码并渲染
    4. 生成完整的 YAML 配置文件

    示例:
        aiwrite init -t "基于Spring Boot的人事管理系统设计与实现" -o hrm.yaml -i examples/img2 -w 10000
    """
    console.print(Panel(
        "[bold]AIWrite 大纲初始化[/bold]\n"
        f"论文标题: {title}\n"
        f"目标字数: {target_words}\n"
        f"图片目录: {images_dir or '（未指定）'}",
        border_style="blue",
    ))

    # 加载配置
    config = load_config(env_file)

    # 创建思考模型 Provider（同时支持文本和图像）
    thinking_provider = create_thinking_provider(config)
    console.print(f"[dim]使用模型: {thinking_provider.model}[/dim]")

    # 运行交互式初始化
    async def run():
        return await run_init_interactive(
            paper_title=title,
            thinking_provider=thinking_provider,
            images_path=images_dir,
            output_path=output_file,
            target_words=target_words,
        )

    try:
        paper = asyncio.run(run())
        console.print(f"\n[green]✓ 初始化完成，配置已保存到: {output_file}[/green]")
        console.print("\n[dim]下一步：[/dim]")
        console.print(f"[bold]aiwrite generate-draft {output_file}[/bold]")
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("suggest-outline")
def suggest_outline(
    input_file: Path = typer.Argument(
        ...,
        help="输入的大纲 YAML 文件路径",
        exists=True,
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="输出的详细大纲文件路径（默认覆盖输入文件）",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env", "-e",
        help=".env 配置文件路径",
    ),
) -> None:
    """
    根据主要章节生成详细的小节结构
    
    使用思考模型（如 doubao-seed-thinking）分析论文标题和主要章节，
    为每个章节生成合理的小节结构。
    """
    console.print(Panel(
        "[bold]AIWrite 大纲生成[/bold]\n"
        f"输入文件: {input_file}",
        border_style="blue",
    ))

    # 加载配置
    config = load_config(env_file)
    
    # 加载大纲
    paper = load_outline(input_file)
    
    console.print(f"[cyan]论文标题: {paper.title}[/cyan]")
    console.print(f"[cyan]主要章节数: {len(paper.sections)}[/cyan]")

    # 创建思考模型 Provider
    thinking_provider = create_thinking_provider(config)

    # 执行大纲生成
    step = OutlineSuggestStep(thinking_provider)
    
    async def run():
        from .models import PipelineContext, LLMOptions
        context = PipelineContext(
            paper=paper,
            llm_options=LLMOptions(
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            ),
        )
        return await step.execute(context)

    result = asyncio.run(run())

    # 显示生成的大纲
    display_outline(result.paper)

    # 保存结果
    output_path = output_file or input_file
    save_outline(result.paper, output_path)
    console.print(f"\n[green]✓ 大纲已保存到: {output_path}[/green]")

    # 提示下一步
    console.print("\n[dim]请检查生成的大纲，确认后使用以下命令生成草稿:[/dim]")
    console.print(f"[bold]aiwrite generate-draft {output_path}[/bold]")


@app.command("generate-draft")
def generate_draft(
    input_file: Path = typer.Argument(
        ...,
        help="输入的大纲 YAML 文件路径",
        exists=True,
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="输出文件路径（默认覆盖输入文件）",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env", "-e",
        help=".env 配置文件路径",
    ),
    use_alt: bool = typer.Option(
        False,
        "--alt",
        help="使用备选写作模型",
    ),
) -> None:
    """
    为论文章节生成草稿内容
    
    使用写作模型（如 DeepSeek-V3 或 Kimi-K2）为每个章节生成 LaTeX 格式的草稿。
    """
    console.print(Panel(
        "[bold]AIWrite 草稿生成[/bold]\n"
        f"输入文件: {input_file}",
        border_style="blue",
    ))

    config = load_config(env_file)
    paper = load_outline(input_file)

    console.print(f"[cyan]论文标题: {paper.title}[/cyan]")

    # 确认大纲
    if paper.status == PaperStatus.PENDING_OUTLINE:
        if not Confirm.ask("大纲尚未确认，是否继续生成草稿？"):
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit()
        paper.status = PaperStatus.OUTLINE_CONFIRMED

    # 创建写作模型
    writing_provider = create_writing_provider(config, use_alt=use_alt)
    console.print(f"[dim]使用模型: {writing_provider.model}[/dim]")

    # 执行草稿生成
    step = SectionDraftStep(writing_provider)

    async def run():
        from .models import PipelineContext, LLMOptions
        context = PipelineContext(
            paper=paper,
            llm_options=LLMOptions(
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            ),
        )
        return await step.execute(context)

    result = asyncio.run(run())

    # 保存结果
    output_path = output_file or input_file
    save_outline(result.paper, output_path)
    console.print(f"\n[green]✓ 草稿已保存到: {output_path}[/green]")

    # 提示下一步
    console.print("\n[dim]请检查生成的草稿，确认后使用以下命令润色并导出:[/dim]")
    console.print(f"[bold]aiwrite finalize {output_path}[/bold]")


@app.command("finalize")
def finalize(
    input_file: Path = typer.Argument(
        ...,
        help="输入的论文 YAML 文件路径",
        exists=True,
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="输出目录（默认为 output/）",
    ),
    images_dir: Optional[Path] = typer.Option(
        None,
        "--images", "-i",
        help="图片目录路径（用于在 Word 中插入真实图片）",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env", "-e",
        help=".env 配置文件路径",
    ),
    skip_refine: bool = typer.Option(
        False,
        "--skip-refine",
        help="跳过润色步骤",
    ),
    skip_abstract: bool = typer.Option(
        False,
        "--skip-abstract",
        help="跳过摘要生成步骤",
    ),
    latex_only: bool = typer.Option(
        False,
        "--latex-only",
        help="只生成 LaTeX，不转换为 Word",
    ),
) -> None:
    """
    润色章节并导出最终文档
    
    1. 使用写作模型润色所有章节
    2. 使用思考模型生成摘要
    3. 组装完整 LaTeX 文档
    4. 导出 Word 文档
    """
    console.print(Panel(
        "[bold]AIWrite 最终导出[/bold]\n"
        f"输入文件: {input_file}",
        border_style="blue",
    ))

    config = load_config(env_file)
    paper = load_outline(input_file)

    console.print(f"[cyan]论文标题: {paper.title}[/cyan]")

    output_dir = output_dir or Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 润色步骤
    if not skip_refine and paper.status != PaperStatus.FINAL:
        writing_provider = create_writing_provider(config)
        step = SectionRefineStep(writing_provider)

        async def run_refine():
            from .models import PipelineContext, LLMOptions
            context = PipelineContext(
                paper=paper,
                llm_options=LLMOptions(
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                ),
            )
            return await step.execute(context)

        result = asyncio.run(run_refine())
        paper = result.paper

    # 摘要生成步骤（使用思考模型）
    if not skip_abstract:
        # 检查是否有摘要章节
        has_abstract = any("摘要" in s.title.lower() or "abstract" in s.title.lower() 
                          for s in paper.sections)
        if has_abstract:
            thinking_provider = create_thinking_provider(config)
            writing_provider = create_writing_provider(config)
            abstract_step = AbstractGenerateStep(thinking_provider, writing_provider)

            async def run_abstract():
                from .models import PipelineContext, LLMOptions
                context = PipelineContext(
                    paper=paper,
                    llm_options=LLMOptions(
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                    ),
                )
                return await abstract_step.execute(context)

            result = asyncio.run(run_abstract())
            paper = result.paper

    # 保存处理后的结果
    save_outline(paper, input_file)

    # 生成 LaTeX
    console.print("\n[bold blue]📄 生成 LaTeX 文档...[/bold blue]")
    latex_renderer = LatexRenderer()
    
    # 生成文件名
    safe_title = "".join(c for c in paper.title if c.isalnum() or c in " _-")[:50]
    latex_path = output_dir / f"{safe_title}.tex"
    latex_renderer.render_to_file(paper, latex_path, use_final=True)
    console.print(f"[green]✓ LaTeX 文件: {latex_path}[/green]")

    # 转换为 Word
    if not latex_only:
        console.print("\n[bold blue]📝 生成 Word 文档...[/bold blue]")
        # 确定图片基础路径
        images_base_path = str(images_dir) if images_dir else str(input_file.parent)
        # 默认使用 docx 方法，因为用户可能没有安装 pandoc
        word_exporter = WordExporter(method="docx", images_base_path=images_base_path)

        word_path = output_dir / f"{safe_title}.docx"
        try:
            word_exporter.export(paper, word_path, use_final=True)
        except Exception as e:
            console.print(f"[red]Word 导出失败: {e}[/red]")
            console.print("[dim]您可以手动使用 pandoc 或其他工具转换 LaTeX 文件[/dim]")

    console.print(Panel(
        f"[bold green]✓ 论文导出完成[/bold green]\n\n"
        f"输出目录: {output_dir}",
        border_style="green",
    ))


@app.command("status")
def status(
    input_file: Path = typer.Argument(
        ...,
        help="论文 YAML 文件路径",
        exists=True,
    ),
) -> None:
    """
    查看论文当前状态和进度
    """
    paper = load_outline(input_file)
    
    console.print(Panel(
        f"[bold]{paper.title}[/bold]",
        title="论文状态",
        border_style="blue",
    ))

    # 状态信息
    status_colors = {
        PaperStatus.PENDING_OUTLINE: "yellow",
        PaperStatus.OUTLINE_CONFIRMED: "cyan",
        PaperStatus.DRAFT: "blue",
        PaperStatus.FINAL: "green",
    }
    status_color = status_colors.get(paper.status, "white")
    console.print(f"状态: [{status_color}]{paper.status.value}[/{status_color}]")

    # 大纲概览
    display_outline(paper)


@app.command("analyze-images")
def analyze_images(
    input_file: Path = typer.Argument(
        ...,
        help="输入的论文 YAML 文件路径",
        exists=True,
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="输出文件路径（默认覆盖输入文件）",
    ),
    images_dir: Optional[Path] = typer.Option(
        None,
        "--images", "-i",
        help="图片目录路径",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env", "-e",
        help=".env 配置文件路径",
    ),
) -> None:
    """
    分析论文中的图片
    
    使用视觉模型（如 doubao-vision）分析 YAML 中定义的图片，
    生成图片描述供写作参考。
    """
    console.print(Panel(
        "[bold]AIWrite 图片分析[/bold]\n"
        f"输入文件: {input_file}",
        border_style="blue",
    ))

    config = load_config(env_file)
    paper = load_outline(input_file)

    console.print(f"[cyan]论文标题: {paper.title}[/cyan]")

    # 确定图片基础路径
    base_path = str(images_dir) if images_dir else str(input_file.parent)

    # 创建视觉模型
    vision_provider = create_vision_llm_provider(config)
    console.print(f"[dim]使用模型: {vision_provider.model}[/dim]")

    # 执行图片识别
    step = ImageAnalyzeStep(vision_provider, base_path=base_path)

    async def run():
        from .models import PipelineContext, LLMOptions
        context = PipelineContext(
            paper=paper,
            llm_options=LLMOptions(
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            ),
        )
        return await step.execute(context)

    result = asyncio.run(run())

    # 保存结果
    output_path = output_file or input_file
    save_outline(result.paper, output_path)
    console.print(f"\n[green]✓ 图片分析结果已保存到: {output_path}[/green]")

    # 显示分析结果概要
    total_figures = sum(len(s.figures) for s in result.paper.get_all_sections())
    analyzed = sum(1 for s in result.paper.get_all_sections() 
                   for f in s.figures if f.description)
    console.print(f"[dim]共 {total_figures} 张图片，已分析 {analyzed} 张[/dim]")


def display_outline(paper: Paper) -> None:
    """显示论文大纲"""
    table = Table(title="论文大纲", show_header=True)
    table.add_column("章节", style="cyan")
    table.add_column("目标字数", justify="right")
    table.add_column("草稿", justify="center")
    table.add_column("润色", justify="center")

    def add_section_row(section, indent: int = 0):
        prefix = "  " * indent
        draft_status = "✓" if section.draft_latex else "-"
        final_status = "✓" if section.final_latex else "-"
        table.add_row(
            f"{prefix}{section.title}",
            str(section.target_words or "-"),
            f"[green]{draft_status}[/green]" if section.draft_latex else f"[dim]{draft_status}[/dim]",
            f"[green]{final_status}[/green]" if section.final_latex else f"[dim]{final_status}[/dim]",
        )
        for child in section.children:
            add_section_row(child, indent + 1)

    for section in paper.sections:
        add_section_row(section)

    console.print(table)


@app.callback()
def main():
    """
    AIWrite - 基于 LLM 的学术论文自动写作系统
    
    从「题目 + 章节大纲」生成完整的 Word 论文
    """
    pass


if __name__ == "__main__":
    app()
