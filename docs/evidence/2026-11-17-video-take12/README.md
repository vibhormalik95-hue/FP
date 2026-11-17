# Demo video, take 12 (17 November 2026)

File (sent separately, not in the repository): `COMP9500-Feed-Control-Lab-demo.mp4`, 10:22, 1920x1080, one continuous take by `tools/recording/record_demo.py` (real pointer, highlight ring, ripple, Kokoro af_heart narration).

- Research user 14. The trained ranker puts news and incident stories in every user's top ten (see `docs/evidence/2026-11-17-popularity/`), so the manual-control step first hides the five KuaiRec news and incident categories (Preview, Apply); they stay applied for the rest of the take, and Undo is shown on a later control.
- The API key is pasted into the masked field and confirmed as held in memory only; it is never shown. The clipboard is cleared at once and its data is excluded from clipboard history.
- Model: OpenAI gpt-5 at **minimal** reasoning effort, chosen for the video because gpt-5 at low effort took up to 240 s per call that day. The measured results use low effort; the narration says so.
- English display mode (machine translation of the Chinese KuaiRec text).
- The Results page shows the final five-model tables with their commits.

Checks (`tools/recording/check_take.py`, `check.json`): no silence of 5 s or more at -45 dB; faster-whisper small.en transcript matches 97/97 script sentences (word-sequence similarity 0.898); one frame every 30 s (`contact-sheet.png`).

Take 11 (9:23, `docs/evidence/2026-11-17-video/`) is kept as a backup. Takes 12-12e were discarded (a foreign window took focus; length over 12 minutes because of slow gpt-5 calls).
