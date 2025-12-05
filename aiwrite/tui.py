"""
AIWrite 交互式终端界面 (TUI)

提供友好的交互式操作界面，无需记忆命令行参数
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional, List

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import (
    load_config,
    load_outline,
    save_outline,
    create_thinking_provider,
    create_writing_provider,
)
from .models import Paper, PaperStatus, PipelineContext, LLMOptions
from .pipeline import (
    OutlineSuggestStep,
    SectionDraftStep,
    SectionRefineStep,
    AbstractGenerateStep,
)
from .pipeline.init_step import OutlineInitializer
from .render import LatexRenderer, WordExporter

console = Console()


def has_abstract(paper: Paper) -> bool:
    """检查论文是否已有摘要"""
    for section in paper.sections:
        title_lower = section.title.lower()
        if "摘要" in title_lower and section.final_latex:
            return True
    return bool(paper.abstract_cn)


# 自定义样式
STYLE = questionary.Style([
    ("qmark", "fg:cyan bold"),
    ("question", "bold"),
    ("answer", "fg:green"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
])


def clear_screen():
    """清屏"""
    console.clear()


def show_banner():
    """显示欢迎横幅"""
    banner = """
    ╭─────────────────────────────────────────╮
    │     🚀 AIWrite - 论文自动生成系统       │
    │                                         │
    │   从「题目 + 大纲」到「完整论文」       │
    ╰─────────────────────────────────────────╯
    """
    console.print(banner, style="cyan")


def show_main_menu() -> str:
    """显示主菜单"""
    choices = [
        questionary.Choice("📝 新建论文（从头开始）", value="new"),
        questionary.Choice("📂 继续写作（选择已有项目）", value="continue"),
        questionary.Choice("🖼️  生成图表（Mermaid）", value="diagram"),
        questionary.Choice("⚙️  设置", value="settings"),
        questionary.Choice("❓ 帮助", value="help"),
        questionary.Choice("🚪 退出", value="quit"),
    ]
    
    return questionary.select(
        "请选择操作：",
        choices=choices,
        style=STYLE,
    ).ask()


def new_paper_flow():
    """新建论文流程"""
    console.print("\n[bold cyan]━━━ 📝 新建论文 ━━━[/bold cyan]\n")
    
    # 1. 输入标题
    title = questionary.text(
        "论文标题：",
        style=STYLE,
    ).ask()
    
    if not title:
        console.print("[yellow]已取消[/yellow]")
        return
    
    # 2. 目标字数
    words_str = questionary.text(
        "目标字数：",
        default="10000",
        style=STYLE,
    ).ask()
    
    try:
        target_words = int(words_str)
    except ValueError:
        target_words = 10000
    
    # 3. 图片目录（可选）
    has_images = questionary.confirm(
        "是否有系统截图/图片需要插入？",
        default=False,
        style=STYLE,
    ).ask()
    
    images_dir = None
    if has_images:
        images_dir = questionary.path(
            "图片目录路径：",
            style=STYLE,
        ).ask()
        if images_dir:
            # 去掉用户可能输入的引号
            images_dir = images_dir.strip().strip('"').strip("'")
    
    # 4. 大纲输入方式
    outline_method = questionary.select(
        "大纲输入方式：",
        choices=[
            questionary.Choice("从文件读取 (.txt)", value="file"),
            questionary.Choice("使用模板快速生成", value="template"),
            questionary.Choice("手动输入（多行）", value="manual"),
        ],
        style=STYLE,
    ).ask()
    
    outline_text = None
    
    if outline_method == "file":
        outline_file = questionary.path(
            "大纲文件路径：",
            style=STYLE,
        ).ask()
        if outline_file:
            # 去掉用户可能输入的引号
            outline_file = outline_file.strip().strip('"').strip("'")
            if Path(outline_file).exists():
                outline_text = Path(outline_file).read_text(encoding="utf-8")
            else:
                console.print(f"[red]文件不存在: {outline_file}[/red]")
                return
        else:
            console.print("[red]未输入路径[/red]")
            return
            
    elif outline_method == "template":
        template_type = questionary.select(
            "选择模板类型：",
            choices=[
                questionary.Choice("管理系统类（Spring Boot / Vue）", value="management"),
                questionary.Choice("深度学习/AI 类", value="ai"),
                questionary.Choice("通用毕业论文", value="general"),
            ],
            style=STYLE,
        ).ask()
        outline_text = get_template(template_type)
        
    elif outline_method == "manual":
        console.print("[dim]请输入大纲（每行一个章节，输入空行两次或输入 END 结束）：[/dim]")
        lines = []
        empty_count = 0
        try:
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                    lines.append(line)
                else:
                    empty_count = 0
                    lines.append(line)
        except EOFError:
            pass
        outline_text = "\n".join(lines).strip()
    
    if not outline_text:
        console.print("[yellow]未输入大纲，已取消[/yellow]")
        return
    
    # 5. 输出文件名
    default_filename = title.replace(" ", "_").replace("/", "_")[:30] + ".yaml"
    output_file = questionary.text(
        "保存配置文件名：",
        default=default_filename,
        style=STYLE,
    ).ask()
    
    if not output_file.endswith(".yaml"):
        output_file += ".yaml"
    
    output_path = Path(output_file)
    
    # 6. 确认信息
    console.print("\n[bold]确认信息：[/bold]")
    console.print(f"  标题：{title}")
    console.print(f"  字数：{target_words}")
    console.print(f"  图片：{images_dir or '无'}")
    console.print(f"  输出：{output_path}")
    
    confirm = questionary.confirm(
        "\n确认开始生成？",
        default=True,
        style=STYLE,
    ).ask()
    
    if not confirm:
        console.print("[yellow]已取消[/yellow]")
        return
    
    # 7. 执行初始化
    console.print("\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在初始化...", total=None)
        
        try:
            config = load_config()
            thinking_provider = create_thinking_provider(config)
            
            progress.update(task, description="正在解析大纲...")
            
            async def run_init():
                images_path = Path(images_dir) if images_dir else None
                
                initializer = OutlineInitializer(
                    thinking_provider=thinking_provider,
                    images_path=images_path,
                )
                
                # 扫描图片和表格
                images = []
                tables = []
                
                if images_path and images_path.exists():
                    progress.update(task, description="正在扫描图片...")
                    images = await initializer.scan_images()
                    tables = initializer.scan_tables()  # 同步方法
                
                progress.update(task, description="正在解析大纲...")
                config = await initializer.parse_outline(
                    paper_title=title,
                    outline_text=outline_text,
                    images=images,
                    tables=tables,
                    target_words=target_words,
                )
                
                # 构建 Paper 对象
                paper = initializer.build_paper(config)
                
                return paper
            
            paper = asyncio.run(run_init())
            
            # 保存配置
            save_outline(paper, output_path)
            
        except Exception as e:
            console.print(f"\n[red]错误: {e}[/red]")
            return
    
    console.print(f"\n[green]✓ 配置已保存到: {output_path}[/green]")
    
    # 显示大纲预览
    display_outline_preview(paper)
    
    # 8. 下一步选项
    next_action = questionary.select(
        "\n下一步：",
        choices=[
            questionary.Choice("🚀 立即生成论文草稿", value="draft"),
            questionary.Choice("⚡ 一键全流程（草稿 + 润色 + 导出）", value="all"),
            questionary.Choice("📋 返回主菜单", value="menu"),
        ],
        style=STYLE,
    ).ask()
    
    if next_action == "draft":
        generate_draft_flow(output_path, images_dir)
    elif next_action == "all":
        full_pipeline_flow(output_path, images_dir)


def continue_paper_flow():
    """继续写作流程"""
    console.print("\n[bold cyan]━━━ 📂 继续写作 ━━━[/bold cyan]\n")
    
    # 扫描已有的 YAML 文件
    yaml_files = list(Path(".").glob("*.yaml")) + list(Path("examples").glob("*.yaml"))
    
    if not yaml_files:
        console.print("[yellow]未找到任何 YAML 配置文件[/yellow]")
        console.print("[dim]请先使用「新建论文」创建配置[/dim]")
        return
    
    # 构建选项
    choices = []
    for f in yaml_files[:20]:  # 最多显示 20 个
        try:
            paper = load_outline(f)
            status_icon = {
                PaperStatus.PENDING_OUTLINE: "⏳",
                PaperStatus.PENDING_CONFIRMATION: "📋",
                PaperStatus.OUTLINE_CONFIRMED: "✅",
                PaperStatus.DRAFT: "✏️",
                PaperStatus.FINAL: "✨",
            }.get(paper.status, "📄")
            choices.append(questionary.Choice(
                f"{status_icon} {paper.title[:40]} ({f.name})",
                value=str(f),
            ))
        except Exception:
            choices.append(questionary.Choice(f"❓ {f.name}", value=str(f)))
    
    choices.append(questionary.Choice("📁 输入其他路径", value="other"))
    choices.append(questionary.Choice("↩️  返回", value="back"))
    
    selected = questionary.select(
        "选择项目：",
        choices=choices,
        style=STYLE,
    ).ask()
    
    if selected == "back":
        return
    
    if selected == "other":
        selected = questionary.path(
            "配置文件路径：",
            style=STYLE,
        ).ask()
    
    if not selected or not Path(selected).exists():
        console.print("[red]文件不存在[/red]")
        return
    
    file_path = Path(selected)
    paper = load_outline(file_path)
    
    # 显示当前状态
    console.print(f"\n[bold]{paper.title}[/bold]")
    console.print(f"状态: {paper.status.value}")
    display_outline_preview(paper)
    
    # 根据状态提供选项
    choices = []
    
    if paper.status == PaperStatus.OUTLINE_CONFIRMED:
        choices.append(questionary.Choice("✏️  生成草稿", value="draft"))
    
    if paper.status in [PaperStatus.OUTLINE_CONFIRMED, PaperStatus.DRAFT]:
        choices.append(questionary.Choice("✨ 润色内容", value="refine"))
    
    choices.append(questionary.Choice("⚡ 一键完成剩余流程", value="all"))
    choices.append(questionary.Choice("📄 导出 Word", value="export"))
    choices.append(questionary.Choice("📊 查看详细状态", value="status"))
    choices.append(questionary.Choice("↩️  返回", value="back"))
    
    action = questionary.select(
        "选择操作：",
        choices=choices,
        style=STYLE,
    ).ask()
    
    # 需要图片目录的操作：一键完成、导出、草稿（如果后续要导出）
    images_dir: str | None = None
    if action in ["draft", "refine", "all", "export"]:
        if questionary.confirm("是否有图片需要插入 Word？", default=False, style=STYLE).ask():
            images_dir = questionary.path("图片目录：", style=STYLE).ask()
            if images_dir:
                images_dir = images_dir.strip('"')
    
    if action == "draft":
        generate_draft_flow(file_path, images_dir)
    elif action == "refine":
        refine_flow(file_path, images_dir)
    elif action == "all":
        full_pipeline_flow(file_path, images_dir)
    elif action == "export":
        export_flow(file_path, images_dir)
    elif action == "status":
        show_detailed_status(paper)


def generate_draft_flow(file_path: Path, images_dir: str | None = None):
    """生成草稿流程"""
    console.print("\n[bold cyan]━━━ ✏️ 生成草稿 ━━━[/bold cyan]\n")
    
    paper = load_outline(file_path)
    config = load_config()
    writing_provider = create_writing_provider(config)
    
    console.print(f"[dim]使用模型: {writing_provider.model}[/dim]\n")
    
    # 统计需要生成的章节（按章整体生成）
    main_chapters = [s for s in paper.sections if s.level == 1 and not s.draft_latex]
    
    if not main_chapters:
        console.print("[green]所有章节已有草稿，无需生成[/green]")
    else:
        console.print(f"需要生成 {len(main_chapters)} 章的草稿\n")
        
        step = SectionDraftStep(writing_provider)
        
        # 直接运行，step 内部会显示进度
        async def run():
            context = PipelineContext(
                paper=paper,
                llm_options=LLMOptions(
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                ),
            )
            return await step.execute(context)
        
        try:
            result = asyncio.run(run())
            paper = result.paper
        except Exception as e:
            console.print(f"\n[red]错误: {e}[/red]")
            return
        
        # 保存结果
        save_outline(paper, file_path)
        console.print(f"\n[green]✓ 草稿已保存到: {file_path}[/green]")
    
    # 下一步
    next_action = questionary.select(
        "\n下一步：",
        choices=[
            questionary.Choice("✨ 润色内容", value="refine"),
            questionary.Choice("📄 直接导出 Word", value="export"),
            questionary.Choice("↩️  返回主菜单", value="menu"),
        ],
        style=STYLE,
    ).ask()
    
    if next_action == "refine":
        refine_flow(file_path, images_dir)
    elif next_action == "export":
        export_flow(file_path, images_dir)


def refine_flow(file_path: Path, images_dir: str | None = None):
    """润色流程"""
    console.print("\n[bold cyan]━━━ ✨ 润色内容 ━━━[/bold cyan]\n")
    
    paper = load_outline(file_path)
    config = load_config()
    writing_provider = create_writing_provider(config)
    
    step = SectionRefineStep(writing_provider)
    
    # 直接运行，step 内部会显示进度
    async def run():
        context = PipelineContext(
            paper=paper,
            llm_options=LLMOptions(
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            ),
        )
        return await step.execute(context)
    
    try:
        result = asyncio.run(run())
        paper = result.paper
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        return
    
    save_outline(paper, file_path)
    console.print(f"\n[green]✓ 润色完成，已保存[/green]")
    
    # 下一步
    if questionary.confirm("是否导出 Word？", default=True, style=STYLE).ask():
        export_flow(file_path, images_dir)


def export_flow(file_path: Path, images_dir: Optional[str] = None):
    """导出流程"""
    console.print("\n[bold cyan]━━━ 📄 导出文档 ━━━[/bold cyan]\n")
    
    paper = load_outline(file_path)
    
    # 输出目录
    default_output = Path("output") / file_path.stem
    output_dir = questionary.text(
        "输出目录：",
        default=str(default_output),
        style=STYLE,
    ).ask()
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 图片目录（只在没有传入时询问）
    if not images_dir:
        has_images = questionary.confirm(
            "是否需要在 Word 中插入图片？",
            default=False,
            style=STYLE,
        ).ask()
        
        if has_images:
            images_dir = questionary.path(
                "图片目录路径：",
                style=STYLE,
            ).ask()
            if images_dir:
                images_dir = images_dir.strip().strip('"').strip("'")
    else:
        console.print(f"[dim]图片目录: {images_dir}[/dim]")
    
    try:
        config = load_config()
        
        # 生成摘要（如果没有）
        if not has_abstract(paper):
            console.print("[cyan]📋 正在生成摘要...[/cyan]")
            thinking_provider = create_thinking_provider(config)
            abstract_step = AbstractGenerateStep(thinking_provider)
            
            async def gen_abstract():
                context = PipelineContext(paper=paper, llm_options=LLMOptions())
                return await abstract_step.execute(context)
            
            result = asyncio.run(gen_abstract())
            paper = result.paper
        
        console.print("[cyan]📄 正在生成 LaTeX...[/cyan]")
        
        # 生成 LaTeX
        renderer = LatexRenderer()
        latex_content = renderer.render(paper)
        latex_file = output_path / f"{paper.title}.tex"
        latex_file.write_text(latex_content, encoding="utf-8")
        
        console.print("[cyan]📝 正在生成 Word...[/cyan]")
        
        # 生成 Word
        exporter = WordExporter()
        word_file = output_path / f"{paper.title}.docx"
        images_path = Path(images_dir) if images_dir else None
        exporter.export(paper, word_file, images_base_path=images_path)
        
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        return
    
    console.print(f"\n[green]✓ 导出完成！[/green]")
    console.print(f"  LaTeX: {latex_file}")
    console.print(f"  Word:  {word_file}")
    
    # 打开输出目录
    if questionary.confirm("是否打开输出目录？", default=True, style=STYLE).ask():
        import subprocess
        subprocess.run(["explorer", str(output_path)], shell=True)


def full_pipeline_flow(file_path: Path, images_dir: Optional[str] = None):
    """一键全流程"""
    console.print("\n[bold cyan]━━━ ⚡ 一键全流程 ━━━[/bold cyan]\n")
    
    paper = load_outline(file_path)
    
    steps = []
    if paper.status == PaperStatus.OUTLINE_CONFIRMED:
        steps.append("生成草稿")
    if paper.status in [PaperStatus.OUTLINE_CONFIRMED, PaperStatus.DRAFT]:
        steps.append("润色内容")
    steps.append("生成摘要")
    steps.append("导出文档")
    
    console.print(f"将依次执行: {' → '.join(steps)}\n")
    
    if not questionary.confirm("确认开始？", default=True, style=STYLE).ask():
        return
    
    # 询问图片目录
    if not images_dir:
        has_images = questionary.confirm(
            "是否需要在 Word 中插入图片？",
            default=False,
            style=STYLE,
        ).ask()
        
        if has_images:
            images_dir = questionary.path(
                "图片目录路径：",
                style=STYLE,
            ).ask()
    
    # 输出目录
    default_output = Path("output") / file_path.stem
    output_dir = questionary.text(
        "输出目录：",
        default=str(default_output),
        style=STYLE,
    ).ask()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    config = load_config()
    
    try:
        # 1. 生成草稿
        if paper.status == PaperStatus.OUTLINE_CONFIRMED:
            console.print("\n[bold blue]━━━ [1/4] 生成草稿 ━━━[/bold blue]\n")
            writing_provider = create_writing_provider(config)
            step = SectionDraftStep(writing_provider)
            
            async def run_draft():
                context = PipelineContext(paper=paper, llm_options=LLMOptions())
                return await step.execute(context)
            
            result = asyncio.run(run_draft())
            paper = result.paper
            save_outline(paper, file_path)
        
        # 2. 润色
        if paper.status in [PaperStatus.OUTLINE_CONFIRMED, PaperStatus.DRAFT]:
            console.print("\n[bold blue]━━━ [2/4] 润色内容 ━━━[/bold blue]\n")
            writing_provider = create_writing_provider(config)
            step = SectionRefineStep(writing_provider)
            
            async def run_refine():
                context = PipelineContext(paper=paper, llm_options=LLMOptions())
                return await step.execute(context)
            
            result = asyncio.run(run_refine())
            paper = result.paper
            save_outline(paper, file_path)
        
        # 3. 生成摘要
        if not has_abstract(paper):
            console.print("\n[bold blue]━━━ [3/4] 生成摘要 ━━━[/bold blue]\n")
            thinking_provider = create_thinking_provider(config)
            step = AbstractGenerateStep(thinking_provider)
            
            async def run_abstract():
                context = PipelineContext(paper=paper, llm_options=LLMOptions())
                return await step.execute(context)
            
            result = asyncio.run(run_abstract())
            paper = result.paper
            save_outline(paper, file_path)
        
        # 4. 导出
        console.print("\n[bold blue]━━━ [4/4] 导出文档 ━━━[/bold blue]\n")
        
        # LaTeX
        console.print("[cyan]📄 正在生成 LaTeX...[/cyan]")
        renderer = LatexRenderer()
        latex_content = renderer.render(paper)
        latex_file = output_path / f"{paper.title}.tex"
        latex_file.write_text(latex_content, encoding="utf-8")
        
        # Word
        console.print("[cyan]📝 正在生成 Word...[/cyan]")
        exporter = WordExporter()
        word_file = output_path / f"{paper.title}.docx"
        images_path = Path(images_dir) if images_dir else None
        exporter.export(paper, word_file, images_base_path=images_path)
        
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        import traceback
        traceback.print_exc()
        return
    
    console.print(f"\n[bold green]✅ 全部完成！[/bold green]")
    console.print(f"  LaTeX: {latex_file}")
    console.print(f"  Word:  {word_file}")
    
    # 打开输出目录
    if questionary.confirm("是否打开输出目录？", default=True, style=STYLE).ask():
        import subprocess
        subprocess.run(["explorer", str(output_path)], shell=True)


def diagram_flow():
    """图表生成流程"""
    console.print("\n[bold cyan]━━━ 🖼️ 生成图表 ━━━[/bold cyan]\n")
    
    diagram_type = questionary.select(
        "选择图表类型：",
        choices=[
            questionary.Choice("流程图 (flowchart)", value="flowchart"),
            questionary.Choice("时序图 (sequenceDiagram)", value="sequence"),
            questionary.Choice("ER图 (erDiagram)", value="er"),
            questionary.Choice("类图 (classDiagram)", value="class"),
            questionary.Choice("思维导图 (mindmap)", value="mindmap"),
            questionary.Choice("饼图 (pie)", value="pie"),
            questionary.Choice("↩️  返回", value="back"),
        ],
        style=STYLE,
    ).ask()
    
    if diagram_type == "back":
        return
    
    # 显示模板
    template = get_diagram_template(diagram_type)
    console.print("\n[dim]参考模板：[/dim]")
    console.print(f"[cyan]{template}[/cyan]\n")
    
    console.print("[dim]请输入 Mermaid 代码（按 Ctrl+D 或 Ctrl+Z 结束）：[/dim]")
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    mermaid_code = "\n".join(lines)
    
    if not mermaid_code.strip():
        console.print("[yellow]未输入代码[/yellow]")
        return
    
    # 输出文件名
    output_file = questionary.text(
        "输出文件名：",
        default="diagram.png",
        style=STYLE,
    ).ask()
    
    if not output_file.endswith(".png"):
        output_file += ".png"
    
    # 渲染
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在渲染...", total=None)
        
        try:
            from .diagram.mermaid import MermaidRenderer
            renderer = MermaidRenderer()
            renderer.render_to_file(mermaid_code, output_file)
        except Exception as e:
            console.print(f"\n[red]错误: {e}[/red]")
            return
    
    console.print(f"\n[green]✓ 图表已保存到: {output_file}[/green]")
    
    # 打开图片
    if questionary.confirm("是否打开查看？", default=True, style=STYLE).ask():
        import subprocess
        subprocess.run(["explorer", output_file], shell=True)


def settings_flow():
    """设置流程"""
    console.print("\n[bold cyan]━━━ ⚙️ 设置 ━━━[/bold cyan]\n")
    
    try:
        config = load_config()
        console.print("[bold]当前配置：[/bold]")
        console.print(f"  思考模型: {config.thinking_model}")
        console.print(f"  写作模型: {config.writing_model}")
        console.print(f"  最大 Token: {config.max_tokens}")
        console.print(f"  温度: {config.temperature}")
    except Exception as e:
        console.print(f"[red]无法加载配置: {e}[/red]")
        console.print("[dim]请确保 .env 文件存在且配置正确[/dim]")
    
    console.print("\n[dim]配置文件: .env[/dim]")
    
    questionary.press_any_key_to_continue("按任意键返回...").ask()


def help_flow():
    """帮助信息"""
    console.print("\n[bold cyan]━━━ ❓ 帮助 ━━━[/bold cyan]\n")
    
    help_text = """
