"""Compositional controls, atomic review/apply, and isolation from frozen A-E."""
import csv
import json

import pytest
from fastapi.testclient import TestClient

from feedctrl.api import create_app
from feedctrl import semantic_workflow as wf
from feedctrl.semantic_controls import TEXT_FIELDS, TopicGroundingError


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "topics.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["video_id", *TEXT_FIELDS])
        writer.writeheader()
        for i in range(1, 37):
            writer.writerow({"video_id": i, "caption": "\u4eac\u90fd" if i in (1, 2)
                else "\u7f8e\u98df" if i in (3, 4) else "\u6e38\u620f" if i in (5, 6) else "\u8dd1\u6b65"})
    with TestClient(create_app(fixture=True, semantic_path=path)) as value:
        yield value


def headers(client):
    return {"X-Session-ID": client.post("/api/session", json={}).json()["session_id"]}


def control(topic="\u4eac\u90fd", operation="boost", strength="strong"):
    return {"topic": topic, "operation": operation, "strength": strength}


def preview(client, h, actions, mode="merge", user=1):
    return client.post("/api/steering/preview", headers=h,
        json={"user_id": user, "backend": "manual", "mode": mode, "actions": actions})


def apply(client, h, plan, user=1):
    return client.post("/api/steering/apply", headers=h, json={"user_id": user, "plan_id": plan["plan_id"]})


def test_review_is_atomic_and_manual_composition_does_not_modify_ae(client):
    h = headers(client)
    before = client.get("/api/compare?user_id=1", headers=h).json()
    actions = [control(), control("\u6e38\u620f", "reduce", "light"), control("\u7f8e\u98df", "exclude", "none")]
    proposal = preview(client, h, actions).json()
    assert proposal["ready"] and proposal["applied"] is False
    assert client.get("/api/steering?user_id=1", headers=h).json()["commands"] == []
    assert proposal["preview"]["available_items"] == 34
    assert len(proposal["preview"]["topic_exposure"]) == 3
    result = apply(client, h, proposal).json()
    assert result["applied"] and len(result["commands"]) == 3
    assert not {3, 4} & {item["item_id"] for item in result["feed"]["items"]}
    assert result["feed"]["fill_rate"] == 1
    assert client.get("/api/compare?user_id=1", headers=h).json() == before


def test_replace_profile_remove_reset_and_stale_review(client):
    h = headers(client)
    first = preview(client, h, [control()]).json()
    assert apply(client, h, first).status_code == 200
    second = preview(client, h, [control("\u7f8e\u98df")], "replace").json()
    assert apply(client, h, second).json()["commands"][0]["topic"] == "\u7f8e\u98df"
    assert len(client.get("/api/steering?user_id=1", headers=h).json()["commands"]) == 1
    pending = preview(client, h, [control()]).json()
    removed = client.post("/api/steering/remove", headers=h, json={"user_id": 1, "topic": "\u7f8e\u98df"})
    assert removed.json()["commands"] == []
    assert apply(client, h, pending).status_code == 409
    pending = preview(client, h, [control()]).json()
    assert client.post("/api/reset", headers=h, json={"user_id": 1}).status_code == 200
    assert apply(client, h, pending).status_code == 409
    assert client.get("/api/steering?user_id=1", headers=h).json()["commands"] == []


def test_conflicting_and_partly_ungrounded_plans_never_partially_apply(client):
    h = headers(client)
    conflict = preview(client, h, [control(), control(operation="reduce", strength="light")]).json()
    assert conflict["ready"] is False and conflict["needs_clarification"]
    ungrounded = preview(client, h, [control(), control("unknown-subject")]).json()
    assert ungrounded["ready"] is False
    assert client.get("/api/steering?user_id=1", headers=h).json()["commands"] == []


def test_review_token_bound_to_user_session_and_time(client):
    h, other = headers(client), headers(client)
    plan = preview(client, h, [control()]).json()
    assert apply(client, other, plan).status_code == 409
    assert apply(client, h, plan, user=2).status_code == 409
    demo = client.app.state.demo
    state = demo.user_state(h["X-Session-ID"], 1)
    state["steering_pending"]["created"] -= 301
    assert apply(client, h, plan).status_code == 409


def test_model_stages_separate_ascii_plan_from_unconstrained_translation(client, monkeypatch):
    responses = iter([json.dumps({"needs_clarification": False, "question": "", "actions": [
        control("Kyoto"), control("gaming", "reduce", "light")]}), "\u4eac\u90fd", "\u6e38\u620f"])
    stages = []
    def chat(messages, model, timeout, schema=None):
        stages.append(schema)
        return next(responses)
    monkeypatch.setattr(wf, "_chat", chat)
    monkeypatch.setattr(wf, "ollama_provenance", lambda *args: {"digest": "test-digest"})
    index = client.app.state.demo.topic_index
    result = wf.interpret("Much more Kyoto and a little less gaming", index)
    assert stages[0] is wf.PLAN_SCHEMA and stages[1:] == [None, None]
    assert [c["topic"] for c in result["commands"]] == ["\u4eac\u90fd", "\u6e38\u620f"]
    assert [c["adjustment"] for c in result["commands"]] == [.4, -.1]
    assert all(c["candidate_matches"] == 2 and c["translated"] for c in result["commands"])


