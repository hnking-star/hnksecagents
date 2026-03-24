"""Agent 中间件统一导出。"""

from __future__ import annotations

from hnk_agent.agent.middleware.background import (
    BackgroundSubagentMiddleware,
    BackgroundSubagentOrchestrator,
    BackgroundTask,
    BackgroundTaskRegistry,
    ToolCallCounterMiddleware,
    create_task_output_tool,
    create_wait_tool,
    current_background_task_id,
    extract_result_content,
)

__all__ = [
    "BackgroundSubagentMiddleware",
    "BackgroundSubagentOrchestrator",
    "BackgroundTask",
    "BackgroundTaskRegistry",
    "ToolCallCounterMiddleware",
    "create_wait_tool",
    "create_task_output_tool",
    "extract_result_content",
    "current_background_task_id",
    "create_deepagent_middleware",
]

from hnk_agent.agent.middleware.deepagent_middleware import create_deepagent_middleware


def __getattr__(name: str):
    """按需导入重依赖模块。"""
    if name == "create_deepagent_middleware":
        from hnk_agent.agent.middleware.deepagent_middleware import create_deepagent_middleware

        return create_deepagent_middleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
