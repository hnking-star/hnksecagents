"""通用子代理定义。

这一层先不依赖 Daytona、MCP 或具体运行时实现，
只负责定义“一个通用子代理应该拿到哪些工具、长什么样”。
"""

from typing import Any

from hnk_agent.agent.prompts import build_general_subagent_prompt

def _build_general_system_prompt(
    max_iterations: int,
    tool_summary: str = "",
    skills_prompt: str = "",
) -> str:
    """构建通用子代理的默认系统提示词。"""
    return build_general_subagent_prompt(
        max_iterations=max_iterations,
        tool_summary=tool_summary,
        skills_prompt=skills_prompt,
    )


def _tool_identity(tool: Any) -> str:
    """提取工具的稳定标识，用于去重。"""
    if hasattr(tool, "name"):
        return str(tool.name)
    return repr(tool)


def _merge_tools(*tool_groups: list[Any] | None) -> list[Any]:
    """合并多组工具，并按名称去重。"""
    merged: list[Any] = []
    seen: set[str] = set()

    for group in tool_groups:
        if not group:
            continue
        for tool in group:
            identity = _tool_identity(tool)
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(tool)

    return merged


def get_general_subagent_config(
    max_iterations: int = 10,
    execute_code_tool: Any | None = None,
    bash_tool: Any | None = None,
    filesystem_tools: list[Any] | None = None,
    additional_tools: list[Any] | None = None,
    vision_tools: list[Any] | None = None,
    middleware: list[Any] | None = None,
    tool_summary: str = "",
    skills_prompt: str = "",
    system_prompt: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """生成通用子代理配置。"""
    base_tools: list[Any] = []

    if execute_code_tool is not None:
        base_tools.append(execute_code_tool)

    if bash_tool is not None:
        base_tools.append(bash_tool)

    tools = _merge_tools(
        base_tools,
        filesystem_tools,
        vision_tools,
        additional_tools,
    )

    final_system_prompt = system_prompt or _build_general_system_prompt(
        max_iterations=max_iterations,
        tool_summary=tool_summary,
        skills_prompt=skills_prompt,
    )

    final_description = description or (
        "把复杂的多步骤任务委派给通用子代理。"
        "它适合处理文件操作、代码执行、信息整理、结果汇总等完整子任务。"
    )

    spec: dict[str, Any] = {
        "name": "general-purpose",
        "description": final_description,
        "system_prompt": final_system_prompt,
        "tools": tools,
    }

    if middleware:
        spec["middleware"] = list(middleware)

    return spec


def create_general_subagent(
    max_iterations: int = 10,
    execute_code_tool: Any | None = None,
    bash_tool: Any | None = None,
    filesystem_tools: list[Any] | None = None,
    additional_tools: list[Any] | None = None,
    vision_tools: list[Any] | None = None,
    middleware: list[Any] | None = None,
    tool_summary: str = "",
    skills_prompt: str = "",
    system_prompt: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """创建通用子代理。"""
    return get_general_subagent_config(
        max_iterations=max_iterations,
        execute_code_tool=execute_code_tool,
        bash_tool=bash_tool,
        filesystem_tools=filesystem_tools,
        additional_tools=additional_tools,
        vision_tools=vision_tools,
        middleware=middleware,
        tool_summary=tool_summary,
        skills_prompt=skills_prompt,
        system_prompt=system_prompt,
        description=description,
    )
