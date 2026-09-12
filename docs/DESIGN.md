# Agent-Gen — Design Document

A self-improving AI agent that ingests external knowledge, improves its own
prompt, knowledge, and code, and runs inside a **desktop window** showing the
**agents**, a **chat/work window**, and a **Second Brain** backed by an
**Obsidian vault with a graph view** ("graphify"). It can use its own tools
and skills on its own initiative, works in multiple languages, and is
configured with **any provider / any model, no hard limits**, **long
conversations**, **long context**, and **full freedom to think and work**.

> Status: **Draft v4** — design phase. No code yet.
> The first milestone to build is the **eval + improvement loop** (M1);
> the window + second brain land in M2.

---

## 1. Vision

Build an agent that gets better *over time, by itself*:

- **Opens a nice window** — when the agent runs, a desktop window opens with
  the agents, a chat/work window, and the knowledge graph (Section 11).
- It **learns** from data it ingests — GitHub repos and links, websites,
  scraped pages, feeds (RSS/Atom), scratch notes, and pictures.
- It **improves its own code and files** — it can read, write, and edit its
  own tools and components, then validate them.
- It **improves its own prompt and knowledge** — based on measured results,
  not vibes.
- It **thinks in a Second Brain** — knowledge lives in an **Obsidian vault**
  (plain Markdown + wikilinks) with a **graph view**, so both the agent and
  the human share one living, linked brain (Section 12).
- It **uses its own tools and skills anytime, on its own initiative**
  ("self control") — it decides which capability to invoke and when, not only
  when the user explicitly commands it.
- It **knows multiple languages** — it speaks, reads, ingests, and reasons
  across languages (English + Hindi by default; more are configurable).
- It **is free to think and work** — any provider, any model, no hard limits,
  long-running conversations and context, and an autonomy level that lets it
  reason and act on its own (Section 9).
- It is **steered through chat** — the chat/work window where the user gives
  commands ("ingest this repo", "run the evals", "make yourself better at X")
  and just talks to it.

### 1.1 What "self-improving" means concretely here

The agent's identity is made of **versioned artifacts** (we call them
"the Brain"):

| Artifact | What it holds | How it improves |
|----------|---------------|-----------------|
| **Prompt** | System prompt, instructions, few-shot examples | Rewritten after reflection on failures |
| **Knowledge** | Second-brain notes (Obsidian Markdown) | New notes added; stale/wrong notes edited or removed |
| **Tools** | Definitions & code for the agent's capabilities | Code written/edited by the agent, validated by tests |
| **Memory** | Episodic log of tasks, outcomes, feedback | Appended automatically; distilled into notes |

The **unit of improvement is a versioned diff** (a git commit against the
Brain). Every change is measurable, reviewable, and reversible.

### 1.2 Non-goals (v1)

- No autonomous fine-tuning of model weights (that is a later, optional track).
- No forced limits on providers/models/conversation length — limits exist only
  where the user chooses to set them (see Sections 7–8).
- Not a general "AGI" — this is a task-oriented agent with a bounded,
  inspectable improvement loop. ("Bounded" = bounded by what *you* configure,
  not by hard-coded caps.)

---

## 2. Design Principles

1. **The self is data, not code.** The prompt, knowledge, tool schemas, and
   config live as plain files under version control. The agent can rewrite
   them like any other file. Hard-coded logic is minimized.
2. **Evals before self-improvement.** You cannot improve what you cannot
   measure. Every improvement must move a number (or at least not regress it).
3. **Model-agnostic and unlimited.** All LLM access goes through one interface;
   any number of providers and models can be added purely via config, with no
   hardcoded list or cap (Section 7).
4. **Long conversation, long context.** Conversations and context are
   persistent and effectively unbounded through compaction and retrieval, not
   silently truncated (Section 8).
5. **Plain-text second brain.** Knowledge is Markdown in an Obsidian vault —
   readable by humans, editable by the agent, renderable as a graph. No
   proprietary lock-in (Section 12).
6. **Sandbox everything that mutates.** Code the agent writes runs in a
   sandbox and must pass tests before it is merged into the live agent.
7. **Auditable and reversible.** Every Brain change is a git commit; any
   change can be diffed and rolled back.
8. **Autonomy as a dial, up to full freedom.** The agent chooses which tool or
   skill to use and when, by default; the dial goes all the way to **full** —
   self-directed reasoning, self-set goals, self-improvement (Section 9).
9. **Multilingual by default.** Every text path — chat, ingestion, notes,
   evals — is language-aware. Language is first-class metadata, not an
   afterthought.

---

## 3. System Architecture

