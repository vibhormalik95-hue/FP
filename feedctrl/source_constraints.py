"""Conservative text-witness constraints, never semantic entailment verification."""
import re
import unicodedata

_LIST_COUNTS = dict(zip(
    ('two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'),
    range(2, 11)))
_LIST_INTRO = re.compile(r'\ball\s+(' + '|'.join(_LIST_COUNTS) + r')\s+(?:of|conditions)\s*:\s*')
_LIST_MARKER = re.compile(
    r'(?P<label>\((?P<number>[1-9][0-9]*)\))\s+'
    r'(?=(?:a|an|the|that|each|every|its|it)\s+[a-z])')

def _normalized(text):
    return unicodedata.normalize('NFKC',text).casefold()

def _top_level_positions(text):
    """Locate syntax outside quotes/backticks and balanced bracketed text.

    This scanner only restricts formatting recognition; it never removes the
    quoted/bracketed text from literal term extraction. Ambiguous unmatched
    delimiters disable the exception for this input rather than guessing.
    """
    # Multi-backtick spans/fences have their own delimiter-length rules. Do
    # not guess at Markdown parsing or expose their contents as list syntax.
    if '``' in text:
        return None
    pairs = {'(': ')', '[': ']', '{': '}'}
    quotes = {'"': '"', "'": "'", '`': '`', '“': '”', '‘': '’',
              '«': '»', '‹': '›', '”': '”', '’': '’', '»': '»', '›': '›'}
    positions = []
    brackets = []
    quote = None
    escaped = False
    for offset, char in enumerate(text):
        positions.append(quote is None and not brackets)
        # Apply the same word-apostrophe rule inside and outside quotes.
        # Escaped characters are handled first and never change delimiters.
        if quote is not None and escaped:
            escaped = False
            continue
        if quote is not None and char == '\\':
            escaped = True
            continue
        apostrophe = (char in ("'", '’') and 0 < offset < len(text) - 1
                      and text[offset - 1].isalnum() and text[offset + 1].isalnum())
        if apostrophe:
            continue
        # A trailing apostrophe after a word can be a possessive or a closing
        # single quote. Do not guess and expose later quoted list syntax.
        # Other active quote types safely contain it as ordinary text.
        if (char in ("'", '’') and offset > 0 and text[offset - 1].isalnum()
                and quote in (None, "'", '’')):
            return None
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in quotes and not apostrophe:
            quote = quotes[char]
        elif char in pairs:
            brackets.append(pairs[char])
        elif char in pairs.values():
            if not brackets or brackets.pop() != char:
                return None
    return positions if quote is None and not brackets else None

def _without_structural_enumeration(text):
    """Mask only a complete, explicitly counted, semicolon-separated list.

    Accepted syntax is ``all three of: (1) the ...; (2) a ...; and (3) that ...``
    or ``all three conditions: ...`` (word counts two through ten).
    Labels must be consecutive from one; each
    clause must start with an article/determiner/pronoun, not a quantity/unit.
    Syntax must be outside quotes/backticks and brackets. Any extra top-level
    semicolon leaves the list unchanged. Anything outside this narrow grammar
    remains a literal requirement. Mask occurrences, not numeric values:
    factual ``1`` elsewhere must survive.
    This is a formatting convention, not a semantic or grammatical validator.
    """
    top_level = _top_level_positions(text)
    if top_level is None:
        return text
    labels = []
    intros = [match for match in _LIST_INTRO.finditer(text) if top_level[match.start()]
              and (match.start() == 0 or text[match.start() - 1] not in "'’")]
    separators = [match.start() for match in re.finditer(';', text) if top_level[match.start()]]
    for position, intro in enumerate(intros):
        count = _LIST_COUNTS[intro.group(1)]
        start = intro.end()
        limit = intros[position + 1].start() if position + 1 < len(intros) else len(text)
        candidate = []
        for number in range(1, count + 1):
            marker = _LIST_MARKER.match(text, start, limit)
            if marker is None or not top_level[start] or marker.group('number') != str(number):
                break
            candidate.append(marker.span('label'))
            separator = next((position for position in separators if marker.end() <= position < limit), -1)
            if separator == -1:
                if number != count:
                    break
            else:
                # Do not accept a valid-looking prefix of any continued or
                # malformed list, including empty/decimal extra clauses.
                if number == count:
                    break
                start = separator + 1
                continuation = re.match(r'\s*(?:and\s+)?', text[start:])
                start += continuation.end()
        else:
            labels.extend(candidate)
    for start, end in reversed(sorted(set(labels))):
        text = text[:start] + ' ' * (end - start) + text[end:]
    return text

def literal_requirements(objective,definition):
    """Declare digit-bearing terms from the request and approved definition.

    This intentionally abstains on equivalent wording, ranges or conversions.
    A matching term may still be negated, quoted or unrelated: presence is not
    evidence of truth and never grants positive membership by itself.
    Only complete lists in the narrow structural-enumeration grammar are
    exempt; ambiguous numbering remains fail-closed (see the source guide).
    """
    terms=set()
    for text in (objective,definition):
        for token in re.findall(r'(?<!\w)[\w.\-]*\d[\w.\-]*(?!\w)',
                                _without_structural_enumeration(_normalized(text))):
            token=token.strip('._-')
            if token:terms.add(token)
    return {'terms':sorted(terms),'matching':'Unicode NFKC/casefold, word-delimited literal text',
        'necessary_only':True,'semantic_truth_verified':False,
        'coverage_limit':'Equivalent words, unit conversions and ranges can be withheld; a present term may be negated, quoted or unrelated.'}

def source_witnesses(requirements,fields):
    witnesses={}
    for term in requirements['terms']:
        pattern=r'(?<![\w.])'+re.escape(term)+r'(?!\w|\.\d)'
        witnesses[term]=sorted(field for field,text in fields.items() if re.search(pattern,_normalized(text)))
    return {'present':{k:v for k,v in witnesses.items() if v},'missing':sorted(k for k,v in witnesses.items() if not v)}
