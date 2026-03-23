"""后台子代理相关组件导出。"""

from hnk_agent.agent.middleware.background.counter import ToolCallCounterMiddleware
from hnk_agent.agent.middleware.background.middleware import (
    BackgroundSubagentMiddleware,
    current_background_task_id,
)
from hnk_agent.agent.middleware.background.orchestrator import BackgroundSubagentOrchestrator
from hnk_agent.agent.middleware.background.registry import BackgroundTask, BackgroundTaskRegistry
from hnk_agent.agent.middleware.background.tools import (
    create_task_output_tool,
    create_wait_tool,
    extract_result_content,
)

__all__ = [
    "BackgroundTask",
    "BackgroundTaskRegistry",
    "BackgroundSubagentMiddleware",
    "BackgroundSubagentOrchestrator",
    "ToolCallCounterMiddleware",
    "create_wait_tool",
    "create_task_output_tool",
    "extract_result_content",
    "current_background_task_id",
]
