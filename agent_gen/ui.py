"""Desktop window — a local web UI served with the stdlib HTTP server.

A polished three-panel window: agents roster, chat/work window (with a LIVE
work log streaming the agent's thinking, knowledge retrieval, skills, and
tools), and the second brain (search, notes browser + reader, interactive
knowledge graph).

Endpoints:
    GET  /                the app
    GET  /api/state       graph + notes + provider info
    GET  /api/note?path=  one note (markdown + meta + resolved links)
    POST /api/chat        Server-Sent Events: live work log + answer
    POST /api/eval        scorecard
    POST /api/improve     improvement report

No CDN, no dependencies — works fully offline.
"""

from __future__ import annotations

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from . import __version__
from .agent import Agent
from .bootstrap import ensure_brain
from .config import Config
from .evals.harness import render_scorecard, run_suite, scorecard
from .evals.suite import DEFAULT_SUITE
from .gateway.registry import LLMPool
from .improve.loop import render_report, run_improve
from .memory.store import Memory
from .vault import Vault, slugify

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent-Gen</title>
<style>
  :root {
    --bg:#0a0d14; --panel:#121722; --panel2:#151b27; --line:#1e2636;
    --text:#e8edf6; --dim:#8a94a8; --faint:#5b6577;
    --brand:#6366f1; --brand2:#22d3ee; --ok:#34d399; --warn:#fbbf24;
    --err:#f87171; --purple:#a78bfa; --pink:#f472b6;
  }
  * { box-sizing:border-box; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--text);
    font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  ::-webkit-scrollbar { width:9px; height:9px; }
  ::-webkit-scrollbar-thumb { background:#263049; border-radius:8px; }
  ::-webkit-scrollbar-track { background:transparent; }

  #app { display:grid; grid-template-columns:250px 1fr 390px; grid-template-rows:56px 1fr 36px;
         height:100vh; gap:1px; background:var(--line); }

  /* ---------- header ---------- */
  #header { grid-column:1 / -1; background:linear-gradient(180deg,#121826,#10141f);
    display:flex; align-items:center; gap:14px; padding:0 16px; border-bottom:1px solid var(--line); }
  .logo { width:34px; height:34px; border-radius:10px; flex:0 0 auto;
    background:linear-gradient(135deg,var(--brand),var(--brand2));
    display:flex; align-items:center; justify-content:center; font-size:18px;
    box-shadow:0 4px 16px rgba(99,102,241,.4); }
  #title { font-weight:700; font-size:15px; letter-spacing:.01em; }
  #title small { display:block; font-weight:400; font-size:11px; color:var(--dim); }
  .pill { display:inline-flex; align-items:center; gap:6px; font-size:11.5px; font-weight:600;
    padding:3px 10px; border-radius:999px; border:1px solid var(--line); color:var(--dim); background:var(--panel2); }
  .pill b { color:var(--text); font-weight:600; }
  .pill.autonomy { color:var(--purple); border-color:rgba(167,139,250,.4); }
  #hspacer { flex:1; }

  /* ---------- panels ---------- */
  .panel { background:var(--panel); overflow:hidden; display:flex; flex-direction:column; min-height:0; }
  .panel > h2 { font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--dim);
    padding:12px 16px; margin:0; border-bottom:1px solid var(--line); display:flex; align-items:center; gap:8px; }

  /* ---------- agents ---------- */
  #agents { overflow-y:auto; padding:10px; display:flex; flex-direction:column; gap:8px; }
  .agent { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:12px;
    border:1px solid transparent; cursor:pointer; transition:.15s; }
  .agent:hover { background:var(--panel2); }
  .agent.active { background:linear-gradient(135deg,rgba(99,102,241,.16),rgba(34,211,238,.08));
    border-color:rgba(99,102,241,.5); }
  .agent .avatar { width:34px; height:34px; border-radius:10px; flex:0 0 auto;
    display:flex; align-items:center; justify-content:center; font-size:17px;
    background:var(--panel2); border:1px solid var(--line); }
  .agent.active .avatar { border-color:rgba(99,102,241,.6); }
  .agent .who { min-width:0; }
  .agent .name { font-weight:600; font-size:13.5px; }
  .agent .role { font-size:11.5px; color:var(--dim); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .dot { width:8px; height:8px; border-radius:50%; background:#3a455c; flex:0 0 auto; margin-left:auto; }
  .dot.busy { background:var(--ok); box-shadow:0 0 8px var(--ok); animation:pulse 1s infinite; }
  @keyframes pulse { 50% { opacity:.4; } }

  /* ---------- chat ---------- */
  #messages { flex:1; overflow-y:auto; padding:18px 16px; display:flex; flex-direction:column; gap:12px; }
  .msg { display:flex; gap:10px; max-width:92%; animation:fadein .25s ease; }
  @keyframes fadein { from { opacity:0; transform:translateY(4px);} }
  .msg .ava { width:30px; height:30px; border-radius:9px; flex:0 0 auto; display:flex;
    align-items:center; justify-content:center; font-size:15px; }
  .msg.user { align-self:flex-end; flex-direction:row-reverse; }
  .msg.user .ava { background:#1c2b4a; }
  .msg.agent .ava { background:linear-gradient(135deg,rgba(99,102,241,.8),rgba(34,211,238,.6)); }
  .bubble { padding:10px 14px; border-radius:14px; background:var(--panel2); border:1px solid var(--line);
    min-width:0; overflow-wrap:anywhere; }
  .msg.user .bubble { background:linear-gradient(135deg,#24345c,#1c2b4a); border-color:#2c3f66; }
  .bubble .time { font-size:10px; color:var(--faint); margin-top:6px; }
  .bubble h2,.bubble h3,.bubble h4 { margin:10px 0 6px; line-height:1.3; }
  .bubble h2 { font-size:15px; } .bubble h3 { font-size:14px; } .bubble h4 { font-size:13px; }
  .bubble p { margin:6px 0; }
  .bubble ul,.bubble ol { margin:6px 0; padding-left:20px; }
  .bubble li { margin:3px 0; }
  .bubble code { background:#0c1019; border:1px solid var(--line); border-radius:5px; padding:1px 5px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:12px; color:var(--brand2); }
  .bubble pre.code { background:#0c1019; border:1px solid var(--line); border-radius:10px; padding:12px;
    overflow-x:auto; font-size:12px; line-height:1.5; }
  .bubble blockquote { border-left:3px solid var(--brand); margin:8px 0; padding:2px 12px; color:var(--dim); }
  .bubble hr { border:0; border-top:1px solid var(--line); margin:12px 0; }
  .bubble a { color:var(--brand2); }
  .mdgap { height:6px; }

  /* work log */
  .work { display:flex; gap:9px; align-items:flex-start; padding:7px 12px; margin:0 0 4px;
    background:rgba(13,17,26,.6); border:1px solid var(--line); border-radius:10px;
    font-size:12.5px; color:#9fb2c8; animation:fadein .2s ease; }
  .work .ic { flex:0 0 auto; width:22px; height:22px; border-radius:7px; display:flex; align-items:center;
    justify-content:center; font-size:12px; }
  .work.think .ic { background:rgba(52,211,153,.14); }
  .work.skill .ic { background:rgba(167,139,250,.16); }
  .work.knowledge .ic { background:rgba(99,102,241,.16); }
  .work.tool .ic { background:rgba(251,191,36,.14); }
  .work.error .ic { background:rgba(248,113,113,.16); }
  .work .k { color:#cfe3ff; font-weight:600; }
  .work.think .k { color:var(--ok); } .work.skill .k { color:var(--purple); }
  .work.knowledge .k { color:#93a9ff; } .work.tool .k { color:var(--warn); }
  .work.error .k { color:var(--err); }

  /* typing indicator */
  .typing { display:inline-flex; gap:4px; padding:4px 2px; }
  .typing i { width:6px; height:6px; border-radius:50%; background:var(--brand2); animation:blink 1s infinite; }
  .typing i:nth-child(2){ animation-delay:.2s; } .typing i:nth-child(3){ animation-delay:.4s; }
  @keyframes blink { 50% { opacity:.25; } }

  /* empty state */
  #welcome { margin:auto; text-align:center; color:var(--dim); padding:24px; max-width:520px; }
  #welcome .big { font-size:34px; margin-bottom:10px; }
  #welcome h3 { margin:0 0 6px; color:var(--text); }
  .chips { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:16px; }
  .chip { background:var(--panel2); border:1px solid var(--line); border-radius:999px; padding:7px 13px;
    font-size:12.5px; color:var(--dim); cursor:pointer; transition:.15s; }
  .chip:hover { color:var(--text); border-color:var(--brand); }

  /* composer */
  #composer { border-top:1px solid var(--line); padding:10px 14px; background:var(--panel2); }
  #quick { display:flex; gap:6px; margin-bottom:8px; }
  #quick button { background:transparent; border:1px solid var(--line); color:var(--dim); border-radius:8px;
    padding:4px 10px; font-size:11.5px; cursor:pointer; font-family:ui-monospace,monospace; }
  #quick button:hover { color:var(--text); border-color:var(--brand); }
  #inputrow { display:flex; gap:8px; align-items:center; }
  #input { flex:1; background:#0d1220; color:var(--text); border:1px solid var(--line);
    border-radius:12px; padding:11px 14px; outline:none; font-size:14px; }
  #input:focus { border-color:var(--brand); box-shadow:0 0 0 3px rgba(99,102,241,.18); }
  #send { background:linear-gradient(135deg,var(--brand),var(--brand2)); color:#fff; border:0;
    border-radius:12px; padding:11px 22px; cursor:pointer; font-weight:600; font-size:14px; }
  #send:hover { filter:brightness(1.1); }
  #send:disabled { opacity:.5; cursor:default; }

  /* ---------- second brain ---------- */
  .searchrow { display:flex; gap:8px; padding:10px 12px; border-bottom:1px solid var(--line); }
  .searchrow input { flex:1; background:#0d1220; color:var(--text); border:1px solid var(--line);
    border-radius:9px; padding:8px 12px; outline:none; font-size:13px; }
  .searchrow input:focus { border-color:var(--brand); }
  .tabs { display:flex; border-bottom:1px solid var(--line); }
  .tabs button { flex:1; background:none; color:var(--dim); border:0; padding:11px; cursor:pointer;
    font-size:12.5px; font-weight:600; border-bottom:2px solid transparent; }
  .tabs button.on { color:var(--text); border-bottom-color:var(--brand); }
  #brainbody { position:relative; flex:1; min-height:0; }
  #noteslist { position:absolute; inset:0; overflow-y:auto; padding:10px; }
  .note { padding:10px 12px; border-radius:10px; cursor:pointer; border:1px solid transparent; }
  .note:hover { background:var(--panel2); border-color:var(--line); }
  .note .nt { font-weight:600; font-size:13px; }
  .note .nx { font-size:12px; color:var(--dim); margin-top:2px; display:-webkit-box;
    -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  .note .badge { font-size:10px; color:var(--brand2); }
  #graphwrap { position:absolute; inset:0; background:radial-gradient(circle at 50% 40%, #101624, #0a0d14); }
  #graphwrap canvas { display:block; width:100%; height:100%; cursor:grab; }
  #graphwrap canvas.panning { cursor:grabbing; }
  #tooltip { position:absolute; pointer-events:none; background:#0d1220; border:1px solid var(--line);
    border-radius:10px; padding:8px 11px; font-size:12px; display:none; max-width:220px; box-shadow:0 8px 24px rgba(0,0,0,.5); }
  #tooltip .tt { font-weight:700; color:var(--text); }
  #tooltip .tf { color:var(--brand2); font-size:10.5px; }
  #legend { position:absolute; left:10px; bottom:10px; display:flex; flex-wrap:wrap; gap:8px;
    background:rgba(13,18,32,.85); border:1px solid var(--line); border-radius:10px; padding:7px 10px; }
  #legend span { display:inline-flex; align-items:center; gap:5px; font-size:10.5px; color:var(--dim); }
  #legend i { width:8px; height:8px; border-radius:50%; display:inline-block; }
  #noteview { position:absolute; inset:0; background:var(--panel); overflow-y:auto; padding:16px; display:none; }
  #noteview h3 { margin:2px 0 10px; font-size:17px; }
  .tagrow { display:flex; flex-wrap:wrap; gap:6px; margin:10px 0; }
  .tag { background:var(--panel2); border:1px solid var(--line); border-radius:999px; padding:2px 10px;
    font-size:11px; color:var(--dim); }
  .tag.link { color:var(--brand2); cursor:pointer; }
  .tag.link:hover { border-color:var(--brand2); }
  #noteview .body { font-size:13.5px; }
  #noteview .body h1,#noteview .body h2,#noteview .body h3 { margin:12px 0 6px; }
  #noteview .body code { background:#0c1019; border:1px solid var(--line); border-radius:5px; padding:1px 5px; font-size:12px; }
  #back { background:transparent; border:1px solid var(--line); color:var(--dim); border-radius:8px;
    padding:5px 12px; cursor:pointer; font-size:12px; margin-bottom:10px; }
  #back:hover { color:var(--text); border-color:var(--brand); }

  /* ---------- status bar ---------- */
  #statusbar { grid-column:1 / -1; background:var(--panel); border-top:1px solid var(--line);
    display:flex; align-items:center; gap:14px; padding:0 14px; color:var(--dim); font-size:11.5px; }
  #status { display:flex; align-items:center; gap:7px; }
  #status i { width:7px; height:7px; border-radius:50%; background:var(--ok); display:inline-block; }
  #status.working i { background:var(--warn); animation:pulse 1s infinite; }
  .spacer { flex:1; }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <div class="logo">🧠</div>
    <div id="title">Agent-Gen<small>self-improving agent · second brain</small></div>
    <div class="pill autonomy" id="autopill">⚡ <b id="autolabel">full</b></div>
    <div class="pill" id="modelpill"></div>
    <div id="hspacer"></div>
    <div class="pill">v<span id="ver"></span></div>
  </div>

  <!-- agents -->
  <div class="panel" id="agentspanel">
    <h2>👥 Agents</h2>
    <div id="agents"></div>
  </div>

  <!-- chat -->
  <div class="panel">
    <h2 id="chattitle">💬 Chat / Work window — all agents</h2>
    <div id="messages"></div>
    <div id="composer">
      <div id="quick">
        <button data-cmd="/eval">/eval</button>
        <button data-cmd="/improve">/improve</button>
        <button data-cmd="/graph">/graph</button>
        <button data-cmd="/help">/help</button>
        <button data-cmd="/clear">clear</button>
      </div>
      <div id="inputrow">
        <input id="input" placeholder="Command or chat…  (e.g. 'search the vault for lessons', 'What is the capital of France?')" autocomplete="off">
        <button id="send">Send ➤</button>
      </div>
    </div>
  </div>

  <!-- second brain -->
  <div class="panel">
    <h2>🧠 Second Brain <span id="brainhint" style="margin-left:auto;text-transform:none;letter-spacing:0;color:var(--faint)"></span></h2>
    <div class="searchrow">
      <input id="search" placeholder="Search notes…" autocomplete="off">
    </div>
    <div class="tabs">
      <button class="on" data-tab="graph">Graph</button>
      <button data-tab="notes">Notes</button>
    </div>
    <div id="brainbody">
      <div id="graphwrap">
        <canvas id="graph"></canvas>
        <div id="tooltip"></div>
        <div id="legend"></div>
      </div>
      <div id="noteslist" style="display:none"></div>
      <div id="noteview"></div>
    </div>
  </div>

  <!-- status -->
  <div id="statusbar">
    <span id="status"><i></i><span id="statustext">ready</span></span>
    <span id="metrics"></span>
    <span class="spacer"></span>
    <span id="statver"></span>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const messages = $('#messages');
let graphData = {nodes:[],edges:[]};
let noteList = [];
let activeAgent = 'all';
let busy = false;

const AGENTS = [
  {id:'all', name:'All agents', emoji:'🧠', role:'the whole crew'},
  {id:'builder', name:'Builder', emoji:'🛠️', role:'builds & fixes code'},
  {id:'reader', name:'Reader', emoji:'📖', role:'reads & researches'},
  {id:'writer', name:'Writer', emoji:'✍️', role:'writes & summarizes'},
];
const FOLDER_COLORS = {'00-inbox':'#8a94a8','10-notes':'#6366f1','20-people':'#22d3ee',
  '30-projects':'#a78bfa','40-resources':'#34d399','90-meta':'#fbbf24','tag':'#47536b'};
const ICONS = {think:'💭',skill:'⚡',knowledge:'📚',tool:'🛠️',error:'⚠️'};

/* ---------------- helpers ---------------- */
function escapeHtml(s){return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function timeStr(){return new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});}

/* ---------------- markdown ---------------- */
function mdInline(t){
  return t
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g,'$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
}
function md(text){
  const lines = text.split('\n');
  const out = []; let inCode=false, code=[], listTag=null;
  const flushList = () => { if(listTag){ out.push('</'+listTag+'>'); listTag=null; } };
  for (const raw of lines){
    const line = escapeHtml(raw); const t = line.trim();
    if (t.startsWith('```')){
      if (!inCode){ inCode=true; code=[]; } else { out.push('<pre class="code">'+code.join('\n')+'</pre>'); inCode=false; }
      continue;
    }
    if (inCode){ code.push(line); continue; }
    if (!t){ flushList(); out.push('<div class="mdgap"></div>'); continue; }
    if (/^### /.test(t)){ flushList(); out.push('<h4>'+mdInline(t.slice(4))+'</h4>'); continue; }
    if (/^## /.test(t)){ flushList(); out.push('<h3>'+mdInline(t.slice(3))+'</h3>'); continue; }
    if (/^# /.test(t)){ flushList(); out.push('<h2>'+mdInline(t.slice(2))+'</h2>'); continue; }
    if (/^&gt; /.test(t)){ flushList(); out.push('<blockquote>'+mdInline(t.slice(5))+'</blockquote>'); continue; }
    if (/^---$/.test(t)){ flushList(); out.push('<hr>'); continue; }
    const ul = /^[-*] /.test(t), ol = /^\d+\. /.test(t);
    if (ul || ol){
      const tag = ul?'ul':'ol';
      if (listTag !== tag){ flushList(); out.push('<'+tag+'>'); listTag=tag; }
      out.push('<li>'+mdInline(t.replace(/^([-*]|\d+\.)\s+/, ''))+'</li>'); continue;
    }
    flushList(); out.push('<p>'+mdInline(t)+'</p>');
  }
  flushList();
  if (inCode) out.push('<pre class="code">'+code.join('\n')+'</pre>');
  return out.join('');
}

/* ---------------- chat ---------------- */
function addMsg(role, text){
  const el = document.createElement('div');
  el.className = 'msg ' + role;
  const ava = document.createElement('div');
  ava.className = 'ava'; ava.textContent = role==='user' ? '🙂' : '🤖';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = md(text);
  const t = document.createElement('div'); t.className='time'; t.textContent = timeStr();
  bubble.appendChild(t);
  el.appendChild(ava); el.appendChild(bubble);
  messages.appendChild(el);
  scrollDown();
  return el;
}
function addWork(kind, html){
  const el = document.createElement('div');
  el.className = 'work ' + kind;
  el.innerHTML = '<span class="ic">'+(ICONS[kind]||'•')+'</span><span>'+html+'</span>';
  messages.appendChild(el);
  scrollDown();
  return el;
}
function scrollDown(){ messages.scrollTop = messages.scrollHeight; }

let typingEl = null;
function showTyping(){
  if (typingEl) return;
  typingEl = document.createElement('div');
  typingEl.className = 'msg agent';
  typingEl.innerHTML = '<div class="ava">🤖</div><div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div>';
  messages.appendChild(typingEl); scrollDown();
}
function hideTyping(){ if (typingEl){ typingEl.remove(); typingEl=null; } }

function setBusy(b){
  busy = b;
  $('#status').className = b ? 'working' : '';
  $('#statustext').textContent = b ? 'working…' : 'ready';
  $('#send').disabled = b;
  document.querySelectorAll('#agents .agent').forEach(a => {
    if (a.dataset.id === 'all') a.querySelector('.dot').classList.toggle('busy', b);
  });
}

async function send(){
  if (busy) return;
  const input = $('#input'); const text = input.value.trim();
  if (!text) return;
  input.value = '';
  handleCommand(text);
}

function handleCommand(text){
  const cmd = text.toLowerCase();
  if (cmd === '/clear'){ messages.innerHTML=''; showWelcome(); return; }
  if (cmd === '/help'){ showHelp(); return; }
  if (cmd === '/graph'){ refresh(); addWork('knowledge','<span class="k">graph</span> refreshed'); return; }
  if (cmd === '/eval' || cmd === '/improve'){
    addMsg('user', text);
    setBusy(true); showTyping();
    post('/api/'+cmd.slice(1)).then(r => {
      hideTyping(); addMsg('agent', r.text || JSON.stringify(r)); setBusy(false); refresh();
    });
    return;
  }
  addMsg('user', text);
  setBusy(true); showTyping();
  streamChat(text).then(()=>{ setBusy(false); refresh(); });
}

function showHelp(){
  addMsg('user','/help');
  const el = document.createElement('div'); el.className='msg agent';
  el.innerHTML = '<div class="ava">🤖</div><div class="bubble"><h3>Commands</h3><ul>'+
    '<li><code>/eval</code> — run the eval suite</li>'+
    '<li><code>/improve</code> — run the self-improvement loop</li>'+
    '<li><code>/graph</code> — refresh the knowledge graph</li>'+
    '<li><code>/clear</code> — clear this chat</li>'+
    '<li>or just chat — try <code>search the vault for lessons</code></li></ul></div>';
  messages.appendChild(el); scrollDown();
}

function showWelcome(){
  if (messages.children.length) return;
  const el = document.createElement('div');
  el.id = 'welcome';
  el.innerHTML = '<div class="big">🧠</div><h3>Welcome to Agent-Gen</h3>'+
    '<div>Type a command and watch it work live — thinking, knowledge, skills, tools.</div>'+
    '<div class="chips">'+
    '<div class="chip" data-q="What is the capital of France?">What is the capital of France?</div>'+
    '<div class="chip" data-q="search the vault for lessons">search the vault for lessons</div>'+
    '<div class="chip" data-q="remember that my favorite color is blue">remember that…</div>'+
    '<div class="chip" data-q="/eval">run /eval</div>'+
    '</div>';
  messages.appendChild(el);
  el.querySelectorAll('.chip').forEach(c => c.onclick = () => { $('#input').value = c.dataset.q; send(); });
}

/* ---------------- SSE streaming ---------------- */
function handleEvent(ev){
  switch (ev.type){
    case 'mode': break;
    case 'think': addWork('think','<span class="k">think</span> · '+escapeHtml(ev.text)); break;
    case 'skill': addWork('skill','<span class="k">skill</span> · '+escapeHtml(ev.name)+
      (ev.description?' — '+escapeHtml(ev.description):'')); break;
    case 'knowledge': addWork('knowledge','<span class="k">second brain</span> · '+
      ((ev.notes&&ev.notes.length)? ev.notes.map(escapeHtml).join(', ') : '(nothing relevant)')); break;
    case 'tool_start': addWork('tool','<span class="k">tool</span> · '+escapeHtml(ev.name)+' …'); break;
    case 'tool_end': addWork('tool','<span class="k">tool</span> · '+escapeHtml(ev.name)+' ✓'); break;
    case 'answer': hideTyping(); addMsg('agent', ev.text); break;
    case 'error': hideTyping(); addWork('error','<span class="k">error</span> · '+escapeHtml(ev.text)); break;
    case 'done': hideTyping();
      $('#statustext').textContent = 'ready · '+(ev.steps||0)+' step(s)';
      break;
  }
}
async function streamChat(text){
  const res = await fetch('/api/chat', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({message:text, agent:activeAgent})});
  const reader = res.body.getReader();
  const dec = new TextDecoder(); let buf = '';
  while (true){
    const {done, value} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {stream:true});
    let idx;
    while ((idx = buf.indexOf('\n\n')) >= 0){
      const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
      const line = chunk.split('\n').find(l => l.startsWith('data: '));
      if (!line) continue;
      try { handleEvent(JSON.parse(line.slice(6))); } catch(e){}
    }
  }
}
async function post(path, body){
  const res = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body||{})});
  return res.json();
}

