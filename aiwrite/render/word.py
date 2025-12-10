"""
Word 导出器

将论文导出为规范的 Word 文档
"""

from __future__ import annotations

import subprocess
import shutil
import re
from pathlib import Path
from typing import Literal, TYPE_CHECKING

from rich.console import Console

from ..models import Paper, Section, Figure, Table
from .latex import LatexRenderer

if TYPE_CHECKING:
    from docx import Document

console = Console()


class WordExporter:
    """
    Word 导出器
    
    将论文导出为 Word (.docx) 文档
    支持两种方式：
    1. LaTeX → Word (通过 pandoc)
    2. 直接生成 Word (通过 python-docx)
    """

    def __init__(
        self,
        method: Literal["pandoc", "docx"] = "docx",
        pandoc_path: str | None = None,
        reference_doc: str | Path | None = None,
        images_base_path: str | Path | None = None,
    ):
        """
        初始化导出器
        
        Args:
            method: 导出方法，"pandoc" 或 "docx"（默认改为 docx）
            pandoc_path: pandoc 可执行文件路径
            reference_doc: Word 参考模板文件（用于样式）
            images_base_path: 图片文件的基础路径
        """
        self.method = method
        self.pandoc_path = pandoc_path or self._find_pandoc()
        self.reference_doc = Path(reference_doc) if reference_doc else None
        self.images_base_path = Path(images_base_path) if images_base_path else None
        self.latex_renderer = LatexRenderer()

    def _resolve_image_path(self, figure_path: str) -> Path:
        """
        智能解析图片路径，避免路径重复拼接
        
        例如：
        - images_base_path = D:/project/img
        - figure_path = img/1.png
        - 结果应为 D:/project/img/1.png 而不是 D:/project/img/img/1.png
        """
        figure_path_obj = Path(figure_path)
        
        if not self.images_base_path:
            return figure_path_obj
        
        # 直接拼接的路径
        direct_path = self.images_base_path / figure_path
        
        # 如果直接拼接的路径存在，使用它
        if direct_path.exists():
            return direct_path
        
        # 检查是否有路径重复（如 base=.../img, path=img/1.png）
        # 尝试只使用文件名
        filename_only = self.images_base_path / figure_path_obj.name
        if filename_only.exists():
            return filename_only
        
        # 尝试去掉 figure_path 的第一层目录
        parts = figure_path_obj.parts
        if len(parts) > 1:
            without_first = Path(*parts[1:])
            alt_path = self.images_base_path / without_first
            if alt_path.exists():
                return alt_path
        
        # 都不存在，返回直接拼接的路径（让后续代码处理不存在的情况）
        return direct_path

    def _find_pandoc(self) -> str | None:
        """查找 pandoc 可执行文件"""
        pandoc_path = shutil.which("pandoc")
        return pandoc_path

    def check_pandoc(self) -> bool:
        """检查 pandoc 是否可用"""
        if not self.pandoc_path:
            return False
        try:
            result = subprocess.run(
                [self.pandoc_path, "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def export(
        self,
        paper: Paper,
        output_path: str | Path,
        use_final: bool = True,
    ) -> Path:
        """
        导出论文为 Word 文档
        
        Args:
            paper: 论文对象
            output_path: 输出文件路径
            use_final: 是否使用润色后的内容
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.method == "pandoc":
            return self._export_via_pandoc(paper, output_path, use_final)
        else:
            return self._export_via_docx(paper, output_path, use_final)

    def _export_via_pandoc(
        self,
        paper: Paper,
        output_path: Path,
        use_final: bool,
    ) -> Path:
        """通过 pandoc 导出"""
        if not self.check_pandoc():
            raise RuntimeError(
                "pandoc 未安装或不可用。请先安装 pandoc: https://pandoc.org/installing.html"
            )

        console.print("[cyan]📄 正在生成 LaTeX 文件...[/cyan]")

        # 先生成 LaTeX 文件
        latex_path = output_path.with_suffix(".tex")
        self.latex_renderer.render_to_file(paper, latex_path, use_final)

        console.print("[cyan]🔄 正在转换为 Word 文档...[/cyan]")

        # 构建 pandoc 命令
        cmd = [
            self.pandoc_path,
            str(latex_path),
            "-o", str(output_path),
            "--from", "latex",
            "--to", "docx",
        ]

        if self.reference_doc and self.reference_doc.exists():
            cmd.extend(["--reference-doc", str(self.reference_doc)])

        # 执行转换
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=latex_path.parent,
        )

        if result.returncode != 0:
            console.print(f"[red]pandoc 错误: {result.stderr}[/red]")
            raise RuntimeError(f"pandoc 转换失败: {result.stderr}")

        console.print(f"[green]✓ Word 文档已生成: {output_path}[/green]")

        return output_path

    def _export_via_docx(
        self,
        paper: Paper,
        output_path: Path,
        use_final: bool,
    ) -> Path:
        """通过 python-docx 直接生成 Word"""
        try:
            from docx import Document
            from docx.shared import Pt, Inches, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.enum.style import WD_STYLE_TYPE
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
        except ImportError:
            raise RuntimeError(
                "python-docx 未安装。请运行: pip install python-docx"
            )

        console.print("[cyan]📄 正在直接生成 Word 文档...[/cyan]")

        doc = Document()
        
        # 设置文档默认字体和段落格式
        self._set_document_defaults(doc)

        # 论文标题
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(paper.title)
        title_run.bold = True
        title_run.font.size = Pt(22)
        title_run.font.name = '黑体'
        title_run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_para.paragraph_format.first_line_indent = Cm(0)  # 标题不缩进
        title_para.space_after = Pt(24)

        # 作者
        if paper.authors:
            author_para = doc.add_paragraph()
            author_run = author_para.add_run(", ".join(paper.authors))
            author_run.font.size = Pt(12)
            author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            author_para.paragraph_format.first_line_indent = Cm(0)

        doc.add_page_break()

        # 添加目录标题
        toc_title = doc.add_paragraph()
        toc_run = toc_title.add_run("目  录")
        toc_run.bold = True
        toc_run.font.size = Pt(16)
        toc_run.font.name = '黑体'
        toc_run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        toc_title.paragraph_format.first_line_indent = Cm(0)
        toc_title.space_after = Pt(18)

        # 添加目录域（需要用户手动更新）
        self._add_toc_field(doc)
        
        doc.add_paragraph()  # 空行
        hint_para = doc.add_paragraph()
        hint_run = hint_para.add_run('（请右键点击目录，选择"更新域"以生成目录）')
        hint_run.italic = True
        hint_para.paragraph_format.first_line_indent = Cm(0)

        # 章节内容
        for i, section in enumerate(paper.sections):
            # 每个主要章节前添加分页符
            doc.add_page_break()
            self._add_section_to_doc(doc, section, use_final, level=1, is_first_section=(i==0), keywords=paper.keywords, keywords_en=paper.keywords_en)

        # 保存文档
        doc.save(str(output_path))
        console.print(f"[green]✓ Word 文档已生成: {output_path}[/green]")

        return output_path

    def _set_document_defaults(self, doc: "Document") -> None:
        """设置文档默认样式"""
        from docx.shared import Pt, Cm
        from docx.oxml.ns import qn

        # 设置正文样式
        style = doc.styles['Normal']
        style.font.name = '宋体'
        style.font.size = Pt(12)
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.first_line_indent = Cm(0.74)  # 首行缩进2字符

        # 设置标题样式
        for i in range(1, 4):
            heading_style = doc.styles[f'Heading {i}']
            if i == 1:
                heading_style.font.size = Pt(16)
            elif i == 2:
                heading_style.font.size = Pt(14)
            else:
                heading_style.font.size = Pt(12)
            heading_style.font.name = '黑体'
            heading_style.font.bold = True
            heading_style._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
            heading_style.paragraph_format.first_line_indent = Cm(0)  # 标题不缩进
            heading_style.paragraph_format.space_before = Pt(12)
            heading_style.paragraph_format.space_after = Pt(6)

    def _add_toc_field(self, doc: "Document") -> None:
        """添加目录域"""
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        paragraph = doc.add_paragraph()
        run = paragraph.add_run()
        
        # 创建复杂域
        fldChar1 = OxmlElement('w:fldChar')
        fldChar1.set(qn('w:fldCharType'), 'begin')
        
        instrText = OxmlElement('w:instrText')
        instrText.set(qn('xml:space'), 'preserve')
        instrText.text = 'TOC \\o "1-3" \\h \\z \\u'
        
        fldChar2 = OxmlElement('w:fldChar')
        fldChar2.set(qn('w:fldCharType'), 'separate')
        
        fldChar3 = OxmlElement('w:fldChar')
        fldChar3.set(qn('w:fldCharType'), 'end')
        
        run._r.append(fldChar1)
        run._r.append(instrText)
        run._r.append(fldChar2)
        run._r.append(fldChar3)

    def _add_section_to_doc(
        self,
        doc: "Document",
        section: "Section",
        use_final: bool,
        level: int,
        is_first_section: bool = False,
        keywords: list[str] | None = None,
        keywords_en: list[str] | None = None,
    ) -> None:
        """添加章节到 Word 文档
        
        Args:
            keywords: 中文关键词列表，仅在摘要章节后输出
            keywords_en: 英文关键词列表，仅在英文摘要章节后输出
        """
        from docx.shared import Pt, Cm, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        # 获取内容
        content = ""
        if use_final and section.final_latex:
            content = section.final_latex
        elif section.draft_latex:
            content = section.draft_latex

        # 始终添加章节标题（不管内容中是否有子标题）
        heading_level = min(level, 9)
        heading = doc.add_heading(section.title, level=heading_level)
        
        # 设置标题字体
        for run in heading.runs:
            run.font.name = '黑体'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        
        heading.paragraph_format.first_line_indent = Cm(0)

        if content:
            # 收集本章节及所有子章节的图片和表格
            all_figures = self._collect_all_figures(section)
            all_tables = self._collect_all_tables(section)
            # 解析 LaTeX 内容并添加到文档（包括处理 \subsection）
            self._add_latex_content_to_doc(doc, content, level, all_figures, all_tables)
        
        # 如果是摘要章节，在内容后添加关键词
        if keywords and section.id in ("abstract-zh", "abstract", "摘要"):
            kw_para = doc.add_paragraph()
            kw_bold = kw_para.add_run("关键词：")
            kw_bold.bold = True
            kw_bold.font.name = '宋体'
            kw_bold._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            kw_run = kw_para.add_run("；".join(keywords))
            kw_run.font.name = '宋体'
            kw_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            kw_para.paragraph_format.first_line_indent = Cm(0)
            kw_para.space_after = Pt(12)
        
        # 如果是英文摘要章节，在内容后添加 Keywords
        if keywords and section.id in ("abstract-en", "Abstract"):
            kw_para = doc.add_paragraph()
            kw_bold = kw_para.add_run("Keywords: ")
            kw_bold.bold = True
            # 使用英文关键词（如果有），否则使用中文关键词
            kw_en = keywords_en if keywords_en else keywords
            kw_para.add_run("; ".join(kw_en))
            kw_para.paragraph_format.first_line_indent = Cm(0)
            kw_para.space_after = Pt(12)
        
        # 如果没有内容但有图片，单独添加图片
        if not content and section.figures:
            self._add_figures_to_doc(doc, section.figures)

        # 递归处理子章节（如果没有内容或内容中没有\subsection）
        # 如果内容中已经包含\subsection，说明子标题已经在内容中了，不需要递归
        has_subsections_in_content = bool(re.search(r"\\subsection\{", content))
        if not has_subsections_in_content:
            for child in section.children:
                self._add_section_to_doc(doc, child, use_final, level + 1, keywords=keywords, keywords_en=keywords_en)

    def _add_figures_to_doc(
        self,
        doc: "Document",
        figures: list[Figure],
    ) -> None:
        """添加图片到文档"""
        from docx.shared import Pt, Cm, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        for figure in figures:
            # 确定图片路径（智能处理路径重复）
            image_path = self._resolve_image_path(figure.path)
            
            # 添加图片
            if image_path.exists():
                try:
                    # 添加图片（宽度为页面宽度的 80%）
                    para = doc.add_paragraph()
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = para.add_run()
                    run.add_picture(str(image_path), width=Inches(5))
                    
                    # 添加图片标题
                    caption_para = doc.add_paragraph()
                    caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    caption_run = caption_para.add_run(f"图 {figure.id}: {figure.caption}")
                    caption_run.font.name = '宋体'
                    caption_run.font.size = Pt(10)
                    caption_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                    caption_para.paragraph_format.first_line_indent = Cm(0)
                    caption_para.space_after = Pt(12)
                    
                    console.print(f"[green]  ✓ 插入图片: {figure.caption}[/green]")
                except Exception as e:
                    console.print(f"[yellow]  ⚠ 图片插入失败 {figure.path}: {e}[/yellow]")
                    # 添加占位符
                    self._add_figure_placeholder(doc, figure)
            else:
                console.print(f"[yellow]  ⚠ 图片不存在: {image_path}[/yellow]")
                # 添加占位符
                self._add_figure_placeholder(doc, figure)

    def _add_figure_placeholder(
        self,
        doc: "Document",
        figure: Figure,
    ) -> None:
        """添加图片占位符"""
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(f"[图 {figure.id}: {figure.caption}]")
        run.font.name = '宋体'
        run.font.size = Pt(10)
        run.italic = True
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        para.paragraph_format.first_line_indent = Cm(0)
        
        if figure.description:
            desc_para = doc.add_paragraph()
            desc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            desc_run = desc_para.add_run(f"（{figure.description[:100]}...）" if len(figure.description) > 100 else f"（{figure.description}）")
            desc_run.font.name = '宋体'
            desc_run.font.size = Pt(9)
            desc_run.italic = True
            desc_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            desc_para.paragraph_format.first_line_indent = Cm(0)

    def _insert_table(
        self,
        doc: "Document",
        table: Table,
    ) -> None:
        """插入表格到文档"""
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        
        # 如果有 path，从 Excel 读取表格内容
        if table.path:
            try:
                from ..utils.excel import read_excel_file
                
                # 确定表格路径（智能处理路径重复）
                table_path = self._resolve_image_path(table.path)
                
                if table_path.exists():
                    rows = read_excel_file(table_path)
                    if rows:
                        self._create_word_table(doc, rows, table)
                        console.print(f"[green]  ✓ 插入表格: {table.caption}[/green]")
                        return
                    else:
                        console.print(f"[yellow]  ⚠ 表格文件为空: {table_path}[/yellow]")
                else:
                    console.print(f"[yellow]  ⚠ 表格文件不存在: {table_path}[/yellow]")
            except Exception as e:
                console.print(f"[red]  ✗ 读取表格失败 {table.path}: {e}[/red]")
        
        # 如果有 content（Markdown 格式），解析并创建表格
        if table.content:
            rows = self._parse_markdown_table(table.content)
            if rows:
                self._create_word_table(doc, rows, table)
                console.print(f"[green]  ✓ 插入表格: {table.caption}[/green]")
                return
        
        # 否则添加占位符
        self._add_table_placeholder(doc, table)

    def _create_word_table(
        self,
        doc: "Document",
        rows: list[list[str]],
        table: Table,
    ) -> None:
        """创建 Word 表格"""
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        
        if not rows:
            return
        
        num_rows = len(rows)
        num_cols = max(len(row) for row in rows)
        
        # 创建表格
        word_table = doc.add_table(rows=num_rows, cols=num_cols)
        word_table.style = 'Table Grid'
        word_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # 填充表格内容
        for i, row in enumerate(rows):
            for j, cell_text in enumerate(row):
                if j < num_cols:
                    cell = word_table.rows[i].cells[j]
                    cell.text = cell_text
                    
                    # 设置单元格字体
                    for paragraph in cell.paragraphs:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        for run in paragraph.runs:
                            run.font.name = '宋体'
                            run.font.size = Pt(10)
                            run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                            # 表头加粗
                            if i == 0:
                                run.bold = True
        
        # 添加表格标题（在表格下方）
        caption_para = doc.add_paragraph()
        caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption_run = caption_para.add_run(f"表 {table.id}: {table.caption}")
        caption_run.font.name = '宋体'
        caption_run.font.size = Pt(10)
        caption_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        caption_para.paragraph_format.first_line_indent = Cm(0)
        caption_para.space_after = Pt(12)

    def _parse_markdown_table(self, content: str) -> list[list[str]]:
        """解析 Markdown 格式的表格"""
        lines = content.strip().split('\n')
        rows: list[list[str]] = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('|--') or line.startswith('| --'):
                continue  # 跳过分隔行
            if line.startswith('|'):
                # 解析表格行
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if cells:
                    rows.append(cells)
        
        return rows

    def _add_table_placeholder(
        self,
        doc: "Document",
        table: Table,
    ) -> None:
        """添加表格占位符"""
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(f"[表 {table.id}: {table.caption}]")
        run.font.name = '宋体'
        run.font.size = Pt(10)
        run.italic = True
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        para.paragraph_format.first_line_indent = Cm(0)
        
        if table.description:
            desc_para = doc.add_paragraph()
            desc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            desc_run = desc_para.add_run(f"（{table.description[:100]}...）" if len(table.description) > 100 else f"（{table.description}）")
            desc_run.font.name = '宋体'
            desc_run.font.size = Pt(9)
            desc_run.italic = True
            desc_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            desc_para.paragraph_format.first_line_indent = Cm(0)

    def _collect_all_figures(self, section: Section) -> list[Figure]:
        """递归收集章节及其所有子章节的图片"""
        all_figures: list[Figure] = []
        
        # 添加当前章节的图片
        all_figures.extend(section.figures)
        
        # 递归添加子章节的图片
        for child in section.children:
            all_figures.extend(self._collect_all_figures(child))
        
        return all_figures

    def _collect_all_tables(self, section: Section) -> list[Table]:
        """递归收集章节及其所有子章节的表格"""
        all_tables: list[Table] = []
        
        # 添加当前章节的表格
        all_tables.extend(section.tables)
        
        # 递归添加子章节的表格
        for child in section.children:
            all_tables.extend(self._collect_all_tables(child))
        
        return all_tables

    def _add_latex_content_to_doc(
        self,
        doc: "Document",
        latex_content: str,
        base_level: int = 1,
        figures: list[Figure] | None = None,
        tables: list[Table] | None = None,
    ) -> None:
        """将 LaTeX 内容转换并添加到 Word 文档"""
        from docx.shared import Pt, Cm, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        figures = figures or []
        tables = tables or []
        figure_map = {f.id: f for f in figures}
        # 同时用 caption 作为备用 key
        for f in figures:
            figure_map[f.caption] = f
        table_map = {t.id: t for t in tables}
        for t in tables:
            table_map[t.caption] = t
        figures_inserted = set()
        tables_inserted = set()

        # 先处理 LaTeX 转义符号
        content = latex_content
        content = content.replace("\\%", "%")
        content = content.replace("\\$", "$")
        content = content.replace("\\&", "&")
        content = content.replace("\\#", "#")
        content = content.replace("\\_", "_")
        content = content.replace("\\{", "{")
        content = content.replace("\\}", "}")
        
        # 处理数学公式 $...$
        content = re.sub(r"\$([^$]+)\$", r"\1", content)
        
        # 处理图表占位符 - 转换为特殊标记以便后续处理
        content = re.sub(r"\{\{FIGURE:([^:]*):([^}]*)\}\}", r"\n\n<<FIGURE:\1:\2>>\n\n", content)
        content = re.sub(r"\{\{TABLE:([^:]*):([^}]*)\}\}", r"\n\n<<TABLE:\1:\2>>\n\n", content)
        
        # 处理 \textbf{...} - 保留内容
        content = re.sub(r"\\textbf\{([^}]*)\}", r"\1", content)
        
        # 处理 \textit{...} 和 \emph{...}
        content = re.sub(r"\\textit\{([^}]*)\}", r"\1", content)
        content = re.sub(r"\\emph\{([^}]*)\}", r"\1", content)
        
        # 处理 \cite{...}
        content = re.sub(r"\\cite\{[^}]*\}", "[引用]", content)
        
        # 移除 \label{...} 和 \ref{...} 等引用命令（这些不应该出现在Word中）
        content = re.sub(r"\\label\{[^}]*\}", "", content)
        content = re.sub(r"\\ref\{[^}]*\}", "", content)
        content = re.sub(r"\\pageref\{[^}]*\}", "", content)
        content = re.sub(r"\\autoref\{[^}]*\}", "", content)
        
        # 使用特殊标记分割章节和内容
        # 将 \section{...} \subsection{...} 等替换为特殊标记 (LaTeX格式)
        content = re.sub(r"\\section\{([^}]*)\}", r"\n\n<<HEADING:1:\1>>\n\n", content)
        content = re.sub(r"\\subsection\{([^}]*)\}", r"\n\n<<HEADING:2:\1>>\n\n", content)
        content = re.sub(r"\\subsubsection\{([^}]*)\}", r"\n\n<<HEADING:3:\1>>\n\n", content)
        
        # 同时处理 Markdown 格式的标题
        # ### 三级标题
        content = re.sub(r"^### (.+)$", r"\n\n<<HEADING:3:\1>>\n\n", content, flags=re.MULTILINE)
        # ## 二级标题
        content = re.sub(r"^## (.+)$", r"\n\n<<HEADING:2:\1>>\n\n", content, flags=re.MULTILINE)
        # # 一级标题 (章节主标题,通常已经在外面处理了,这里忽略)
        content = re.sub(r"^# .+$", r"", content, flags=re.MULTILINE)
        
        # 移除其他 LaTeX 命令但保留内容
        content = re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", content)
        content = re.sub(r"\\[a-zA-Z]+\*?", "", content)
        content = re.sub(r"[{}]", "", content)
        
        # 移除残留的 sec: subsec: 等标签文本
        content = re.sub(r"\b(sec|subsec|fig|tab|eq|chap):[a-zA-Z0-9_-]+\b", "", content)
        
        # 清理多余空行
        content = re.sub(r"\n{3,}", "\n\n", content)
        
        # 按段落分割并添加
        paragraphs = content.strip().split("\n\n")
        for para_text in paragraphs:
            para_text = para_text.strip()
            
            # 跳过空段落
            if not para_text or len(para_text) < 2:
                continue
            
            # 检查是否是标题标记
            heading_match = re.match(r"<<HEADING:(\d+):(.+)>>", para_text)
            if heading_match:
                heading_rel_level = int(heading_match.group(1))
                heading_title = heading_match.group(2).strip()
                # 计算实际的标题级别
                actual_level = base_level + heading_rel_level - 1
                actual_level = min(actual_level, 9)
                
                heading = doc.add_heading(heading_title, level=actual_level)
                for run in heading.runs:
                    run.font.name = '黑体'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
                heading.paragraph_format.first_line_indent = Cm(0)
                continue
            
            # 检查是否是图片标记
            figure_match = re.match(r"<<FIGURE:([^:]*):([^>]*)>>", para_text)
            if figure_match:
                fig_caption = figure_match.group(1).strip()
                fig_desc = figure_match.group(2).strip()
                
                # 尝试查找匹配的真实图片
                matched_figure = None
                for fig_id, fig in figure_map.items():
                    if fig.caption == fig_caption or fig_id not in figures_inserted:
                        matched_figure = fig
                        figures_inserted.add(fig_id)
                        break
                
                if matched_figure:
                    # 插入真实图片
                    self._insert_figure(doc, matched_figure)
                else:
                    # 添加占位符
                    para = doc.add_paragraph()
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = para.add_run(f"[图: {fig_caption}]")
                    run.font.name = '宋体'
                    run.font.size = Pt(10)
                    run.italic = True
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                    para.paragraph_format.first_line_indent = Cm(0)
                    
                    if fig_desc:
                        desc_para = doc.add_paragraph()
                        desc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        desc_run = desc_para.add_run(f"说明: {fig_desc}")
                        desc_run.font.name = '宋体'
                        desc_run.font.size = Pt(9)
                        desc_run.italic = True
                        desc_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                        desc_para.paragraph_format.first_line_indent = Cm(0)
                continue
            
            # 检查是否是表格标记
            table_match = re.match(r"<<TABLE:([^:]*):([^>]*)>>", para_text)
            if table_match:
                tab_caption = table_match.group(1).strip()
                tab_desc = table_match.group(2).strip()
                
                # 尝试查找匹配的真实表格
                matched_table = None
                for tab_key, tab in table_map.items():
                    if tab.caption == tab_caption or tab_key not in tables_inserted:
                        matched_table = tab
                        tables_inserted.add(tab.id)
                        tables_inserted.add(tab.caption)
                        break
                
                if matched_table:
                    # 插入真实表格
                    self._insert_table(doc, matched_table)
                else:
                    # 添加占位符
                    para = doc.add_paragraph()
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = para.add_run(f"[表: {tab_caption}]")
                    run.font.name = '宋体'
                    run.font.size = Pt(10)
                    run.italic = True
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                    para.paragraph_format.first_line_indent = Cm(0)
                    
                    if tab_desc:
                        desc_para = doc.add_paragraph()
                        desc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        desc_run = desc_para.add_run(f"说明: {tab_desc}")
                        desc_run.font.name = '宋体'
                        desc_run.font.size = Pt(9)
                        desc_run.italic = True
                        desc_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                        desc_para.paragraph_format.first_line_indent = Cm(0)
                continue
            
            # 合并段落内的换行
            para_text = re.sub(r"\s*\n\s*", " ", para_text)
            para_text = re.sub(r"\s+", " ", para_text).strip()
            
            # 普通段落
            para = doc.add_paragraph()
            run = para.add_run(para_text)
            run.font.name = '宋体'
            run.font.size = Pt(12)
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            para.paragraph_format.first_line_indent = Cm(0.74)  # 首行缩进
            para.paragraph_format.line_spacing = 1.5
        
        # 插入剩余未插入的图片（在内容末尾）
        for fig in figures:
            if fig.id not in figures_inserted and fig.caption not in figures_inserted:
                self._insert_figure(doc, fig)
                figures_inserted.add(fig.id)
                figures_inserted.add(fig.caption)
        
        # 插入剩余未插入的表格（在内容末尾）
        for tab in tables:
            if tab.id not in tables_inserted and tab.caption not in tables_inserted:
                self._insert_table(doc, tab)
                tables_inserted.add(tab.id)
                tables_inserted.add(tab.caption)

    def _insert_figure(
        self,
        doc: "Document",
        figure: Figure,
    ) -> None:
        """插入单张图片"""
        from docx.shared import Pt, Cm, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        # 检查 path 是否存在且有效
        if not figure.path or figure.path.strip() in ('', '.', '..'):
            console.print(f"[yellow]  ⚠ 图片未指定路径: {figure.caption}[/yellow]")
            self._add_figure_placeholder(doc, figure)
            return

        # 确定图片路径（智能处理路径重复）
        image_path = self._resolve_image_path(figure.path)
        
        if image_path.exists():
            try:
                # 添加图片
                para = doc.add_paragraph()
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = para.add_run()
                run.add_picture(str(image_path), width=Inches(5))
                
                # 添加图片标题
                caption_para = doc.add_paragraph()
                caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption_run = caption_para.add_run(f"图 {figure.id}: {figure.caption}")
                caption_run.font.name = '宋体'
                caption_run.font.size = Pt(10)
                caption_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                caption_para.paragraph_format.first_line_indent = Cm(0)
                caption_para.space_after = Pt(12)
                
                console.print(f"[green]  ✓ 插入图片: {figure.caption}[/green]")
            except Exception as e:
                console.print(f"[yellow]  ⚠ 图片插入失败 {figure.path}: {e}[/yellow]")
                self._add_figure_placeholder(doc, figure)
        else:
            console.print(f"[yellow]  ⚠ 图片不存在: {image_path}[/yellow]")
            self._add_figure_placeholder(doc, figure)

    def _strip_latex_commands(self, text: str) -> str:
        """移除 LaTeX 命令，保留文本内容"""
        import re

        # 移除 \section{}, \subsection{} 等命令
        text = re.sub(r"\\(sub)*section\{[^}]*\}", "", text)
        
        # 移除 \textbf{...} 但保留内容
        text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\textit\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
        
        # 移除 \cite{...}
        text = re.sub(r"\\cite\{[^}]*\}", "[引用]", text)
        
        # 移除其他常见命令
        text = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", text)
        text = re.sub(r"\\[a-zA-Z]+", "", text)
        
        # 清理多余空白
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()
