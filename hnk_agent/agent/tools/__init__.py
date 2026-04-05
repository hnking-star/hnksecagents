"""Agent 工具层统一导出。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from hnk_agent.agent.tools.bash import create_execute_bash_tool
from hnk_agent.agent.tools.code_execution import create_execute_code_tool
from hnk_agent.agent.tools.file_ops import create_filesystem_tools
from hnk_agent.agent.tools.glob import create_glob_tool
from hnk_agent.agent.tools.grep import create_grep_tool
from hnk_agent.agent.tools.http_ctf import create_ctf_http_tools
from hnk_agent.agent.tools.mcp_tools import load_mcp_tools

__all__ = [
    "create_execute_bash_tool",
    "create_execute_code_tool",
    "create_filesystem_tools",
    "create_glob_tool",
    "create_grep_tool",
    "create_ctf_http_tools",
    "load_mcp_tools",
    "get_all_tools",
]


def get_all_tools(runtime: Any, tool_registry: Any | None = None) -> list[BaseTool]:
    """创建当前默认的全部基础工具。"""
    read_file, write_file, edit_file = create_filesystem_tools(runtime)
    glob_tool = create_glob_tool(runtime)
    grep_tool = create_grep_tool(runtime)

    normalize_url_tool, http_request_tool, http_probe_tool, extract_flags_tool = create_ctf_http_tools()

    return [
        create_execute_code_tool(runtime, tool_registry=tool_registry),
        create_execute_bash_tool(runtime),
        glob_tool,
        grep_tool,
        read_file,
        write_file,
        edit_file,
        normalize_url_tool,
        http_request_tool,
        http_probe_tool,
        extract_flags_tool,
    ]
