"""内容搜索工具封装。"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any, Literal

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)


def _matches_glob_pattern(
    *,
    pattern: str,
    name: str,
    relative_path: Path | None = None,
    relative_str: str | None = None,
) -> bool:
    """统一处理常见 glob 模式匹配。"""
    candidates: list[str] = [name]
    if relative_str:
        candidates.append(relative_str)

    for candidate in candidates:
        if fnmatch.fnmatch(candidate, pattern):
            return True

    if relative_path is not None and relative_path.match(pattern):
        return True

    if pattern.startswith("**/"):
        fallback_pattern = pattern[3:]
        for candidate in candidates:
            if fnmatch.fnmatch(candidate, fallback_pattern):
                return True
        if relative_path is not None and relative_path.match(fallback_pattern):
            return True

    return False


def _match_type(candidate: Path, file_type: str | None) -> bool:
    """按简化的文件类型规则过滤文件。"""
    if not file_type:
        return True

    normalized_type = file_type.lstrip(".")
    suffix = candidate.suffix.lstrip(".")
    return suffix == normalized_type


def _match_glob(candidate: Path, search_root: Path, glob_pattern: str | None) -> bool:
    """按 glob 规则过滤候选文件。"""
    if not glob_pattern:
        return True

    relative_path = candidate.relative_to(search_root)
    relative = str(relative_path)
    return _matches_glob_pattern(
        pattern=glob_pattern,
        name=candidate.name,
        relative_path=relative_path,
        relative_str=relative,
    )


def _collect_candidate_files(
    search_root: Path,
    *,
    glob_pattern: str | None,
    file_type: str | None,
) -> list[Path]:
    """收集符合过滤条件的候选文件。"""
    if search_root.is_file():
        if _match_type(search_root, file_type) and _match_glob(search_root, search_root.parent, glob_pattern):
            return [search_root]
        return []

    candidates: list[Path] = []
    for candidate in search_root.rglob("*"):
        if not candidate.is_file():
            continue
        if not _match_type(candidate, file_type):
            continue
        if not _match_glob(candidate, search_root, glob_pattern):
            continue
        candidates.append(candidate)

    return sorted(candidates)


def _build_content_entry(
    *,
    runtime: Any,
    file_path: Path,
    line_number: int,
    line: str,
    n: bool,
) -> str:
    """构造单条内容输出。"""
    virtual_path = runtime.virtualize_path(str(file_path))
    if n:
        return f"{virtual_path}:{line_number}:{line}"
    return f"{virtual_path}:{line}"


def create_grep_tool(runtime: Any) -> BaseTool:
    """创建 grep 工具。"""

    @tool
    async def grep(
        pattern: str,
        path: str | None = None,
        output_mode: Literal["files_with_matches", "content", "count"] | None = "files_with_matches",
        glob: str | None = None,
        type: str | None = None,  # noqa: A002
        i: bool | None = False,
        n: bool | None = True,
        A: int | None = None,
        B: int | None = None,
        C: int | None = None,
        multiline: bool | None = False,
        head_limit: int | None = None,
        offset: int = 0,
    ) -> str:
        """按正则模式搜索文件内容。

        适用场景：
        - 搜索配置键、函数名、报错文本
        - 在指定目录或指定文件类型中检索内容

        当前实现说明：
        - 支持 `files_with_matches`、`content`、`count`
        - `A/B/C/multiline` 先保留接口，后续可继续增强
        """
        del A, B, C, multiline

        if runtime is None:
            return "ERROR: Runtime not initialized"

        search_path = path or "."

        try:
            flags = re.MULTILINE
            if i:
                flags |= re.IGNORECASE

            try:
                regex = re.compile(pattern, flags)
            except re.error as exc:
                return f"ERROR: Invalid regex pattern: {exc!s}"

            normalized_path = runtime.normalize_path(search_path)
            if not runtime.validate_path(normalized_path):
                return f"ERROR: Access denied: {search_path}"

            search_root = Path(normalized_path)
            if not search_root.exists():
                return f"ERROR: Path not found: {search_path}"

            logger.info(
                "grep_search_started",
                pattern=pattern,
                path=search_path,
                normalized_path=normalized_path,
                output_mode=output_mode,
                glob=glob,
                file_type=type,
                case_insensitive=bool(i),
            )

            candidates = _collect_candidate_files(
                search_root,
                glob_pattern=glob,
                file_type=type,
            )

            file_matches: list[str] = []
            content_matches: list[str] = []
            count_matches: list[tuple[str, int]] = []

            for candidate in candidates:
                try:
                    text = candidate.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue

                line_hits: list[tuple[int, str]] = []
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        line_hits.append((line_number, line))

                if not line_hits:
                    continue

                virtual_path = runtime.virtualize_path(str(candidate))
                file_matches.append(virtual_path)
                count_matches.append((virtual_path, len(line_hits)))

                for line_number, line in line_hits:
                    content_matches.append(
                        _build_content_entry(
                            runtime=runtime,
                            file_path=candidate,
                            line_number=line_number,
                            line=line,
                            n=bool(n),
                        )
                    )

            if output_mode == "count":
                selected: list[Any] = count_matches
            elif output_mode == "content":
                selected = content_matches
            else:
                selected = file_matches

            if offset > 0:
                selected = selected[offset:]
            if head_limit is not None:
                selected = selected[:head_limit]

            if not selected:
                return f"No matches found for pattern '{pattern}' in '{search_path}'"

            if output_mode == "count":
                lines = [f"Match counts for pattern '{pattern}':"]
                for file_path, count in selected:
                    lines.append(f"{file_path}: {count}")
                result = "\n".join(lines)
            elif output_mode == "content":
                result = f"Matches for pattern '{pattern}':\n" + "\n".join(selected)
            else:
                lines = [f"Found matches in {len(selected)} file(s):"]
                lines.extend(selected)
                result = "\n".join(lines)

            logger.info(
                "grep_search_completed",
                pattern=pattern,
                path=search_path,
                output_mode=output_mode,
                results_count=len(selected),
            )
            return result

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "grep_tool_exception",
                pattern=pattern,
                path=search_path,
                error=str(exc),
                exc_info=True,
            )
            return f"ERROR: Failed to grep content: {exc!s}"

    return grep
