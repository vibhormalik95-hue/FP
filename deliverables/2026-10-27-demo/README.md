# COMP 9500 professor demo, 27 October 2026

Start with the [39-item plan acceptance audit](PLAN-ACCEPTANCE-AUDIT-2026-10-27.md) and [timed professor demo script](PROFESSOR-DEMO-SCRIPT.md). The [full-talk notes](FINAL-TALK-NOTES-2026-10-27.md) follow the current 30-page BCIT deck; the [cold-review response and claim map](COLD-REVIEW-AND-CLAIM-MAP-2026-10-27.md) lists checks and unresolved findings. The [earlier 26 October evidence matrix](EVIDENCE-AND-135-HOURS.md) remains as a dated progress snapshot. The [dated review paper and slides](../2026-10-19/README-2026-10-19.md), [fresh AI-reference E2 results](../../docs/ai-reference-e2-results-2026-10-14.md), and [compact evidence index](../../docs/ai-reference-e2-evidence/README.md) are also in this repository.

## Launch on the research laptop

The public checkout omits the processed research dataset, saved checkpoint and built frontend. Use the existing private full research archive for those inputs; do not download or replace frozen Experiment 1 material. In PowerShell, from the prepared full project folder containing `data/processed.json`, `results/models/seed_42`, and `web/dist`:

```powershell
python -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`; stop the server with **Ctrl+C** in its PowerShell window. If port 8000 is occupied, use `--port 8765` and open that port. Do not stop another process to free a port. Confirm the visible status says **processed dataset**, **trained model** and **rule** before using the script. A missing dataset or checkpoint can activate fixture or diagnostic mode; label it honestly. The app shows metadata cards, not playable videos.

A 27 October isolated working copy passed the full 278-test Python suite, a 1,613-file archive integrity check, and 22 historical release-verifier technical checks. The frontend rebuilt from the lockfile with matching output hashes. Rendered browser checks covered A-E, reset and user isolation. A single fresh local `llama3.1:8b` parser request succeeded, displaying its exact recorded model digest in the UI. The [claim map](COLD-REVIEW-AND-CLAIM-MAP-2026-10-27.md) separates these technical checks from scientific replay. Use the review paper and saved result receipts if the app is unavailable.

The [paper source](../../paper/research-paper-2026-10-19.tex) on this branch clarifies the separate 20 October parser-only check. The already published [dated paper PDF](../2026-10-19/COMP9500-Research-Paper-2026-10-19.pdf) has not been regenerated; a corrected seven-page PDF is prepared privately for review. Neither version is a final supervisor-approved submission.

## Study boundary

The interface is the original A-E control demonstrator. It supports one category per instruction and an editable profile. It does not implement the fresh E2 compound, floor or conditional request interface. Show that study through its saved protocol and result evidence. Do not call rule-parser clicks live Llama inference.

The October 14 fresh AI-reference E2 is complete under its revised protocol. That protocol replaced the earlier human-reference execution instructions; human annotation is not an outstanding requirement of the completed revision. The archived original route did not run its reserved parser/ranking evaluation, which remains a study limitation rather than a task to repeat for this revision. The 20 October student worksheet, 99/100 comparison with initial AI labels and separate exploratory parser-only check are also complete. The 135 hours are planned active student hours. The 20 October retrospective measured-hours reconciliation is closed; its exact entries and totals are not available in this public packet, so no completed-hour total is asserted here.

No original frozen file, private research data, student labels, credential, or personal academic correspondence is included here.
