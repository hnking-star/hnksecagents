"""提示词层统一导出。"""

from hnk_agent.agent.prompts.assembly import (
    build_general_subagent_system_prompt,
    build_main_agent_system_prompt,
)
from hnk_agent.agent.prompts.general_subagent import build_general_subagent_prompt
from hnk_agent.agent.prompts.main_agent import build_main_agent_prompt

__all__ = [
    "build_general_subagent_prompt",
    "build_general_subagent_system_prompt",
    "build_main_agent_prompt",
    "build_main_agent_system_prompt",
]
