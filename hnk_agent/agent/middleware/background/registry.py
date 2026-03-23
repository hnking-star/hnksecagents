"""后台子代理任务注册中心。

这个模块负责维护后台任务的状态、结果和基础统计信息，
是 `task / wait / task_output` 机制的状态核心。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BackgroundTask:
    """后台子代理任务的数据结构。"""

    task_id: str
    """任务唯一标识，通常直接复用 tool_call_id。"""

    task_number: int
    """顺序编号，供主代理以 Task-N 的形式引用。"""

    description: str
    """任务描述，通常来自 task(description=...)。"""

    subagent_type: str
    """子代理类型，例如 research 或 general-purpose。"""

    asyncio_task: asyncio.Task[Any] | None = None
    """真正执行后台任务的 asyncio.Task 对象。"""

    created_at: float = field(default_factory=time.time)
    """任务创建时间戳。"""

    result: Any = None
    """任务完成后的结果。"""

    error: str | None = None
    """任务失败时的错误信息。"""

    completed: bool = False
    """任务是否已经完成。"""

    result_seen: bool = False
    """主代理是否已经显式看过结果。"""

    tool_call_counts: dict[str, int] = field(default_factory=dict)
    """各工具被调用的次数统计。"""

    total_tool_calls: int = 0
    """工具总调用次数。"""

    current_tool: str = ""
    """当前正在执行的工具名。"""

    last_update_time: float = field(default_factory=time.time)
    """最后一次更新统计信息的时间。"""

    @property
    def display_id(self) -> str:
        """返回给主代理展示用的 Task-N 标识。"""
        return f"Task-{self.task_number}"

    @property
    def is_pending(self) -> bool:
        """判断任务是否仍处于运行中或待运行状态。"""
        if self.completed:
            return False
        if self.asyncio_task is None:
            return True
        return not self.asyncio_task.done()


class BackgroundTaskRegistry:
    """后台任务注册中心。

    这个类负责：
    - 注册后台任务
    - 按编号或 ID 查询任务
    - 等待任务完成
    - 保存缓存结果
    - 记录工具调用统计
    """

    def __init__(self) -> None:
        """初始化注册中心。"""
        self._tasks: dict[str, BackgroundTask] = {}
        self._task_by_number: dict[int, str] = {}
        self._next_task_number = 1
        self._lock = asyncio.Lock()
        self._results: dict[str, Any] = {}

    async def register(
        self,
        task_id: str,
        description: str,
        subagent_type: str,
        asyncio_task: asyncio.Task[Any] | None = None,
    ) -> BackgroundTask:
        """注册一个新的后台任务。"""
        async with self._lock:
            task_number = self._next_task_number
            self._next_task_number += 1

            task = BackgroundTask(
                task_id=task_id,
                task_number=task_number,
                description=description,
                subagent_type=subagent_type,
                asyncio_task=asyncio_task,
            )
            self._tasks[task_id] = task
            self._task_by_number[task_number] = task_id

            logger.info(
                "registered_background_task",
                task_id=task_id,
                task_number=task_number,
                display_id=task.display_id,
                subagent_type=subagent_type,
            )

            return task

    async def get_pending_tasks(self) -> list[BackgroundTask]:
        """返回所有尚未完成的任务。"""
        async with self._lock:
            return [task for task in self._tasks.values() if task.is_pending]

    async def get_all_tasks(self) -> list[BackgroundTask]:
        """返回所有已注册任务。"""
        async with self._lock:
            return list(self._tasks.values())

    async def get_by_number(self, task_number: int) -> BackgroundTask | None:
        """按顺序编号获取任务。"""
        async with self._lock:
            task_id = self._task_by_number.get(task_number)
            if task_id is None:
                return None
            return self._tasks.get(task_id)

    def get_by_id(self, task_id: str) -> BackgroundTask | None:
        """按任务 ID 获取任务。

        这里保留同步接口，方便在外部已经确定没有并发修改时直接读取。
        """
        return self._tasks.get(task_id)

    async def update_metrics(self, task_id: str, tool_name: str) -> None:
        """更新某个后台任务的工具调用统计。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            task.tool_call_counts[tool_name] = task.tool_call_counts.get(tool_name, 0) + 1
            task.total_tool_calls += 1
            task.current_tool = tool_name
            task.last_update_time = time.time()

            logger.debug(
                "updated_background_task_metrics",
                task_id=task_id,
                tool_name=tool_name,
                total_tool_calls=task.total_tool_calls,
            )

    async def wait_for_specific(self, task_number: int, timeout: float = 60.0) -> dict[str, Any]:
        """等待指定编号的任务完成。"""
        task_id = self._task_by_number.get(task_number)
        if task_id is None:
            return {"success": False, "error": f"Task-{task_number} not found"}

        task = self._tasks.get(task_id)
        if task is None:
            return {"success": False, "error": f"Task-{task_number} not found"}

        if task.completed:
            return task.result or {"success": True, "result": None}

        if task.asyncio_task is None:
            return {"success": False, "error": f"Task-{task_number} has no asyncio task"}

        logger.info(
            "waiting_for_specific_background_task",
            task_number=task_number,
            display_id=task.display_id,
            timeout=timeout,
        )

        # 这里使用 asyncio.wait 而不是直接 await，
        # 这样在超时时可以保留任务继续在后台运行。
        await asyncio.wait(
            [task.asyncio_task],
            timeout=timeout,
            return_when=asyncio.ALL_COMPLETED,
        )

        async with self._lock:
            if task.asyncio_task.done():
                task.completed = True
                try:
                    result = task.asyncio_task.result()
                    task.result = result
                    self._results[task_id] = result
                    logger.info(
                        "specific_background_task_completed",
                        task_number=task_number,
                        display_id=task.display_id,
                    )
                    return result
                except Exception as exc:  # noqa: BLE001
                    task.error = str(exc)
                    error_result = {"success": False, "error": str(exc)}
                    self._results[task_id] = error_result
                    return error_result

            return {
                "success": False,
                "error": f"Wait timed out after {timeout}s - task may still be running",
                "status": "timeout",
            }

    async def wait_for_all(self, timeout: float = 60.0) -> dict[str, Any]:
        """等待所有未完成任务，直到完成或超时。"""
        async with self._lock:
            tasks_to_wait = {
                task_id: task.asyncio_task
                for task_id, task in self._tasks.items()
                if not task.completed and task.asyncio_task is not None
            }

        if not tasks_to_wait:
            logger.debug("no_background_tasks_to_wait")
            return self._results.copy()

        logger.info(
            "waiting_for_all_background_tasks",
            task_count=len(tasks_to_wait),
            timeout=timeout,
        )

        await asyncio.wait(
            tasks_to_wait.values(),
            timeout=timeout,
            return_when=asyncio.ALL_COMPLETED,
        )

        results: dict[str, Any] = {}
        async with self._lock:
            for task_id, asyncio_task in tasks_to_wait.items():
                task = self._tasks.get(task_id)
                if task is None:
                    continue

                if asyncio_task.done():
                    task.completed = True
                    try:
                        result = asyncio_task.result()
                        task.result = result
                        results[task_id] = result
                        logger.info(
                            "background_task_completed",
                            task_id=task_id,
                            success=result.get("success", False) if isinstance(result, dict) else True,
                        )
                    except Exception as exc:  # noqa: BLE001
                        task.error = str(exc)
                        results[task_id] = {"success": False, "error": str(exc)}
                        logger.error(
                            "background_task_failed",
                            task_id=task_id,
                            error=str(exc),
                        )
                else:
                    # 超时不代表失败，只表示主代理这次等待结束后任务仍在后台继续执行。
                    results[task_id] = {
                        "success": False,
                        "error": f"Wait timed out after {timeout}s - task may still be running",
                        "status": "timeout",
                    }
                    logger.warning(
                        "background_task_wait_timeout",
                        task_id=task_id,
                        timeout=timeout,
                    )

            self._results.update(results)

        return results

    async def get_result(self, task_id: str) -> Any | None:
        """获取指定任务的缓存结果。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return self._results.get(task_id)

            if task.completed:
                return task.result

            # 如果底层 asyncio 任务已经结束，但状态还没同步，
            # 这里顺手把结果同步回来，避免外层读到旧状态。
            if task.asyncio_task is not None and task.asyncio_task.done():
                task.completed = True
                try:
                    task.result = task.asyncio_task.result()
                    return task.result
                except Exception as exc:  # noqa: BLE001
                    task.error = str(exc)
                    return {"success": False, "error": str(exc)}

            return None

    async def is_task_done(self, task_id: str) -> bool:
        """判断指定任务是否已经完成。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return task_id in self._results
            if task.completed:
                return True
            if task.asyncio_task is not None:
                return task.asyncio_task.done()
            return False

    async def cancel_task(self, task_id: str) -> bool:
        """取消指定后台任务。"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.asyncio_task is None:
                return False

            if not task.completed and not task.asyncio_task.done():
                task.asyncio_task.cancel()
                task.completed = True
                task.error = "Cancelled"
                logger.info("cancelled_background_task", task_id=task_id)
                return True

            return False

    async def cancel_all(self) -> int:
        """取消所有仍在运行的后台任务。"""
        cancelled = 0
        async with self._lock:
            for task in self._tasks.values():
                if task.asyncio_task is None:
                    continue
                if not task.completed and not task.asyncio_task.done():
                    task.asyncio_task.cancel()
                    task.completed = True
                    task.error = "Cancelled"
                    cancelled += 1

        if cancelled > 0:
            logger.info("cancelled_background_tasks", count=cancelled)

        return cancelled

    def clear(self) -> None:
        """清空注册中心中的任务和结果缓存。

        注意：
        - 这个方法不会主动取消正在运行的 asyncio 任务
        - 如果需要彻底停止后台任务，应先调用 cancel_all()
        """
        self._tasks.clear()
        self._task_by_number.clear()
        self._next_task_number = 1
        self._results.clear()
        logger.debug("cleared_background_task_registry")

    def has_pending_tasks(self) -> bool:
        """返回当前是否还存在未完成任务。"""
        return any(task.is_pending for task in self._tasks.values())

    @property
    def task_count(self) -> int:
        """返回当前总任务数。"""
        return len(self._tasks)

    @property
    def pending_count(self) -> int:
        """返回当前未完成任务数。"""
        return sum(1 for task in self._tasks.values() if task.is_pending)
