"""技能加载器。"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from hnk_agent.skills.registry import SkillDocument, SkillRegistry


def _parse_frontmatter(content: str) -> dict[str, str]:
    """解析技能文档顶部的 YAML frontmatter。"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not match:
        return {}

    raw_frontmatter = match.group(1)
    try:
        parsed = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError:
        return {}

    if isinstance(parsed, dict):
        return {
            str(key): str(value).strip()
            for key, value in parsed.items()
            if value is not None
        }
    return {}


def _infer_description(content: str) -> str:
    """从技能文本中提取简短描述。"""
    for line in content.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if normalized == "---":
            continue
        if ":" in normalized and not normalized.startswith("#"):
            key = normalized.split(":", 1)[0].strip().lower()
            if key in {"name", "description", "license", "compatibility"}:
                continue
        if normalized.startswith("#"):
            continue
        return normalized[:120]
    return ""


def _discover_skill_files(skill_dir: Path) -> list[Path]:
    """发现目录下全部技能文档。"""
    if not skill_dir.exists() or not skill_dir.is_dir():
        return []

    files = set(skill_dir.rglob("SKILL.md"))
    files.update(skill_dir.glob("*.md"))

    return sorted(
        file_path
        for file_path in files
        if file_path.is_file()
    )


def _build_skill_document(skill_file: Path, *, source: str) -> SkillDocument:
    """从文件构造技能对象。"""
    content = skill_file.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(content)

    if skill_file.name == "SKILL.md" and skill_file.parent.name:
        skill_name = frontmatter.get("name") or skill_file.parent.name
    else:
        skill_name = frontmatter.get("name") or skill_file.stem

    description = frontmatter.get("description") or _infer_description(content)

    return SkillDocument(
        name=skill_name,
        path=skill_file,
        content=content,
        source=source,
        description=description,
    )


def load_skills_from_dir(skill_dir: str | Path, *, source: str = "project") -> SkillRegistry:
    """从单个目录加载技能。"""
    directory = Path(skill_dir).expanduser().resolve()
    registry = SkillRegistry()

    for skill_file in _discover_skill_files(directory):
        registry.add(_build_skill_document(skill_file, source=source))

    return registry


def load_skills_from_dirs(skill_dirs: list[str | Path]) -> SkillRegistry:
    """从多个目录加载技能，并自动去重。"""
    merged = SkillRegistry()
    seen_paths: set[Path] = set()

    for raw_dir in skill_dirs:
        directory = Path(raw_dir).expanduser().resolve()
        source = "user" if ".hnksecagents" in str(directory) else "project"
        partial = load_skills_from_dir(directory, source=source)
        for skill in partial.skills:
            if skill.path in seen_paths:
                continue
            seen_paths.add(skill.path)
            merged.add(skill)

    return merged
