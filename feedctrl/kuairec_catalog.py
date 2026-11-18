"""The KuaiRec item text joined to the processed items, for the language controls.

The processed study data (``data/processed.json``) holds each item's opaque KuaiRec
feature IDs (``category_N``). The official KuaiRec caption table holds the text of
each video: the caption, the manual cover text, the topic tags and the three levels
of KuaiRec category names. This module joins the two by ``video_id`` and builds one
catalogue record per processed item.

Nothing here is invented. Empty fields and the dataset's ``UNKNOWN`` marker are
dropped. An English gloss is optional; it is read from a separate gloss file and is
always labelled machine translation, never treated as source text.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

CAPTION_COLUMNS = ("video_id", "manual_cover_text", "caption", "topic_tag",
                   "first_level_category_name", "second_level_category_name",
                   "third_level_category_name")
CATEGORY_LEVELS = ("first_level_category_name", "second_level_category_name", "third_level_category_name")
MISSING = {"", "UNKNOWN", "[]"}
GLOSS_NOTE = "English gloss: machine translation, not source text"
ENGLISH_LABEL = "machine translation of KuaiRec (CC BY-SA 4.0)"
ENGLISH_VERSION = "v1"


def _tags(raw) -> list[str]:
    if isinstance(raw, list):
        raw = ",".join(raw)
    raw = (raw or "").strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    seen, out = set(), []
    for part in raw.split(","):
        tag = part.strip().strip("'\"").strip()
        if tag and tag not in MISSING and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def read_caption_table(path: str | Path) -> tuple[dict[int, dict], dict]:
    """Read the official caption CSV. Returns ``(rows_by_id, provenance)``.

    The official file puts an unquoted space before quoted topic-tag lists, so the
    reader uses ``skipinitialspace``. Rows without a numeric ``video_id`` are stray
    continuation lines of the official file; they are counted and skipped.
    """
    path = Path(path)
    raw = path.read_bytes()
    rows: dict[int, dict] = {}
    skipped = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, skipinitialspace=True)
        names = {name.strip() for name in reader.fieldnames or []}
        missing = set(CAPTION_COLUMNS) - names
        if missing:
            raise ValueError(f"Caption table is missing columns: {sorted(missing)}")
        for record in reader:
            if None in record:
                raise ValueError("Caption table has a malformed row")
            record = {key.strip(): (value or "").strip() for key, value in record.items()}
            if not record["video_id"].isdigit():
                skipped += 1
                continue
            item_id = int(record["video_id"])
            if item_id in rows:
                raise ValueError(f"Caption table repeats video_id {item_id}")
            rows[item_id] = record
    return rows, {"path_name": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
                  "rows": len(rows), "skipped_non_item_rows": skipped}


def read_english_layer(path: str | Path) -> tuple[dict[int, dict], dict]:
    """Read the English text layer (scripts/build_kuairec_english.py). Same row shape as the caption table.

    This is what the app loads: English cover text, caption, topic tags and category names for every
    processed item, labelled machine translation of KuaiRec. The Chinese source table is not read.
    """
    path = Path(path)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if data.get("label") != ENGLISH_LABEL:
        raise ValueError("The English text layer must carry the label " + repr(ENGLISH_LABEL))
    rows = {int(key): {"video_id": key, **value} for key, value in data["items"].items()}
    return rows, {"path_name": path.name, "sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows),
                  "label": ENGLISH_LABEL, "version": data.get("version"), "source": data.get("source", {})}


def write_english_csv(rows: dict[int, dict], path: str | Path) -> Path:
    """Write the English layer in the caption-table CSV format, for the study view's topic index."""
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CAPTION_COLUMNS)
        for item_id in sorted(rows):
            row = rows[item_id]
            tags = row.get("topic_tag") or []
            writer.writerow([item_id, row.get("manual_cover_text", ""), row.get("caption", ""),
                             "[" + ",".join(tags) + "]" if tags else "[]",
                             *(row.get(level, "") for level in CATEGORY_LEVELS)])
    return path


def item_record(item_id: int, feature_ids: list[str], row: dict | None) -> dict:
    row = row or {}
    clean = lambda key: "" if row.get(key, "") in MISSING else row.get(key, "")
    caption, cover = clean("caption"), clean("manual_cover_text")
    names = []
    for level in CATEGORY_LEVELS:
        value = clean(level)
        if value and value not in names:
            names.append(value)
    title = cover or caption[:40]
    return {"item_id": int(item_id), "feature_ids": list(feature_ids), "title": title,
            "cover_text": cover, "caption": caption, "tags": _tags(row.get("topic_tag", "")),
            "kuairec_categories": names, "has_text": bool(caption or cover)}


def build_catalog(processed: dict, caption_rows: dict[int, dict], gloss: dict | None = None) -> dict[int, dict]:
    """One record per processed item. Every processed item must have a caption row."""
    catalog = {}
    for item in processed["items"]:
        item_id = int(item["item_id"])
        if item_id not in caption_rows:
            raise ValueError(f"Processed item {item_id} has no row in the caption table")
        record = item_record(item_id, item["categories"], caption_rows[item_id])
        if gloss and str(item_id) in gloss.get("items", {}):
            record["gloss_en"] = gloss["items"][str(item_id)]
        catalog[item_id] = record
    return catalog


def label_vocabulary(catalog: dict[int, dict], gloss: dict | None = None) -> list[dict]:
    """Every existing label with its item count: feature IDs, KuaiRec category names and topic tags.

    ``term_id`` is ``feature:<id>``, ``category:<name>`` or ``tag:<name>``. Names are copied
    unchanged from the rows the catalogue was built from: the English machine translation when
    those rows come from the English text layer (``read_english_layer``, what the app loads), the
    original Chinese only when they come from the official caption table. This function does not
    translate or check the language. An English gloss, when present, is labelled machine translation.
    """
    counts: dict[tuple[str, str], int] = {}
    for record in catalog.values():
        for value in record["feature_ids"]:
            counts[("feature", value)] = counts.get(("feature", value), 0) + 1
        for value in record["kuairec_categories"]:
            counts[("category", value)] = counts.get(("category", value), 0) + 1
        for value in record["tags"]:
            counts[("tag", value)] = counts.get(("tag", value), 0) + 1
    labels = (gloss or {}).get("labels", {})
    terms = []
    for (kind, value), count in sorted(counts.items()):
        term = {"term_id": f"{kind}:{value}", "kind": kind, "value": value, "item_count": count}
        if kind != "feature" and value in labels:
            term["gloss_en"] = labels[value]
        terms.append(term)
    return terms


def term_members(catalog: dict[int, dict], term_id: str) -> set[int]:
    kind, _, value = term_id.partition(":")
    field = {"feature": "feature_ids", "category": "kuairec_categories", "tag": "tags"}.get(kind)
    if field is None or not value:
        raise ValueError(f"Unknown label {term_id!r}")
    return {item_id for item_id, record in catalog.items() if value in record[field]}


def load_gloss(path: str | Path | None) -> dict | None:
    if not path or not Path(path).is_file():
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("note") != GLOSS_NOTE:
        raise ValueError("Gloss file must carry the machine-translation note")
    return data
