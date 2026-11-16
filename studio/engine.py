"""Catalogue state, deterministic feed policy, previews, Apply and Undo.

The language model only proposes. Everything here is deterministic: the feed
is recomputed from the catalogue and the list of applied controls, so the
same controls always give the same feed.
"""
from __future__ import annotations

import copy
import json
import secrets
import statistics
import threading
import time
from pathlib import Path

FEED_SIZE = 12
STRENGTHS = {"light": 0.10, "standard": 0.25, "strong": 0.40}
ACTIONS = ("boost", "reduce", "hide", "only")
ACTION_WORDS = {"boost": "Show more", "reduce": "Show less", "hide": "Hide", "only": "Show only"}
PREVIEW_TTL_S = 8 * 3600  # long enough for a person to read the evidence and decide
CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"


class StudioError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def load_catalog(path=CATALOG_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {item["id"]: {**item, "origin": "catalogue"} for item in data["items"]}


def target_text(target):
    kind = {"category": "category", "tag": "tag", "custom": "new category"}[target["kind"]]
    return f"{kind} '{target['value']}'"


def control_text(control):
    strength = f" ({control['strength']})" if control["action"] in ("boost", "reduce") else ""
    return f"{ACTION_WORDS[control['action']]}{strength}: {target_text(control['target'])}"


class Studio:
    """All state for one local session. Thread-safe."""

    def __init__(self, catalog_path=CATALOG_PATH):
        self._lock = threading.RLock()
        self.catalog_path = catalog_path
        self.reset()

    # ----- state -------------------------------------------------------
    def reset(self):
        with self._lock:
            self.items = load_catalog(self.catalog_path)
            self.custom = {}      # label -> {"label","definition","members": {item_id: evidence}}
            self.controls = []    # applied controls, in order
            self.history = []     # snapshots for Undo
            self.previews = {}
            self.version = 0
            self.log = []         # applied/undone actions, newest last

    def _snapshot(self):
        return copy.deepcopy({"items": self.items, "custom": self.custom, "controls": self.controls})

    def _restore(self, snap):
        self.items, self.custom, self.controls = snap["items"], snap["custom"], snap["controls"]

    # ----- vocabulary ---------------------------------------------------
    def categories(self):
        counts = {}
        for item in self.items.values():
            if item.get("category"):
                counts[item["category"]] = counts.get(item["category"], 0) + 1
        return dict(sorted(counts.items()))

    def tags(self):
        counts = {}
        for item in self.items.values():
            for tag in item.get("tags", []):
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items()))

    def vocabulary(self):
        terms = []
        for value, n in self.categories().items():
            terms.append({"term_id": f"category:{value}", "kind": "category", "value": value, "item_count": n})
        for value, n in self.tags().items():
            terms.append({"term_id": f"tag:{value}", "kind": "tag", "value": value, "item_count": n})
        for label, cat in sorted(self.custom.items()):
            terms.append({"term_id": f"custom:{label}", "kind": "custom", "value": label,
                          "item_count": len(self.custom_members(label)), "definition": cat["definition"]})
        return terms

    def custom_members(self, label, custom=None):
        cat = (custom if custom is not None else self.custom).get(label)
        if not cat:
            return []
        return sorted(i for i, ev in cat["members"].items() if ev.get("selected"))

    # ----- feed policy ----------------------------------------------------
    def matches(self, item, target, custom=None):
        kind, value = target["kind"], target["value"]
        if kind == "category":
            return item.get("category") == value
        if kind == "tag":
            return value in item.get("tags", [])
        if kind == "custom":
            cat = (custom if custom is not None else self.custom).get(value)
            return bool(cat and cat["members"].get(item["id"], {}).get("selected"))
        return False

    def feed(self, items=None, controls=None, custom=None):
        items = self.items if items is None else items
        controls = self.controls if controls is None else controls
        custom = self.custom if custom is None else custom
        only = [c for c in controls if c["action"] == "only"]
        rows = []
        for item in items.values():
            if any(c["action"] == "hide" and self.matches(item, c["target"], custom) for c in controls):
                continue
            if only and not all(self.matches(item, c["target"], custom) for c in only):
                continue
            score = item["score"]
            for c in controls:
                if c["action"] in ("boost", "reduce") and self.matches(item, c["target"], custom):
                    delta = STRENGTHS[c["strength"]]
                    score += delta if c["action"] == "boost" else -delta
            rows.append({"id": item["id"], "title": item["title"], "category": item.get("category") or "none",
                         "score": round(score, 3), "origin": item.get("origin", "catalogue")})
        rows.sort(key=lambda r: (-r["score"], r["id"]))
        return {"eligible": len(rows), "catalogue": len(items), "top": rows[:FEED_SIZE]}

    @staticmethod
    def diff(before, after):
        b_ids = [r["id"] for r in before["top"]]
        a_ids = [r["id"] for r in after["top"]]
        return {"entered": [i for i in a_ids if i not in b_ids],
                "left": [i for i in b_ids if i not in a_ids],
                "moved_up": [i for i in a_ids if i in b_ids and a_ids.index(i) < b_ids.index(i)],
                "moved_down": [i for i in a_ids if i in b_ids and a_ids.index(i) > b_ids.index(i)],
                "eligible_before": before["eligible"], "eligible_after": after["eligible"]}

    def affected(self, controls, items=None, custom=None):
        items = self.items if items is None else items
        out = []
        for c in controls:
            ids = sorted(i for i, it in items.items() if self.matches(it, c["target"], custom))
            out.append({"control": control_text(c), "item_ids": ids, "count": len(ids)})
        return out

    # ----- previews -------------------------------------------------------
    def _new_preview(self, kind, summary, *, controls=(), new_custom=None, new_items=None,
                     proposal=None, evidence=None, checks=None, calls=None, notes=None):
        with self._lock:
            self._expire()
            items = dict(self.items)
            for item in new_items or []:
                items[item["id"]] = item
            custom = dict(self.custom)
            if new_custom:
                custom[new_custom["label"]] = new_custom
            all_controls = self.controls + list(controls)
            before = self.feed()
            after = self.feed(items, all_controls, custom)
            preview = {
                "id": secrets.token_urlsafe(9), "kind": kind, "summary": summary,
                "created": time.time(), "expires_in_s": PREVIEW_TTL_S, "base_version": self.version,
                "controls": [dict(c, text=control_text(c)) for c in controls],
                "affected": self.affected(controls, items, custom),
                "new_custom": new_custom, "new_items": new_items or [],
                "proposal": proposal, "evidence": evidence or [], "checks": checks or [],
                "calls": calls or [], "notes": notes or [],
                "feed_before": before, "feed_after": after, "changes": self.diff(before, after),
                "applicable": bool(controls or new_items),
            }
            self.previews[preview["id"]] = preview
            return preview

    def _expire(self):
        now = time.time()
        for pid in [p for p, v in self.previews.items() if now - v["created"] > PREVIEW_TTL_S]:
            del self.previews[pid]

    def apply(self, preview_id):
        with self._lock:
            self._expire()
            preview = self.previews.get(preview_id)
            if not preview:
                raise StudioError("This preview is no longer available (older than 8 hours or already used). Run the preview again.", 404)
            if preview["base_version"] != self.version:
                raise StudioError("The feed changed after this preview was made (another change was applied or undone). Run the preview again so you review the current effect.", 409)
            if not preview["applicable"]:
                raise StudioError("There is nothing to apply in this preview.", 400)
            self.history.append(self._snapshot())
            for item in preview["new_items"]:
                self.items[item["id"]] = item
            if preview["new_custom"]:
                self.custom[preview["new_custom"]["label"]] = preview["new_custom"]
            for label, members in (preview.get("custom_updates") or {}).items():
                if label in self.custom:
                    self.custom[label]["members"].update(members)
            for c in preview["controls"]:
                self.controls.append({k: c[k] for k in ("id", "source", "action", "strength", "target")})
            self.version += 1
            del self.previews[preview_id]
            self.log.append({"event": "applied", "kind": preview["kind"], "summary": preview["summary"], "at": time.time()})
            return self.state()

    def undo(self):
        with self._lock:
            if not self.history:
                raise StudioError("There is nothing to undo.", 400)
            self._restore(self.history.pop())
            self.version += 1
            undone = next((e for e in reversed(self.log) if e["event"] == "applied"), None)
            self.log.append({"event": "undone", "summary": undone["summary"] if undone else "", "at": time.time()})
            return self.state()

    def remove_control(self, control_id):
        with self._lock:
            if not any(c["id"] == control_id for c in self.controls):
                raise StudioError("No such control.", 404)
            self.history.append(self._snapshot())
            self.controls = [c for c in self.controls if c["id"] != control_id]
            self.version += 1
            self.log.append({"event": "applied", "kind": "remove", "summary": f"Removed control {control_id}", "at": time.time()})
            return self.state()

    def state(self):
        with self._lock:
            return {"version": self.version, "feed": self.feed(),
                    "controls": [dict(c, text=control_text(c)) for c in self.controls],
                    "categories": self.categories(), "tags": self.tags(),
                    "custom": [{"label": k, "definition": v["definition"], "members": self.custom_members(k)}
                               for k, v in sorted(self.custom.items())],
                    "items": [self.public_item(i) for i in self.items.values()],
                    "can_undo": bool(self.history), "log": self.log[-12:]}

    @staticmethod
    def public_item(item):
        return {k: item.get(k) for k in ("id", "title", "description", "category", "tags", "score", "origin")}

    def new_item_id(self, offset=0):
        n = 1 + offset + max((int(i[1:]) for i in self.items if i[1:].isdigit()), default=100)
        return f"v{n}"

    def cold_start_score(self):
        return round(statistics.median(i["score"] for i in self.items.values()), 3)


def make_control(source, action, target, strength="standard"):
    if action not in ACTIONS:
        raise StudioError(f"Unknown action {action!r}.")
    if strength not in STRENGTHS:
        raise StudioError(f"Unknown strength {strength!r}.")
    return {"id": secrets.token_hex(4), "source": source, "action": action,
            "strength": strength, "target": target}
