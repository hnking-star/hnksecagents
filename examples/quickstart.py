"""本地 PTC 最小验证示例。"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hnk_agent.agent.tools import create_execute_code_tool
from hnk_agent.runtime import LocalRuntime
from hnk_agent.tooling import ToolRegistry
from hnk_agent.tooling.builtins import register_builtin_tools


async def main() -> None:
    """运行最小本地 PTC 示例。"""
    workspace_root = Path(
        tempfile.mkdtemp(prefix="hnksecagents_demo_", dir="/tmp")
    ).resolve()

    registry = ToolRegistry()
    register_builtin_tools(registry)

    runtime = LocalRuntime(root_dir=workspace_root)
    execute_code = create_execute_code_tool(runtime, tool_registry=registry)

    code = """
from tools.local_tools import add_numbers, echo_text

result = add_numbers(7, 35)
message = echo_text("local ptc is working")

print({"result": result, "message": message})
"""

    output = await execute_code.ainvoke({"code": code})

    print("Workspace:", workspace_root)
    print("Execute Code Output:")
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
