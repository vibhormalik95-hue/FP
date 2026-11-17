"""Language controls over the real KuaiRec feed: state, deterministic policy, preview, Apply, Undo.

The trained recommender ranks every processed KuaiRec item for the chosen user. Its
scores are min-max normalized (``controls.normalize_scores``), the same first step as
the original category policy. Applied controls then change the ranking
deterministically, with the strengths of the original topic policy
(``semantic_controls.STRENGTH_WEIGHTS``):

* ``hide``   removes the items that carry the label (the original "mute");
* ``only``   keeps only items that carry one of the labels of that preference;
* ``boost``  adds the strength to the normalized score;
* ``reduce`` subtracts it; the items stay eligible.

A label is an opaque KuaiRec feature ID, a KuaiRec category name, a topic tag, or a
category that the person created and reviewed. A language model only proposes; this
module checks and applies exactly what the person approved, and Undo restores the
previous state. Nothing here depends on any example request.
"""
from __future__ import annotations

import copy
import secrets
import statistics
import threading
import time
from collections import Counter

from feedctrl.controls import normalize_scores
from feedctrl.kuairec_catalog import label_vocabulary
from feedctrl.semantic_controls import STRENGTH_WEIGHTS

STRENGTHS = dict(STRENGTH_WEIGHTS)          # light 0.10, standard 0.25, strong 0.40
ACTIONS = ("boost", "reduce", "hide", "only")
ACTION_WORDS = {"boost": "Show more", "reduce": "Show less", "hide": "Hide", "only": "Show only"}
KIND_WORDS = {"feature": "KuaiRec feature", "category": "KuaiRec category", "tag": "topic tag",
              "custom": "new category"}
FEED_SIZE = 10
PREVIEW_TTL_S = 8 * 3600     # long enough for a person to read the evidence and decide
NEW_ITEM_BASE = 9_000_000    # added items never collide with KuaiRec video IDs
MIN_TAG_ITEMS = 3            # tags offered to the model; rarer tags stay usable by hand


class LabError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def target_text(target):
    return f"{KIND_WORDS[target['kind']]} '{target['value']}'"


def control_text(control):
    strength = f" ({control['strength']})" if control["action"] in ("boost", "reduce") else ""
    return f"{ACTION_WORDS[control['action']]}{strength}: {target_text(control['target'])}"


def make_control(source, action, target, strength="standard", group=None):
    if action not in ACTIONS:
        raise LabError(f"Unknown action {action!r}.")
    if target.get("kind") not in KIND_WORDS or not target.get("value"):
        raise LabError("A control needs an existing label.")
    strength = strength if action in ("boost", "reduce") and strength in STRENGTHS else "standard"
    control = {"id": secrets.token_hex(4), "source": source, "action": action,
               "target": {"kind": target["kind"], "value": str(target["value"])}, "strength": strength}
    control["group"] = group or control["id"]
    control["text"] = control_text(control)
    return control


def item_matches(item, target, custom):
    kind, value = target["kind"], target["value"]
    if kind == "feature":
        return value in item.get("feature_ids", [])
    if kind == "category":
        return value in item.get("kuairec_categories", [])
    if kind == "tag":
        return value in item.get("tags", [])
    if kind == "custom":
        entry = custom.get(value)
        return bool(entry and entry["members"].get(str(item["item_id"]), {}).get("selected"))
    return False


def apply_controls(scores, items, controls, custom):
    """Deterministic policy. ``scores`` maps item id to normalized score. Returns ranked rows."""
    only_groups = {}
    for c in controls:
        if c["action"] == "only":
            only_groups.setdefault(c["group"], []).append(c)
    rows = []
    for item_id, score in scores.items():
        item = items[item_id]
        if any(c["action"] == "hide" and item_matches(item, c["target"], custom) for c in controls):
            continue
        if any(not any(item_matches(item, c["target"], custom) for c in group) for group in only_groups.values()):
            continue
        adjusted, hits = score, []
        for c in controls:
            if c["action"] in ("boost", "reduce") and item_matches(item, c["target"], custom):
                adjusted += STRENGTHS[c["strength"]] * (1 if c["action"] == "boost" else -1)
                hits.append(c["id"])
            elif c["action"] == "only" and item_matches(item, c["target"], custom):
                hits.append(c["id"])
        rows.append((item_id, adjusted, score, hits))
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows


class UserLab:
    def __init__(self):
        self.controls, self.custom, self.added = [], {}, {}
        self.history, self.previews, self.log = [], {}, []
        self.version = 0


