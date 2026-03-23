"""图式入口与部署辅助。"""

from __future__ import annotations

from typing import Any

from hnk_agent.config import AgentConfig
from hnk_agent.session import SessionManager


async def create_agent_from_config(
    config: AgentConfig,
    *,
    conversation_id: str = "graph-session",
) -> Any:
    """根据配置创建一个可调用 agent。"""
    session = SessionManager.get_session(
        conversation_id,
        config=config,
    )
    return await session.get_agent()


def create_workflow_factory() -> Any:
    """返回一个基于 LangGraph 的工作流构造函数。

    这里使用工厂函数而不是模块导入时直接构建，
    这样可以避免在缺少 langgraph 依赖时影响普通模块导入。
    """
    try:
        from langgraph.graph import END, START, MessagesState, StateGraph
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Building a LangGraph workflow requires langgraph to be installed"
        ) from exc

    def build(config: AgentConfig, *, conversation_id: str = "langgraph-deployment") -> Any:
        """构建一个 LangGraph workflow。"""

        async def hnk_node(state: MessagesState) -> dict[str, Any]:
            agent = await create_agent_from_config(
                config,
                conversation_id=conversation_id,
            )
            return await agent.ainvoke(state)

        workflow = StateGraph(MessagesState)
        workflow.add_node("hnk", hnk_node)
        workflow.add_edge(START, "hnk")
        workflow.add_edge("hnk", END)
        return workflow.compile()

    return build
