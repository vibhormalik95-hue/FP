# Demo video, take 13 (17 November 2026): English-only application

File (sent separately, not in the repository): `COMP9500-Feed-Control-Lab-demo.mp4`, 10:12, 1920x1080, one continuous take by `tools/recording/record_demo.py` (real pointer, highlight ring, ripple, Kokoro af_heart narration), recorded on the English-only application of tag `comp9500-final-2026-11-r4`.

- All KuaiRec text on screen is the English text layer (machine translation of KuaiRec, CC BY-SA 4.0). The recorder ran the CJK probe (`tests/browser/cjk_probe.js`) live before every pointer action and hold: 69 checks, no visible CJK character.
- Research user 14. The manual step hides the five news and incident categories (Social incident, Legal incident, Social news, Livelihood news, Disaster accident) with Preview and Apply; they stay applied for the rest of the take. Undo is shown on the dance boost and later steps.
- The API key is pasted into the masked field and confirmed as held in memory only; it is never shown. The clipboard is cleared at once and excluded from clipboard history.
- Model: OpenAI gpt-5 at minimal reasoning effort for speed; the narration says the measured results used low effort.
- The Results page shows the five-model tables, labelled "Measured on the original-text run (17 Nov); English-input re-run pending", and the narration says so.

Checks (`tools/recording/check_take.py`, `check.json`): no silence of 5 s or more at -45 dB; faster-whisper small.en transcript matches 96/96 script sentences (similarity 0.89); one frame every 30 s (`contact-sheet.png`); live CJK check passed.

Take 12 (`docs/evidence/2026-11-17-video-take12/`, recorded before the English layer) and take 11 are kept as backups.
