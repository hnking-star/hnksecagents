"""技能动态提示词中间件。"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import dynamic_prompt

from hnk_agent.skills.registry import SkillRegistry


def _message_text(message: Any) -> str:
    """尽量从消息对象中提取文本。"""
    if hasattr(message, "text"):
        text = getattr(message, "text")
        if isinstance(text, str):
            return text

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)

    return str(content)


def _latest_user_text(messages: list[Any]) -> str:
    """提取最近一条用户消息文本。"""
    for message in reversed(messages):
        message_type = getattr(message, "type", "")
        if message_type in {"human", "user"}:
            text = _message_text(message).strip()
            if text:
                return text
    return ""


def create_skills_prompt_middleware(
    registry: SkillRegistry,
    *,
    fallback_prompt: str = "",
    max_skills: int = 3,
) -> Any:
    """创建按当前消息动态注入技能 prompt 的中间件。"""

    @dynamic_prompt
    def skills_prompt(request) -> str:
        messages = list(getattr(request, "messages", []) or [])
        state = getattr(request, "state", {}) or {}
        if not messages and isinstance(state, dict):
            messages = list(state.get("messages", []) or [])

        query = _latest_user_text(messages)
        scoped_prompt = registry.build_prompt_for_query(query, limit=max_skills)

        base_prompt = request.system_prompt or fallback_prompt or ""
        if scoped_prompt:
            if base_prompt:
                return f"{base_prompt}\n\n{scoped_prompt}"
            return scoped_prompt

        return base_prompt

    return skills_prompt
