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
from .models import Paper, PaperStatus, PipelineContext, LLMOptions, FigureType
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
        questionary.Choice("📝 新建论文", value="new"),
        questionary.Choice("📂 继续写作", value="continue"),
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
        default="8000",
        style=STYLE,
    ).ask()
    
    try:
        target_words = int(words_str)
    except ValueError:
        target_words = 8000
    
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
    
    try:
        config = load_config()
        thinking_provider = create_thinking_provider(config)
        
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
                console.print("[cyan]📷 正在扫描图片...[/cyan]")
                images = await initializer.scan_images()
                tables = initializer.scan_tables()  # 同步方法
            
            # parse_outline 内部有自己的进度显示
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
        import traceback
        traceback.print_exc()
        return
    
    console.print(f"\n[green]✓ 配置已保存到: {output_path}[/green]")
    
    # 显示大纲预览
    display_outline_preview(paper)
    
    # 统计图片建议
    all_figures = []
    for section in paper.get_all_sections():
        all_figures.extend(section.figures)
    
    generate_figs = [f for f in all_figures if getattr(f, 'fig_type', None) == FigureType.GENERATE]
    suggested_figs = [f for f in all_figures if getattr(f, 'fig_type', None) == FigureType.SUGGESTED]
    missing_figs = [f for f in all_figures if getattr(f, 'fig_type', None) == FigureType.MISSING]
    
    # 8. 下一步选项（根据图片情况动态调整）
    choices = []
    
    if generate_figs or missing_figs:
        choices.append(
            questionary.Choice(
                f"🔧 处理图片建议 ({len(generate_figs)} 个可生成, {len(missing_figs)} 个待补充)",
                value="process_figures"
            )
        )
    
    # 构建一键全流程描述
    all_steps = []
    if generate_figs:
        all_steps.append(f"图片{len(generate_figs)}个")
    all_steps.extend(["草稿", "润色", "导出"])
    all_steps_desc = " + ".join(all_steps)
    
    choices.extend([
        questionary.Choice("🖼️  生成 Mermaid 图表（流程图/ER图等）", value="diagram"),
        questionary.Choice("📝 编辑大纲 YAML 文件", value="edit"),
        questionary.Choice("🚀 立即生成论文草稿", value="draft"),
        questionary.Choice(f"⚡ 一键全流程（{all_steps_desc}）", value="all"),
        questionary.Choice("📋 返回主菜单", value="menu"),
    ])
    
    next_action = questionary.select(
        "\n下一步：",
        choices=choices,
        style=STYLE,
    ).ask()
    
    if next_action == "process_figures":
        process_figure_suggestions(paper, output_path, images_dir)
        # 处理完后重新加载并继续
        paper = load_outline(output_path)
        next_action = questionary.select(
            "\n下一步：",
            choices=[
                questionary.Choice("🖼️  生成 Mermaid 图表（流程图/ER图等）", value="diagram"),
                questionary.Choice("🚀 立即生成论文草稿", value="draft"),
                questionary.Choice("⚡ 一键全流程（草稿 + 润色 + 导出）", value="all"),
                questionary.Choice("📋 返回主菜单", value="menu"),
            ],
            style=STYLE,
        ).ask()
    
    if next_action == "diagram":
        generate_diagrams_for_paper(paper, output_path, images_dir)
        # 生成图表后继续询问下一步
        next_action = questionary.select(
            "\n下一步：",
            choices=[
                questionary.Choice("🚀 立即生成论文草稿", value="draft"),
                questionary.Choice("⚡ 一键全流程（草稿 + 润色 + 导出）", value="all"),
                questionary.Choice("📋 返回主菜单", value="menu"),
            ],
            style=STYLE,
        ).ask()
    
    if next_action == "edit":
        # 打开 YAML 文件进行编辑
        import subprocess
        console.print(f"[dim]正在打开编辑器: {output_path}[/dim]")
        try:
            subprocess.run(["code", str(output_path)], shell=True)
            questionary.press_any_key_to_continue("编辑完成后按任意键继续...").ask()
            paper = load_outline(output_path)
            display_outline_preview(paper)
        except Exception as e:
            console.print(f"[red]无法打开编辑器: {e}[/red]")
    
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
    
    # 根据实际内容状态判断需要什么步骤
    # 注意：内容存储在主章节（level==1），子节不存储内容
    all_sections = paper.get_all_sections()
    main_chapters = [s for s in all_sections if s.level == 1]
    need_draft = any(not s.draft_latex for s in main_chapters)
    need_refine = any(s.draft_latex and not s.final_latex for s in main_chapters)
    has_abstract_done = has_abstract(paper)
    
    # 检查是否有可生成的图片
    all_figures = []
    for section in all_sections:
        all_figures.extend(section.figures)
    generate_figs = [f for f in all_figures if getattr(f, 'fig_type', None) == FigureType.GENERATE]
    
    # 判断是否有剩余流程
    remaining_steps = []
    if generate_figs:
        remaining_steps.append(f"图片{len(generate_figs)}个")
    if need_draft:
        remaining_steps.append("草稿")
    if need_draft or need_refine:
        remaining_steps.append("润色")
    if not has_abstract_done:
        remaining_steps.append("摘要")
    
    # 精简菜单：突出一键完成
    choices = []
    
    if remaining_steps:
        choices.append(questionary.Choice(
            f"⚡ 一键完成 ({' → '.join(remaining_steps)} → 导出)", 
            value="all"
        ))
    
    choices.append(questionary.Choice("📄 导出 Word", value="export"))
    choices.append(questionary.Choice("🔧 更多选项...", value="more"))
    choices.append(questionary.Choice("↩️  返回", value="back"))
    
    action = questionary.select(
        "选择操作：",
        choices=choices,
        style=STYLE,
    ).ask()
    
    # 更多选项子菜单
    if action == "more":
        more_choices = []
        if generate_figs:
            more_choices.append(questionary.Choice(
                f"🖼️  处理图片 ({len(generate_figs)} 个可生成)",
                value="process_figures"
            ))
        if need_draft:
            more_choices.append(questionary.Choice("✏️  仅生成草稿", value="draft"))
        if need_refine:
            more_choices.append(questionary.Choice("✨ 仅润色内容", value="refine"))
        more_choices.append(questionary.Choice("📊 查看详细状态", value="status"))
        more_choices.append(questionary.Choice("🗑️  项目管理", value="manage"))
        more_choices.append(questionary.Choice("↩️  返回", value="back"))
        
        action = questionary.select(
            "更多选项：",
            choices=more_choices,
            style=STYLE,
        ).ask()
    
    if action == "process_figures":
        process_figure_suggestions(paper, file_path, None)
        paper = load_outline(file_path)
    elif action == "draft":
        generate_draft_flow(file_path, None)
    elif action == "refine":
        refine_flow(file_path, None)
    elif action == "all":
        full_pipeline_flow(file_path, None)
    elif action == "export":
        export_flow(file_path, None)
    elif action == "status":
        show_detailed_status(paper)
    elif action == "manage":
        manage_project(file_path)


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
        images_path = Path(images_dir) if images_dir else None
        exporter = WordExporter(images_base_path=images_path)
        word_file = output_path / f"{paper.title}.docx"
        exporter.export(paper, word_file)
        
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
    
    # 检查是否有待生成的图片
    all_figures = []
    for section in paper.get_all_sections():
        all_figures.extend(section.figures)
    generate_figs = [f for f in all_figures if getattr(f, 'fig_type', None) == FigureType.GENERATE]
    
    # 根据实际内容状态判断需要哪些步骤
    # 注意：内容存储在主章节（level==1），子节不存储内容
    all_sections = paper.get_all_sections()
    main_chapters = [s for s in all_sections if s.level == 1]
    need_draft = any(not s.draft_latex for s in main_chapters)
    need_refine = any(s.draft_latex and not s.final_latex for s in main_chapters)
    
    steps = []
    if generate_figs:
        steps.append(f"生成图片 ({len(generate_figs)} 个)")
    if need_draft:
        steps.append("生成草稿")
    if need_draft or need_refine:  # 生成草稿后必然要润色
        steps.append("润色内容")
    steps.append("生成摘要")
    steps.append("导出文档")
    
    console.print(f"将依次执行: {' → '.join(steps)}\n")
    
    if not questionary.confirm("确认开始？", default=True, style=STYLE).ask():
        return
    
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
    step_num = 1
    total_steps = len(steps)
    
    try:
        # 0. 生成图片（如果有）
        if generate_figs:
            console.print(f"\n[bold blue]━━━ [{step_num}/{total_steps}] 生成图片 ━━━[/bold blue]\n")
            step_num += 1
            
            # 确定图片输出目录
            fig_output_dir = output_path / "generated_figures"
            fig_output_dir.mkdir(parents=True, exist_ok=True)
            
            from .diagram import MermaidRenderer
            
            async def generate_all_figures():
                renderer = MermaidRenderer()
                generated = 0
                try:
                    for i, fig in enumerate(generate_figs, 1):
                        mermaid_code = getattr(fig, 'mermaid_code', None)
                        if mermaid_code:
                            console.print(f"🔧 [{i}/{len(generate_figs)}] {fig.caption}...", end="")
                            output_file = fig_output_dir / f"{fig.id or f'fig{i}'}.png"
                            try:
                                result = await renderer.render_async(mermaid_code, output_file)
                                if result and result.exists():
                                    console.print(f" [green]✓[/green]")
                                    fig.path = str(result.relative_to(output_path) if output_path.exists() else result)
                                    fig.fig_type = FigureType.MATCHED
                                    generated += 1
                                else:
                                    console.print(f" [red]✗[/red]")
                            except Exception as e:
                                console.print(f" [red]✗ {e}[/red]")
                finally:
                    await renderer._close_browser()
                return generated
            
            generated = asyncio.run(generate_all_figures())
            console.print(f"[green]✓ 已生成 {generated} 个图片[/green]")
            save_outline(paper, file_path)
        
        # 1. 生成草稿
        if need_draft:
            console.print(f"\n[bold blue]━━━ [{step_num}/{total_steps}] 生成草稿 ━━━[/bold blue]\n")
            step_num += 1
            writing_provider = create_writing_provider(config)
            step = SectionDraftStep(writing_provider)
            
            async def run_draft():
                context = PipelineContext(paper=paper, llm_options=LLMOptions())
                return await step.execute(context)
            
            result = asyncio.run(run_draft())
            paper = result.paper
            save_outline(paper, file_path)
        
        # 2. 润色（如果生成了草稿，或者有待润色的内容）
        if need_draft or need_refine:
            console.print(f"\n[bold blue]━━━ [{step_num}/{total_steps}] 润色内容 ━━━[/bold blue]\n")
            step_num += 1
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
            console.print(f"\n[bold blue]━━━ [{step_num}/{total_steps}] 生成摘要 ━━━[/bold blue]\n")
            step_num += 1
            thinking_provider = create_thinking_provider(config)
            step = AbstractGenerateStep(thinking_provider)
            
            async def run_abstract():
                context = PipelineContext(paper=paper, llm_options=LLMOptions())
                return await step.execute(context)
            
            result = asyncio.run(run_abstract())
            paper = result.paper
            save_outline(paper, file_path)
        
        # 4. 导出
        console.print(f"\n[bold blue]━━━ [{step_num}/{total_steps}] 导出文档 ━━━[/bold blue]\n")
        
        # LaTeX
        console.print("[cyan]📄 正在生成 LaTeX...[/cyan]")
        renderer = LatexRenderer()
        latex_content = renderer.render(paper)
        latex_file = output_path / f"{paper.title}.tex"
        latex_file.write_text(latex_content, encoding="utf-8")
        
        # Word
        console.print("[cyan]📝 正在生成 Word...[/cyan]")
        # 优先使用生成的图片目录
        images_path = output_path if (output_path / "generated_figures").exists() else (Path(images_dir) if images_dir else None)
        exporter = WordExporter(images_base_path=images_path)
        word_file = output_path / f"{paper.title}.docx"
        exporter.export(paper, word_file)
        
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


