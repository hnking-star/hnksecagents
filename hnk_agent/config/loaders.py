"""文件配置加载入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hnk_agent.config.agent import AgentConfig, LLMConfig, LLMDefinition, SkillsConfig, ToolingConfig
from hnk_agent.config.core import CoreConfig, LoggingConfig, RuntimeConfig, SecurityConfig
from hnk_agent.config.utils import load_json_file, load_yaml_file


def get_default_config_dir() -> Path:
    """返回默认配置目录。"""
    return Path.home() / ".hnksecagents"


def find_config_file(filename: str, search_paths: list[Path] | None = None) -> Path | None:
    """在候选目录里查找配置文件。"""
    paths = search_paths or [Path.cwd(), get_default_config_dir()]
    for search_path in paths:
        candidate = search_path / filename
        if candidate.exists():
            return candidate
    return None


def _load_llm_catalog(llms_file: Path) -> dict[str, LLMDefinition]:
    """加载 llms.json。"""
    raw_data = load_json_file(llms_file)
    catalog: dict[str, LLMDefinition] = {}

    if not isinstance(raw_data, dict):
        return catalog

    for name, item in raw_data.items():
        if not isinstance(item, dict):
            continue
        catalog[name] = LLMDefinition(
            name=name,
            provider=str(item.get("provider", "")),
            model_id=str(item.get("model_id", item.get("model", ""))),
            sdk=str(item.get("sdk", "")),
            api_key_env=str(item.get("api_key_env", "")),
            base_url=item.get("base_url"),
            parameters=dict(item.get("parameters", {})),
        )

    return catalog


def load_from_dict(
    config_data: dict[str, Any],
    llm_catalog: dict[str, LLMDefinition] | None = None,
) -> AgentConfig:
    """从字典创建 AgentConfig。"""
    runtime_data = dict(config_data.get("runtime", {}))
    security_data = dict(config_data.get("security", {}))
    logging_data = dict(config_data.get("logging", {}))
    skills_data = dict(config_data.get("skills", {}))
    tooling_data = dict(config_data.get("tooling", {}))
    agent_data = dict(config_data.get("agent", {}))
    llm_data = dict(config_data.get("llm", {}))

    llm_name = str(llm_data.get("name", "custom"))
    llm_definition = llm_catalog.get(llm_name) if llm_catalog else None

    config = AgentConfig(
        llm=LLMConfig(name=llm_name),
        runtime=RuntimeConfig(
            workspace_root=str(runtime_data.get("workspace_root", ".")),
            allowed_directories=list(runtime_data.get("allowed_directories", [".", "/tmp"])),
            enable_path_validation=bool(runtime_data.get("enable_path_validation", True)),
            default_timeout=int(runtime_data.get("default_timeout", 300)),
            shell_executable=str(runtime_data.get("shell_executable", "/bin/bash")),
        ),
        security=SecurityConfig(
            max_execution_time=int(security_data.get("max_execution_time", 300)),
            max_code_length=int(security_data.get("max_code_length", 10000)),
            max_file_size=int(security_data.get("max_file_size", 10485760)),
            enable_code_validation=bool(security_data.get("enable_code_validation", True)),
            allowed_imports=list(security_data.get("allowed_imports", SecurityConfig().allowed_imports)),
            blocked_patterns=list(security_data.get("blocked_patterns", SecurityConfig().blocked_patterns)),
        ),
        logging=LoggingConfig(
            level=str(logging_data.get("level", "INFO")),
            file=str(logging_data.get("file", "logs/hnk_agent.log")),
        ),
        skills=SkillsConfig(
            enabled=bool(skills_data.get("enabled", True)),
            user_skills_dir=str(skills_data.get("user_skills_dir", "~/.hnksecagents/skills")),
            project_skills_dir=str(skills_data.get("project_skills_dir", "skills")),
        ),
        tooling=ToolingConfig(
            enable_builtin_tools=bool(tooling_data.get("enable_builtin_tools", True)),
        ),
        subagents_enabled=list(agent_data.get("subagents_enabled", ["general-purpose"])),
        use_filesystem_tools=bool(agent_data.get("use_filesystem_tools", True)),
        background_auto_wait=bool(agent_data.get("background_auto_wait", False)),
        recursion_limit=int(agent_data.get("recursion_limit", 1000)),
        llm_definition=llm_definition,
    )

    return config


def load_from_files(
    config_file: Path | None = None,
    llms_file: Path | None = None,
) -> AgentConfig:
    """从文件系统加载 AgentConfig。"""
    resolved_config_file = config_file or find_config_file("config.yaml")
    if resolved_config_file is None:
        raise FileNotFoundError("config.yaml not found")

    resolved_llms_file = llms_file or find_config_file("llms.json")
    llm_catalog = _load_llm_catalog(resolved_llms_file) if resolved_llms_file else {}

    config_data = load_yaml_file(resolved_config_file)
    config = load_from_dict(config_data, llm_catalog=llm_catalog)
    config.config_file_dir = resolved_config_file.parent
    return config


def load_core_from_files(config_file: Path | None = None) -> CoreConfig:
    """从文件加载 CoreConfig。"""
    agent_config = load_from_files(config_file=config_file)
    return agent_config.to_core_config()
