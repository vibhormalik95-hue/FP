# Feed Control Studio: step-by-step guide

This guide follows the demonstration video step by step. You need about ten minutes and an Anthropic API key. Nothing asks for a password.

Feed Control Studio is the application for the COMP 9500 project "LLM-mediated natural-language controls for short-video recommender systems". A language model proposes each change to the feed. The application checks the proposal against the catalogue. The feed changes only when you click **Apply**, and **Undo** restores the previous feed.

The catalogue holds 40 invented short-video records (title, description, one category, tags) in ten categories. They are not real videos and not KuaiRec items. A fixed score stands in for the recommender's relevance, so every change you see comes from your controls.

## 1. Install (once)

You need Windows 10 or 11 with **Python 3.11 or newer** on the PATH, and Git (or the ZIP from GitHub).

```
git clone https://github.com/vibhormalik95-hue/FP.git
cd FP
studio-setup.cmd
```

`studio-setup.cmd` creates a `.venv` folder and installs the Studio. On macOS or Linux run `python3 -m venv .venv && .venv/bin/pip install -e ".[studio,test]"`.

## 2. Start

```
run-studio.cmd
```

The browser opens **http://127.0.0.1:8765/**. The Studio listens only on your own computer. On macOS or Linux run `.venv/bin/python -m studio`.

![The Studio after start-up](images/studio/01-start.png)

The page has three columns: **Model and key** and the four workflows on the left, **Review** in the middle, and **Your feed** (top 12 videos) with **Applied controls** and **Undo** on the right.

## 3. Paste your API key

1. In **Provider**, choose **Anthropic API (Claude)**.
2. **Model** shows `claude-sonnet-5-5` and **Effort** `low`. These settings finished every test workflow in under 40 seconds. You can type `claude-opus-5-5` instead.
3. Paste your key into **API key**. The field is masked.
4. Click **Use this model**. The status line at the top changes to *Anthropic API · claude-sonnet-5-5 · effort low · key pasted (memory only)*.

The key stays in the memory of the local server process. It is never written to disk, logged, returned by the server or shown on the page. When you close the Studio the key is gone. Instead of pasting, you can set the environment variable `ANTHROPIC_API_KEY` before `run-studio.cmd`.

![The key field and status line](images/studio/02-key.png)

The **OpenAI-compatible** provider works the same way with an OpenAI key, or with a local server such as Ollama (set **Base URL**). **Mock** needs no key; it matches words literally and is only for tests.

## 4. Workflow 1: manual control (no model)

1. Open the **Manual** tab.
2. Choose **Label** `Gaming (4)` and **Action** `Hide`.
3. Click **Preview**. The **Review** column shows that no model was called, the check that Gaming exists, and the effect: eligible videos 40 → 36, the four gaming videos leave the top 12 and others move in. The feed has not changed yet.
4. Click **Apply**. The feed now shows 36 eligible videos and the control appears under **Applied controls**.
5. Click **Undo**. All 40 videos are back.

![Manual control preview](images/studio/03-manual.png)

## 5. Workflow 2: a plain-language request

The request does not have to name a category. The model receives only the request and the existing category and tag names with their counts; it does not see video descriptions.

1. Open **Plain language**.
2. Type: `I'm not hungry, remove all the stuff that makes me hungry.`
3. Click **Interpret and preview**.
4. Read the review: the model call (time, tokens, cost), the words of your request the model quoted, the labels and action it chose and its reason, the application checks (each label exists, the quoted words occur in your request), and the effect on the feed.
5. Click **Apply**, then **Undo**.

A second example from another domain: `My knees are killing me this week, so skip anything that would make me sweat.` Tick **Auto-apply** first to see the change applied immediately; the evidence stays on screen and **Undo** still works.

![Plain-language review](images/studio/04-interpret.png)

## 6. Workflow 3: a new category from a description

1. Open **New category**.
2. Type: `Videos where someone teaches a practical skill step by step, so I can follow along.`
3. Click **Propose a definition**. The model reads all 40 titles and descriptions and proposes a label, a one-paragraph definition and supporting quotes. The application marks each quote *found* or *NOT found* in the video text.
4. Edit the label or the definition if you want. Choose **Then: Show only this category**.
5. Click **Classify all videos and preview**. The model classifies every video under the exact definition in batches of ten, citing an exact quote for each match. A separate call, which never sees the verdicts, checks whether each quote supports the definition. A video is selected only if the classifier matched it, its quote is found in the text, and the independent check agrees.
6. Read the table of matched videos (verdict, quote, reason, independent check). The other videos are listed under the collapsed line below it. Then read the effect on the feed.
7. Click **Apply**. The feed shows only the new category. Keep it applied for the next workflow.

![New-category evidence](images/studio/05-category.png)

## 7. Workflow 4: add new videos

1. Open **Add videos**.
2. Video 1 title `Sourdough starter, day three`; description `A baker shows step by step how to feed the starter, check the bubbles and shape the first loaf.`
3. Click **+ Another video**. Video 2 title `Retro kart racing tournament`; description `Eight players race a classic kart game while the commentator yells at every crash.`
4. Click **Classify and preview**. The model chooses an existing category and existing tags for each video and gives a verdict, with a quote, for your new category.
5. Click **Apply**. The new videos join the catalogue (marked NEW). Because the feed shows only the new category, the tutorial appears and the kart race is filtered out.
6. Click **Undo** twice: first the videos are removed, then the new category.

![New videos classified](images/studio/06-items.png)

## 8. Run every workflow from the command line

```
studio-test.cmd
```

With no arguments this uses the mock provider: no key, no cost. It starts the Studio on a free local port, runs every workflow on several examples from different domains (preview, Apply, check the feed equals the preview, Undo, check the feed is restored) and writes `summary.md`, `results.json` and `calls.csv` to `studio-results\<date-time>-<provider>-<model>\`. Live run:

```
set ANTHROPIC_API_KEY=...your key...
studio-test.cmd --provider anthropic --model claude-sonnet-5-5 --budget-usd 5
```

`--budget-usd` stops the run once the running total of model cost reaches the limit.

## What this shows, and what it does not

- It shows each workflow working end to end on one invented 40-item catalogue with real model calls, with the evidence visible before Apply.
- It does not measure classification accuracy on real data, user satisfaction or recommendation quality. The frozen offline experiments (E1, E2) in this repository are unchanged and are reported separately.
- Categories you create live for the session; they are not saved to the catalogue file.
