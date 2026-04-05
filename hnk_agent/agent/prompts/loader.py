"""Markdown 提示词模板加载器。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class PromptLoader:
    """统一管理主代理与子代理 Markdown 提示词模板。"""

    def __init__(
        self,
        templates_dir: Path | None = None,
        session_start_time: datetime | None = None,
    ) -> None:
        """初始化模板环境。"""
        self.templates_dir = templates_dir or Path(__file__).parent / "templates"
        self._session_start_time = session_start_time or datetime.now(tz=UTC)

    @property
    def session_date(self) -> str:
        """返回会话日期。"""
        return self._session_start_time.strftime("%Y-%m-%d")

    @property
    def session_datetime(self) -> str:
        """返回会话时间。"""
        return self._session_start_time.strftime("%Y-%m-%d %H:%M:%S")

    def _read_template(self, template_name: str) -> str:
        """读取模板文件。"""
        return (self.templates_dir / template_name).read_text(encoding="utf-8")

    def render(self, template_name: str, **kwargs: Any) -> str:
        """渲染模板。"""
        template = self._read_template(template_name)
        context = {
            "date": self.session_date,
            "datetime": self.session_datetime,
            **kwargs,
        }
        rendered = template
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{ {key} }}}}", str(value))
        return "\n".join(line.rstrip() for line in rendered.strip().splitlines())

    def get_system_prompt(
        self,
        *,
        tool_summary: str,
        subagent_summary: str,
        runtime_context: str | None = None,
    ) -> str:
        """构建主代理系统提示词。"""
        project_policy = self._read_template("components/project_policy.md.j2")
        runtime_context_section = ""
        if runtime_context:
            runtime_context_section = f"\n{runtime_context}\n"
        return self.render(
            "system.md.j2",
            tool_summary=tool_summary,
            subagent_summary=subagent_summary,
            project_policy=project_policy,
            runtime_context_section=runtime_context_section,
        )

    def get_subagent_prompt(
        self,
        subagent_type: str,
        *,
        max_iterations: int,
        tool_summary: str = "",
        runtime_context: str | None = None,
    ) -> str:
        """构建子代理系统提示词。"""
        project_policy = self._read_template("components/project_policy.md.j2")
        runtime_context_section = ""
        if runtime_context:
            runtime_context_section = f"\n{runtime_context}\n"
        tool_summary_section = ""
        if tool_summary:
            tool_summary_section = f"\n可用工具摘要：\n{tool_summary}\n"
        return self.render(
            f"subagents/{subagent_type}.md.j2",
            max_iterations=max_iterations,
            tool_summary_section=tool_summary_section,
            project_policy=project_policy,
            runtime_context_section=runtime_context_section,
        )


_loader: PromptLoader | None = None


def get_loader(session_start_time: datetime | None = None) -> PromptLoader:
    """返回全局单例 PromptLoader。"""
    global _loader
    if _loader is None:
        _loader = PromptLoader(session_start_time=session_start_time)
    return _loader


def init_loader(session_start_time: datetime | None = None) -> PromptLoader:
    """重建全局 PromptLoader。"""
    global _loader
    _loader = PromptLoader(session_start_time=session_start_time)
    return _loader


def reset_loader() -> None:
    """重置全局 PromptLoader。"""
    global _loader
    _loader = None
