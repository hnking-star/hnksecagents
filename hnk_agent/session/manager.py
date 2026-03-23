"""会话管理器。"""

from __future__ import annotations

from typing import Any

import structlog

from hnk_agent.session.session import Session

logger = structlog.get_logger(__name__)


class SessionManager:
    """管理多个会话实例。"""

    _sessions: dict[str, Session] = {}

    @classmethod
    def get_session(
        cls,
        conversation_id: str,
        model: Any,
        *,
        runtime: Any | None = None,
        tool_registry: Any | None = None,
        agent_options: dict[str, Any] | None = None,
        workspace_root: str | None = None,
    ) -> Session:
        """按会话 ID 获取或创建会话。"""
        if conversation_id not in cls._sessions:
            logger.info("creating_new_session", conversation_id=conversation_id)
            cls._sessions[conversation_id] = Session(
                conversation_id=conversation_id,
                model=model,
                runtime=runtime,
                tool_registry=tool_registry,
                agent_options=agent_options,
                workspace_root=workspace_root,
            )
        else:
            logger.debug("returning_existing_session", conversation_id=conversation_id)

        return cls._sessions[conversation_id]

    @classmethod
    async def cleanup_session(cls, conversation_id: str) -> None:
        """清理指定会话。"""
        if conversation_id in cls._sessions:
            session = cls._sessions[conversation_id]
            await session.cleanup()
            del cls._sessions[conversation_id]
            logger.info("session_removed", conversation_id=conversation_id)

    @classmethod
    async def cleanup_all(cls) -> None:
        """清理所有活动会话。"""
        logger.info("cleaning_up_all_sessions", count=len(cls._sessions))
        for conversation_id in list(cls._sessions.keys()):
            await cls.cleanup_session(conversation_id)
        logger.info("all_sessions_cleaned_up")

    @classmethod
    def get_active_sessions(cls) -> list[str]:
        """返回当前活动会话 ID 列表。"""
        return list(cls._sessions.keys())

    @classmethod
    def get_session_count(cls) -> int:
        """返回当前活动会话数。"""
        return len(cls._sessions)
