"""文件操作工具封装。"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


def _format_cat_n(lines: list[str], *, start_line_number: int) -> str:
    """把文本按类似 cat -n 的方式加上行号。"""
    return "\n".join(
        f"{line_number:6}\t{line}"
        for line_number, line in enumerate(lines, start=start_line_number)
    )


def _get_result_value(result: Any, key: str, default: Any = None) -> Any:
    """统一从字典或对象结果里读取字段。"""
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def create_filesystem_tools(runtime: Any) -> tuple[Any, Any, Any]:
    """创建读、写、编辑文件工具。

    当前约定 runtime 需要提供：
    - read_file_text(file_path)
    - read_file_range(file_path, offset, limit)  可选
    - write_file_text(file_path, content)
    - edit_file_text(file_path, old_string, new_string, replace_all=False)
    """

    @tool
    async def read_file(
        file_path: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        """读取文件内容，并以带行号的文本返回。"""
        if runtime is None:
            return "ERROR: Runtime not initialized"

        try:
            logger.info(
                "reading_file_via_tool",
                file_path=file_path,
                offset=offset,
                limit=limit,
            )

            start_offset = offset or 0
            max_lines = limit or 2000

            # 如果 runtime 提供了范围读取，优先直接用；
            # 否则回退到全量读取后再在工具层裁剪。
            if hasattr(runtime, "read_file_range") and (offset is not None or limit is not None):
                content = await runtime.read_file_range(
                    file_path=file_path,
                    offset=start_offset,
                    limit=max_lines,
                )
            else:
                full_content = await runtime.read_file_text(file_path=file_path)
                if full_content is None:
                    return f"ERROR: File not found: {file_path}"
                lines = str(full_content).splitlines()
                content = "\n".join(lines[start_offset : start_offset + max_lines])

            if content is None:
                return f"ERROR: File not found: {file_path}"

            lines = str(content).splitlines()
            return _format_cat_n(lines, start_line_number=start_offset + 1)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "read_file_tool_exception",
                file_path=file_path,
                error=str(exc),
                exc_info=True,
            )
            return f"ERROR: Failed to read file: {exc!s}"

    @tool
    async def write_file(file_path: str, content: str) -> str:
        """写入文件内容，若文件存在则覆盖。"""
        if runtime is None:
            return "ERROR: Runtime not initialized"

        try:
            logger.info(
                "writing_file_via_tool",
                file_path=file_path,
                content_length=len(content),
            )

            result = await runtime.write_file_text(
                file_path=file_path,
                content=content,
            )

            success = bool(_get_result_value(result, "success", result is True))
            if not success:
                error = _get_result_value(result, "error", "Write operation failed")
                return f"ERROR: {error}"

            bytes_written = len(content.encode("utf-8"))
            return f"Wrote {bytes_written} bytes to {file_path}"

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "write_file_tool_exception",
                file_path=file_path,
                error=str(exc),
                exc_info=True,
            )
            return f"ERROR: Failed to write file: {exc!s}"

    @tool
    async def edit_file(
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """在文件中精确替换字符串。"""
        if runtime is None:
            return "ERROR: Runtime not initialized"

        try:
            logger.info(
                "editing_file_via_tool",
                file_path=file_path,
                replace_all=replace_all,
                old_string_preview=old_string[:80],
            )

            result = await runtime.edit_file_text(
                file_path=file_path,
                old_string=old_string,
                new_string=new_string,
                replace_all=replace_all,
            )

            success = bool(_get_result_value(result, "success", False))
            if not success:
                error = _get_result_value(result, "error", "Edit operation failed")
                return f"ERROR: {error}"

            message = _get_result_value(result, "message", "File edited successfully")
            return str(message)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "edit_file_tool_exception",
                file_path=file_path,
                error=str(exc),
                exc_info=True,
            )
            return f"ERROR: Failed to edit file: {exc!s}"

    return read_file, write_file, edit_file
