"""Start the Studio:  python -m studio  [--port 8765] [--provider anthropic|openai|mock] [--no-browser]

A key is never passed on the command line. Paste it into the page, or set
ANTHROPIC_API_KEY / OPENAI_API_KEY in the environment before starting.
"""
import argparse
import os
import threading
import webbrowser

import uvicorn

from studio.providers import ProviderError, build_provider
from studio.server import create_app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m studio", description="Feed Control Studio (local only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--provider", choices=["anthropic", "openai", "mock", "claude-cli"], default=None,
                        help="Provider at start-up (default: anthropic if ANTHROPIC_API_KEY is set, else mock).")
    parser.add_argument("--model", default=None)
    parser.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--enable-claude-cli", action="store_true",
                        help="Allow the local Claude CLI provider (author's computer only).")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if args.enable_claude_cli or args.provider == "claude-cli":
        os.environ["STUDIO_ENABLE_CLAUDE_CLI"] = "1"
    provider = None
    if args.provider:
        try:
            provider = build_provider(args.provider, model=args.model, effort=args.effort)
        except ProviderError as exc:
            parser.error(str(exc))
    app = create_app(port=args.port, provider=provider)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Feed Control Studio is running at {url}  (press Ctrl+C to stop)")
    print(f"Model provider: {app.state.provider.label} / {app.state.provider.model}")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
