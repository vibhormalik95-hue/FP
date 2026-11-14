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
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from feedctrl.controls import ParserOperationalError
from feedctrl.indirect_grounding import (APPLICATION_CHECK, PROVIDER_FAILURE, REPLY_REJECTED, _digest,
                                         _response_snapshot, clean_page_text, failure_sentence, rejected_call)
from feedctrl.label_validation import is_printable_label
from feedctrl.semantic_review import (LIMIT_CHECK, MAX_GROUPS, ProviderFailure, TooManyControls, limit_reason,
                                      printable_request, scope_effect, scoped_index, seal_group)
from feedctrl import vocabulary_grounding as grounding

# The same words that the page uses for the three actions.
ACTION_WORDS = {'boost': 'Show more', 'reduce': 'Show less', 'exclude': 'Remove'}
TERM_FIELDS = ('term_id', 'kind', 'level', 'field', 'value')
MAX_LABEL = 80


class VocabularyScope(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: int = Field(ge=0)
    candidate_ids: list[StrictInt] = Field(min_length=2, max_length=20)


class VocabularyPreview(VocabularyScope):
    text: str = Field(min_length=1, max_length=2000)
    mode: Literal['merge', 'replace'] = 'merge'

    @field_validator('text')
    @classmethod
    def printable(cls, value):
        return printable_request(value)


def term_key(term):
    """What a term is: its field and its exact value. Identifiers depend on the scope."""
    return (term['field'], term['value'])


def same_control(group, control):
    """True when an applied group is a category and tag control with this operation and these terms.

    Such a group is the earlier instruction for the same thing, so the new
    control replaces it in merge mode (its strength can differ: the latest
    reviewed strength wins). A control of another method, another operation
    or another term set is never replaced, whatever its name is.
    """
    proposal = group['proposal']
    return (proposal.get('grounding') == 'vocabulary'
            and proposal['action']['operation'] == control['action']['operation']
            and {term_key(term) for term in proposal.get('vocabulary_terms', [])}
            == {term_key(term) for term in control['terms']})


def control_label(control, taken):
    """A printable group name from the action and the kind and value of each term.

    The kind is part of the name, because one value can be a category and a
    tag. A name that is too long is cut and gets a short hash of its action and
    terms, so that two long names do not become equal. ``taken`` holds the
    case-folded names that are in use (the kept applied controls and the
    controls of this proposal); a name that is in use gets a number. A new
    control therefore never takes the name of a control over other terms.
    """
    word = ACTION_WORDS[control['action']['operation']]
    label = f"{word}: " + ', '.join(f'{term["kind"]} "{term["value"]}"' for term in control['terms'])
    if not is_printable_label(label):
        # A catalogue value may hold a format character. Identifiers never do.
        label = f"{word}: terms {', '.join(term['term_id'] for term in control['terms'])}"
    if len(label) > MAX_LABEL:
        mark = _digest([control['action']['operation'], control['action']['strength'],
                        sorted(term_key(term) for term in control['terms'])])[:6]
        label = label[:MAX_LABEL - 12].rstrip() + f'... [{mark}]'
    base, number = label, 2
    while label.casefold() in taken:
        suffix = f' ({number})'
        label, number = base[:MAX_LABEL - len(suffix)].rstrip() + suffix, number + 1
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
        # One entry for each provider invocation that was begun, also one that raised.
        attempts, extra = [], {}
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

        def not_ready(status, reason, source, clarification=None):
            # ``vocabulary`` here holds the terms and the checks only: a result
            # that is not ready never lists controls.
            value = {'ready': False, 'applied': False, 'status': status, 'reason': reason,
                     'grounding': 'vocabulary',
                     'vocabulary': {'terms': deepcopy(vocabulary['terms']), 'checks': deepcopy(vocabulary['checks'])},
                     'model_calls': deepcopy(calls), 'model_provenance': deepcopy(provenance),
                     'calls_attempted': len(attempts), 'call_attempts': deepcopy(attempts),
                     'outcome_source': source, 'failed_stage': 'interpretation', **extra}
            if clarification is not None:
                value['clarification'] = deepcopy(clarification)
            return value

        def limit(applied, added):
            vocabulary['checks'] = [*vocabulary['checks'], {'check': LIMIT_CHECK, 'passed': False,
                                    'detail': f'{applied} stay applied; this request adds {added}'}]
            return not_ready('limit', limit_reason(applied, added), APPLICATION_CHECK)

        try:
            # The existing terms are part of every answer, also when the provider cannot start.
            vocabulary['terms'] = grounding.build_vocabulary(index)
            if body.mode != 'replace' and len(existing) >= MAX_GROUPS:
                # Every reply adds at least one control, so no call is spent on a plan that cannot fit.
                return limit(len(existing), 1)
            # Operator-selected transport, never request-supplied URLs or keys.
            infer, provenance = configured_infer()

            def tracked_infer(payload, schema):
                # Own raw receipts; these are returned only to this session's caller.
                attempt = {'stage': 'interpretation', 'status': 'started'}
                attempts.append(attempt)
                try:
                    raw = infer(deepcopy(payload), deepcopy(schema))
                except Exception as exc:
                    attempt.update(status='failed', error_type=type(exc).__name__)
                    raise
                try:
                    bounded = _response_snapshot(raw)
                except (TypeError, ValueError, RecursionError):
                    # The grounding step rejects this reply itself and says why.
                    # The reply stays visible to the reviewer as bounded text.
                    attempt['status'] = 'reply_rejected'
                    calls.append(rejected_call(payload, schema, raw))
                    return raw
                attempt['status'] = 'returned'
                calls.append({'request_sha256': _digest(payload), 'schema_sha256': _digest(schema),
                              'response_sha256': _digest(bounded), 'raw_response': deepcopy(bounded)})
                return bounded

            proposal = grounding.propose_vocabulary(body.text, index, tracked_infer, model_provenance=provenance)
            vocabulary = {'terms': proposal['vocabulary']['terms'], 'checks': proposal['checks']}
            if 'reply_reason' in proposal:
                # The reason that the reply gives for itself. Model text; shown as such.
                extra['reply_reason'] = proposal['reply_reason']
            if proposal['status'] != 'review':
                return not_ready(proposal['status'], proposal['reason'], proposal['outcome_source'],
                                 proposal.get('clarification'))
            # In merge mode a new control replaces an applied control only when
            # that one has the same operation over the same terms (see
            # ``same_control``). Every other applied control stays, whatever its
            # name is; a generated name that is in use gets a number.
            kept = [] if body.mode == 'replace' else [
                group for group in existing
                if not any(same_control(group, control) for control in proposal['controls'])]
            if len(kept) + len(proposal['controls']) > MAX_GROUPS:
                return limit(len(kept), len(proposal['controls']))
            taken = {group['label'].casefold() for group in kept}
            outside_terms = {term_key(term): term for term in grounding.build_vocabulary(demo.topic_index)}
            groups, controls, scope_effects = [], [], []
            for control in proposal['controls']:
                label = control_label(control, taken)
                sealed = {'status': 'review', 'requires_review': True, 'reason': control['relation'],
                          'action': deepcopy(control['action']), 'item_ids': list(control['item_ids']),
                          'evidence': deepcopy(control['evidence']), 'provenance': deepcopy(control['provenance']),
                          'action_source': 'model', 'grounding': 'vocabulary',
                          'vocabulary_terms': [{key: term[key] for key in TERM_FIELDS} for term in control['terms']]}
                groups.append(seal_group(label, body.text, sealed, index, demo.items))
                # A control changes only the items of the evidence scope. Items
                # outside it that carry a chosen term stay as they are.
                outside = sorted({item for term in control['terms']
                                  for item in outside_terms.get(term_key(term), {'item_ids': []})['item_ids']
                                  if item not in index['items']})
                controls.append({'label': groups[-1]['label'], **control['action'], 'relation': control['relation'],
                                 'terms': deepcopy(control['terms']), 'item_ids': list(control['item_ids']),
                                 'outside_scope_item_ids': outside})
                scope_effects.append(scope_effect(groups[-1]['label'], control['item_ids'], outside,
                                                  len(index['items'])))
            selected = {item for control in controls for item in control['item_ids']}
            # Evidence for exclusion: what each item outside every control carries.
            vocabulary.update(controls=controls, not_selected=[
                {'item_id': item, 'terms': [{'kind': term['kind'], 'level': term['level'], 'value': term['value']}
                                            for term in vocabulary['terms'] if item in term['item_ids']]}
                for item in sorted(index['items']) if item not in selected])
            with demo.lock:
                state = state_for(x_session_id, body.user_id)
                if state['semantic_revision'] != revision or state.get('semantic_preview_nonce') != nonce:
                    raise HTTPException(409, 'Preferences changed during inference; review again')
                result = review(state, body.user_id, kept + groups,
                                proposals=[group['proposal'] for group in groups])
                return {**result, 'grounding': 'vocabulary', 'vocabulary': deepcopy(vocabulary),
                        'model_calls': deepcopy(calls), 'model_provenance': deepcopy(provenance),
                        'calls_attempted': len(attempts), 'call_attempts': deepcopy(attempts),
                        'scope_effects': scope_effects, **extra}
        except TooManyControls as exc:
            return limit(exc.applied, exc.added)
        except ValueError as exc:
            # An application sentence about the request or the plan; it holds no provider text.
            return not_ready('error', f'Proposal rejected ({type(exc).__name__}): {clean_page_text(exc)}',
                             REPLY_REJECTED if attempts else APPLICATION_CHECK)
        except ParserOperationalError as exc:
            # The provider could not start, so no call was begun. HTTP 502 as before;
            # the body carries the same fields as every other answer that is not ready.
            sentence = failure_sentence(exc)
            raise ProviderFailure('Category and tag match failed '
                                  f'({type(exc).__name__}); no preferences changed: {sentence}',
                                  not_ready('error', sentence, PROVIDER_FAILURE)) from exc
