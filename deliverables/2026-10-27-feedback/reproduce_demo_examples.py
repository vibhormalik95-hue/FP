"""Reproduce one saved-data/saved-model UI example, not an evaluation run.

Usage: python reproduce_demo_examples.py DATA_JSON MODEL_DIR
The script reads existing inputs and writes only stdout. It never modifies study files.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from feedctrl.api import DemoState  # noqa: E402
from feedctrl.controls import parse_control, parse_profile  # noqa: E402


def ids(feed):
    return [card["item_id"] for card in feed["items"]]


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    data_path, model_path = map(Path, sys.argv[1:])
    if not data_path.is_file() or not model_path.is_dir():
        raise SystemExit("Prepared data/model path missing")
    demo = DemoState(data_path, model_path)
    if demo.fixture or demo.model is None:
        raise SystemExit("Refusing fixture or diagnostic scorer")
    user_id = 14
    state = demo.user_state(demo.create_session(), user_id)
    baseline = demo.rank(user_id, state, "A", 10)

    # A and B use one item-specific like. C, D, E use an equal category intent.
    state["feedback"][1116] = 1
    state["command"] = parse_control("Show me more category_1", demo.categories)
    profile_result = parse_profile("Show me more category_1.", demo.categories)
    if profile_result["operation"] != "set":
        raise SystemExit("Profile did not parse")
    state["profile"] = profile_result["profile"]
    feeds = {condition: demo.rank(user_id, state, condition, 10)
             for condition in "ABCDE"}

    # Additional mute and conflict checks start from the same frozen scores.
    state["command"] = parse_control("Mute category_28", demo.categories)
    state["profile"] = {}
    mute = demo.rank(user_id, state, "C", 10)
    state["command"] = parse_control("Mute category_1", demo.categories)
    state["profile"] = {"category_1": 0.25}
    conflict = demo.rank(user_id, state, "E", 10)

    result = {
        "scope": "In-process demonstration only; saved processed data and seed-42 model, rule parser; not a scientific evaluation, browser check or LLM inference",
        "user_id": user_id,
        "users": len(demo.users),
        "items": len(demo.items),
        "baseline_history_only_top10": ids(baseline),
        "baseline_target_count_category_1": baseline["category_exposure"].get("category_1", 0),
        "baseline_target_count_category_28": baseline["category_exposure"].get("category_28", 0),
        "condition_inputs": {
            "A_B": "like item 1116",
            "C": "Show me more category_1 via rule parser",
            "D": "Show me more category_1. via rule profile parser",
            "E": "same C command and D profile; explicit command wins, no doubling",
        },
        "conditions": {
            c: {"top10": ids(f), "fill_rate": f["fill_rate"],
                "target_count_category_1": f["category_exposure"].get("category_1", 0),
                "explanations_enabled": f["explanations_enabled"],
                "feedback_count": f["feedback_count"]}
            for c, f in feeds.items()
        },
        "mute_category_28_C": {
            "top10": ids(mute),
            "target_count": mute["category_exposure"].get("category_28", 0),
            "fill_rate": mute["fill_rate"],
        },
        "conflict_E_explicit_mute_profile_boost_category_1": {
            "top10": ids(conflict),
            "target_count": conflict["category_exposure"].get("category_1", 0),
            "fill_rate": conflict["fill_rate"],
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
