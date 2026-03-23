"""统一提示词装配层。

这一层负责把“基础 prompt 模板”和“技能目录元信息”
合成为最终 system prompt，采用更接近 ptc-agent 的渐进披露形式。
"""

from __future__ import annotations

from hnk_agent.agent.prompts.general_subagent import build_general_subagent_prompt
from hnk_agent.agent.prompts.main_agent import build_main_agent_prompt
from hnk_agent.skills.registry import SkillRegistry

def _merge_prompt_blocks(*blocks: str) -> str:
    """合并多个 prompt 片段，并自动跳过空块。"""
    return "\n\n".join(block.strip() for block in blocks if block and block.strip())


def build_skills_catalog_prompt(
    *,
    registry: SkillRegistry | None,
) -> str:
    """构造技能目录提示词。"""
    if registry is None or registry.is_empty():
        return ""
    return registry.build_catalog_prompt()


def build_main_agent_system_prompt(
    *,
    tool_summary: str,
    subagent_summary: str,
    registry: SkillRegistry | None = None,
    base_skills_prompt: str = "",
    system_prompt_suffix: str | None = None,
) -> str:
    """统一构建主代理 system prompt。"""
    skills_catalog_prompt = build_skills_catalog_prompt(
        registry=registry,
    )
    merged_skills_prompt = _merge_prompt_blocks(base_skills_prompt, skills_catalog_prompt)

    return build_main_agent_prompt(
        tool_summary=tool_summary,
        subagent_summary=subagent_summary,
        skills_enabled=registry is not None and not registry.is_empty(),
        skills_prompt=merged_skills_prompt,
        system_prompt_suffix=system_prompt_suffix,
    )


def build_general_subagent_system_prompt(
    *,
    max_iterations: int,
    tool_summary: str = "",
    registry: SkillRegistry | None = None,
    base_skills_prompt: str = "",
) -> str:
    """统一构建通用子代理 system prompt。"""
    skills_catalog_prompt = build_skills_catalog_prompt(
        registry=registry,
    )
    merged_skills_prompt = _merge_prompt_blocks(base_skills_prompt, skills_catalog_prompt)

    return build_general_subagent_prompt(
        max_iterations=max_iterations,
        tool_summary=tool_summary,
        skills_enabled=registry is not None and not registry.is_empty(),
        skills_prompt=merged_skills_prompt,
    )
