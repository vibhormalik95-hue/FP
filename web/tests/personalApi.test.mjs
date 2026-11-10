import test from 'node:test';
import assert from 'node:assert/strict';
import {createApiClient} from '../src/personalApi.js';

const ORIGIN='http://127.0.0.1:8000', TOKEN='synthetic-only-token-0123456789abcd';
const response=(ok=true,data={ok:true})=>({ok,json:async()=>data});

test('locked personal client does not send an API request',async()=>{
  let calls=0; const c=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async()=>{calls++;return response();}});
  await assert.rejects(c.request('status'),/Unlock/);assert.equal(calls,0);
});
test('unlock, normal reset and API use token only as a header',async()=>{
  const calls=[];const c=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async(url,options)=>{calls.push({url,options});return response();}});
  assert.equal(await c.unlock(TOKEN),true);
  await c.request('reset',{user_id:1},'POST','synthetic-session');
  await c.request('status');
  assert.equal(calls.length,3);
  for(const {url,options} of calls){
    assert.ok(!url.includes(TOKEN));assert.ok(!(options.body||'').includes(TOKEN));
    assert.equal(options.headers['X-Personal-Operator-Token'],TOKEN);
    assert.equal(options.redirect,'error');assert.equal(options.cache,'no-store');
    assert.equal(options.credentials,'omit');assert.equal(options.referrerPolicy,'no-referrer');
  }
  assert.equal(calls[1].options.headers['X-Session-ID'],'synthetic-session');
});
test('failed unlock and a fresh page both remain locked',async()=>{
  let calls=0;const bad=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async()=>{calls++;return response(false);}});
  assert.equal(await bad.unlock(TOKEN),false);await assert.rejects(bad.request('status'),/Unlock/);assert.equal(calls,1);
  const refreshed=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async()=>response()});
  await assert.rejects(refreshed.request('status'),/Unlock/);
});
test('lock aborts an in-flight request and blocks later requests',async()=>{
  let activeSignal;let pendingResolve;let calls=0;
  const c=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async(url,options)=>{
    calls++;if(calls===1)return response();activeSignal=options.signal;
    return new Promise(resolve=>{pendingResolve=resolve;});
  }});
  assert.equal(await c.unlock(TOKEN),true);const pending=c.request('status');
  c.lock();assert.equal(activeSignal.aborted,true);pendingResolve(response());
  await assert.rejects(pending,/locked/);await assert.rejects(c.request('status'),/Unlock/);assert.equal(calls,2);
});
test('lock invalidates a delayed unlock',async()=>{
  let resolve;let signal;const c=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async(_,options)=>{
    signal=options.signal;return new Promise(r=>{resolve=r;});}});
  const pending=c.unlock(TOKEN);c.lock();assert.equal(signal.aborted,true);resolve(response());
  assert.equal(await pending,false);await assert.rejects(c.request('status'),/Unlock/);
});
test('response body completing after lock cannot restore data',async()=>{
  let resolveBody;let calls=0;const c=createApiClient({personal:true,origin:ORIGIN,fetchImpl:async()=>{
    calls++;if(calls===1)return response();return {ok:true,json:()=>new Promise(r=>{resolveBody=r;})};}});
  assert.equal(await c.unlock(TOKEN),true);const pending=c.request('status');await Promise.resolve();await Promise.resolve();
  c.lock();resolveBody({secret:'synthetic'});await assert.rejects(pending,/locked/);
});
test('normal app has no token gate or personal header',async()=>{
  let options;const c=createApiClient({personal:false,origin:ORIGIN,fetchImpl:async(_,o)=>{options=o;return response();}});
  await c.request('status');assert.equal(options.headers['X-Personal-Operator-Token'],undefined);
  for(const key of ['redirect','credentials','cache','referrerPolicy']) assert.equal(Object.hasOwn(options,key),false);
});
test('refuses traversal outside API path before fetch',async()=>{
  let calls=0;const c=createApiClient({personal:false,origin:ORIGIN,fetchImpl:async()=>{calls++;return response();}});
  await assert.rejects(c.request('../secret'),/Invalid API target/);assert.equal(calls,0);
});