[bold]使用流程：[/bold]

1️⃣  [cyan]新建论文[/cyan]
   输入标题 → 选择大纲来源 → 生成配置文件

2️⃣  [cyan]生成草稿[/cyan]
   AI 自动为每个章节生成正文内容

3️⃣  [cyan]润色内容[/cyan]
   AI 优化语言表达、补充细节

4️⃣  [cyan]导出文档[/cyan]
   生成 LaTeX 源码和 Word 文档

[bold]快捷操作：[/bold]

• 选择「一键全流程」可自动完成所有步骤
• 图片会在导出 Word 时自动插入
• 中途退出后可通过「继续写作」恢复

[bold]配置说明：[/bold]

在 .env 文件中配置 API 密钥：
• THINKING_API_KEY - 思考模型密钥
• WRITING_API_KEY - 写作模型密钥
"""
    console.print(help_text)
    
    questionary.press_any_key_to_continue("按任意键返回...").ask()


def display_outline_preview(paper: Paper):
    """显示大纲预览"""
    table = Table(title="大纲预览", show_header=True, width=60)
    table.add_column("章节", style="cyan")
    table.add_column("状态", justify="center", width=8)
    
    def add_row(section, indent=0):
        prefix = "  " * indent
        status = "✓" if section.draft_latex else "-"
        table.add_row(
            f"{prefix}{section.title[:40]}",
            f"[green]{status}[/green]" if section.draft_latex else f"[dim]{status}[/dim]",
        )
        for child in section.children[:5]:  # 最多显示 5 个子节
            add_row(child, indent + 1)
        if len(section.children) > 5:
            table.add_row(f"{prefix}  ... 还有 {len(section.children) - 5} 个", "[dim]-[/dim]")
    
    for section in paper.sections[:7]:  # 最多显示 7 章
        add_row(section)
    
    if len(paper.sections) > 7:
        table.add_row(f"... 还有 {len(paper.sections) - 7} 章", "-")
    
    console.print(table)


def show_detailed_status(paper: Paper):
    """显示详细状态"""
    console.print(f"\n[bold]{paper.title}[/bold]")
    console.print(f"状态: {paper.status.value}")
    console.print(f"目标字数: {paper.target_words}")
    console.print(f"关键词: {', '.join(paper.keywords)}")
    
    if has_abstract(paper):
        console.print(f"\n[green]✓ 已生成摘要[/green]")
    else:
        console.print(f"\n[dim]- 未生成摘要[/dim]")
    
    # 统计
    all_sections = paper.get_all_sections()
    drafted = sum(1 for s in all_sections if s.draft_latex)
    refined = sum(1 for s in all_sections if s.final_latex)
    
    console.print(f"\n章节统计:")
    console.print(f"  总章节数: {len(all_sections)}")
    console.print(f"  已生成草稿: {drafted}")
    console.print(f"  已润色: {refined}")
    
    display_outline_preview(paper)
    
    questionary.press_any_key_to_continue("按任意键返回...").ask()


def get_template(template_type: str) -> str:
    """获取大纲模板"""
    templates = {
        "management": """第1章 绪论
