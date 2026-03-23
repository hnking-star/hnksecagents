"""代码执行工具封装。

这一层负责把 runtime 的 Python 执行能力包装成 agent 可调用工具，
是后续 PTC 机制继续演进的基础入口。
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)


def _get_result_value(result: Any, key: str, default: Any = None) -> Any:
    """统一从字典或对象结果里读取字段。"""
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def _format_created_files(files_created: Any) -> str:
    """把创建文件列表格式化成可展示文本。"""
    if not files_created:
        return ""

    normalized: list[str] = []
    for item in files_created:
        if hasattr(item, "name"):
            normalized.append(str(item.name))
        else:
            normalized.append(str(item))

    if not normalized:
        return ""

    return f"Files created: {', '.join(normalized)}"


def create_execute_code_tool(runtime: Any, tool_registry: Any | None = None) -> BaseTool:
    """创建代码执行工具。

    当前约定 runtime 需要提供：
    - execute_python(code, tool_registry=None)

    这里保留 tool_registry 这个入口，
    后续可以把本地工具注入能力接进来，而不用重写工具层接口。
    """

    @tool
    async def execute_code(code: str) -> str:
        """执行 Python 代码。

        适用场景：
        - 多步骤数据处理
        - 复杂逻辑编排
        - 文件生成与结果汇总
        - 后续通过本地工具注册中心进行程序化工具调用

        参数：
        - code: 要执行的 Python 代码
        """
        if runtime is None:
            return "ERROR: Runtime not initialized"

        try:
            logger.info(
                "executing_python_code",
                code_length=len(code),
                tool_registry_enabled=tool_registry is not None,
            )

            result = await runtime.execute_python(
                code=code,
                tool_registry=tool_registry,
            )

            success = bool(_get_result_value(result, "success", False))
            stdout = str(_get_result_value(result, "stdout", "") or "")
            stderr = str(_get_result_value(result, "stderr", "") or "")
            files_created = _get_result_value(result, "files_created", [])

            if success:
                parts: list[str] = ["SUCCESS"]

                if stdout:
                    parts.append(stdout)

                files_text = _format_created_files(files_created)
                if files_text:
                    parts.append(files_text)

                logger.info(
                    "python_code_completed",
                    stdout_length=len(stdout),
                    created_file_count=len(files_created) if files_created else 0,
                )
                return "\n".join(parts)

            error_output = stderr if stderr else stdout
            logger.warning(
                "python_code_failed",
                stderr_length=len(stderr),
                stdout_length=len(stdout),
            )
            return f"ERROR\n{error_output}"

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "python_code_exception",
                error=str(exc),
                exc_info=True,
            )
            return f"ERROR: Failed to execute code: {exc!s}"

    return execute_code
