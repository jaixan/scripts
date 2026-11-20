#!/usr/bin/env python3
"""Scan a zip of exam screenshots for signs of AI tool use.

Usage:
    python3 checkexam.py "Student Name.zip" [more.zip ...] [-o reports/] [-j 8]

Also available as the "Détecter IA dans ZIP" Finder Quick Action.

Each screenshot is OCR'd with Apple's Vision framework (via ocr.swift, compiled
on first run), the text is matched against tiered rules, and a self-contained
HTML report is written per zip. OCR results are cached, so re-running after
tweaking the rules is instant.

The report is evidence for a human to review, not a verdict: OCR can't see
inline code completions, a phone next to the keyboard, or text it misreads.
"""

import argparse
import base64
import csv
import difflib
import hashlib
import html
import json
import os
import queue
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OCR_SRC = HERE / "ocr.swift"
OCR_BIN = HERE / ".build" / "ocr"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".tif", ".tiff", ".bmp", ".gif"}

HIGH, MEDIUM, INFO = 3, 2, 1
SEVERITY_NAME = {HIGH: "high", MEDIUM: "medium", INFO: "info"}

# --------------------------------------------------------------------------
# Detection rules. Patterns run on each OCR line after normalize(): lowercase,
# accents stripped, whitespace collapsed. Keep them tolerant of OCR noise.
# --------------------------------------------------------------------------

AI_DOMAINS = (
    r"chat\s?gpt\.com|chat\.openai\.com|claude\.ai|gemini\.google\.com|bard\.google\.com"
    r"|aistudio\.google\.com|notebooklm\.google|copilot\.microsoft\.com|copilot\.cloud\.microsoft"
    r"|perplexity\.ai|chat\.deepseek\.com|deepseek\.com|chat\.mistral\.ai|grok\.com|x\.ai"
    r"|poe\.com|phind\.com|you\.com|blackbox\.ai|huggingface\.co/chat|chat\.qwen\.ai|kimi\.com"
    r"|meta\.ai|character\.ai|quillbot\.com|cursor\.com|v0\.dev|bolt\.new|lovable\.dev|t3\.chat"
    r"|duck\.ai|chatgpt\.fr|chatgptfrancais|gptgo|talkai|monica\.im"
)

# Names of AI products; used for the generic "mentioned" / "label" rules.
AI_NAMES = (
    r"chat\s?gpt|openai|claude|anthropic|gemini|copilot|perplexity|deepseek|mistral ai"
    r"|grok|codeium|windsurf|tabnine|qwen|huggingchat|notebooklm|quillbot|blackbox ai"
)

# Desktop apps that count as AI use when they are the frontmost app.
AI_APPS = re.compile(
    r"^(chat\s?gpt|claude|gemini|copilot|perplexity|cursor|windsurf|deepseek|le chat"
    r"|msty|lm studio|ollama|poe|jan|grok|codex)$"
)

