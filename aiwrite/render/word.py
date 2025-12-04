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

from ..models import Paper, Section
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
    ):
        """
        初始化导出器
        
        Args:
            method: 导出方法，"pandoc" 或 "docx"（默认改为 docx）
            pandoc_path: pandoc 可执行文件路径
            reference_doc: Word 参考模板文件（用于样式）
        """
        self.method = method
        self.pandoc_path = pandoc_path or self._find_pandoc()
        self.reference_doc = Path(reference_doc) if reference_doc else None
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
        
        # 设置文档默认字体
        self._set_document_defaults(doc)

        # 论文标题
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(paper.title)
        title_run.bold = True
        title_run.font.size = Pt(22)
        title_run.font.name = '黑体'
        title_run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_para.space_after = Pt(24)

        # 作者
        if paper.authors:
            author_para = doc.add_paragraph()
            author_run = author_para.add_run(", ".join(paper.authors))
            author_run.font.size = Pt(12)
            author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 关键词
        if paper.keywords:
            kw_para = doc.add_paragraph()
            kw_bold = kw_para.add_run("关键词：")
            kw_bold.bold = True
            kw_para.add_run("；".join(paper.keywords))
            kw_para.space_after = Pt(12)

        doc.add_page_break()

        # 添加目录标题
        toc_title = doc.add_paragraph()
        toc_run = toc_title.add_run("目  录")
        toc_run.bold = True
        toc_run.font.size = Pt(16)
        toc_run.font.name = '黑体'
        toc_run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        toc_title.space_after = Pt(18)

        # 添加目录域（需要用户手动更新）
        self._add_toc_field(doc)
        
        doc.add_paragraph()  # 空行
        hint_para = doc.add_paragraph()
        hint_run = hint_para.add_run('（请右键点击目录，选择"更新域"以生成目录）')
        hint_run.italic = True

        doc.add_page_break()

        # 章节内容
        for section in paper.sections:
            self._add_section_to_doc(doc, section, use_final, level=1)

        # 保存文档
        doc.save(str(output_path))
        console.print(f"[green]✓ Word 文档已生成: {output_path}[/green]")

        return output_path

    def _set_document_defaults(self, doc: "Document") -> None:
        """设置文档默认样式"""
        from docx.shared import Pt
        from docx.oxml.ns import qn

        # 设置正文样式
        style = doc.styles['Normal']
        style.font.name = '宋体'
        style.font.size = Pt(12)
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.paragraph_format.line_spacing = 1.5

        # 设置标题样式
        for i in range(1, 4):
            heading_style = doc.styles[f'Heading {i}']
            if i == 1:
                heading_style.font.size = Pt(16)
                heading_style.font.name = '黑体'
            elif i == 2:
                heading_style.font.size = Pt(14)
                heading_style.font.name = '黑体'
            else:
                heading_style.font.size = Pt(12)
                heading_style.font.name = '黑体'
            heading_style.font.bold = True
            heading_style._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')

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
    ) -> None:
        """添加章节到 Word 文档"""
        from docx.shared import Pt
        from docx.oxml.ns import qn

        # 使用正确的 Word 内置标题样式（支持目录生成）
        heading_level = min(level, 9)  # Word 最多支持 9 级标题
        heading = doc.add_heading(level=heading_level)
        heading_run = heading.runs[0] if heading.runs else heading.add_run(section.title)
        if not heading.runs:
            heading_run = heading.add_run(section.title)
        else:
            heading_run.text = section.title
        
        # 设置中文字体
        heading_run.font.name = '黑体'
        heading_run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')

        # 获取内容
        content = ""
        if use_final and section.final_latex:
            content = section.final_latex
        elif section.draft_latex:
            content = section.draft_latex

        if content:
            # 解析 LaTeX 内容并添加到文档
            self._add_latex_content_to_doc(doc, content, section.title)

        # 递归处理子章节
        for child in section.children:
            self._add_section_to_doc(doc, child, use_final, level + 1)

    def _add_latex_content_to_doc(
        self,
        doc: "Document",
        latex_content: str,
        section_title: str,
    ) -> None:
        """将 LaTeX 内容转换并添加到 Word 文档"""
        from docx.shared import Pt
        from docx.oxml.ns import qn

        # 移除 \section{} 和 \subsection{} 命令（已由标题处理）
        content = re.sub(r"\\(sub)*section\{[^}]*\}", "", latex_content)
        
        # 处理 \textbf{...}
        content = re.sub(r"\\textbf\{([^}]*)\}", r"【\1】", content)
        
        # 处理 \textit{...} 和 \emph{...}
        content = re.sub(r"\\textit\{([^}]*)\}", r"\1", content)
        content = re.sub(r"\\emph\{([^}]*)\}", r"\1", content)
        
        # 处理 \cite{...}
        content = re.sub(r"\\cite\{[^}]*\}", "[引用]", content)
        
        # 移除其他 LaTeX 命令
        content = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", content)
        content = re.sub(r"\\[a-zA-Z]+", "", content)
        
        # 按段落分割并添加
        paragraphs = content.split("\n\n")
        for para_text in paragraphs:
            para_text = para_text.strip()
            # 跳过空段落和只有空白的段落
            if not para_text or para_text.isspace():
                continue
            # 跳过只包含标点的段落
            if len(para_text) < 5:
                continue
                
            para = doc.add_paragraph()
            run = para.add_run(para_text)
            run.font.name = '宋体'
            run.font.size = Pt(12)
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

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