/* ---------------- second brain ---------------- */
function folderColor(f){ return FOLDER_COLORS[f] || '#8a94a8'; }

async function refresh(){
  const st = await (await fetch('/api/state')).json();
  graphData = st.graph || {nodes:[],edges:[]};
  noteList = st.noteList || [];
  $('#metrics').textContent = noteList.length + ' notes · ' + graphData.edges.length + ' links';
  $('#brainhint').textContent = noteList.length + ' notes';
  $('#autolabel').textContent = st.autonomy || 'full';
  const [p, m] = st.route || ['',''];
  const llm = st.llm || '';
  $('#modelpill').textContent = llm === 'mock' ? 'offline mock LLM' : (p||'') + (m ? ' / ' + m : '');
  $('#ver').textContent = st.version || ''; $('#statver').textContent = st.version ? 'agent-gen '+st.version : '';
  layoutDirty = true;
  drawGraph(); renderNotes(); renderLegend();
}

function renderNotes(filter){
  const list = $('#noteslist'); list.innerHTML='';
  const q = (filter||'').toLowerCase();
  noteList.filter(n => !q || n.title.toLowerCase().includes(q) || (n.excerpt||'').toLowerCase().includes(q))
    .forEach(n => {
      const d = document.createElement('div');
      d.className = 'note';
      d.innerHTML = '<div class="nt">'+escapeHtml(n.title)+'</div>'+
        '<div class="nx">'+escapeHtml(n.excerpt||'')+'</div>'+
        '<div class="badge">'+escapeHtml(n.folder)+'</div>';
      d.onclick = () => openNote(n.relpath);
      list.appendChild(d);
    });
  if (!list.children.length) list.innerHTML = '<div style="color:var(--dim);padding:16px;text-align:center">no notes</div>';
}

