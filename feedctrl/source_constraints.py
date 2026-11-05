"""Conservative text-witness constraints, never semantic entailment verification."""
import re
import unicodedata

def _normalized(text):
    return unicodedata.normalize('NFKC',text).casefold()

def literal_requirements(objective,definition):
    """Declare digit-bearing terms from the request and approved definition.

    This intentionally abstains on equivalent wording, ranges or conversions.
    A matching term may still be negated, quoted or unrelated: presence is not
    evidence of truth and never grants positive membership by itself.
    """
    terms=set()
    for text in (objective,definition):
        for token in re.findall(r'(?<!\w)[\w.\-]*\d[\w.\-]*(?!\w)',_normalized(text)):
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
