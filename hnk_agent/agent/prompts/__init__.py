"""提示词模板统一导出。"""

from hnk_agent.agent.prompts.assembly import (
    build_general_subagent_system_prompt,
    build_main_agent_system_prompt,
)
from hnk_agent.agent.prompts.loader import (
    PromptLoader,
    get_loader,
    init_loader,
    reset_loader,
)

__all__ = [
    "PromptLoader",
    "build_general_subagent_system_prompt",
    "build_main_agent_system_prompt",
    "get_loader",
    "init_loader",
    "reset_loader",
]
