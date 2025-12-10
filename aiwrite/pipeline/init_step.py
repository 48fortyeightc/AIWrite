"""
大纲初始化步骤

实现从纯文本大纲 + 本地图片 → 完整 YAML 配置的自动化流程
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.syntax import Syntax

from ..models import Paper, Section, Figure, Table, PaperStatus, LLMOptions, FigureType
from ..prompts import build_outline_init_prompt, build_mermaid_generation_prompt
from ..utils.excel import read_excel_file, table_to_markdown

if TYPE_CHECKING:
    from ..llm import LLMProvider

console = Console()


class OutlineInitializer:
    """
    大纲初始化器
    
    功能：
    1. 扫描本地图片目录，使用 AI 识别图片内容
    2. 扫描本地表格文件，读取表格结构
    3. 解析用户输入的纯文本大纲
    4. 使用 AI 生成完整的 YAML 配置，自动匹配图表到章节
    5. 为缺少的图表生成 Mermaid 代码并渲染
    """
    
    def __init__(
        self,
        thinking_provider: "LLMProvider",
        vision_provider: "LLMProvider | None" = None,
        images_path: str | Path | None = None,
    ):
        """
        初始化
        
        Args:
            thinking_provider: 思考模型（用于大纲解析和Mermaid生成）
            vision_provider: 视觉模型（用于图片识别），如果不提供则使用 thinking_provider
            images_path: 图片目录路径
        """
        self.thinking_provider = thinking_provider
        self.vision_provider = vision_provider or thinking_provider
        self.images_path = Path(images_path) if images_path else None
    
    async def scan_images(self) -> list[dict]:
        """
        扫描图片目录并识别图片内容
        
        Returns:
            图片信息列表，包含路径和 AI 识别的描述
        """
        if not self.images_path or not self.images_path.exists():
            return []
        
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        images = []
        
        for file_path in self.images_path.iterdir():
            if file_path.suffix.lower() in image_extensions:
                images.append({
                    "path": str(file_path.relative_to(self.images_path.parent)),
                    "filename": file_path.name,
                    "full_path": file_path,
                    "description": None,  # 稍后由 AI 填充
                })
        
        if not images:
            return []
        
        console.print(f"\n[cyan]🔍 发现 {len(images)} 个图片文件[/cyan]")
        console.print("[cyan]🤖 正在使用 AI 批量识别图片内容...[/cyan]")
        
        # 批量识别所有图片（一次 API 调用）
        try:
            descriptions = await self._analyze_images_batch(images)
            for img, desc in zip(images, descriptions):
                img["description"] = desc
                console.print(f"  ✓ {img['filename']} → [green]{desc[:40]}...[/green]" if len(desc) > 40 else f"  ✓ {img['filename']} → [green]{desc}[/green]")
        except Exception as e:
            console.print(f"[yellow]批量识别失败，改用逐张识别: {e}[/yellow]")
            # 回退到逐张识别
            for i, img in enumerate(images, 1):
                try:
                    description = await self._analyze_image(img["full_path"])
                    img["description"] = description
                    console.print(f"  [{i}/{len(images)}] {img['filename']} → [green]{description[:40]}[/green]")
                except Exception:
                    img["description"] = f"图片: {img['filename']}"
        
        # 清理临时字段
        for img in images:
            img.pop("full_path", None)
        
        return images
    
    async def _analyze_images_batch(self, images: list[dict]) -> list[str]:
        """
        批量分析多张图片（一次 API 调用）
        
        Args:
            images: 图片信息列表
            
        Returns:
            图片描述列表
        """
        # 构建批量识别的提示词
        prompt = f"""请依次识别以下 {len(images)} 张图片，每张图片用一句话描述其内容（用于论文写作）。

要求：
1. 每张图片的描述不超过 50 个字
2. 指出图片类型（如系统图、流程图、界面截图等）
3. 按顺序输出，每行一个描述

