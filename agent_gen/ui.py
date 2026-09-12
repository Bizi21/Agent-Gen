"""Desktop window — a local web UI served with the stdlib HTTP server.

Panels: agents roster, chat/work window, and the second brain (notes + graph).
Served on a single page with inline HTML/CSS/JS — no CDN, works fully offline.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .agent import Agent
from .bootstrap import ensure_brain
from .config import Config
from .evals.harness import render_scorecard, run_suite, scorecard
from .evals.suite import DEFAULT_SUITE
from .gateway.registry import LLMPool
from .improve.loop import render_report, run_improve
from .memory.store import Memory
from .vault import Vault

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent-Gen</title>
<style>
  :root { --bg:#0e1117; --panel:#161b22; --line:#21262d; --text:#e6edf3; --dim:#8b949e;
          --accent:#2f81f7; --accent2:#3fb950; --danger:#f85149; }
  * { box-sizing:border-box; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--text);
              font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
  #app { display:grid; grid-template-columns:220px 1fr 340px; grid-template-rows:1fr 44px;
         height:100vh; gap:1px; background:var(--line); }
  .panel { background:var(--panel); overflow:hidden; display:flex; flex-direction:column; }
  .panel > h2 { font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--dim);
                padding:10px 14px; margin:0; border-bottom:1px solid var(--line); }
  /* agents */
  #agents ul { list-style:none; margin:0; padding:8px; }
  #agents li { padding:8px 10px; border-radius:8px; cursor:pointer; display:flex; align-items:center; gap:8px; }
  #agents li:hover { background:#1f2630; }
  #agents li.active { background:#1c2b3f; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--dim); flex:0 0 auto; }
  .dot.busy { background:var(--accent2); }
  /* chat */
  #messages { flex:1; overflow-y:auto; padding:14px; }
  .msg { margin:0 0 12px; max-width:82%; padding:10px 12px; border-radius:10px; white-space:pre-wrap; word-wrap:break-word; }
  .msg.user { background:#1c2b3f; margin-left:auto; }
  .msg.agent { background:#1b2430; }
  .msg.tool { background:#141a22; color:var(--dim); font-size:12px; border:1px solid var(--line); }
  #composer { display:flex; gap:8px; padding:10px 12px; border-top:1px solid var(--line); }
  #composer input { flex:1; background:#0d1117; color:var(--text); border:1px solid var(--line);
                    border-radius:8px; padding:8px 12px; outline:none; }
  #composer button { background:var(--accent); color:#fff; border:0; border-radius:8px; padding:0 18px; cursor:pointer; }
  /* second brain */
  .tabs { display:flex; border-bottom:1px solid var(--line); }
  .tabs button { flex:1; background:none; color:var(--dim); border:0; padding:10px; cursor:pointer; }
  .tabs button.on { color:var(--text); border-bottom:2px solid var(--accent); }
  #noteslist { flex:1; overflow-y:auto; padding:10px; }
  .note { padding:8px 10px; border-radius:8px; cursor:pointer; }
  .note:hover { background:#1f2630; }
  .note .folder { color:var(--dim); font-size:11px; }
  #graph { flex:1; background:#0d1117; }
  /* status bar */
  #statusbar { grid-column:1 / -1; background:var(--panel); border-top:1px solid var(--line);
               display:flex; align-items:center; gap:14px; padding:0 14px; color:var(--dim); font-size:12px; }
  .btn { background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:6px;
         padding:4px 10px; cursor:pointer; font-size:12px; }
  .btn:hover { border-color:var(--accent); }
  pre.sc { white-space:pre-wrap; font-size:12px; }
</style>
</head>
<body>
<div id="app">
  <div class="panel" id="agents">
    <h2>Agents</h2>
    <ul>
      <li class="active" data-agent="all"><span class="dot"></span>All agents</li>
      <li data-agent="builder"><span class="dot"></span>Builder</li>
      <li data-agent="reader"><span class="dot"></span>Reader</li>
      <li data-agent="writer"><span class="dot"></span>Writer</li>
    </ul>
  </div>

  <div class="panel">
    <h2 id="chattitle">Chat / Work window</h2>
    <div id="messages"></div>
    <div id="composer">
      <input id="input" placeholder="Type a command or a message… (/eval, /improve, or anything)" autocomplete="off">
      <button id="send">Send</button>
    </div>
  </div>

  <div class="panel">
    <h2>Second Brain</h2>
    <div class="tabs">
      <button class="on" data-tab="graph">Graph</button>
      <button data-tab="notes">Notes</button>
    </div>
    <canvas id="graph" style="display:block"></canvas>
    <div id="noteslist" style="display:none"></div>
  </div>

  <div id="statusbar">
    <span id="status">ready</span>
    <span id="metrics"></span>
    <button class="btn" id="evalbtn">/eval</button>
    <button class="btn" id="improvebtn">/improve</button>
    <button class="btn" id="graphbtn">refresh graph</button>
  </div>
</div>
<script>
const $ = s => document.querySelector(s);
const messages = $('#messages');
let graphData = {nodes:[],edges:[]};

function addMsg(role, text) {
  const el = document.createElement('div');
  el.className = 'msg ' + role;
  el.textContent = text;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
  return el;
}

async function post(path, body) {
  const res = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
                                 body: JSON.stringify(body||{})});
  return res.json();
}

async function send() {
  const input = $('#input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMsg('user', text);
  $('#status').textContent = 'working…';
  if (text === '/eval' || text === '/improve') {
    const r = await post('/api/' + text.slice(1));
    const el = addMsg('agent', r.text || JSON.stringify(r));
    if (r.text && r.text.length > 600) el.innerHTML = '<pre class="sc">' + escapeHtml(r.text) + '</pre>';
  } else {
    const r = await post('/api/chat', {message:text});
    addMsg('agent', r.reply || '');
  }
  $('#status').textContent = 'ready';
  refresh();
}

function escapeHtml(s){return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}

async function refresh() {
  const st = await (await fetch('/api/state')).json();
  graphData = st.graph;
  $('#metrics').textContent = st.notes + ' notes · ' + st.edges + ' links';
  drawGraph();
  renderNotes(st);
}

function renderNotes(st) {
  const list = $('#noteslist');
  list.innerHTML = '';
  (st.noteList||[]).forEach(n => {
    const d = document.createElement('div');
    d.className = 'note';
    d.innerHTML = '<div>'+escapeHtml(n.title)+'</div><div class="folder">'+escapeHtml(n.folder)+'</div>';
    list.appendChild(d);
  });
}

// --- tiny force-directed graph (no external lib) ---
function drawGraph() {
  const canvas = $('#graph'), ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr; canvas.height = rect.height * dpr;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  const W = rect.width, H = rect.height;
  const nodes = graphData.nodes.filter(n => !n.id.startsWith('tag:'));
  const tags = graphData.nodes.filter(n => n.id.startsWith('tag:'));
  const pos = {};
  nodes.forEach((n,i)=>{ const a = (i/nodes.length)*Math.PI*2;
    pos[n.id] = {x: W/2 + Math.cos(a)*(W*0.32), y: H/2 + Math.sin(a)*(H*0.32), n}; });
  tags.forEach((n,i)=>{ const a = (i/Math.max(tags.length,1))*Math.PI*2;
    pos[n.id] = {x: W/2 + Math.cos(a)*(W*0.16), y: H/2 + Math.sin(a)*(H*0.16), n}; });
  // a few relaxation iterations
  for (let iter=0; iter<40; iter++) {
    const keys = Object.keys(pos);
    for (let a=0;a<keys.length;a++) for (let b=a+1;b<keys.length;b++) {
      const A=pos[keys[a]], B=pos[keys[b]];
      let dx=B.x-A.x, dy=B.y-A.y; let d2=dx*dx+dy*dy; if(d2<1)d2=1;
      const f=28/d2; dx/=Math.sqrt(d2); dy/=Math.sqrt(d2);
      B.x+=dx*f; B.y+=dy*f; A.x-=dx*f; A.y-=dy*f;
    }
    graphData.edges.forEach(e => {
      const A=pos[e.source], B=pos[e.target]; if(!A||!B) return;
      const dx=B.x-A.x, dy=B.y-A.y; const d=Math.sqrt(dx*dx+dy*dy)||1;
      A.x+=dx*0.02*d*0.02; A.y+=dy*0.02*d*0.02;
      B.x-=dx*0.02*d*0.02; B.y-=dy*0.02*d*0.02;
    });
    keys.forEach(k=>{ const p=pos[k]; p.x=Math.max(20,Math.min(W-20,p.x)); p.y=Math.max(20,Math.min(H-20,p.y)); });
  }
  ctx.clearRect(0,0,W,H);
  graphData.edges.forEach(e => {
    const A=pos[e.source], B=pos[e.target]; if(!A||!B) return;
    ctx.strokeStyle = e.kind==='tag' ? 'rgba(139,148,158,0.25)' : 'rgba(47,129,247,0.4)';
    ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(A.x,A.y); ctx.lineTo(B.x,B.y); ctx.stroke();
  });
  Object.values(pos).forEach(p => {
    const isTag = p.n.id.startsWith('tag:');
    ctx.fillStyle = isTag ? '#2f6f4f' : '#2f81f7';
    ctx.beginPath(); ctx.arc(p.x,p.y, isTag?3:6, 0, Math.PI*2); ctx.fill();
    if (!isTag) { ctx.fillStyle='#e6edf3'; ctx.font='10px sans-serif';
      ctx.fillText(p.n.title.slice(0,18), p.x+8, p.y+3); }
  });
}

document.querySelectorAll('#agents li').forEach(li => li.onclick = () => {
  document.querySelectorAll('#agents li').forEach(x=>x.classList.remove('active'));
  li.classList.add('active');
  $('#chattitle').textContent = 'Chat / Work window — ' + li.dataset.agent;
});
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');
  const g = b.dataset.tab==='graph';
  $('#graph').style.display = g?'block':'none';
  $('#noteslist').style.display = g?'none':'block';
});
$('#send').onclick = send;
$('#input').addEventListener('keydown', e => { if (e.key==='Enter') send(); });
$('#evalbtn').onclick = async () => { $('#input').value='/eval'; send(); };
$('#improvebtn').onclick = async () => { $('#input').value='/improve'; send(); };
$('#graphbtn').onclick = refresh;
window.addEventListener('resize', drawGraph);
refresh();
</script>
</body>
</html>
"""


