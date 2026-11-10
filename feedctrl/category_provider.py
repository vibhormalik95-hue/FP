"""Explicit app-owned category callable; no transport or automatic activation."""
from copy import deepcopy
import threading
import time

from feedctrl.controls import ParserOperationalError
from feedctrl.indirect_grounding import _digest, _response_snapshot
from feedctrl import induction_integration as induction


class CategoryProvider:
    """Cache one configured adapter and preserve a single callable invocation per stage.

    Provenance is the adapter's declared identity, not model-weight attestation.
    The adapter must report truthful identity and enforce its own transport,
    timeout and total attempt limits. This class never retries or falls back.
    """

    def __init__(self, factory=None, *, allow_local_models=True):
        if factory is not None and not callable(factory):
            raise ValueError('Category provider factory must be callable')
        if type(allow_local_models) is not bool:
            raise ValueError("allow_local_models must be a boolean")
        self.allow_local_models = allow_local_models
        self.factory = factory
        self.lock = threading.Lock()
        self.initialized = False
        self.adapter = None

    def require_available(self):
        if self.factory is None and not self.allow_local_models:
            raise ParserOperationalError("No configured category provider; local models are disabled")

    def stage(self, stage, model, *, expected=None):
        if stage not in {'combined', 'definition', 'membership', 'evidence_audit'}:
            raise ValueError('Unknown category stage')
        self.require_available()
        if self.factory is None:
            return induction.make_induction_infer(model, timeout=90)
        with self.lock:
            if not self.initialized:
                # A failed factory is not reconstructed to replenish its budget.
                self.initialized = True
                try:
                    infer, declared = self.factory()
                except Exception as exc:
                    raise ValueError('Configured category factory failed') from exc
                if (not callable(infer) or not isinstance(declared, dict)
                        or set(declared) != {'backend', 'model_id', 'model_revision'}):
                    raise ValueError('Configured category adapter omitted exact model provenance')
                for value in declared.values():
                    induction.producer._text(value, 300)
                self.adapter = infer, declared, deepcopy(declared)
            if self.adapter is None:
                raise ValueError('Configured category adapter initialization failed')
            infer, declared, identity = self.adapter
            if declared != identity or (expected is not None and identity != expected):
                raise ValueError('Category model identity changed')
            provenance = deepcopy(identity)
        calls = []
        used = False

        def invoke(payload, schema):
            nonlocal used
            with self.lock:
                if used:
                    raise ValueError('One callable invocation per category stage; no retry')
                used = True
                if declared != identity:
                    raise ValueError('Category model identity changed before inference')
                payload, schema = deepcopy(payload), deepcopy(schema)
                call = {'stage': stage, 'producer_payload_sha256': _digest(payload),
                        'schema_sha256': _digest(schema), 'model_provenance': deepcopy(identity),
                        'status': 'started'}
                calls.append(call)
                start = time.monotonic()
                try:
                    raw = _response_snapshot(infer(payload, schema))
                    call.update(raw_response=raw, raw_response_sha256=_digest(raw))
                    if declared != identity:
                        raise ValueError('Category model identity changed during inference')
                    call['status'] = 'returned_json'
                    return deepcopy(raw)
                except Exception as exc:
                    call.update(status='error', error_type=type(exc).__name__, error=str(exc))
                    if isinstance(exc, (ValueError, ParserOperationalError)):
                        raise
                    raise ParserOperationalError('Configured category callable failed') from exc
                finally:
                    call['elapsed_seconds'] = time.monotonic() - start

        return invoke, provenance, calls
