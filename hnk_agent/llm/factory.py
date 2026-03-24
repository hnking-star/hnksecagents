"""模型工厂。

这一层负责统一创建聊天模型，避免：
- langgraph 入口自己拼环境变量
- Session/Config 各写一套模型初始化逻辑
- 后续 CLI、部署入口重复实现
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

if TYPE_CHECKING:
    from hnk_agent.config.agent import AgentConfig, LLMDefinition


def load_env_file(env_file: str | Path | None = None, *, override: bool = False) -> Path | None:
    """加载指定的 .env 文件。"""
    if env_file is None:
        return None

    env_path = Path(env_file).expanduser().resolve()
    if not env_path.exists():
        return None

    load_dotenv(env_path, override=override)
    return env_path


def get_env_str(name: str, default: str | None = None) -> str | None:
    """读取环境变量字符串，并自动清理空值。"""
    value = os.getenv(name, default)
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


def _parse_float(value: str | None) -> float | None:
    """把字符串解析为浮点数。"""
    if value is None:
        return None
    return float(value)


def _parse_int(value: str | None) -> int | None:
    """把字符串解析为整数。"""
    if value is None:
        return None
    return int(value)


def _guess_provider(model_name: str | None) -> str | None:
    """按常见模型名前缀猜测 provider。"""
    if not model_name:
        return None

    normalized = model_name.lower()
    if normalized.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    if normalized.startswith("claude"):
        return "anthropic"
    if normalized.startswith("gemini"):
        return "google_genai"
    if normalized.startswith("deepseek"):
        return "openai"
    return None


def _normalize_provider(provider: str | None, model_name: str | None) -> str | None:
    """规范化 provider，并在缺失时尝试推断。"""
    if provider:
        return provider.strip()
    return _guess_provider(model_name)


def _compact_kwargs(raw_kwargs: dict[str, Any]) -> dict[str, Any]:
    """移除值为 None 的参数。"""
    return {
        key: value
        for key, value in raw_kwargs.items()
        if value is not None
    }


def create_chat_model(
    *,
    model_name: str,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    user_agent: str | None = None,
    extra_parameters: dict[str, Any] | None = None,
) -> Any:
    """创建 LangChain 聊天模型实例。"""
    resolved_provider = _normalize_provider(provider, model_name)
    if not resolved_provider:
        raise ValueError(
            "无法确定模型 provider。"
            "请显式提供 provider，或使用可推断的模型名称。"
        )

    kwargs = _compact_kwargs(
        {
            "api_key": api_key,
            "base_url": base_url,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "default_headers": {"User-Agent": user_agent} if user_agent else None,
        }
    )

    if extra_parameters:
        kwargs.update(extra_parameters)

    return init_chat_model(
        model=model_name,
        model_provider=resolved_provider,
        **kwargs,
    )


def create_llm_from_env(
    *,
    prefix: str = "HNKSECAGENTS",
    env_file: str | Path | None = None,
    override: bool = False,
) -> Any:
    """从环境变量创建聊天模型。"""
    load_env_file(env_file, override=override)

    model_name = get_env_str(f"{prefix}_MODEL")
    if not model_name:
        raise ValueError(f"缺少环境变量 {prefix}_MODEL")

    provider = get_env_str(f"{prefix}_MODEL_PROVIDER")
    api_key = get_env_str(f"{prefix}_API_KEY")
    base_url = get_env_str(f"{prefix}_BASE_URL")
    temperature = _parse_float(get_env_str(f"{prefix}_TEMPERATURE"))
    max_tokens = _parse_int(get_env_str(f"{prefix}_MAX_TOKENS"))

    user_agent = get_env_str(f"{prefix}_USER_AGENT")

    return create_chat_model(
        model_name=model_name,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        user_agent=user_agent,
    )


def create_llm_from_definition(
    definition: LLMDefinition,
    *,
    env_prefix: str = "HNKSECAGENTS",
    env_file: str | Path | None = None,
    override: bool = False,
) -> Any:
    """从 LLMDefinition 创建聊天模型。"""
    load_env_file(env_file, override=override)

    model_name = definition.model_id or definition.name
    provider = definition.provider or _guess_provider(model_name)

    api_key = None
    if definition.api_key_env:
        api_key = get_env_str(definition.api_key_env)
    if api_key is None:
        api_key = get_env_str(f"{env_prefix}_API_KEY")

    base_url = definition.base_url or get_env_str(f"{env_prefix}_BASE_URL")

    parameters = dict(definition.parameters)
    temperature = parameters.pop("temperature", None)
    max_tokens = parameters.pop("max_tokens", None)
    user_agent = parameters.pop("user_agent", None) or get_env_str(f"{env_prefix}_USER_AGENT")

    return create_chat_model(
        model_name=model_name,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        temperature=float(temperature) if temperature is not None else None,
        max_tokens=int(max_tokens) if max_tokens is not None else None,
        user_agent=str(user_agent) if user_agent is not None else None,
        extra_parameters=parameters,
    )


def create_llm_from_agent_config(
    config: AgentConfig,
    *,
    env_prefix: str = "HNKSECAGENTS",
    env_file: str | Path | None = None,
    override: bool = False,
) -> Any:
    """从 AgentConfig 懒创建聊天模型。"""
    if config.llm_client is not None:
        return config.llm_client

    if config.llm_definition is not None:
        model = create_llm_from_definition(
            config.llm_definition,
            env_prefix=env_prefix,
            env_file=env_file,
            override=override,
        )
        config.llm_client = model
        return model

    model = create_llm_from_env(
        prefix=env_prefix,
        env_file=env_file,
        override=override,
    )
    config.llm_client = model
    return model
