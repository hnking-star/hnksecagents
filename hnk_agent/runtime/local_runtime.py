"""本地运行时实现。"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Any

import structlog

from hnk_agent.runtime.base import AgentRuntime
from hnk_agent.runtime.execution_result import PythonExecutionResult, ShellExecutionResult
from hnk_agent.runtime.workspace import LocalWorkspace

logger = structlog.get_logger(__name__)


class LocalRuntime(AgentRuntime):
    """基于本地文件系统和本地 Python/Shell 的运行时实现。"""

    def __init__(
        self,
        root_dir: str | Path | None = None,
        *,
        workspace: LocalWorkspace | None = None,
        allowed_directories: list[str | Path] | None = None,
        enable_path_validation: bool = True,
        default_timeout: int = 300,
        shell_executable: str = "/bin/bash",
    ) -> None:
        """初始化本地运行时。"""
        root = Path(root_dir or Path.cwd()).expanduser().resolve()
        self.workspace = workspace or LocalWorkspace(
            root_dir=root,
            allowed_directories=allowed_directories,
            enable_path_validation=enable_path_validation,
        )
        self.workspace.ensure_layout()

        self.default_timeout = default_timeout
        self.shell_executable = shell_executable
        self.execution_count = 0
        self.shell_execution_count = 0

    def normalize_path(self, path: str | None) -> str:
        """转发给工作区做路径规范化。"""
        return self.workspace.normalize_path(path)

    def virtualize_path(self, path: str) -> str:
        """转发给工作区做路径虚拟化。"""
        return self.workspace.virtualize_path(path)

    def validate_path(self, file_path: str) -> bool:
        """转发给工作区做路径校验。"""
        return self.workspace.validate_path(file_path)

    async def execute_shell(
        self,
        command: str,
        working_dir: str | None = None,
        timeout: int | None = None,
        background: bool = False,
    ) -> ShellExecutionResult:
        """执行本地 Shell 命令。"""
        normalized_dir, error = self.workspace.validate_and_normalize_path(working_dir or ".")
        if error:
            return ShellExecutionResult(
                success=False,
                stdout="",
                stderr=error,
                exit_code=1,
                duration=0.0,
                command=command,
                working_dir=normalized_dir,
                background=background,
            )

        start_time = time.time()
        self.shell_execution_count += 1

        logger.info(
            "local_runtime_execute_shell",
            command=command[:100],
            working_dir=normalized_dir,
            background=background,
        )

        if background:
            process = await asyncio.create_subprocess_exec(
                self.shell_executable,
                "-lc",
                command,
                cwd=normalized_dir,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            duration = time.time() - start_time
            return ShellExecutionResult(
                success=True,
                stdout=f"Background command started (pid {process.pid})",
                stderr="",
                exit_code=0,
                duration=duration,
                command=command,
                working_dir=normalized_dir,
                background=True,
                pid=process.pid,
            )

        process = await asyncio.create_subprocess_exec(
            self.shell_executable,
            "-lc",
            command,
            cwd=normalized_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout or self.default_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
            duration = time.time() - start_time
            return ShellExecutionResult(
                success=False,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=f"Command timed out after {timeout or self.default_timeout}s\n"
                + stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=-1,
                duration=duration,
                command=command,
                working_dir=normalized_dir,
            )

        duration = time.time() - start_time
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = process.returncode or 0

        return ShellExecutionResult(
            success=exit_code == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration=duration,
            command=command,
            working_dir=normalized_dir,
        )

    async def execute_python(
        self,
        code: str,
        tool_registry: Any | None = None,
        timeout: int | None = None,
        working_dir: str | None = None,
    ) -> PythonExecutionResult:
        """执行本地 Python 代码。"""
        del tool_registry

        normalized_dir, error = self.workspace.validate_and_normalize_path(working_dir or ".")
        if error:
            return PythonExecutionResult(
                success=False,
                stdout="",
                stderr=error,
                duration=0.0,
            )

        self.workspace.ensure_layout()
        self.execution_count += 1
        execution_id = f"exec_{self.execution_count:04d}"
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        code_path = self.workspace.code_dir / f"{execution_id}.py"

        start_time = time.time()
        files_before = await self._list_workspace_files()
        await asyncio.to_thread(code_path.write_text, code, "utf-8")

        env = os.environ.copy()
        python_paths = [normalized_dir]
        existing_pythonpath = env.get("PYTHONPATH")
        if existing_pythonpath:
            python_paths.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(python_paths)

        logger.info(
            "local_runtime_execute_python",
            execution_id=execution_id,
            code_length=len(code),
            working_dir=normalized_dir,
        )

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(code_path),
            cwd=normalized_dir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout or self.default_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
            duration = time.time() - start_time
            return PythonExecutionResult(
                success=False,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=f"Code execution timed out after {timeout or self.default_timeout}s\n"
                + stderr_bytes.decode("utf-8", errors="replace"),
                duration=duration,
                execution_id=execution_id,
                code_hash=code_hash,
            )

        duration = time.time() - start_time
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        success = (process.returncode or 0) == 0

        files_after = await self._list_workspace_files()
        files_created = sorted(files_after - files_before)

        return PythonExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            duration=duration,
            files_created=files_created,
            files_modified=[],
            execution_id=execution_id,
            code_hash=code_hash,
        )

    async def read_file_text(self, file_path: str) -> str | None:
        """读取文本文件。"""
        normalized, error = self.workspace.validate_and_normalize_path(file_path)
        if error:
            raise ValueError(error)

        path = Path(normalized)
        if not path.exists() or not path.is_file():
            return None

        try:
            return await asyncio.to_thread(path.read_text, "utf-8")
        except UnicodeDecodeError:
            return None

    async def read_file_range(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> str | None:
        """按行范围读取文本文件。"""
        content = await self.read_file_text(file_path)
        if content is None:
            return None

        lines = content.splitlines()
        start = max(0, offset)
        end = start + limit
        return "\n".join(lines[start:end])

    async def write_file_text(self, file_path: str, content: str) -> dict[str, Any]:
        """写入文本文件。"""
        normalized, error = self.workspace.validate_and_normalize_path(file_path)
        if error:
            return {"success": False, "error": error}

        path = Path(normalized)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, encoding="utf-8")
        return {
            "success": True,
            "path": self.virtualize_path(str(path)),
            "bytes_written": len(content.encode("utf-8")),
        }

    async def edit_file_text(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> dict[str, Any]:
        """编辑文本文件内容。"""
        normalized, error = self.workspace.validate_and_normalize_path(file_path)
        if error:
            return {"success": False, "error": error}

        path = Path(normalized)
        if not path.exists() or not path.is_file():
            return {"success": False, "error": "File not found"}

        content = await asyncio.to_thread(path.read_text, encoding="utf-8")

        if old_string == new_string:
            return {"success": False, "error": "old_string and new_string must be different"}

        if old_string not in content:
            return {"success": False, "error": f"old_string not found in file: {file_path}"}

        if not replace_all and content.count(old_string) > 1:
            return {
                "success": False,
                "error": "old_string found multiple times and requires more code context to uniquely identify the intended match",
            }

        updated = (
            content.replace(old_string, new_string)
            if replace_all
            else content.replace(old_string, new_string, 1)
        )

        if updated == content:
            return {"success": False, "error": "Edit produced no changes"}

        await asyncio.to_thread(path.write_text, updated, encoding="utf-8")
        occurrences = content.count(old_string) if replace_all else 1
        return {
            "success": True,
            "message": f"Updated {self.virtualize_path(str(path))}",
            "occurrences": occurrences,
        }

    async def _list_workspace_files(self) -> set[str]:
        """列出当前工作区内的文件集合，用于追踪新生成文件。"""
        return await asyncio.to_thread(self._list_workspace_files_sync)

    def _list_workspace_files_sync(self) -> set[str]:
        """同步收集工作区文件列表。"""
        ignored_dir_names = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "code"}
        ignored_files = {".DS_Store"}

        results: set[str] = set()
        for path in self.workspace.root_dir.rglob("*"):
            if any(part in ignored_dir_names for part in path.parts):
                continue
            if path.name in ignored_files:
                continue
            if path.is_file():
                results.add(self.virtualize_path(str(path)))
        return results
