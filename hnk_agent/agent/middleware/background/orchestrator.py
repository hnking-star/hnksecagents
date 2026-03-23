"""后台子代理调度器。

这个模块负责包装最终 agent，并在后台任务完成后决定是否通知主代理重入。
"""

from collections.abc import AsyncIterator
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from hnk_agent.agent.middleware.background.middleware import BackgroundSubagentMiddleware

logger = structlog.get_logger(__name__)


class BackgroundSubagentOrchestrator:
    """负责后台任务通知和重入控制的调度器。"""

    def __init__(
        self,
        agent: Any,
        middleware: BackgroundSubagentMiddleware,
        max_iterations: int = 3,
        auto_wait: bool = False,
    ) -> None:
        """初始化调度器。"""
        self.agent = agent
        self.middleware = middleware
        self.max_iterations = max_iterations
        self.auto_wait = auto_wait

    async def ainvoke(
        self,
        input_state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """以自动重入的方式执行 agent。"""
        config = config or {}
        iteration = 0
        current_state = input_state
        result: dict[str, Any] = {}

        while iteration < self.max_iterations:
            iteration += 1

            logger.info(
                "background_orchestrator_invoking_agent",
                iteration=iteration,
                has_messages="messages" in current_state,
            )

            result = await self.agent.ainvoke(current_state, config)

            notification = await self.check_and_get_notification()
            if notification:
                logger.info(
                    "background_tasks_completed_notifying_agent",
                    iteration=iteration,
                )
                messages = result.get("messages", [])
                notification_message = HumanMessage(content=notification)
                current_state = {**result, "messages": [*messages, notification_message]}
                continue

            if self.middleware.registry.has_pending_tasks():
                logger.info(
                    "background_orchestrator_waiting_for_pending_tasks",
                    pending_count=self.middleware.registry.pending_count,
                    timeout=self.middleware.timeout,
                )
                await self.middleware.registry.wait_for_all(timeout=self.middleware.timeout)

                notification = await self.check_and_get_notification()
                if notification:
                    logger.info(
                        "background_tasks_completed_after_wait_notifying_agent",
                        iteration=iteration,
                    )
                    messages = result.get("messages", [])
                    notification_message = HumanMessage(content=notification)
                    current_state = {**result, "messages": [*messages, notification_message]}
                    continue

            logger.debug(
                "background_orchestrator_returning_without_reinvoke",
                iteration=iteration,
            )
            return result

        logger.warning(
            "background_orchestrator_reached_max_iterations",
            max_iterations=self.max_iterations,
        )
        return result

    def invoke(
        self,
        input_state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """同步执行模式下直接透传到底层 agent。"""
        logger.warning("background_orchestrator_sync_invoke_fallback")
        return self.agent.invoke(input_state, config or {})

    async def astream(
        self,
        input_state: dict[str, Any],
        config: dict[str, Any] | None = None,
        *,
        stream_mode: str | list[str] | None = None,
        subgraphs: bool = False,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """以流式方式执行 agent，并在轮次之间处理后台任务通知。"""
        config = config or {}
        iteration = 0
        current_state = input_state

        stream_kwargs: dict[str, Any] = {**kwargs}
        if stream_mode is not None:
            stream_kwargs["stream_mode"] = stream_mode
        if subgraphs:
            stream_kwargs["subgraphs"] = subgraphs

        while iteration < self.max_iterations:
            iteration += 1

            logger.info(
                "background_orchestrator_streaming_agent",
                iteration=iteration,
                stream_mode=stream_mode,
                subgraphs=subgraphs,
            )

            async for event in self.agent.astream(current_state, config, **stream_kwargs):
                yield event

            notification = await self.check_and_get_notification()
            if notification:
                logger.info(
                    "background_tasks_completed_after_stream_notifying_agent",
                    iteration=iteration,
                )
                state_snapshot = await self.agent.aget_state(config)
                state_values = state_snapshot.values
                messages = state_values.get("messages", [])
                notification_message = HumanMessage(content=notification)
                current_state = {**state_values, "messages": [*messages, notification_message]}
                continue

            if not self.middleware.registry.has_pending_tasks():
                return

            # 当 auto_wait 为 False 时，说明我们希望立即把控制权交还给上层，
            # 例如 CLI 可以自己展示“仍有后台任务在运行”的状态。
            if not self.auto_wait:
                logger.info(
                    "background_orchestrator_returning_with_pending_tasks",
                    pending_count=self.middleware.registry.pending_count,
                )
                return

            logger.info(
                "background_orchestrator_waiting_after_stream",
                pending_count=self.middleware.registry.pending_count,
                timeout=self.middleware.timeout,
            )
            await self.middleware.registry.wait_for_all(timeout=self.middleware.timeout)

            notification = await self.check_and_get_notification()
            if not notification:
                return

            logger.info(
                "background_tasks_completed_after_stream_wait_notifying_agent",
                iteration=iteration,
            )
            state_snapshot = await self.agent.aget_state(config)
            state_values = state_snapshot.values
            messages = state_values.get("messages", [])
            notification_message = HumanMessage(content=notification)
            current_state = {**state_values, "messages": [*messages, notification_message]}

    def _format_notification(self) -> str:
        """为所有已完成后台任务生成统一通知文本。"""
        completed_tasks = [
            task for task in self.middleware.registry._tasks.values()
            if task.completed
        ]
        return self._format_notification_for_tasks(completed_tasks)

    def _format_notification_for_tasks(self, tasks: list[Any]) -> str:
        """为指定任务列表生成通知文本。"""
        if not tasks:
            return ""

        sorted_tasks = sorted(tasks, key=lambda item: item.task_number)

        if len(sorted_tasks) == 1:
            task = sorted_tasks[0]
            return (
                f"你的后台子代理任务已经完成：**{task.display_id}**。\n\n"
                f"请调用 `task_output(task_number={task.task_number})` 查看结果。"
            )

        task_list = ", ".join(f"**{task.display_id}**" for task in sorted_tasks)
        return (
            f"你的后台子代理任务已经完成：{task_list}。\n\n"
            f"请调用 `task_output()` 查看全部结果，"
            f"或调用 `task_output(task_number=N)` 查看单个任务结果。"
        )

    def get_pending_tasks_status(self) -> dict[str, Any]:
        """返回给上层界面展示的后台任务状态摘要。"""
        tasks = list(self.middleware.registry._tasks.values())
        pending_tasks = [task for task in tasks if not task.completed]
        completed_tasks = [task for task in tasks if task.completed]

        return {
            "total": len(tasks),
            "pending": len(pending_tasks),
            "completed": len(completed_tasks),
            "pending_tasks": [
                {
                    "id": task.display_id,
                    "type": task.subagent_type,
                    "description": task.description[:50],
                }
                for task in pending_tasks
            ],
            "completed_tasks": [
                {
                    "id": task.display_id,
                    "type": task.subagent_type,
                }
                for task in completed_tasks
            ],
        }

    def has_pending_tasks(self) -> bool:
        """返回当前是否仍有后台任务未完成。"""
        return self.middleware.registry.has_pending_tasks()

    async def check_and_get_notification(self) -> str | None:
        """检查是否有新完成的后台任务，并生成通知文本。"""
        # 先把已经结束但还没同步状态的 asyncio 任务同步回 registry。
        for task in self.middleware.registry._tasks.values():
            if not task.completed and task.asyncio_task and task.asyncio_task.done():
                task.completed = True
                try:
                    task.result = task.asyncio_task.result()
                except Exception as exc:  # noqa: BLE001
                    task.error = str(exc)
                    task.result = {"success": False, "error": str(exc)}

        all_tasks = list(self.middleware.registry._tasks.values())
        unseen_tasks = [task for task in all_tasks if task.completed and not task.result_seen]

        logger.debug(
            "background_orchestrator_check_notification",
            total_tasks=len(all_tasks),
            completed=[task.display_id for task in all_tasks if task.completed],
            unseen=[task.display_id for task in unseen_tasks],
        )

        if not unseen_tasks:
            return None

        # 这里把结果标记为“已通过通知感知”，
        # 但并不清理 registry，因为主代理下一轮还要调用 task_output() 取结果。
        for task in unseen_tasks:
            task.result_seen = True

        return self._format_notification_for_tasks(unseen_tasks)

    def with_config(self, config: dict[str, Any]) -> "BackgroundSubagentOrchestrator":
        """把配置继续下传给底层 agent，并返回新的调度器包装。"""
        configured_agent = self.agent.with_config(config)
        return BackgroundSubagentOrchestrator(
            agent=configured_agent,
            middleware=self.middleware,
            max_iterations=self.max_iterations,
            auto_wait=self.auto_wait,
        )

    def __getattr__(self, name: str) -> Any:
        """把未命中的属性访问代理到底层 agent。"""
        return getattr(self.agent, name)
