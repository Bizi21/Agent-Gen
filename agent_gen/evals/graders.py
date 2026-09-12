"""Graders: decide whether an agent answer passes a task."""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple

from .suite import Task


def grade(task: Task, answer: str) -> Tuple[bool, float, str]:
    """Return (passed, score 0..1, detail)."""
    answer = answer or ""
    expected = task.expected or ""

    if task.grader == "exact":
        ok = answer.strip().lower() == expected.strip().lower()
        return ok, 1.0 if ok else 0.0, f"exact match (expected {expected!r})"

    if task.grader == "regex":
        pattern = task.grader_kwargs.get("pattern", expected)
        try:
            ok = re.search(pattern, answer, re.IGNORECASE) is not None
        except re.error as exc:
            return False, 0.0, f"bad regex: {exc}"
        return ok, 1.0 if ok else 0.0, f"regex {pattern!r}"

    if task.grader == "llm_judge":
        return False, 0.0, "llm_judge grading not available offline"

    # default: contains
    ok = expected.strip().lower() in answer.lower()
    return ok, 1.0 if ok else 0.0, f"contains {expected!r}"


def is_learnable(task: Task) -> bool:
    """Whether a failed task can be turned into a knowledge note."""
    return task.grader in ("contains", "exact", "regex") and bool(task.expected)
