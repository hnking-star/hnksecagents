"""后台子代理工具调用计数中间件。

这个中间件用于注入到后台子代理内部，
把子代理的工具调用次数和当前工具名回写到后台任务注册中心。
"""

from collections.abc import Awaitable, Callable

import structlog
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from hnk_agent.agent.middleware.background.middleware import current_background_task_id
from hnk_agent.agent.middleware.background.registry import BackgroundTaskRegistry

logger = structlog.get_logger(__name__)


class ToolCallCounterMiddleware(AgentMiddleware):
    """用于统计后台任务工具调用次数的中间件。"""

    def __init__(self, registry: BackgroundTaskRegistry) -> None:
        """初始化计数中间件。"""
        super().__init__()
        self.tools = []
        self.registry = registry

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """同步模式下直接透传，不做额外处理。"""
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """异步模式下记录工具调用统计后继续执行。"""
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown")

        # 这里通过 ContextVar 获取当前后台任务 ID。
        # 这个值会在后台任务创建时由 middleware.py 写入。
        task_id = current_background_task_id.get()

        if task_id and self.registry:
            await self.registry.update_metrics(task_id, tool_name)
            logger.debug(
                "counted_background_tool_call",
                task_id=task_id,
                tool_name=tool_name,
            )

        return await handler(request)
