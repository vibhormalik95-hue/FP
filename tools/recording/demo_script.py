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
from pathlib import Path

import pyautogui

SPOKEN_MODEL = {"gpt-5-mini": "GPT five mini", "gpt-5": "GPT five", "claude-sonnet-5-5": "Claude Sonnet five point five"}
WAIT_LINES = {
    "interpret": ["The model reads the request and the list of existing labels. It sees no video text.",
                  "Next, the server checks that every label exists and that the quoted words are in the request."],
    "define": ["The model reads the description and the top videos of this user's current feed.",
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
    """Set (or, with an empty string, clear) the Windows clipboard. The value goes through stdin, never a
    command line. The data carries the formats that keep it out of Windows clipboard history and cloud
    clipboard sync (ExcludeClipboardContentFromMonitorProcessing, CanIncludeInClipboardHistory=0,
    CanUploadToCloudClipboard=0), so clearing it leaves no copy behind."""
    import subprocess
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
$v = [Console]::In.ReadToEnd()
if ($v.Length -eq 0) { [System.Windows.Forms.Clipboard]::Clear(); exit 0 }
$d = New-Object System.Windows.Forms.DataObject
$d.SetData([System.Windows.Forms.DataFormats]::UnicodeText, $v)
$zero = New-Object System.IO.MemoryStream (,[byte[]](0,0,0,0))
$d.SetData('ExcludeClipboardContentFromMonitorProcessing', (New-Object System.IO.MemoryStream (,[byte[]](0))))
$d.SetData('CanIncludeInClipboardHistory', $zero)
$d.SetData('CanUploadToCloudClipboard', (New-Object System.IO.MemoryStream (,[byte[]](0,0,0,0))))
[System.Windows.Forms.Clipboard]::SetDataObject($d, $true)
"""
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-STA", "-Command", script], input=text,
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
    """Spoken names of the labels. The labels are English already, so each name is the label itself."""
    return {t["value"]: t["value"] for t in api("lab/labels?user_id=14&limit=2000")["labels"]}


def spoken_controls(texts, gloss, limit=4):
    words = []
    for text in texts:
        m = re.match(r"(Show more|Show less|Hide|Show only)(?: \((\w+)\))?: (.+?) '(.+)'", text)
        if not m:
            continue
        action, _, kind, value = m.groups()
        name = gloss.get(value, value)
        words.append(f"{action.lower()} {kind.replace('KuaiRec ', '')} {name}")
    if not words:
        return "no control"
    more = f", and {len(words) - limit} more" if len(words) > limit else ""
    return "; ".join(words[:limit]) + more


def money(v):
    """Spoken cost of a list-price estimate. None (unknown) is never turned into a number."""
    if v is None:
        return "cost not known"
    if v == 0:
        return "no API charge"
    if v < 0.01:
        return "an estimated cost below one cent"
    return f"an estimated {round(v * 100):d} cents" if v < 1 else f"an estimated {v:.2f} dollars"


def calls_line(p):
    calls = p.get("calls", [])
    ok = [c for c in calls if not c.get("error")]
    failed = len(calls) - len(ok)
    secs = sum(c.get("latency_s") or 0 for c in ok)
    unknown = sum(c.get("cost_usd") is None for c in calls)
    cost = None if unknown == len(calls) and calls else sum(c.get("cost_usd") or 0 for c in calls)
    line = f"{len(ok)} model call{'s' if len(ok) != 1 else ''}, {secs:.0f} seconds of model time summed over the calls, {money(cost)}"
    if unknown and cost is not None:
        line += f", plus {unknown} call{'s' if unknown != 1 else ''} of unknown cost"
    if failed:
        line += f"; {failed} call{'s' if failed != 1 else ''} failed"
    return line


MEASURED_SUMMARY = Path(__file__).resolve().parents[2] / "docs/evidence/lab-eval/20261117-main/summary.json"


def measured_summary(path=MEASURED_SUMMARY):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def model_line(model, spoken, summary):
    """What the narration says about the chosen model: only facts from the published measured summary."""
    s = (summary or {}).get("summaries", {}).get(model)
    if not s:
        return f"Model: {spoken}. It was not measured under this name, so I make no claim about its accuracy."
    f1 = {n: v.get("nc_member_f1") for n, v in summary["summaries"].items() if v.get("nc_member_f1") is not None}
    best = max(f1, key=f1.get) if f1 else None
    line = f"Model: {spoken}. In my measured runs it chose the exact labels for {s['nl_exact']} of {s['nl_cases']} nonliteral requests"
    if s.get("nc_member_f1") is not None:
        line += f", with a new-category member F1 of {s['nc_member_f1']:.2f}" + (", the highest of the measured models" if best == model else "")
    return line + "."


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
    d.click("[data-tab='manual']", "The manual tab.")
    d.click("[data-role='label-filter']", "I search for incident.")
    d.page.fill("[data-role='label-filter']", "")
    say_while_typing(d, "incident", "Labels are English.")
    time.sleep(0.8)
    d.click("[data-role='label-list'] option[value='Social incident']", "I pick Social incident.")
    d.click("[data-tab='category']", "The new category tab.")
    d.choose("[data-role='scope']", "The scope is a list now: ten.", "10")
    d.events.append({"scope": d.page.locator("[data-role='scope']").input_value()})
    d.click("[data-view='results']", "The Results page.")
    d.page.wait_for_selector("[data-role='results']")
    d.point("[data-role='text-label']", "Each run says which text it was measured on.")
    d.check_cjk("end of test clip")
    d.events.append({"cjk_checks": d.cjk_checks, "cjk_hits": 0})
