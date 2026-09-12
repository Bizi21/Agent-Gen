"""Agent core: plan -> (retrieve) -> act -> answer.

The agent retrieves relevant knowledge from the second brain, then runs the
LLM loop with tools available. With the offline mock LLM, the answer echoes
the retrieved knowledge, which is what lets golden retrieval tasks pass once
the right note has been learned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .gateway.base import LLM, Message, ToolCall
from .memory.store import Memory
from .tools import TOOLS, ToolContext, execute, tool_schemas
from .vault import Vault

KNOWLEDGE_MARKER = "KNOWLEDGE:"
TASK_MARKER = "TASK:"


@dataclass
class RunResult:
    answer: str
    trace: List[Dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    retrieved_notes: List[str] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        config: Config,
        llm: LLM,
        vault: Vault,
        memory: Memory,
        system_prompt_path: Optional[Path] = None,
    ):
        self.config = config
        self.llm = llm
        self.vault = vault
        self.memory = memory
        self.system_prompt_path = system_prompt_path or (config.brain_dir / "prompt" / "system.md")

    # -- knowledge -------------------------------------------------------- #
    def _system_prompt(self) -> str:
        if self.system_prompt_path.is_file():
            return self.system_prompt_path.read_text(encoding="utf-8")
        return "You are Agent-Gen, a self-improving AI agent with a second brain."

    def _retrieve(self, task: str, top_k: int = 5) -> str:
        results = self.vault.search(task, top_k=top_k)
        if not results:
            return ""
        blocks = [f"[{note.relpath}] {note.body}" for note, _ in results]
        return "\n\n".join(blocks)

    def _compose_user(self, task: str, context: str) -> str:
        ctx = context or "(none)"
        return f"{KNOWLEDGE_MARKER}\n{ctx}\n\n{TASK_MARKER}\n{task}"

    # -- run -------------------------------------------------------------- #
    def run(self, task: str, max_steps: Optional[int] = None) -> RunResult:
        limit = max_steps if max_steps is not None else self.config.max_steps
        limit = limit if (limit and limit > 0) else 8

        context = self._retrieve(task)
        retrieved = [n for n in [self._top_note_title(task)] if n]

        messages: List[Message] = [
            Message(role="system", content=self._system_prompt()),
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
                    result = execute(tc.name, tc.arguments, self._ctx())
                    trace.append({"tool": tc.name, "args": tc.arguments, "result": result[:500]})
                    messages.append(Message(role="tool", content=result, tool_call_id=tc.id))
                steps += 1
                continue
            answer = resp.content
            break

        if not answer:
            answer = "I could not produce an answer."

        self.memory.log(
            "task",
            {"task": task, "answer": answer, "steps": steps, "retrieved": retrieved},
        )
        return RunResult(answer=answer, trace=trace, steps=steps, retrieved_notes=retrieved)

    def _top_note_title(self, task: str) -> Optional[str]:
        results = self.vault.search(task, top_k=1)
        return results[0][0].title if results else None

    def _ctx(self) -> ToolContext:
        return ToolContext(vault=self.vault, memory=self.memory, root=self.config.root)