def test_model_ambiguity_and_operational_error_preserve_active_controls(client, monkeypatch):
    h = headers(client)
    assert apply(client, h, preview(client, h, [control()]).json()).status_code == 200
    before = client.get("/api/steering?user_id=1", headers=h).json()
    monkeypatch.setattr(wf, "interpret", lambda *a, **k: {"needs_clarification": True,
        "question": "Which subject should change?", "commands": []})
    r = client.post("/api/steering/preview", headers=h, json={"user_id": 1, "text": "Less of that"}).json()
    assert not r["ready"] and not r["applied"]
    def unavailable(*a, **k):
        raise wf.ParserOperationalError("Model unavailable")
    monkeypatch.setattr(wf, "interpret", unavailable)
    assert client.post("/api/steering/preview", headers=h,
        json={"user_id": 1, "text": "More cooking"}).status_code == 502
    assert client.get("/api/steering?user_id=1", headers=h).json() == before


def test_explicit_clause_guard_rejects_reversed_model_direction():
    with pytest.raises(TopicGroundingError, match="direction conflicts"):
        wf.check_explicit_direction("Much more guitar and slightly less jazz.", ["jazz"], "boost")
    wf.check_explicit_direction("Much more guitar and slightly less jazz.", ["jazz"], "reduce")
    wf.check_explicit_direction("Do not hide jazz anymore.", ["jazz"], "remove")
    with pytest.raises(TopicGroundingError):
        wf.check_explicit_direction("Do not hide jazz anymore.", ["jazz"], "exclude")


def test_manual_and_model_with_same_grounded_intent_have_equal_rankings(client, monkeypatch):
    h = headers(client)
    actions = [control(), control("\u6e38\u620f", "exclude", "none")]
    manual = preview(client, h, actions).json()
    commands = wf.ground_actions(actions, client.app.state.demo.topic_index, "ollama:test")
    monkeypatch.setattr(wf, "interpret", lambda *a, **k: {
        "needs_clarification": False, "question": "", "commands": commands})
    llm = client.post("/api/steering/preview", headers=h,
        json={"user_id": 1, "text": "Much more Kyoto, no gaming"}).json()
    assert llm["preview"] == manual["preview"]
    assert apply(client, h, manual).status_code == 409  # a newer review supersedes it
    assert apply(client, h, llm).status_code == 200


def test_translation_does_not_use_generic_words_or_change_chinese_subject(client):
    index = client.app.state.demo.topic_index
    with pytest.raises(TopicGroundingError):
        wf.ground_actions([control("food")], index, "ollama:test", lambda text: "\u89c6\u9891")
    with pytest.raises(TopicGroundingError, match="Chinese request"):
        wf.ground_actions([control("Kyoto")], index, "ollama:test", lambda text: "\u4eac\u90fd",
                          original_text="\u591a\u4e00\u70b9\u7f8e\u98df")


def test_overlap_exclusion_wins_and_strength_moves_an_eligible_item():
    index = {"candidate_items": 6, "items": {i: {"fields": {}, "search_text":
        "alpha beta" if i == 5 else "beta" if i == 1 else "other"} for i in range(1, 7)}}
    alpha = wf.ground_actions([control("alpha")], index, "manual")
    ids, scores = list(range(1, 7)), [.9, .8, .7, .6, .5, .4]
    neutral = wf.rank(ids, scores, [], index)
    boosted = wf.rank(ids, scores, alpha, index)
    assert [x["item_id"] for x in boosted["items"]].index(5) < [x["item_id"] for x in neutral["items"]].index(5)
    beta = wf.ground_actions([control("beta", "exclude", "none")], index, "manual")
    assert not {1, 5} & {x["item_id"] for x in wf.rank(ids, scores, alpha + beta, index)["items"]}


def test_translated_compound_cannot_silently_shorten_to_a_parent_label(client):
    index = client.app.state.demo.topic_index
    index["items"][5]["fields"]["first_level_category_name"] = "\u6e38\u620f"
    with pytest.raises(wf.GroundingClarification):
        wf.ground_actions([control("gaming", "reduce", "light")], index, "ollama:test",
                          translator=lambda text: "\u7535\u5b50\u6e38\u620f")


