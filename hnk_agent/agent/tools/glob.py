"""文件匹配工具封装。"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)


def _matches_pattern(
    *,
    pattern: str,
    name: str,
    relative_path: Path | None = None,
    relative_str: str | None = None,
) -> bool:
    """统一处理常见 glob 规则匹配。"""
    candidates: list[str] = [name]
    if relative_str:
        candidates.append(relative_str)

    for candidate in candidates:
        if fnmatch.fnmatch(candidate, pattern):
            return True

    if relative_path is not None and relative_path.match(pattern):
        return True

    # `**/*.py` 这类模式在顶层文件上容易漏匹配，
    # 这里补一个去掉 `**/` 前缀的兜底分支。
    if pattern.startswith("**/"):
        fallback_pattern = pattern[3:]
        for candidate in candidates:
            if fnmatch.fnmatch(candidate, fallback_pattern):
                return True
        if relative_path is not None and relative_path.match(fallback_pattern):
            return True

    return False


def _collect_matches(search_root: Path, pattern: str) -> list[Path]:
    """收集匹配 glob 规则的文件和目录。"""
    results: list[Path] = []

    if search_root.is_file():
        if _matches_pattern(pattern=pattern, name=search_root.name):
            return [search_root]
        return []

    for candidate in search_root.rglob("*"):
        relative = candidate.relative_to(search_root)
        relative_str = str(relative)
        if _matches_pattern(
            pattern=pattern,
            name=candidate.name,
            relative_path=relative,
            relative_str=relative_str,
        ):
            results.append(candidate)

    return sorted(results)


def create_glob_tool(runtime: Any) -> BaseTool:
    """创建 glob 工具。"""

    @tool
    async def glob(pattern: str, path: str | None = None) -> str:
        """按文件名或相对路径模式查找文件。

        适用场景：
        - 查找某类文件，例如 `**/*.py`
        - 在某个目录下按名字筛选文件

        不适用场景：
        - 按文件内容搜索，请使用 grep
        """
        if runtime is None:
            return "ERROR: Runtime not initialized"

        search_path = path or "."

        try:
            normalized_path = runtime.normalize_path(search_path)
            if not runtime.validate_path(normalized_path):
                return f"ERROR: Access denied: {search_path}"

            search_root = Path(normalized_path)
            if not search_root.exists():
                return f"ERROR: Path not found: {search_path}"

            logger.info(
                "glob_search_started",
                pattern=pattern,
                path=search_path,
                normalized_path=normalized_path,
            )

            matches = _collect_matches(search_root, pattern)
            if not matches:
                return f"No files matching pattern '{pattern}' found in '{search_path}'"

            lines = [f"Found {len(matches)} path(s) matching '{pattern}':"]
            for match in matches:
                lines.append(runtime.virtualize_path(str(match)))

            logger.info(
                "glob_search_completed",
                pattern=pattern,
                path=search_path,
                matches=len(matches),
            )
            return "\n".join(lines)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "glob_tool_exception",
                pattern=pattern,
                path=search_path,
                error=str(exc),
                exc_info=True,
            )
            return f"ERROR: Failed to glob files: {exc!s}"

    return glob