async function openNote(relpath){
  const data = await (await fetch('/api/note?path='+encodeURIComponent(relpath))).json();
  const v = $('#noteview');
  v.style.display = 'block';
  let html = '<button id="back">← back</button>';
  html += '<h3>'+escapeHtml(data.title||relpath)+'</h3>';
  html += '<div class="tagrow">'+
    '<span class="tag">📁 '+escapeHtml(data.folder||'')+'</span>'+
    (data.tags||[]).map(t=>'<span class="tag">#'+escapeHtml(t)+'</span>').join('')+
    (data.meta && data.meta.language ? '<span class="tag">🌐 '+escapeHtml(data.meta.language)+'</span>' : '')+
    '</div>';
  if (data.links && data.links.length){
    html += '<div class="tagrow">'+data.links.map(l =>
      l.relpath ? '<span class="tag link" data-path="'+escapeHtml(l.relpath)+'">🔗 '+escapeHtml(l.title)+'</span>'
                : '<span class="tag">'+escapeHtml(l.title)+'</span>').join('')+'</div>';
  }
  html += '<div class="body">'+md(data.body||'')+'</div>';
  v.innerHTML = html;
  v.querySelector('#back').onclick = closeNote;
  v.querySelectorAll('.tag.link').forEach(t => t.onclick = () => openNote(t.dataset.path));
}
function closeNote(){ $('#noteview').style.display='none'; }

