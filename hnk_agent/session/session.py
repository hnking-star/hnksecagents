"""会话生命周期管理。"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

import structlog

from hnk_agent.agent import HNKAgent
from hnk_agent.config import AgentConfig
from hnk_agent.runtime import LocalRuntime
from hnk_agent.runtime.base import AgentRuntime
from hnk_agent.tooling import ToolRegistry
from hnk_agent.tooling.builtins import register_builtin_tools

logger = structlog.get_logger(__name__)


class Session:
    """代表一个完整的 agent 会话。"""

    def __init__(
        self,
        conversation_id: str,
        model: Any | None = None,
        *,
        config: AgentConfig | None = None,
        runtime: AgentRuntime | None = None,
        tool_registry: ToolRegistry | None = None,
        agent_options: dict[str, Any] | None = None,
        workspace_root: str | None = None,
    ) -> None:
        """初始化会话。"""
        self.conversation_id = conversation_id
        self.model = model
        self.config = config
        self.runtime = runtime
        self.tool_registry = tool_registry
        self.agent_options = agent_options or {}
        self.workspace_root = workspace_root

        self.agent_builder: HNKAgent | None = None
        self.agent: Any | None = None
        self._initialized = False

        logger.info("created_session", conversation_id=conversation_id)

    async def initialize(self) -> None:
        """初始化会话中的运行时、工具注册中心和 agent。"""
        if self._initialized:
            logger.warning("session_already_initialized", conversation_id=self.conversation_id)
            return

        logger.info("initializing_session", conversation_id=self.conversation_id)

        model = self.model
        runtime = self.runtime
        tool_registry = self.tool_registry
        agent_options = dict(self.agent_options)
        workspace_root = self.workspace_root

        if self.config is not None:
            model = self.config.get_llm_client()
            agent_options = {**self.config.to_agent_options(), **agent_options}

            if workspace_root is None:
                workspace_root = self.config.runtime.workspace_root

            skill_dirs: list[str] = []
            if self.config.skills.enabled:
                skill_dirs = self.config.skills.local_skill_dirs(
                    cwd=Path(workspace_root or "."),
                )

            if runtime is None:
                allowed_directories = list(self.config.runtime.allowed_directories)
                for skill_dir in skill_dirs:
                    if skill_dir not in allowed_directories:
                        allowed_directories.append(skill_dir)

                runtime = LocalRuntime(
                    root_dir=workspace_root,
                    allowed_directories=allowed_directories,
                    enable_path_validation=self.config.runtime.enable_path_validation,
                    default_timeout=self.config.runtime.default_timeout,
                    shell_executable=self.config.runtime.shell_executable,
                )

            if tool_registry is None:
                tool_registry = ToolRegistry()

            if self.config.tooling.enable_builtin_tools:
                register_builtin_tools(tool_registry)

            if self.config.skills.enabled and "skill_sources" not in agent_options:
                agent_options["skill_sources"] = skill_dirs

        if model is None:
            raise ValueError("Session requires either a model or an AgentConfig with llm_client")

        if runtime is None:
            runtime = LocalRuntime(root_dir=workspace_root)
        elif isinstance(runtime, LocalRuntime) and self.config is not None and self.config.skills.enabled:
            skill_dirs = self.config.skills.local_skill_dirs(
                cwd=Path(workspace_root or "."),
            )
            for skill_dir in skill_dirs:
                resolved = Path(skill_dir).expanduser().resolve()
                if resolved not in runtime.workspace.allowed_directories:
                    runtime.workspace.allowed_directories.append(resolved)

        if tool_registry is None:
            tool_registry = ToolRegistry()

        if self.runtime is None:
            self.runtime = runtime
        else:
            runtime = self.runtime

        if self.tool_registry is None:
            self.tool_registry = tool_registry
        else:
            tool_registry = self.tool_registry

        self.agent_builder = HNKAgent(
            model,
            runtime=runtime,
            tool_registry=tool_registry,
            **agent_options,
        )
        self.agent = self.agent_builder.create_agent()
        self._initialized = True

        logger.info("session_initialized", conversation_id=self.conversation_id)

    async def get_agent(self) -> Any:
        """获取当前会话的 agent，如未初始化则先初始化。"""
        if not self._initialized:
            await self.initialize()
        return self.agent

    async def cleanup(self) -> None:
        """清理会话状态。"""
        logger.info("cleaning_up_session", conversation_id=self.conversation_id)
        self.agent = None
        self.agent_builder = None
        self._initialized = False

        logger.info("session_cleaned_up", conversation_id=self.conversation_id)

    async def stop(self) -> None:
        """停止会话。

        当前本地实现没有额外外部资源需要停机，
        因此这里先与 cleanup 保持一致语义。
        """
        await self.cleanup()

    async def __aenter__(self) -> "Session":
        """异步上下文入口。"""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """异步上下文退出。"""
        await self.cleanup()
