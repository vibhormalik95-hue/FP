"""Reproduce a source-text topic preview without running a scientific evaluation.

Usage: python scripts/reproduce_semantic_topic_preview.py DATA_JSON MODEL_DIR CAPTION_CSV
Reads the three supplied files and prints JSON; no study file is written.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feedctrl.api import DemoState  # noqa: E402
from feedctrl.semantic_controls import manual_topic_command, match_topic  # noqa: E402


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    data_path, model_path, sidecar_path = map(Path, sys.argv[1:])
    demo = DemoState(data_path, model_path, semantic_path=sidecar_path)
    if demo.fixture or demo.model is None or demo.topic_index is None:
        raise SystemExit("Saved processed data, trained model and official sidecar are required")
    user_id = 14
    state = demo.user_state(demo.create_session(), user_id)
    topic = "青岛"  # Qingdao: an ad-hoc caption topic, not an official category ID.
    command = manual_topic_command("boost", topic)
    matched, evidence = match_topic(demo.topic_index, command)
    original = demo.rank(user_id, state, "C", 10)
    result = {"scope": "Opt-in in-process semantic source-text preview, not E1/E2 or live LLM inference",
              "user_id": user_id, "topic": topic, "source": demo.topic_index["source"],
              "sidecar_sha256": demo.topic_index["sha256"],
              "candidate_items": demo.topic_index["candidate_items"],
              "items_with_caption": demo.topic_index["items_with_caption"],
              "ignored_non_item_rows": demo.topic_index["ignored_non_item_rows"],
              "matched_candidate_count": len(matched), "sample_evidence": evidence,
              "neutral_top10": [card["item_id"] for card in original["items"]],
              "neutral_top10_matches": sum(card["item_id"] in matched for card in original["items"]),
              "operations": {}}
    for operation in ("boost", "reduce", "exclude"):
        command = manual_topic_command(operation, topic)
        preview = demo.topic_preview(user_id, state, command, "C", 10)
        result["operations"][operation] = {
            "top10": [card["item_id"] for card in preview["items"]],
            "top10_text_matches": preview["top_k_match_count"],
            "available_items": preview["available_items"],
            "fill_rate": preview["fill_rate"],
            "source": command["source"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
