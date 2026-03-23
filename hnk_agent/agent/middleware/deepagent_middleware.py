"""deepagent 中间件栈工厂。"""

from typing import Any

SUBAGENT_MIDDLEWARE_DESCRIPTION = """启动一个子代理来处理复杂、多步骤任务。

参数：
    description: 传给子代理的完整任务描述
    subagent_type: 要使用的子代理类型

使用建议：
- 适合：复杂任务、上下文较重的独立子任务、并行拆分工作
- 不适合：1 到 2 次工具调用就能完成的简单操作
- 可以并行启动多个子代理
- 子代理返回的是整理后的结果，而不是完整中间过程
"""


def create_deepagent_middleware(
    model: Any,
    tools: list[Any],
    subagents: list[Any],
    backend: Any,
    custom_middleware: list[Any] | None = None,
    max_tokens_before_summary: int = 170000,
    messages_to_keep: int = 6,
) -> list[Any]:
    """创建当前 agent 使用的 deepagent 风格中间件栈。"""
    try:
        from deepagents.middleware import FilesystemMiddleware, SubAgentMiddleware
        from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
        from langchain.agents.middleware import TodoListMiddleware
        from langchain.agents.middleware.summarization import SummarizationMiddleware
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Creating the full HNKAgent middleware stack requires deepagents and langchain dependencies"
        ) from exc

    middleware: list[Any] = [
        TodoListMiddleware(),
        FilesystemMiddleware(backend=backend),
        SubAgentMiddleware(
            default_model=model,
            default_tools=tools,
            subagents=subagents if subagents else [],
            task_description=SUBAGENT_MIDDLEWARE_DESCRIPTION,
            system_prompt=None,
            default_middleware=[
                TodoListMiddleware(),
                FilesystemMiddleware(backend=backend),
                SummarizationMiddleware(
                    model=model,
                    trigger=("tokens", max_tokens_before_summary),
                    keep=("messages", messages_to_keep),
                ),
                PatchToolCallsMiddleware(),
            ],
            general_purpose_agent=True,
        ),
        SummarizationMiddleware(
            model=model,
            trigger=("tokens", max_tokens_before_summary),
            keep=("messages", messages_to_keep),
        ),
        PatchToolCallsMiddleware(),
    ]

    if custom_middleware:
        middleware.extend(custom_middleware)

    return middleware
