"""
数据模型定义：Paper, Section 等核心结构
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PaperStatus(str, Enum):
    """论文写作阶段状态"""
    PENDING_OUTLINE = "pending_outline"       # 等待生成大纲
    PENDING_CONFIRMATION = "pending_confirmation"  # 等待用户确认大纲
    OUTLINE_CONFIRMED = "outline_confirmed"   # 大纲已确认
    DRAFT = "draft"                           # 草稿阶段
    FINAL = "final"                           # 最终版


class FigureType(str, Enum):
    """图片类型"""
    MATCHED = "matched"      # 已匹配用户提供的图片
    GENERATE = "generate"    # 可自动生成（Mermaid）
    SUGGESTED = "suggested"  # AI 建议放图
    MISSING = "missing"      # 缺失，需用户补充


class Figure(BaseModel):
    """图片数据模型"""
    id: str = Field(..., description="图片唯一标识，如 fig3-1")
    path: str | None = Field(default=None, description="图片文件路径（matched 类型必填）")
    caption: str = Field(..., description="图片标题")
    description: str | None = Field(default=None, description="AI 识别的图片描述")
    position: str = Field(default="here", description="图片位置：here, top, bottom")
    # 新增字段
    fig_type: FigureType = Field(default=FigureType.MATCHED, description="图片类型")
    suggestion: str | None = Field(default=None, description="AI 建议（suggested/missing 类型）")
    can_generate: bool = Field(default=False, description="是否可用 Mermaid 自动生成")
    mermaid_code: str | None = Field(default=None, description="Mermaid 代码（generate 类型）")


class Table(BaseModel):
    """表格数据模型"""
    id: str = Field(..., description="表格唯一标识，如 tab3-1")
    caption: str = Field(..., description="表格标题")
    path: str | None = Field(default=None, description="Excel 文件路径（可选，用于自动读取表格内容）")
    content: str | None = Field(default=None, description="表格内容（Markdown 格式或从 Excel 读取）")
    description: str | None = Field(default=None, description="表格说明")


class Section(BaseModel):
    """章节数据模型"""
    id: str = Field(..., description="章节唯一标识，如 ch1, ch1.1")
    title: str = Field(..., description="章节标题")
    level: int = Field(..., description="层级：0=特殊区段，1=section，2=subsection，3=subsubsection")
    target_words: int | None = Field(default=None, description="目标字数")
    style: str | None = Field(default=None, description="写作风格")
    notes: str | None = Field(default=None, description="写作要点说明")
    children: list[Section] = Field(default_factory=list, description="子章节列表")
    figures: list[Figure] = Field(default_factory=list, description="本章节包含的图片")
    tables: list[Table] = Field(default_factory=list, description="本章节包含的表格")
    draft_latex: str | None = Field(default=None, description="草稿版 LaTeX 正文")
    final_latex: str | None = Field(default=None, description="最终版 LaTeX 正文")

    def get_all_sections(self) -> list[Section]:
        """递归获取本节及所有子节"""
        result = [self]
        for child in self.children:
            result.extend(child.get_all_sections())
        return result

    def find_section_by_id(self, section_id: str) -> Section | None:
        """根据 ID 查找章节"""
        if self.id == section_id:
            return self
        for child in self.children:
            found = child.find_section_by_id(section_id)
            if found:
                return found
        return None


class Paper(BaseModel):
    """论文数据模型"""
    title: str = Field(..., description="论文题目")
    authors: list[str] = Field(default_factory=list, description="作者列表")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    keywords_en: list[str] = Field(default_factory=list, description="英文关键词列表")
    abstract_cn: str | None = Field(default=None, description="中文摘要")
    abstract_en: str | None = Field(default=None, description="英文摘要")
    language: Literal["zh", "en"] = Field(default="zh", description="语言")
    style: str = Field(default="academic", description="写作风格")
    target_words: int = Field(default=8000, description="目标总字数")
    status: PaperStatus = Field(default=PaperStatus.PENDING_OUTLINE, description="当前状态")
    sections: list[Section] = Field(default_factory=list, description="章节列表")

    def get_all_sections(self) -> list[Section]:
        """获取所有章节（包括子章节）"""
        result = []
        for section in self.sections:
            result.extend(section.get_all_sections())
        return result

    def find_section_by_id(self, section_id: str) -> Section | None:
        """根据 ID 查找章节"""
        for section in self.sections:
            found = section.find_section_by_id(section_id)
            if found:
                return found
        return None

    def get_main_chapters(self) -> list[Section]:
        """获取正文章节（level=1）"""
        return [s for s in self.sections if s.level == 1]

    def get_special_sections(self) -> list[Section]:
        """获取特殊区段（level=0，如摘要、参考文献）"""
        return [s for s in self.sections if s.level == 0]