def manage_project(file_path: Path):
    """管理单个项目"""
    paper = load_outline(file_path)
    
    console.print(f"\n[bold cyan]━━━ 🗑️ 项目管理: {paper.title} ━━━[/bold cyan]\n")
    
    # 统计
    total_sections = len(paper.sections)
    drafted_sections = sum(1 for s in paper.sections if s.draft_latex)
    refined_sections = sum(1 for s in paper.sections if s.final_latex)
    console.print(f"状态: {paper.status.value}")
    console.print(f"章节: {total_sections} 个 ({drafted_sections} 有草稿, {refined_sections} 已润色)")
    
    action = questionary.select(
        "\n选择操作：",
        choices=[
            questionary.Choice("🔄 重置草稿（清除所有草稿内容）", value="reset_draft"),
            questionary.Choice("✨ 重置润色（保留草稿，清除润色）", value="reset_refine"),
            questionary.Choice("📋 重置为大纲（清除所有内容）", value="reset_all"),
            questionary.Choice("🗑️  删除项目", value="delete"),
            questionary.Choice("📁 打开输出目录", value="open_output"),
            questionary.Choice("↩️  返回", value="back"),
        ],
        style=STYLE,
    ).ask()
    
    if action == "back":
        return
    
    if action == "reset_draft":
        if questionary.confirm("确定要清除所有草稿内容？", default=False, style=STYLE).ask():
            for section in paper.sections:
                section.draft_latex = None
                section.final_latex = None
                for child in section.children:
                    child.draft_latex = None
                    child.final_latex = None
            paper.status = PaperStatus.OUTLINE_CONFIRMED
            save_outline(paper, file_path)
            console.print("[green]✓ 已重置所有草稿[/green]")
    
    elif action == "reset_refine":
        if questionary.confirm("确定要清除润色内容？", default=False, style=STYLE).ask():
            for section in paper.sections:
                section.final_latex = None
                for child in section.children:
                    child.final_latex = None
            paper.status = PaperStatus.DRAFT
            save_outline(paper, file_path)
            console.print("[green]✓ 已重置润色内容[/green]")
    
    elif action == "reset_all":
        if questionary.confirm("确定要清除所有内容？", default=False, style=STYLE).ask():
            for section in paper.sections:
                section.draft_latex = None
                section.final_latex = None
                for child in section.children:
                    child.draft_latex = None
                    child.final_latex = None
            paper.status = PaperStatus.OUTLINE_CONFIRMED
            paper.abstract_cn = None
            paper.abstract_en = None
            save_outline(paper, file_path)
            console.print("[green]✓ 已重置为大纲状态[/green]")
    
    elif action == "delete":
        output_dir = Path("output") / file_path.stem
        if questionary.confirm(f"确定要删除项目 {paper.title}？", default=False, style=STYLE).ask():
            file_path.unlink()
            console.print(f"[green]✓ 已删除配置文件[/green]")
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)
                console.print(f"[green]✓ 已删除输出目录[/green]")
    
    elif action == "open_output":
        output_dir = Path("output") / file_path.stem
        if output_dir.exists():
            import subprocess
            subprocess.run(["explorer", str(output_dir)], shell=True)
        else:
            console.print("[yellow]输出目录不存在[/yellow]")