```
                    ┌───────────────────────────────────────────────┐
                    │        DESKTOP WINDOW  (opens on run)         │
                    │  ┌───────────┬──────────────────┬───────────┐  │
                    │  │  AGENTS   │   CHAT / WORK    │  NOTES +  │  │
                    │  │  panel    │   window         │  GRAPH    │  │
                    │  └───────────┴──────────────────┴───────────┘  │
                    └────────────────────┬───────────────────────────┘
                                         │ commands / messages
                    ┌────────────────────▼───────────────────────────┐
                    │                 ORCHESTRATOR                   │
                    │   (decides: act / ingest / eval / reflect /    │
                    │    improve)                                    │
                    └───────┬───────────────┬───────────────┬────────┘
                            │               │               │
             ┌──────────────▼─────┐ ┌───────▼────────┐ ┌────▼────────────┐
             │     AGENT CORE     │ │  EVAL HARNESS  │ │   INGESTION     │
             │ (plan→choose skill→│ │ (run, score,   │ │   PIPELINE      │
             │  tools→act→reflect)│ │  regression)   │ │(fetch→normalize │
             └──────────┬─────────┘ └───────┬────────┘ │ →embed→index)   │
                        │                   │          └────┬────────────┘
             ┌──────────▼─────────┐         │               │
             │ SKILL & TOOL LAYER │         │               │
             │ skills + file read/│         │               │
             │ write/edit, exec,  │         │               │
             │ search, scrape,    │         │               │
             │ git, vision        │         │               │
             └──────────┬─────────┘         │               │
                        │                   │               │
             ┌──────────▼───────────────────▼───────────────▼────────────┐
             │              SECOND BRAIN  (Obsidian vault)               │
             │  inbox/ · notes/ · people/ · projects/ · meta/            │
             │  Markdown + [[wikilinks]] + #tags + frontmatter           │
             │  + graph index · embeddings · episodic log (SQLite)       │
             └──────────────────────────────┬───────────────────────────┘
                                            │
             ┌──────────────────────────────▼───────────────────────────┐
             │                  VERSIONED BRAIN (git)                   │
             │   prompt/ · knowledge/ · tools/ · skills/ · config/      │
             └──────────────────────────────────────────────────────────┘

              All LLM calls go through the LLM GATEWAY (provider adapters)
              All text passes through the LANGUAGE layer (detect/translate)
              Everything is configured via CONFIG: .env (secrets) + agent.yaml
```

### 3.1 Components

| Component | Responsibility |
|-----------|----------------|
| **Desktop Window** | The GUI that opens when the agent runs: agents panel + chat/work window + notes/graph panel (Section 11). |
| **Orchestrator** | The event loop. Routes user intent to: run a task, ingest data, run evals, reflect, or improve. |
| **Agent Core** | The "thinking" part: plans a task, **self-selects skills/tools**, executes, produces an answer. Stateless between calls; state lives in memory. |
| **Skill & Tool Layer** | Skills (reusable capabilities) built on tools: file I/O, code execution (sandbox), web search, scraping, git, image handling, vault read/write. Skills and tools are part of the Brain and can be edited. |
| **Eval Harness** | Runs a task suite against the current Brain, scores results, detects regressions. |
| **Ingestion Pipeline** | Pulls external data (GitHub, web, feeds, images, scratch) into the second brain. |
| **Second Brain** | Obsidian-vault knowledge store + graph index + embeddings + episodic log (Section 12). |
| **Versioned Brain** | Git-backed store of prompt, knowledge, tools, skills, config. The improvement loop commits here. |
| **LLM Gateway** | One interface → unlimited providers (Section 6). |
| **Config** | `.env` (secrets) + `config/agent.yaml` (routing & limits) — Section 7. |
| **Language Layer** | Detects and normalizes language across all text paths (Section 10). |

---

## 4. The Improvement Loop (heart of the system)

The first milestone. The loop turns measured feedback into a better Brain:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CHECKOUT   load current Brain (prompt + knowledge + tools)│
│ 2. EVALUATE   run task suite → scores + failure breakdown    │
│ 3. REFLECT    1 or more LLM passes: why did X fail?          │
│ 4. PROPOSE    LLM writes a diff: prompt / notes / code       │
│ 5. GATE       safety + budget + (optional) human approval    │
│ 6. APPLY      apply diff, run evals in sandbox               │
│ 7. COMMIT     if no regression → commit; else reject/rollback│
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Step details

1. **Checkout** — deterministic snapshot of the Brain for this run (commit hash).
2. **Evaluate** — the eval harness runs the suite with the snapshot and returns
   per-task results: pass/fail, cost, latency, and a short trace.
3. **Reflect** — the LLM is given failures (question, agent trace, grader
   verdict) and asked to produce a *root-cause hypothesis*. Reflection is
   written as structured notes, not free rambling.
4. **Propose** — based on reflections, the LLM proposes one of:
   - a **prompt edit** (`prompt/system.md` diff),
   - a **knowledge edit** (add/edit/remove a vault note),
   - a **skill/tool edit** (a file under `skills/` or `tools/` + a test).
5. **Gate** — checks: is this a permitted artifact? within budget? no secrets?
   Initially, prompt/knowledge edits auto-apply only if evals pass; skill/code
   edits always require human approval until trust is earned. At **full
   autonomy** the approval gates may be turned off (Section 9).
6. **Apply + validate** — apply the diff in a sandboxed copy, re-run the suite.
7. **Commit or rollback** — commit if `new_score >= old_score` (no regression
   on held-out set); otherwise reject and record the rejection (the agent can
   reflect on *that* too).

### 4.2 Example: one improvement

