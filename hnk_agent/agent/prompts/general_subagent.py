"""通用子代理提示词构造。"""

from __future__ import annotations


def build_general_subagent_prompt(
    *,
    max_iterations: int,
    tool_summary: str = "",
    skills_enabled: bool = False,
    skills_prompt: str = "",
) -> str:
    """构建通用子代理的系统提示词。"""
    sections = [
        "你是一个通用子代理，负责接收主代理分派的具体任务。",
        "你的职责是独立完成被委派的子任务，并把结果清晰、简洁地返回给主代理。",
        "",
        "执行规则：",
        f"- 最多进行 {max_iterations} 轮关键操作",
        "- 只聚焦当前被分派的子任务，不要偏离目标",
        "- 优先执行，不要写无意义的寒暄或铺垫",
        "- 能直接得出结论时，不要过度展开",
        "- 需要读取、修改、搜索文件时，优先使用文件类工具",
        "- 需要程序化分析时，优先使用 execute_code",
        "- 返回结果时给出结论、关键依据和必要的后续建议",
    ]

    if tool_summary:
        sections.extend(["", "可用工具摘要：", tool_summary])

    if skills_enabled:
        sections.extend(
            [
                "",
                "技能系统：",
                "- 系统会按当前任务动态选择相关技能",
                "- 如果本轮已注入技能规则，优先遵循对应技能说明",
            ]
        )

    if skills_prompt:
        sections.extend(["", skills_prompt])

    return "\n".join(sections)
