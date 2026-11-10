"""Explicit hosted-only application wiring. Importing this module sends nothing.

No credentials, models or budgets are discovered automatically. The caller must
establish data, account and spending authority before constructing a transport.
This wiring is not evidence of entitlement, semantic accuracy or a completed run.
"""
from copy import deepcopy

from feedctrl.model_adapters import make_openai_responses_infer


def category_payload(payload):
    """Map the category producer's trusted instruction field to the transport.

    Preserve the complete evidence and objective. Reject an ambiguous instruction
    envelope instead of merging, rewriting or silently dropping supplied fields.
    """
    if not isinstance(payload, dict) or "system" in payload:
        raise ValueError("Category payload must have one instructions field")
    owned = deepcopy(payload)
    prompt = owned.pop("instructions", None)
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Category payload requires nonempty instructions")
    return {"system": prompt, **owned}


def shared_factories(infer, provenance):
    """Bind both workflows to one existing OpenAI callable and its allowance.

    These factories never create transports or replenish a consumed budget. The
    category revision is the transport configuration digest, not a weight hash.
    """
    if not callable(infer) or not isinstance(provenance, dict):
        raise ValueError("A configured transport and truthful provenance are required")
    identity = deepcopy(provenance)
    if identity.get("backend") != "openai-responses":
        raise ValueError("This binding supports only the explicit OpenAI Responses transport")
    for field in ("model", "digest"):
        if not isinstance(identity.get(field), str) or not identity[field].strip():
            raise ValueError("Transport model and configuration digest are required")
    category_identity = {
        "backend": identity["backend"],
        "model_id": identity["model"],
        "model_revision": identity["digest"],
    }

    def category_infer(payload, schema):
        return infer(category_payload(payload), deepcopy(schema))

    def semantic_factory():
        return infer, deepcopy(identity)

    def category_factory():
        return category_infer, deepcopy(category_identity)

    return semantic_factory, category_factory


def create_openai_hosted_app(*, api_key, model, reasoning_effort, run_budget,
                             authorized=False, spend_guard=None, data_path=None,
                             semantic_path=None, fixture=False,
                             max_output_tokens=4096, timeout=90,
                             max_request_bytes=20000):
    """Build a hosted-only app with one transport shared across both workflows.

    No local model is loaded by this factory. If the non-fixture configuration
    has a local recommender checkpoint, construction fails instead of loading it
    or silently substituting a different scorer. The historical experiment and
    its legacy launcher remain unchanged. Resolve that configuration separately
    before a live run, along with hosted account, data and spending authority.
    """
    if spend_guard is None:
        raise ValueError("A verified durable spending guard is required; a call cap is not a dollar cap")
    infer, provenance, receipts = make_openai_responses_infer(
        api_key=api_key, model=model, reasoning_effort=reasoning_effort,
        run_budget=run_budget, authorized=authorized, spend_guard=spend_guard,
        max_output_tokens=max_output_tokens, timeout=timeout,
        max_request_bytes=max_request_bytes,
    )
    semantic_factory, category_factory = shared_factories(infer, provenance)
    from feedctrl.api import create_app
    app = create_app(data_path=data_path, semantic_path=semantic_path, fixture=fixture,
                     semantic_infer_factory=semantic_factory,
                     category_infer_factory=category_factory,
                     allow_local_models=False, allow_local_recommender=False)
    app.state.hosted_model_provenance = deepcopy(provenance)
    app.state.hosted_model_receipts = receipts
    return app