```
[run]    eval score: 0.72  (fails: 4 web-scraping tasks)
[reflect] root cause: extraction breaks on <pre> and tables; prompt has no
          rule about code blocks.
[propose] prompt/system.md: + "When scraping, preserve <pre>/<table> verbatim."
[gate]   prompt edit → allowed, low risk
[apply]  sandbox re-eval: 0.78, no regression
[commit] "improve(prompt): preserve code blocks when scraping (0.72→0.78)"
```

### 4.3 Guardrails

- **No regression** on the held-out set — hard rule for auto-apply.
- **Budgets**: max LLM cost per improvement, max commits per session.
  (Each is configurable; `0` disables the limit — Section 7.)
- **Rate limits** so the loop can't spin forever (configurable; `0` = none).
- **Rollback**: `git revert` is always one command away.
- **Immutable log**: every proposal, gate decision, and eval result is stored
  in the episodic log for later audit and analysis.

---

## 5. Data Ingestion

Everything external becomes normalized knowledge in the second brain.

### 5.1 Sources

| Source | How it's fetched | What's extracted |
|--------|------------------|------------------|
| **GitHub links / repos** | `git clone --depth 1` (or GitHub API for links/issues) | code files, README, docs, issue/PR text; chunked by file/function |
| **Websites / pages** | HTTP fetch → readability extraction | main text, title, links, metadata |
| **Scraped data** | user-defined scrape jobs (selectors, pagination) | structured text records |
| **Feeds (RSS/Atom)** | periodic poll of feed URLs | new items → title, body, link, date |
| **Scratch notes** | user pastes/typing | raw text, tagged by topic |
| **Pictures** | upload or URL | OCR text + vision-model description + thumbnail |

### 5.2 Normalization pipeline (common to all sources)

```
raw source ──► FETCHER ──► LANGUAGE DETECT ──► NORMALIZER (Markdown + metadata)
        ──► INBOX (00-inbox) ──► CHUNKER ──► EMBEDDER ──► GRAPH INDEX
        ──► SUMMARIZER ──► NOTE filed into the vault (curated, editable)
```

- **Inbox first**: everything lands in `00-inbox/` before it is organized —
  the "capture" step of the second brain (Section 12).
- **Language detect**: every ingested document is tagged with its language(s)
  before normalization (see Section 10).
- **Chunker**: splits text into retrieval-sized chunks with source provenance.
- **Embedder**: via the LLM Gateway (multilingual embedding model for
  cross-language retrieval).
- **Summarizer**: produces candidate *notes* — concise, attributed, and
  editable — that the agent files into the right vault folder and links.
- **Images**: OCR (e.g. tesseract, multilingual) + a vision-capable model for
  description; both stored as text alongside a thumbnail.

### 5.3 Provenance

Every note/chunk keeps `source_url`, `source_type`, `ingested_at`, `language`,
and a content hash in its frontmatter, so the agent can always answer "where
did I learn this?" and can re-ingest when sources change.

---

## 6. Model-Agnostic LLM Gateway

One interface, many providers, zero code changes when swapping models — and no
cap on how many you add (config-driven, see Section 7).

```python
class LLM:
    def chat(self, messages, tools=None, **kw) -> AssistantMessage
    def complete(self, prompt, **kw) -> str
    def embed(self, texts: list[str]) -> list[list[float]]
    def describe_image(self, image_bytes, prompt="") -> str

# Adapters: OpenAIGateway, AnthropicGateway, GoogleGateway, MistralGateway,
#           GroqGateway, DeepSeekGateway, CohereGateway, OpenRouterGateway,
#           OllamaGateway, OpenAICompatibleGateway (any custom endpoint), ...
```

- **Config-driven**: provider, model name, temperature, token budget per
  capability (chat / reflection / summarization / embedding can use different
  models) — all set in `.env` / `agent.yaml`.
- **Tool-calling normalization**: the gateway exposes one tool-use contract and
  maps it to each provider's native format.
- **Capability registry**: each adapter declares what it supports (vision,
  tools, embeddings). The orchestrator picks a model per task based on needs.
- **Multilingual capability**: adapters declare which languages they handle
  well, so the language layer can route to the best model for a given text.
- **Cost & latency telemetry** on every call — feeds the eval harness.
- **No hardcoded list**: providers are discovered from config + adapter
  presence. A new provider is added by (a) filling in its key, or (b) dropping
  a small adapter file in `gateway/`. Any OpenAI-compatible endpoint works
  with zero new code via `OpenAICompatibleGateway`.

---

## 7. Configuration — any provider, any model, no limits

All configuration lives in two places, split by sensitivity:

| File | What it holds | Committed? |
|------|---------------|------------|
| **`.env`** | Secrets: API keys, endpoints, local model URLs | No (gitignored) |
| **`.env.example`** | Documented template of `.env` | Yes |
| **`config/agent.yaml`** | Non-secrets: model routing, limits, autonomy, languages, vault, window | Yes (part of Brain) |

> `.env` and `.env.example` are provided at the repo root. Copy the template
> and fill in only the providers you use.

### 7.1 "Any provider, any model, no limit"

