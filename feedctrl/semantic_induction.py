"""Evidence validation for prospective semantic categories over existing items.

This does not infer intent or call a model. It validates a separately produced
membership hypothesis without modifying the source catalogue or prior studies.
Exact source quotes are necessary provenance, not proof of semantic entailment.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

from feedctrl.controls import normalize_scores
from feedctrl.label_validation import is_printable_label
from feedctrl.semantic_controls import STRENGTH_WEIGHTS


class MembershipValidationError(ValueError):
    pass


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def catalogue_snapshot(items):
    """Return an immutable-by-convention source view; never add synthetic IDs."""
    result = {}
    for item in items:
        item_id = item.get("item_id")
        text = item.get("source_text")
        categories = item.get("categories", [])
        if type(item_id) is not int or item_id < 0 or item_id in result:
            raise MembershipValidationError("Source items need unique nonnegative integer IDs")
        if not isinstance(text, str) or len(text) > 20000:
            raise MembershipValidationError("Each source item needs bounded supplied text")
        if (not isinstance(categories, list)
                or any(not isinstance(c, str) or not c for c in categories)):
            raise MembershipValidationError("Source categories must be a list of names")
        result[item_id] = {"item_id": item_id, "source_text": text,
                           "categories": sorted(set(categories))}
    if not result:
        raise MembershipValidationError("A source catalogue cannot be empty")
    return result


def manual_category_membership(catalogue, category):
    """Existing-category baseline with no language-model inference."""
    if not isinstance(category, str) or not category:
        raise MembershipValidationError("Name one existing category")
    if not any(category in item["categories"] for item in catalogue.values()):
        raise MembershipValidationError("The source catalogue has no such category")
    return sorted(i for i, item in catalogue.items() if category in item["categories"])


def validate_induced_category(proposal, catalogue, provenance):
    """Require a disposition for every supplied item and literal quote custody.

    The returned members are an inference hypothesis. Membership precision must
    be tested against independent locked references, not this validator itself.
    """
    # Own the authoritative input records and every nested provenance field.
    # API callers must take these snapshots while holding their session lock.
    proposal, catalogue, provenance = deepcopy((proposal, catalogue, provenance))
    if not isinstance(proposal, dict) or set(proposal) != {"label", "definition", "memberships"}:
        raise MembershipValidationError("Expected label, definition and memberships")
    for key, bound in (("label", 80), ("definition", 1000)):
        value = proposal[key]
        if (not isinstance(value, str) or not 1 <= len(value.strip()) <= bound
                or any(ord(c) < 32 for c in value)):
            raise MembershipValidationError(f"Invalid {key}")
    if not is_printable_label(proposal["label"]):
        raise MembershipValidationError("Invalid label")
    if (not isinstance(provenance, dict)
            or any(not isinstance(provenance.get(k), str) or not provenance[k]
                   for k in ("model_id", "model_revision", "prompt_sha256"))):
        raise MembershipValidationError("Exact model, revision and prompt provenance is required")
    rows = proposal["memberships"]
    if not isinstance(rows, list) or len(rows) != len(catalogue):
        raise MembershipValidationError("Every supplied source item needs one disposition")
    seen, validated = set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"item_id", "verdict", "evidence_quote", "reason"}:
            raise MembershipValidationError("Invalid membership schema")
        item_id = row["item_id"]
        if type(item_id) is not int or item_id not in catalogue or item_id in seen:
            raise MembershipValidationError("Unknown or repeated source item ID")
        seen.add(item_id)
        if row["verdict"] not in {"match", "not_match", "unknown"}:
            raise MembershipValidationError("Invalid membership verdict")
        quote, reason = row["evidence_quote"], row["reason"]
        if (not isinstance(quote, str) or len(quote) > 2000 or not isinstance(reason, str)
                or not 1 <= len(reason.strip()) <= 1000):
            raise MembershipValidationError("Invalid evidence or reasoning field")
        if row["verdict"] == "match" and not quote.strip():
            raise MembershipValidationError("A positive membership needs supplied-text evidence")
        if quote and quote not in catalogue[item_id]["source_text"]:
            raise MembershipValidationError("Evidence quote is absent from that source item")
        validated.append(dict(row))
    source_rows = [catalogue[i] for i in sorted(catalogue)]
    result = {"label": proposal["label"].strip(), "definition": proposal["definition"].strip(),
        "catalogue_sha256": canonical_hash(source_rows), "provenance": provenance,
        "memberships": sorted(validated, key=lambda row: row["item_id"]),
        "member_ids": sorted(row["item_id"] for row in validated if row["verdict"] == "match"),
        "unknown_ids": sorted(row["item_id"] for row in validated if row["verdict"] == "unknown"),
        "coverage_items": len(catalogue), "semantic_entailment_verified": False}
    result["category_revision"] = canonical_hash(result)
    return result


def rerank_membership(item_ids, scores, member_ids, operation, strength="standard", limit=10):
    """Apply the same bounded score adjustments to an explicit existing-ID set."""
    if (len(item_ids) != len(scores) or not item_ids or len(set(item_ids)) != len(item_ids)
            or any(type(i) is not int for i in item_ids)
            or any(not isinstance(x, (float, int)) or not math.isfinite(x) for x in scores)):
        raise MembershipValidationError("Use one finite score for each unique existing item")
    if (any(type(i) is not int for i in member_ids)
            or not set(member_ids) <= set(item_ids)):
        raise MembershipValidationError("Membership cannot introduce new catalogue items")
    if operation not in {"boost", "reduce", "exclude"}:
        raise MembershipValidationError("Unsupported membership operation")
    if operation == "exclude" and strength != "none":
        raise MembershipValidationError("Hard exclusion has no graded strength")
    if operation != "exclude" and strength not in STRENGTH_WEIGHTS:
        raise MembershipValidationError("Unsupported graded strength")
    if type(limit) is not int or limit < 1:
        raise MembershipValidationError("Positive list limit required")
    members = set(member_ids)
    weight = 0 if operation == "exclude" else STRENGTH_WEIGHTS[strength]
    if operation == "reduce":
        weight = -weight
    normalized = normalize_scores(scores)
    candidates = [(i, float(s) + (weight if i in members else 0), order)
                  for order, (i, s) in enumerate(zip(item_ids, normalized))
                  if not (operation == "exclude" and i in members)]
    candidates.sort(key=lambda row: (-row[1], row[0]))
    return {"items": [{"item_id": i, "score": s} for i, s, _ in candidates[:limit]],
            "available_items": len(candidates), "fill_rate": min(limit, len(candidates)) / limit}