RULES = [
    # id, severity, label, pattern -- first match wins for each line.
    # Buttons and menu entries that exist whether or not AI was used.
    ("ambient-ai-ui", INFO, "AI menu entries / buttons (ambient UI)",
     r"add (?:file|folder|selection) to chat|open inline chat|try out the new agents window"
     r"|open in agents window|agent quick input|interroger gemini|ask chatgpt|demander a chatgpt"
     r"|^\W*\w?\W*(?:mode ia|ai mode)\W*$|afficher : mode ia|faites-en plus avec le mode"),
    ("ai-website", HIGH, "AI website visible",
     rf"(?<![\w.])(?:https?://)?(?:www\.)?(?:{AI_DOMAINS})\b"),
    # Text that only shows up inside an AI chat app or an actual AI answer.
    ("ai-chat-ui", HIGH, "AI chat interface / AI answer text",
     r"chat\s?gpt (?:can make mistakes|peut (?:faire|commettre) des erreurs)"
     r"|message chat\s?gpt|envoyer un message a chat\s?gpt"
     r"|claude (?:can make mistakes|peut (?:faire|commettre) des erreurs)|reply to claude|repondre a claude"
     r"|gemini (?:can make mistakes|may display|peut (?:faire|afficher|commettre))"
     r"|copilot (?:may make mistakes|peut faire des erreurs)|ai.generated content may be incorrect"
     r"|contenu genere par (?:l'?)?ia|as an ai language model|en tant que modele de langage"
     r"|regenerate(?: response)?|regenerer la reponse|used \d+ references?|\d+ references? utilisees?"
     r"|copilot is (?:working|thinking)"),
    # Empty prompt boxes and assistant panels: the tool was on screen, maybe not used.
    ("ai-panel", MEDIUM, "AI prompt box / assistant panel / AI search answer visible",
     r"\w{2,4}t w\w{0,3} copilot|copilot chat|agent mode|mode agent"
     r"|ask anything|poser une question|how can i help(?: you)? today|comment puis-je vous aider"
     r"|que puis-je faire pour vous|saisissez une requete|enter a prompt here|discuter avec gemini"
     r"|ask or edit in context|ask copilot|demander a copilot|edits? with copilot"
     r"|build with agent|ask about your code|add context\.{0,3}$"
     r"|apercus? (?:ia|de l'ia)|ai overview|\bmode ia\b|\bai mode\b|gemini dans chrome|gemini in chrome"),
]
RULES = [(rid, sev, label, re.compile(pat)) for rid, sev, label, pat in RULES]
AI_NAME_RE = re.compile(rf"\b(?:{AI_NAMES})\b")

# Chrome's always-visible "Ask Gemini" toolbar button. OCR mangles it a lot
# ("Demaoder à Gemini", "sander 3 Gemini"), so match any short line ending in Gemini.
TOOLBAR_GEMINI = re.compile(r"^\W*(?:\w+\W*){0,2}\W*gemini\W*$")

URL_RE = re.compile(
    r"\b((?:[a-z0-9-]{2,}\.)+(?:com|org|net|ca|io|ai|fr|dev|app|edu|gov|co|me|so|gg|new|chat"
    r"|microsoft|google|qc\.ca))\b(?![.@])"
)
NOT_DOMAINS = re.compile(r"(?:^|\.)(?:\w*exa\w{2,4}\.com|x?code\.app)$")


