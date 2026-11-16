"""Record the narrated Feed Control Studio demonstration in one continuous take (Windows).

What it does
- starts the Studio on 127.0.0.1:8765 and a fresh, maximized Chrome window (no extensions,
  password manager off), connected through the Chrome DevTools protocol;
- moves the real OS pointer with smooth curved paths (pyautogui), shows a highlight ring
  around each target while the narration names it, then clicks with a ripple;
- types text character by character with the real keyboard;
- narrates every step with local Kokoro TTS (one clip per step, measured, waited for);
- captures the screen with ffmpeg gdigrab (cursor visible) and mixes the narration clips
  onto the video at the exact moments they were played.

Usage (from the repository root, Studio venv):
    python tools/studio_recording/record_demo.py --tts-python <py with kokoro> --out <folder> [--test-clip]
The API key is never typed by this script: put it on the clipboard before starting;
the script pastes it into the masked field with Ctrl+V and clears the clipboard afterwards.
Do not touch the mouse or keyboard while it runs. Moving the pointer into a screen corner aborts.
"""
from __future__ import annotations

import argparse
import array
import ctypes
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import threading
import time
import wave
import winsound
from pathlib import Path

import pyautogui
from playwright.sync_api import sync_playwright

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://127.0.0.1:8765/"
CDP_PORT = 9333
SCALE = 1.3333          # Chrome device scale: 2560 physical px -> 1920 CSS px viewport width
FPS = 30
HERE = Path(__file__).parent
REPO = HERE.parent.parent

OVERLAY_JS = r"""
(() => {
  if (window.__demo) return;
  const st = document.createElement('style');
  st.textContent = `
  .__ring{position:fixed;pointer-events:none;z-index:2147483646;border:4px solid #ff8a00;border-radius:12px;
    box-shadow:0 0 0 4px rgba(255,138,0,.25),0 0 18px rgba(255,138,0,.55);animation:__pulse 0.9s ease-in-out infinite alternate}
  @keyframes __pulse{from{box-shadow:0 0 0 3px rgba(255,138,0,.20),0 0 10px rgba(255,138,0,.45)}to{box-shadow:0 0 0 9px rgba(255,138,0,.10),0 0 26px rgba(255,138,0,.70)}}
  .__ripple{position:fixed;pointer-events:none;z-index:2147483647;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;
    background:rgba(255,138,0,.55);animation:__rip .6s ease-out forwards}
  @keyframes __rip{to{transform:scale(5);opacity:0}}`;
  document.head.appendChild(st);
  window.__demo = {
    ring(x, y, w, h) { this.clear(); const d = document.createElement('div'); d.className = '__ring';
      Object.assign(d.style, {left: (x - 7) + 'px', top: (y - 7) + 'px', width: (w + 14) + 'px', height: (h + 14) + 'px'});
      document.body.appendChild(d); this.cur = d; },
    clear() { if (this.cur) { this.cur.remove(); this.cur = null; } },
    ripple(x, y) { const d = document.createElement('div'); d.className = '__ripple';
      Object.assign(d.style, {left: x + 'px', top: y + 'px'}); document.body.appendChild(d); setTimeout(() => d.remove(), 700); },
  };
  window.__mouse = {x: -1, y: -1};
  document.addEventListener('mousemove', e => { window.__mouse = {x: e.clientX, y: e.clientY}; }, true);
})();
"""


