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
    "interpret": ["The model now reads the request and the list of existing labels. It sees no item text.",
                  "It must copy each label exactly, and quote the words of the request that express the preference.",
                  "When it answers, the server checks every label and the quoted span before anything is shown."],
    "define": ["The model reads the description and the text of this user's forty top items.",
               "It drafts a short label and a definition with conditions, and cites example items with exact quotations.",
               "The server will check that every quotation really occurs in the cited item."],
    "classify": ["Now every item in scope is classified under the reviewed definition, ten items per call, four calls at a time.",
                 "Each match must come with an exact quotation from the item's own Chinese text.",
                 "A separate model call then checks each quotation without seeing the verdict.",
                 "Only items whose quotation exists and passes this independent check are selected.",
                 "Nothing is applied yet. The result comes back as a preview for review."],
    "new-items": ["The model reads the new item's title and description and the existing KuaiRec categories and tags.",
                  "It may only choose labels that exist, and it judges the new category with a quotation.",
                  "The server drops any label that does not exist before the preview is shown."],
}
FILLER = "The model is still working. Long waits are normal for hosted models; the stage line on the page counts the seconds."


def clipboard(text):
    """Put text on the Windows clipboard (used to type characters a keyboard layout cannot)."""
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = (text + "\0").encode("utf-16-le")
    for _ in range(20):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    u32.EmptyClipboard()
    if text:
        h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ctypes.memmove(k32.GlobalLock(h), data, len(data))
        k32.GlobalUnlock(h)
        u32.SetClipboardData(CF_UNICODETEXT, h)
    u32.CloseClipboard()


def type_text(text, interval=0.05):
    """Character by character with the real keyboard; non-ASCII characters through the clipboard."""
    for ch in text:
        if ord(ch) < 128:
            pyautogui.write(ch, interval=0)
        else:
            clipboard(ch)
            pyautogui.hotkey("ctrl", "v")
        time.sleep(interval if ord(ch) < 128 else 0.12)
    clipboard("")


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


def wait_done(d, before, task):
    """Wait for the page to finish a request, explaining each stage so no gap reaches five seconds."""
    lines = list(WAIT_LINES.get(task, []))
    page = d.page
    done = lambda: page.evaluate("b => (window.labDone || 0) > b", before)
    d.wait_speech()
    started = time.monotonic()
    while not done():
        if lines:
            d.say(lines.pop(0), wait=False)
        elif time.monotonic() - started > 20:
            d.say(FILLER, wait=False)
            started = time.monotonic()
        while time.monotonic() < d.speech_end - 0.2:
            if done():
                break
            time.sleep(0.2)
        if done():
            break
        if not lines:
            time.sleep(1.0)    # pauses stay short: the next filler comes long before five seconds pass
            if not done():
                d.say(f"Still waiting: {page.evaluate('document.querySelector(\"[data-role=stage] b\")?.textContent || \"\"')}.", wait=True)
    d.wait_speech()
    err = page.evaluate("window.labLastError || null")
    return err


def done_count(page):
    return page.evaluate("window.labDone || 0")


