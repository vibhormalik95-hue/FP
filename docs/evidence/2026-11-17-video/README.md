# Demo video of 17 November 2026

File (not in the repository; sent separately): `COMP9500-Feed-Control-Lab-demo.mp4`, 9:23, 1920x1080, one continuous take recorded by `tools/recording/record_demo.py` (real pointer, highlight ring, ripple, Kokoro af_heart narration).

App: the integrated app on KuaiRec, English display mode (machine translation of the Chinese text), provider OpenAI gpt-5 with the key read from the environment (never shown).

Checks (`tools/recording/check_take.py`, results in `check.json`): no silence of 5 s or more at -45 dB; faster-whisper small.en transcript matches 96/96 script sentences (word-sequence similarity 0.936); one frame every 30 s (`contact-sheet.png`).

Earlier takes 1-10 failed (focus loss, a page bug that kept Preview disabled, missing key paste, silence gaps) and were discarded; the fixes are in the git history of 17 November.
