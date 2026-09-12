"""The improvement loop: evaluate -> reflect -> propose -> gate -> apply -> commit.

Offline-safe: reflection and proposal are built deterministically from the
eval failures, so the loop genuinely improves (learns knowledge notes) even
with the mock LLM. When a real provider is configured, its output is attached
to the reflection as extra reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agent import Agent
from ..config import Config
from ..evals.graders import is_learnable
from ..evals.harness import EvalResult, render_scorecard, run_suite, scorecard
from ..evals.suite import Task
from ..vault import Vault, slugify
from . import gitx


@dataclass
class Reflection:
    task_id: str
    root_cause: str
    reasoning: str = ""


@dataclass
class Proposal:
    notes: List[Dict[str, Any]] = field(default_factory=list)
    prompt_patch: str = ""
    summary: str = ""


# --------------------------------------------------------------------------- #
# reflect
# --------------------------------------------------------------------------- #
def reflect(failures: List[EvalResult], llm=None) -> List[Reflection]:
    reflections: List[Reflection] = []
    for r in failures:
        root_cause = (
            f"No knowledge note exists for '{r.task.question}' "
            f"(answer was {r.answer[:80]!r}, expected contains {r.task.expected!r})."
        )
        reasoning = ""
        if llm is not None:
            try:
                prompt = (
                    "You are reflecting on a failed eval task.\n"
                    f"Task: {r.task.question}\n"
                    f"Expected: {r.task.expected}\n"
                    f"Got: {r.answer[:300]}\n"
                    "Explain the root cause in one sentence."
                )
                reasoning = llm.complete(prompt)
            except Exception as exc:  # noqa: BLE001
                reasoning = f"(llm reflection unavailable: {exc})"
        reflections.append(Reflection(task_id=r.task.id, root_cause=root_cause, reasoning=reasoning))
    return reflections


# --------------------------------------------------------------------------- #
# propose
# --------------------------------------------------------------------------- #
def propose(failures: List[EvalResult], reflections: List[Reflection], vault: Vault) -> Proposal:
    notes: List[Dict[str, Any]] = []
    patch_lines: List[str] = []
    seen: set = set()

    for r, ref in zip(failures, reflections):
        if not is_learnable(r.task):
            continue
        # dedupe: don't re-propose a note that already exists
        if r.task.id in seen:
            continue
        seen.add(r.task.id)

        filename = f"lesson-{slugify(r.task.id)}.md"
        if (vault.path / "10-notes" / filename).exists():
            continue

        body = (
            f"**Question:** {r.task.question}\n\n"
            f"**Answer:** {r.task.expected}\n\n"
            f"**Category:** {r.task.category}\n\n"
            f"**Why:** {ref.root_cause}"
        )
        notes.append({
            "title": f"Lesson: {r.task.question}",
            "body": body,
            "folder": "10-notes",
            "filename": filename,
            "tags": ["lesson", r.task.category],
            "meta": {"source": "self-improvement", "language": r.task.language},
        })
        patch_lines.append(f"- {r.task.question} -> {r.task.expected}")

    summary = f"{len(notes)} new lesson note(s), {len(patch_lines)} prompt bullet(s)"
    return Proposal(notes=notes, prompt_patch="\n".join(patch_lines), summary=summary)


# --------------------------------------------------------------------------- #
# gate / apply
# --------------------------------------------------------------------------- #
def gate(proposal: Proposal, config: Config) -> bool:
    """Prompt/knowledge edits auto-apply. Code/config edits would require approval."""
    if not config.allow_self_improve:
        return False
    return bool(proposal.notes or proposal.prompt_patch)


def apply(proposal: Proposal, vault: Vault, system_prompt_path: Path) -> List[Path]:
    changed: List[Path] = []
    for spec in proposal.notes:
        p = vault.write_note(
            title=spec["title"],
            body=spec["body"],
            folder=spec.get("folder", "10-notes"),
            filename=spec.get("filename"),
            tags=spec.get("tags"),
            meta=spec.get("meta"),
        )
        changed.append(p)
    if proposal.prompt_patch:
        sp = system_prompt_path
        existing = sp.read_text(encoding="utf-8") if sp.is_file() else ""
        if "## Learned lessons" not in existing:
            existing = existing.rstrip() + "\n\n## Learned lessons\n"
        new_lines = []
        for line in proposal.prompt_patch.splitlines():
            if line and line not in existing:
                new_lines.append(line)
        if new_lines:
            existing = existing.rstrip() + "\n" + "\n".join(new_lines) + "\n"
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(existing, encoding="utf-8")
            changed.append(sp)
    return changed


# --------------------------------------------------------------------------- #
# the loop
# --------------------------------------------------------------------------- #
def run_improve(
    agent: Agent,
    tasks: List[Task],
    config: Config,
    vault: Vault,
    system_prompt_path: Path,
    *,
    max_rounds: int = 3,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "rounds": [],
        "commits": [],
        "rejections": [],
        "final_scorecard": None,
    }

    for rnd in range(1, max_rounds + 1):
        results = run_suite(agent, tasks)
        before = scorecard(results)
        failures = [r for r in results if not r.passed]

        if not failures:
            report["final_scorecard"] = before
            break

        reflections = reflect(failures)
        proposal = propose(failures, reflections, vault)

        if not gate(proposal, config):
            report["rejections"].append({"round": rnd, "reason": "gate denied"})
            break
        if not proposal.notes and not proposal.prompt_patch:
            report["rejections"].append({"round": rnd, "reason": "nothing to propose"})
            break

        changed = apply(proposal, vault, system_prompt_path)

        # re-evaluate on the changed brain
        results2 = run_suite(agent, tasks)
        after = scorecard(results2)

        rel_paths = [str(p.relative_to(config.root)) for p in changed]
        round_info = {
            "round": rnd,
            "before": before.passed,
            "after": after.passed,
            "notes": [n["filename"] for n in proposal.notes],
            "changed": rel_paths,
        }

        if after.passed >= before.passed and after.passed > before.passed:
            sha = gitx.commit(
                config.root, rel_paths,
                f"improve(brain): learn {len(proposal.notes)} lesson(s) "
                f"({before.passed}/{before.total} -> {after.passed}/{after.total})",
            )
            round_info["committed"] = sha
            report["commits"].append(sha)
        elif after.passed == before.passed and not proposal.notes:
            # nothing changed, nothing to keep
            gitx.discard(config.root, changed)
            round_info["committed"] = None
        else:
            # regression or no gain: revert
            gitx.discard(config.root, changed)
            round_info["committed"] = None
            report["rejections"].append({"round": rnd, "reason": "no improvement/regression"})

        report["rounds"].append(round_info)
        report["final_scorecard"] = after

    return report


def render_report(report: Dict[str, Any]) -> str:
    lines = ["Improvement report", "-" * 40]
    for r in report["rounds"]:
        lines.append(
            f"round {r['round']}: {r['before']} -> {r['after']} "
            f"(notes: {', '.join(r['notes']) or 'none'}) "
            f"{'committed ' + str(r['committed'])[:8] if r.get('committed') else 'reverted'}"
        )
    if report["rejections"]:
        lines.append("rejections: " + "; ".join(
            f"round {x['round']} ({x['reason']})" for x in report["rejections"]
        ))
    if report["final_scorecard"]:
        lines.append("")
        lines.append(render_scorecard(report["final_scorecard"]))
    return "\n".join(lines)
