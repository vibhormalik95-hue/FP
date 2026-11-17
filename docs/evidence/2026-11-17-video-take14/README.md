# Demo video, take 14 (17 November 2026)

File (sent separately, not in the repository): `COMP9500-Feed-Control-Lab-demo.mp4`, 10:57, 1920x1080, one continuous
take by `tools/recording/record_demo.py` on the English-only application (commit `e1f54e9`).

- Model: OpenAI gpt-5-mini at **low** reasoning effort, the setting of the measured results. The API key is pasted into
  the masked field and confirmed as held in memory only; it is never shown.
- Research user 14. The manual step hides the five news and incident categories (Preview, Apply); they stay applied.
  A dance boost is applied and undone. Two requests in my own words are interpreted, applied and undone.
- New category from "Videos about dogs. Any video whose title, description or tags mention a dog or a puppy belongs to
  the category.", scope: the top 50 items of the current feed. Label shortened to "Dogs", action Show more.
  **3 of 50 selected: 2882, 8902, 7564.** After Apply the top ten changes: before 7383, 2894, 4367, 2687, 4506, 1146,
  5993, 2882, 10184, 8777; after 2882, 8902, 7564, 7383, 2894, 4367, 2687, 4506, 1146, 5993.
- New item "Our puppy's first walk in the park": existing categories Pet dog, Pet daily record, Pets, Everyday candid
  shots; Dogs: match on "puppy", independent check supports, **selected**; Dogs has 4 members after Apply. It starts at
  the user's median score and does not enter the top ten (as the setup predicts). Undo removes it.
- The Results page states that the numbers come from the original-text run (17 Nov) and the English re-run is pending.

Checks (`check.json`): no silence of 5 s or more at -45 dB; transcript 103/103 script sentences (similarity 0.899);
one frame every 30 s (22 frames, `contact-sheet.png`); live CJK check 69 checks, none visible.

Live attempts: 4 (14a aborted at the key check; 14b stopped by a low-memory reaper; 14c failed the silence check and
selected 1 member; 14d passed). Log: `FINAL2/PROGRESS.md`. Take 13 is kept unchanged.
