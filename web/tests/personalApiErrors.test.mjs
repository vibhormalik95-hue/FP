// Authored responses only. Node's Response parses bytes; fetch never accesses a network.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createApiClient} from '../src/personalApi.js';

const ORIGIN = 'http://127.0.0.1:8000';
const TOKEN = 'synthetic-only-token-0123456789abcd';
const FALLBACK = 'Check the input and try again.';

async function clientFor(errorResponse, personal=true) {
  const calls = [];
  const client = createApiClient({personal, origin:ORIGIN, fetchImpl:async (url, options)=>{
    calls.push({url, options});
    if (personal && calls.length === 1) return new Response('{}');
    return errorResponse;
  }});
  if (personal) assert.equal(await client.unlock(TOKEN), true);
  return {client, calls};
}

test('plain-text, HTML, empty and malformed JSON HTTP errors use the safe existing fallback', async t=>{
  for (const personal of [true, false]) {
    for (const [status, contentType, body] of [
      [403, 'text/plain', 'Personal operator token required'],
      [502, 'text/html', `<html>upstream body ${TOKEN}</html>`],
      [503, 'text/plain', ''],
      [422, 'application/json', `{"untrusted":"${TOKEN}`],
    ]) {
      await t.test(`${personal ? 'personal' : 'normal'} ${status} ${contentType}`, async ()=>{
        const {client, calls} = await clientFor(new Response(body, {status, headers:{'Content-Type':contentType}}), personal);
        await assert.rejects(client.request('status'), error=>{
          assert.equal(error.message, FALLBACK);
          assert.ok(!(error instanceof SyntaxError));
          assert.ok(!error.message.includes(TOKEN));
          return true;
        });
        assert.equal(calls.length, personal ? 2 : 1);
        for (const {url, options} of calls) {
          assert.ok(!url.includes(TOKEN));
          assert.ok(!(options.body || '').includes(TOKEN));
        }
      });
    }
  }
});

test('JSON HTTP errors retain a string detail and safely handle absent or non-string details', async t=>{
  for (const [payload, expected] of [
    [{detail:'Authored validation failure'}, 'Authored validation failure'],
    [{detail:''}, ''], [{detail:[{msg:'invalid'}]}, FALLBACK], [{}, FALLBACK],
    [null, FALLBACK], ['untrusted string', FALLBACK], [[], FALLBACK],
  ]) {
    await t.test(JSON.stringify(payload), async ()=>{
      const {client} = await clientFor(new Response(JSON.stringify(payload), {status:422}));
      await assert.rejects(client.request('status'), error=>error.message === expected);
    });
  }
});

test('successful JSON payloads keep their exact existing shape', async t=>{
  for (const payload of [{ok:true, nested:{values:[1, false]}}, null, ['authored'], 'authored']) {
    await t.test(JSON.stringify(payload), async ()=>{
      const {client} = await clientFor(new Response(JSON.stringify(payload)));
      assert.deepEqual(await client.request('status'), payload);
    });
  }
});

test('a malformed successful JSON response still rejects rather than becoming success', async ()=>{
  const {client} = await clientFor(new Response('not JSON'));
  await assert.rejects(client.request('status'), SyntaxError);
});

test('lock wins over a delayed body parse failure for HTTP errors and successful statuses', async t=>{
  for (const ok of [false, true]) {
    await t.test(`ok=${ok}`, async ()=>{
      let rejectBody;
      let bodyStarted;
      const started = new Promise(resolve=>{bodyStarted=resolve;});
      const response = {ok, json:()=>new Promise((_, reject)=>{rejectBody=reject;bodyStarted();})};
      const {client, calls} = await clientFor(response);
      const pending = client.request('status');
      await started;
      client.lock();
      rejectBody(new SyntaxError(`Authored parser error containing ${TOKEN}`));
      await assert.rejects(pending, error=>error.message === 'Personal session is locked.');
      await assert.rejects(client.request('status'), /Unlock/);
      assert.equal(calls.length, 2);
    });
  }
});

test('a newer unlock also invalidates a delayed non-JSON error from the old generation', async ()=>{
  let rejectBody;
  let bodyStarted;
  const started = new Promise(resolve=>{bodyStarted=resolve;});
  let calls = 0;
  const client = createApiClient({personal:true, origin:ORIGIN, fetchImpl:async ()=>{
    calls++;
    if (calls === 2) return {ok:false, json:()=>new Promise((_, reject)=>{rejectBody=reject;bodyStarted();})};
    return new Response('{}');
  }});
  assert.equal(await client.unlock(TOKEN), true);
  const pending = client.request('status');
  await started;
  assert.equal(await client.unlock('new-synthetic-only-token-0123456789abcd'), true);
  rejectBody(new SyntaxError('authored incomplete JSON'));
  await assert.rejects(pending, error=>error.message === 'Personal session is locked.');
  assert.deepEqual(await client.request('status'), {});
  assert.equal(calls, 4);
});
