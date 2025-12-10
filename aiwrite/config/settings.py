"""
配置管理模块
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ..llm import LLMPurpose, create_provider, LLMProvider, create_vision_provider, VisionProvider
from ..models import Paper, Section, PaperStatus, Figure, Table, FigureType


class LLMConfig(BaseModel):
    """LLM 配置"""
    api_key: str
    base_url: str
    model: str
    provider_type: str = "openai_compatible"


class AppConfig(BaseModel):
    """应用配置"""
    thinking_llm: LLMConfig = Field(..., description="思考模型配置")
    writing_llm: LLMConfig = Field(..., description="写作模型配置")
    writing_alt_llm: LLMConfig | None = Field(default=None, description="备选写作模型")
    vision_llm: LLMConfig | None = Field(default=None, description="视觉模型配置")
    max_tokens: int = Field(default=8192, description="最大 Token 数")
    temperature: float = Field(default=0.3, description="温度参数")
    
    # 数据库配置（可选）
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=3306)
    db_user: str = Field(default="root")
    db_password: str = Field(default="")
    db_name: str = Field(default="aiwrite")


def load_config(env_file: str | Path | None = None) -> AppConfig:
    """
    从环境变量加载配置
    
    Args:
        env_file: .env 文件路径，默认为当前目录的 .env
        
    Returns:
        AppConfig 实例
    """
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    thinking_llm = LLMConfig(
        api_key=os.getenv("THINKING_API_KEY", ""),
        base_url=os.getenv("THINKING_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        model=os.getenv("THINKING_MODEL", "doubao-seed-1-6-thinking-250715"),
        provider_type="doubao",
    )

    writing_llm = LLMConfig(
        api_key=os.getenv("WRITING_API_KEY", ""),
        base_url=os.getenv("WRITING_BASE_URL", "https://api.deepseek.com/v1"),
        model=os.getenv("WRITING_MODEL", "deepseek-v3-1-terminus"),
        provider_type="deepseek",
    )

    writing_alt_llm = None
    if os.getenv("WRITING_ALT_API_KEY"):
        writing_alt_llm = LLMConfig(
            api_key=os.getenv("WRITING_ALT_API_KEY", ""),
            base_url=os.getenv("WRITING_ALT_BASE_URL", "https://api.moonshot.cn/v1"),
            model=os.getenv("WRITING_ALT_MODEL", "kimi-k2-thinking-251104"),
            provider_type="kimi",
        )

    # 视觉模型配置（默认使用思考模型的 API Key，因为豆包视觉模型也在火山引擎）
    vision_llm = LLMConfig(
        api_key=os.getenv("VISION_API_KEY", os.getenv("THINKING_API_KEY", "")),
        base_url=os.getenv("VISION_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        model=os.getenv("VISION_MODEL", "doubao-1-5-vision-pro-32k-250115"),
        provider_type="doubao_vision",
    )

    return AppConfig(
        thinking_llm=thinking_llm,
        writing_llm=writing_llm,
        writing_alt_llm=writing_alt_llm,
        vision_llm=vision_llm,
        max_tokens=int(os.getenv("AIWRITE_LLM_MAX_TOKENS", "8192")),
        temperature=float(os.getenv("AIWRITE_LLM_TEMPERATURE", "0.3")),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_user=os.getenv("DB_USER", "root"),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_name=os.getenv("DB_NAME", "aiwrite"),
    )


def create_thinking_provider(config: AppConfig) -> LLMProvider:
    """创建思考模型 Provider"""
    return create_provider(
        provider_type=config.thinking_llm.provider_type,
        api_key=config.thinking_llm.api_key,
        base_url=config.thinking_llm.base_url,
        model=config.thinking_llm.model,
        purpose=LLMPurpose.THINKING,
    )


def create_writing_provider(config: AppConfig, use_alt: bool = False) -> LLMProvider:
    """创建写作模型 Provider"""
    llm_config = config.writing_alt_llm if use_alt and config.writing_alt_llm else config.writing_llm
    return create_provider(
        provider_type=llm_config.provider_type,
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        model=llm_config.model,
        purpose=LLMPurpose.WRITING,
    )


def create_vision_llm_provider(config: AppConfig) -> VisionProvider:
    """创建视觉模型 Provider"""
    if config.vision_llm:
        return create_vision_provider(
            api_key=config.vision_llm.api_key,
            base_url=config.vision_llm.base_url,
            model=config.vision_llm.model,
        )
    # 如果没有配置视觉模型，使用思考模型的配置
    return create_vision_provider(
        api_key=config.thinking_llm.api_key,
        base_url=config.thinking_llm.base_url,
        model="doubao-1-5-vision-pro-32k-250115",
    )


def load_outline(file_path: str | Path) -> Paper:
    """
    从 YAML 文件加载论文大纲
    
    Args:
        file_path: YAML 文件路径
        
    Returns:
        Paper 实例
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    paper_data = data.get("paper", {})
    sections_data = data.get("sections", [])

    def parse_figure(f: dict[str, Any]) -> Figure:
        # 解析 fig_type
        fig_type_str = f.get("fig_type", "matched")
        try:
            fig_type = FigureType(fig_type_str)
        except ValueError:
            # 兼容旧格式
            if f.get("path"):
                fig_type = FigureType.MATCHED
            elif f.get("mermaid_code"):
                fig_type = FigureType.GENERATE
            else:
                fig_type = FigureType.SUGGESTED
        
        return Figure(
            id=f.get("id", ""),
            fig_type=fig_type,
            path=f.get("path"),  # 现在是可选的
            caption=f.get("caption", ""),
            description=f.get("description"),
            position=f.get("position", "here"),
            suggestion=f.get("suggestion"),
            can_generate=f.get("can_generate", False),
            mermaid_code=f.get("mermaid_code"),
        )

    def parse_table(t: dict[str, Any]) -> Table:
        return Table(
            id=t.get("id", ""),
            caption=t.get("caption", ""),
            path=t.get("path"),
            content=t.get("content"),
            description=t.get("description"),
        )

    def parse_section(s: dict[str, Any]) -> Section:
        children = [parse_section(c) for c in s.get("children", [])]
        figures = [parse_figure(f) for f in s.get("figures", [])]
        tables = [parse_table(t) for t in s.get("tables", [])]
        return Section(
            id=s["id"],
            title=s["title"],
            level=s.get("level", 1),
            target_words=s.get("target_words"),
            style=s.get("style"),
            notes=s.get("notes"),
            children=children,
            figures=figures,
            tables=tables,
            draft_latex=s.get("draft_latex"),
            final_latex=s.get("final_latex"),
        )

    sections = [parse_section(s) for s in sections_data]

    status_str = paper_data.get("status", "pending_outline")
    try:
        status = PaperStatus(status_str)
    except ValueError:
        status = PaperStatus.PENDING_OUTLINE

    return Paper(
        title=paper_data.get("title", ""),
        authors=paper_data.get("authors", []),
        keywords=paper_data.get("keywords", []),
        keywords_en=paper_data.get("keywords_en", []),
        language=paper_data.get("language", "zh"),
        style=paper_data.get("style", "academic"),
        target_words=paper_data.get("target_words", 8000),
        status=status,
        sections=sections,
    )


