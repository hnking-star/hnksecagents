"""Bash 工具封装。

这一层负责把 runtime 的命令执行能力包装成 agent 可调用工具。
"""

from typing import Any

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)


def _get_result_value(result: Any, key: str, default: Any = None) -> Any:
    """统一从字典或对象结果里读取字段。"""
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def create_execute_bash_tool(runtime: Any) -> BaseTool:
    """创建 Bash 工具。

    当前约定 runtime 需要提供：
    - execute_shell(command, working_dir=None, timeout=None, background=False)
    """

    @tool
    async def Bash(
        command: str,
        description: str | None = None,
        timeout: int | None = 120000,
        run_in_background: bool | None = False,
        working_dir: str | None = None,
    ) -> str:
        """执行 Bash 命令。

        适用场景：
        - git、npm、构建命令
        - 目录操作
        - 系统命令执行

        不适用场景：
        - 精确的文件读写编辑，优先使用专门的文件工具

        参数：
        - command: 要执行的命令
        - description: 命令的简短描述，当前仅用于语义补充
        - timeout: 超时时间，单位毫秒
        - run_in_background: 是否后台执行
        - working_dir: 工作目录，未传时由 runtime 自行决定
        """
        del description

        if runtime is None:
            return "ERROR: Runtime not initialized"

        try:
            logger.info(
                "executing_bash_command",
                command=command[:100],
                working_dir=working_dir,
                timeout=timeout,
                background=run_in_background,
            )

            # agent 工具层统一接受毫秒，这里转换成更适合 runtime 的秒级超时。
            timeout_seconds: int | None
            if timeout is None:
                timeout_seconds = None
            else:
                timeout_seconds = max(1, int(timeout / 1000))

            result = await runtime.execute_shell(
                command=command,
                working_dir=working_dir,
                timeout=timeout_seconds,
                background=bool(run_in_background),
            )

            success = bool(_get_result_value(result, "success", False))
            stdout = str(_get_result_value(result, "stdout", "") or "")
            stderr = str(_get_result_value(result, "stderr", "") or "")
            exit_code = _get_result_value(result, "exit_code", -1)

            if success:
                output = stdout
                if stderr:
                    output = f"{output}\n{stderr}" if output else stderr

                if output:
                    logger.info(
                        "bash_command_completed",
                        command=command[:50],
                        output_length=len(output),
                    )
                    return output

                logger.info(
                    "bash_command_completed_without_output",
                    command=command[:50],
                )
                return "Command completed successfully"

            logger.warning(
                "bash_command_failed",
                command=command[:50],
                exit_code=exit_code,
            )
            error_output = stderr or stdout or "Command execution failed"
            return f"ERROR: Command failed (exit code {exit_code})\n{error_output}"

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "bash_command_exception",
                command=command[:50],
                error=str(exc),
                exc_info=True,
            )
            return f"ERROR: Failed to execute bash command: {exc!s}"

    return Bash