- **Any provider**: every provider block in `.env` is optional. Setting its key
  *enables* it; leaving it blank *disables* it. There is no whitelist and no
  count limit — add as many providers as you want.
- **Any model**: each provider can point at any model it offers (or any local
  model via Ollama / LM Studio / vLLM). A generic `OpenAICompatibleGateway`
  covers any HTTP endpoint that speaks the OpenAI schema.
- **No limit on routing**: each *capability* (chat, reflect, summarize, judge,
  vision, embedding) can use a different provider/model, so you can mix e.g.
  Claude for reflection, Gemini for vision, and a local model for embeddings.

### 7.2 `.env` (secrets) — key variables

```
AGENT_GEN_PROVIDER=openai          # default provider
AGENT_GEN_MODEL=auto               # default model (auto = provider default)
OPENAI_API_KEY=                    # any provider key you like (add many)
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
... (Mistral, Groq, DeepSeek, Cohere, OpenRouter, Together, Azure, ...)
OLLAMA_BASE_URL=http://localhost:11434   # local models
CUSTOM_BASE_URL= / CUSTOM_API_KEY= / CUSTOM_MODEL=   # any OpenAI-compatible server
AGENT_GEN_MODEL_CHAT|REFLECT|SUMMARIZE|JUDGE|VISION|EMBEDDING=   # per-capability
AGENT_GEN_MAX_CONTEXT_TOKENS=0     # 0 = unlimited (provider max)
AGENT_GEN_CONVERSATION_MEMORY=on   # remember long conversations
AGENT_GEN_AUTO_SUMMARIZE_AT=0      # 0 = never compact
AGENT_GEN_AUTONOMY=full            # assisted | semi | auto | full
AGENT_GEN_MAX_STEPS=0              # 0 = no limit
AGENT_GEN_MAX_COST=0               # 0 = no spending limit
AGENT_GEN_RATE_LIMIT=0             # 0 = no rate limit
AGENT_GEN_ALLOW_SELF_IMPROVE=on    # agent may improve itself freely
AGENT_GEN_FREE_THINK=on            # agent may reason/reflect openly at length
AGENT_GEN_LANGUAGES=en,hi          # any BCP-47 codes
AGENT_GEN_DEFAULT_LANG=auto
# --- Window & Second Brain ---
AGENT_GEN_UI_AUTO_OPEN=on          # open the window when the agent starts
AGENT_GEN_UI_PORT=0                # 0 = pick a free port
AGENT_GEN_VAULT_PATH=./brain/vault # path to the Obsidian vault (your second brain)
AGENT_GEN_OPEN_IN_OBSIDIAN=off     # also launch Obsidian pointing at the vault
```

The full, annotated template lives in `.env.example` at the repo root.

### 7.3 `config/agent.yaml` (non-secrets) — example

```yaml
gateway:
  default_provider: openai
  default_model: auto
  routing:                       # any capability -> any provider/model
    chat:      { provider: openai,     model: gpt-4o }
    reflect:   { provider: anthropic,  model: claude-sonnet-4-5 }
    summarize: { provider: openrouter, model: deepseek/deepseek-chat }
    embedding: { provider: openai,     model: text-embedding-3-large }
    vision:    { provider: google,     model: gemini-2.5-pro }
    judge:     { provider: anthropic,  model: claude-sonnet-4-5 }

limits:                          # 0 / "none" = no limit
  max_steps: 0
  max_cost_usd: 0
  max_context_tokens: 0          # 0 = provider maximum
  rate_per_minute: 0

autonomy: full                   # assisted | semi | auto | full
conversation:
  persist: true
  auto_summarize_at_tokens: 0    # 0 = never; else rolling compaction
languages: [en, hi]

window:                          # the desktop window (Section 11)
  auto_open: true
  port: 0                        # 0 = auto
  title: "Agent-Gen"

second_brain:                    # Obsidian vault (Section 12)
  vault_path: ./brain/vault
  graph_view: true               # enable the "graphify" knowledge graph
  open_in_obsidian: false
```

### 7.4 "No limit" semantics

Every limit field accepts `0` or `none` to mean **unlimited**. With all limits
at `0`, the agent is bounded only by the provider's own context window and your
API plan — no artificial caps are imposed by Agent-Gen itself.

---

## 8. Long Conversation & Long Context

The agent should hold **long conversations** and use **long context** without
silently forgetting or truncating.

### 8.1 Conversation memory

- **Persistent transcript**: every session's full message history is stored
  (append-only) in the memory store. Conversations resume across restarts.
- **Context assembly** each turn = system prompt + Brain summary + retrieved
  knowledge + *rolling conversation summary* + recent turns.