# ------------------------------------------------------------------ TTS
class Voice:
    def __init__(self, tts_python, folder, voice="af_heart"):
        self.folder = Path(folder); self.folder.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen([tts_python, str(HERE / "tts_kokoro.py"), voice], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        ready = json.loads(self.proc.stdout.readline())
        assert ready.get("ready"), ready
        self.cache, self.lock = {}, threading.Lock()

    def synth(self, text):
        text = re.sub(r"\s+", " ", text).strip()
        with self.lock:
            if text in self.cache:
                return self.cache[text]
            out = self.folder / f"clip-{len(self.cache):03d}-{hashlib.sha1(text.encode()).hexdigest()[:8]}.wav"
            self.proc.stdin.write(json.dumps({"text": text, "out": str(out)}) + "\n"); self.proc.stdin.flush()
            res = json.loads(self.proc.stdout.readline())
            self.cache[text] = (out, res["seconds"], text)
            return self.cache[text]

    def close(self):
        self.proc.stdin.close(); self.proc.wait(10)


# ------------------------------------------------------------------ screen capture
class Capture:
    def __init__(self, path, size):
        self.path = Path(path)
        w, h = size
        self.proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-y", "-f", "gdigrab", "-framerate", str(FPS), "-draw_mouse", "1",
             "-offset_x", "0", "-offset_y", "0", "-video_size", f"{w}x{h}", "-i", "desktop",
             "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-pix_fmt", "yuv420p", str(self.path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        self.t0 = None
        self.log = []
        threading.Thread(target=self._read, daemon=True).start()
        for _ in range(400):
            if self.t0 is not None:
                break
            time.sleep(0.025)
        if self.t0 is None:
            raise RuntimeError("ffmpeg did not start capturing: " + "".join(self.log[-5:]))

    def _read(self):
        buf = ""
        while True:
            ch = self.proc.stderr.read(1)
            if not ch:
                return
            buf += ch
            if ch in "\r\n":
                self.log.append(buf)
                m = re.search(r"frame=\s*(\d+)", buf)
                if m and self.t0 is None and int(m.group(1)) > 0:
                    self.t0 = time.monotonic() - int(m.group(1)) / FPS
                buf = ""

    def now(self):
        return time.monotonic() - self.t0

    def stop(self):
        self.proc.stdin.write("q"); self.proc.stdin.flush()
        self.proc.wait(60)


# ------------------------------------------------------------------ the director
class Director:
    def __init__(self, page, voice, capture, events):
        self.page, self.voice, self.cap, self.events = page, voice, capture, events
        self.timeline = []
        self.speech_end = 0.0
        self.calibrate()

    # -- coordinates
    def calibrate(self):
        self.page.evaluate(OVERLAY_JS)
        m = self.page.evaluate("({sx:screenX, sy:screenY, ow:outerWidth, oh:outerHeight, iw:innerWidth, ih:innerHeight, dpr:devicePixelRatio})")
        self.dpr = m["dpr"]
        self.ox = (m["sx"] + (m["ow"] - m["iw"]) / 2) * self.dpr
        self.oy = (m["sy"] + (m["oh"] - m["ih"])) * self.dpr
        self.vw, self.vh = m["iw"], m["ih"]
        for _ in range(2):   # measure and correct the offset with real mouse events
            tx, ty = 300, 300
            pyautogui.moveTo(*self.screen(tx, ty)); time.sleep(0.05)
            pyautogui.moveRel(1, 0); pyautogui.moveRel(-1, 0); time.sleep(0.1)
            got = self.page.evaluate("window.__mouse")
            if got["x"] < 0:
                continue
            self.ox -= (got["x"] - tx) * self.dpr
            self.oy -= (got["y"] - ty) * self.dpr
        self.events.append({"calibration": {"dpr": self.dpr, "ox": self.ox, "oy": self.oy, "viewport": [self.vw, self.vh]}})

    def screen(self, x, y):
        return int(round(self.ox + x * self.dpr)), int(round(self.oy + y * self.dpr))

    def box(self, sel):
        loc = self.page.locator(sel).first
        loc.wait_for(state="visible", timeout=30000)
        return loc.bounding_box()

    def ensure_visible(self, sel, margin=90):
        b = self.box(sel)
        top_limit, bottom_limit = margin, self.vh - margin
        if b["y"] < top_limit or b["y"] + b["height"] > bottom_limit:
            dy = (b["y"] + b["height"] / 2) - self.vh * 0.45
            self.scroll_by(dy)
            b = self.box(sel)
        return b

    def scroll_by(self, dy):
        self.page.evaluate(f"window.scrollBy({{top: {dy}, behavior: 'smooth'}})")
        time.sleep(0.9)

    def scroll_to_top(self):
        self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        time.sleep(0.9)

    # -- pointer
    def glide(self, x, y, dur=None):
        x0, y0 = pyautogui.position()
        dist = math.hypot(x - x0, y - y0)
        if dist < 2:
            return
        dur = dur or min(1.25, 0.5 + dist / 2600)
        nx, ny = -(y - y0) / dist, (x - x0) / dist
        bend = random.uniform(-0.12, 0.12) * dist
        c1 = (x0 + (x - x0) * 0.3 + nx * bend, y0 + (y - y0) * 0.3 + ny * bend)
        c2 = (x0 + (x - x0) * 0.7 + nx * bend * 0.6, y0 + (y - y0) * 0.7 + ny * bend * 0.6)
        steps = max(20, int(dur * 120))
        start = time.monotonic()
        for i in range(1, steps + 1):
            t = i / steps
            e = 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
            bx = (1 - e) ** 3 * x0 + 3 * (1 - e) ** 2 * e * c1[0] + 3 * (1 - e) * e ** 2 * c2[0] + e ** 3 * x
            by = (1 - e) ** 3 * y0 + 3 * (1 - e) ** 2 * e * c1[1] + 3 * (1 - e) * e ** 2 * c2[1] + e ** 3 * y
            pyautogui.moveTo(int(bx), int(by), _pause=False)
            wait = start + dur * i / steps - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        pyautogui.moveTo(int(x), int(y), _pause=False)

    # -- speech
    def say(self, text, wait=True, gap=0.35):
        path, secs, text = self.voice.synth(text)
        self.wait_speech()
        at = self.cap.now()
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        self.timeline.append({"at": round(at, 3), "seconds": secs, "file": str(path), "text": text})
        self.speech_end = time.monotonic() + secs + gap
        if wait:
            self.wait_speech()
        return secs

    def wait_speech(self):
        d = self.speech_end - time.monotonic()
        if d > 0:
            time.sleep(d)

    def hold(self, secs):
        self.wait_speech(); time.sleep(secs)

    # -- actions
    def point(self, sel, text, min_ring=1.6):
        """Narrate, glide to the target, ring it while the narration names it."""
        b = self.ensure_visible(sel)
        path, secs, _ = self.voice.synth(text)
        self.say(text, wait=False)
        cx, cy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        self.glide(*self.screen(cx, cy))
        self.page.evaluate(f"window.__demo.ring({b['x']},{b['y']},{b['width']},{b['height']})")
        ring_start = time.monotonic()
        self.wait_speech()
        left = min_ring - (time.monotonic() - ring_start)
        if left > 0:
            time.sleep(left)
        return cx, cy

    def click(self, sel, text):
        cx, cy = self.point(sel, text)
        self.page.evaluate("window.__demo.clear()")
        self.page.evaluate(f"window.__demo.ripple({cx},{cy})")
        pyautogui.click()
        self.events.append({"t": round(self.cap.now(), 2), "click": sel})
        time.sleep(0.35)

    def choose(self, sel, text, typed):
        """Open a select list and choose an option by typing its first letters, as a person would."""
        self.click(sel, text)
        time.sleep(0.45)
        pyautogui.write(typed, interval=0.12)
        time.sleep(0.35)
        pyautogui.press("enter")
        time.sleep(0.5)

    def type_into(self, sel, text, narration, interval=0.05):
        self.click(sel, narration)
        pyautogui.hotkey("ctrl", "a"); pyautogui.press("delete")
        pyautogui.write(text, interval=interval)
        time.sleep(0.4)

    def wait_preview(self, prev_id, timeout=420, explain=None):
        """Wait for a new preview. If it is still running when the narration ends, explain the stage once."""
        done = "prev => window.studioLastPreview && window.studioLastPreview.id !== prev"
        if explain:
            self.wait_speech()
            if not self.page.evaluate(done, prev_id):
                time.sleep(2.0)
                if not self.page.evaluate(done, prev_id):
                    self.say(explain, wait=False)
        self.page.wait_for_function(
            "prev => window.studioLastPreview && window.studioLastPreview.id !== prev", arg=prev_id, timeout=timeout * 1000)
        return self.page.evaluate("window.studioLastPreview")

    def last_id(self):
        return self.page.evaluate("window.studioLastPreview ? window.studioLastPreview.id : null")


# ------------------------------------------------------------------ narration helpers
def money(v):
    if not v:
        return "less than a cent"
    if v < 0.01:
        return "less than a cent"
    cents = round(v * 100, 1)
    return f"about {cents:g} cents" if v < 1 else f"about {v:.2f} dollars"


def listing(names, limit=6):
    names = list(names)
    if not names:
        return "none"
    if len(names) > limit:
        return ", ".join(names[:limit]) + f", and {len(names) - limit} more"
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def calls_line(p):
    calls = [c for c in p["calls"] if not c.get("error")]
    secs = sum(c.get("latency_s") or 0 for c in calls)
    cost = sum(c.get("cost_usd") or 0 for c in calls)
    n = len(calls)
    return f"{n} model call{'s' if n != 1 else ''}, {secs:.0f} seconds of model time, {money(cost)}"


def say_spoken(text):
    """Make IDs and symbols speakable."""
    return text.replace("&", "and").replace("/", " ")


# ------------------------------------------------------------------ the script
PROVIDERS = {"openai": ("OpenAI", "OpenAI-compatible API"), "anthropic": ("Anth", "Anthropic API")}
SPOKEN_MODEL = {"gpt-5-mini": "GPT five mini", "gpt-5": "GPT five", "claude-sonnet-5-5": "Claude Sonnet five point five",
                "claude-opus-5-5": "Claude Opus five point five"}


def run_demo(d: Director, page, cfg, events):
    titles = {i["id"]: i["title"] for i in page.evaluate("fetch('/api/state').then(r => r.json())")["items"]}

    def effect(p):
        ch = p["changes"]
        if ch["eligible_before"] != ch["eligible_after"]:
            return f"eligible videos go from {ch['eligible_before']} to {ch['eligible_after']}"
        return f"all {ch['eligible_after']} videos stay eligible, but {len(ch['entered'])} enter the top twelve and {len(ch['moved_up'])} move up"

    # Intro
    d.say("This is Feed Control Studio, the application for my comp ninety-five hundred project. It lets a person steer a short-video "
          "feed in plain language.")
    d.say("A language model proposes each change, the application checks the proposal against the catalogue, and "
          "nothing changes until I click Apply.")
    d.point("#feed-card", "On the right is my feed: the top twelve of forty invented videos in ten categories, ranked by a fixed score.")
    d.hold(0.6)

    # 1. Model and key
    d.point("#key-card", "First, the model. The person running the app brings their own key; there is no password or login.")
    typed, name = PROVIDERS[cfg.provider]
    d.choose("#provider-kind", f"The app works with any provider: Anthropic, OpenAI, or a local server that speaks the OpenAI format. "
                               f"Here I choose the {name}.", typed)
    spoken = SPOKEN_MODEL.get(cfg.model, cfg.model)
    if page.input_value("#model-select") != cfg.model:
        d.type_into("#model-select", cfg.model, f"I set the model to {spoken}.")
    else:
        d.point("#model-select", f"The model is {spoken}.")
    if page.input_value("#effort-select") != cfg.effort:
        d.choose("#effort-select", f"Effort {cfg.effort}.", cfg.effort[:3])
    d.click("#api-key", "Now I paste my API key into this field.")
    pyautogui.hotkey("ctrl", "v"); time.sleep(0.6)
    d.say("The field is masked. The key stays only in the memory of the local server; it is never written to disk or shown.")
    d.click("#save-provider", "I click Use this model.")
    page.wait_for_selector("#provider-msg.ok", timeout=20000)
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $null"], check=False)
    d.point("#provider-line", f"The status at the top now shows the {name}, the model, and that the key was pasted and is held in memory only.")
    d.hold(0.5)

    # 2. Manual
    d.click("#tab-manual", "Workflow one is the manual control. It uses no model, and it is the reference for the others.")
    d.choose("#manual-value", "I pick the category Gaming,", "Gam")
    d.choose("#manual-action", "and the action Hide.", "Hid")
    prev = d.last_id()
    d.click("#manual-preview", "I click Preview.")
    p = d.wait_preview(prev)
    gone = [titles[i] for i in p["affected"][0]["item_ids"]]
    d.point("#review", f"The review says no model was called, the application checked that Gaming exists, and the effect: "
                       f"{effect(p)}. The {len(gone)} gaming videos leave the top twelve and {len(p['changes']['entered'])} others move in. "
                       f"My feed has not changed yet.", min_ring=2.0)
    d.hold(1.0)
    d.click("#apply-btn", "I click Apply.")
    d.point("#feed-card", "The feed now has 36 eligible videos, with no gaming, and the control is listed under Applied controls.")
    d.click("#undo-btn", "Undo restores the previous feed.")
    d.say("All forty videos are back.")
    d.hold(0.8)

    # 3. Plain-language request
    d.scroll_to_top()
    d.click("#tab-interpret", "Workflow two is a plain-language request that never names a category.")
    req = "I'm not hungry, remove all the stuff that makes me hungry."
    d.type_into("#interpret-text", req, "I type: I'm not hungry, remove all the stuff that makes me hungry.")
    prev = d.last_id()
    d.click("#interpret-preview", "I click Interpret and preview.")
    d.say("The request goes to the model with the list of existing categories and tags and how many videos carry each. "
          "The model sees no video descriptions in this workflow.", wait=False)
    p = d.wait_preview(prev)
    ev = p["evidence"][0] if p["evidence"] else {}
    labels = [c["target"]["value"] for c in p["controls"]]
    d.point("#review", f"{calls_line(p)}. The model quoted the words '{ev.get('intent_span', '')}' from my request and chose "
                       f"the action {ev.get('action', '')} for {listing(labels, 4)}.", min_ring=2.0)
    d.say(f"Its reason: {ev.get('relation', '')}")
    removed = sorted({i for a in p["affected"] for i in a["item_ids"]})
    d.say(f"The application checked that each label exists and that the quoted words really appear in my request. "
          f"Effect: {effect(p)}. The {len(removed)} videos removed are {listing([titles[i] for i in removed], 5)}.")
    d.hold(0.8)
    d.click("#apply-btn", "I click Apply.")
    d.point("#feed-card", f"The food videos are gone; the feed shows {p['changes']['eligible_after']} eligible videos.")
    d.click("#undo-btn", "And Undo brings them back.")
    d.hold(0.6)

    # 3b. Second domain + auto-apply
    d.scroll_to_top()
    req2 = "My knees are killing me this week, so skip anything that would make me sweat."
    d.type_into("#interpret-text", req2, "A second example, from a different domain: My knees are killing me this week, so skip anything that would make me sweat.")
    d.click("#auto-apply", "This time I turn on auto-apply. The change is applied straight away, but the evidence stays on screen and Undo still works.")
    prev = d.last_id()
    d.click("#interpret-preview", "Interpret.")
    p = d.wait_preview(prev, explain="Again, one call with the request and the existing labels only.")
    page.wait_for_selector("text=Auto-applied", timeout=30000)
    ev = p["evidence"][0] if p["evidence"] else {}
    labels = [c["target"]["value"] for c in p["controls"]]
    d.point("#review", f"{calls_line(p)}. The model linked '{ev.get('intent_span', '')}' to {listing(labels, 5)}, "
                       f"and the change was applied automatically: {effect(p)}.", min_ring=2.0)
    d.click("#auto-apply", "I turn auto-apply off again,")
    d.click("#undo-btn", "and undo.")
    d.hold(0.6)

    # 4. New category
    d.scroll_to_top()
    d.click("#tab-category", "Workflow three creates a category that does not exist yet, from a description.")
    desc = "Videos where someone teaches a practical skill step by step, so I can follow along."
    d.type_into("#category-text", desc, "I describe it: Videos where someone teaches a practical skill step by step, so I can follow along.")
    d.click("#category-define", "I click Propose a definition.")
    d.say("The model now reads all forty titles and descriptions and proposes one definition, with quotes that support it.", wait=False)
    page.wait_for_function("window.studioLastDefinition", timeout=300000)
    df = page.evaluate("window.studioLastDefinition")
    found = sum(1 for e in df["evidence"] if e["quote_verified"])
    d.point("#definition-box", f"It proposed the label {df['label']}. The definition is in the box below it. "
                               f"The application found {found} of its {len(df['evidence'])} supporting quotes word for word in the video text. "
                               f"I could edit the label or the definition here; I accept it as it is.", min_ring=2.0)
    d.choose("#category-action", "Then I choose what to do with the category: show only these videos.", "Show o")
    prev = d.last_id()
    d.click("#category-classify", "I click Classify all videos and preview.")
    d.say("The model classifies every video under that exact definition, in four batches of ten, citing an exact quote for each match. "
          "Then a separate call, which never sees the verdicts, checks whether each quote really supports the definition. "
          "A video is selected only if both agree and the quote is found.", wait=False)
    p = d.wait_preview(prev, explain="The batches run in parallel, so the wait is about as long as the slowest one. "
                                     "Each reply must name every video exactly once; a video the model skips counts as unknown, never as a match.")
    rows = p["evidence"]
    sel = [r for r in rows if r["selected"]]
    matched = [r for r in rows if r["verdict"] == "match"]
    rejected = [r for r in matched if not r["selected"]]
    d.point("#match-table", f"{calls_line(p)}. The classifier matched {len(matched)} videos and {len(sel)} were selected: "
                            f"{listing([r['title'] for r in sel], 6)}.", min_ring=2.0)
    if rejected:
        r0 = rejected[0]
        why = "the independent check disagreed" if r0.get("assessment") and not r0["assessment"]["supports"] else "its quote was not found"
        d.say(f"{r0['title']} was matched but not selected, because {why}.")
    if sel:
        d.say(f"For example, for {sel[0]['title']}, the evidence is the quote: {sel[0]['quote']}.")
    d.point("#other-rows", f"The other {len(rows) - len(matched)} videos are listed here with their verdicts.")
    d.ensure_visible("#apply-btn", margin=160)
    d.say(f"Below, the effect: {effect(p)}.")
    d.hold(0.8)
    d.click("#apply-btn", "I click Apply.")
    d.point("#feed-card", f"The feed now shows only the {len(sel)} videos in the new category, from different topics.")
    d.hold(0.6)

    # 5. Add videos (classified into existing labels and the new category)
    d.scroll_to_top()
    d.click("#tab-items", "Workflow four adds new videos to the catalogue. They are classified into the existing labels and into my new category.")
    d.type_into("#item-title-0", "Sourdough starter, day three", "The first video's title: Sourdough starter, day three.")
    d.type_into("#item-desc-0", "A baker shows step by step how to feed the starter, check the bubbles and shape the first loaf.",
                "Its description.", interval=0.035)
    d.click("#add-item-row", "I add a second video.")
    d.type_into("#item-title-1", "Retro kart racing tournament", "Title: Retro kart racing tournament.")
    d.type_into("#item-desc-1", "Eight players race a classic kart game while the commentator yells at every crash.",
                "And its description.", interval=0.035)
    prev = d.last_id()
    d.click("#items-preview", "I click Classify and preview.")
    p = d.wait_preview(prev, explain="One call picks an existing category and tags for each new video and gives a verdict, with a quote, "
                                     "for my new category. A matched video then goes through the same independent check as before.")
    parts = []
    for e in p["evidence"]:
        nc = e["new_categories"][0] if e["new_categories"] else None
        cat_part = f"{nc['label']}: {nc['verdict'].replace('_', ' ')}" if nc else ""
        parts.append(f"{e['title']} goes to {e['category']}" + (f", and for {cat_part}" if cat_part else ""))
    d.point("#review", f"{calls_line(p)}. " + "; ".join(parts) + ".", min_ring=2.0)
    d.say(f"Because my feed shows only the new category, the effect is: {effect(p)}.")
    d.click("#apply-btn", "I click Apply.")
    d.point("#feed-card", "The sourdough tutorial is now in my feed, marked new. The kart race is in the catalogue but filtered out.")
    d.click("#undo-btn", "Undo removes the two new videos,")
    d.click("#undo-btn", "and a second Undo removes the new category, so the feed is back where it started.")
    d.hold(0.6)

    # Close
    spend = page.evaluate("fetch('/api/ledger').then(r => r.json())")
    d.point("#spend", f"The model cost for this whole session was {money(spend['total_usd'])}, shown at the top.")
    d.say("That was the manual control, a plain-language request matched to existing labels, a new category built from a "
          "description with quoted and independently checked evidence, and new videos classified into both, each with a "
          "preview, Apply and Undo. The guide in the repository repeats every step.")
    d.hold(1.5)
    events.append({"ledger": spend})


def test_clip(d: Director, page):
    d.say("This is a short calibration clip.")
    d.click("#tab-interpret", "The pointer moves to the Plain language tab, and the ring highlights it.")
    d.type_into("#interpret-text", "testing typing", "I type into the request box.")
    d.click("#tab-manual", "Back to the manual tab.")
    d.choose("#manual-value", "I choose Gaming from the list.", "Gam")
    d.hold(1.0)


# ------------------------------------------------------------------ setup helpers
def set_toasts(enabled):
    import winreg
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\PushNotifications")
    try:
        old = winreg.QueryValueEx(key, "ToastEnabled")[0]
    except OSError:
        old = None
    winreg.SetValueEx(key, "ToastEnabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
    winreg.CloseKey(key)
    return old


def mix_audio(timeline, duration, out_wav):
    rate = 24000
    total = array.array("i", [0]) * int((duration + 1) * rate)
    for clip in timeline:
        with wave.open(clip["file"]) as w:
            assert w.getframerate() == rate and w.getsampwidth() == 2 and w.getnchannels() == 1
            data = array.array("h", w.readframes(w.getnframes()))
        start = int(clip["at"] * rate)
        for i, v in enumerate(data):
            if start + i < len(total):
                total[start + i] += v
    pcm = array.array("h", (max(-32768, min(32767, v)) for v in total))
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                         capture_output=True, text=True)
    return float(out.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts-python", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--test-clip", action="store_true")
    ap.add_argument("--studio-python", default=sys.executable)
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--effort", default="low")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    events = []
    ctypes.windll.user32.SetProcessDPIAware()
    phys = (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
    cap_size = (phys[0], phys[0] * 9 // 16)          # top 16:9 region of the screen
    events.append({"screen": phys, "capture": cap_size})

    voice = Voice(args.tts_python, out / "voice", args.voice)
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
    server = subprocess.Popen([args.studio_python, "-m", "studio", "--no-browser", "--port", "8765", "--provider", "mock"],
                              cwd=REPO, env=env)
    profile = out / "chrome-profile"
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    (profile / "Default" / "Preferences").write_text(json.dumps({
        "credentials_enable_service": False, "profile": {"password_manager_enabled": False},
        "translate": {"enabled": False}, "browser": {"has_seen_welcome_page": True}}))
    old_toasts = set_toasts(False)
    subprocess.run(["powershell", "-NoProfile", "-Command", "(New-Object -ComObject Shell.Application).MinimizeAll()"])
    time.sleep(1.0)
    chrome = subprocess.Popen([CHROME, f"--user-data-dir={profile}", f"--remote-debugging-port={CDP_PORT}", "--start-maximized",
                               f"--force-device-scale-factor={SCALE}", "--no-first-run", "--no-default-browser-check",
                               "--disable-features=Translate,PasswordManagerOnboarding", "--hide-crash-restore-bubble",
                               "--disable-extensions", "--disable-sync", URL])
    cap = None
    try:
        with sync_playwright() as p:
            for _ in range(60):
                try:
                    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
                    break
                except Exception:
                    time.sleep(0.5)
            page = next(pg for ctx in browser.contexts for pg in ctx.pages if pg.url.startswith(URL))
            page.wait_for_selector("#feed li", timeout=30000)
            page.bring_to_front()
            time.sleep(1.5)
            pyautogui.moveTo(phys[0] // 2, phys[1] // 2)
            cap = Capture(out / "video-raw.mp4", cap_size)
            d = Director(page, voice, cap, events)
            time.sleep(1.0)
            if args.test_clip:
                test_clip(d, page)
            else:
                run_demo(d, page, args, events)
            d.wait_speech(); time.sleep(1.0)
            cap.stop(); cap = None
            timeline = d.timeline
            browser.close()
    finally:
        if cap:
            cap.stop()
        chrome.terminate()
        server.terminate()
        voice.close()
        set_toasts(True if old_toasts in (None, 1) else False)
        subprocess.run(["powershell", "-NoProfile", "-Command", "(New-Object -ComObject Shell.Application).UndoMinimizeALL()"])
    duration = probe_duration(out / "video-raw.mp4")
    mix_audio(timeline, duration, out / "narration.wav")
    final = out / ("test-clip.mp4" if args.test_clip else "COMP9500-Feed-Control-Studio-demo.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out / "video-raw.mp4"), "-i",
                    str(out / "narration.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)], check=True)
    (out / "timeline.json").write_text(json.dumps({"timeline": timeline, "events": events, "duration": duration}, indent=2))
    print(json.dumps({"video": str(final), "duration_s": duration, "clips": len(timeline)}))


if __name__ == "__main__":
    main()