1.1 研究背景与意义
1.2 国内外研究现状
1.3 研究内容与方法
1.4 论文组织结构

第2章 相关技术介绍
2.1 Spring Boot框架
2.2 Vue.js前端技术
2.3 MySQL数据库
2.4 其他技术

第3章 系统需求分析
3.1 可行性分析
3.2 功能需求分析
3.3 非功能需求分析
3.4 用例分析

第4章 系统设计
4.1 系统架构设计
4.2 功能模块设计
4.3 数据库设计
4.4 接口设计

第5章 系统实现
5.1 开发环境搭建
5.2 核心功能实现
5.3 系统界面展示

第6章 系统测试
6.1 测试环境
6.2 功能测试
6.3 性能测试
6.4 测试结论

第7章 总结与展望
7.1 工作总结
7.2 未来展望""",
        
        "ai": """第1章 绪论
1.1 研究背景与意义
1.2 国内外研究现状
1.3 研究内容与创新点
1.4 论文组织结构

第2章 相关理论基础
2.1 深度学习基础
2.2 卷积神经网络
2.3 循环神经网络
2.4 注意力机制

第3章 方法设计
3.1 问题定义
3.2 模型架构
3.3 损失函数设计
3.4 训练策略

第4章 实验设计与分析
4.1 数据集介绍
4.2 实验设置
4.3 评价指标
4.4 实验结果分析
4.5 消融实验

