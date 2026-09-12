"""Skills: reusable capabilities the agent self-selects.

A skill is a small JSON spec (name, description, keywords, prompt, tools)
stored in ``brain/skills/*.json``. The agent scores skills against the current
task and activates the best matches — its own "self decision" of how to work.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_skills(skills_dir: Path) -> List[Dict[str, Any]]:
    skills: List[Dict[str, Any]] = []
    if not skills_dir.is_dir():
        return skills
    for f in sorted(skills_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("name"):
                skills.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return skills


def select_skills(
    task: str,
    skills: List[Dict[str, Any]],
    max_skills: int = 3,
) -> List[Dict[str, Any]]:
    """Pick skills whose keywords appear in the task, best matches first."""
    text = task.lower()
    scored: List[tuple] = []
    for s in skills:
        score = sum(1 for kw in s.get("keywords", []) if kw.lower() in text)
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda pair: -pair[0])
    return [s for _, s in scored[:max_skills]]
