import pytest
from feedctrl.source_constraints import literal_requirements,source_witnesses

@pytest.mark.parametrize('objective,definition,expected',[
    ('An IP68 claim','Rated IP68',['ip68']),('Exactly 90 points','A score of 90',['90']),
    ('An 18-month plan','A current 18-month plan',['18-month']),
    ('Version 5.4','Version 5.4.',['5.4']),('A quiet activity','Quiet activities',[]),
    ('Fullwidth ＩＰ６８','IP68',['ip68'])])
def test_declared_terms_are_general_and_deduplicated(objective,definition,expected):
    r=literal_requirements(objective,definition)
    assert r['terms']==expected and r['necessary_only'] and not r['semantic_truth_verified']

@pytest.mark.parametrize('text,missing',[
    ('Rated 90 points.',False),('Rated 190 points.',True),('Rated 90.0 points.',True),
    ('Rated ninety points.',True),('No 90-point rating is claimed.',False),
    ("A customer asks '90 points?'",False)])
def test_presence_is_only_a_literal_constraint_not_semantic_support(text,missing):
    w=source_witnesses(literal_requirements('Exactly 90 points','Score exactly 90'),{'caption':text})
    assert bool(w['missing']) is missing
