# Agent-Gen

A **self-improving AI agent** that:

- **Runs inside a desktop window** — agents panel, chat/work window, and a
  live knowledge graph of your **Second Brain** (an **Obsidian vault**).
- **Ingests** external knowledge (GitHub, websites, feeds, images, scratch
  notes) into the vault.
- **Improves its own prompt, knowledge, and code** through an
  *eval → reflect → propose → apply → commit* loop.
- **Works with any provider / any model, no hard limits**, long conversations,
  long context, full autonomy, and multiple languages.

Everything runs with **zero third-party dependencies** (Python stdlib only).

## Quickstart

```bash
# 1. (optional) configure providers — copy and edit .env
cp .env.example .env

# 2. create the brain + vault (idempotent)
python3 -m agent_gen init

# 3. run the eval suite
python3 -m agent_gen eval

# 4. run the self-improvement loop (the agent learns and commits)
python3 -m agent_gen improve

# 5. open the desktop window (web UI)
python3 -m agent_gen ui
```

> No API key? No problem. With no keys configured the agent automatically uses
> a built-in **offline mock LLM**, so `eval`, `improve`, `chat`, and the window
> all work end-to-end without any network or key. Add keys to `.env` to switch
> to real providers (OpenAI, Anthropic, Gemini, Mistral, Groq, DeepSeek,
> Ollama, or any OpenAI-compatible endpoint).

## Commands

```
init                    create the brain + vault
eval                    run the eval suite, print a scorecard
improve                 run the improvement loop (learn + commit)
run "task"              run a single task
chat                    interactive chat (REPL)
ingest <url|file>       capture external data into the vault
graph                   print the knowledge graph (notes + links)
ui                      open the desktop window (web UI)
```

## How self-improvement works (M1)

1. **Evaluate** — a golden task suite scores the agent.
2. **Reflect** — failures are turned into root-cause hypotheses.
3. **Propose** — the agent writes *lesson notes* into the vault (and can patch
   its own `brain/prompt/system.md`).
4. **Gate + apply** — prompt/knowledge edits auto-apply; code edits would
   require approval.
5. **Re-evaluate + commit** — the change is kept only if the score improves
   (no regression), and committed to git; otherwise it is reverted.

Real run from this repo: `2/6 → 6/6` in one round.

## Layout

```
agent_gen/            the agent (stdlib only)
  gateway/            LLM adapters: mock, openai-compatible, anthropic, google
  memory/             SQLite episodic + conversation memory
  evals/              task suite, graders, scorecard
  improve/            the improvement loop + git helpers
  vault.py            the second brain (Obsidian vault: notes, wikilinks, graph)
  tools.py            read/write/edit file, vault, ingest_url, remember, ...
  ui.py               the desktop window (web UI + live graph)
brain/                the versioned Brain (git-tracked)
  prompt/system.md    the agent's own instructions (it can edit these)
  config/agent.json   non-secret settings
  vault/              the Obsidian vault (your second brain)
tests/                stdlib unittest suite
docs/DESIGN.md        full design document + roadmap
```

## Tests

```bash
python3 -m unittest discover -t . -s tests
```

## Docs

See [`docs/DESIGN.md`](docs/DESIGN.md) for the complete architecture, the
improvement loop, autonomy levels, multilingual design, the second brain
(Obsidian + graph), and the roadmap.
