"""Joint action-choice contracts. Offline doubles are not semantic accuracy."""
from copy import deepcopy
import pytest
from feedctrl import semantic_review as sr
from test_semantic_review import client,headers,preview,saved,fake_model

@pytest.mark.parametrize('choice',[
    'boost/light','boost/standard','boost/strong',
    'reduce/light','reduce/standard','reduce/strong','exclude/none'])
def test_each_declared_choice_decodes_exactly_without_mutation(choice):
    raw={'needs_clarification':False,'question':'','control':choice,'intent_span':'food'}
    before=deepcopy(raw)
    action,question=sr.interpret_action('Control food',lambda *a:raw)
    operation,strength=choice.split('/')
    assert action=={'operation':operation,'strength':strength,'intent_span':'food'}
    assert not question and raw==before

def test_schema_contains_only_seven_compatible_enum_choices():
    choices=sr.ACTION_SCHEMA['properties']['control']['enum']
    assert len(choices)==len(set(choices))==7
    assert set(choices)=={'boost/light','boost/standard','boost/strong',
        'reduce/light','reduce/standard','reduce/strong','exclude/none'}
    assert not {'operation','strength'} & sr.ACTION_SCHEMA['properties'].keys()
    assert sr.ACTION_SCHEMA['additionalProperties'] is False

@pytest.mark.parametrize('bad',['exclude/light','exclude/standard','exclude/strong',
    'boost/none','reduce/none','exclude','exclude/none ','EXCLUDE/none',None,True,[],{}])
def test_invalid_choices_are_rejected_not_repaired(bad):
    with pytest.raises(ValueError):sr.interpret_action('Hide food',lambda *a:{
        'needs_clarification':False,'question':'','control':bad,'intent_span':'food'})

def test_legacy_invalid_pair_is_not_silently_accepted(client,monkeypatch):
    raw={'needs_clarification':False,'question':'','operation':'exclude','strength':'strong','intent_span':'food'}
    monkeypatch.setattr(sr,'make_local_ollama_infer',lambda *a,**k:(lambda *a:deepcopy(raw),{'backend':'test-double','model':'fixture','digest':'fixture'}))
    h=headers(client);before=saved(client,h).json();result=preview(client,h).json()
    assert result['status']=='error' and not result['ready'] and not result['applied']
    assert result['model_calls'][0]['raw_response']==raw
    assert saved(client,h).json()==before

def test_valid_clarification_remains_nonexecuting():
    action,question=sr.interpret_action('Which one?',lambda *a:{'needs_clarification':True,
        'question':'Name the subject.','control':'boost/standard','intent_span':''})
    assert action is None and question=='Name the subject.'

def test_invalid_choice_is_not_ignored_even_in_clarification():
    with pytest.raises(ValueError):sr.interpret_action('Which one?',lambda *a:{
        'needs_clarification':True,'question':'Name the subject.','control':'exclude/strong','intent_span':''})

@pytest.mark.parametrize('operation,strength,delta',[
    ('boost','light',.10),('boost','standard',.25),('boost','strong',.40),
    ('reduce','light',-.10),('reduce','standard',-.25),('reduce','strong',-.40)])
def test_parsed_choice_preserves_graded_policy_and_eligibility(client,monkeypatch,operation,strength,delta):
    fake_model(monkeypatch,operation=operation,strength=strength)
    h=headers(client);proposal=preview(client,h).json()
    assert proposal['ready'] and proposal['proposal']['action']['operation']==operation
    assert proposal['proposal']['action']['strength']==strength
    demo=client.app.state.demo;ids=sorted(demo.items)
    result=sr.rank_groups(ids,[0.0]*len(ids),proposal['groups'],demo.topic_index,
        limit=len(ids),original_categories=demo.items)
    scores={r['item_id']:r['score'] for r in result['items']}
    assert result['available_items']==len(ids) and set(scores)==set(ids)
    assert scores[3]==pytest.approx(delta)
    assert all(score==0 for item,score in scores.items() if item!=3)

def test_clarification_rejects_nonstring_placeholder_span():
    with pytest.raises(ValueError):sr.interpret_action('Which one?',lambda *a:{
        'needs_clarification':True,'question':'Name the subject.','control':'boost/standard','intent_span':[]})