第5章 总结与展望
5.1 工作总结
5.2 研究局限
5.3 未来工作""",
        
        "general": """第1章 绪论
1.1 研究背景
1.2 研究意义
1.3 研究现状
1.4 研究内容
1.5 论文结构

第2章 理论基础
2.1 相关概念
2.2 理论框架
2.3 技术方法

第3章 研究设计
3.1 研究方法
3.2 数据来源
3.3 分析框架

第4章 分析与讨论
4.1 现状分析
4.2 问题分析
4.3 对策建议

第5章 结论
5.1 研究结论
5.2 研究不足
5.3 未来展望""",
    }
    return templates.get(template_type, templates["general"])


def get_diagram_template(diagram_type: str) -> str:
    """获取图表模板"""
    templates = {
        "flowchart": """flowchart TD
    A[开始] --> B{条件判断}
    B -->|是| C[执行操作]
    B -->|否| D[其他操作]
    C --> E[结束]
    D --> E""",
        
        "sequence": """sequenceDiagram
    participant 用户
    participant 系统
    participant 数据库
    用户->>系统: 发起请求
    系统->>数据库: 查询数据
    数据库-->>系统: 返回结果
    系统-->>用户: 显示结果""",
        
        "er": """erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : included_in
    USER {
        int id PK
        string name
        string email
    }""",
        
        "class": """classDiagram
    class User {
        +int id
        +String name
        +login()
        +logout()
    }
    class Order {
        +int orderId
        +Date createTime
        +submit()
    }
    User "1" --> "*" Order : creates""",
        
        "mindmap": """mindmap
  root((系统功能))
    用户管理
      用户注册
      用户登录
      权限控制
    业务模块
      数据查询
      数据编辑
      报表导出""",
        
        "pie": """pie title 模块分布
    "用户模块" : 25
    "订单模块" : 30
    "商品模块" : 25
    "其他" : 20""",
    }
    return templates.get(diagram_type, "")


def run_tui():
    """运行交互式界面"""
    try:
        while True:
            clear_screen()
            show_banner()
            
            choice = show_main_menu()
            
            if choice == "quit" or choice is None:
                console.print("\n[cyan]再见！👋[/cyan]\n")
                break
            elif choice == "new":
                new_paper_flow()
            elif choice == "continue":
                continue_paper_flow()
            elif choice == "diagram":
                diagram_flow()
            elif choice == "settings":
                settings_flow()
            elif choice == "help":
                help_flow()
            
            # 流程结束后暂停
            if choice not in ["quit", "settings", "help"]:
                questionary.press_any_key_to_continue("\n按任意键返回主菜单...").ask()
                
    except KeyboardInterrupt:
        console.print("\n\n[cyan]再见！👋[/cyan]\n")


if __name__ == "__main__":
    run_tui()
