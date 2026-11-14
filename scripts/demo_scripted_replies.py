"""Hand-written replies for the two bundled demonstration scenarios.

These are rehearsal doubles, not model output and not a method. They let the
review screens, Apply and Undo be exercised with no inference. Each reply is
returned only for the exact bundled request; every other request is refused.
Every reason string starts with "Authored rehearsal reply" and the category
label ends with "(authored rehearsal)", so the text identifies itself on screen.
"""

_AUTHORED = 'Authored rehearsal reply, not model output. '

_CATEGORY_OBJECTIVE = (
    'Propose one useful new category from these eight descriptions. Decide the shared '
    'concept yourself from the stated facts, rather than taking an existing category code '
    'as its meaning. Give a precise definition supported by the descriptions; do not merely '
    'rename an existing category or invent missing facts.')
_CATEGORY_IDS = list(range(41001, 41009))
_CATEGORY_DEFINITION = {
    'status': 'propose',
    'label': 'Repaired existing object that is kept (authored rehearsal)',
    'definition': ('The description states that a damaged existing object is repaired and '
                   'that the same object is kept.'),
    'rationale': _AUTHORED + 'Three descriptions state both a repair and that the same object is kept.',
    'alternatives': [],
    'evidence': [
        {'item_id': 41001, 'field': 'caption',
         'quote': 'straightened with pliers and used again. The existing piece is kept.',
         'reason': _AUTHORED + 'States a repair and that the existing piece is kept.'},
        {'item_id': 41003, 'field': 'caption',
         'quote': 'sealed and returned to watering plants. The same jug remains in use.',
         'reason': _AUTHORED + 'States a repair and that the same jug remains.'},
    ],
}
# (verdict, quote, reason) per item for the membership call.
_CATEGORY_MEMBERSHIP = {
    41001: ('match', 'straightened with pliers and used again. The existing piece is kept.',
            'Repair and retention are both stated.'),
    41002: ('match', 'mended with a needle and spare thread so it can carry books again. The same bag is kept.',
            'Repair and retention are both stated.'),
    41003: ('match', 'sealed and returned to watering plants. The same jug remains in use.',
            'Repair and retention are both stated.'),
    41004: ('not_match', 'put in recycling and a newly purchased organizer is unpacked in its place',
            'The broken object is replaced, not kept.'),
    41005: ('unknown', '', 'The text describes folding paper offcuts into a new tray; whether a damaged existing object was repaired and kept is not stated.'),
    41006: ('unknown', '',
            'The text describes shaping a raw wooden blank into a new knob; whether a damaged existing object was repaired and kept is not stated.'),
    41007: ('unknown', '', 'No completed activity is described.'),
    41008: ('unknown', '', 'The subject is not described.'),
}
# (assessment, quote, reason) per item for the separate evidence assessment.
# Missing repair evidence stays unknown in both authored stages.
# Deliberately incorrect classifications belong in adversarial tests, not this rehearsal.
_CATEGORY_AUDIT = {
    41001: ('supported', 'straightened with pliers and used again. The existing piece is kept.',
            'Both conditions are stated.'),
    41002: ('supported', 'mended with a needle and spare thread so it can carry books again. The same bag is kept.',
            'Mending and retention of the same bag are stated.'),
    41003: ('supported', 'sealed and returned to watering plants. The same jug remains in use.',
            'Both conditions are stated.'),
    41004: ('contradicted', 'a newly purchased organizer is unpacked in its place',
            'The object is replaced.'),
    41005: ('not_stated', '', 'Whether an existing damaged object was repaired is not stated.'),
    41006: ('not_stated', '', 'The text describes shaping a raw wooden blank into a new knob; whether a damaged existing object was repaired and kept is not stated.'),
    41007: ('not_stated', '', 'No completed activity or finished object is described.'),
    41008: ('not_stated', '', 'The subject is not described.'),
}

_HUNGER_REQUEST = "I'm not hungry, remove all the stuff that makes me hungry."
_HUNGER_IDS = list(range(81001, 81009))
_HUNGER_ACTION = {'needs_clarification': False, 'question': '', 'control': 'exclude/none',
                  'intent_span': 'all the stuff that makes me hungry'}
_HUNGER_GROUNDING = {
    'status': 'propose',
    'reason': _AUTHORED + 'Descriptions of preparing food to be eaten are taken as the stated subject.',
    'negation_resolved': True, 'alternatives': [],
    'evidence': [
        {'item_id': 81001, 'field': 'caption', 'quote': 'prepares an edible tomato-and-pasta dinner'},
        {'item_id': 81003, 'field': 'caption', 'quote': 'bakes the loaf, and slices it for eating'},
        {'item_id': 81006, 'field': 'caption', 'quote': 'mixes a salad intended to be eaten'},
    ],
}


def _catalogue_ids(payload):
    rows = payload.get('catalogue')
    return sorted(row['item_id'] for row in rows) if isinstance(rows, list) else None


def lookup(payload, schema):
    """Return the authored reply for one exact bundled request, or None."""
    required = set(schema.get('required', []))
    ids = _catalogue_ids(payload)
    if required == {'status', 'label', 'definition', 'rationale', 'alternatives', 'evidence'}:
        if payload.get('objective') == _CATEGORY_OBJECTIVE and ids == _CATEGORY_IDS:
            return _CATEGORY_DEFINITION
    elif required == {'memberships'}:
        if ids == _CATEGORY_IDS and (payload.get('reviewed_definition') or {}).get('definition') \
                == _CATEGORY_DEFINITION['definition']:
            return {'memberships': [
                {'item_id': item, 'verdict': verdict, 'field': 'caption' if quote else '',
                 'evidence_quote': quote, 'reason': _AUTHORED + reason}
                for item, (verdict, quote, reason) in _CATEGORY_MEMBERSHIP.items()]}
    elif required == {'assessments'}:
        if ids == _CATEGORY_IDS and (payload.get('reviewed_definition') or {}).get('definition') \
                == _CATEGORY_DEFINITION['definition']:
            return {'assessments': [
                {'item_id': item, 'assessment': assessment, 'field': 'caption' if quote else '',
                 'quote': quote, 'reason': _AUTHORED + reason}
                for item, (assessment, quote, reason) in _CATEGORY_AUDIT.items()]}
    elif required == {'needs_clarification', 'question', 'control', 'intent_span'}:
        if payload.get('request') == _HUNGER_REQUEST:
            return _HUNGER_ACTION
    elif required == {'status', 'reason', 'negation_resolved', 'alternatives', 'evidence'}:
        if payload.get('request') == _HUNGER_REQUEST and ids == _HUNGER_IDS:
            return _HUNGER_GROUNDING
    return None


TABLE = [_CATEGORY_OBJECTIVE, _CATEGORY_DEFINITION, _CATEGORY_MEMBERSHIP, _CATEGORY_AUDIT,
         _HUNGER_REQUEST, _HUNGER_ACTION, _HUNGER_GROUNDING]
