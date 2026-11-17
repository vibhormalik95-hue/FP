"""The narrated walkthrough of the integrated Feed Control Lab on KuaiRec (used by record_demo.py).

Every sentence is spoken by Kokoro (voice af_heart) before or while the pointer acts. Model
waits are filled with stage explanations so that no silence lasts five seconds. Chinese text is
never read aloud: the narration uses the English machine-translation gloss of each label.
The requests come from tools/demo_examples.json, never from the evaluation set.
"""
from __future__ import annotations

import ctypes
import json
import re
import time
import urllib.request

import pyautogui

SPOKEN_MODEL = {"gpt-5-mini": "GPT five mini", "gpt-5": "GPT five", "claude-sonnet-5-5": "Claude Sonnet five point five"}
WAIT_LINES = {
    "interpret": ["The model reads the request and the list of existing labels. It sees no video text.",
                  "Next, the server checks that every label exists and that the quoted words are in the request."],
    "define": ["The model reads the description and this user's top forty videos.",
               "It drafts a label and a definition, and cites example videos with exact quotations."],
    "classify": ["Each video in scope is classified under the definition, ten per call, four calls in parallel.",
                 "Every match must quote the video's own text.",
                 "A separate call checks each quotation without seeing the verdict.",
                 "Only matches that pass both checks are selected."],
    "new-items": ["The model assigns existing categories and tags, and judges the new category with a quotation."],
}
WAIT_LINES_ALL = [line for lines in WAIT_LINES.values() for line in lines]
FILLER = "The model is still working."


def clipboard(text):
    """Set (or, with an empty string, clear) the Windows clipboard. The value goes through stdin,
    never through a command line, so it does not appear in any process list or log."""
    import subprocess
    script = ("$v = [Console]::In.ReadToEnd(); if ($v.Length -gt 0) { Set-Clipboard -Value $v } "
              "else { Set-Clipboard -Value $null }")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], input=text,
                   text=True, encoding="utf-8", capture_output=True, timeout=30, check=True)


GUARD = None   # set by record_demo: verifies Chrome is in front before each keystroke


def type_text(text, interval=0.05):
    """Character by character with the real keyboard; non-ASCII characters through the clipboard."""
    for ch in text:
        if GUARD:
            GUARD()
        if ord(ch) < 128:
            pyautogui.write(ch, interval=0)
        else:
            clipboard(ch)
            pyautogui.hotkey("ctrl", "v")
        time.sleep(interval if ord(ch) < 128 else 0.12)
    clipboard("")


def say_while_typing(d, text, line, interval=0.04):
    """Start a sentence, type while it plays, then wait for it to end: typing is never silent."""
    d.say(line, wait=False)
    type_text(text, interval=interval)
    d.wait_speech()


def post(path, body):
    req = urllib.request.Request("http://127.0.0.1:8765/api/" + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def prehide(categories, user=14):
    """Apply visible Hide controls before the take (shown under Applied now and narrated)."""
    for value in categories:
        p = post("lab/manual", {"user_id": user, "kind": "category", "value": value, "action": "hide"})
        post("lab/apply", {"user_id": user, "preview_id": p["preview_id"]})


def api(path):
    with urllib.request.urlopen("http://127.0.0.1:8765/api/" + path, timeout=30) as r:
        return json.loads(r.read())


def glosses():
    out = {}
    for t in api("lab/labels?user_id=14&limit=2000")["labels"]:
        if t.get("gloss_en"):
            out[t["value"]] = t["gloss_en"]
    return out


def spoken_controls(texts, gloss, limit=4):
    words = []
    for text in texts:
        m = re.match(r"(Show more|Show less|Hide|Show only)(?: \((\w+)\))?: (.+?) '(.+)'", text)
        if not m:
            continue
        action, _, kind, value = m.groups()
        name = gloss.get(value, "a label")
        words.append(f"{action.lower()} {kind.replace('KuaiRec ', '')} {name}")
    if not words:
        return "no control"
    more = f", and {len(words) - limit} more" if len(words) > limit else ""
    return "; ".join(words[:limit]) + more


def money(v):
    if not v or v < 0.01:
        return "less than one cent"
    return f"about {round(v * 100):d} cents" if v < 1 else f"about {v:.2f} dollars"


def calls_line(p):
    calls = [c for c in p.get("calls", []) if not c.get("error")]
    secs = sum(c.get("latency_s") or 0 for c in calls)
    cost = sum(c.get("cost_usd") or 0 for c in calls)
    return f"{len(calls)} model call{'s' if len(calls) != 1 else ''}, {secs:.0f} seconds of model time, {money(cost)}"


def wait_done(d, before, task, trigger=None, limit=360):
    """Wait for the page to finish a request, explaining each stage so no gap reaches five seconds.
    If the trigger click did not start anything, click it once more; give up after ``limit`` seconds."""
    lines = list(WAIT_LINES.get(task, []))
    page = d.page
    done = lambda: page.evaluate("b => (window.labDone || 0) > b", before)
    busy = lambda: page.evaluate("t => !!document.querySelector('[data-role=stage]') || !!(t && document.querySelector(t)?.disabled)", trigger)
    started = time.monotonic()
    nudged = False
    d.wait_speech()
    while not done():
        if time.monotonic() - started > limit:
            raise RuntimeError(f"The {task} request did not finish within {limit} s.")
        if trigger and not nudged and time.monotonic() - started > 3 and not busy() and not done():
            if page.locator(trigger).first.is_enabled():
                page.click(trigger, timeout=5000)   # the first click did not register: send it again
            nudged = True
            d.events.append({"t": round(d.cap.now(), 2), "nudged": trigger})
            continue
        if lines:
            d.say(lines.pop(0), wait=False)
        elif time.monotonic() > d.speech_end + 1.5:
            stage = page.evaluate('document.querySelector("[data-role=stage] b")?.textContent || ""')
            d.say(f"Still waiting for the model, {stage} so far." if stage else FILLER, wait=False)
        while time.monotonic() < d.speech_end - 0.2 and not done():
            time.sleep(0.2)
        time.sleep(0.3)
    d.wait_speech()
    return page.evaluate("window.labLastError || null")


def done_count(page):
    return page.evaluate("window.labDone || 0")


def test_clip(d, page, cfg):
    d.say("This is a short calibration clip.")
    d.click("[data-view='lab']", "The pointer moves to the Language controls tab, and the ring highlights it.")
    page.wait_for_selector(".lab-card")
    d.choose("[data-role='provider-kind']", "Provider: the OpenAI API.", "Op")
    d.type_into("[data-role='provider-model']", "gpt-5", "Model: GPT five.")
    d.click("[data-role='api-key']", "I paste a key into the masked field.")
    clipboard(cfg.key)
    try:
        if GUARD:
            GUARD()
        pyautogui.hotkey("ctrl", "v")
    finally:
        clipboard("")
    time.sleep(0.4)
    d.click("[data-role='provider-save']", "Use this provider.")
    time.sleep(1.0)
    source = api("lab/status")["provider"].get("key_source", "")
    d.events.append({"key_source": source})
    d.say("The key is held in memory." if "memory" in source else "The key was not accepted.")