function renderLegend(){
  const folders = ['10-notes','20-people','30-projects','40-resources','00-inbox','90-meta'];
  $('#legend').innerHTML = folders.map(f =>
    '<span><i style="background:'+folderColor(f)+'"></i>'+f+'</span>').join('')+
    '<span><i style="background:#47536b;width:6px;height:6px"></i>tag</span>';
}

/* ---------------- graph (pan / zoom / hover / click) ---------------- */
const canvas = $('#graph'), ctx = canvas.getContext('2d');
const tooltip = $('#tooltip');
let view = {scale:1, tx:0, ty:0}, layoutDirty = true;
let world = {pos:{}, edges:[]};
let hoverNode = null, drag = null;

function computeLayout(){
  world.pos = {}; world.edges = graphData.edges || [];
  const nodes = (graphData.nodes||[]).filter(n=>!n.id.startsWith('tag:'));
  const tags = (graphData.nodes||[]).filter(n=>n.id.startsWith('tag:'));
  const W = canvas.clientWidth, H = canvas.clientHeight;
  nodes.forEach((n,i)=>{ const a=(i/Math.max(nodes.length,1))*Math.PI*2;
    world.pos[n.id] = {x:Math.cos(a)*(W*0.30), y:Math.sin(a)*(H*0.30), n}; });
  tags.forEach((n,i)=>{ const a=(i/Math.max(tags.length,1))*Math.PI*2;
    world.pos[n.id] = {x:Math.cos(a)*(W*0.13), y:Math.sin(a)*(H*0.13), n}; });
  for (let it=0; it<50; it++){
    const keys = Object.keys(world.pos);
    for (let a=0;a<keys.length;a++) for (let b=a+1;b<keys.length;b++){
      const A=world.pos[keys[a]], B=world.pos[keys[b]];
      let dx=B.x-A.x, dy=B.y-A.y; let d2=dx*dx+dy*dy; if(d2<1)d2=1;
      const f=2000/d2; const d=Math.sqrt(d2);
      dx/=d; dy/=d; B.x+=dx*f; B.y+=dy*f; A.x-=dx*f; A.y-=dy*f;
    }
    world.edges.forEach(e=>{
      const A=world.pos[e.source], B=world.pos[e.target]; if(!A||!B) return;
      const dx=B.x-A.x, dy=B.y-A.y; const d=Math.sqrt(dx*dx+dy*dy)||1;
      const pull=0.002*d;
      A.x+=dx*pull; A.y+=dy*pull; B.x-=dx*pull; B.y-=dy*pull;
    });
  }
  // normalize to a centered bounding box
  let minx=1e9,miny=1e9,maxx=-1e9,maxy=-1e9;
  Object.values(world.pos).forEach(p=>{ minx=Math.min(minx,p.x);miny=Math.min(miny,p.y);maxx=Math.max(maxx,p.x);maxy=Math.max(maxy,p.y); });
  const cx=(minx+maxx)/2, cy=(miny+maxy)/2;
  Object.values(world.pos).forEach(p=>{ p.x-=cx; p.y-=cy; });
  layoutDirty = false;
}
function degree(id){ let d=0; world.edges.forEach(e=>{ if(e.source===id||e.target===id) d++; }); return d; }
function screenOf(p){ return {x:p.x*view.scale+view.tx, y:p.y*view.scale+view.ty}; }
function worldOf(sx,sy){ return {x:(sx-view.tx)/view.scale, y:(sy-view.ty)/view.scale}; }

