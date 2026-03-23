"""技能层统一导出。"""

from __future__ import annotations

__all__ = [
    "SkillDocument",
    "SkillRegistry",
    "create_skills_prompt_middleware",
    "load_skills_from_dir",
    "load_skills_from_dirs",
]


def __getattr__(name: str):
    """按需导出技能层对象，避免循环导入。"""
    if name in {"SkillDocument", "SkillRegistry"}:
        from hnk_agent.skills.registry import SkillDocument, SkillRegistry

        return {
            "SkillDocument": SkillDocument,
            "SkillRegistry": SkillRegistry,
        }[name]

    if name in {"load_skills_from_dir", "load_skills_from_dirs"}:
        from hnk_agent.skills.loader import load_skills_from_dir, load_skills_from_dirs

        return {
            "load_skills_from_dir": load_skills_from_dir,
            "load_skills_from_dirs": load_skills_from_dirs,
        }[name]

    if name == "create_skills_prompt_middleware":
        from hnk_agent.skills.middleware import create_skills_prompt_middleware

        return create_skills_prompt_middleware

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
