"""供 langgraph dev 使用的图入口。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hnk_agent.agent import HNKAgent
from hnk_agent.config import AgentConfig
from hnk_agent.llm import create_llm_from_env, load_env_file

_agent = None


def _project_root() -> Path:
    """返回仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def _load_project_env() -> None:
    """加载项目根目录下的 .env。"""
    load_env_file(_project_root() / ".env", override=False)


def _get_env_str(name: str, default: str | None = None) -> str | None:
    """读取环境变量字符串，并自动去掉空值。"""
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _build_agent() -> Any:
    """构建供 langgraph dev 直接加载的原生 graph agent。"""
    _load_project_env()

    repo_root = _project_root()
    workspace_root = _get_env_str("HNKSECAGENTS_WORKSPACE_ROOT", str(repo_root)) or str(repo_root)
    model = create_llm_from_env(
        prefix="HNKSECAGENTS",
        env_file=_project_root() / ".env",
    )

    config = AgentConfig.create(
        model,
        workspace_root=workspace_root,
        allowed_directories=[workspace_root, "/tmp"],
        enable_builtin_tools=True,
        subagents_enabled=["general-purpose"],
        use_filesystem_tools=True,
        background_auto_wait=False,
    )

    runtime = config.create_runtime()
    tool_registry = config.create_tool_registry()
    skill_sources = config.skills.local_skill_dirs(cwd=Path(workspace_root))

    builder = HNKAgent(
        model,
        runtime=runtime,
        tool_registry=tool_registry,
        **config.to_agent_options(),
        skill_sources=skill_sources,
    )
    return builder.create_langgraph_agent()


if _agent is None:
    _agent = _build_agent()

agent = _agent
