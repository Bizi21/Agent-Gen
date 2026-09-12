---
title: Agent-Gen
created: 2026-09-12
tags: [agent-gen, index]
language: en
---
# Agent-Gen

Agent-Gen is a self-improving AI agent.

It ingests external knowledge (GitHub, websites, feeds, images, scratch notes),
improves its own prompt, knowledge, and code, and is controlled through a chat
interface.

- The eval command is `/eval` — it runs the eval suite and shows a scorecard.
- The improve command is `/improve` — it runs the improvement loop.
- Long-term knowledge is stored in an **Obsidian** vault (the second brain).
- The knowledge graph ("graphify") shows notes as [[Agent-Gen]] nodes and links as edges.
- In the config, `0` means unlimited.
