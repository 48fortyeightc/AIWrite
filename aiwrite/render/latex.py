"""
LaTeX 渲染器

将论文内容组装成完整的 LaTeX 文档
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, BaseLoader

from ..models import Paper, Section


# 默认 LaTeX 模板
DEFAULT_LATEX_TEMPLATE = r"""
\documentclass[12pt, a4paper]{article}

% 中文支持
\usepackage{ctex}

% 页面设置
\usepackage{geometry}
\geometry{left=2.5cm, right=2.5cm, top=2.5cm, bottom=2.5cm}

% 常用宏包
\usepackage{amsmath, amssymb, amsfonts}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{booktabs}
\usepackage{enumitem}
\usepackage{caption}
\usepackage{subcaption}
\usepackage{fancyhdr}
\usepackage{setspace}

% 行距设置
\onehalfspacing

% 超链接设置
\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    citecolor=blue,
    urlcolor=blue
}

% 页眉页脚
\pagestyle{fancy}
\fancyhf{}
\fancyhead[C]{\leftmark}
\fancyfoot[C]{\thepage}

% 标题信息
\title{ {{- title -}} }
\author{ {{- authors | join(' \\and ') -}} }
\date{\today}

\begin{document}

\maketitle

{% if abstract %}
\begin{abstract}
{{ abstract }}
\end{abstract}
{% endif %}

{% if keywords %}
\noindent\textbf{关键词：} {{ keywords | join('；') }}
\vspace{1em}
{% endif %}

\tableofcontents
\newpage

{% for section in sections %}
{{ section.content }}

{% endfor %}

{% if references %}
\begin{thebibliography}{99}
{% for ref in references %}
\bibitem{ {{- ref.key -}} } {{ ref.text }}
{% endfor %}
\end{thebibliography}
{% endif %}

\end{document}
"""


class LatexRenderer:
    """
    LaTeX 渲染器
    
    将 Paper 对象渲染为完整的 LaTeX 文档
    """

    def __init__(
        self,
        template_path: str | Path | None = None,
        template_string: str | None = None,
    ):
        """
        初始化渲染器
        
        Args:
            template_path: 自定义模板文件路径
            template_string: 自定义模板字符串
        """
        if template_path:
            template_dir = Path(template_path).parent
            template_name = Path(template_path).name
            self.env = Environment(loader=FileSystemLoader(str(template_dir)))
            self.template = self.env.get_template(template_name)
        elif template_string:
            from jinja2 import Template
            self.template = Template(template_string)
        else:
            from jinja2 import Template
            self.template = Template(DEFAULT_LATEX_TEMPLATE)

    def render(self, paper: Paper, use_final: bool = True) -> str:
        """
        渲染论文为 LaTeX 文档
        
        Args:
            paper: 论文对象
            use_final: 是否使用润色后的内容（否则使用草稿）
            
        Returns:
            完整的 LaTeX 文档字符串
        """
        # 准备模板数据
        sections_data = []
        abstract_content = None
        
        for section in paper.sections:
            section_content = self._render_section(section, use_final)
            
            # 检查是否是摘要
            if "摘要" in section.title.lower() or "abstract" in section.title.lower():
                abstract_content = section_content
            else:
                sections_data.append({
                    "title": section.title,
                    "content": section_content,
                })

        template_data = {
            "title": paper.title,
            "authors": paper.authors or [],
            "keywords": paper.keywords or [],
            "abstract": abstract_content,
            "sections": sections_data,
            "references": [],  # TODO: 解析参考文献
        }

        return self.template.render(**template_data)

    def _render_section(self, section: Section, use_final: bool) -> str:
        """渲染单个章节及其子章节"""
        # 获取内容
        if use_final and section.final_latex:
            content = section.final_latex
        elif section.draft_latex:
            content = section.draft_latex
        else:
            # 如果没有生成的内容，创建占位符
            content = f"% TODO: {section.title} 内容待生成\n"

        # 递归渲染子章节
        if section.children:
            children_content = []
            for child in section.children:
                children_content.append(self._render_section(child, use_final))
            content = content + "\n\n" + "\n\n".join(children_content)

        return content

    def render_to_file(
        self,
        paper: Paper,
        output_path: str | Path,
        use_final: bool = True,
    ) -> Path:
        """
        渲染论文并保存到文件
        
        Args:
            paper: 论文对象
            output_path: 输出文件路径
            use_final: 是否使用润色后的内容
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        latex_content = self.render(paper, use_final)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        return output_path
