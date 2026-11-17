"""The narrated take, English only, one short line per step (used by record_demo.py)."""
from __future__ import annotations

import time

import pyautogui

import demo_script
from demo_script import (SPOKEN_MODEL, api, calls_line, clipboard, done_count, glosses, say_while_typing,
                         spoken_controls, wait_done)


def run_demo(d, page, cfg, events, model_label, results_line):
    gloss = glosses()
    spoken_model = SPOKEN_MODEL.get(cfg.model, cfg.model)
    # A to E
    d.say("Feed Control Lab: natural-language control of a short-video recommender on real KuaiRec data. A trained SASRec model ranks; the language model only proposes, and I review.")
    d.click("button.condition:has-text('Free text')", "First, the original study. Condition C takes a free-text category instruction.")
    d.type_into("#control", "Show me more category_5", "I name one category by its dataset ID.")
    d.click("button:has-text('Apply instruction')", "Apply. The rule parser reads it, and the fixed policy boosts that category.")
    page.wait_for_selector(".active-instruction", timeout=30000)
    d.hold(2.0)
    # Language controls
    d.click("[data-view='lab']", "Now the language controls.")
    page.wait_for_selector(".lab-card")
    d.say("Everything here is English: the KuaiRec text was machine-translated before processing, and the models read the English text.")
    d.say("On the right: this user's top ten from the trained model.")
    d.hold(3.0)
    d.choose("[data-role='provider-kind']", "Provider: the OpenAI API.", "Op")
    d.type_into("[data-role='provider-model']", cfg.model, f"Model: {spoken_model}, fast and inexpensive, and the best of my tests at new categories.")
    d.choose("[data-role='provider-effort']", "Reasoning effort low, the same setting as the measured results.", "lo")
    d.click("[data-role='api-key']", "This is where your own API key goes. I paste mine into the masked field.")
    clipboard(cfg.key)
    try:
        if demo_script.GUARD:
            demo_script.GUARD()
        pyautogui.hotkey("ctrl", "v")
    finally:
        clipboard("")                  # the key leaves the clipboard at once, also if the take aborts
    time.sleep(0.4)
    d.click("[data-role='provider-save']", "Use this provider. The key stays in this server's memory only; it is never shown, logged or saved.")
    status = {}
    for attempt in range(2):
        for _ in range(16):                      # the save can take a few seconds; wait up to 8 s
            time.sleep(0.5)
            status = api("lab/status")["provider"]
            if "memory" in status.get("key_source", ""):
                break
        if "memory" in status.get("key_source", "") or attempt:
            break
        if not page.locator("[data-role='api-key']").input_value():
            break                                # the field is empty: nothing to save again
        d.events.append({"t": round(d.cap.now(), 2), "nudged": "provider-save"})
        page.click("[data-role='provider-save']")   # the first click did not register: send it again
    if "memory" not in status.get("key_source", ""):
        raise RuntimeError("The page did not report the pasted key as held in memory; the take is aborted.")
    d.say("The status line confirms it: key typed into this page, memory only.")
    # 1. Manual: hide the news and incident categories, kept applied for the rest of the take
    d.click("[data-tab='manual']", "Workflow one, the reference: a manual category control. No model.")
    d.say("This user's feed is full of news and incident stories, so first I hide those categories.")
    for word, picks in (("incident", ("Social incident", "Legal incident")), ("news", ("Social news", "Livelihood news")),
                        ("disaster", ("Disaster accident",))):
        d.click("[data-role='label-filter']", f"I search for {word}.")
        d.page.fill("[data-role='label-filter']", "")
        say_while_typing(d, word, "Labels can be searched in English.")
        time.sleep(0.8)
        for value in picks:
            d.click(f"[data-role='label-list'] option[value='{value}']", f"I pick {value}.")
    d.choose("[data-role='manual-action']", "The action is Hide.", "Hi")
    b = done_count(page)
    d.click("[data-role='manual-preview']", "Preview. A preview never changes the feed.")
    wait_done(d, b, "manual", "[data-role='manual-preview']")
    ch = page.evaluate("window.labLastPreview")["changes"]
    d.say(f"Five hide controls: {ch['eligible_before'] - ch['eligible_after']} videos would leave the feed, and {len(ch['left'])} leave the top ten.")
    d.click("[data-role='apply']", "Apply changes exactly the reviewed set. These stay applied for the rest of this video.")
    page.wait_for_function("!document.querySelector('[data-role=review]')")
    d.say("The news and incident categories are now listed under Applied now.")
    # A second manual control, applied and then undone, to show Undo
    d.click("[data-role='label-filter']", "Now one more: dance.")
    d.page.fill("[data-role='label-filter']", "")
    say_while_typing(d, "dance", "I search for dance.")
    time.sleep(0.8)
    d.click(f"[data-role='label-list'] option[value='{cfg.manual_value}']", "I pick Dance.")
    d.choose("[data-role='manual-action']", "Show more,", "Show m")
    d.choose("[data-role='lab-strength']", "strong.", "str")
    b = done_count(page)
    d.click("[data-role='manual-preview']", "Preview.")
    wait_done(d, b, "manual", "[data-role='manual-preview']")
    ch = page.evaluate("window.labLastPreview")["changes"]
    d.say(f"{len(ch['entered'])} dance videos would enter the top ten.")
    d.click("[data-role='apply']", "Apply.")
    page.wait_for_function("!document.querySelector('[data-role=review]')")
    d.say("Each card names the control that moved it.")
    d.click("[data-role='undo']", "Undo removes the dance boost and restores the previous feed exactly; the news hide stays.")
    # 2. Nonliteral requests in two domains
    for n, ex in enumerate(cfg.interpret):
        d.click("[data-tab='interpret']", "Workflow two: a request in my own words, mapped to existing categories and tags." if n == 0
                else "A second request, in another domain.")
        d.click("[data-role='request']", ex["say"])
        pyautogui.hotkey("ctrl", "a"); pyautogui.press("delete")
        say_while_typing(d, ex["request"], "No category name is used.")
        b = done_count(page)
        d.click("[data-role='interpret-preview']", "Interpret and preview.")
        err = wait_done(d, b, "interpret", "[data-role='interpret-preview']")
        d.say("The answer is back.", wait=False)
        if err:
            d.say("The call failed; the page shows the error, and nothing changed.")
            d.hold(3.0)
            continue
        p = page.evaluate("window.labLastPreview")
        d.say(f"Proposal: {spoken_controls(p['controls'], gloss)}. {calls_line(p)}.")
        d.ensure_visible("[data-role='review']")
        d.hold(2.0)
        if p["applicable"]:
            d.click("[data-role='apply']", "Apply.")
            page.wait_for_function("!document.querySelector('[data-role=review]')")
            d.hold(3.0)
            d.click("[data-role='undo']", "Undo.")
            d.hold(2.0)
        else:
            d.click("[data-role='discard']", "Nothing to apply, so I discard it.")
    # 3. New category
    d.click("[data-tab='category']", "Workflow three: a new category that KuaiRec does not have.")
    d.click("[data-role='category-description']", "I describe it.")
    say_while_typing(d, cfg.new_category, "Plain English, no existing label.", interval=0.035)
    d.choose("[data-role='scope']", "The scope is the top fifty videos of this user's current feed; the hidden news videos are left out.", cfg.scope)
    b = done_count(page)
    d.click("[data-role='define']", "Step one: propose a definition.")
    wait_done(d, b, "define", "[data-role='define']")
    d.say("The answer is back.", wait=False)
    defn = page.evaluate("window.labLastDefinition")
    d.ensure_visible("[data-role='definition']")
    d.say(f"A label, a definition with conditions, and {defn['evidence']} cited examples, each quotation checked.")
    d.hold(3.0)
    d.type_into("[data-role='definition-label']", cfg.category_label, "I review it, and shorten the label.")
    d.choose("[data-role='category-action']", "When applied: show more.", "Show m")
    b = done_count(page)
    d.click("[data-role='classify']", "Approve and classify.")
    wait_done(d, b, "classify", "[data-role='classify']")
    d.say("The answer is back.", wait=False)
    p = page.evaluate("window.labLastPreview")
    d.ensure_visible(".lab-table")
    d.say(f"One row per video: verdict, quotation, independent check. {p['selected']} of {p['rows']} selected. {calls_line(p)}.")
    d.events.append({"new_category": {"selected": p["selected"], "rows": p["rows"], "entered": p["changes"].get("entered", []),
                                      "left": p["changes"].get("left", [])}})
    d.hold(4.0)
    d.say("The feed stays visible on the right during review.")
    d.hold(2.0)
    if p["applicable"]:
        d.click("[data-role='apply']", "Apply. The new category is now a label of its own.")
        page.wait_for_function("!document.querySelector('[data-role=review]')")
        entered = len(p["changes"].get("entered", []))
        d.say(f"{entered} of its videos enter the top ten, and its members move up." if entered
              else "Its members move up in the ranking; none enters the top ten.")
        d.hold(2.0)
    # 4. New items
    d.click("[data-tab='items']", "Workflow four: add a video that is not in KuaiRec.")
    d.click("[data-role='new-title-0']", "A title")
    say_while_typing(d, cfg.new_item["title"], "and", interval=0.035)
    d.click("[data-role='new-description-0']", "a description.")
    say_while_typing(d, cfg.new_item["description"], "The model sees only these words.", interval=0.03)
    b = done_count(page)
    d.click("[data-role='new-items-preview']", "Classify and preview.")
    wait_done(d, b, "new-items", "[data-role='new-items-preview']")
    d.say("The answer is back.", wait=False)
    d.ensure_visible("[data-role='review']")
    q = page.evaluate("window.labLastPreview")
    d.events.append({"new_item": {"joined": q.get("joined", 0)}})
    if q.get("joined"):
        d.say("It got existing categories and tags. For my new category: a match, with a quotation and a passed independent check, so it joins the category.")
    else:
        d.say("It got existing categories and tags. For my new category it was not selected; the review says why.")
    d.hold(4.0)
    d.click("[data-role='apply']", "Apply. It starts at this user's median score, since the recommender has no history for it, so it does not reach the top ten by itself.")
    page.wait_for_function("!document.querySelector('[data-role=review]')")
    d.hold(2.5)
    d.click("[data-role='undo']", "Undo removes the new video; the new category and its members stay.")
    # Results: slower, every headline number read from the result files
    d.click("[data-view='results']", "The Results page reads the measured result files. I will go through the headline numbers.")
    page.wait_for_selector("[data-role='results']")
    d.point("[data-role='text-label']", "These numbers were measured on the original-text run of 17 November. The re-run on the English text is pending.")
    keep = ("The first table", "Next, cases", "For new categories", "Local versus frontier", "Finally, the old")
    for line in [l for l in results_line if l["say"].startswith(keep)]:
        d.say(line["say"], wait=False)
        if line.get("selector"):
            d.ensure_visible(line["selector"])
        d.wait_speech()
        time.sleep(line.get("hold", 3.0))
    d.say("The test set was drafted by an AI and reviewed row by row by me. Claude is both the drafter's family and a measured model.")
    d.say("Code, tests, data and results are in the repository. Thank you.")
    d.check_cjk("end of take")
    d.events.append({"cjk_checks": d.cjk_checks, "cjk_hits": 0})
