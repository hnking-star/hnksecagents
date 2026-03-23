"""子代理定义与装配入口。"""

from collections.abc import Callable
from typing import Any

from hnk_agent.agent.subagents.general import (
    create_general_subagent,
    get_general_subagent_config,
)

# 当前先只保留最关键的通用子代理。
# 研究型子代理、专项子代理后续再逐步补。
SUBAGENT_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "general-purpose": create_general_subagent,
}

# 记录每类子代理允许接收的参数，避免把无关参数一路传下去。
SUBAGENT_PARAMS: dict[str, dict[str, list[str]]] = {
    "general-purpose": {
        "accepted": [
            "max_iterations",
            "execute_code_tool",
            "bash_tool",
            "filesystem_tools",
            "additional_tools",
            "vision_tools",
            "middleware",
            "tool_summary",
            "system_prompt",
            "description",
        ],
    },
}


def create_subagent_by_name(name: str, **kwargs: Any) -> dict[str, Any]:
    """按名称创建单个子代理配置。"""
    if name not in SUBAGENT_REGISTRY:
        available = ", ".join(SUBAGENT_REGISTRY.keys())
        raise ValueError(f"Unknown subagent: '{name}'. Available: {available}")

    create_fn = SUBAGENT_REGISTRY[name]
    accepted_params = SUBAGENT_PARAMS.get(name, {}).get("accepted", [])
    filtered_kwargs = {key: value for key, value in kwargs.items() if key in accepted_params}
    return create_fn(**filtered_kwargs)


def create_subagents_from_names(
    names: list[str],
    counter_middleware: Any | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """按名称批量创建子代理配置。"""
    subagents: list[dict[str, Any]] = []

    for name in names:
        spec = create_subagent_by_name(name, **kwargs)

        # 后台任务模式下，会把计数中间件注入到子代理里，
        # 这样 task_output() 才能展示出子代理的工具调用进度。
        if counter_middleware is not None:
            existing_middleware = spec.get("middleware", [])
            spec["middleware"] = [counter_middleware, *list(existing_middleware)]

        subagents.append(spec)

    return subagents


__all__ = [
    "SUBAGENT_REGISTRY",
    "create_general_subagent",
    "create_subagent_by_name",
    "create_subagents_from_names",
    "get_general_subagent_config",
]