- **Rolling compaction**: when history passes `auto_summarize_at_tokens`
  (or a fraction of the model's window), older turns are distilled into a
  **conversation summary** (with key facts, decisions, and open questions
  preserved). The conversation is therefore effectively unbounded: the oldest
  turns never vanish, they get summarized and stay retrievable.
- **Cross-session memory**: durable facts about the user and past work are
  promoted to long-term knowledge (vault notes), so a "new" chat still
  remembers.

### 8.2 Long context

- **Full window**: the agent reads and writes up to the provider's maximum
  context window (e.g. 128k, 200k, 1M tokens). `max_context_tokens=0` means
  "use the provider's maximum, no self-imposed ceiling."
- **Oversized documents**: content longer than the window is handled by
  chunking + retrieval (Section 5), never by blind truncation.
- **Streaming**: long responses stream token-by-token so the UI stays live.
- **Attention to budget**: cost/latency rise with context; telemetry exposes
  tokens-per-turn so the user can see what long context costs (but it is never
  capped unless they set a cap).

---

## 9. Agent Autonomy & Skills

The agent must be able to use its capabilities **on its own initiative** —
"self control" — and, at the top level, be **free to think and work**.

### 9.1 Skills

A **skill** is a reusable capability composed of a prompt fragment, a set of
tools, and (optionally) code. The agent invokes skills the way a craftsman
picks a tool from a box:

```
skill: scrape_and_summarize
  description: "Fetch a URL, extract main text, return a 3-bullet summary"
  tools: [web_fetch, readability_extract]
  prompt: "You are scraping. Preserve code blocks and tables."
  language_hint: "respond in the language of the input"
```

- Skills live under `skills/` in the Brain, so the agent can **add, edit, and
  retire its own skills** through the same improvement loop as code and prompt.
- Skills are self-invoked: the Agent Core reads the skill catalog each turn
  and decides which (if any) to use to satisfy the current goal.

### 9.2 The act loop (self-controlled)

```
1. GOAL      user intent or self-generated sub-goal
2. THINK     reason openly (extended reflection if FREE_THINK=on)
3. PLAN      choose skills/tools; estimate cost
4. ACT       execute one step (call tool/skill)
5. OBSERVE   read the result, update working memory
6. DECIDE    done? else loop to 2 (bounded only by budget)
7. REPORT    summarize to the user (in their language)
```

The agent keeps looping autonomously **until** the goal is met, the budget is
exhausted, or it hits an escalation condition (below).

### 9.3 Autonomy levels (a dial, up to full freedom)

| Level | Behavior |
|-------|----------|
| **Assisted** | Agent suggests skills/tools, asks before acting. |
| **Semi-autonomous** | Agent acts, but reports each step and can be interrupted. |
| **Autonomous** | Agent acts silently within budget/permissions; reports only the result. |
| **Full** | Agent may also **self-initiate** work: set its own sub-goals, run background self-improvement, edit its own prompt/knowledge/skills (subject to the gate policy), and reason at length without being asked. |

`AGENT_GEN_AUTONOMY=full` + `ALLOW_SELF_IMPROVE=on` + `FREE_THINK=on` + all
limits at `0` gives the agent **free freedom to think and work on**.

### 9.4 Safety bounds on autonomy (all optional, all user-controlled)

- **Budget**: max steps, max LLM cost, max wall-clock per goal — `0` = none.
- **Permissions**: each skill declares required permissions (read files, write
  files, network, exec); the agent may only invoke skills whose permissions
  are granted at the current autonomy level.
- **Escalation**: the agent must stop and ask a human when it needs a
  permission it doesn't have, when confidence is low, or when an action is
  irreversible. (Can be relaxed at **full** autonomy.)
- **Kill switch**: any goal can be interrupted and rolled back — always
  available, even at full freedom.

---

## 10. Multilingual Support

The agent **knows multiple languages** end-to-end — not just at the chat
layer. Default languages are **English and Hindi**; the set is configurable.

### 10.1 Language layer

A thin layer that every text path flows through:

- **Detect**: identify language(s) of any incoming text (user message, doc,
  note) — including code-switched / mixed text (Hinglish, etc.).
- **Normalize**: record `language` as metadata on every stored item.
- **Route**: pick the best-capable model per language (via gateway capability
  registry).
- **Respond**: reply in the user's language unless told otherwise.

### 10.2 Per-path behavior

| Path | Multilingual behavior |
|------|-----------------------|
| **Chat** | Detects user language and replies in it; honors code-switching; `/lang hi` pins the language. |
| **Ingestion** | Tags each document with its language; notes may be stored in the source language. |
| **Knowledge/notes** | Notes carry a `language` field in frontmatter; retrieval is cross-lingual via multilingual embeddings. |
| **Summaries** | Default: summarize into the user's preferred language; keep a source-language copy. |
| **Evals** | Tasks declare a language; the judge grades in that language; translations are only a convenience, never the graded artifact. |
| **Voice (later)** | Speech in/out via multilingual TTS/STT; out of scope for M1. |

### 10.3 Retrieval across languages

- Embeddings use a **multilingual model**, so a Hindi question can retrieve an
  English note and vice versa without requiring translation first.
- Optional **cross-lingual summarizer** produces a translated gloss of a
  retrieved note on demand (never mutating the original).

---

## 11. Desktop Window (GUI)

When the agent runs, a **nice window opens** — not a terminal. It shows the
agents, the chat/work window, and the second brain at a glance.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent-Gen                                          [–] [□] [✕]        │
├──────────────┬──────────────────────────────────────┬───────────────────┤
│  AGENTS      │         CHAT / WORK WINDOW           │  SECOND BRAIN     │
│              │                                      │  ┌─────────────┐  │
│  ● Builder   │  You:  "summarize this repo"         │  │  📄 Notes   │  │
│  ○ Reader    │  Agent: [streaming…]                 │  │  🕸 Graph   │  │
│  ○ Writer    │                                      │  ├─────────────┤  │
│  ○ All       │  ┌─ tool calls / step log ────────┐  │  │  ●─●─●      │  │
│              │  │ ✓ scrape  ✓ summarize          │  │  │   ╲ ╱       │  │
│              │  └────────────────────────────────┘  │  │    ●        │  │
│              │                                      │  └─────────────┘  │
├──────────────┴──────────────────────────────────────┴───────────────────┤
│  /task · /ingest · /eval · /improve · /autonomy · /lang · status bar   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.1 Panels

| Panel | Purpose |
|-------|---------|
| **Agents panel** | A roster of agents (Builder, Reader, Writer, …). Click one to talk to that agent specifically, or "All" to talk to the group. Shows each agent's status (idle / working / done). |
| **Chat / Work window** | The main conversation plus a **live work log**: which tool/skill ran, its output, cost, and duration. Streaming responses. |
| **Second Brain panel** | Tabs for **Notes** (browse/search the vault) and **Graph** ("graphify" — the interactive knowledge graph). |

### 11.2 Commands (also available in the window)

```
/task <prompt>          run a task through the agent
/ingest <url|repo|file> add external data into the second brain
/eval                   run the eval suite, show scorecard
/improve [category]     run the improvement loop
/diff                   show the latest Brain change
/brain                  browse prompt/knowledge/tools/skills
/rollback <commit>      revert a Brain change
/autonomy <level>       assisted | semi | auto | full
/lang <code>            pin chat language (en, hi, auto, ...)
```

### 11.3 Window technology

- **Recommended**: a local web app (FastAPI backend + React/Vue frontend) that
  is **auto-opened** in the browser when the agent starts, optionally wrapped
  in a **native window** via `pywebview` so it feels like a real desktop app.
- **Alternatives**: Tauri/Electron shell (JS) talking to the Python backend as
  a sidecar, for a fully native window.
- **Auto-open**: `AGENT_GEN_UI_AUTO_OPEN=on` (default) opens the window on run;
  `AGENT_GEN_UI_PORT=0` auto-picks a free port.
- The window runs locally only; it never requires the user's browser to reach
  `localhost` from a remote machine (all calls are relative, proxied by the
  backend).

---

## 12. Second Brain — Obsidian + Graph ("graphify") + memory

The memory system is modeled as a **Second Brain** (capture → organize →
distill → express), and it is physically an **Obsidian vault**: a folder of
plain Markdown notes with `[[wikilinks]]`, `#tags`, and YAML frontmatter.

### 12.1 Why Obsidian as the second brain

- **Plain text, no lock-in** — the vault is readable by the agent, by
  Obsidian, and by any text tool.
- **Links = structure** — `[[wikilinks]]` and `#tags` make the knowledge a
  *graph*, not a pile of files.
- **You can open the same vault** in the Obsidian app while the agent works in
  it — one brain, two editors (human + agent).

### 12.2 Vault layout

```
brain/vault/                  # AGENT_GEN_VAULT_PATH (an Obsidian vault)
  00-inbox/                   # capture: everything lands here first
  10-notes/                   # organized notes (curated knowledge)
  20-people/                  # people, accounts, sources
  30-projects/                # per-project notes
  40-resources/               # raw extracted material (chunks w/ provenance)
  90-meta/                    # the agent's own reflections & improvement log
```

### 12.3 The CODE loop, mapped

| Second-brain step | Agent-Gen equivalent |
|-------------------|----------------------|
| **Capture** | Everything ingested or typed lands in `00-inbox/` with frontmatter (`source_url`, `language`, `ingested_at`, `hash`). |
| **Organize** | The agent files notes into folders, adds `[[links]]` and `#tags`, and connects related ideas. |
| **Distill** | Progressive summarization: highlight → summary → evergreen note (the summarizer writes these). |
| **Express** | Retrieval during chat returns the distilled note, cited with its source. |

### 12.4 Graph view ("graphify")

- An interactive, force-directed **knowledge graph**: notes are **nodes**,
  `[[wikilinks]]` and shared tags are **edges**.
- Rendered with a graph library (Cytoscape.js / d3-force / vis-network) in the
  window's Second Brain panel.
- **Live**: the graph updates as the agent writes/links notes. Clicking a node
  opens the note; hovering shows its tags and sources.
- **Graph is derived, not stored** — it is computed from the vault (markdown +
  frontmatter) and cached in a `graph index`, so it never drifts from the
  truth.

### 12.5 Memory types (and where each lives)

| Memory | Storage | Purpose |
|--------|---------|---------|
| **Working memory** | In-request context | Current task's plan, tool outputs, scratch. |
| **Conversation memory** | SQLite (+ rolling summaries) | Long chats; resumes across restarts (Section 8). |
| **Episodic log** | SQLite (append-only) | Immutable record of every action/outcome for audit & reflection. |
| **Knowledge (second brain)** | Obsidian vault (Markdown) | Durable, linked, human-readable notes. |
| **Graph index + embeddings** | SQLite/vector store | Fast retrieval + graph rendering, derived from the vault. |

The vault Markdown is the **source of truth**; indexes are always
reconstructible from it.

---

## 13. Self-Modification & Safety

This is the riskiest part of the design, so it gets its own section.

### 13.1 What the agent may modify

- `prompt/**` — its own instructions. *Auto-apply if evals pass.*
- `knowledge/**` (the vault) — its notes. *Auto-apply if evals pass.*
- `skills/**` — its reusable capabilities. *Sandbox tests + human approval.*
- `tools/**` — its low-level capabilities. *Requires sandbox tests + human approval.*
- `config/**` — budgets, gates. *Requires human approval, always.*

At **full autonomy**, the human-approval gates may be switched off per the
user's choice; the no-regression rule and sandbox tests always remain.

### 13.2 Sandbox

- Code the agent writes runs in an isolated environment (container/VM):
  no access to the live Brain, network egress restricted, resource limits.
- A skill or tool is only merged after its tests pass **inside the sandbox**,
  then again against the full eval suite outside it.

### 13.3 Human-in-the-loop gates

| Change type | Auto-apply? | Condition |
|-------------|-------------|-----------|
| Prompt / knowledge (vault note) edit | Yes (M1) | eval score improves, no regression |
| Skill / tool code edit | No (M1) | human reviews the diff |
| Config change | No | human reviews |
| Anything touching credentials/network | No | always blocked without approval |

The gate policy is itself config; trust (and therefore autonomy) can be
increased over time, up to full freedom.

---

## 14. Eval Harness (the first thing to build)

The improvement loop is only as good as its measurement.

### 14.1 Task suite

- **Golden tasks** with reference answers, graded by exact match, substring,
  or code-exec tests.
- **LLM-judge tasks** for open-ended answers (a judge model scores 1–5 against
  a rubric).
- **Tool/skill tasks** that assert the agent's capabilities work (scrape
  returns expected text, a skill produces a valid diff, vault read/write
  works, etc.).
