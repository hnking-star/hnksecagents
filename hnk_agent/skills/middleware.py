"""技能动态提示词中间件。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import SystemMessage

from hnk_agent.skills.registry import SkillRegistry


PromptBuilder = Callable[[list[Any]], str]


class SkillsPromptMiddleware(AgentMiddleware):
    """技能提示词装配中间件。

    这个中间件不再做“简单追加一段 prompt”，
    而是先选择命中的技能，再调用统一 prompt builder
    一次性重建最终的 system prompt。
    """

    def __init__(
        self,
        registry: SkillRegistry,
        *,
        prompt_builder: PromptBuilder | None = None,
        fallback_prompt: str = "",
        max_skills: int = 3,
    ) -> None:
        """初始化技能提示词中间件。"""
        super().__init__()
        self.registry = registry
        self.prompt_builder = prompt_builder
        self.fallback_prompt = fallback_prompt
        self.max_skills = max_skills

    def _resolve_messages(self, request: ModelRequest) -> list[Any]:
        """从请求里提取消息列表。"""
        messages = list(getattr(request, "messages", []) or [])
        state = getattr(request, "state", {}) or {}
        if not messages and isinstance(state, dict):
            messages = list(state.get("messages", []) or [])
        return messages

    def _build_prompt(self, request: ModelRequest) -> str:
        """构建最终 system prompt。"""
        if self.prompt_builder is not None:
            messages = self._resolve_messages(request)
            return self.prompt_builder(messages)

        catalog_prompt = self.registry.build_catalog_prompt()
        base_prompt = request.system_prompt or self.fallback_prompt or ""
        if catalog_prompt and base_prompt:
            return f"{base_prompt}\n\n{catalog_prompt}"
        return catalog_prompt or base_prompt

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Any],
    ) -> Any:
        """同步模式下写回统一装配后的 system prompt。"""
        prompt = self._build_prompt(request)
        next_request = request.override(system_message=SystemMessage(content=prompt))
        return handler(next_request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[Any]],
    ) -> Any:
        """异步模式下写回统一装配后的 system prompt。"""
        prompt = self._build_prompt(request)
        next_request = request.override(system_message=SystemMessage(content=prompt))
        return await handler(next_request)


def create_skills_prompt_middleware(
    registry: SkillRegistry,
    *,
    prompt_builder: PromptBuilder | None = None,
    fallback_prompt: str = "",
    max_skills: int = 3,
) -> Any:
    """创建按当前消息动态装配 prompt 的中间件。"""
    return SkillsPromptMiddleware(
        registry,
        prompt_builder=prompt_builder,
        fallback_prompt=fallback_prompt,
        max_skills=max_skills,
    )