function drawGraph(){
  if (!canvas.clientWidth) return;
  const dpr = window.devicePixelRatio||1;
  canvas.width = canvas.clientWidth*dpr; canvas.height = canvas.clientHeight*dpr;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  const W = canvas.clientWidth, H = canvas.clientHeight;
  if (layoutDirty) computeLayout();
  ctx.clearRect(0,0,W,H);
  // edges
  world.edges.forEach(e=>{
    const A=world.pos[e.source], B=world.pos[e.target]; if(!A||!B) return;
    const a=screenOf(A), b=screenOf(B);
    const isTag = e.target.startsWith('tag:') || e.source.startsWith('tag:');
    ctx.strokeStyle = isTag ? 'rgba(139,148,168,.22)' : 'rgba(99,102,241,.42)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
  });
  // nodes
  Object.values(world.pos).forEach(p=>{
    const s = screenOf(p);
    const isTag = p.n.id.startsWith('tag:');
    const d = degree(p.n.id);
    const r = isTag ? 3.5*view.scale : Math.min(14, 5+Math.sqrt(d)*2.2)*view.scale;
    const color = folderColor(p.n.folder);
    ctx.beginPath(); ctx.arc(s.x,s.y,Math.max(2,r),0,Math.PI*2);
    ctx.fillStyle = color;
    ctx.globalAlpha = hoverNode === p.n.id ? 1 : 0.92;
    ctx.fill(); ctx.globalAlpha = 1;
    if (hoverNode === p.n.id){
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke();
    }
    if (!isTag && view.scale > 0.5){
      ctx.fillStyle = '#e8edf6'; ctx.font = (11*view.scale)+'px sans-serif';
      ctx.fillText(p.n.title.slice(0,16), s.x + r + 4, s.y + 3);
    }
  });
}

