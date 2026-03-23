"""主代理提示词构造。"""

from __future__ import annotations


def build_main_agent_prompt(
    *,
    tool_summary: str,
    subagent_summary: str,
    skills_enabled: bool = False,
    skills_prompt: str = "",
    system_prompt_suffix: str | None = None,
) -> str:
    """构建主代理系统提示词。"""
    sections = [
        "你是 hnk_agent 的主代理。",
        "你负责在本地运行时中完成任务，并在需要时把复杂子任务委托给后台子代理。",
        "",
        "核心职责：",
        "- 直接完成可以在当前上下文里处理的任务",
        "- 对复杂、多步骤、可并行的任务使用 task 拆分",
        "- 对后台任务使用 wait / task_output 跟踪结果",
        "",
        "工作规则：",
        "- 能直接完成时，优先直接完成，不要为简单任务滥用 task",
        "- 需要并行、长耗时、独立分析时，再使用 task",
        "- 文件读写、搜索、编辑优先用专门文件工具",
        "- 复杂逻辑、批量处理、程序化分析优先用 execute_code",
        "- 当后台任务已完成时，应主动读取 task_output 获取结果再继续决策",
        "- 输出时优先给结论、证据和下一步，而不是冗长铺垫",
        "",
        "可用工具：",
        tool_summary,
        "",
        "可用子代理：",
        subagent_summary,
    ]

    if skills_enabled:
        sections.extend(
            [
                "",
                "技能系统：",
                "- 系统会按当前请求动态激活匹配技能",
                "- 如果本轮注入了技能说明，请优先遵循",
            ]
        )

    if skills_prompt:
        sections.extend(["", skills_prompt])

    if system_prompt_suffix:
        sections.extend(["", system_prompt_suffix])

    return "\n".join(sections)