def manage_projects_flow():
    """项目管理流程"""
    console.print("\n[bold cyan]━━━ 🗂️ 项目管理 ━━━[/bold cyan]\n")
    
    # 扫描已有的 YAML 文件
    yaml_files = list(Path(".").glob("*.yaml")) + list(Path("examples").glob("*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_template")]
    
    if not yaml_files:
        console.print("[yellow]未找到任何项目文件[/yellow]")
        return
    
    # 构建选项
    choices = []
    for f in yaml_files[:20]:
        try:
            paper = load_outline(f)
            # 统计章节状态
            total = len(paper.sections)
            drafted = sum(1 for s in paper.sections if s.draft_latex)
            refined = sum(1 for s in paper.sections if s.final_latex)
            choices.append(questionary.Choice(
                f"📄 {paper.title[:30]} ({drafted}/{total}草稿, {refined}/{total}润色)",
                value=str(f),
            ))
        except Exception:
            choices.append(questionary.Choice(f"❓ {f.name}", value=str(f)))
    
    choices.append(questionary.Choice("↩️  返回", value="back"))
    
    selected = questionary.select(
        "选择要管理的项目：",
        choices=choices,
        style=STYLE,
    ).ask()
    
    if selected == "back":
        return
    
    file_path = Path(selected)
    if not file_path.exists():
        console.print("[red]文件不存在[/red]")
        return
    
    paper = load_outline(file_path)
    
    # 显示项目详情
    console.print(f"\n[bold]{paper.title}[/bold]")
    console.print(f"文件: {file_path}")
    console.print(f"状态: {paper.status.value}")
    
    # 统计
    total_sections = len(paper.sections)
    drafted_sections = sum(1 for s in paper.sections if s.draft_latex)
    refined_sections = sum(1 for s in paper.sections if s.final_latex)
    console.print(f"章节: {total_sections} 个 ({drafted_sections} 有草稿, {refined_sections} 已润色)")
    
    # 管理选项
    action = questionary.select(
        "\n选择操作：",
        choices=[
            questionary.Choice("🔄 重置草稿（清除所有草稿内容）", value="reset_draft"),
            questionary.Choice("✨ 重置润色（保留草稿，清除润色）", value="reset_refine"),
            questionary.Choice("📋 重置为大纲（清除所有内容）", value="reset_all"),
            questionary.Choice("🗑️  删除项目", value="delete"),
            questionary.Choice("📁 打开输出目录", value="open_output"),
            questionary.Choice("↩️  返回", value="back"),
        ],
        style=STYLE,
    ).ask()
    
    if action == "back":
        return
    
    if action == "reset_draft":
        if questionary.confirm("确定要清除所有草稿内容？此操作不可撤销！", default=False, style=STYLE).ask():
            for section in paper.sections:
                section.draft_latex = None
                section.final_latex = None
                for child in section.children:
                    child.draft_latex = None
                    child.final_latex = None
            paper.status = PaperStatus.OUTLINE_CONFIRMED
            save_outline(paper, file_path)
            console.print("[green]✓ 已重置所有草稿[/green]")
    
    elif action == "reset_refine":
        if questionary.confirm("确定要清除润色内容？草稿将保留。", default=False, style=STYLE).ask():
            for section in paper.sections:
                section.final_latex = None
                for child in section.children:
                    child.final_latex = None
            paper.status = PaperStatus.DRAFT
            save_outline(paper, file_path)
            console.print("[green]✓ 已重置润色内容，草稿已保留[/green]")
    
    elif action == "reset_all":
        if questionary.confirm("确定要清除所有内容？只保留大纲结构。", default=False, style=STYLE).ask():
            for section in paper.sections:
                section.draft_latex = None
                section.final_latex = None
                for child in section.children:
                    child.draft_latex = None
                    child.final_latex = None
            paper.status = PaperStatus.OUTLINE_CONFIRMED
            paper.abstract_cn = None
            paper.abstract_en = None
            save_outline(paper, file_path)
            console.print("[green]✓ 已重置为大纲状态[/green]")
    
    elif action == "delete":
        console.print(f"\n[red]警告：将删除以下内容：[/red]")
        console.print(f"  - 配置文件: {file_path}")
        output_dir = Path("output") / file_path.stem
        if output_dir.exists():
            console.print(f"  - 输出目录: {output_dir}")
        
        if questionary.confirm("确定要删除？此操作不可撤销！", default=False, style=STYLE).ask():
            file_path.unlink()
            console.print(f"[green]✓ 已删除配置文件[/green]")
            
            if output_dir.exists():
                if questionary.confirm("是否同时删除输出目录？", default=False, style=STYLE).ask():
                    import shutil
                    shutil.rmtree(output_dir)
                    console.print(f"[green]✓ 已删除输出目录[/green]")
    
    elif action == "open_output":
        output_dir = Path("output") / file_path.stem
        if output_dir.exists():
            import subprocess
            subprocess.run(["explorer", str(output_dir)], shell=True)
        else:
            console.print("[yellow]输出目录不存在[/yellow]")


