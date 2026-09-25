"""Skill files for Nexa's agents (progressive disclosure).

Each skill is `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`).
Agents see the index (name + description) in their system prompt and load the full
instructions with the read-only `get_skill` tool when a skill applies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str


@lru_cache(maxsize=1)
def load_skills() -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER.match(text)
        meta = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line) if match else {}
        name = meta.get("name", path.parent.name).strip()
        skills[name] = Skill(name=name, description=meta.get("description", "").strip(), body=text[match.end():].strip() if match else text)
    return skills


def skills_index() -> str:
    return "\n".join(f"- {s.name}: {s.description}" for s in load_skills().values())
