"""Session-bound review of controls over existing category and tag terms.

One configured model call maps a request to existing terms. The application
checks the terms, selects the members and seals one reviewed group for each
control. Review, Apply and Undo are the unchanged semantic-group routes, so a
group made here is validated, ranked and reversed exactly like every other one.
"""
from copy import deepcopy
import secrets
from typing import Literal

from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from feedctrl.controls import ParserOperationalError
from feedctrl.indirect_grounding import _digest, _response_snapshot
from feedctrl.label_validation import is_printable_label
from feedctrl.semantic_review import scoped_index, seal_group
from feedctrl import vocabulary_grounding as grounding

OPERATION_WORDS = {'boost': 'Increase', 'reduce': 'Decrease', 'exclude': 'Exclude'}
TERM_FIELDS = ('term_id', 'kind', 'level', 'field', 'value')


class VocabularyScope(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: int = Field(ge=0)
    candidate_ids: list[StrictInt] = Field(min_length=2, max_length=20)


class VocabularyPreview(VocabularyScope):
    text: str = Field(min_length=1, max_length=2000)
    mode: Literal['merge', 'replace'] = 'merge'


def control_label(control, taken):
    """A printable group name from the operation and the term values.

    ``taken`` holds the names already given in this proposal, case-folded, so
    that two controls of one request never share a name. A later request with
    the same operation and terms gets the same name and replaces the earlier
    group in merge mode: the latest reviewed instruction for those terms wins.
    """
    word = OPERATION_WORDS[control['action']['operation']]
    label = f"{word}: {' + '.join(term['value'] for term in control['terms'])}"
    if not is_printable_label(label):
        # A catalogue value may hold a format character. Identifiers never do.
        label = f"{word}: terms {' + '.join(term['term_id'] for term in control['terms'])}"
    if len(label) > 80:
        label = label[:79].rstrip() + '…'
    base, number = label, 2
    while label.casefold() in taken:
        suffix = f' ({number})'
        label, number = base[:80 - len(suffix)].rstrip() + suffix, number + 1
    taken.add(label.casefold())
    return label


def install_vocabulary_routes(app, demo, state_for, review, *, configured_infer, provider_available):
    """Add the two vocabulary routes to a session-scoped semantic application."""

    @app.post('/api/semantic/vocabulary/terms')
    def terms(body: VocabularyScope, x_session_id: str | None = Header(default=None)):
        # No model call: the existing terms of the declared scope, for display.
        with demo.lock:
            state_for(x_session_id, body.user_id)
            try:
                index = scoped_index(demo.topic_index, body.candidate_ids)
                vocabulary = grounding.build_vocabulary(index)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return {'terms': vocabulary, 'source_sha256': index['sha256'],
                'vocabulary_sha256': _digest(vocabulary),
                'note': 'Existing category and tag values of the supplied items. '
                        'A tag field is split on commas, semicolons and vertical bars. No model was called.'}

    @app.post('/api/semantic/vocabulary/preview')
    def preview(body: VocabularyPreview, x_session_id: str | None = Header(default=None)):
        if not provider_available:
            raise HTTPException(503, 'No model provider is configured for this server; '
                                     'a category and tag match needs one. No inference was attempted')
        calls, provenance, vocabulary = [], None, {'terms': [], 'checks': []}
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            revision, nonce = state['semantic_revision'], secrets.token_urlsafe(16)
            state['semantic_preview_nonce'] = nonce
            state['semantic_pending'] = None
            existing = deepcopy(state['semantic_groups'])
            try:
                index = scoped_index(demo.topic_index, body.candidate_ids)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

        def not_ready(status, reason, clarification=None):
            value = {'ready': False, 'applied': False, 'status': status, 'reason': reason,
                     'grounding': 'vocabulary', 'vocabulary': deepcopy(vocabulary),
                     'model_calls': deepcopy(calls), 'model_provenance': deepcopy(provenance)}
            if clarification is not None:
                value['clarification'] = deepcopy(clarification)
            return value

        try:
            # Operator-selected transport, never request-supplied URLs or keys.
            infer, provenance = configured_infer()

            def tracked_infer(payload, schema):
                # Own raw receipts; these are returned only to this session's caller.
                try:
                    raw = _response_snapshot(infer(deepcopy(payload), deepcopy(schema)))
                except RecursionError as exc:
                    raise ValueError('Model response exceeds JSON nesting budget') from exc
                calls.append({'request_sha256': _digest(payload), 'schema_sha256': _digest(schema),
                              'response_sha256': _digest(raw), 'raw_response': deepcopy(raw)})
                return raw

            proposal = grounding.propose_vocabulary(body.text, index, tracked_infer, model_provenance=provenance)
            vocabulary = {'terms': proposal['vocabulary']['terms'], 'checks': proposal['checks']}
            if proposal['status'] != 'review':
                return not_ready(proposal['status'], proposal['reason'], proposal.get('clarification'))
            taken, groups, controls = set(), [], []
            for control in proposal['controls']:
                label = control_label(control, taken)
                sealed = {'status': 'review', 'requires_review': True, 'reason': control['relation'],
                          'action': deepcopy(control['action']), 'item_ids': list(control['item_ids']),
                          'evidence': deepcopy(control['evidence']), 'provenance': deepcopy(control['provenance']),
                          'action_source': 'model', 'grounding': 'vocabulary',
                          'vocabulary_terms': [{key: term[key] for key in TERM_FIELDS} for term in control['terms']]}
                groups.append(seal_group(label, body.text, sealed, index, demo.items))
                controls.append({'label': groups[-1]['label'], **control['action'], 'relation': control['relation'],
                                 'terms': deepcopy(control['terms']), 'item_ids': list(control['item_ids'])})
            selected = {item for control in controls for item in control['item_ids']}
            # Evidence for exclusion: what each item outside every control carries.
            vocabulary.update(controls=controls, not_selected=[
                {'item_id': item, 'terms': [{'kind': term['kind'], 'level': term['level'], 'value': term['value']}
                                            for term in vocabulary['terms'] if item in term['item_ids']]}
                for item in sorted(index['items']) if item not in selected])
            kept = [] if body.mode == 'replace' else [g for g in existing if g['label'].casefold() not in taken]
            if len(kept) + len(groups) > 8:
                raise ValueError('At most eight active semantic groups')
            with demo.lock:
                state = state_for(x_session_id, body.user_id)
                if state['semantic_revision'] != revision or state.get('semantic_preview_nonce') != nonce:
                    raise HTTPException(409, 'Preferences changed during inference; review again')
                result = review(state, body.user_id, kept + groups,
                                proposals=[group['proposal'] for group in groups])
                return {**result, 'grounding': 'vocabulary', 'vocabulary': deepcopy(vocabulary),
                        'model_calls': deepcopy(calls), 'model_provenance': deepcopy(provenance)}
        except ValueError as exc:
            return not_ready('error', f'Proposal rejected ({type(exc).__name__}): {exc}')
        except ParserOperationalError as exc:
            raise HTTPException(502, 'Category and tag match failed '
                                     f'({type(exc).__name__}); no preferences changed: {exc}') from exc
