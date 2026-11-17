import test from 'node:test';
import assert from 'node:assert/strict';
import {createApiClient} from '../src/personalApi.js';

const ORIGIN='http://127.0.0.1:8000';
const response=(ok=true,data={ok:true})=>({ok,json:async()=>data});

test('personal client sends requests directly with browser safeguards and no credential header',async()=>{
  const calls=[];const c=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async(url,options)=>{calls.push({url,options});return response();}});
  await c.request('reset',{user_id:1},'POST','synthetic-session');
  await c.request('status');
  assert.equal(calls.length,2);
  for(const {options} of calls){
    assert.deepEqual(Object.keys(options.headers).filter(k=>k!=='Content-Type'&&k!=='X-Session-ID'),[]);
    assert.equal(options.redirect,'error');assert.equal(options.cache,'no-store');
    assert.equal(options.credentials,'omit');assert.equal(options.referrerPolicy,'no-referrer');
  }
  assert.equal(calls[0].url,'/api/reset');assert.equal(calls[0].options.method,'POST');
  assert.equal(calls[0].options.body,JSON.stringify({user_id:1}));
  assert.equal(calls[0].options.headers['X-Session-ID'],'synthetic-session');
  assert.equal(calls[1].url,'/api/status');assert.equal(calls[1].options.method,'GET');
  assert.equal(Object.hasOwn(calls[1].options,'body'),false);
});
test('client exposes no unlock or lock step',()=>{
  const c=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async()=>response()});
  assert.deepEqual(Object.keys(c),['request']);
});
test('normal app has no personal safeguards',async()=>{
  let options;const c=createApiClient({personal:false,origin:ORIGIN,fetchImpl:async(_,o)=>{options=o;return response();}});
  await c.request('status');
  for(const key of ['redirect','credentials','cache','referrerPolicy']) assert.equal(Object.hasOwn(options,key),false);
});
test('refuses traversal outside API path before fetch',async()=>{
  for(const personal of [true,false]){
    let calls=0;const c=createApiClient({personal,origin:ORIGIN,fetchImpl:async()=>{calls++;return response();}});
    await assert.rejects(c.request('../secret'),/Invalid API target/);assert.equal(calls,0);
  }
});
