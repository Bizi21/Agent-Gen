"""Eval harness: run a suite, produce results + a scorecard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..agent import Agent
from .graders import grade
from .suite import Task


@dataclass
class EvalResult:
    task: Task
    answer: str
    passed: bool
    score: float
    detail: str
    steps: int = 0


@dataclass
class Scorecard:
    total: int = 0
    passed: int = 0
    by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)
    failures: List[EvalResult] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return (self.passed / self.total) if self.total else 0.0


def run_suite(agent: Agent, tasks: List[Task]) -> List[EvalResult]:
    results: List[EvalResult] = []
    for task in tasks:
        run = agent.run(task.question)
        ok, score, detail = grade(task, run.answer)
        results.append(EvalResult(task=task, answer=run.answer, passed=ok,
                                  score=score, detail=detail, steps=run.steps))
    return results


def scorecard(results: List[EvalResult]) -> Scorecard:
    card = Scorecard(total=len(results))
    for r in results:
        if r.passed:
            card.passed += 1
        cat = r.task.category
        bucket = card.by_category.setdefault(cat, {"passed": 0, "total": 0})
        bucket["total"] += 1
        if r.passed:
            bucket["passed"] += 1
        if not r.passed:
            card.failures.append(r)
    return card


def render_scorecard(card: Scorecard) -> str:
    lines = [
        "=" * 56,
        f"  SCORECARD   {card.passed}/{card.total} passed  ({card.ratio:.0%})",
        "=" * 56,
    ]
    for cat in sorted(card.by_category):
        b = card.by_category[cat]
        lines.append(f"  {cat:<14} {b['passed']}/{b['total']}")
    if card.failures:
        lines.append("-" * 56)
        lines.append("  FAILURES:")
        for r in card.failures:
            got = r.answer.replace("\n", " ")[:70]
            lines.append(f"  - {r.task.id} [{r.task.category}] {r.detail}")
            lines.append(f"      got: {got}")
    lines.append("=" * 56)
    return "\n".join(lines)