图片顺序：
""" + "\n".join(f"{i+1}. {img['filename']}" for i, img in enumerate(images))
        
        prompt += """

请严格按以下格式输出（每行一个描述，不要编号）：
系统登录界面，包含用户名密码输入框
用户管理模块界面，展示用户列表和操作按钮
..."""
        
        # 收集所有图片路径
        image_paths = [img["full_path"] for img in images]
        
        options = LLMOptions(max_tokens=500)
        response = await self.thinking_provider.invoke_vision(
            prompt=prompt,
            image_paths=image_paths,
            options=options,
        )
        
        # 解析响应，按行分割
        content = response.content.strip() if response.content else ""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # 确保描述数量与图片数量匹配
        descriptions = []
        for i, img in enumerate(images):
            if i < len(lines):
                # 移除可能的编号前缀（如 "1. " 或 "1、"）
                desc = re.sub(r'^[\d]+[.、\s]+', '', lines[i]).strip()
                descriptions.append(desc if desc else f"图片: {img['filename']}")
            else:
                descriptions.append(f"图片: {img['filename']}")
        
        return descriptions
    
    async def _analyze_image(self, image_path: Path) -> str:
        """
        使用 AI 分析单张图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            图片内容描述
        """
        prompt = """请简洁描述这张图片的内容，用于论文写作。
        
要求：
1. 一句话概括图片类型和主要内容
2. 不超过 50 个字
3. 如果是系统图/流程图/时序图等，指出是什么类型的图

