"""Agent 工具层统一导出。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from hnk_agent.agent.tools.bash import create_execute_bash_tool
from hnk_agent.agent.tools.code_execution import create_execute_code_tool
from hnk_agent.agent.tools.file_ops import create_filesystem_tools

__all__ = [
    "create_execute_bash_tool",
    "create_execute_code_tool",
    "create_filesystem_tools",
    "get_all_tools",
]


def get_all_tools(runtime: Any, tool_registry: Any | None = None) -> list[BaseTool]:
    """创建当前默认的全部基础工具。"""
    read_file, write_file, edit_file = create_filesystem_tools(runtime)

    return [
        create_execute_code_tool(runtime, tool_registry=tool_registry),
        create_execute_bash_tool(runtime),
        read_file,
        write_file,
        edit_file,
    ]
