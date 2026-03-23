"""技能注册中心。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillDocument:
    """单个技能文档。"""

    name: str
    path: Path
    content: str
    source: str = "project"
    description: str = ""

    @property
    def normalized_content(self) -> str:
        """返回去掉首尾空白后的技能内容。"""
        return self.content.strip()


@dataclass
class SkillRegistry:
    """技能注册中心。"""

    skills: list[SkillDocument] = field(default_factory=list)

    def add(self, skill: SkillDocument) -> None:
        """添加技能。"""
        self.skills.append(skill)

    def extend(self, skills: list[SkillDocument]) -> None:
        """批量添加技能。"""
        self.skills.extend(skills)

    def is_empty(self) -> bool:
        """判断当前是否没有技能。"""
        return not self.skills

    def names(self) -> list[str]:
        """返回全部技能名称。"""
        return [skill.name for skill in self.skills]

    def build_prompt(self) -> str:
        """把全部技能渲染成可拼接到 system prompt 的文本。"""
        if self.is_empty():
            return ""

        sections = [
            "技能规则：",
            "当任务明显匹配某个技能时，优先遵循对应技能说明。",
            "如果多个技能同时相关，可以组合使用，但保持最小必要集合。",
        ]

        for skill in self.skills:
            header = f"### 技能：{skill.name}"
            meta = f"来源：{skill.source} | 路径：{skill.path}"
            body = skill.normalized_content or "（技能内容为空）"
            sections.extend(["", header, meta, body])

        return "\n".join(sections).strip()
