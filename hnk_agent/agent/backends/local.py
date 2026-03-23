"""本地 deepagent backend 适配层。"""

from __future__ import annotations

import asyncio
import fnmatch
import re
import threading
from pathlib import Path
from typing import Any

import structlog
from deepagents.backends.protocol import (
    EditResult,
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    WriteResult,
)

from hnk_agent.runtime.local_runtime import LocalRuntime

logger = structlog.get_logger(__name__)


class LocalBackend:
    """把 LocalRuntime 适配到 deepagents backend 协议。"""

    def __init__(self, runtime: LocalRuntime, *, virtual_mode: bool = True) -> None:
        """初始化本地 backend。"""
        self.runtime = runtime
        self.virtual_mode = virtual_mode
        self.root_dir = str(runtime.workspace.root_dir)

        logger.info(
            "initialized_local_backend",
            root_dir=self.root_dir,
            virtual_mode=virtual_mode,
        )

    @property
    def id(self) -> str:
        """返回 backend 的稳定标识。"""
        return f"local:{self.root_dir}"

    def _normalize_path(self, path: str | None) -> str:
        """把输入路径转换成真实路径。"""
        if not self.virtual_mode:
            return str(path or self.root_dir)
        return self.runtime.normalize_path(path)

    def _format_cat_n(self, lines: list[str], *, start_line_number: int) -> str:
        """把文本按 cat -n 风格编号。"""
        return "\n".join(
            f"{line_number:6}\t{line}"
            for line_number, line in enumerate(lines, start=start_line_number)
        )

    def _run_sync(self, coroutine: Any) -> Any:
        """在同步接口里执行协程。

        如果当前线程没有事件循环，直接 asyncio.run。
        如果已经处于事件循环中，则切到新线程执行，避免嵌套事件循环报错。
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)

        result: dict[str, Any] = {}
        error: dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result["value"] = asyncio.run(coroutine)
            except BaseException as exc:  # noqa: BLE001
                error["value"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if "value" in error:
            raise error["value"]
        return result.get("value")

    def _path_for_output(self, path: str) -> str:
        """把真实路径转换成返回给上层的展示路径。"""
        return self.runtime.virtualize_path(path) if self.virtual_mode else path

    # ------------------------------------------------------------------
    # 同步接口
    # ------------------------------------------------------------------

    def ls_info(self, path: str = ".") -> list[dict]:  # pragma: no cover
        """同步目录列表接口。"""
        return self._run_sync(self.als_info(path))

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:  # pragma: no cover
        """同步文件读取接口。"""
        return self._run_sync(self.aread(file_path, offset, limit))

    def write(self, file_path: str, content: str) -> WriteResult:  # pragma: no cover
        """同步文件写入接口。"""
        return self._run_sync(self.awrite(file_path, content))

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        *,
        replace_all: bool = False,
    ) -> EditResult:  # pragma: no cover
        """同步文件编辑接口。"""
        return self._run_sync(
            self.aedit(
                file_path,
                old_string,
                new_string,
                replace_all=replace_all,
            )
        )

    def grep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list[dict] | str:  # pragma: no cover
        """同步 grep 接口。"""
        return self._run_sync(self.agrep_raw(pattern, path=path, glob=glob))

    def glob_info(self, pattern: str, path: str = "/") -> list[dict]:  # pragma: no cover
        """同步 glob 接口。"""
        return self._run_sync(self.aglob_info(pattern, path))

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:  # pragma: no cover
        """同步上传接口。"""
        return self._run_sync(self.aupload_files(files))

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:  # pragma: no cover
        """同步下载接口。"""
        return self._run_sync(self.adownload_files(paths))

    def execute(self, command: str) -> ExecuteResponse:  # pragma: no cover
        """同步命令执行接口。"""
        return self._run_sync(self.aexecute(command))

    # ------------------------------------------------------------------
    # 异步接口
    # ------------------------------------------------------------------

    async def als_info(self, path: str = ".") -> list[dict]:
        """异步列出目录内容。"""
        normalized_path = Path(self._normalize_path(path))
        if not normalized_path.exists() or not normalized_path.is_dir():
            return []

        def _scan() -> list[dict]:
            results: list[dict] = []
            for entry in sorted(normalized_path.iterdir(), key=lambda item: item.name):
                results.append(
                    {
                        "path": self._path_for_output(str(entry)),
                        "is_dir": entry.is_dir(),
                    }
                )
            return results

        return await asyncio.to_thread(_scan)

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """异步读取文件，并按行号格式返回。"""
        content = await self.runtime.read_file_text(file_path)
        if content is None:
            return f"Error: File '{file_path}' not found"

        lines = content.splitlines()
        window = lines[offset : offset + limit]
        return self._format_cat_n(window, start_line_number=offset + 1)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        """异步写入文件。"""
        result = await self.runtime.write_file_text(file_path=file_path, content=content)
        if result.get("success"):
            return WriteResult(
                path=self._path_for_output(self._normalize_path(file_path)),
                files_update=None,
            )
        return WriteResult(error=str(result.get("error", "Failed to write file")))

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        *,
        replace_all: bool = False,
    ) -> EditResult:
        """异步编辑文件。"""
        result = await self.runtime.edit_file_text(
            file_path=file_path,
            old_string=old_string,
            new_string=new_string,
            replace_all=replace_all,
        )
        if result.get("success"):
            return EditResult(
                path=self._path_for_output(self._normalize_path(file_path)),
                files_update=None,
                occurrences=int(result.get("occurrences", 1)),
            )
        return EditResult(error=str(result.get("error", "Edit failed")))

    async def agrep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[dict] | str:
        """异步 grep，返回结构化匹配结果。"""
        search_root = Path(self._normalize_path(path or "."))
        if not search_root.exists():
            return []

        try:
            regex = re.compile(pattern)
        except re.error:
            regex = re.compile(re.escape(pattern))

        def _search() -> list[dict]:
            matches: list[dict] = []
            candidate_files: list[Path] = []

            if search_root.is_file():
                candidate_files = [search_root]
            else:
                for candidate in search_root.rglob("*"):
                    if not candidate.is_file():
                        continue
                    if glob and not fnmatch.fnmatch(candidate.name, glob):
                        continue
                    candidate_files.append(candidate)

            for candidate in candidate_files:
                try:
                    text = candidate.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue

                for line_number, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        matches.append(
                            {
                                "path": self._path_for_output(str(candidate)),
                                "line": line_number,
                                "text": line,
                            }
                        )

            return matches

        return await asyncio.to_thread(_search)

    async def aglob_info(self, pattern: str, path: str = "/") -> list[dict]:
        """异步 glob，返回匹配路径信息。"""
        search_root = Path(self._normalize_path(path))
        if not search_root.exists():
            return []

        def _glob() -> list[dict]:
            if search_root.is_file():
                return [{"path": self._path_for_output(str(search_root))}]

            results: list[dict] = []
            for candidate in search_root.rglob("*"):
                relative = candidate.relative_to(search_root)
                if fnmatch.fnmatch(str(relative), pattern) or fnmatch.fnmatch(candidate.name, pattern):
                    results.append({"path": self._path_for_output(str(candidate))})
            return results

        return await asyncio.to_thread(_glob)

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """异步批量下载文件内容。"""

        async def _download_one(path: str) -> FileDownloadResponse:
            normalized = Path(self._normalize_path(path))
            try:
                content = await asyncio.to_thread(normalized.read_bytes)
                return FileDownloadResponse(path=path, content=content)
            except OSError:
                logger.exception("local_backend_download_failed", path=path)
                return FileDownloadResponse(path=path, error="file_not_found")

        return await asyncio.gather(*[_download_one(path) for path in paths])

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """异步批量上传文件内容。"""

        async def _upload_one(path: str, content: bytes) -> FileUploadResponse:
            normalized = Path(self._normalize_path(path))
            try:
                if not self.runtime.validate_path(str(normalized)):
                    return FileUploadResponse(path=path, error="permission_denied")

                await asyncio.to_thread(normalized.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(normalized.write_bytes, content)
                return FileUploadResponse(path=path)
            except OSError:
                logger.exception("local_backend_upload_failed", path=path)
                return FileUploadResponse(path=path, error="permission_denied")

        return await asyncio.gather(*[_upload_one(path, content) for path, content in files])

    async def aexecute(self, command: str) -> ExecuteResponse:
        """异步执行 Shell 命令。"""
        try:
            result = await self.runtime.execute_shell(
                command=command,
                working_dir=".",
                timeout=60,
                background=False,
            )
            output = (result.stdout or "") + (f"\n{result.stderr}" if result.stderr else "")
            return ExecuteResponse(
                output=output,
                exit_code=int(result.exit_code),
                truncated=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("local_backend_execute_failed")
            return ExecuteResponse(output=str(exc), exit_code=1, truncated=False)
