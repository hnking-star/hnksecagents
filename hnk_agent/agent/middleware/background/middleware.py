"""后台子代理执行中间件。

这个中间件负责拦截主代理发起的 `task` 工具调用，
把原本会阻塞当前轮次的子代理执行改成后台任务。
"""

import asyncio
import contextvars
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from hnk_agent.agent.middleware.background.registry import BackgroundTaskRegistry
from hnk_agent.agent.middleware.background.tools import (
    create_task_output_tool,
    create_wait_tool,
)

# 这个 ContextVar 用来把后台任务 ID 传递到子代理内部的工具调用链路里。
# 后续 counter.py 会读取它，并把工具调用统计回写到注册中心。
current_background_task_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_background_task_id",
    default=None,
)

logger = structlog.get_logger(__name__)


def _truncate_description(description: str, max_sentences: int = 2) -> str:
    """把任务描述裁剪成更适合展示的短文本。"""
    sentences: list[str] = []
    remaining = description

    for _ in range(max_sentences):
        period_index = remaining.find(".")
        if period_index == -1:
            sentences.append(remaining)
            break

        sentences.append(remaining[: period_index + 1])
        remaining = remaining[period_index + 1 :].lstrip()
        if not remaining:
            break

    return " ".join(sentences)


class BackgroundSubagentMiddleware(AgentMiddleware):
    """把 `task` 工具调用转成后台执行的中间件。"""

    def __init__(self, timeout: float = 60.0, *, enabled: bool = True) -> None:
        """初始化后台子代理中间件。"""
        super().__init__()
        self.registry = BackgroundTaskRegistry()
        self.timeout = timeout
        self.enabled = enabled

        # 这里暴露给主代理两个配套工具：
        # 1. wait：等待后台任务完成
        # 2. task_output：查看后台任务结果或进度
        self.tools = [
            create_wait_tool(self),
            create_task_output_tool(self.registry),
        ]

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """同步模式下直接透传。

        当前后台执行机制依赖 asyncio 任务，因此同步模式不做拦截。
        """
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """异步模式下拦截 `task` 并把它改成后台任务。"""
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "")

        if not self.enabled or tool_name != "task":
            return await handler(request)

        tool_call_id = tool_call.get("id", "unknown")
        if not tool_call_id or tool_call_id == "unknown":
            raise RuntimeError("后台任务必须携带有效的 tool_call_id")

        args = tool_call.get("args", {})
        description = args.get("description", "unknown task")
        subagent_type = args.get("subagent_type", "general-purpose")

        task = await self.registry.register(
            task_id=tool_call_id,
            description=description,
            subagent_type=subagent_type,
            asyncio_task=None,
        )

        logger.info(
            "intercepted_task_tool_for_background_execution",
            tool_call_id=tool_call_id,
            task_number=task.task_number,
            display_id=task.display_id,
            subagent_type=subagent_type,
        )

        # 这里先把当前后台任务 ID 写入上下文，供后续子代理内部工具调用读取。
        current_background_task_id.set(tool_call_id)

        async def execute_in_background() -> dict[str, Any]:
            """在后台执行真正的 task handler。"""

            async def run_handler() -> ToolMessage | Command:
                return await handler(request)

            # 这里单独包一层 Task，避免主代理当前轮次结束时把底层子代理也一起带停。
            handler_task: asyncio.Task[ToolMessage | Command] = asyncio.create_task(run_handler())

            try:
                result = await asyncio.shield(handler_task)
                logger.debug(
                    "background_subagent_completed",
                    task_id=tool_call_id,
                    display_id=task.display_id,
                    result_type=type(result).__name__,
                )
                return {"success": True, "result": result}
            except asyncio.CancelledError:
                # 即使外层包装任务被取消，也尽量等待底层 handler 跑完，
                # 这样注册中心仍然有机会拿到结果。
                logger.info(
                    "background_subagent_cancellation_requested",
                    task_id=tool_call_id,
                    display_id=task.display_id,
                )
                try:
                    result = await handler_task
                    return {"success": True, "result": result}
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "background_subagent_failed_after_cancellation",
                        task_id=tool_call_id,
                        display_id=task.display_id,
                        error=str(exc),
                    )
                    return {
                        "success": False,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "background_subagent_failed",
                    task_id=tool_call_id,
                    display_id=task.display_id,
                    error=str(exc),
                )
                return {
                    "success": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }

        asyncio_task = asyncio.create_task(
            execute_in_background(),
            name=f"background_subagent_{task.display_id}",
        )
        task.asyncio_task = asyncio_task

        short_description = _truncate_description(description, max_sentences=2)
        pseudo_result = (
            f"后台子代理已启动：**{task.display_id}**\n"
            f"- 类型：{subagent_type}\n"
            f"- 任务：{short_description}\n"
            f"- 状态：后台运行中\n\n"
            f"你现在可以：\n"
            f"- 继续处理其他工作\n"
            f"- 使用 `task_output(task_number={task.task_number})` 查看进度或结果\n"
            f"- 使用 `wait(task_number={task.task_number})` 阻塞等待它完成\n"
            f"- 使用 `wait()` 等待全部后台任务"
        )

        return ToolMessage(
            content=pseudo_result,
            tool_call_id=tool_call_id,
            name="task",
        )

    def after_agent(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        """同步模式下不做额外处理。"""
        return None

    async def aafter_agent(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        """异步模式下也不在这里处理等待逻辑。

        后台任务完成后的通知和重入控制，后续交给 orchestrator.py。
        """
        return None

    def clear_registry(self) -> None:
        """清空后台任务注册中心。"""
        self.registry.clear()
        logger.debug("cleared_background_registry_via_middleware")

    async def cancel_all_tasks(self) -> int:
        """取消所有仍在运行的后台任务。"""
        return await self.registry.cancel_all()

    @property
    def pending_task_count(self) -> int:
        """返回当前未完成后台任务数。"""
        return self.registry.pending_count