- Every task has a **category** (retrieval, coding, scraping, reasoning) and a
  **language**, so failures can be grouped for reflection.

### 14.2 Metrics

- **Pass rate** per category, per language, and overall.
- **Regression** — the held-out set that must never go down.
- **Cost & latency** — so "better" isn't bought by spending 10× more.
- **Improvement delta** — did the proposed change actually move the number?

### 14.3 M1 exit criteria

- CLI can run a task suite against a Brain snapshot and print a scorecard.
- The full improve loop (eval → reflect → propose → apply → commit/rollback)
  works end-to-end on prompt/knowledge artifacts.
- Every improvement is a git commit with eval before/after in the message.
- Config loads from `.env` + `config/agent.yaml`; provider/model routing works
  for at least two providers.
- The agent replies in the user's language in a smoke test (English + Hindi).

---

## 15. Proposed Tech Stack

- **Language**: Python 3.11+ (plain, minimal deps — no agent framework yet;
  the design is small enough that a framework adds more indirection than value).
- **Window**: FastAPI + React/Vue, auto-opened in browser, wrapped by
  `pywebview` for a native window (alternative: Tauri/Electron shell).
- **Config**: `.env` (secrets, via `python-dotenv`) + `config/agent.yaml`
  (non-secrets, via PyYAML).
