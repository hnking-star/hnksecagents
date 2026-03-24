"""Agent 模块统一导出。"""

__all__ = ["HNKAgent"]

from hnk_agent.agent.agent import HNKAgent


def __getattr__(name: str):
    """按需加载重量级对象，避免无关依赖在导入期就被拉起。"""
    if name == "HNKAgent":
        from hnk_agent.agent.agent import HNKAgent

        return HNKAgent
    raise AttributeError(name)
