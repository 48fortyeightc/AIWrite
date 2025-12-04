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

from ..models import Paper, Section, Figure
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

        # 关键词
        if paper.keywords:
            kw_para = doc.add_paragraph()
            kw_bold = kw_para.add_run("关键词：")
            kw_bold.bold = True
            kw_para.add_run("；".join(paper.keywords))
            kw_para.space_after = Pt(12)
            kw_para.paragraph_format.first_line_indent = Cm(0)

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
            self._add_section_to_doc(doc, section, use_final, level=1, is_first_section=(i==0))

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
    ) -> None:
        """添加章节到 Word 文档"""
        from docx.shared import Pt, Cm, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        # 获取内容
        content = ""
        if use_final and section.final_latex:
            content = section.final_latex
        elif section.draft_latex:
            content = section.draft_latex

        # 检查内容中是否包含 \subsection（说明内容已经包含子标题）
        has_subsections_in_content = bool(re.search(r"\\subsection\{", content))
        
        # 只有当内容中没有包含子标题时，才添加标题
        # 否则标题会由 _add_latex_content_to_doc 处理
        if not has_subsections_in_content or section.level == 0:
            # 添加标题（使用 Word 内置标题样式）
            heading_level = min(level, 9)
            heading = doc.add_heading(section.title, level=heading_level)
            
            # 设置标题字体
            for run in heading.runs:
                run.font.name = '黑体'
                run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
            
            heading.paragraph_format.first_line_indent = Cm(0)

        if content:
            # 解析 LaTeX 内容并添加到文档（包括处理 \subsection）
            self._add_latex_content_to_doc(doc, content, level, section.figures)
        
        # 如果没有内容但有图片，单独添加图片
        if not content and section.figures:
            self._add_figures_to_doc(doc, section.figures)

        # 只有当内容中没有包含子章节时，才递归处理子章节
        # 避免重复输出
        if not has_subsections_in_content:
            for child in section.children:
                self._add_section_to_doc(doc, child, use_final, level + 1)

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
            # 确定图片路径
            if self.images_base_path:
                image_path = self.images_base_path / figure.path
            else:
                image_path = Path(figure.path)
            
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

    def _add_latex_content_to_doc(
        self,
        doc: "Document",
        latex_content: str,
        base_level: int = 1,
        figures: list[Figure] | None = None,
    ) -> None:
        """将 LaTeX 内容转换并添加到 Word 文档"""
        from docx.shared import Pt, Cm, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        figures = figures or []
        figure_map = {f.id: f for f in figures}
        figures_inserted = set()

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
        
        # 使用特殊标记分割章节和内容
        # 将 \section{...} \subsection{...} 等替换为特殊标记
        content = re.sub(r"\\section\{([^}]*)\}", r"\n\n<<HEADING:1:\1>>\n\n", content)
        content = re.sub(r"\\subsection\{([^}]*)\}", r"\n\n<<HEADING:2:\1>>\n\n", content)
        content = re.sub(r"\\subsubsection\{([^}]*)\}", r"\n\n<<HEADING:3:\1>>\n\n", content)
        
        # 移除其他 LaTeX 命令但保留内容
        content = re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", content)
        content = re.sub(r"\\[a-zA-Z]+\*?", "", content)
        content = re.sub(r"[{}]", "", content)
        
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
        for fig_id, fig in figure_map.items():
            if fig_id not in figures_inserted:
                self._insert_figure(doc, fig)

    def _insert_figure(
        self,
        doc: "Document",
        figure: Figure,
    ) -> None:
        """插入单张图片"""
        from docx.shared import Pt, Cm, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        # 确定图片路径
        if self.images_base_path:
            image_path = self.images_base_path / figure.path
        else:
            image_path = Path(figure.path)
        
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