- **Second brain**: an Obsidian vault = plain Markdown + YAML frontmatter +
  `[[wikilinks]]`. Optional `obsidian://` deep-link to open in Obsidian.
- **Graph view**: Cytoscape.js (or d3-force/vis-network) rendering the vault
  graph in the window.
- **Brain store**: git (via `dulwich` or subprocess) — prompt/knowledge/tools/skills/config.
- **Vector store**: SQLite + `sqlite-vec` (or Chroma) — zero-infra, file-based;
  multilingual embedding model.
- **Episodic/conversation**: SQLite.
- **LLM Gateway**: thin adapter layer (OpenAI, Anthropic, Google, Mistral,
  Groq, DeepSeek, Cohere, OpenRouter, Ollama, and a generic OpenAI-compatible
  adapter for anything else).
- **Language layer**: lightweight detector (e.g. `lingua`/`fasttext` lid model)
  + optional translation via the gateway.
- **Sandbox**: Docker, or `subprocess` + resource limits for a lighter start.
- **Testing**: pytest — the eval harness reuses it for code/tool tasks.

> Stack is a recommendation, not final. It keeps things simple and auditable.

### 15.1 Proposed repository layout (future)

```
agent-gen/
  .env                    # your secrets (gitignored)
  .env.example            # documented template (committed)
  brain/                  # the versioned self (git repo of record)
    vault/                # SECOND BRAIN — the Obsidian vault
      00-inbox/ 10-notes/ 20-people/ 30-projects/ 40-resources/ 90-meta/
    prompt/system.md
    skills/*.yaml + code
    tools/*.py + tests
    config/agent.yaml     # non-secret settings (committed)
  src/agent_gen/
    orchestrator.py       # the loop
    agent.py              # act: plan → skill → tools → answer
    config.py             # load .env + agent.yaml, resolve routing/limits
    gateway/              # LLM adapters (unlimited providers)
    lang/                 # language detect + route
    memory/               # episodic + conversation (sqlite) + graph index
    vault.py              # second-brain read/write/link helpers
    ingestion/            # fetchers + normalizers
    evals/                # harness, suites, graders
    improve/              # reflect + propose + gate + apply
  ui/                     # the desktop window (FastAPI + React + graph view)
  docs/                   # this doc + ADRs
```