def process_figure_suggestions(paper: Paper, yaml_path: Path, images_dir: str | None = None):
    """处理 AI 建议的图片"""
    console.print("\n[bold cyan]━━━ 🔧 处理图片建议 ━━━[/bold cyan]\n")
    
    from .diagram import MermaidRenderer
    from .models import FigureType
    
    # 收集所有需要处理的图片
    figures_to_process = []
    for section in paper.get_all_sections():
        for fig in section.figures:
            fig_type = getattr(fig, 'fig_type', FigureType.MATCHED)
            if fig_type in [FigureType.GENERATE, FigureType.MISSING]:
                figures_to_process.append((section, fig))
    
    if not figures_to_process:
        console.print("[yellow]没有需要处理的图片建议[/yellow]")
        return
    
    # 确定输出目录
    if images_dir:
        output_dir = Path(images_dir)
    else:
        output_dir = Path("output") / yaml_path.stem / "generated_figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"共有 [cyan]{len(figures_to_process)}[/cyan] 个图片待处理")
    console.print(f"[dim]图片将保存到: {output_dir}[/dim]\n")
    
    # 先询问处理模式
    mode = questionary.select(
        "选择处理模式：",
        choices=[
            questionary.Choice("🚀 一键生成全部（跳过无法生成的）", value="auto"),
            questionary.Choice("👆 逐个确认（可编辑代码）", value="manual"),
            questionary.Choice("❌ 取消", value="cancel"),
        ],
        style=STYLE,
    ).ask()
    
    if mode == "cancel":
        return
    
    # 图标定义
    type_icons = {
        FigureType.GENERATE: ("🔧", "blue", "可自动生成"),
        FigureType.MISSING: ("⚠", "yellow", "用户标注需要"),
    }
    
    generated_count = 0
    skipped_count = 0
    
    # 使用异步函数批量处理
    async def process_all():
        nonlocal generated_count, skipped_count
        
        renderer = MermaidRenderer()
        
        try:
            for i, (section, fig) in enumerate(figures_to_process, 1):
                fig_type = getattr(fig, 'fig_type', FigureType.GENERATE)
                icon, color, type_label = type_icons.get(fig_type, ("?", "white", "未知"))
                mermaid_code = getattr(fig, 'mermaid_code', None)
                can_generate = getattr(fig, 'can_generate', False) or mermaid_code
                
                if mode == "auto":
                    # 自动模式：直接生成
                    if can_generate and mermaid_code:
                        console.print(f"[{color}]{icon}[/{color}] [{i}/{len(figures_to_process)}] {fig.caption}...", end="")
                        output_file = output_dir / f"{fig.id or f'fig{i}'}.png"
                        
                        try:
                            result = await renderer.render_async(mermaid_code, output_file)
                            if result and result.exists():
                                console.print(f" [green]✓[/green]")
                                generated_count += 1
                                fig.path = str(result.relative_to(output_dir.parent) if output_dir.parent.exists() else result)
                                fig.fig_type = FigureType.MATCHED
                            else:
                                console.print(f" [red]✗[/red]")
                                skipped_count += 1
                        except Exception as e:
                            console.print(f" [red]✗ {e}[/red]")
                            skipped_count += 1
                    else:
                        console.print(f"[dim]⏭️  [{i}/{len(figures_to_process)}] {fig.caption} (无法自动生成)[/dim]")
                        skipped_count += 1
                
                else:
                    # 手动模式：逐个确认
                    console.print(f"\n[{color}]{icon}[/{color}] [{i}/{len(figures_to_process)}] {fig.caption}")
                    console.print(f"   章节: [dim]{section.title}[/dim]")
                    if fig.suggestion:
                        console.print(f"   建议: [dim]{fig.suggestion}[/dim]")
                    
                    # 如果有 Mermaid 代码，显示预览
                    if mermaid_code:
                        from rich.syntax import Syntax
                        from rich.panel import Panel
                        console.print(Panel(
                            Syntax(mermaid_code, "text", theme="monokai", line_numbers=False),
                            title="Mermaid 代码预览",
                            width=60,
                        ))
                    
                    # 询问操作
                    if can_generate and mermaid_code:
                        choices = [
                            questionary.Choice("✓ 生成图片", value="generate"),
                            questionary.Choice("📝 编辑代码后生成", value="edit"),
                            questionary.Choice("⏭️  跳过", value="skip"),
                            questionary.Choice("🚀 生成剩余全部", value="auto_rest"),
                            questionary.Choice("🚫 跳过后续所有", value="skip_all"),
                        ]
                    else:
                        choices = [
                            questionary.Choice("⏭️  跳过（需手动补充）", value="skip"),
                            questionary.Choice("🚫 跳过后续所有", value="skip_all"),
                        ]
                    
                    action = questionary.select(
                        "操作：",
                        choices=choices,
                        style=STYLE,
                    ).ask()
                    
                    if action == "skip_all":
                        console.print(f"[dim]跳过剩余 {len(figures_to_process) - i} 个图片[/dim]")
                        break
                    
                    if action == "auto_rest":
                        # 切换到自动模式处理剩余图片（包括当前这个）
                        console.print("[cyan]切换到自动模式...[/cyan]")
                        # 先处理当前这个
                        if mermaid_code:
                            output_file = output_dir / f"{fig.id or f'fig{i}'}.png"
                            try:
                                result = await renderer.render_async(mermaid_code, output_file)
                                if result and result.exists():
                                    console.print(f"   [green]✓ 已生成: {result.name}[/green]")
                                    generated_count += 1
                                    fig.path = str(result.relative_to(output_dir.parent) if output_dir.parent.exists() else result)
                                    fig.fig_type = FigureType.MATCHED
                            except Exception as e:
                                console.print(f"   [red]✗ 错误: {e}[/red]")
                                skipped_count += 1
                        
                        # 处理剩余的
                        for j, (sec2, fig2) in enumerate(figures_to_process[i:], i + 1):
                            mermaid_code2 = getattr(fig2, 'mermaid_code', None)
                            can_gen2 = getattr(fig2, 'can_generate', False) or mermaid_code2
                            
                            if can_gen2 and mermaid_code2:
                                console.print(f"🔧 [{j}/{len(figures_to_process)}] {fig2.caption}...", end="")
                                output_file2 = output_dir / f"{fig2.id or f'fig{j}'}.png"
                                try:
                                    result2 = await renderer.render_async(mermaid_code2, output_file2)
                                    if result2 and result2.exists():
                                        console.print(f" [green]✓[/green]")
                                        generated_count += 1
                                        fig2.path = str(result2.relative_to(output_dir.parent) if output_dir.parent.exists() else result2)
                                        fig2.fig_type = FigureType.MATCHED
                                    else:
                                        console.print(f" [red]✗[/red]")
                                        skipped_count += 1
                                except Exception as e:
                                    console.print(f" [red]✗ {e}[/red]")
                                    skipped_count += 1
                            else:
                                console.print(f"[dim]⏭️  [{j}/{len(figures_to_process)}] {fig2.caption} (无法自动生成)[/dim]")
                                skipped_count += 1
                        break
                    
                    if action == "skip":
                        skipped_count += 1
                        continue
                    
                    current_code = mermaid_code
                    if action == "edit":
                        console.print("[dim]请输入新的 Mermaid 代码（输入空行后按回车结束）:[/dim]")
                        lines = []
                        while True:
                            line = input()
                            if line.strip() == "" and lines:
                                break
                            lines.append(line)
                        current_code = "\n".join(lines)
                    
                    if action in ["generate", "edit"] and current_code:
                        output_file = output_dir / f"{fig.id or f'fig{i}'}.png"
                        
                        try:
                            console.print(f"   [dim]正在渲染...[/dim]", end="")
                            result = await renderer.render_async(current_code, output_file)
                            if result and result.exists():
                                console.print(f"\r   [green]✓ 已生成: {result.name}[/green]")
                                generated_count += 1
                                fig.path = str(result.relative_to(output_dir.parent) if output_dir.parent.exists() else result)
                                fig.fig_type = FigureType.MATCHED
                                if action == "edit":
                                    fig.mermaid_code = current_code
                            else:
                                console.print(f"\r   [red]✗ 生成失败[/red]")
                                skipped_count += 1
                        except Exception as e:
                            console.print(f"\r   [red]✗ 错误: {e}[/red]")
                            skipped_count += 1
        
        finally:
            # 确保关闭浏览器
            await renderer._close_browser()
    
    # 运行异步处理
    asyncio.run(process_all())
    
    # 显示统计
    console.print(f"\n[bold]处理完成:[/bold]")
    console.print(f"  [green]✓ 已生成: {generated_count}[/green]")
    console.print(f"  [dim]⏭️  跳过: {skipped_count}[/dim]")
    
    # 保存更新后的配置
    if generated_count > 0:
        save_outline(paper, yaml_path)
        console.print(f"\n[green]✓ 配置已更新[/green]")