function hitNode(mx,my){
  let best=null, bestD=22*view.scale;
  Object.values(world.pos).forEach(p=>{
    const s=screenOf(p);
    const dx=s.x-mx, dy=s.y-my; const d=Math.sqrt(dx*dx+dy*dy);
    if (d < bestD){ bestD=d; best=p.n; }
  });
  return best;
}
function showTooltip(n,mx,my){
  tooltip.style.display='block';
  tooltip.innerHTML = '<div class="tt">'+escapeHtml(n.title)+'</div>'+
    '<div class="tf">'+escapeHtml(n.folder||'')+' · '+degree(n.id)+' link(s)'+(n.tags&&n.tags.length? ' · #'+n.tags.join(' #'):'')+'</div>';
  const r = $('#graphwrap').getBoundingClientRect();
  tooltip.style.left = (mx - r.left + 14)+'px'; tooltip.style.top = (my - r.top + 12)+'px';
  const tr = tooltip.getBoundingClientRect();
  if (mx - r.left + 14 + tr.width > r.width) tooltip.style.left = (mx - r.left - tr.width - 14)+'px';
}
canvas.addEventListener('mousedown', e=>{
  drag = {x:e.offsetX, y:e.offsetY, moved:false, lastX:e.offsetX, lastY:e.offsetY};
  canvas.classList.add('panning');
});
canvas.addEventListener('mousemove', e=>{
  if (drag){
    const dx=e.offsetX-drag.lastX, dy=e.offsetY-drag.lastY;
    if (Math.abs(e.offsetX-drag.x)+Math.abs(e.offsetY-drag.y) > 4) drag.moved = true;
    if (drag.moved){ view.tx+=dx; view.ty+=dy; }
    drag.lastX=e.offsetX; drag.lastY=e.offsetY;
    drawGraph(); return;
  }
  const n = hitNode(e.offsetX, e.offsetY);
  if (n){ hoverNode=n.id; showTooltip(n,e.offsetX,e.offsetY); canvas.style.cursor='pointer'; }
  else { hoverNode=null; tooltip.style.display='none'; canvas.style.cursor='grab'; }
  drawGraph();
});
canvas.addEventListener('mouseup', e=>{
  canvas.classList.remove('panning');
  if (drag && !drag.moved){
    const n = hitNode(e.offsetX,e.offsetY);
    if (n && !n.id.startsWith('tag:') && n.relpath) openNote(n.relpath);
  }
  drag=null;
});
canvas.addEventListener('mouseleave', ()=>{ hoverNode=null; tooltip.style.display='none'; drag=null; });
canvas.addEventListener('wheel', e=>{
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 0.9;
  const ns = Math.min(3, Math.max(0.35, view.scale*factor));
  const mx=e.offsetX, my=e.offsetY;
  view.tx = mx - (mx-view.tx)*(ns/view.scale);
  view.ty = my - (my-view.ty)*(ns/view.scale);
  view.scale = ns;
  drawGraph();
},{passive:false});

