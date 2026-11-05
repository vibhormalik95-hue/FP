"""Bounded local inference and source custody for reviewed category induction."""
from copy import deepcopy
import json
import re
import time

from feedctrl.controls import _request, ollama_provenance
from feedctrl.indirect_grounding import _catalogue, _digest
from feedctrl import category_induction_producer as producer
from feedctrl.semantic_induction import catalogue_snapshot, validate_induced_category

MAX_ITEMS = 12
PRODUCER_BYTES = 7000
CHAT_BYTES = 10000


def projected_inventory(index, original_categories, groups):
    """Explicit inventory projection onto this declared evidence pool."""
    ids = set(index['items'])
    rows = []
    categories = sorted({c for i in ids for c in original_categories[i]})
    for c in categories:
        rows.append({'category_id': 'original:' + c, 'label': c,
                     'member_ids': sorted(i for i in ids if c in original_categories[i])})
    for field in ('first_level_category_name', 'second_level_category_name', 'third_level_category_name'):
        labels = sorted({r['fields'].get(field, '') for r in index['items'].values()} - {'', 'UNKNOWN'})
        for label in labels:
            rows.append({'category_id': 'source:' + field + ':' + _digest(label), 'label': label,
                'member_ids': sorted(i for i in ids if index['items'][i]['fields'].get(field) == label)})
    for n, group in enumerate(groups):
        rows.append({'category_id': 'saved:' + str(n) + ':' + _digest(group['label']),
            'label': group['label'], 'member_ids': sorted(ids & set(group['proposal']['item_ids']))})
    return sorted(rows, key=lambda c: c['category_id'])


def make_induction_infer(model, timeout=90):
    """One local call, exact identity, explicit instructions-to-system adapter.

    Raw HTTP JSON is retained before content parsing so malformed model content
    remains inspectable. Nothing is persisted or applied by this adapter.
    """
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,150}', model):
        raise ValueError('Invalid installed model name')
    if not 0 < timeout <= 90:
        raise ValueError('Timeout must be positive and at most 90 seconds')
    p = ollama_provenance('http://127.0.0.1:11434', model, 10)
    provenance = {'backend': 'ollama-loopback', 'model_id': model, 'model_revision': p['digest']}
    calls = []
    used = False

    def infer(payload, schema):
        nonlocal used
        if used:
            raise ValueError('One inference attempt per category proposal; no retry')
        used = True
        payload, schema = deepcopy(payload), deepcopy(schema)
        prompt = payload.pop('instructions')
        request = {'model': model, 'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, allow_nan=False)}],
            'format': schema, 'stream': False, 'keep_alive': '2m',
            'options': {'temperature': 0, 'seed': 42, 'num_ctx': 16384, 'num_predict': 4096}}
        # Match controls._request's actual JSON serialization, including ASCII
        # escapes for non-ASCII source text. UTF-8 display size is not wire size.
        wire_bytes = len(json.dumps(request, allow_nan=False).encode('utf-8'))
        if wire_bytes > CHAT_BYTES:
            raise ValueError('Actual chat payload exceeds the declared 10000-byte budget')
        call = {'request_sha256': _digest(request), 'producer_payload_sha256': _digest({'instructions': prompt, **payload}),
            'schema_sha256': _digest(schema), 'model': model, 'digest': p['digest'],
            'ollama_version': p.get('ollama_version'), 'request_bytes': wire_bytes, 'status': 'started'}
        calls.append(call)
        start = time.monotonic()
        try:
            raw = _request('http://127.0.0.1:11434', '/api/chat', request, timeout)
            call['raw_http_response'] = deepcopy(raw)
            call['raw_response_sha256'] = _digest(raw)
            if raw.get('done') is not True or raw.get('done_reason') == 'length':
                raise ValueError('Incomplete model response')
            if raw.get('model') != model:
                raise ValueError('Response model identity differs from requested model')
            current = ollama_provenance('http://127.0.0.1:11434', model, 10)
            if current['digest'] != p['digest']:
                raise ValueError('Installed model changed during inference')
            result = json.loads(raw['message']['content'])
            call['status'] = 'returned_json'
            return result
        except Exception as exc:
            call.update(status='error', error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            call['elapsed_seconds'] = time.monotonic() - start
    return infer, provenance, calls


def checked_category(envelope, objective, index, inventory):
    if 'staged_definition' in envelope:
        from feedctrl.staged_induction import revalidate_membership_envelope
        revalidate_membership_envelope(envelope,objective,index,inventory)
    proposal, provenance = producer.validate_current_source(envelope, objective, index, inventory)
    catalogue = catalogue_snapshot(producer.catalogue_records(index, inventory))
    return validate_induced_category(proposal, catalogue, provenance)


def category_as_control(envelope, objective, index, inventory, operation, strength, runtime_model):
    """Bridge only validated positives into a separately reviewed action."""
    validated = checked_category(envelope, objective, index, inventory)
    action = {'operation': operation, 'strength': strength, 'intent_span': objective}
    return {'status': 'review', 'requires_review': True, 'reason': envelope['rationale'],
        'action': action, 'action_source': 'manual', 'item_ids': validated['member_ids'],
        'evidence': [{'item_id': r['item_id'], 'field': r['field'], 'quote': r['evidence_quote']}
                     for r in envelope['field_evidence'] if r['verdict'] == 'match'],
        'provenance': {'source_sha256': index['sha256'], 'catalogue_sha256': _digest(_catalogue(index)),
            'request_sha256': _digest(objective), 'action_sha256': _digest(action),
            'model': {'backend': runtime_model['backend'], 'model': runtime_model['model_id'],
                      'digest': runtime_model['model_revision']}},
        'induction': {'objective': objective, 'envelope': deepcopy(envelope),
            'inventory': deepcopy(inventory), 'validated_category': validated}}


def revalidate_category(control, index, original_categories):
    """Recheck every definition/disposition and exact field quote on current data."""
    record = control['induction']
    if original_categories is None:
        raise ValueError('Current original category mappings are required for induced groups')
    try:
        current_base = projected_inventory(index, original_categories, [])
    except (KeyError, TypeError) as exc:
        raise ValueError('Current original category mappings are missing or invalid') from exc
    # Saved groups describe the creation-time comparison context, not the live
    # source taxonomy. Reproject the authoritative original/source inventory on
    # every use, without introducing the induced group itself as a new dependency.
    recorded_base = [c for c in record['inventory'] if not c['category_id'].startswith('saved:')]
    if _digest(current_base) != _digest(recorded_base):
        raise ValueError('Category inventory changed since induction; regenerate and review')
    validated = checked_category(record['envelope'], record['objective'], index, record['inventory'])
    if (validated != record['validated_category'] or validated['member_ids'] != control['item_ids']
            or record['objective'] != control['action']['intent_span']):
        raise ValueError('Category definition, membership or objective changed after review')
    evidence = [{'item_id': r['item_id'], 'field': r['field'], 'quote': r['evidence_quote']}
                for r in record['envelope']['field_evidence'] if r['verdict'] == 'match']
    if evidence != control['evidence']:
        raise ValueError('Approved field evidence changed')
