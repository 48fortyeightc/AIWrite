"""
Word 导出器

使用 pandoc 将 LaTeX 转换为 Word 文档
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Literal

from rich.console import Console

from ..models import Paper
from .latex import LatexRenderer


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
        method: Literal["pandoc", "docx"] = "pandoc",
        pandoc_path: str | None = None,
        reference_doc: str | Path | None = None,
    ):
        """
        初始化导出器
        
        Args:
            method: 导出方法，"pandoc" 或 "docx"
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
            from docx.shared import Pt, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            raise RuntimeError(
                "python-docx 未安装。请运行: pip install python-docx"
            )

        console.print("[cyan]📄 正在直接生成 Word 文档...[/cyan]")

        doc = Document()

        # 标题
        title_para = doc.add_heading(paper.title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 作者
        if paper.authors:
            author_para = doc.add_paragraph(", ".join(paper.authors))
            author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 关键词
        if paper.keywords:
            kw_para = doc.add_paragraph()
            kw_para.add_run("关键词：").bold = True
            kw_para.add_run("；".join(paper.keywords))

        doc.add_page_break()

        # 章节内容
        for section in paper.sections:
            self._add_section_to_doc(doc, section, use_final, level=1)

        doc.save(str(output_path))
        console.print(f"[green]✓ Word 文档已生成: {output_path}[/green]")

        return output_path

    def _add_section_to_doc(
        self,
        doc: "Document",
        section: "Section",
        use_final: bool,
        level: int,
    ) -> None:
        """添加章节到 Word 文档"""
        # 添加标题
        doc.add_heading(section.title, level=min(level, 9))

        # 获取内容
        content = ""
        if use_final and section.final_latex:
            content = section.final_latex
        elif section.draft_latex:
            content = section.draft_latex

        if content:
            # 简单处理：移除 LaTeX 命令，保留文本
            content = self._strip_latex_commands(content)
            for para_text in content.split("\n\n"):
                para_text = para_text.strip()
                if para_text:
                    doc.add_paragraph(para_text)

        # 递归处理子章节
        for child in section.children:
            self._add_section_to_doc(doc, child, use_final, level + 1)

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