/* ---------------- wiring ---------------- */
function renderAgents(){
  $('#agents').innerHTML = AGENTS.map(a =>
    '<div class="agent'+(a.id==='all'?' active':'')+'" data-id="'+a.id+'">'+
    '<div class="avatar">'+a.emoji+'</div><div class="who"><div class="name">'+a.name+'</div>'+
    '<div class="role">'+a.role+'</div></div><span class="dot"></span></div>').join('');
  document.querySelectorAll('#agents .agent').forEach(el => el.onclick = () => {
    document.querySelectorAll('#agents .agent').forEach(x=>x.classList.remove('active'));
    el.classList.add('active');
    activeAgent = el.dataset.id;
    const a = AGENTS.find(x=>x.id===activeAgent);
    $('#chattitle').textContent = '💬 Chat / Work window — ' + a.name;
  });
}
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');
  $('#graphwrap').style.display = b.dataset.tab==='graph'?'block':'none';
  $('#noteslist').style.display = b.dataset.tab==='notes'?'block':'none';
  closeNote();
  if (b.dataset.tab==='graph'){ layoutDirty=true; drawGraph(); }
});
$('#search').addEventListener('input', e => renderNotes(e.target.value));
$('#send').onclick = send;
$('#input').addEventListener('keydown', e => { if (e.key==='Enter') send(); });
document.querySelectorAll('#quick button').forEach(b => b.onclick = () => {
  const c = b.dataset.cmd;
  if (c==='/clear') handleCommand('/clear'); else if (c==='/help') handleCommand('/help');
  else { $('#input').value = c; send(); }
});
document.addEventListener('keydown', e => {
  if (e.key==='/' && document.activeElement !== $('#input') && document.activeElement !== $('#search')){ e.preventDefault(); $('#input').focus(); }
});
window.addEventListener('resize', ()=>{ layoutDirty=true; drawGraph(); });
renderAgents();
showWelcome();
$('#input').focus();
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
            note_list.append({
                "title": n.title,
                "folder": n.relpath.split("/")[0],
                "relpath": n.relpath,
                "excerpt": " ".join(n.body.split())[:140],
                "tags": n.tags,
            })
        provider, model = self.config.route("chat")
        llm_name = getattr(self.agent.llm, "name", type(self.agent.llm).__name__)
        return {
            "graph": graph,
            "notes": len(notes),
            "edges": len(graph["edges"]),
            "noteList": note_list,
            "autonomy": self.config.autonomy,
            "provider": provider,
            "model": model,
            "llm": llm_name,
            "route": [provider, model],
            "version": __version__,
        }

    def note(self, relpath: str) -> Dict[str, Any]:
        n = self.vault.read_note(relpath)
        if n is None:
            return {"error": "not found", "relpath": relpath}
        index = self.vault.note_titles()
        links = []
        for title in n.links:
            links.append({"title": title, "relpath": index.get(slugify(title))})
        return {
            "title": n.title,
            "relpath": n.relpath,
            "folder": n.relpath.split("/")[0],
            "body": n.body,
            "tags": n.tags,
            "links": links,
            "meta": n.meta,
        }

    def chat_stream(self, message: str, emit: Callable[[Dict[str, Any]], None],
                    agent: Optional[str] = None) -> None:
        def paced(ev: Dict[str, Any]) -> None:
            emit(ev)
            if ev.get("type") not in ("done", "error"):
                time.sleep(0.05)
        with self.lock:
            self.memory.log("ui_chat", {"message": message, "agent": agent})
            self.agent.run_stream(message, emit=paced)

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
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._send(200, json.dumps(runtime.state(), ensure_ascii=False).encode("utf-8"))
            elif path == "/api/note":
                qs = parse_qs(parsed.query)
                relpath = (qs.get("path") or [""])[0]
                self._send(200, json.dumps(runtime.note(relpath), ensure_ascii=False).encode("utf-8"))
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

            if path == "/api/chat":
                message = str(payload.get("message", ""))
                agent = str(payload.get("agent", "") or "")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                def emit(ev: Dict[str, Any]) -> None:
                    try:
                        data = json.dumps(ev, ensure_ascii=False)
                        self.wfile.write(("data: " + data + "\n\n").encode("utf-8"))
                        self.wfile.flush()
                    except OSError:
                        pass

                try:
                    runtime.chat_stream(message, emit, agent=agent)
                except Exception as exc:  # noqa: BLE001
                    emit({"type": "error", "text": str(exc)})
                self.close_connection = True
                return

            try:
                if path == "/api/eval":
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