---

## 16. Roadmap

| Milestone | Deliverable | Exit criteria |
|-----------|-------------|---------------|
| **M0 — Design** *(now)* | This document + `.env` template | Scope agreed, stack chosen |
| **M1 — Eval + improvement loop** | LLM gateway (multi-provider), config loader, minimal agent, memory, versioned Brain, eval harness, improve loop, basic language layer | Loop improves prompt/knowledge with no regression; multi-provider routing works; bilingual smoke test passes |
| **M2 — Window + Second Brain** | Desktop window (agents panel + chat/work + notes/graph), Obsidian vault, graph view ("graphify"), conversation memory | Window opens on run; agent reads/writes the vault; graph updates live |
| **M3 — Ingestion** | GitHub, website, feed, scratch, and image ingestion → second brain | Agent retrieves and cites ingested data, cross-lingually |
| **M4 — Self-code + skills + autonomy** | Skill/tool editing + sandbox + tests + approval gates + autonomy dial (incl. full) | Agent ships a working skill/tool change end-to-end; runs autonomously |
| **M5 — Multi-agent polish** | Multiple named agents collaborating over the shared second brain, per-agent routing | The window shows several agents working together on one task |

---

## 17. Risks & Open Questions

1. **Eval quality** — if the task suite is weak, "improvement" becomes
   overfitting. Mitigation: held-out set, human spot-checks.
2. **Runaway loops** — the agent could churn indefinitely. Mitigation: budgets,
   rate limits, convergence checks (stop if score stops moving). With limits
   set to `0`, the user accepts unbounded loops; the kill switch still works.
3. **Over-eager autonomy** — acting without asking can be dangerous or
   annoying. Mitigation: autonomy dial (incl. `full`), permission-scoped
   skills, escalation, kill switch.
4. **Self-modification safety** — prompt/knowledge auto-apply is bounded;
   skill/code/config always gated by default. Revisit as trust grows.
5. **Model-agnostic friction** — tool-calling and vision differ per provider;
   the gateway must normalize carefully (small, tested adapters). The generic
   OpenAI-compatible adapter covers most long-tail providers.
6. **Vault concurrency** — the human (Obsidian) and the agent can both edit
   notes at once. Mitigation: atomic per-file writes, git as the merge base,
   conflict markers surfaced in the window.
7. **Graph scale** — thousands of notes can make the graph view slow.
   Mitigation: client-side clustering, lazy rendering, filters by tag/folder.
8. **Long context costs** — huge contexts raise cost and latency. Mitigation:
   telemetry + optional compaction; never a hard truncation by default.
9. **Multilingual quality** — cross-lingual retrieval and mixed-language
   (code-switched) input are hard; judge must grade in-language, not on
   machine-translated text. Mitigation: multilingual embeddings, per-language
   evals.
10. **Overfitting to the judge** — LLM-judge scoring can be gamed; use rubric +
    multi-judge for high-stakes tasks.
11. **Open**: which provider to default to first? which languages beyond
    English + Hindi? native window (pywebview/Tauri) vs. browser tab? how large
    should the initial eval suite be? exact sandbox choice (Docker vs
    process-level)?

---

## 18. Definitions

- **Brain**: the versioned set of prompt, knowledge, tools, skills, and config
  that defines the agent's behavior.
- **Second brain**: the Obsidian vault holding the agent's linked knowledge —
  the living, human-readable memory (capture → organize → distill → express).
- **Graph view ("graphify")**: the interactive force-directed graph of the
  second brain (notes = nodes, links/tags = edges), live in the window.
- **Agent**: a named role (prompt + skills + tools) shown in the window;
  multiple agents share the same second brain.
- **Skill**: a reusable capability (prompt + tools + optional code) the agent
  self-invokes to accomplish a goal.
- **Autonomy level**: how much the agent may act without asking (assisted →
  semi-autonomous → autonomous → full).
- **Full freedom**: autonomy level where the agent may self-initiate work,
  reason at length, and improve itself, bounded only by what the user configures.
- **Conversation memory**: the persistent transcript + rolling summaries that
  let long conversations continue without forgetting or truncating.
- **Episodic log**: immutable record of what the agent did and what happened.
- **Notes**: curated, durable knowledge distilled from ingested data and lessons.
- **Held-out set**: eval tasks never used during improvement proposals, used
  only to detect regression/overfitting.
- **Language layer**: the cross-cutting component that detects, tags, routes,
  and responds in the right language.
