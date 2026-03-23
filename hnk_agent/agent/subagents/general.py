"""通用子代理定义。

这一层先不依赖 Daytona、MCP 或具体运行时实现，
只负责定义“一个通用子代理应该拿到哪些工具、长什么样”。
"""

from typing import Any


def _build_general_system_prompt(
    max_iterations: int,
    tool_summary: str = "",
) -> str:
    """构建通用子代理的默认系统提示词。"""
    lines = [
        "你是一个通用子代理，负责接收主代理分派的具体任务。",
        "你的目标是独立完成被分配的子任务，并把结果清晰返回给主代理。",
        "",
        "工作要求：",
        f"- 最多进行 {max_iterations} 轮关键操作",
        "- 优先直接完成任务，不要写无意义的铺垫",
        "- 如果有工具可用，优先利用工具完成任务",
        "- 如果任务需要读取、修改、搜索文件，可以使用文件相关工具",
        "- 如果任务需要执行代码，请通过 execute_code 类工具完成",
        "- 输出结果时尽量给出结论、关键依据和必要的下一步建议",
    ]

    if tool_summary:
        lines.extend(
            [
                "",
                "可用工具摘要：",
                tool_summary,
            ]
        )

    return "\n".join(lines)


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
        system_prompt=system_prompt,
        description=description,
    )