def test_model_catalogue_choice_needs_explicit_source_confirmation(client, monkeypatch):
    index = client.app.state.demo.topic_index
    index["items"][3]["fields"]["second_level_category_name"] = "\u7f8e\u98df"
    responses = iter([json.dumps({"needs_clarification": False, "question": "",
        "actions": [control("cooking")]}), "unmatched-translation", "\u7f8e\u98df", "NO"])
    monkeypatch.setattr(wf, "ollama_provenance", lambda *args: {"digest": "test"})
    monkeypatch.setattr(wf, "_chat", lambda *args: next(responses))
    with pytest.raises(wf.GroundingClarification, match="may change scope"):
        wf.interpret("Much more cooking", index)


def test_unsupported_quotas_clarify_before_inference(client, monkeypatch):
    def never(*args):
        raise AssertionError("Unsupported quota should not start a model")
    monkeypatch.setattr(wf, "ollama_provenance", never)
    result = wf.interpret("Exactly three gaming clips unless I watched them", client.app.state.demo.topic_index)
    assert result["needs_clarification"] and result["commands"] == []


def test_model_cannot_replace_named_english_subject_with_unrelated_topic(client, monkeypatch):
    monkeypatch.setattr(wf, "ollama_provenance", lambda *args: {"digest": "test"})
    monkeypatch.setattr(wf, "_chat", lambda *args: json.dumps({"needs_clarification": False,
        "question": "", "actions": [control("travel")]}))
    with pytest.raises(TopicGroundingError, match="not in the English request"):
        wf.interpret("More cooking", client.app.state.demo.topic_index)


def test_reviewed_undo_restores_exact_profile_and_source_aliases(client):
    h=headers(client)
    original=apply(client,h,preview(client,h,[control()]).json()).json()
    second=apply(client,h,preview(client,h,[control(operation="reduce",strength="light")]).json()).json()
    assert second["commands"][0]["operation"]=="reduce"
    undo=client.post('/api/steering/history/preview',headers=h,json={"user_id":1,"action":"undo"}).json()
    assert undo["ready"] and not undo["applied"]
    assert client.get('/api/steering?user_id=1',headers=h).json()["commands"]==second["commands"]
    restored=apply(client,h,undo).json()
    assert restored["commands"]==original["commands"] and restored["feed"]==original["feed"]
    assert restored["focus"]==original["focus"]


def test_single_focus_followup_reuses_grounding_and_ambiguous_focus_is_rejected(client,monkeypatch):
    index=client.app.state.demo.topic_index
    saved=wf.ground_actions([control()],index,'manual')
    saved[0]['aliases'].append('Kyoto')
    monkeypatch.setattr(wf,'ollama_provenance',lambda *args:{'digest':'test'})
    def chat(*args):
        return json.dumps({'needs_clarification':False,'question':'','history_action':'none',
            'actions':[dict(control('Kyoto','reduce','light'),reference_id=0)]})
    monkeypatch.setattr(wf,'_chat',chat)
    result=wf.interpret('A little less of that.',index,context={'commands':saved,'focus':'\u4eac\u90fd'})
    assert result['commands'][0]['topic']=='\u4eac\u90fd'
    assert result['commands'][0]['context_reference']==0
    with pytest.raises(TopicGroundingError,match='no unique focus'):
        wf.interpret('A little less of that.',index,context={'commands':saved,'focus':None})


def test_confirmed_bilingual_scope_is_reused_without_retranslation(client,monkeypatch):
    index=client.app.state.demo.topic_index
    bindings=wf.confirmed_bindings([{'requested_topic':'Kyoto','source_topic':'\u4eac\u90fd'}],index)
    def never(subject):
        raise AssertionError('A confirmed scope must not drift through a new translation')
    commands=wf.ground_actions([control('Kyoto')],index,'ollama:test',translator=never,bindings=bindings)
    assert commands[0]['topic']=='\u4eac\u90fd' and 'kyoto' in commands[0]['aliases']
    chinese=wf.ground_actions([control('\u4eac\u90fd')],index,'ollama:test')
    ids=list(range(1,37));scores=list(range(36))
    assert wf.rank(ids,scores,commands,index)==wf.rank(ids,scores,chinese,index)


def test_removing_a_saved_control_is_not_exclusion_and_can_be_undone(client):
    h=headers(client)
    hidden=apply(client,h,preview(client,h,[control(operation='exclude',strength='none')]).json()).json()
    restored=apply(client,h,preview(client,h,[control(operation='remove',strength='none')]).json()).json()
    assert restored['commands']==[] and restored['feed']['available_items']==36
    undo=client.post('/api/steering/history/preview',headers=h,json={'user_id':1,'action':'undo'}).json()
    assert apply(client,h,undo).json()['feed']==hidden['feed']