示例输出：
- "系统部署架构图，展示前后端分离的B/S架构"
- "用户登录时序图，包含用户、系统、数据库交互"
- "数据库ER图，包含用户表、订单表等实体"
- "系统功能结构图，展示五大功能模块"
"""
        
        # 调用支持视觉的模型
        options = LLMOptions(max_tokens=200)
        response = await self.thinking_provider.invoke_vision(
            prompt=prompt,
            image_paths=[image_path],
            options=options,
        )
        
        return response.content.strip() if response.content else f"图片: {image_path.name}"
    
    def scan_tables(self) -> list[dict]:
        """
        扫描表格文件并读取内容
        
        Returns:
            表格信息列表，包含路径和列信息
        """
        if not self.images_path or not self.images_path.exists():
            return []
        
        table_extensions = {'.xls', '.xlsx', '.csv'}
        tables = []
        
        for file_path in self.images_path.iterdir():
            if file_path.suffix.lower() in table_extensions:
                try:
                    # 读取表格内容
                    rows = read_excel_file(file_path)
                    if rows:
                        columns = rows[0] if rows else []
                        tables.append({
                            "path": str(file_path.relative_to(self.images_path.parent)),
                            "filename": file_path.name,
                            "columns": columns,
                            "row_count": len(rows) - 1,  # 减去表头
                            "description": f"表格包含列: {', '.join(str(c) for c in columns[:5])}{'...' if len(columns) > 5 else ''}",
                        })
                except Exception as e:
                    console.print(f"[yellow]警告: 读取表格 {file_path.name} 失败: {e}[/yellow]")
        
        if tables:
            console.print(f"\n[cyan]📊 发现 {len(tables)} 个表格文件[/cyan]")
            for t in tables:
                console.print(f"  - {t['filename']}: {t['description']}")
        
        return tables
    
    async def parse_outline(
        self,
        paper_title: str,
        outline_text: str,
        images: list[dict],
        tables: list[dict],
        target_words: int = 8000,
    ) -> dict:
        """
        解析大纲文本，生成完整配置
        
        Args:
            paper_title: 论文标题
            outline_text: 用户输入的大纲文本
            images: 图片信息列表
            tables: 表格信息列表
            target_words: 目标字数
            
        Returns:
            解析后的配置字典
        """
        # 格式化图片描述
        if images:
            image_desc_lines = []
            for img in images:
                image_desc_lines.append(f"- 文件: {img['path']}")
                image_desc_lines.append(f"  内容: {img['description']}")
            image_descriptions = "\n".join(image_desc_lines)
        else:
            image_descriptions = "（无本地图片）"
        
        # 格式化表格描述
        if tables:
            table_desc_lines = []
            for t in tables:
                table_desc_lines.append(f"- 文件: {t['path']}")
                table_desc_lines.append(f"  列: {', '.join(str(c) for c in t['columns'])}")
            table_descriptions = "\n".join(table_desc_lines)
        else:
            table_descriptions = "（无本地表格）"
        
        # 构建 Prompt
        prompt = build_outline_init_prompt(
            paper_title=paper_title,
            target_words=target_words,
            outline_text=outline_text,
            image_descriptions=image_descriptions,
            table_descriptions=table_descriptions,
        )
        
        console.print("\n[cyan]🤔 正在分析大纲并匹配图表...[/cyan]")
        console.print("[dim]（AI 思考中，通常需要 2-3 分钟，请耐心等待）[/dim]")
        
        # 使用动态进度显示
        import time
        from rich.live import Live
        from rich.text import Text
        
        start_time = time.time()
        response = None
        
        async def call_api():
            nonlocal response
            options = LLMOptions(max_tokens=8192)
            response = await self.thinking_provider.invoke(
                prompt=prompt,
                options=options,
            )
        
        # 创建异步任务
        api_task = asyncio.create_task(call_api())
        
        # 简单的等待动画，只显示真实的等待时间
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frame_idx = 0
        
        with Live(console=console, refresh_per_second=8) as live:
            while not api_task.done():
                elapsed = time.time() - start_time
                frame = spinner_frames[frame_idx % len(spinner_frames)]
                frame_idx += 1
                
                # 格式化时间显示
                if elapsed >= 60:
                    time_str = f"{int(elapsed // 60)}分{int(elapsed % 60)}秒"
                else:
                    time_str = f"{int(elapsed)}秒"
                
                spinner_text = Text()
                spinner_text.append(f"{frame} ", style="cyan")
                spinner_text.append("AI 思考中...", style="cyan")
                spinner_text.append(f"  [{time_str}]", style="dim")
                
                live.update(spinner_text)
                await asyncio.sleep(0.1)
        
        # 等待任务完成
        await api_task
        
        elapsed = time.time() - start_time
        if elapsed >= 60:
            time_str = f"{int(elapsed // 60)}分{elapsed % 60:.0f}秒"
        else:
            time_str = f"{elapsed:.1f}秒"
        console.print(f"[green]✓ 分析完成 ({time_str})[/green]")
        
        # 解析 JSON 响应
        content = response.content or ""
        
        # 尝试提取 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析
            json_str = content
        
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError as e:
            console.print(f"[red]JSON 解析失败: {e}[/red]")
            console.print("[dim]原始响应:[/dim]")
            console.print(content[:1000])
            raise ValueError("AI 返回的格式不正确，请重试")
    
    async def generate_missing_diagrams(
        self,
        paper_title: str,
        missing_diagrams: list[dict],
        output_dir: Path,
        mode: str = "auto",
    ) -> list[dict]:
        """
        生成缺失的图表
        
        Args:
            paper_title: 论文标题
            missing_diagrams: 缺失图表列表
            output_dir: 输出目录
            mode: 生成模式 - "auto"（全部自动）, "confirm"（逐个确认）, "skip"（跳过）
            
        Returns:
            生成的图表信息列表
        """
        if not missing_diagrams or mode == "skip":
            return []
        
        from ..diagram import MermaidRenderer
        renderer = MermaidRenderer()
        
        generated = []
        
        for i, diagram in enumerate(missing_diagrams, 1):
            caption = diagram.get("caption", f"图表{i}")
            diagram_type = diagram.get("type", "flowchart")
            mermaid_code = diagram.get("mermaid_code", "")
            
            if mode == "confirm":
                console.print(f"\n[cyan]📊 [{i}/{len(missing_diagrams)}] {caption}[/cyan]")
                console.print(Panel(
                    Syntax(mermaid_code, "text", theme="monokai"),
                    title="Mermaid 代码",
                ))
                
                action = Prompt.ask(
                    "操作",
                    choices=["确认", "编辑", "重新生成", "跳过"],
                    default="确认"
                )
                
                if action == "跳过":
                    continue
                elif action == "编辑":
                    console.print("[dim]请输入新的 Mermaid 代码（输入 END 结束）:[/dim]")
                    lines = []
                    while True:
                        line = input()
                        if line.strip() == "END":
                            break
                        lines.append(line)
                    mermaid_code = "\n".join(lines)
                elif action == "重新生成":
                    # 重新调用 AI 生成
                    prompt = build_mermaid_generation_prompt(
                        paper_title=paper_title,
                        diagram_type=diagram_type,
                        diagram_caption=caption,
                        section_title=diagram.get("section_id", ""),
                        diagram_description=diagram.get("description", caption),
                    )
                    response = await self.thinking_provider.invoke(
                        prompt=prompt,
                        options=LLMOptions(max_tokens=2000),
                    )
                    mermaid_code = response.content.strip() if response.content else mermaid_code
            
            # 渲染图表
            output_path = output_dir / f"{diagram.get('id', f'fig{i}')}.png"
            
            try:
                console.print(f"  渲染: {caption}...", end="")
                await renderer.render_async(mermaid_code, output_path)
                console.print(f" [green]✓ {output_path}[/green]")
                
                generated.append({
                    "id": diagram.get("id"),
                    "path": str(output_path.relative_to(output_dir.parent)),
                    "caption": caption,
                    "mermaid_code": mermaid_code,
                })
            except Exception as e:
                console.print(f" [red]✗ 渲染失败: {e}[/red]")
        
        return generated
    
    def build_paper(self, config: dict) -> Paper:
        """
        从配置字典构建 Paper 对象
        
        Args:
            config: 解析后的配置字典
            
        Returns:
            Paper 对象
        """
        paper_config = config.get("paper", {})
        sections_config = config.get("sections", [])
        
        def build_section(s: dict, level: int = 1) -> Section:
            """递归构建 Section"""
            figures = []
            for f in s.get("figures", []):
                # 解析 fig_type，支持新旧格式
                fig_type_str = f.get("fig_type", "matched")
                try:
                    fig_type = FigureType(fig_type_str)
                except ValueError:
                    # 兼容旧格式，根据其他字段推断
                    if f.get("source") == "local" or f.get("path"):
                        fig_type = FigureType.MATCHED
                    elif f.get("mermaid_code"):
                        fig_type = FigureType.GENERATE
                    else:
                        fig_type = FigureType.SUGGESTED
                
                figures.append(Figure(
                    id=f.get("id", ""),
                    fig_type=fig_type,
                    path=f.get("path"),  # 现在是可选的
                    caption=f.get("caption", ""),
                    description=f.get("description", ""),
                    suggestion=f.get("suggestion"),
                    can_generate=f.get("can_generate", fig_type == FigureType.GENERATE),
                    mermaid_code=f.get("mermaid_code"),
                ))
            
            tables = []
            for t in s.get("tables", []):
                tables.append(Table(
                    id=t.get("id", ""),
                    path=t.get("path", ""),
                    caption=t.get("caption", ""),
                    content="",
                    description=t.get("description", ""),
                ))
            
            children = []
            for child in s.get("children", []):
                children.append(build_section(child, level + 1))
            
            return Section(
                id=s.get("id", ""),
                title=s.get("title", ""),
                level=s.get("level", level),
                target_words=s.get("target_words"),
                notes=s.get("notes"),
                figures=figures,
                tables=tables,
                children=children,
            )
        
        sections = []
        for s in sections_config:
            sections.append(build_section(s))
        
        return Paper(
            title=paper_config.get("title", ""),
            keywords=paper_config.get("keywords", []),
            keywords_en=paper_config.get("keywords_en", []),
            target_words=paper_config.get("target_words", 10000),
            status=PaperStatus.PENDING_OUTLINE,
            sections=sections,
        )


async def run_init_interactive(
    paper_title: str,
    thinking_provider: "LLMProvider",
    images_path: str | Path | None = None,
    output_path: str | Path | None = None,
    target_words: int = 8000,
) -> Paper:
    """
    交互式运行大纲初始化
    
    Args:
        paper_title: 论文标题
        thinking_provider: 思考模型
        images_path: 图片目录路径
        output_path: 输出 YAML 路径
        target_words: 目标字数
        
    Returns:
        生成的 Paper 对象
    """
    from ..config.settings import save_outline
    
    initializer = OutlineInitializer(
        thinking_provider=thinking_provider,
        images_path=images_path,
    )
    
    # 显示欢迎信息
    console.print(Panel(
        f"[bold]论文标题[/bold]: {paper_title}\n"
        f"[bold]目标字数[/bold]: {target_words}\n"
        f"[bold]图片目录[/bold]: {images_path or '（未指定）'}",
        title="📝 AIWrite 大纲初始化",
    ))
    
    # 扫描本地资源
    images = await initializer.scan_images()
    tables = initializer.scan_tables()
    
    # 输入大纲
    console.print("\n[bold cyan]请粘贴论文大纲（输入 END 结束）:[/bold cyan]")
    outline_lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            outline_lines.append(line)
        except EOFError:
            break
    
    outline_text = "\n".join(outline_lines)
    
    if not outline_text.strip():
        raise ValueError("大纲不能为空")
    
    # 解析大纲
    config = await initializer.parse_outline(
        paper_title=paper_title,
        outline_text=outline_text,
        images=images,
        tables=tables,
        target_words=target_words,
    )
    
    # 显示匹配结果
    sections = config.get("sections", [])
    console.print(f"\n[green]✓ 识别到 {len(sections)} 个章节[/green]")
    
    matched_figures = 0
    matched_tables = 0
    
    def count_resources(s: dict):
        nonlocal matched_figures, matched_tables
        matched_figures += len(s.get("figures", []))
        matched_tables += len(s.get("tables", []))
        for child in s.get("children", []):
            count_resources(child)
    
    for s in sections:
        count_resources(s)
    
    console.print(f"[green]✓ 已匹配 {matched_figures} 个图片[/green]")
    console.print(f"[green]✓ 已匹配 {matched_tables} 个表格[/green]")
    
    # 处理缺失的图表
    missing_diagrams = config.get("missing_diagrams", [])
    if missing_diagrams:
        console.print(f"\n[yellow]⚠ 需要生成 {len(missing_diagrams)} 个图表[/yellow]")
        for d in missing_diagrams:
            console.print(f"  - {d.get('caption', '未命名')}")
        
        mode = Prompt.ask(
            "\n请选择生成方式",
            choices=["auto", "confirm", "skip"],
            default="auto"
        )
        
        if mode != "skip" and images_path:
            output_dir = Path(images_path)
            generated = await initializer.generate_missing_diagrams(
                paper_title=paper_title,
                missing_diagrams=missing_diagrams,
                output_dir=output_dir,
                mode=mode,
            )
            
            # 更新配置，将生成的图表添加到对应章节
            # TODO: 根据 section_id 添加到正确的章节
    
    # 构建 Paper 对象
    paper = initializer.build_paper(config)
    
    # 保存 YAML
    if output_path:
        output_path = Path(output_path)
        save_outline(paper, output_path)
        console.print(f"\n[green]✓ 大纲已保存: {output_path}[/green]")
    
    console.print(Panel(
        f"下一步: python -m aiwrite generate-draft {output_path or 'your_outline.yaml'}",
        title="✅ 初始化完成",
    ))
    
    return paper
