"""Served development audit of reviewed dialogue; not a human/held-out study."""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feedctrl.controls import _local_endpoint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url');parser.add_argument('output',type=Path)
    parser.add_argument('--profile-only',action='store_true',help='Audit fresh replacement planning after an existing multi-topic profile')
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Preserve the old receipt; choose a new output path')
    base=_local_endpoint(args.base_url)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(path,body=None,h=None):
        req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type':'application/json',**(h or {})})
        try:
            with opener.open(req,timeout=115) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    _,session=call('/api/session',{});h={'X-Session-ID':session['session_id']}
    _,clean_ae=call('/api/compare?user_id=14',h=h)
    call('/api/feedback',{'user_id':14,'item_id':1116,'direction':'like'},h)
    call('/api/control',{'user_id':14,'text':'Show me more category_1','backend':'rule'},h)
    # Keep a real nonempty original A-E state fixed throughout the new workflow.
    _,fixed_ae=call('/api/compare?user_id=14',h=h)
    _,status=call('/api/status')
    record={'scope':'development cases, no human relevance or universal accuracy claim',
        'started_utc':datetime.now(timezone.utc).isoformat(),'status':status,'cases':[],'comparisons':{}}
    expected={
        'confirmed_english_light_qingdao':[('\u9752\u5c9b','boost','light')],
        'explicit_strong_qingdao':[('\u9752\u5c9b','boost','strong')],
        'context_change_direction':[('\u9752\u5c9b','reduce','light')],
        'hard_exclude':[('\u9752\u5c9b','exclude','none')],
        'cancel_exclusion':[('\u9752\u5c9b','remove','none')],
        'confirmed_english_travel':[('\u65c5\u6e38','boost','standard')],
        'equivalent_chinese_travel':[('\u65c5\u6e38','boost','standard')],
        'composed_instruction':[('\u9752\u5c9b','boost','strong'),('\u6e38\u620f','reduce','light')],
        'editable_profile':[('\u9752\u5c9b','boost','light'),('\u6e38\u620f','exclude','none')],
        'valid_only_a_little':[('\u9752\u5c9b','boost','light')]}
    def compact(r):
        out={k:r[k] for k in ('ready','applied','question','clarification','can_undo','focus','detail') if k in r}
        if 'commands'in r:out['commands']=[{k:c[k] for k in ('topic','requested_topic','operation','strength','adjustment','aliases','grounding_method','context_reference','source') if k in c}for c in r['commands']]
        feed=r.get('preview',r.get('feed'))
        if feed:out['feed']={'items':[{'item_id':x['item_id'],'score':x.get('score')}for x in feed['items']],
            **{k:feed[k] for k in ('fill_rate','available_items','topic_exposure')}}
        if 'interpretation'in r:out['interpretation']={k:r['interpretation'][k] for k in ('history_action','provenance') if k in r['interpretation']}
        if 'interpretation'in r:out['interpreted_commands']=[{k:c[k] for k in ('topic','operation','strength')} for c in r['interpretation'].get('commands',[])]
        return out
    def save():args.output.write_text(json.dumps(record,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    def run(name,path,body=None,check=True):
        start=time.monotonic();code,r=call(path,body,h)
        _,after=call('/api/compare?user_id=14',h=h)
        item={'name':name,'status_code':code,'seconds':round(time.monotonic()-start,3),
            'request':{k:v for k,v in (body or {}).items() if k!='plan_id'},'response':compact(r)}
        if check:item['fixed_ae_unchanged']=after==fixed_ae
        record['cases'].append(item);save()
        print(json.dumps({'name':name,'status':code,'ready':r.get('ready'),'applied':r.get('applied'),
            'question':r.get('question'),'fixed_ae_unchanged':item.get('fixed_ae_unchanged')},ensure_ascii=True),flush=True)
        return r
    def review(name,text,apply=False,mode='merge',bindings=None):
        _,before=call('/api/steering?user_id=14',h=h)
        body={'user_id':14,'text':text,'mode':mode,'bindings':bindings or []}
        r=run(name,'/api/steering/preview',body)
        _,after=call('/api/steering?user_id=14',h=h)
        item=record['cases'][-1]
        item['review_did_not_change_active_profile']=before==after
        valid=True
        if name in expected:
            actual=sorted((c['topic'],c['operation'],c['strength']) for c in r.get('interpretation',{}).get('commands',[]))
            valid=r.get('ready') is True and actual==sorted(expected[name])
            item['expected_commands']=expected[name];item['interpretation_matches_expected']=valid
        if name=='context_stronger':
            actual=[(c['topic'],c['operation'],c['strength']) for c in r.get('interpretation',{}).get('commands',[])]
            valid=r.get('ready') is True and actual in [[('\u9752\u5c9b','boost','standard')],[('\u9752\u5c9b','boost','strong')]]
            item['expected_relative_strength']='Higher than light, preserving boost and scope'
            item['interpretation_matches_expected']=valid
        if name=='ambiguous_reference':item['expected_clarification_received']=not r.get('ready')
        save()
        if apply and r.get('ready') and valid:
            return run(name+'_apply','/api/steering/apply',{'user_id':14,'plan_id':r['plan_id']})
        return r
    def manual(name,actions):
        return run(name,'/api/steering/preview',{'user_id':14,'backend':'manual','mode':'replace','actions':actions})
    def command(topic,op='boost',strength='light'):return {'topic':topic,'operation':op,'strength':strength}
    def same_feed(a,b):return isinstance(a,dict) and isinstance(b,dict) and a==b
    if args.profile_only:
        setup=manual('manual_prior_profile',[command('\u9752\u5c9b','boost','strong'),
            command('\u6e38\u620f','reduce','light'),command('\u65c5\u6e38','boost','standard')])
        prior=run('manual_prior_profile_apply','/api/steering/apply',{'user_id':14,'plan_id':setup['plan_id']})
        oracle=manual('manual_replacement_oracle',[command('\u9752\u5c9b'),command('\u6e38\u620f','exclude','none')])
        chosen=[{'requested_topic':'Qingdao','source_topic':'\u9752\u5c9b'},{'requested_topic':'gaming','source_topic':'\u6e38\u620f'}]
        result=review('editable_profile','A little more Qingdao. Hide gaming completely.',True,'replace',chosen)
        record['comparisons']['replacement_equals_manual']=same_feed(result.get('feed'),oracle.get('preview'))
        undone=review('undo_replacement','Undo the last change.',True)
        record['comparisons']['undo_restores_prior_profile_feed']=same_feed(undone.get('feed'),prior.get('feed'))
        run('global_reset','/api/reset',{'user_id':14},False)
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save()
        print(json.dumps(record['comparisons']),flush=True)
        return
    oracle=manual('manual_light_qingdao',[command('\u9752\u5c9b')])
    review('unconfirmed_english_light_qingdao','A little more Qingdao.')
    # A scope selection is an explicit manual input, not model-derived intent.
    first=review('confirmed_english_light_qingdao','A little more Qingdao.',True,
                 bindings=[{'requested_topic':'Qingdao','source_topic':'\u9752\u5c9b'}])
    record['comparisons']['manual_light_equals_english']=same_feed(oracle.get('preview'),first.get('feed'))
    review('context_stronger','Make that stronger.',True)
    strong=review('explicit_strong_qingdao','A lot more Qingdao.',True)
    weaker=review('context_change_direction','A little less of that.',True)
    undone=review('natural_language_undo','Undo the last change.',True)
    record['comparisons']['undo_restores_strong_feed']=same_feed(strong.get('feed'),undone.get('feed'))
    review('hard_exclude','Hide Qingdao completely.',True)
    review('cancel_exclusion','Do not hide Qingdao anymore.',True)
    review('travel_scope_before_confirmation','More travel.')
    bindings=[{'requested_topic':'travel','source_topic':'\u65c5\u6e38'}]
    oracle_travel=manual('manual_confirmed_travel',[command('\u65c5\u6e38','boost','standard')])
    english=review('confirmed_english_travel','More travel.',True,'replace',bindings)
    chinese=review('equivalent_chinese_travel','\u591a\u63a8\u8350\u4e00\u4e9b\u65c5\u6e38\u89c6\u9891\u3002',False,'replace')
    record['comparisons']['confirmed_english_equals_manual']=same_feed(english.get('feed'),oracle_travel.get('preview'))
    record['comparisons']['confirmed_english_equals_chinese']=same_feed(english.get('feed'),chinese.get('preview'))
    chosen=[{'requested_topic':'Qingdao','source_topic':'\u9752\u5c9b'},
            {'requested_topic':'gaming','source_topic':'\u6e38\u620f'}]
    review('composed_instruction','A lot more Qingdao and slightly less gaming.',True,bindings=chosen)
    review('ambiguous_reference','Make that stronger.')
    review('editable_profile','A little more Qingdao. Hide gaming completely.',True,'replace',chosen)
    review('unknown_subject','More flarbblargoplanets.')
    review('unsupported_quota','Exactly three gaming videos unless I watched them.')
    review('valid_only_a_little','Only a little more Qingdao.',False)
    review('clear_topic_profile','Clear my topic profile.',True)
    review('undo_clearing','Undo the last change.',True)
    _,other=call('/api/session',{});_,isolated=call('/api/steering?user_id=14',h={'X-Session-ID':other['session_id']})
    record['comparisons']['other_session_empty']=isolated.get('commands')==[]
    _,other_user=call('/api/steering?user_id=19',h=h)
    record['comparisons']['other_user_empty']=other_user.get('commands')==[]
    run('global_reset','/api/reset',{'user_id':14},False)
    _,final_ae=call('/api/compare?user_id=14',h=h);_,final=call('/api/steering?user_id=14',h=h)
    record['comparisons']['global_reset_restores_clean_ae']=final_ae==clean_ae
    record['comparisons']['global_reset_clears_profile_and_history']=not final['commands'] and not final['can_undo']
    record['finished_utc']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps(record['comparisons']),flush=True)


if __name__=='__main__':main()
