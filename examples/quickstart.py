"""本地 PTC 最小验证示例。"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hnk_agent.config import AgentConfig
from hnk_agent.agent.tools import create_execute_code_tool


async def main() -> None:
    """运行最小本地 PTC 示例。"""
    workspace_root = Path(
        tempfile.mkdtemp(prefix="hnksecagents_demo_", dir="/tmp")
    ).resolve()

    # 这里用 object() 作为最小 llm 占位，仅用于演示配置驱动流程。
    # 当前示例不会真正创建完整 HNKAgent，因此不会使用到这个对象。
    config = AgentConfig.create(
        llm=object(),
        workspace_root=str(workspace_root),
        enable_builtin_tools=True,
        subagents_enabled=["general-purpose"],
    )

    registry = config.create_tool_registry()
    runtime = config.create_runtime()
    execute_code = create_execute_code_tool(runtime, tool_registry=registry)

    code = """
from tools.local_tools import add_numbers, echo_text

result = add_numbers(7, 35)
message = echo_text("local ptc is working")

print({"result": result, "message": message})
"""

    output = await execute_code.ainvoke({"code": code})

    print("Workspace:", workspace_root)
    print("Builtin Tools:")
    print(registry.as_summary())
    print("Execute Code Output:")
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
