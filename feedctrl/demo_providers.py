"""Two labelled stand-ins for a model connection. Neither one is a model.

``scripted``
    Returns replies that were written by hand for exact, known requests. It
    lets anyone exercise the review screens, Apply and Undo without any
    inference. It refuses every request it has no authored reply for.

``relay``
    Writes each request to a folder and waits for a reply file. An operator
    carries the request to a model that has no programmatic connection to this
    app and saves the reply unchanged. The model name is the operator's
    declaration; this transport cannot attest it.

Both announce themselves. Their backend name appears in ``/api/status``, in the
status strip of the interface and in the provenance line of every review, so
that an authored or relayed reply cannot be mistaken for an automatic call.
The normal validators still check every reply; nothing here approves anything.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time

from jsonschema import Draft202012Validator

from feedctrl.controls import ParserOperationalError
from feedctrl.hosted_app import category_payload
from feedctrl.indirect_grounding import _response_snapshot
from feedctrl.model_adapters import _decode, _hash, _json

SCRIPTED_BACKEND = 'scripted-authored-replies'
RELAY_BACKEND = 'operator-relay-file-queue'
NOT_A_MODEL = 'none (replies written by hand)'


def bind_factories(infer, identity):
    """Share one callable between the indirect-intent and category workflows.

    The category producer sends its instruction as ``instructions``; the
    semantic workflow sends ``system``. ``category_payload`` maps the first form
    to the second without altering any other field.
    """
    identity = deepcopy(identity)
    for key in ('backend', 'model', 'digest'):
        if not isinstance(identity.get(key), str) or not identity[key].strip():
            raise ValueError('Provider identity needs backend, model and digest')
    category_identity = {'backend': identity['backend'], 'model_id': identity['model'],
                         'model_revision': identity['digest']}

    def category_infer(payload, schema):
        return infer(category_payload(payload), deepcopy(schema))

    def semantic_factory():
        return infer, deepcopy(identity)

    def category_factory():
        return category_infer, deepcopy(category_identity)

    semantic_factory.model_identity = deepcopy(identity)
    category_factory.model_identity = deepcopy(identity)
    return semantic_factory, category_factory


# --------------------------------------------------------------------------
# Scripted provider
# --------------------------------------------------------------------------

def scripted_provider(lookup, table):
    """Return ``(infer, identity, receipts)`` for hand-written rehearsal replies.

    ``lookup(payload, schema)`` returns the authored reply for one exact request,
    or ``None``. The reply text lives with the demonstration scripts, outside
    this package, so that no example-specific wording becomes part of the
    application logic. ``table`` is the JSON form of all authored replies; its
    hash identifies the set that was used.
    """
    if not callable(lookup):
        raise ValueError('A lookup function for authored replies is required')
    identity = {'backend': SCRIPTED_BACKEND, 'model': NOT_A_MODEL,
                'digest': _hash(json.loads(json.dumps(table))),
                'digest_kind': 'sha256 of the authored reply table',
                'live_model': False}
    receipts, lock = [], threading.Lock()

    def infer(payload, schema):
        reply = lookup(deepcopy(payload), deepcopy(schema))
        with lock:
            receipts.append({'ordinal': len(receipts) + 1, 'request_sha256': _hash(payload),
                             'schema_sha256': _hash(schema), 'answered': reply is not None,
                             'utc': _utc()})
        if reply is None:
            raise ParserOperationalError(
                'The scripted provider has authored replies only for the bundled '
                'scenario requests; it cannot interpret other text')
        return deepcopy(reply)

    return infer, identity, receipts


# --------------------------------------------------------------------------
# Operator relay provider
# --------------------------------------------------------------------------

def _utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _write_new(path, data):
    """Create a complete file that must not already exist; never overwrite a record."""
    temporary = path.with_name(path.name + '.partial')
    with open(temporary, 'xb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temporary, path)  # fails if the destination exists
    except FileExistsError:
        temporary.unlink()
        raise
    except OSError:
        # No hard links on this file system: fall back to exclusive creation.
        with open(path, 'xb') as handle:
            handle.write(data)
    temporary.unlink()


def _await_reply(path, started, timeout, poll, settle, limit=1_000_000):
    """Return the reply bytes once the file is present, non-empty and settled.

    An editor or a slow copy can create the name before the content is complete.
    The file is read only after its size has stayed the same, and above zero,
    for ``settle`` seconds. This is not a repair: the bytes are used exactly as
    they settle. Writing under another name and renaming avoids the wait risk.
    """
    size, changed = None, time.monotonic()
    while True:
        now = time.monotonic()
        if now - started > timeout:
            raise TimeoutError('No relayed reply arrived in time')
        try:
            current = path.stat().st_size
        except FileNotFoundError:
            current = None
        if current != size:
            size, changed = current, now
        if size is not None:
            if size > limit:
                raise ValueError('Relayed reply exceeds the response budget')
            if size > 0 and now - changed >= settle:
                return path.read_bytes()
        time.sleep(poll)


def relay_provider(spool, *, declared_model, transport_note, max_calls, timeout=600, poll=0.25, settle=1.0):
    """Return ``(infer, identity, receipts)`` for an operator-carried exchange.

    For call ``n`` the app writes ``request-000n.json`` into ``spool`` and waits
    for ``response-000n.json``. The reply file must contain exactly one JSON
    object in UTF-8 (a byte-order mark is accepted). It is decoded strictly
    (duplicate keys and non-finite numbers are rejected) and validated against
    the request schema. There is no repair, no retry and no fallback; a late,
    malformed or invalid reply fails the call, and so does a reply file that
    exists before its request. A Markdown fence or any text around the object is
    a malformed reply. ``scripts/relay_tools.py`` shows a request as the exact
    text for a model and delivers an answer file by an atomic rename.
    """
    spool = Path(spool)
    if not spool.is_dir() or any(spool.iterdir()):
        raise ValueError('The relay needs an existing empty folder for this run')
    if not isinstance(declared_model, str) or not declared_model.strip() or len(declared_model) > 150:
        raise ValueError('Declare the model the operator will use')
    if not isinstance(transport_note, str) or not transport_note.strip() or len(transport_note) > 500:
        raise ValueError('Describe how requests reach the model')
    if type(max_calls) is not int or not 1 <= max_calls <= 10:
        raise ValueError('Invalid call allowance')
    if type(timeout) not in (int, float) or not 0 < timeout <= 1800:
        raise ValueError('Invalid relay timeout')
    if type(settle) not in (int, float) or not 0 <= settle <= 30:
        raise ValueError('Invalid settle time')
    config = {'backend': RELAY_BACKEND, 'model': declared_model, 'transport_note': transport_note,
              'max_calls': max_calls, 'timeout_seconds': timeout,
              'reply_rule': 'one bare JSON object; strict decode; schema validated; no repair or retry'}
    identity = {**config, 'digest': _hash(config),
                'digest_kind': 'configuration_sha256_not_model_weights',
                'identity_limit': 'Model name is an operator declaration; the relay cannot attest it',
                'live_model': 'operator_declared'}
    receipts, lock, state = [], threading.Lock(), {'calls': 0}

    def infer(payload, schema):
        payload, schema = deepcopy(payload), deepcopy(schema)
        if (not isinstance(payload, dict) or not isinstance(payload.get('system'), str)
                or not payload['system'].strip()):
            raise ValueError('Explicit system prompt required')
        Draft202012Validator.check_schema(schema)
        with lock:
            if state['calls'] >= max_calls:
                raise ParserOperationalError('Relay call allowance exhausted')
            state['calls'] += 1
            ordinal = state['calls']
        body = {key: value for key, value in payload.items() if key != 'system'}
        request = {'ordinal': ordinal, 'created_utc': _utc(), 'system': payload['system'],
                   'payload': body, 'schema': schema}
        request['request_sha256'] = _hash({k: request[k] for k in ('system', 'payload', 'schema')})
        receipt = {'ordinal': ordinal, 'request_sha256': request['request_sha256'],
                   'schema_sha256': _hash(schema), 'started_utc': request['created_utc'],
                   'declared_model': declared_model, 'outcome': 'waiting'}
        receipts.append(receipt)
        started = time.monotonic()
        reply_path = spool / f'response-{ordinal:04d}.json'
        try:
            if reply_path.exists():
                raise ValueError('A reply file existed before its request was written')
            _write_new(spool / f'request-{ordinal:04d}.json',
                       json.dumps(request, ensure_ascii=False, indent=2).encode('utf-8'))
            raw = _await_reply(reply_path, started, timeout, poll, settle)
            receipt['response_sha256'] = hashlib.sha256(raw).hexdigest()
            receipt['response_bytes'] = len(raw)
            result = _response_snapshot(_decode(raw.decode('utf-8-sig')))
            if not isinstance(result, dict):
                raise ValueError('Relayed reply must be one JSON object')
            Draft202012Validator(schema).validate(result)
            receipt['outcome'] = 'parsed_transport_only'
            return result
        except Exception as exc:
            receipt.update(outcome='error', error_type=type(exc).__name__)
            raise ParserOperationalError('Relayed call failed: ' + type(exc).__name__) from exc
        finally:
            receipt['elapsed_seconds'] = round(time.monotonic() - started, 3)
            receipt['finished_utc'] = _utc()
            try:
                _write_new(spool / f'receipt-{ordinal:04d}.json',
                           _json(receipt) + b'\n')
            except OSError:
                receipt['receipt_file_written'] = False

    return infer, identity, receipts
