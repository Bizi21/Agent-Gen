"""Agent core: self-decide mode -> plan -> knowledge -> skills/tools -> answer.

``run_stream`` emits live events so the window can show the agent *working*:

    mode -> skill -> think -> knowledge -> tool_start/end -> answer -> done

With the offline mock LLM, plain questions echo the retrieved knowledge (which
is what makes golden retrieval tasks pass once a note has been learned), while
commands containing action verbs (search/find/list/ingest) trigger real tool
calls so the loop's tools are exercised live too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import Config
from .gateway.base import LLM, Message
from .memory.store import Memory
from .skills import load_skills, select_skills
from .tools import TOOLS, ToolContext, execute, tool_schemas
from .vault import Vault

KNOWLEDGE_MARKER = "KNOWLEDGE:"
TASK_MARKER = "TASK:"

EventEmitter = Callable[[Dict[str, Any]], None]


@dataclass
class RunResult:
    answer: str
    trace: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    retrieved_notes: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    plan: str = ""


class Agent:
    def __init__(
        self,
        config: Config,
        llm: LLM,
        vault: Vault,
        memory: Memory,
        system_prompt_path: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
    ):
        self.config = config
        self.llm = llm
        self.vault = vault
        self.memory = memory
        self.system_prompt_path = system_prompt_path or (config.brain_dir / "prompt" / "system.md")
        self.skills_dir = skills_dir or (config.brain_dir / "skills")
        self.skills = load_skills(self.skills_dir)

    # -- self decision ---------------------------------------------------- #
    def _select_skills(self, task: str) -> List[Dict[str, Any]]:
        return select_skills(task, self.skills)

    def _plan(self, task: str, active_skills: List[Dict[str, Any]]) -> str:
        names = ", ".join(s["name"] for s in active_skills) or "none"
        return (
            f"Mode: {self.config.autonomy}. Skills: {names}. "
            "Plan: (1) retrieve knowledge from the second brain, "
            "(2) use tools/skills if needed, (3) answer."
        )

    def _system_prompt(self, active_skills: Optional[List[Dict[str, Any]]] = None) -> str:
        base = ""
        if self.system_prompt_path.is_file():
            base = self.system_prompt_path.read_text(encoding="utf-8")
        else:
            base = "You are Agent-Gen, a self-improving AI agent with a second brain."
        if active_skills:
            lines = [
                f"- **{s['name']}**: {s.get('prompt') or s.get('description', '')}"
                for s in active_skills
            ]
            base = base.rstrip() + "\n\n## Active skills\n" + "\n".join(lines) + "\n"
        return base

    # -- knowledge -------------------------------------------------------- #
    def _retrieve(self, task: str, top_k: int = 5):
        return self.vault.search(task, top_k=top_k)

    def _compose_user(self, task: str, context: str) -> str:
        ctx = context or "(none)"
        return f"{KNOWLEDGE_MARKER}\n{ctx}\n\n{TASK_MARKER}\n{task}"

    # -- run -------------------------------------------------------------- #
    def run_stream(
        self,
        task: str,
        max_steps: Optional[int] = None,
        emit: Optional[EventEmitter] = None,
    ) -> RunResult:
        emit = emit or (lambda event: None)
        limit = max_steps if max_steps is not None else self.config.max_steps
        limit = limit if (limit and limit > 0) else 8

        # 1) self-decide: mode + skills + plan
        active_skills = self._select_skills(task)
        plan = self._plan(task, active_skills)
        emit({"type": "mode", "value": self.config.autonomy})
        for s in active_skills:
            emit({"type": "skill", "name": s["name"], "description": s.get("description", "")})
        emit({"type": "think", "text": plan})

        # 2) retrieve knowledge from the second brain
        results = self._retrieve(task)
        notes = [n.relpath for n, _ in results]
        context = "\n\n".join(f"[{n.relpath}] {n.body}" for n, _ in results)
        emit({"type": "knowledge", "notes": notes})

        # 3) act: LLM loop with tools/skills
        messages: List[Message] = [
            Message(role="system", content=self._system_prompt(active_skills)),
            Message(role="user", content=self._compose_user(task, context)),
        ]
        trace: List[Dict[str, Any]] = []
        answer = ""
        steps = 0

        while steps < limit:
            resp = self.llm.chat(messages, tools=tool_schemas())
            if resp.tool_calls:
                messages.append(Message(role="assistant", content="", tool_calls=resp.tool_calls))
                for tc in resp.tool_calls:
                    emit({"type": "tool_start", "name": tc.name, "args": tc.arguments})
                    result = execute(tc.name, tc.arguments, self._ctx())
                    emit({"type": "tool_end", "name": tc.name, "result": result[:500]})
                    trace.append({"tool": tc.name, "args": tc.arguments, "result": result[:500]})
                    messages.append(Message(role="tool", content=result, tool_call_id=tc.id))
                steps += 1
                continue
            answer = resp.content
            break

        if not answer:
            answer = "I could not produce an answer."

        emit({"type": "answer", "text": answer})
        emit({"type": "done", "steps": steps, "skills": [s["name"] for s in active_skills]})

        self.memory.log(
            "task",
            {"task": task, "answer": answer, "steps": steps, "retrieved": notes,
             "skills": [s["name"] for s in active_skills]},
        )
        return RunResult(
            answer=answer,
            trace=trace,
            steps=steps,
            retrieved_notes=notes,
            skills=[s["name"] for s in active_skills],
            plan=plan,
        )

    def run(self, task: str, max_steps: Optional[int] = None) -> RunResult:
        events: List[Dict[str, Any]] = []
        result = self.run_stream(task, max_steps=max_steps, emit=events.append)
        result.events = events
        return result

    def _ctx(self) -> ToolContext:
        return ToolContext(vault=self.vault, memory=self.memory, root=self.config.root)
