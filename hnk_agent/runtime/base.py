"""运行时抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentRuntime(ABC):
    """Agent 运行时抽象基类。

    这一层用于隔离 agent/tools 与具体执行后端。
    后续无论是本地执行、远程执行，还是更严格的安全沙箱，
    只要实现这一组接口即可接入上层。
    """

    @abstractmethod
    async def execute_shell(
        self,
        command: str,
        working_dir: str | None = None,
        timeout: int | None = None,
        background: bool = False,
    ) -> Any:
        """执行 Shell 命令。"""

    @abstractmethod
    async def execute_python(
        self,
        code: str,
        tool_registry: Any | None = None,
        timeout: int | None = None,
        working_dir: str | None = None,
    ) -> Any:
        """执行 Python 代码。"""

    @abstractmethod
    async def read_file_text(self, file_path: str) -> str | None:
        """读取文本文件。"""

    @abstractmethod
    async def read_file_range(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> str | None:
        """按行范围读取文本文件。"""

    @abstractmethod
    async def write_file_text(self, file_path: str, content: str) -> Any:
        """写入文本文件。"""

    @abstractmethod
    async def edit_file_text(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> Any:
        """编辑文本文件。"""

    @abstractmethod
    def normalize_path(self, path: str | None) -> str:
        """把输入路径规范化为真实路径。"""

    @abstractmethod
    def virtualize_path(self, path: str) -> str:
        """把真实路径转换为对 agent 更友好的展示路径。"""

    @abstractmethod
    def validate_path(self, file_path: str) -> bool:
        """校验路径是否允许访问。"""
