"""Record the narrated Feed Control Lab demonstration (integrated app on KuaiRec) in one continuous take (Windows).

What it does
- starts the app (scripts/run_app.py) on 127.0.0.1:8765 and a fresh, maximized Chrome window (no extensions,
  password manager off), connected through the Chrome DevTools protocol;
- moves the real OS pointer with smooth curved paths (pyautogui), shows a highlight ring
  around each target while the narration names it, then clicks with a ripple;
- types text character by character with the real keyboard;
- narrates every step with local Kokoro TTS (one clip per step, measured, waited for);
- captures the screen with ffmpeg gdigrab (cursor visible) and mixes the narration clips
  onto the video at the exact moments they were played.

Usage (from the repository root, app venv):
    python tools/recording/record_demo.py --tts-python <py with kokoro> --out <folder> [--test-clip]
The API key comes from OPENAI_API_KEY in this process; the script puts it on the clipboard,
pastes it into the masked field with Ctrl+V and clears the clipboard at once. The server
process gets no key in its environment, so the page's key is the one used.
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

sys.path.insert(0, str(Path(__file__).parent))
import demo_script  # noqa: E402

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


# ------------------------------------------------------------------ foreground guard
def foreground_title():
    u32 = ctypes.windll.user32
    hwnd = u32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(512)
    u32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


class NotInFront(RuntimeError):
    pass


# ------------------------------------------------------------------ the director
class Director:
    def __init__(self, page, voice, capture, events):
        self.page, self.voice, self.cap, self.events = page, voice, capture, events
        self.timeline = []
        self.speech_end = 0.0
        self.calibrate()

    def ensure_front(self):
        """Every click and keystroke must reach Chrome. Refocus once; abort the take otherwise."""
        if "Chrome" in foreground_title():
            return
        self.page.bring_to_front()
        time.sleep(0.6)
        if "Chrome" not in foreground_title():
            raise NotInFront(f"Foreground window is '{foreground_title()}', not Chrome; the take is aborted.")
        self.events.append({"t": round(self.cap.now(), 2), "refocused": True})

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
        path, secs, text = self.voice.synth(speakable(text))
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
        self.voice.synth(speakable(text))
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
        self.ensure_front()
        pyautogui.click()
        self.events.append({"t": round(self.cap.now(), 2), "click": sel})
        print(f"[take] {self.events[-1]['t']:7.1f}s click {sel}", flush=True)
        time.sleep(0.35)

    def choose(self, sel, text, typed):
        """Choose an option the way a keyboard user does: focus the list and type its first letters.
        The native drop-down popup is never opened, so it cannot swallow the next click."""
        cx, cy = self.point(sel, text)
        self.page.evaluate("window.__demo.clear()")
        self.page.evaluate(f"window.__demo.ripple({cx},{cy})")
        self.page.focus(sel)
        self.ensure_front()
        pyautogui.write(typed, interval=0.12)
        time.sleep(0.6)
        want = self.page.evaluate("([s, t]) => { const o = [...document.querySelector(s).options].find(o => o.text.toLowerCase().startsWith(t.toLowerCase())); return o ? o.value : null; }", [sel, typed])
        if want is not None and self.page.locator(sel).first.input_value() != want:
            self.page.select_option(sel, want)
            self.events.append({"t": round(self.cap.now(), 2), "choose_corrected": sel})
        self.events.append({"t": round(self.cap.now(), 2), "choose": sel})
        print(f"[take] {self.events[-1]['t']:7.1f}s choose {sel}", flush=True)
        time.sleep(0.4)

    def type_into(self, sel, text, narration, interval=0.05):
        self.click(sel, narration)
        pyautogui.hotkey("ctrl", "a"); pyautogui.press("delete")
        pyautogui.write(text, interval=interval)
        time.sleep(0.4)

    def wait_preview(self, prev_id, timeout=420, explain=None):
        """Wait for a new preview. If it is still running when the narration ends, explain the stage once."""
        done = "prev => window.labLastPreview && window.labLastPreview.id !== prev"
        if explain:
            self.wait_speech()
            if not self.page.evaluate(done, prev_id):
                time.sleep(2.0)
                if not self.page.evaluate(done, prev_id):
                    self.say(explain, wait=False)
        self.page.wait_for_function(
            "prev => window.labLastPreview && window.labLastPreview.id !== prev", arg=prev_id, timeout=timeout * 1000)
        return self.page.evaluate("window.labLastPreview")

    def last_id(self):
        return self.page.evaluate("window.labLastPreview ? window.labLastPreview.id : null")


# ------------------------------------------------------------------ narration helpers
SPOKEN = {r"SASRec": "Sass-Rec", r"KuaiRec": "Kwai-Rec", r"TCP@10": "TCP at ten", r"HR@1": "hit rate at one",
          r"NDCG@10": "N D C G at ten", r"USD": "dollars", r"F1": "F one", r"Ollama": "Oh-lama"}


def speakable(text):
    """Spell out words that text-to-speech mispronounces."""
    for pat, rep in SPOKEN.items():
        text = re.sub(pat, rep, text)
    return text


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


def static_lines(extra=()):
    """Every literal narration sentence of demo_script, found by parsing it, so it can be synthesized before capture."""
    import ast
    tree = ast.parse((Path(__file__).parent / "demo_script.py").read_text(encoding="utf-8"))
    texts = set(extra) | set(demo_script.WAIT_LINES_ALL) | {demo_script.FILLER}
    for node in ast.walk(tree):
        name = node.func.attr if isinstance(getattr(node, "func", None), ast.Attribute) else getattr(getattr(node, "func", None), "id", None)
        if isinstance(node, ast.Call) and name in ("say", "click", "choose", "type_into", "point", "say_while_typing"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and " " in arg.value and not arg.value.startswith(("[", "#", ".")):
                    texts.add(arg.value)
    return sorted(texts)


def results_lines(folder):
    """What the narration says on the Results page, read from the newest published summary."""
    runs = sorted((p for p in Path(folder).iterdir() if (p / "summary.json").is_file()), reverse=True) if Path(folder).is_dir() else []
    if not runs:
        return [{"say": "No measured results are published yet."}]
    s = json.loads((runs[0] / "narration.json").read_text(encoding="utf-8")) if (runs[0] / "narration.json").is_file() else None
    return s or [{"say": "The tables show the measured results of every model."}]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts-python", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--test-clip", action="store_true")
    ap.add_argument("--app-python", default=sys.executable)
    ap.add_argument("--results", default="docs/evidence/lab-eval")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    ap.add_argument("--model", default="gpt-5")
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
    args.key = os.environ.get("OPENAI_API_KEY", "")
    if not args.key and not args.test_clip:  # noqa
        raise SystemExit("OPENAI_API_KEY is needed for the take (it is pasted into the masked field).")
    examples = json.loads((REPO / "tools/demo_examples.json").read_text(encoding="utf-8"))
    args.manual_value = examples["manual"][1]["value"]
    args.interpret = [{**examples["interpret"][2], "say": "I write that I just ate, and do not want to be tempted by food. No category name."},
                      {**examples["interpret"][3], "say": "In Chinese: there has been too much negative news lately; give me a few quiet days."}]
    args.new_category = examples["new_category"][0]["description"]
    args.new_item = examples["new_items"][0]["items"][0]
    server = subprocess.Popen([args.app_python, "scripts/run_app.py", "--port", "8765", "--provider", "mock"],
                              cwd=REPO, env=env)
    import urllib.request
    for _ in range(240):   # the app must answer before Chrome opens it
        try:
            urllib.request.urlopen(URL + "api/lab/status", timeout=2).read()
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise SystemExit("The app did not start.")
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
            pages = [pg for ctx in browser.contexts for pg in ctx.pages]
            page = next((pg for pg in pages if pg.url.startswith(URL)), pages[0])
            if not page.url.startswith(URL):
                page.goto(URL)
            page.wait_for_selector("[data-view='lab']", timeout=60000)
            page.bring_to_front()
            time.sleep(1.5)
            pyautogui.moveTo(phys[0] // 2, phys[1] // 2)
            lines = static_lines([l["say"] for l in results_lines(REPO / args.results)] if not args.test_clip else [])
            for n, text in enumerate(lines, 1):
                voice.synth(speakable(text))
            events.append({"presynthesized": len(lines)})
            cap = Capture(out / "video-raw.mp4", cap_size)
            d = Director(page, voice, cap, events)
            demo_script.GUARD = d.ensure_front
            time.sleep(1.0)
            if args.test_clip:
                demo_script.test_clip(d, page, args)
            else:
                demo_script.run_demo(d, page, args, events, args.model, results_lines(REPO / args.results))
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
    final = out / ("test-clip.mp4" if args.test_clip else "COMP9500-Feed-Control-Lab-demo.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out / "video-raw.mp4"), "-i",
                    str(out / "narration.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)], check=True)
    (out / "timeline.json").write_text(json.dumps({"timeline": timeline, "events": events, "duration": duration}, indent=2))
    print(json.dumps({"video": str(final), "duration_s": duration, "clips": len(timeline)}))


if __name__ == "__main__":
    main()
