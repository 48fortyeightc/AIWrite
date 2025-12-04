"""
Pipeline 执行器
"""

from __future__ import annotations

from typing import Callable, Awaitable

from rich.console import Console
from rich.panel import Panel

from ..models import Paper, PipelineStep, PipelineContext, LLMOptions


console = Console()


class PipelineExecutor:
    """
    流水线执行器
    
    管理和执行多个 PipelineStep，支持：
    - 顺序执行步骤
    - 用户确认点
    - 错误处理
    """

    def __init__(self, steps: list[PipelineStep] | None = None):
        self.steps: list[PipelineStep] = steps or []
        self._confirmation_handlers: dict[str, Callable[[Paper], Awaitable[bool]]] = {}

    def add_step(self, step: PipelineStep) -> "PipelineExecutor":
        """添加步骤"""
        self.steps.append(step)
        return self

    def add_confirmation_after(
        self,
        step_name: str,
        handler: Callable[[Paper], Awaitable[bool]],
    ) -> "PipelineExecutor":
        """
        在指定步骤后添加确认点
        
        Args:
            step_name: 步骤名称
            handler: 确认处理函数，返回 True 继续，False 中止
        """
        self._confirmation_handlers[step_name] = handler
        return self

    async def run(
        self,
        paper: Paper,
        llm_options: LLMOptions | None = None,
    ) -> Paper:
        """
        执行整个流水线
        
        Args:
            paper: 论文对象
            llm_options: LLM 选项
            
        Returns:
            处理后的 Paper 对象
        """
        context = PipelineContext(
            paper=paper,
            llm_options=llm_options or LLMOptions(),
        )

        console.print(Panel(
            f"[bold]开始执行写作流水线[/bold]\n"
            f"论文标题: {paper.title}\n"
            f"步骤数量: {len(self.steps)}",
            title="AIWrite Pipeline",
            border_style="blue",
        ))

        for i, step in enumerate(self.steps, 1):
            console.print(f"\n[bold cyan]═══ 步骤 {i}/{len(self.steps)}: {step.description} ═══[/bold cyan]")

            try:
                context = await step.execute(context)
            except Exception as e:
                console.print(f"[bold red]✗ 步骤执行失败: {e}[/bold red]")
                raise

            # 检查是否需要用户确认
            if step.name in self._confirmation_handlers:
                handler = self._confirmation_handlers[step.name]
                should_continue = await handler(context.paper)
                if not should_continue:
                    console.print("[yellow]用户取消，流水线中止[/yellow]")
                    break

        console.print(Panel(
            f"[bold green]流水线执行完成[/bold green]\n"
            f"最终状态: {context.paper.status.value}",
            title="完成",
            border_style="green",
        ))

        return context.paper

    async def run_step(
        self,
        step_name: str,
        paper: Paper,
        llm_options: LLMOptions | None = None,
    ) -> Paper:
        """
        只执行指定的单个步骤
        
        Args:
            step_name: 步骤名称
            paper: 论文对象
            llm_options: LLM 选项
            
        Returns:
            处理后的 Paper 对象
        """
        context = PipelineContext(
            paper=paper,
            llm_options=llm_options or LLMOptions(),
        )

        for step in self.steps:
            if step.name == step_name:
                console.print(f"[bold cyan]执行步骤: {step.description}[/bold cyan]")
                context = await step.execute(context)
                return context.paper

        raise ValueError(f"未找到步骤: {step_name}")
