"""Command-line interface.

Usage::

    python -m agent_gen init
    python -m agent_gen eval
    python -m agent_gen improve
    python -m agent_gen run "your task"
    python -m agent_gen chat
    python -m agent_gen ingest <url-or-file>
    python -m agent_gen graph
    python -m agent_gen ui
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .agent import Agent
from .bootstrap import ensure_brain
from .config import Config
from .evals.harness import render_scorecard, run_suite, scorecard
from .evals.suite import DEFAULT_SUITE
from .gateway.registry import LLMPool
from .improve.loop import render_report, run_improve
from .memory.store import Memory
from .vault import Vault


def build_runtime(config: Config):
    """Construct (llm_pool, vault, memory, agent) for a config."""
    ensure_brain(config)
    pool = LLMPool(config)
    vault = Vault(config.vault_path)
    memory = Memory(config.memory_path)
    agent = Agent(config, pool.get("chat"), vault, memory)
    return pool, vault, memory, agent


def cmd_init(config: Config) -> int:
    ensure_brain(config)
    print(f"Brain ready at {config.brain_dir}")
    print(f"Vault ready at {config.vault_path}")
    return 0


def cmd_eval(config: Config) -> int:
    _, _, _, agent = build_runtime(config)
    results = run_suite(agent, DEFAULT_SUITE)
    card = scorecard(results)
    print(render_scorecard(card))
    return 0 if card.failures == [] else 1


def cmd_improve(config: Config) -> int:
    _, vault, _, agent = build_runtime(config)
    report = run_improve(
        agent, DEFAULT_SUITE, config, vault,
        config.brain_dir / "prompt" / "system.md",
    )
    print(render_report(report))
    return 0


def cmd_run(config: Config, task: str) -> int:
    _, _, _, agent = build_runtime(config)
    result = agent.run(task)
    print(result.answer)
    return 0


def cmd_chat(config: Config, session: str = "default") -> int:
    _, _, memory, agent = build_runtime(config)
    print(f"Agent-Gen chat ({config.autonomy} autonomy). Type /exit to quit.")
    for role, content in memory.history(session):
        print(f"{role}: {content}")
    while True:
        try:
            user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in {"/exit", "/quit"}:
            break
        memory.add_message(session, "user", user)
        result = agent.run(user)
        memory.add_message(session, "assistant", result.answer)
        print(f"\nAgent: {result.answer}")
    return 0


def cmd_ingest(config: Config, target: str) -> int:
    _, vault, _, _ = build_runtime(config)
    if target.startswith(("http://", "https://")):
        from .tools import _ingest_url, ToolContext
        ctx = ToolContext(vault=vault, memory=Memory(config.memory_path), root=config.root)
        print(_ingest_url(ctx, target))
    else:
        p = Path(target)
        if not p.is_file():
            print(f"ERROR: file not found: {target}", file=sys.stderr)
            return 1
        text = p.read_text(encoding="utf-8", errors="replace")
        out = vault.add_to_inbox(text, title=p.stem, source=str(p.resolve()))
        print(f"Ingested {len(text)} chars from {target} into {out.relative_to(vault.path)}")
    return 0


def cmd_graph(config: Config) -> int:
    _, vault, _, _ = build_runtime(config)
    g = vault.graph()
    print(f"{len(g['nodes'])} nodes, {len(g['edges'])} edges\n")
    for n in g["nodes"]:
        folder = n.get("folder", "")
        if folder == "tag":
            continue
        print(f"  [{folder}] {n['title']}  ({n['relpath']})")
    for e in g["edges"]:
        if e["kind"] != "link":
            continue
        print(f"  link: {e['source']} -> {e['target']}")
    return 0


def cmd_ui(config: Config) -> int:
    from .ui import serve
    serve(config)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-gen", description="Self-improving AI agent")
    parser.add_argument("--version", action="version", version=f"agent-gen {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="create the brain + vault structure")
    sub.add_parser("eval", help="run the eval suite and print a scorecard")
    sub.add_parser("improve", help="run the improvement loop")
    sub.add_parser("chat", help="interactive chat (CLI)")

    p_run = sub.add_parser("run", help="run one task")
    p_run.add_argument("task")

    p_ingest = sub.add_parser("ingest", help="ingest a URL or file into the vault")
    p_ingest.add_argument("target")

    sub.add_parser("graph", help="print the vault knowledge graph")
    sub.add_parser("ui", help="open the desktop window (web UI)")
    sub.add_parser("start", help="open the desktop window (same as ui)")

    args = parser.parse_args(argv)
    config = Config.load()
    if not args.cmd:
        # Default: one simple command opens the chat window (the first screen).
        return cmd_ui(config)

    if args.cmd == "init":
        return cmd_init(config)
    if args.cmd == "eval":
        return cmd_eval(config)
    if args.cmd == "improve":
        return cmd_improve(config)
    if args.cmd == "run":
        return cmd_run(config, args.task)
    if args.cmd == "chat":
        return cmd_chat(config)
    if args.cmd == "ingest":
        return cmd_ingest(config, args.target)
    if args.cmd == "graph":
        return cmd_graph(config)
    if args.cmd in ("ui", "start"):
        return cmd_ui(config)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