def save_outline(paper: Paper, file_path: str | Path) -> None:
    """
    将论文大纲保存到 YAML 文件
    
    Args:
        paper: Paper 实例
        file_path: 输出文件路径
    """
    def figure_to_dict(f: Figure) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": f.id,
            "caption": f.caption,
        }
        # 新增字段
        if hasattr(f, 'fig_type') and f.fig_type:
            d["fig_type"] = f.fig_type.value if hasattr(f.fig_type, 'value') else str(f.fig_type)
        if f.path:
            d["path"] = f.path
        if f.description:
            d["description"] = f.description
        if f.position != "here":
            d["position"] = f.position
        if hasattr(f, 'suggestion') and f.suggestion:
            d["suggestion"] = f.suggestion
        if hasattr(f, 'can_generate') and f.can_generate:
            d["can_generate"] = f.can_generate
        if hasattr(f, 'mermaid_code') and f.mermaid_code:
            d["mermaid_code"] = f.mermaid_code
        return d

    def table_to_dict(t: Table) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": t.id,
            "caption": t.caption,
        }
        if t.path:
            d["path"] = t.path
        if t.content:
            d["content"] = t.content
        if t.description:
            d["description"] = t.description
        return d

    def section_to_dict(s: Section) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": s.id,
            "title": s.title,
            "level": s.level,
        }
        if s.target_words is not None:
            d["target_words"] = s.target_words
        if s.style:
            d["style"] = s.style
        if s.notes:
            d["notes"] = s.notes
        if s.figures:
            d["figures"] = [figure_to_dict(f) for f in s.figures]
        if s.tables:
            d["tables"] = [table_to_dict(t) for t in s.tables]
        if s.children:
            d["children"] = [section_to_dict(c) for c in s.children]
        if s.draft_latex:
            d["draft_latex"] = s.draft_latex
        if s.final_latex:
            d["final_latex"] = s.final_latex
        return d

    data = {
        "paper": {
            "title": paper.title,
            "authors": paper.authors,
            "keywords": paper.keywords,
            "keywords_en": paper.keywords_en,
            "language": paper.language,
            "style": paper.style,
            "target_words": paper.target_words,
            "status": paper.status.value,
        },
        "sections": [section_to_dict(s) for s in paper.sections],
    }

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
