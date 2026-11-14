"""Hand-written replies for the three bundled demonstration scenarios.

These are rehearsal doubles, not model output and not a method. They let the
review screens, Apply and Undo be exercised with no inference. Each reply is
returned only for the exact bundled request; every other request is refused.
Every reason string starts with "Authored rehearsal reply" and each generated
label or title ends with "(authored rehearsal)", so the text identifies itself
on screen.
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

# Scenario "tags" (scenarios/categories-and-tags): requests matched to existing
# category and tag terms. Each reply is bound to the exact request text and to
# the exact vocabulary of the ten bundled items: [kind, level, value, items].
_TAGS_IDS = list(range(61001, 61011))
_TAGS_VOCABULARY = [
    ['category', 1, 'Cooking', 3], ['category', 1, 'Music', 2], ['category', 1, 'Repair', 2],
    ['category', 1, 'Travel', 2],
    ['category', 2, 'Baking', 1], ['category', 2, 'Bicycle repair', 1], ['category', 2, 'City walks', 1],
    ['category', 2, 'Guitar', 1], ['category', 2, 'Home recipes', 2], ['category', 2, 'Home repair', 1],
    ['category', 2, 'Live sessions', 1], ['category', 2, 'Rail journeys', 1],
    ['tag', None, 'baking', 1], ['tag', None, 'bicycle', 1], ['tag', None, 'bread', 1],
    ['tag', None, 'bridge', 1], ['tag', None, 'dinner', 1], ['tag', None, 'guitar', 1],
    ['tag', None, 'lamp', 1], ['tag', None, 'live', 1], ['tag', None, 'night market', 1],
    ['tag', None, 'piano', 1], ['tag', None, 'practice', 1], ['tag', None, 'recipe', 2],
    ['tag', None, 'salad', 1], ['tag', None, 'street food', 1], ['tag', None, 'tools', 2],
    ['tag', None, 'train', 1],
]
_FOOD_TERMS = [['category', 'Cooking'], ['tag', 'street food']]
# One entry for each bundled request. A term is written as [kind, value]; its
# identifier is read from the request, so no identifier is fixed here.
_TAGS_REPLIES = {
    "I'm not hungry, remove all the stuff that makes me hungry.": {
        'status': 'propose', 'negation_resolved': True, 'alternatives': [],
        'reason': _AUTHORED + 'Not being hungry is a personal state; the command is to remove what causes hunger.',
        'controls': [{'control': 'exclude/none', 'intent_span': 'all the stuff that makes me hungry',
                      'relation': _AUTHORED + 'The category Cooking and the tag street food name food.',
                      'terms': _FOOD_TERMS}]},
    'Hide the Repair category.': {
        'status': 'propose', 'negation_resolved': True, 'alternatives': [],
        'reason': _AUTHORED + 'The request names one existing category.',
        'controls': [{'control': 'exclude/none', 'intent_span': 'the Repair category',
                      'relation': _AUTHORED + 'The category Repair has the same name.',
                      'terms': [['category', 'Repair']]}]},
    'Show me more repair videos, and remove anything about food.': {
        'status': 'propose', 'negation_resolved': True, 'alternatives': [],
        'reason': _AUTHORED + 'The request holds two separate preferences.',
        'controls': [
            {'control': 'boost/standard', 'intent_span': 'more repair videos',
             'relation': _AUTHORED + 'The category Repair covers repair videos.',
             'terms': [['category', 'Repair']]},
            {'control': 'exclude/none', 'intent_span': 'anything about food',
             'relation': _AUTHORED + 'The category Cooking and the tag street food name food.',
             'terms': _FOOD_TERMS}]},
    'I have had enough of the heavy stuff.': {
        'status': 'ambiguous', 'negation_resolved': True, 'controls': [],
        'reason': _AUTHORED + 'The word heavy can point to several existing terms.',
        'alternatives': ['Heavy as in rich food: the category Cooking.',
                         'Heavy as in tools and manual work: the category Repair.',
                         'Heavy as in loud music: the category Music.']},
    'Show me at most two cooking videos per day.': {
        'status': 'unsupported', 'negation_resolved': True, 'alternatives': [], 'controls': [],
        'reason': _AUTHORED + ('A limit for each day is a quota. The controls can increase, decrease or '
                               'exclude whole terms. They cannot count items or use the date.')},
    'Show me fewer videos about astronomy.': {
        'status': 'no_match', 'negation_resolved': True, 'alternatives': [], 'controls': [],
        'reason': _AUTHORED + 'No existing category or tag is about astronomy.'},
}
# The separate two-call route that reads descriptions, on the same ten items.
_EATING_REQUEST = 'Remove the videos where someone is eating.'
_EATING_ACTION = {'needs_clarification': False, 'question': '', 'control': 'exclude/none',
                  'intent_span': 'the videos where someone is eating'}
_EATING_GROUNDING = {
    'status': 'propose',
    'reason': _AUTHORED + 'One description states that a person eats.',
    'negation_resolved': True, 'alternatives': [],
    'evidence': [{'item_id': 61004, 'field': 'caption', 'quote': 'between bites of a sandwich'}],
}
_FICTIONAL_BRIEF = 'A fictional 40-second clip about repairing a kite, for a test feed.'
_FICTIONAL_DRAFT = {
    'title': 'Kite repair clip (authored rehearsal)',
    'description': _AUTHORED + ('A fictional 40-second clip. A torn kite is patched with tape and flies again. '
                                'No real video exists.'),
    'category_label': 'Repair (authored rehearsal)',
}


def _catalogue_ids(payload):
    rows = payload.get('catalogue')
    return sorted(row['item_id'] for row in rows) if isinstance(rows, list) else None


def _vocabulary_reply(payload):
    """The authored reply for one bundled request over the exact bundled vocabulary."""
    vocabulary = payload.get('vocabulary')
    if not isinstance(vocabulary, list) or not all(isinstance(term, dict) for term in vocabulary):
        return None
    supplied = {(term.get('kind'), term.get('level'), term.get('value'), term.get('item_count'))
                for term in vocabulary}
    reply = _TAGS_REPLIES.get(payload.get('request'))
    if reply is None or supplied != {tuple(row) for row in _TAGS_VOCABULARY}:
        return None
    identifier = {(term['kind'], term['value']): term['term_id'] for term in vocabulary}
    controls = [{**control, 'terms': [{'term_id': identifier[(kind, value)], 'value': value}
                                      for kind, value in control['terms']]}
                for control in reply['controls']]
    return {**reply, 'controls': controls}


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
        if payload.get('request') == _EATING_REQUEST:
            return _EATING_ACTION
    elif required == {'status', 'reason', 'negation_resolved', 'alternatives', 'evidence'}:
        if payload.get('request') == _HUNGER_REQUEST and ids == _HUNGER_IDS:
            return _HUNGER_GROUNDING
        if payload.get('request') == _EATING_REQUEST and ids == _TAGS_IDS:
            return _EATING_GROUNDING
    elif required == {'status', 'reason', 'negation_resolved', 'alternatives', 'controls'}:
        return _vocabulary_reply(payload)
    elif required == {'title', 'description', 'category_label'}:
        if payload.get('brief') == _FICTIONAL_BRIEF:
            return _FICTIONAL_DRAFT
    return None


TABLE = [_CATEGORY_OBJECTIVE, _CATEGORY_DEFINITION, _CATEGORY_MEMBERSHIP, _CATEGORY_AUDIT,
         _HUNGER_REQUEST, _HUNGER_ACTION, _HUNGER_GROUNDING,
         _TAGS_VOCABULARY, _TAGS_REPLIES, _EATING_REQUEST, _EATING_ACTION, _EATING_GROUNDING,
         _FICTIONAL_BRIEF, _FICTIONAL_DRAFT]