def normalize(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


MAC_MENU_WORDS = re.compile(r"^(?:file|fichier|edit|edition|view|presentation|window|fenetre|help|aide)$")


def frontmost_app(lines):
    """The app name in the macOS menu bar, i.e. the leftmost text near the top.

    Returns None when the frame has no macOS menu bar (Windows, fullscreen apps).
    """
    top = [ln for ln in lines if ln["y"] < 0.03]
    words = re.findall(r"[a-z]+", normalize(" ".join(ln["t"] for ln in top)))
    if sum(1 for w in words if MAC_MENU_WORDS.match(w)) < 2:
        return None
    cands = [ln for ln in top if ln["x"] < 0.2 and re.search(r"[A-Za-z]{2}", ln["t"])]
    if not cands:
        return None
    return min(cands, key=lambda ln: ln["x"])["t"].strip()


def analyze_frame(lines):
    """Return (hits, app, domains); hits are (severity, rule_id, label, text, box)."""
    hits = []
    app = frontmost_app(lines)
    if app and AI_APPS.match(normalize(app)):
        menu_line = next(ln for ln in lines if ln["t"].strip() == app)
        hits.append((HIGH, "ai-app-frontmost", "AI app in foreground", app, menu_line))

    domains = set()
    for ln in lines:
        norm = normalize(ln["t"])
        for m in URL_RE.finditer(norm):
            if not NOT_DOMAINS.search(m.group(1)):
                domains.add(m.group(1))
        if TOOLBAR_GEMINI.match(norm) and len(norm) <= 26:
            continue
        matched = False
        for rid, sev, label, pat in RULES:
            if pat.search(norm):
                hits.append((sev, rid, label, ln["t"], ln))
                matched = True
                break
        if matched or not AI_NAME_RE.search(norm):
            continue
        # A bare product name is almost always an app icon or menu label;
        # a name inside real text is worth a look.
        if len(re.findall(r"[a-z]{2,}", norm)) <= 2:
            hits.append((INFO, "ai-label", "AI app icon / label visible", ln["t"], ln))
        else:
            hits.append((MEDIUM, "ai-mention", "AI product mentioned in text", ln["t"], ln))
    return hits, app, domains


# --------------------------------------------------------------------------
# OCR
# --------------------------------------------------------------------------

def ensure_ocr_binary():
    if OCR_BIN.exists() and OCR_BIN.stat().st_mtime >= OCR_SRC.stat().st_mtime:
        return OCR_BIN
    if not shutil.which("swiftc"):
        sys.exit("swiftc not found. Install the Xcode command line tools: xcode-select --install")
    print("Compiling OCR helper (first run only)…", file=sys.stderr)
    OCR_BIN.parent.mkdir(exist_ok=True)
    subprocess.run(["swiftc", "-O", str(OCR_SRC), "-o", str(OCR_BIN)], check=True)
    return OCR_BIN


def run_ocr(paths, jobs, fast, on_result):
    """OCR paths across `jobs` processes (Vision serializes within a process)."""
    binary = ensure_ocr_binary()
    chunks = [paths[i::jobs] for i in range(jobs) if paths[i::jobs]]
    out = queue.Queue()
    procs = []
    for chunk in chunks:
        p = subprocess.Popen([str(binary)] + (["--fast"] if fast else []),
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p.stdin.write("\n".join(chunk) + "\n")
        p.stdin.close()
        procs.append(p)

    def pump(proc):
        for line in proc.stdout:
            out.put(line)
        out.put(None)

    for p in procs:
        threading.Thread(target=pump, args=(p,), daemon=True).start()
    done_procs = 0
    while done_procs < len(procs):
        line = out.get()
        if line is None:
            done_procs += 1
        elif line.strip():
            on_result(json.loads(line))
    for p in procs:
        if p.wait() != 0:
            raise RuntimeError(f"OCR helper exited with code {p.returncode}")


# --------------------------------------------------------------------------
# Frames, timing and grouping
# --------------------------------------------------------------------------

TS_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _T]?(\d{2})[-:._h](\d{2})[-:._m](\d{2})")


def frame_time(name, zinfo):
    m = TS_RE.search(Path(name).name)
    if m:
        try:
            return datetime(*map(int, m.groups()))
        except ValueError:
            pass
    if zinfo.date_time[0] > 1980:
        return datetime(*zinfo.date_time)
    return None


def merge_ocr_variants(counts, threshold=0.84):
    """Fold OCR typos ("nusicbrainz.org") into the most frequent spelling.

    `counts` maps text -> set of frame indexes; returns the same shape.
    """
    merged = {}
    for key in sorted(counts, key=lambda k: -len(counts[k])):
        target = next((m for m in merged if difflib.SequenceMatcher(None, key, m).ratio() >= threshold), None)
        if target:
            merged[target] |= counts[key]
        else:
            merged[key] = set(counts[key])
    return merged


def fmt_dur(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}" if h else (f"{m} min {s:02d}s" if m else f"{s}s")


def group_episodes(frames, interval):
    """Merge nearby frames with hits of the same severity into episodes.

    OCR misses a word now and then, so short runs of clean frames don't split an episode.
    """
    max_gap = max(6 * interval, 30)
    episodes = []
    open_eps = {}
    for idx, fr in enumerate(frames):
        for sev in sorted({h[0] for h in fr["hits"]}):
            ep = open_eps.get(sev)
            close = ep and (
                (fr["time"] and ep["end_time"] and (fr["time"] - ep["end_time"]).total_seconds() <= max_gap)
                or (not fr["time"] and idx - ep["last_idx"] <= 6)
            )
            if not close:
                ep = {"severity": sev, "labels": Counter(), "frames": [],
                      "texts": Counter(), "start_time": fr["time"]}
                open_eps[sev] = ep
                episodes.append(ep)
            ep["frames"].append(idx)
            ep["last_idx"] = idx
            ep["end_time"] = fr["time"]
            for h in fr["hits"]:
                if h[0] == sev:
                    ep["labels"][h[2]] += 1
                    ep["texts"][h[3].strip()] += 1
    for ep in episodes:
        ep["label"] = " · ".join(label for label, _ in ep["labels"].most_common())
    episodes.sort(key=lambda e: (-e["severity"], e["frames"][0]))
    return episodes


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e3e2dd;
--high:#c62828;--high-bg:#fdecea;--med:#b26a00;--med-bg:#fff4e0;--info:#4a5f80;--info-bg:#eaf0f8;--ok:#2e7d32;--ok-bg:#e8f5e9}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#21211f;--fg:#ecebe6;--muted:#a09f99;--line:#33332f;
--high:#ff6b5e;--high-bg:#3a1d1a;--med:#f0a640;--med-bg:#35290f;--info:#9db4d8;--info-bg:#1e2633;--ok:#7bc67e;--ok-bg:#1b2e1c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:32px 16px 64px}h1{font-size:26px;margin:0 0 4px}
h2{font-size:18px;margin:36px 0 12px}.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.verdict{padding:18px 20px;border-radius:10px;margin:20px 0;border:1px solid}.verdict b{font-size:19px;display:block;margin-bottom:4px}
.v-high{background:var(--high-bg);border-color:var(--high);color:var(--fg)}.v-high b{color:var(--high)}
.v-medium{background:var(--med-bg);border-color:var(--med)}.v-medium b{color:var(--med)}
.v-ok{background:var(--ok-bg);border-color:var(--ok)}.v-ok b{color:var(--ok)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.stat .n{font-size:22px;font-weight:600}.stat .l{color:var(--muted);font-size:13px}
.tag{display:inline-block;font-size:12px;font-weight:600;padding:1px 8px;border-radius:99px;text-transform:uppercase;letter-spacing:.03em}
.t-high{background:var(--high-bg);color:var(--high)}.t-medium{background:var(--med-bg);color:var(--med)}.t-info{background:var(--info-bg);color:var(--info)}
.ep{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:16px;margin-bottom:14px}
@media (max-width:760px){.ep{grid-template-columns:1fr}}
.shot{position:relative;cursor:zoom-in;border-radius:6px;overflow:hidden;border:1px solid var(--line);align-self:start}
.shot img{display:block;width:100%}.shot .box{position:absolute;border:2px solid var(--high);border-radius:3px;box-shadow:0 0 0 2000px rgba(0,0,0,.18)}
.shot.big{position:fixed;inset:2vh 2vw;z-index:10;cursor:zoom-out;background:#000;display:flex;align-items:center;border:0;border-radius:0}
.shot.big .inner{position:relative;margin:auto;max-width:96vw;max-height:96vh}.shot.big img{max-height:96vh;width:auto;max-width:96vw}
.inner{position:relative}
.texts{margin:8px 0 0;padding:0;list-style:none;font:13px/1.45 ui-monospace,Menlo,monospace}.texts li{padding:3px 0;border-top:1px dashed var(--line);word-break:break-word}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:500}td.num{text-align:right;font-variant-numeric:tabular-nums}tr.ai td{color:var(--high);font-weight:600}
.timeline{position:relative;height:34px;background:var(--card);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.timeline span{position:absolute;top:0;bottom:0;min-width:2px}.tl-high{background:var(--high)}.tl-medium{background:var(--med)}.tl-gap{background:repeating-linear-gradient(45deg,var(--line),var(--line) 3px,transparent 3px,transparent 6px)}
.tl-axis{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-top:4px}
.legend{font-size:13px;color:var(--muted);margin-top:6px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 12px;vertical-align:-1px}
.wrap{overflow-x:auto}
"""

JS = """document.querySelectorAll('.shot').forEach(s=>s.addEventListener('click',()=>s.classList.toggle('big')));
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.shot.big').forEach(s=>s.classList.remove('big'))});"""


def esc(s):
    return html.escape(str(s))


def shot_html(img_bytes, ext, boxes):
    mime = {"jpg": "jpeg", "tif": "tiff"}.get(ext, ext)
    b64 = base64.b64encode(img_bytes).decode()
    overlays = "".join(
        f'<div class="box" style="left:{b["x"]*100:.2f}%;top:{b["y"]*100:.2f}%;'
        f'width:{b["w"]*100:.2f}%;height:{b["h"]*100:.2f}%"></div>' for b in boxes)
    return f'<div class="shot"><div class="inner"><img src="data:image/{mime};base64,{b64}" alt="">{overlays}</div></div>'


def build_report(student, frames, episodes, gaps, apps, domains, label_counts, interval, read_image, ocr_note):
    times = [f["time"] for f in frames if f["time"]]
    start, end = (min(times), max(times)) if times else (None, None)
    span = (end - start).total_seconds() if times else 0
    high = [e for e in episodes if e["severity"] == HIGH]
    med = [e for e in episodes if e["severity"] == MEDIUM]

    if high:
        vclass, vtitle = "v-high", "AI use detected — review the evidence below"
        vtext = (f"{len(high)} high-confidence episode(s) across "
                 f"{sum(len(e['frames']) for e in high)} screenshot(s): an AI website, AI chat interface or AI app was on screen.")
    elif med:
        vclass, vtitle = "v-medium", "AI tools visible — manual review recommended"
        vtext = (f"No AI conversation was clearly visible, but {len(med)} episode(s) show AI panels, "
                 "AI search answers or AI products mentioned in on-screen text.")
    else:
        vclass, vtitle = "v-ok", "No evidence of AI use found"
        vtext = "None of the OCR'd text matched an AI website, chat interface or assistant panel."

    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{esc(student)} – AI check</title><style>{CSS}</style></head><body><main>"]
    out.append(f"<h1>{esc(student)}</h1><div class='muted'>"
               + (f"{start:%Y-%m-%d %H:%M:%S} → {end:%H:%M:%S} · {fmt_dur(span)} · " if start else "")
               + f"{len(frames)} screenshots · {esc(ocr_note)}</div>")
    out.append(f"<div class='verdict {vclass}'><b>{esc(vtitle)}</b>{esc(vtext)}</div>")

    out.append("<div class='stats'>")
    for n, l in [(len(high), "high-confidence episodes"), (len(med), "medium episodes"),
                 (sum(1 for f in frames if any(h[0] >= MEDIUM for h in f["hits"])), "flagged screenshots"),
                 (len(gaps), "capture gaps"), (fmt_dur(interval) if interval else "–", "capture interval")]:
        out.append(f"<div class='stat'><div class='n'>{esc(n)}</div><div class='l'>{esc(l)}</div></div>")
    out.append("</div>")

    if start and span > 0:
        out.append("<h2>Timeline</h2><div class='timeline'>")
        pos = lambda t: (t - start).total_seconds() / span * 100
        for g in gaps:
            out.append(f"<span class='tl-gap' style='left:{pos(g[0]):.3f}%;width:{max(pos(g[1]) - pos(g[0]), .2):.3f}%' title='No screenshots {g[0]:%H:%M:%S}–{g[1]:%H:%M:%S}'></span>")
        for f in frames:
            sev = max((h[0] for h in f["hits"]), default=0)
            if sev >= MEDIUM and f["time"]:
                out.append(f"<span class='tl-{SEVERITY_NAME[sev]}' style='left:{pos(f['time']):.3f}%' title='{f['time']:%H:%M:%S} {esc(f['name'])}'></span>")
        out.append(f"</div><div class='tl-axis'><span>{start:%H:%M}</span><span>{(start + (end - start) / 2):%H:%M}</span><span>{end:%H:%M}</span></div>")
        out.append("<div class='legend'><i class='tl-high'></i>high<i class='tl-medium'></i>medium<i class='tl-gap'></i>no screenshots</div>")

    shown = 0
    for title, eps in [("High-confidence evidence", high), ("Worth a look", med)]:
        if not eps:
            continue
        out.append(f"<h2>{title}</h2>")
        for e in eps:
            fr_idx = e["frames"]
            best = max(fr_idx, key=lambda i: sum(1 for h in frames[i]["hits"] if h[0] == e["severity"]))
            fr = frames[best]
            boxes = [h[4] for h in fr["hits"] if h[0] == e["severity"]]
            when = (f"{e['start_time']:%H:%M:%S}" + (f" → {e['end_time']:%H:%M:%S}" if len(fr_idx) > 1 else "")
                    if e["start_time"] else "")
            dur = ((e["end_time"] - e["start_time"]).total_seconds() + interval) if e["start_time"] and e["end_time"] else 0
            img = shot_html(read_image(fr["name"]), Path(fr["name"]).suffix[1:].lower(), boxes) if shown < 150 else ""
            shown += 1
            texts = "".join(f"<li>{esc(t)}" + (f" <span class='muted'>×{n}</span>" if n > 1 else "") + "</li>"
                            for t, n in e["texts"].most_common(6))
            names = [frames[i]["name"] for i in fr_idx]
            out.append(
                f"<div class='card ep'>{img}<div><span class='tag t-{SEVERITY_NAME[e['severity']]}'>{SEVERITY_NAME[e['severity']]}</span> "
                f"<b>{esc(e['label'])}</b><div class='muted'>{esc(when)} · {len(fr_idx)} screenshot(s)"
                + (f" · ~{fmt_dur(dur)}" if dur else "") + "</div>"
                f"<div class='muted' style='font-size:13px;margin-top:4px'>Shown: {esc(fr['name'])}"
                + (f"<br>Range: {esc(names[0])} … {esc(names[-1])}" if len(names) > 1 else "") + "</div>"
                f"<ul class='texts'>{texts}</ul></div></div>")

    if apps:
        out.append("<h2>Foreground app (from the menu bar)</h2><div class='card wrap'><table><tr><th>App</th><th class='num'>Screenshots</th><th class='num'>≈ Time</th></tr>")
        for app, n in [(a, n) for a, n in apps.most_common(15) if n >= 3]:
            ai = AI_APPS.match(normalize(app))
            out.append(f"<tr class='{'ai' if ai else ''}'><td>{esc(app)}</td><td class='num'>{n}</td><td class='num'>{fmt_dur(n * interval) if interval else ''}</td></tr>")
        out.append("</table></div>")

    if domains:
        out.append("<h2>Web domains read on screen</h2><p class='muted'>Domains OCR'd anywhere in a screenshot (URL bars, tabs, page text). Seen in at least two screenshots; OCR typos are possible.</p>"
                   "<div class='card wrap'><table><tr><th>Domain</th><th class='num'>Screenshots</th><th>First seen</th></tr>")
        ai_dom = re.compile(rf"(?:^|\.)(?:{AI_DOMAINS})$")
        rows = sorted(((d, v) for d, v in domains.items() if len(v) >= 2 or ai_dom.search(d)),
                      key=lambda kv: (not ai_dom.search(kv[0]), -len(kv[1])))
        for d, idxs in rows[:60]:
            t = frames[min(idxs)]["time"]
            out.append(f"<tr class='{'ai' if ai_dom.search(d) else ''}'><td>{esc(d)}</td><td class='num'>{len(idxs)}</td><td>{f'{t:%H:%M:%S}' if t else esc(frames[min(idxs)]['name'])}</td></tr>")
        out.append("</table></div>")

    if gaps:
        out.append("<h2>Capture gaps</h2><p class='muted'>Periods with no screenshots, longer than usual. Screen capture may have been paused or the computer asleep.</p>"
                   "<div class='card wrap'><table><tr><th>From</th><th>To</th><th class='num'>Duration</th></tr>")
        for a, b in gaps:
            out.append(f"<tr><td>{a:%H:%M:%S}</td><td>{b:%H:%M:%S}</td><td class='num'>{fmt_dur((b - a).total_seconds())}</td></tr>")
        out.append("</table></div>")

    if label_counts:
        out.append("<h2>Ambient AI UI (not counted as evidence)</h2><p class='muted'>App icons, toolbar buttons and menu entries that show AI tools are installed but not that they were used.</p>"
                   "<div class='card wrap'><table><tr><th>Text</th><th class='num'>Screenshots</th></tr>")
        for t, n in label_counts.most_common(20):
            out.append(f"<tr><td>{esc(t)}</td><td class='num'>{n}</td></tr>")
        out.append("</table></div>")

    out.append("<h2>Limitations</h2><p class='muted'>This report flags on-screen text only. It cannot see inline AI code completions "
               "(e.g. Copilot ghost text), AI used on another device, or text the OCR misreads. Treat it as a list of moments to look at, "
               f"not a verdict. Generated {datetime.now():%Y-%m-%d %H:%M}.</p>")
    out.append(f"</main><script>{JS}</script></body></html>")
    return "".join(out)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def process_zip(zip_path, outdir, jobs, fast, every, progress=False):
    student = zip_path.stem
    with zipfile.ZipFile(zip_path) as zf:
        members = [zi for zi in zf.infolist()
                   if not zi.is_dir() and Path(zi.filename).suffix.lower() in IMAGE_EXTS
                   and not Path(zi.filename).name.startswith("._") and "__MACOSX" not in zi.filename]
        if not members:
            print(f"  {zip_path.name}: no images found, skipped", file=sys.stderr)
            return None
        times = {zi.filename: frame_time(zi.filename, zi) for zi in members}
        members.sort(key=lambda zi: (times[zi.filename] or datetime.min, zi.filename))
        members = members[::every]

        digest = hashlib.sha1()
        with open(zip_path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        cache_dir = outdir / ".ocr-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{digest.hexdigest()[:16]}-{'fast' if fast else 'accurate'}.jsonl"
        ocr = {}
        if cache_file.exists():
            for line in cache_file.open():
                d = json.loads(line)
                ocr[d["name"]] = d
        todo = [zi for zi in members if zi.filename not in ocr]

        if todo:
            with tempfile.TemporaryDirectory(prefix="checkexam-") as tmp:
                path_to_name = {}
                for i, zi in enumerate(todo):
                    # Flattened names: never trust paths inside the archive.
                    p = Path(tmp) / f"{i:06d}{Path(zi.filename).suffix.lower()}"
                    p.write_bytes(zf.read(zi))
                    path_to_name[str(p)] = zi.filename
                done = 0
                if progress:
                    print(f"PROGRESS 0 {len(todo)}", flush=True)
                with cache_file.open("a") as cache:
                    def on_result(d):
                        nonlocal done
                        d["name"] = path_to_name[d.pop("file")]
                        ocr[d["name"]] = d
                        cache.write(json.dumps(d, ensure_ascii=False) + "\n")
                        done += 1
                        if done % 10 == 0 or done == len(todo):
                            if progress:
                                print(f"PROGRESS {done} {len(todo)}", flush=True)
                            else:
                                print(f"\r  OCR {done}/{len(todo)}", end="", file=sys.stderr, flush=True)
                    run_ocr(list(path_to_name), jobs, fast, on_result)
                if not progress:
                    print(file=sys.stderr)

        if progress:
            print("SAVING", flush=True)

        frames = []
        apps = defaultdict(set)
        domains = defaultdict(set)
        label_counts = Counter()
        errors = 0
        for zi in members:
            d = ocr[zi.filename]
            if "error" in d:
                errors += 1
                lines = []
            else:
                lines = d["lines"]
            hits, app, doms = analyze_frame(lines)
            idx = len(frames)
            frames.append({"name": zi.filename, "time": times[zi.filename], "hits": hits})
            if app:
                apps[app].add(idx)
            for dom in doms:
                domains[dom].add(idx)
            for t in {h[3].strip() for h in hits if h[0] == INFO}:
                label_counts[t] += 1
            frames[-1]["hits"] = [h for h in hits if h[0] >= MEDIUM]

        stamps = [f["time"] for f in frames if f["time"]]
        deltas = [(b - a).total_seconds() for a, b in zip(stamps, stamps[1:]) if b > a]
        interval = statistics.median(deltas) if deltas else 0
        gap_min = max(3 * interval, 30)
        gaps = [(a, b) for a, b in zip(stamps, stamps[1:]) if interval and (b - a).total_seconds() > gap_min]

        apps = Counter({app: len(idxs) for app, idxs in merge_ocr_variants(apps, 0.75).items()})
        domains = merge_ocr_variants(domains)
        episodes = group_episodes(frames, interval)
        ocr_note = ("Vision OCR, fast mode" if fast else "Vision OCR") + (f", every {every}th screenshot" if every > 1 else "")
        if errors:
            ocr_note += f", {errors} unreadable"
        report = build_report(student, frames, episodes, gaps, apps, domains, label_counts, interval,
                              lambda name: zf.read(name), ocr_note)

    out_file = outdir / f"{student} - AI check.html"
    out_file.write_text(report, encoding="utf-8")
    high = [e for e in episodes if e["severity"] == HIGH]
    med = [e for e in episodes if e["severity"] == MEDIUM]
    verdict = "AI USE DETECTED" if high else ("REVIEW" if med else "clean")
    print(f"  → {verdict}: {len(high)} high / {len(med)} medium episodes, {len(gaps)} capture gaps")
    for e in (high + med)[:8]:
        t = f"{e['start_time']:%H:%M:%S}" if e["start_time"] else frames[e["frames"][0]]["name"]
        sample = e["texts"].most_common(1)[0][0]
        print(f"     [{SEVERITY_NAME[e['severity']]:>6}] {t}  {e['label']}: {sample[:70]!r} ({len(e['frames'])} shots)")
    print(f"  Report: {out_file}")
    return {"student": student, "verdict": verdict, "high": len(high), "medium": len(med),
            "gaps": len(gaps), "screenshots": len(frames), "report": str(out_file)}


def main():
    ap = argparse.ArgumentParser(description="Flag AI tool use in a zip of exam screenshots.")
    ap.add_argument("zips", nargs="+", type=Path, help="zip file(s) of screenshots, one per student")
    ap.add_argument("-o", "--outdir", type=Path, help="where to write reports (default: next to each zip)")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4, help="parallel OCR processes")
    ap.add_argument("--fast", action="store_true", help="Vision's fast mode (much less accurate on small screenshots)")
    ap.add_argument("--every", type=int, default=1, metavar="N", help="only OCR every Nth screenshot, for a quick pass")
    ap.add_argument("--progress", action="store_true",
                    help='print "PROGRESS <done> <total>" and "SAVING" lines (used by zip2pptx-progress.js)')
    ap.add_argument("--open", action="store_true", help="open each report in the browser when done")
    args = ap.parse_args()

    if sys.platform != "darwin":
        sys.exit("This script uses Apple's Vision framework and only runs on macOS.")
    summary = []
    for zp in args.zips:
        if not zp.is_file():
            print(f"{zp}: not found", file=sys.stderr)
            continue
        outdir = args.outdir or zp.resolve().parent
        outdir.mkdir(parents=True, exist_ok=True)
        print(f"{zp.name}")
        row = process_zip(zp, outdir, max(1, args.jobs), args.fast, max(1, args.every), args.progress)
        if row:
            summary.append(row)
            if args.open:
                subprocess.run(["open", row["report"]])
            if args.progress:
                # Last line: shown in the Quick Action's notification.
                print(f"{row['student']}: {row['verdict']} ({row['high']} high, {row['medium']} medium)")
    if len(summary) > 1:
        outdir = args.outdir or args.zips[0].resolve().parent
        with open(outdir / "summary.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(summary[0]))
            w.writeheader()
            w.writerows(summary)
        print(f"\nSummary: {outdir / 'summary.csv'}")


if __name__ == "__main__":
    main()
