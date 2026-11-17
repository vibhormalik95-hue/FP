"""Start the Feed Control Lab on real KuaiRec: one app, one command.

    python scripts/run_app.py                     # mock provider, no key needed
    python scripts/run_app.py --provider openai --model gpt-5-mini
    python scripts/run_app.py --provider ollama --model qwen2.5-coder:7b-instruct

The page shows the original study view (conditions A to E) and every language control
on the processed KuaiRec data (865 users, 2,593 items), ranked by the trained SASRec
checkpoint. The server binds to 127.0.0.1 only. There is no token or password.
API keys come from the environment (OPENAI_API_KEY, ANTHROPIC_API_KEY) or from the
masked field of the page; a key is kept in memory only and never written anywhere.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NEEDED = {"processed data": "data/processed.json", "caption table": "data/raw/kuairec_caption_category.csv",
          "checkpoint": "results/models/seed_42/model.pt"}


def build(args):
    missing = [f"{name}: {path}" for name, path in NEEDED.items() if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit("Missing private research files (they are not in the repository):\n  " + "\n  ".join(missing)
                         + "\nCopy them from the research archive, or see docs/install-and-run.md.")
    os.environ["FEEDCTRL_CAPTION_SIDECAR"] = str(ROOT / NEEDED["caption table"])
    from feedctrl.api import create_app
    from feedctrl.lab_routes import LoopbackGuard, mount_lab
    app = create_app(data_path=ROOT / NEEDED["processed data"], model_path=ROOT / "results/models/seed_42",
                     semantic_path=ROOT / NEEDED["caption table"], allow_local_models=True,
                     allow_local_recommender=True)
    lab = mount_lab(app, gloss_path=ROOT / args.gloss, budget_usd=args.budget_usd)
    if args.provider != "mock":
        app.state.provider_slot.configure(args.provider, model=args.model, base_url=args.base_url, effort="low")
    return app, lab


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--provider", default="mock", choices=("mock", "openai", "anthropic", "ollama", "claude-cli"))
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--gloss", default="data/kuairec_gloss_en.json")
    ap.add_argument("--budget-usd", type=float, default=None, help="stop model calls once this much is spent")
    args = ap.parse_args(argv)
    app, lab = build(args)
    from feedctrl.lab_routes import LoopbackGuard
    import uvicorn
    status = {"serving": f"http://127.0.0.1:{args.port}", "users": len(app.state.demo.users),
              "items": len(lab.catalog), "ranker": "trained SASRec seed 42" if app.state.demo.model else "none",
              "provider": app.state.provider_slot.describe()["provider"],
              "gloss": "loaded (machine translation)" if lab.gloss else "missing: run scripts/build_kuairec_gloss.py"}
    print(json.dumps(status, indent=2), flush=True)
    print(f"Open http://127.0.0.1:{args.port}  (Ctrl+C stops the server)", flush=True)
    uvicorn.run(LoopbackGuard(app, args.port), host="127.0.0.1", port=args.port, log_level="warning",
                proxy_headers=False, server_header=False)


if __name__ == "__main__":
    main()
