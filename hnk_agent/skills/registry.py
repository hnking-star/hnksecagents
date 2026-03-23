"""技能注册中心。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def _tokenize(text: str) -> list[str]:
    """把文本切成简单 token。"""
    return [
        token
        for token in re.split(r"[^a-zA-Z0-9_]+", text.lower())
        if len(token) >= 2
    ]


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

    @property
    def search_text(self) -> str:
        """返回用于匹配的搜索文本。"""
        return "\n".join(
            part
            for part in [
                self.name,
                self.description,
                self.normalized_content[:4000],
            ]
            if part
        )

    def match_score(self, query: str) -> int:
        """计算当前技能对查询文本的匹配分数。"""
        normalized_query = query.strip().lower()
        if not normalized_query:
            return 0

        query_tokens = set(_tokenize(normalized_query))
        if not query_tokens:
            return 0

        name_tokens = set(_tokenize(self.name))
        desc_tokens = set(_tokenize(self.description))
        content_tokens = set(_tokenize(self.search_text))

        score = 0
        skill_name_text = self.name.replace("-", " ").replace("_", " ").lower()
        if skill_name_text and skill_name_text in normalized_query:
            score += 20

        score += len(query_tokens & name_tokens) * 5
        score += len(query_tokens & desc_tokens) * 3
        score += len(query_tokens & content_tokens)
        return score


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

    def match(self, query: str, *, limit: int = 3) -> list[SkillDocument]:
        """按查询文本匹配最相关的技能。"""
        scored = [
            (skill.match_score(query), skill)
            for skill in self.skills
        ]
        scored = [
            item
            for item in scored
            if item[0] > 0
        ]
        scored.sort(
            key=lambda item: (-item[0], item[1].name),
        )
        return [skill for _, skill in scored[:limit]]

    def build_prompt(self, skills: list[SkillDocument] | None = None) -> str:
        """把技能渲染成可拼接到 system prompt 的文本。"""
        target_skills = skills if skills is not None else self.skills
        if not target_skills:
            return ""

        sections = [
            "技能规则：",
            "当任务明显匹配某个技能时，优先遵循对应技能说明。",
            "如果多个技能同时相关，可以组合使用，但保持最小必要集合。",
        ]

        for skill in target_skills:
            header = f"### 技能：{skill.name}"
            meta = f"来源：{skill.source} | 路径：{skill.path}"
            body = skill.normalized_content or "（技能内容为空）"
            sections.extend(["", header, meta, body])

        return "\n".join(sections).strip()

    def build_prompt_for_query(self, query: str, *, limit: int = 3) -> str:
        """按查询文本只渲染命中的技能 prompt。"""
        matched = self.match(query, limit=limit)
        return self.build_prompt(matched)

    def build_guidance_prompt(self) -> str:
        """返回轻量的技能使用说明。"""
        if self.is_empty():
            return ""
        return (
            "技能系统：当前项目已加载本地技能。"
            "当系统在本轮注入匹配技能后，优先遵循对应技能说明。"
        )