def generate_diagrams_for_paper(paper: Paper, yaml_path: Path, images_dir: str | None = None):
    """为论文生成 Mermaid 图表"""
    console.print("\n[bold cyan]━━━ 🖼️ 为论文生成图表 ━━━[/bold cyan]\n")
    
    # 根据论文主题推荐图表类型
    console.print("[dim]根据您的论文，以下图表可能有用：[/dim]")
    console.print("  • 系统架构图（流程图）")
    console.print("  • 数据库 ER 图")
    console.print("  • 业务流程时序图")
    console.print("  • 功能模块类图")
    console.print("")
    
    # 选择要生成的图表
    diagram_choices = questionary.checkbox(
        "选择要生成的图表类型：",
        choices=[
            questionary.Choice("📊 系统架构/流程图", value="flowchart", checked=True),
            questionary.Choice("🗃️  数据库 ER 图", value="er", checked=True),
            questionary.Choice("🔄 业务流程时序图", value="sequence"),
            questionary.Choice("📦 功能模块类图", value="class"),
            questionary.Choice("🧠 系统功能思维导图", value="mindmap"),
        ],
        style=STYLE,
    ).ask()
    
    if not diagram_choices:
        console.print("[yellow]未选择任何图表[/yellow]")
        return
    
    # 确定图表输出目录
    if images_dir:
        output_dir = Path(images_dir)
    else:
        output_dir = Path("output") / yaml_path.stem / "diagrams"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"\n[dim]图表将保存到: {output_dir}[/dim]\n")
    
    from .diagram import MermaidRenderer
    renderer = MermaidRenderer()
    
    generated_files = []
    
    for diagram_type in diagram_choices:
        console.print(f"[cyan]正在生成 {diagram_type} 图表...[/cyan]")
        
        # 根据论文信息生成图表代码
        mermaid_code = _generate_diagram_code_for_paper(paper, diagram_type)
        
        if mermaid_code:
            output_file = output_dir / f"{diagram_type}_{paper.title[:10]}.png"
            try:
                result = asyncio.run(renderer.render_async(mermaid_code, output_file))
                if result and result.exists():
                    console.print(f"[green]  ✓ 已生成: {result.name}[/green]")
                    generated_files.append(result)
                else:
                    console.print(f"[yellow]  ⚠ 生成失败[/yellow]")
            except Exception as e:
                console.print(f"[red]  ✗ 错误: {e}[/red]")
    
    if generated_files:
        console.print(f"\n[green]✓ 共生成 {len(generated_files)} 个图表[/green]")
        
        # 询问是否打开输出目录
        if questionary.confirm("是否打开图表目录？", default=True, style=STYLE).ask():
            import subprocess
            subprocess.run(["explorer", str(output_dir)], shell=True)