class _Runtime:
    def __init__(self, config: Config):
        ensure_brain(config)
        self.config = config
        self.pool = LLMPool(config)
        self.vault = Vault(config.vault_path)
        self.memory = Memory(config.memory_path)
        self.agent = Agent(config, self.pool.get("chat"), self.vault, self.memory)
        self.lock = threading.Lock()

    def state(self) -> Dict[str, Any]:
        graph = self.vault.graph()
        notes = self.vault.list_notes()
        note_list = []
        for p in notes:
            n = self.vault.parse(p)
            note_list.append({"title": n.title, "folder": n.relpath.split("/")[0]})
        return {
            "graph": graph,
            "notes": len(notes),
            "edges": len(graph["edges"]),
            "noteList": note_list,
            "autonomy": self.config.autonomy,
        }

    def chat(self, message: str) -> str:
        with self.lock:
            return self.agent.run(message).answer

    def eval(self) -> str:
        with self.lock:
            results = run_suite(self.agent, DEFAULT_SUITE)
            return render_scorecard(scorecard(results))

    def improve(self) -> str:
        with self.lock:
            report = run_improve(
                self.agent, DEFAULT_SUITE, self.config, self.vault,
                self.config.brain_dir / "prompt" / "system.md",
            )
            return render_report(report)


def _make_handler(runtime: "_Runtime"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default logging
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/" or path == "/index.html":
                self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._send(200, json.dumps(runtime.state()).encode("utf-8"))
            else:
                self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                payload = {}
            try:
                if path == "/api/chat":
                    reply = runtime.chat(str(payload.get("message", "")))
                    self._send(200, json.dumps({"reply": reply}).encode("utf-8"))
                elif path == "/api/eval":
                    self._send(200, json.dumps({"text": runtime.eval()}).encode("utf-8"))
                elif path == "/api/improve":
                    self._send(200, json.dumps({"text": runtime.improve()}).encode("utf-8"))
                else:
                    self._send(404, b'{"error":"not found"}')
            except Exception as exc:  # noqa: BLE001
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"))

    return Handler


def serve(config: Config, open_browser: bool = True) -> None:
    runtime = _Runtime(config)
    host = config.ui_host
    port = config.ui_port or 0

    server = ThreadingHTTPServer((host, port), _make_handler(runtime))
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}"
    print(f"Agent-Gen window: {url}")
    print("Ctrl+C to stop.")
    if open_browser and config.ui_auto_open:
        try:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        except Exception:  # noqa: BLE001
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        server.server_close()
