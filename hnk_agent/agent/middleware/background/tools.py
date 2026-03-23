"""后台子代理管理工具。

这个模块负责把后台任务注册中心包装成主代理可调用的工具，
当前主要提供：
- wait：主动等待后台任务完成
- task_output：查看后台任务结果或进度
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.tools import StructuredTool

if TYPE_CHECKING:
    from hnk_agent.agent.middleware.background.middleware import BackgroundSubagentMiddleware
    from hnk_agent.agent.middleware.background.registry import BackgroundTask, BackgroundTaskRegistry

logger = structlog.get_logger(__name__)


def _sync_task_completion(task: BackgroundTask) -> None:
    """把 asyncio 任务的实际完成状态同步回任务对象。"""
    if task.completed:
        return
    if task.asyncio_task is None:
        return
    if not task.asyncio_task.done():
        return

    task.completed = True
    try:
        task.result = task.asyncio_task.result()
    except Exception as exc:  # noqa: BLE001
        task.error = str(exc)
        task.result = {"success": False, "error": str(exc)}


def extract_result_content(result: dict[str, Any] | Any) -> tuple[bool, str]:
    """从任务结果中提取统一的可展示内容。"""
    if not isinstance(result, dict):
        return (True, str(result))

    if result.get("success"):
        inner = result.get("result")
        if inner is None:
            return (True, "任务已成功完成，但没有返回内容")

        if hasattr(inner, "content"):
            return (True, str(inner.content))

        # 某些结果对象会把真正消息放在 update.messages 里。
        if hasattr(inner, "update"):
            update = inner.update
            if isinstance(update, dict) and "messages" in update:
                messages = update["messages"]
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, "content"):
                        return (True, str(last_message.content))

        return (True, str(inner))

    error = result.get("error", "未知错误")
    status = result.get("status", "error")
    return (False, f"{status.upper()}: {error}")


def _format_result(result: dict[str, Any] | Any) -> str:
    """把任务结果格式化为主代理可读文本。"""
    success, content = extract_result_content(result)
    if success:
        return content
    return f"任务失败：{content}"


def _format_task_progress(task: BackgroundTask) -> str:
    """把运行中的任务状态格式化为进度文本。"""
    elapsed_seconds = max(0, int(time.time() - task.created_at))
    last_update_seconds = max(0, int(time.time() - task.last_update_time))

    lines = [
        f"**{task.display_id}** ({task.subagent_type}) 仍在运行中",
        f"- 任务描述：{task.description}",
        f"- 已运行：{elapsed_seconds}s",
        f"- 工具调用总数：{task.total_tool_calls}",
    ]

    if task.current_tool:
        lines.append(f"- 当前工具：{task.current_tool}")

    if task.tool_call_counts:
        tool_summary = ", ".join(
            f"{tool_name} x{count}"
            for tool_name, count in sorted(
                task.tool_call_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        )
        lines.append(f"- 工具统计：{tool_summary}")

    lines.append(f"- 最近一次状态更新：{last_update_seconds}s 前")
    return "\n".join(lines)


def create_wait_tool(middleware: BackgroundSubagentMiddleware) -> StructuredTool:
    """创建 wait 工具。"""

    async def wait_for_subagents(
        task_number: int | None = None,
        timeout: float = 60.0,
    ) -> str:
        """等待后台任务完成并返回结果。"""
        registry = middleware.registry

        if task_number is not None:
            logger.info(
                "waiting_for_specific_task_via_tool",
                task_number=task_number,
                timeout=timeout,
            )

            result = await registry.wait_for_specific(task_number, timeout)
            task = await registry.get_by_number(task_number)

            if task is None:
                return f"Task-{task_number} not found"

            if isinstance(result, dict) and result.get("status") == "timeout":
                return (
                    f"**{task.display_id}** ({task.subagent_type}) 仍在后台运行中 "
                    f"(本次等待 {timeout}s 后返回，任务没有被取消)"
                )

            task.result_seen = True
            return (
                f"**{task.display_id}** ({task.subagent_type}) 已完成：\n\n"
                f"{_format_result(result)}"
            )

        logger.info("waiting_for_all_tasks_via_tool", timeout=timeout)
        results = await registry.wait_for_all(timeout=timeout)

        if not results:
            return "当前没有需要等待的后台任务。"

        completed_count = sum(
            1 for result in results.values()
            if not (isinstance(result, dict) and result.get("status") == "timeout")
        )
        running_count = len(results) - completed_count

        if running_count == 0:
            output = f"全部 {len(results)} 个后台任务已完成：\n\n"
        elif completed_count == 0:
            output = f"全部 {len(results)} 个后台任务仍在运行中（本次等待 {timeout}s）：\n\n"
        else:
            output = f"后台任务状态：{completed_count} 个完成，{running_count} 个仍在运行。\n\n"

        for task_id, result in results.items():
            task = registry.get_by_id(task_id)
            if task is None:
                continue

            is_running = isinstance(result, dict) and result.get("status") == "timeout"
            if is_running:
                output += f"### {task.display_id} ({task.subagent_type}) - 仍在运行\n\n"
                continue

            task.result_seen = True
            output += (
                f"### {task.display_id} ({task.subagent_type}) - 已完成\n"
                f"{_format_result(result)}\n\n"
            )

        return output

    return StructuredTool.from_function(
        name="wait",
        description=(
            "等待后台子代理任务完成并返回结果。"
            "可以指定 task_number 等待单个任务，也可以不传参数等待所有任务。"
        ),
        coroutine=wait_for_subagents,
    )


def create_task_output_tool(registry: BackgroundTaskRegistry) -> StructuredTool:
    """创建 task_output 工具。"""

    async def task_output(task_number: int | None = None) -> str:
        """查询后台任务结果或进度。"""
        if task_number is not None:
            task = await registry.get_by_number(task_number)
            if task is None:
                return f"Task-{task_number} not found"

            _sync_task_completion(task)

            if task.completed:
                task.result_seen = True
                return (
                    f"**{task.display_id}** ({task.subagent_type}) 已完成：\n\n"
                    f"{_format_result(task.result)}"
                )

            return _format_task_progress(task)

        all_tasks = await registry.get_all_tasks()
        if not all_tasks:
            return "当前还没有分配任何后台任务。"

        for task in all_tasks:
            _sync_task_completion(task)

        pending_count = sum(1 for task in all_tasks if not task.completed)
        completed_count = len(all_tasks) - pending_count

        output = (
            f"**后台任务概览**（共 {len(all_tasks)} 个："
            f"{completed_count} 个完成，{pending_count} 个运行中）\n\n"
        )

        for task in sorted(all_tasks, key=lambda item: item.task_number):
            if task.completed:
                task.result_seen = True
                output += (
                    f"### {task.display_id} ({task.subagent_type})\n"
                    f"{_format_result(task.result)}\n\n"
                )
            else:
                output += _format_task_progress(task) + "\n\n"

        return output

    return StructuredTool.from_function(
        name="task_output",
        description=(
            "查看后台子代理任务的结果或进度。"
            "如果任务已完成则返回结果，否则返回当前进度。"
        ),
        coroutine=task_output,
    )
