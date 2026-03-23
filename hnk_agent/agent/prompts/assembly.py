"""统一提示词装配层。"""

from __future__ import annotations

from hnk_agent.agent.prompts.general_subagent import build_general_subagent_prompt
from hnk_agent.agent.prompts.main_agent import build_main_agent_prompt


def build_main_agent_system_prompt(
    *,
    tool_summary: str,
    subagent_summary: str,
    system_prompt_suffix: str | None = None,
) -> str:
    """统一构建主代理 system prompt。"""
    return build_main_agent_prompt(
        tool_summary=tool_summary,
        subagent_summary=subagent_summary,
        system_prompt_suffix=system_prompt_suffix,
    )


def build_general_subagent_system_prompt(
    *,
    max_iterations: int,
    tool_summary: str = "",
) -> str:
    """统一构建通用子代理 system prompt。"""
    return build_general_subagent_prompt(
        max_iterations=max_iterations,
        tool_summary=tool_summary,
    )
