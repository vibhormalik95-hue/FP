# COMP 9500 professor demo, 27 October 2026

Start with the [timed script](PROFESSOR-DEMO-SCRIPT.md) and [135-hour evidence matrix](EVIDENCE-AND-135-HOURS.md). The current [review paper and slides](../2026-10-19/README-2026-10-19.md), [fresh AI-reference E2 results](../../docs/ai-reference-e2-results-2026-10-14.md), and [compact evidence index](../../docs/ai-reference-e2-evidence/README.md) are already in this repository.

## Launch on the research laptop

The public checkout omits the processed research dataset, saved checkpoint and built frontend. Use the existing private full research archive for those inputs; do not download or replace frozen Experiment 1 material. In PowerShell, from the prepared full project folder containing `data/processed.json`, `results/models/seed_42`, and `web/dist`:

```powershell
python -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`; stop the server with **Ctrl+C** in its PowerShell window. If port 8000 is occupied, use `--port 8765` and open that port. Do not stop another process to free a port. Confirm the visible status says **processed dataset**, **trained model** and **rule** before using the script. A missing dataset or checkpoint can activate fixture or diagnostic mode; label it honestly. The app shows metadata cards, not playable videos.

A 27 October isolated working copy passed saved-data/saved-model rule checks and live browser checks for A-E, reset and user isolation. A single fresh local `llama3.1:8b` parser request also succeeded, displaying its exact recorded model digest in the UI. That check was one demonstration request, not the Experiment 2 benchmark. Use the current paper and saved result receipts if the app is unavailable.

## Study boundary

The interface is the original A-E control demonstrator. It supports one category per instruction and an editable profile. It does not implement the fresh E2 compound, floor or conditional request interface. Show that study through its saved protocol and result evidence. Do not call rule-parser clicks live Llama inference.

The October 14 fresh AI-reference E2 is complete under its own protocol. The original human-reference route is separate and still requires an adjudicated human reference set and planned parser/ranking analysis. The 20 October student-label comparison is descriptive and exploratory. The 135 hours remain planned active student hours. Vibhor reported measured hours in the 20 October retrospective reconciliation, but the accessible record does not include exact measured totals or the underlying entries.

No original frozen file, private research data, student labels, credential, or personal academic correspondence is included here.