def test_topic_clear_and_undo_preserve_nonempty_original_ae_state(client):
    h=headers(client)
    client.post('/api/feedback',headers=h,json={'user_id':1,'item_id':1,'direction':'like'})
    client.post('/api/control',headers=h,json={'user_id':1,'text':'Show me more category_1','backend':'rule'})
    client.put('/api/profile',headers=h,json={'user_id':1,'profile':{'category_2':-1}})
    before=client.get('/api/compare?user_id=1',headers=h).json()
    apply(client,h,preview(client,h,[control()]).json())
    cleared=client.post('/api/steering/history/preview',headers=h,json={'user_id':1,'action':'clear'}).json()
    assert apply(client,h,cleared).json()['commands']==[]
    undo=client.post('/api/steering/history/preview',headers=h,json={'user_id':1,'action':'undo'}).json()
    assert apply(client,h,undo).json()['commands']
    assert client.get('/api/compare?user_id=1',headers=h).json()==before


def test_confirmed_subject_name_resolves_wrong_model_index_and_relative_strength_is_bounded(client,monkeypatch):
    index=client.app.state.demo.topic_index
    saved=wf.ground_actions([control('Kyoto',strength='light'),control('gaming',strength='light')],index,
        'manual',bindings={'kyoto':'\u4eac\u90fd','gaming':'\u6e38\u620f'})
    monkeypatch.setattr(wf,'ollama_provenance',lambda *a:{'digest':'test'})
    plan={'needs_clarification':False,'question':'','actions':[
        {'topic':'Kyoto','operation':'boost','strength':'strong','reference_id':1}]}
    monkeypatch.setattr(wf,'_chat',lambda *a,**k:json.dumps(plan))
    result=wf.interpret('A lot more Kyoto.',index,context={'commands':saved,'focus':None})
    assert result['commands'][0]['topic']=='\u4eac\u90fd' and result['commands'][0]['context_reference']==0
    plan['actions'][0]={'topic':'Kyoto','operation':'boost','strength':'light','reference_id':0}
    with pytest.raises(TopicGroundingError,match='higher supported strength'):
        wf.interpret('Make that stronger.',index,context={'commands':saved,'focus':'\u4eac\u90fd'})


def test_replacement_language_plan_has_no_old_row_references_but_retains_confirmed_scope(client,monkeypatch):
    index=client.app.state.demo.topic_index
    saved=wf.ground_actions([control('\u4eac\u90fd')],index,'manual')
    monkeypatch.setattr(wf,'ollama_provenance',lambda *a:{'digest':'test'})
    def chat(messages,*a,**k):
        prompt=json.loads(messages[-1]['content'])
        assert prompt['saved_controls']==[] and prompt['focus_id'] is None
        assert prompt['confirmed_subject_bindings']['kyoto']=='\u4eac\u90fd'
        return json.dumps({'needs_clarification':False,'question':'','actions':[control('Kyoto',strength='light')]})
    monkeypatch.setattr(wf,'_chat',chat)
    result=wf.interpret('A little more Kyoto.',index,context={'commands':saved,'focus':'\u4eac\u90fd','mode':'replace'},
        bindings={'kyoto':'\u4eac\u90fd'})
    assert result['commands'][0]['topic']=='\u4eac\u90fd' and result['commands'][0]['adjustment']==.1


@pytest.mark.parametrize('model_topic',['Kyoto','\u4eac\u90fd'])
def test_confirmed_source_on_empty_profile_ignores_invented_model_row(client,monkeypatch,model_topic):
    # The UI replaces an English subject with its confirmed literal phrase.
    # Mock model interpretation only; this is not live inference evidence.
    h=headers(client)
    before=client.get('/api/compare?user_id=1',headers=h).json()
    oracle=preview(client,h,[control('\u4eac\u90fd',strength='strong')]).json()['preview']
    monkeypatch.setattr(wf,'ollama_provenance',lambda *a:{'digest':'unit-test-only'})
    plan={'needs_clarification':False,'question':'','history_action':'none','actions':[
        {'topic':model_topic,'operation':'boost','strength':'strong','reference_id':0}]}
    monkeypatch.setattr(wf,'_chat',lambda *a,**k:json.dumps(plan))
    proposal=client.post('/api/steering/preview',headers=h,json={
        'user_id':1,'text':'A lot more \u4eac\u90fd.','mode':'merge',
        'bindings':[{'requested_topic':'Kyoto','source_topic':'\u4eac\u90fd'}]}).json()
    assert proposal['ready'],proposal
    assert client.get('/api/steering?user_id=1',headers=h).json()['commands']==[]
    assert apply(client,h,proposal).json()['feed']==oracle
    assert client.get('/api/compare?user_id=1',headers=h).json()==before
