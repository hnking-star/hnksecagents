"""运行时结果对象。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ShellExecutionResult:
    """Shell 命令执行结果。"""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    command: str = ""
    working_dir: str = ""
    background: bool = False
    pid: int | None = None


@dataclass
class PythonExecutionResult:
    """Python 代码执行结果。"""

    success: bool
    stdout: str
    stderr: str
    duration: float
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    execution_id: str = ""
    code_hash: str = ""
