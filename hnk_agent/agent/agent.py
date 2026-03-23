"""hnk_agent 主装配层。"""

from __future__ import annotations

from typing import Any
from pathlib import Path

import structlog
from hnk_agent.agent.prompts import (
    build_general_subagent_system_prompt,
    build_main_agent_system_prompt,
)
from hnk_agent.agent.tools import (
    create_execute_bash_tool,
    create_execute_code_tool,
    create_filesystem_tools,
    create_glob_tool,
    create_grep_tool,
)
from hnk_agent.runtime import LocalRuntime
from hnk_agent.runtime.base import AgentRuntime

logger = structlog.get_logger(__name__)

DEFAULT_MAX_GENERAL_ITERATIONS = 10


class HNKAgent:
    """hnk_agent 的主 agent 装配器。"""

    def __init__(
        self,
        model: Any,
        *,
        runtime: AgentRuntime | None = None,
        tool_registry: Any | None = None,
        subagents_enabled: list[str] | None = None,
        use_filesystem_tools: bool = True,
        background_auto_wait: bool = False,
        recursion_limit: int = 1000,
        skill_sources: list[str] | None = None,
    ) -> None:
        """初始化 HNKAgent。"""
        self.model = model
        self.runtime = runtime or LocalRuntime()
        self.tool_registry = tool_registry
        self.subagents_enabled = subagents_enabled or ["general-purpose"]
        self.use_filesystem_tools = use_filesystem_tools
        self.background_auto_wait = background_auto_wait
        self.recursion_limit = recursion_limit
        self.skill_sources = list(skill_sources or [])

        if isinstance(self.runtime, LocalRuntime):
            for skill_source in self.skill_sources:
                resolved = Path(skill_source).expanduser().resolve()
                if resolved not in self.runtime.workspace.allowed_directories:
                    self.runtime.workspace.allowed_directories.append(resolved)

        self.subagents: dict[str, Any] = {}
        self.native_tools: list[str] = []

        logger.info(
            "initialized_hnk_agent",
            model=getattr(model, "model", getattr(model, "model_name", "unknown")),
            runtime_type=type(self.runtime).__name__,
        )

    def _build_tool_summary(self, tool_names: list[str]) -> str:
        """生成简单工具摘要。"""
        if not tool_names:
            return "当前没有可用工具。"
        return "\n".join(f"- {tool_name}" for tool_name in tool_names)

    def _build_subagent_summary(self, subagents: list[dict[str, Any]]) -> str:
        """生成简单子代理摘要。"""
        if not subagents:
            return "当前没有启用子代理。"

        lines: list[str] = []
        for subagent in subagents:
            name = str(subagent.get("name", "unknown"))
            description = str(subagent.get("description", "")).strip()
            lines.append(f"- {name}: {description}")
        return "\n".join(lines)

    def _build_system_prompt(
        self,
        tool_summary: str,
        subagent_summary: str,
        system_prompt_suffix: str | None = None,
    ) -> str:
        """构建主代理系统提示词。"""
        return build_main_agent_system_prompt(
            tool_summary=tool_summary,
            subagent_summary=subagent_summary,
            system_prompt_suffix=system_prompt_suffix,
        )

    def _build_general_subagent_system_prompt(
        self,
        *,
        max_iterations: int,
        tool_summary: str,
    ) -> str:
        """构建通用子代理系统提示词。"""
        return build_general_subagent_system_prompt(
            max_iterations=max_iterations,
            tool_summary=tool_summary,
        )

    def _build_langgraph_agent_with_background(
        self,
        *,
        runtime: AgentRuntime | None = None,
        tool_registry: Any | None = None,
        subagent_names: list[str] | None = None,
        additional_subagents: list[dict[str, Any]] | None = None,
        additional_tools: list[Any] | None = None,
        background_timeout: float = 300.0,
        checkpointer: Any | None = None,
        system_prompt_suffix: str | None = None,
        llm: Any | None = None,
    ) -> tuple[Any, Any]:
        """构建 raw LangGraph agent 及其后台中间件。"""
        try:
            from langchain.agents import create_agent
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Creating the full HNKAgent requires langchain to be installed"
            ) from exc

        from hnk_agent.agent.backends import LocalBackend
        from hnk_agent.agent.middleware import (
            BackgroundSubagentMiddleware,
            ToolCallCounterMiddleware,
            create_deepagent_middleware,
        )
        from hnk_agent.agent.subagents import create_subagents_from_names

        model = llm if llm is not None else self.model
        resolved_runtime = runtime or self.runtime
        resolved_tool_registry = tool_registry if tool_registry is not None else self.tool_registry

        execute_code_tool = create_execute_code_tool(
            resolved_runtime,
            tool_registry=resolved_tool_registry,
        )
        bash_tool = create_execute_bash_tool(resolved_runtime)

        tools: list[Any] = [execute_code_tool, bash_tool]

        filesystem_tools: list[Any] = []
        if self.use_filesystem_tools:
            read_file, write_file, edit_file = create_filesystem_tools(resolved_runtime)
            glob_tool = create_glob_tool(resolved_runtime)
            grep_tool = create_grep_tool(resolved_runtime)
            filesystem_tools = [read_file, write_file, edit_file, glob_tool, grep_tool]
            tools.extend(filesystem_tools)

        if additional_tools:
            tools.extend(additional_tools)

        backend = LocalBackend(resolved_runtime)

        background_middleware = BackgroundSubagentMiddleware(
            timeout=background_timeout,
            enabled=True,
        )
        tools.extend(background_middleware.tools)

        counter_middleware = ToolCallCounterMiddleware(
            registry=background_middleware.registry,
        )

        selected_subagents = subagent_names or self.subagents_enabled
        tool_names = [getattr(tool, "name", str(tool)) for tool in tools]
        tool_summary = self._build_tool_summary(tool_names)

        subagents = create_subagents_from_names(
            names=selected_subagents,
            counter_middleware=counter_middleware,
            max_iterations=DEFAULT_MAX_GENERAL_ITERATIONS,
            execute_code_tool=execute_code_tool,
            bash_tool=bash_tool,
            filesystem_tools=filesystem_tools,
            tool_summary=tool_summary,
            system_prompt=self._build_general_subagent_system_prompt(
                max_iterations=DEFAULT_MAX_GENERAL_ITERATIONS,
                tool_summary=tool_summary,
            ),
        )

        if additional_subagents:
            subagents.extend(additional_subagents)

        self.subagents = {}
        for subagent in subagents:
            name = str(subagent.get("name", "unknown"))
            subagent_tools = subagent.get("tools", [])
            tool_identities = [
                getattr(tool, "name", str(tool))
                for tool in subagent_tools
            ]
            self.subagents[name] = {
                "description": subagent.get("description", ""),
                "tools": tool_identities,
            }

        self.native_tools = tool_names

        subagent_summary = self._build_subagent_summary(subagents)
        system_prompt = self._build_system_prompt(
            tool_summary=tool_summary,
            subagent_summary=subagent_summary,
            system_prompt_suffix=system_prompt_suffix,
        )

        middleware_list: list[Any] = [background_middleware]
        deepagent_middleware = create_deepagent_middleware(
            model=model,
            tools=tools,
            subagents=subagents,
            backend=backend,
            skill_sources=self.skill_sources,
            custom_middleware=middleware_list,
        )

        agent = create_agent(
            model,
            system_prompt=system_prompt,
            tools=tools,
            middleware=deepagent_middleware,
            checkpointer=checkpointer,
        ).with_config({"recursion_limit": self.recursion_limit})

        return agent, background_middleware

    def create_langgraph_agent(
        self,
        *,
        runtime: AgentRuntime | None = None,
        tool_registry: Any | None = None,
        subagent_names: list[str] | None = None,
        additional_subagents: list[dict[str, Any]] | None = None,
        additional_tools: list[Any] | None = None,
        background_timeout: float = 300.0,
        checkpointer: Any | None = None,
        system_prompt_suffix: str | None = None,
        llm: Any | None = None,
    ) -> Any:
        """创建原生 LangGraph agent。

        这个入口直接返回 langchain.create_agent(...) 生成的 compiled graph，
        适合给 langgraph dev / Studio 使用，便于直接观察内部图结构与中间件行为。
        """
        agent, _ = self._build_langgraph_agent_with_background(
            runtime=runtime,
            tool_registry=tool_registry,
            subagent_names=subagent_names,
            additional_subagents=additional_subagents,
            additional_tools=additional_tools,
            background_timeout=background_timeout,
            checkpointer=checkpointer,
            system_prompt_suffix=system_prompt_suffix,
            llm=llm,
        )
        return agent

    def create_agent(
        self,
        *,
        runtime: AgentRuntime | None = None,
        tool_registry: Any | None = None,
        subagent_names: list[str] | None = None,
        additional_subagents: list[dict[str, Any]] | None = None,
        additional_tools: list[Any] | None = None,
        background_timeout: float = 300.0,
        checkpointer: Any | None = None,
        system_prompt_suffix: str | None = None,
        llm: Any | None = None,
    ) -> Any:
        """创建并返回最终可调用的业务 agent。"""
        from hnk_agent.agent.middleware import BackgroundSubagentOrchestrator

        agent, background_middleware = self._build_langgraph_agent_with_background(
            runtime=runtime,
            tool_registry=tool_registry,
            subagent_names=subagent_names,
            additional_subagents=additional_subagents,
            additional_tools=additional_tools,
            background_timeout=background_timeout,
            checkpointer=checkpointer,
            system_prompt_suffix=system_prompt_suffix,
            llm=llm,
        )

        return BackgroundSubagentOrchestrator(
            agent=agent,
            middleware=background_middleware,
            auto_wait=self.background_auto_wait,
        )
