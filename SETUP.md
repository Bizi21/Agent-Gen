# 🚀 Agent-Gen — Install, Setup & Run Guide

Is guide mein **step-by-step commands** hain — download se lekar window kholne tak.

---

## 0. Kya chahiye (Requirements)

| Cheez | Version |
|-------|---------|
| **Python** | 3.9 ya naya (3.11 recommended) |
| **Git** | koi bhi recent version |
| **OS** | Windows / macOS / Linux — sab chalega |

> ✅ **Koi pip install nahi chahiye!** Agent-Gen **zero dependencies** par
> chalta hai — sirf Python standard library. Koi framework, koi package nahi.

Python check karo:

```bash
python3 --version      # ya Windows par: python --version
```

Agar Python nahi hai: [python.org/downloads](https://www.python.org/downloads/) se install karo
(Windows par "Add Python to PATH" tick karna mat bhoolna).

---

## 1. Repo download karo (Clone)

```bash
git clone https://github.com/Bizi21/Agent-Gen.git
cd Agent-Gen
```

> **Branch note:** sab latest code `arena/01a09662-agent-gen` branch par hai.
> Clone ke baad switch karo:
> ```bash
> git checkout arena/01a09662-agent-gen
> ```

---

## 2. Config karo — API key add karo

```bash
# .env.example se .env banao
cp .env.example .env
```

Ab `.env` file kholo (Notepad / VS Code / nano) aur apni **OpenAI key** daalo:

```env
AGENT_GEN_PROVIDER=openai
AGENT_GEN_MODEL=gpt-4o-mini

OPENAI_API_KEY=sk-...yahan-apni-key...
```

> 🔒 `.env` gitignored hai — key kabhi GitHub par upload nahi hogi.
>
> **Koi bhi provider** daal sakte ho: Anthropic, Gemini, Groq, DeepSeek,
> Mistral, Ollama (local), ya koi bhi OpenAI-compatible endpoint. Jis provider
> ki key daaloge, wahi enable hoga.
>
> **Key na bhi daalo to bhi sab chalega** — agent offline "mock" mode mein
> kaam karega (bina network ke).

---

## 3. Pehli baar setup (brain + vault banata hai)

```bash
./agent init
```

Windows par:

```bash
python -m agent_gen init
```

Isse ye banega:

```
brain/
  prompt/system.md        # agent ke instructions (ye khud edit kar sakta hai)
  skills/*.json           # research, summarize, coder, remember
  config/agent.json       # settings
  vault/                  # 🧠 Second Brain (Obsidian vault)
```

---

## 4. RUN karo! 🎉

### ⭐ Sabse simple — window kholo (chat first screen)

```bash
./agent
```

Windows par:

```bash
python -m agent_gen
```

Ye command:
- Agent ko boot karta hai
- **Khud mode + skills decide** karta hai
- Browser mein **desktop window** kholta hai (chat window pehli screen)

---

## 5. Saare commands (one by one)

| Command | Kya karta hai |
|---------|---------------|
| `./agent` | 🖥️ window kholo (chat + agents + graph) |
| `./agent init` | brain + vault structure banao |
| `./agent eval` | eval suite chalao → scorecard |
| `./agent improve` | self-improvement loop (seekh kar khud commit karta hai) |
| `./agent run "sawal"` | ek task chalao |
| `./agent chat` | terminal mein chat (REPL) |
| `./agent ingest <url\|file>` | website/file ko vault mein daalo |
| `./agent graph` | knowledge graph print karo |
| `./agent ui` | window kholo (same as `./agent`) |
| `./agent --version` | version dekho |

Windows par `./agent` ki jagah **`python -m agent_gen`** use karo:

```bash
python -m agent_gen eval
python -m agent_gen improve
python -m agent_gen run "What is the capital of France?"
```

---

## 6. Test karo (sab theek hai ya nahi)

```bash
python3 -m unittest discover -t . -s tests
```

Windows:

```bash
python -m unittest discover -t . -s tests
```

> Output mein `OK` aur `Ran 41 tests` dikhna chahiye.

---

## 7. Window mein kya-kya try karo

Chat box mein likho:

```
What is the capital of France?
search the vault for lessons
remember that my favorite color is blue
/eval
/improve
```

Dekhoge agent **live kaam karta hua** — thinking 💭 → skill ⚡ → knowledge 📚
→ tool 🛠️ → answer 🤖.

Right panel mein:
- **Graph tab** — knowledge graph (drag, zoom, node par click karo → note khulega)
- **Notes tab** — notes browse/search karo

---

## ⚠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `python3 not found` | `python` use karo (Windows), ya Python install karo |
| `./agent permission denied` (Linux/Mac) | `chmod +x agent` |
| "openai unreachable" warning | Sandbox/network issue hai ya key galat — agent offline mode mein continue karega. `.env` mein key check karo. |
| Window nahi khuli | Browser mein manually URL kholo jo terminal mein print hua (jaise `http://127.0.0.1:PORT`) |

---

## 🧠 Obsidian (optional, best experience)

Apna **Second Brain** Obsidian app mein kholne ke liye:

1. [Obsidian](https://obsidian.md) download karo
2. "Open folder as vault" → `Agent-Gen/brain/vault` folder select karo
3. Ab tumhare notes graph view mein bhi dikhenge — aur agent unhi files mein likhta hai

> Ya `.env` mein `AGENT_GEN_OPEN_IN_OBSIDIAN=on` kar do — agent khud Obsidian
> launch kar dega.

---

**Short version (3 commands):**

```bash
git clone https://github.com/Bizi21/Agent-Gen.git && cd Agent-Gen
cp .env.example .env      # .env mein apni key daalo
./agent                   # window khulegi — bas!
```