def run_demo(d, page, cfg, events, model_label, results_line):
    gloss = glosses()
    spoken_model = SPOKEN_MODEL.get(cfg.model, cfg.model)
    # ---------------------------------------------------------------- intro and A to E
    d.say("This is the Feed Control Lab for my COMP 9500 project: natural-language controls for a short-video recommender.")
    d.say("Everything runs on this laptop, on the real KuaiRec dataset: eight hundred sixty-five users and two thousand five hundred ninety-three videos.")
    d.say("A SASRec model that I trained on KuaiRec ranks the videos. The language model never ranks anything. It only proposes a change that I review.")
    d.click("button.condition:has-text('Free text')", "First, the original study view with conditions A to E. I choose condition C, the free-text category instruction.")
    d.type_into("#control", "Show me more category_5", "I type an instruction that names one KuaiRec category by its opaque ID.")
    before = page.evaluate("document.querySelector('.feed-grid')?.innerText || ''")
    d.click("button:has-text('Apply instruction')", "Apply instruction. The rule parser reads category five, and a fixed policy adds a quarter point to those items' normalized scores.")
    page.wait_for_selector(".active-instruction", timeout=30000)
    d.say("The ranking changed: the cards now show the active category boost, and the latest instruction is listed above the feed.")
    d.hold(3.0)
    d.say("This is the frozen baseline of the study. It only understands opaque category IDs. The language controls add what my supervisor asked for.")
    # ---------------------------------------------------------------- provider
    d.click("[data-view='lab']", "I open the Language controls view.")
    page.wait_for_selector(".lab-card")
    d.say("On the right is the feed for this user, ranked by the trained model. Each card shows the original Chinese text from KuaiRec and an English line, clearly labelled machine translation.")
    d.hold(3.0)
    d.choose("[data-role='provider-kind']", "I choose the model provider. The professor can use any OpenAI key here.", "Op")
    d.type_into("[data-role='provider-model']", cfg.model, f"The model is {spoken_model}, the best model in my measurements that needs only an API key.")
    d.click("[data-role='api-key']", "I paste the key. The field is masked, and the server keeps the key in memory only. It is never written to disk or shown again.")
    clipboard(cfg.key)
    pyautogui.hotkey("ctrl", "v")
    clipboard("")
    time.sleep(0.4)
    d.click("[data-role='provider-save']", "Use this provider.")
    d.hold(2.0)
    # ---------------------------------------------------------------- manual
    d.click("[data-tab='manual']", "Workflow one is the reference: a manual category control, with no model at all.")
    d.click("[data-role='label-filter']", "I filter the KuaiRec categories.")
    type_text(cfg.manual_value)
    time.sleep(0.8)
    d.click(f"[data-role='label-list'] option[value='{cfg.manual_value}']", f"I pick the category {gloss.get(cfg.manual_value, 'pets')}.")
    d.choose("[data-role='manual-action']", "The action is Hide.", "Hi")
    b = done_count(page)
    d.click("[data-role='manual-preview']", "Preview. A preview never changes the feed.")
    wait_done(d, b, "manual")
    p = page.evaluate("window.labLastPreview")
    ch = p["changes"]
    d.say(f"The review shows the control, the checks, and the effect: eligible videos would drop from {ch['eligible_before']} to {ch['eligible_after']}, and {len(ch['entered'])} new videos would enter the top ten.")
    d.click(".lab-feed .view-tabs button:has-text('Before')", "On the right I can compare the feed before")
    d.click(".lab-feed .view-tabs button:has-text('After')", "and after Apply.")
    d.hold(2.0)
    d.click("[data-role='apply']", "I approve it. Apply changes exactly the reviewed set, nothing else.")
    page.wait_for_function("!document.querySelector('[data-role=review]')")
    d.say("The feed is filtered, and the applied control is listed under Applied now.")
    d.hold(3.0)
    d.click("[data-role='undo']", "Undo restores the previous state exactly.")
    d.hold(3.0)
    # ---------------------------------------------------------------- nonliteral requests
    for ex, apply_it in ((cfg.interpret[0], True), (cfg.interpret[1], True)):
        d.click("[data-tab='interpret']", "Workflow two maps a request in my own words to existing KuaiRec categories and tags." if apply_it and ex is cfg.interpret[0]
                else "A second request, in a different domain, written in Chinese.")
        d.click("[data-role='request']", ex["say"])
        type_text(ex["request"], interval=0.04)
        time.sleep(0.5)
        b = done_count(page)
        d.click("[data-role='interpret-preview']", "Interpret and preview.")
        err = wait_done(d, b, "interpret")
        if err:
            d.say("The model call failed, and the page shows the error. Nothing was changed.")
            d.hold(3.0)
            continue
        p = page.evaluate("window.labLastPreview")
        d.say(f"The model proposes: {spoken_controls(p['controls'], gloss)}. That took {calls_line(p)}.")
        d.ensure_visible("[data-role='review']")
        d.say("Block one shows what came back, with the model's reason. Block two shows the application's checks: every label exists, and the quoted span is really in my request.")
        d.hold(3.0)
        d.say(f"The feed on the right previews the result: eligible videos go from {p['changes']['eligible_before']} to {p['changes']['eligible_after']}.")
        d.hold(3.0)
        if p["applicable"]:
            d.click("[data-role='apply']", "I apply it.")
            page.wait_for_function("!document.querySelector('[data-role=review]')")
            d.say("Applied. The cards now name the control that moved them.")
            d.hold(3.0)
            d.click("[data-role='undo']", "And Undo puts the feed back.")
            d.hold(2.5)
        else:
            d.click("[data-role='discard']", "There is nothing to apply, so I discard it.")
    # ---------------------------------------------------------------- new category
    d.click("[data-tab='category']", "Workflow three creates a category that KuaiRec does not have, from a description.")
    d.click("[data-role='category-description']", "I describe it in plain English.")
    type_text(cfg.new_category, interval=0.035)
    b = done_count(page)
    d.click("[data-role='define']", "Step one: propose a definition.")
    err = wait_done(d, b, "define")
    defn = page.evaluate("window.labLastDefinition")
    d.ensure_visible("[data-role='definition']")
    d.say(f"The model proposed a label and a definition with explicit conditions, and cited {defn['evidence']} example items. Each quotation shows a check mark when it was found in the item's text.")
    d.hold(3.5)
    d.say("I review the definition. I could edit the label or the conditions before anything is classified.")
    d.choose("[data-role='category-action']", "When applied, I want to see more of these videos.", "Sh")
    b = done_count(page)
    d.click("[data-role='classify']", "I approve the definition, and the model classifies every item in scope.")
    err = wait_done(d, b, "classify")
    p = page.evaluate("window.labLastPreview")
    d.ensure_visible(".lab-table")
    d.say(f"The evidence table has one row per item: the verdict, the exact quotation, and the independent check. {p['selected']} of {p['rows']} items were selected. That took {calls_line(p)}.")
    d.hold(4.0)
    d.scroll_by(260)
    d.say("Matches whose quotation was not found, or that the independent check rejected, are not selected. The feed stays visible on the right while I read.")
    d.hold(3.5)
    if p["applicable"]:
        d.click("[data-role='apply']", "I apply the new category.")
        page.wait_for_function("!document.querySelector('[data-role=review]')")
        d.say("The new category is now a label of its own, with its members, and its videos are boosted in the feed.")
        d.hold(3.0)
    # ---------------------------------------------------------------- new items
    d.click("[data-tab='items']", "Workflow four adds new videos that are not in KuaiRec.")
    d.click("[data-role='new-title-0']", "A title")
    type_text(cfg.new_item["title"], interval=0.035)
    d.click("[data-role='new-description-0']", "and a description.")
    type_text(cfg.new_item["description"], interval=0.03)
    b = done_count(page)
    d.click("[data-role='new-items-preview']", "Classify and preview.")
    wait_done(d, b, "new-items")
    d.ensure_visible("[data-role='review']")
    d.say("The model assigned existing KuaiRec categories and tags to the new video, and judged it against my new category with a quotation, checked independently again.")
    d.hold(4.0)
    d.click("[data-role='apply']", "I apply it. The video joins the catalogue with a cold-start score, because the trained model has no history for it.")
    page.wait_for_function("!document.querySelector('[data-role=review]')")
    d.hold(3.0)
    d.click("[data-role='undo']", "Undo removes the new video")
    d.click("[data-role='undo']", "and a second Undo removes the new category.")
    d.hold(2.5)
    # ---------------------------------------------------------------- results
    d.scroll_to_top()
    d.click("[data-view='results']", "Finally, the Results page. It reads the result files of my measurement.")
    page.wait_for_selector("[data-role='results']")
    for line in results_line:
        if line.get("selector"):
            d.ensure_visible(line["selector"])
        d.say(line["say"])
        d.hold(3.0)
    d.say("The reference answers were drafted by an AI and reviewed row by row by me. Claude is both the drafter's family and one of the measured models, which the report states.")
    d.say("Everything shown is in the repository, with run-all-tests to repeat the checks. Thank you.")
    d.hold(2.0)


def test_clip(d, page, cfg):
    d.say("This is a short calibration clip.")
    d.click("[data-view='lab']", "The pointer moves to the Language controls tab, and the ring highlights it.")
    page.wait_for_selector(".lab-card")
    d.click("[data-tab='interpret']", "I open workflow two.")
    d.click("[data-role='request']", "I type a request into the box.")
    type_text("Show me more 篮球", interval=0.05)
    d.hold(1.0)