def _generate_diagram_code_for_paper(paper: Paper, diagram_type: str) -> str:
    """根据论文信息生成 Mermaid 图表代码"""
    title = paper.title
    
    if diagram_type == "flowchart":
        # 系统架构流程图
        return f"""flowchart TB
    subgraph 表示层
        A[用户界面]
    end
    
    subgraph 业务层
        B[业务逻辑处理]
        C[数据验证]
        D[权限控制]
    end
    
    subgraph 数据层
        E[(数据库)]
        F[缓存]
    end
    
    A --> B
    B --> C
    B --> D
    C --> E
    D --> E
    E --> F"""
    
    elif diagram_type == "er":
        # ER 图
        return """erDiagram
    USER ||--o{ ORDER : places
    USER {
        int id PK
        string username
        string password
        string email
        datetime created_at
    }
    ORDER ||--|{ ORDER_ITEM : contains
    ORDER {
        int id PK
        int user_id FK
        datetime order_date
        string status
        decimal total
    }
    ORDER_ITEM {
        int id PK
        int order_id FK
        int product_id FK
        int quantity
        decimal price
    }
    PRODUCT ||--o{ ORDER_ITEM : "is ordered"
    PRODUCT {
        int id PK
        string name
        string description
        decimal price
        int stock
    }"""
    
    elif diagram_type == "sequence":
        # 时序图
        return """sequenceDiagram
    participant U as 用户
    participant C as 客户端
    participant S as 服务器
    participant D as 数据库
    
    U->>C: 输入请求
    C->>S: 发送请求
    S->>D: 查询数据
    D-->>S: 返回结果
    S-->>C: 响应数据
    C-->>U: 显示结果"""
    
    elif diagram_type == "class":
        # 类图
        return """classDiagram
    class User {
        +int id
        +String username
        +String password
        +login()
        +logout()
    }
    
    class Admin {
        +manageUsers()
        +viewReports()
    }
    
    class Service {
        +processRequest()
        +validateData()
    }
    
    class Database {
        +query()
        +insert()
        +update()
        +delete()
    }
    
    User <|-- Admin
    User --> Service
    Service --> Database"""
    
    elif diagram_type == "mindmap":
        # 思维导图
        return f"""mindmap
    root(({title}))
        用户管理
            登录注册
            权限控制
            信息维护
        核心功能
            数据管理
            业务处理
            报表生成
        系统管理
            系统配置
            日志管理
            备份恢复"""
    
    return ""


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
            asyncio.run(renderer.render_async(mermaid_code, output_file))
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
    """显示大纲预览，包含图片状态"""
    from .models import FigureType
    
    # 图片状态图标
    fig_icons = {
        FigureType.MATCHED: ("✓", "green", "已匹配"),
        FigureType.GENERATE: ("🔧", "blue", "可生成"),
        FigureType.SUGGESTED: ("💡", "yellow", "建议补充"),
        FigureType.MISSING: ("⚠", "red", "待补充"),
    }
    
    table = Table(title="大纲预览", show_header=True, width=70)
    table.add_column("章节", style="cyan")
    table.add_column("字数", justify="right", width=6)
    table.add_column("图片", justify="center", width=12)
    table.add_column("状态", justify="center", width=6)
    
    def format_figures(figures) -> str:
        """格式化图片状态"""
        if not figures:
            return "[dim]-[/dim]"
        
        status_parts = []
        for fig in figures[:3]:  # 最多显示3个
            fig_type = getattr(fig, 'fig_type', FigureType.MATCHED)
            icon, color, _ = fig_icons.get(fig_type, ("?", "white", "未知"))
            status_parts.append(f"[{color}]{icon}[/{color}]")
        
        result = " ".join(status_parts)
        if len(figures) > 3:
            result += f" +{len(figures)-3}"
        return result
    
    def add_row(section, indent=0):
        prefix = "  " * indent
        status = "✓" if section.draft_latex else "-"
        words = str(section.target_words or "") if section.target_words else ""
        figs_str = format_figures(section.figures)
        
        table.add_row(
            f"{prefix}{section.title[:35]}",
            f"[dim]{words}[/dim]",
            figs_str,
            f"[green]{status}[/green]" if section.draft_latex else f"[dim]{status}[/dim]",
        )
        for child in section.children[:5]:  # 最多显示 5 个子节
            add_row(child, indent + 1)
        if len(section.children) > 5:
            table.add_row(f"{prefix}  ... 还有 {len(section.children) - 5} 个", "", "", "[dim]-[/dim]")
    
    for section in paper.sections[:8]:  # 最多显示 8 章
        add_row(section)
    
    if len(paper.sections) > 8:
        table.add_row(f"... 还有 {len(paper.sections) - 8} 章", "", "", "-")
    
    console.print(table)
    
    # 显示图片统计
    all_figures = []
    for section in paper.get_all_sections():
        all_figures.extend(section.figures)
    
    if all_figures:
        stats = {ft: 0 for ft in FigureType}
        for fig in all_figures:
            fig_type = getattr(fig, 'fig_type', FigureType.MATCHED)
            stats[fig_type] = stats.get(fig_type, 0) + 1
        
        stat_parts = []
        for ft, count in stats.items():
            if count > 0:
                icon, color, label = fig_icons.get(ft, ("?", "white", "未知"))
                stat_parts.append(f"[{color}]{icon} {label}: {count}[/{color}]")
        
        if stat_parts:
            console.print(f"\n📊 图片统计: {' | '.join(stat_parts)}")


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
