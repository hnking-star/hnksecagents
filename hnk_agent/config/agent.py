"""Agent 配置模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hnk_agent.config.core import CoreConfig, LoggingConfig, RuntimeConfig, SecurityConfig
from hnk_agent.runtime import LocalRuntime
from hnk_agent.tooling import ToolRegistry
from hnk_agent.tooling.builtins import register_builtin_tools


@dataclass
class SkillsConfig:
    """技能配置。"""

    enabled: bool = True
    user_skills_dir: str = "~/.hnksecagents/skills"
    project_skills_dir: str = "skills"

    def local_skill_dirs(self, *, cwd: Path | None = None) -> list[str]:
        """返回本地技能目录列表。"""
        base = cwd or Path.cwd()
        return [
            str(Path(self.user_skills_dir).expanduser()),
            str((base / self.project_skills_dir).resolve()),
        ]


@dataclass
class LLMDefinition:
    """LLM 定义。"""

    name: str
    provider: str = ""
    model_id: str = ""
    sdk: str = ""
    api_key_env: str = ""
    base_url: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """LLM 选择配置。"""

    name: str = "custom"


@dataclass
class ToolingConfig:
    """工具层配置。"""

    enable_builtin_tools: bool = True


@dataclass
class AgentConfig:
    """完整 agent 配置。"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    tooling: ToolingConfig = field(default_factory=ToolingConfig)

    subagents_enabled: list[str] = field(default_factory=lambda: ["general-purpose"])
    use_filesystem_tools: bool = True
    background_auto_wait: bool = False
    recursion_limit: int = 1000

    llm_definition: LLMDefinition | None = None
    llm_client: Any | None = None
    config_file_dir: Path | None = None

    @classmethod
    def create(
        cls,
        llm: Any,
        **kwargs: Any,
    ) -> "AgentConfig":
        """使用传入的模型对象直接创建配置。"""
        runtime = RuntimeConfig(
            workspace_root=kwargs.pop("workspace_root", "."),
            allowed_directories=kwargs.pop("allowed_directories", [".", "/tmp"]),
            enable_path_validation=kwargs.pop("enable_path_validation", True),
            default_timeout=kwargs.pop("default_timeout", 300),
            shell_executable=kwargs.pop("shell_executable", "/bin/bash"),
        )

        security = SecurityConfig(
            max_execution_time=kwargs.pop("max_execution_time", 300),
            max_code_length=kwargs.pop("max_code_length", 10000),
            max_file_size=kwargs.pop("max_file_size", 10485760),
            enable_code_validation=kwargs.pop("enable_code_validation", True),
            allowed_imports=kwargs.pop("allowed_imports", SecurityConfig().allowed_imports),
            blocked_patterns=kwargs.pop("blocked_patterns", SecurityConfig().blocked_patterns),
        )

        logging = LoggingConfig(
            level=kwargs.pop("log_level", "INFO"),
            file=kwargs.pop("log_file", "logs/hnk_agent.log"),
        )

        skills = SkillsConfig(
            enabled=kwargs.pop("skills_enabled", True),
            user_skills_dir=kwargs.pop("user_skills_dir", "~/.hnksecagents/skills"),
            project_skills_dir=kwargs.pop("project_skills_dir", "skills"),
        )

        tooling = ToolingConfig(
            enable_builtin_tools=kwargs.pop("enable_builtin_tools", True),
        )

        config = cls(
            llm=LLMConfig(name="custom"),
            runtime=runtime,
            security=security,
            logging=logging,
            skills=skills,
            tooling=tooling,
            subagents_enabled=kwargs.pop("subagents_enabled", ["general-purpose"]),
            use_filesystem_tools=kwargs.pop("use_filesystem_tools", True),
            background_auto_wait=kwargs.pop("background_auto_wait", False),
            recursion_limit=kwargs.pop("recursion_limit", 1000),
            llm_client=llm,
        )

        return config

    def get_llm_client(self) -> Any:
        """返回已绑定的模型对象。

        如果当前还没有显式注入 llm_client，
        会尝试基于 llm_definition 或环境变量懒创建。
        """
        if self.llm_client is not None:
            return self.llm_client

        from hnk_agent.llm import create_llm_from_agent_config

        return create_llm_from_agent_config(self)

    def create_runtime(self) -> LocalRuntime:
        """按当前配置创建本地运行时。"""
        return LocalRuntime(
            root_dir=self.runtime.workspace_root,
            allowed_directories=self.runtime.allowed_directories,
            enable_path_validation=self.runtime.enable_path_validation,
            default_timeout=self.runtime.default_timeout,
            shell_executable=self.runtime.shell_executable,
        )

    def create_tool_registry(self) -> ToolRegistry:
        """按当前配置创建工具注册中心。"""
        registry = ToolRegistry()
        if self.tooling.enable_builtin_tools:
            register_builtin_tools(registry)
        return registry

    def to_core_config(self) -> CoreConfig:
        """转换为核心配置。"""
        return CoreConfig(
            runtime=self.runtime,
            security=self.security,
            logging=self.logging,
            config_file_dir=self.config_file_dir,
        )

    def to_agent_options(self) -> dict[str, Any]:
        """转换为 HNKAgent 构造参数。"""
        return {
            "subagents_enabled": self.subagents_enabled,
            "use_filesystem_tools": self.use_filesystem_tools,
            "background_auto_wait": self.background_auto_wait,
            "recursion_limit": self.recursion_limit,
        }
