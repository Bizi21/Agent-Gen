"""Eval task definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    id: str
    category: str
    question: str
    expected: str
    grader: str = "contains"  # contains | exact | regex | llm_judge
    language: str = "en"
    grader_kwargs: Dict[str, Any] = field(default_factory=dict)


DEFAULT_SUITE: List[Task] = [
    # These two are answered by the seed note (brain/vault/10-notes/home.md).
    Task(
        id="t01",
        category="knowledge",
        language="en",
        question="What is the eval command in Agent-Gen?",
        expected="/eval",
    ),
    Task(
        id="t02",
        category="knowledge",
        language="en",
        question="Where does Agent-Gen store its long-term knowledge?",
        expected="Obsidian",
    ),
    # These are not in any note yet — the improvement loop should learn them.
    Task(
        id="t03",
        category="facts",
        language="en",
        question="What is the capital of France?",
        expected="Paris",
    ),
    Task(
        id="t04",
        category="facts",
        language="en",
        question="Who wrote the play Hamlet?",
        expected="Shakespeare",
    ),
    Task(
        id="t05",
        category="facts",
        language="en",
        question="What does HTML stand for?",
        expected="HyperText Markup Language",
    ),
    Task(
        id="t06",
        category="facts",
        language="en",
        question="What is the largest planet in the Solar System?",
        expected="Jupiter",
    ),
]