class KuaiRecLab:
    """All language-control state of this local server, one record per user. Thread-safe."""

    def __init__(self, catalog, *, scorer, users, gloss=None, feed_size=FEED_SIZE):
        self.catalog = catalog                       # item_id -> record (kuairec_catalog.item_record)
        self.scorer = scorer                         # callable(user_id) -> {item_id: raw score}
        self.users = users                           # user_id -> processed user record
        self.gloss = gloss or {}
        self.feed_size = feed_size
        self._lock = threading.RLock()
        self._state, self._scores = {}, {}
        self.base_vocabulary = label_vocabulary(catalog, gloss)

    # ----- state ------------------------------------------------------
    def user(self, user_id):
        if user_id not in self.users:
            raise LabError("Unknown user.", 404)
        with self._lock:
            return self._state.setdefault(user_id, UserLab())

    def reset(self, user_id):
        with self._lock:
            old = self._state.get(user_id)
            fresh = UserLab()
            fresh.version = (old.version + 1) if old else 0   # a stale preview can never match again
            self._state[user_id] = fresh

    def base_scores(self, user_id):
        with self._lock:
            if user_id not in self._scores:
                raw = self.scorer(user_id)
                ids = sorted(raw)
                self._scores[user_id] = dict(zip(ids, normalize_scores([float(raw[i]) for i in ids])))
            return self._scores[user_id]

    def items_for(self, lab):
        return {**self.catalog, **lab.added}

    def scores_for(self, user_id, lab, added=None):
        base = dict(self.base_scores(user_id))
        cold = self.cold_start_score(user_id)
        for item_id in list(lab.added) + list(added or []):
            base[item_id] = cold
        return base

    def cold_start_score(self, user_id):
        return round(statistics.median(self.base_scores(user_id).values()), 4)

    def view(self, user_id):
        """A private copy of one user's state, taken before any model call."""
        lab = self.user(user_id)
        with self._lock:
            return {"version": lab.version, "items": self.items_for(lab), "custom": copy.deepcopy(lab.custom),
                    "controls": copy.deepcopy(lab.controls), "vocabulary": self.vocabulary(lab),
                    "added": copy.deepcopy(lab.added)}

    # ----- vocabulary ---------------------------------------------------
    def vocabulary(self, lab, *, for_model=False):
        with self._lock:
            return self._vocabulary(lab, for_model=for_model)

    def _vocabulary(self, lab, *, for_model=False):
        terms = [t for t in self.base_vocabulary
                 if not (for_model and (t["kind"] == "feature" or (t["kind"] == "tag" and t["item_count"] < MIN_TAG_ITEMS)))]
        if lab.added:   # added items carry existing labels; keep counts honest
            extra = Counter()
            for item in lab.added.values():
                extra.update(("category", v) for v in item["kuairec_categories"])
                extra.update(("tag", v) for v in item["tags"])
            terms = [{**t, "item_count": t["item_count"] + extra.get((t["kind"], t["value"]), 0)} for t in terms]
        for label, entry in sorted(lab.custom.items()):
            terms.append({"term_id": f"custom:{label}", "kind": "custom", "value": label,
                          "item_count": sum(1 for e in entry["members"].values() if e.get("selected")),
                          "definition": entry["definition"]})
        return terms

    # ----- feed -----------------------------------------------------------
    def card(self, item, rank, score, adjusted, hits, controls):
        item_id = item["item_id"]
        gloss = item.get("gloss_en") or self.gloss.get("items", {}).get(str(item_id), {})
        return {"item_id": item_id, "rank": rank, "title": item["title"], "caption": item["caption"],
                "tags": item["tags"], "kuairec_categories": item["kuairec_categories"],
                "feature_ids": item["feature_ids"], "gloss_en": gloss or None,
                "origin": item.get("origin", "kuairec"), "base_score": round(score, 4),
                "score": round(adjusted, 4),
                "controls": [c["text"] for c in controls if c["id"] in hits]}

    def feed(self, user_id, *, lab=None, controls=None, custom=None, added=None, limit=None):
        lab = lab or self.user(user_id)
        controls = lab.controls if controls is None else controls
        custom = lab.custom if custom is None else custom
        items = {**self.items_for(lab), **(added or {})}
        rows = apply_controls(self.scores_for(user_id, lab, added), items, controls, custom)
        limit = limit or self.feed_size
        top = [self.card(items[i], n, s, a, h, controls) for n, (i, a, s, h) in enumerate(rows[:limit], 1)]
        return {"eligible": len(rows), "catalogue": len(items), "items": top,
                "ranked_ids": [r[0] for r in rows]}

    @staticmethod
    def diff(before, after):
        b = [c["item_id"] for c in before["items"]]
        a = [c["item_id"] for c in after["items"]]
        return {"entered": [i for i in a if i not in b], "left": [i for i in b if i not in a],
                "moved_up": [i for i in a if i in b and a.index(i) < b.index(i)],
                "moved_down": [i for i in a if i in b and a.index(i) > b.index(i)],
                "eligible_before": before["eligible"], "eligible_after": after["eligible"]}

    def affected(self, controls, items, custom):
        out = []
        for c in controls:
            ids = sorted(i for i, it in items.items() if item_matches(it, c["target"], custom))
            out.append({"control": c["text"], "count": len(ids), "item_ids": ids[:200]})
        return out

    def scope(self, user_id, size):
        """The items a model classifies: this user's top ``size`` base-ranked items plus added items."""
        lab = self.user(user_id)
        base = self.base_scores(user_id)
        top = sorted(base, key=lambda i: (-base[i], i))[:size]
        with self._lock:
            return [self.catalog[i] for i in top] + list(lab.added.values())

    # ----- previews ---------------------------------------------------------
    def new_preview(self, user_id, kind, summary, *, controls=(), new_custom=None, new_items=None,
                    custom_updates=None, proposal=None, evidence=None, checks=None, calls=None,
                    notes=None, base_version=None, request=None):
        lab = self.user(user_id)
        with self._lock:
            self._expire(lab)
            if base_version is not None and base_version != lab.version:
                raise LabError("The feed changed while the model was working. Run the preview again.", 409)
            added = {}
            for item in new_items or []:
                if item["item_id"] in self.items_for(lab):
                    raise LabError(f"Item {item['item_id']} already exists.", 409)
                added[item["item_id"]] = item
            custom = copy.deepcopy(lab.custom)
            if new_custom:
                custom[new_custom["label"]] = new_custom
            for label, members in (custom_updates or {}).items():
                if label in custom:
                    custom[label]["members"].update(members)
            all_controls = lab.controls + list(controls)
            before = self.feed(user_id, lab=lab)
            after = self.feed(user_id, lab=lab, controls=all_controls, custom=custom, added=added)
            preview = {"preview_id": secrets.token_urlsafe(12), "kind": kind, "summary": summary,
                       "request": request, "controls": list(controls), "new_custom": new_custom,
                       "new_items": list(added.values()), "custom_updates": custom_updates or {},
                       "proposal": proposal, "evidence": evidence or [], "checks": checks or [],
                       "calls": calls or [], "notes": notes or [],
                       "affected": self.affected(list(controls), {**self.items_for(lab), **added}, custom),
                       "before": {k: before[k] for k in ("eligible", "catalogue", "items")},
                       "after": {k: after[k] for k in ("eligible", "catalogue", "items")},
                       "changes": self.diff(before, after), "base_version": lab.version,
                       "created": time.time(), "expires_in_s": PREVIEW_TTL_S,
                       "applicable": bool(controls or added or custom_updates or new_custom)}
            lab.previews[preview["preview_id"]] = preview
            return preview

    def _expire(self, lab):
        now = time.time()
        for pid in [p for p, v in lab.previews.items() if now - v["created"] > PREVIEW_TTL_S]:
            del lab.previews[pid]

    def apply(self, user_id, preview_id):
        lab = self.user(user_id)
        with self._lock:
            self._expire(lab)
            preview = lab.previews.get(preview_id)
            if not preview:
                raise LabError("This preview has expired or was already used. Run it again.", 404)
            if preview["base_version"] != lab.version:
                raise LabError("The feed changed after this preview. Run the preview again.", 409)
            if not preview["applicable"]:
                raise LabError("This preview has nothing to apply.", 400)
            lab.history.append(copy.deepcopy({"controls": lab.controls, "custom": lab.custom, "added": lab.added}))
            for item in preview["new_items"]:
                lab.added[item["item_id"]] = item
            if preview["new_custom"]:
                lab.custom[preview["new_custom"]["label"]] = copy.deepcopy(preview["new_custom"])
            for label, members in preview["custom_updates"].items():
                if label in lab.custom:
                    lab.custom[label]["members"].update(copy.deepcopy(members))
            lab.controls = lab.controls + copy.deepcopy(preview["controls"])
            lab.version += 1
            lab.previews.clear()
            lab.log.append({"action": "apply", "summary": preview["summary"], "at": time.time()})
            return self.state(user_id)

    def undo(self, user_id):
        lab = self.user(user_id)
        with self._lock:
            if not lab.history:
                raise LabError("Nothing to undo.", 400)
            snap = lab.history.pop()
            lab.controls, lab.custom, lab.added = snap["controls"], snap["custom"], snap["added"]
            lab.version += 1
            lab.previews.clear()
            lab.log.append({"action": "undo", "at": time.time()})
            return self.state(user_id)

    def state(self, user_id):
        lab = self.user(user_id)
        with self._lock:
            feed = self.feed(user_id, lab=lab)
            return {"user_id": user_id, "version": lab.version, "controls": lab.controls,
                    "custom": {k: {"label": v["label"], "definition": v["definition"],
                                   "members": sorted(int(i) for i, e in v["members"].items() if e.get("selected"))}
                               for k, v in lab.custom.items()},
                    "added": [{k: it[k] for k in ("item_id", "title", "caption", "kuairec_categories", "tags")}
                              for it in lab.added.values()],
                    "feed": {k: feed[k] for k in ("eligible", "catalogue", "items")},
                    "can_undo": bool(lab.history), "log": lab.log[-20:],
                    "cold_start_score": self.cold_start_score(user_id)}

    def next_item_id(self, lab, offset=0):
        return NEW_ITEM_BASE + len(lab.added) + offset + 1
