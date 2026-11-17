// Authored responses only. Node's Response parses bytes; fetch never accesses a network.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createApiClient} from '../src/personalApi.js';

const ORIGIN = 'http://127.0.0.1:8000';
const MARKER = 'untrusted-body-marker-0123456789abcd';
const FALLBACK = 'Check the input and try again.';

function clientFor(errorResponse, personal=true) {
  const calls = [];
  const client = createApiClient({personal, origin:ORIGIN, fetchImpl:async (url, options)=>{
    calls.push({url, options});
    return errorResponse;
  }});
  return {client, calls};
}

test('plain-text, HTML, empty and malformed JSON HTTP errors use the safe existing fallback', async t=>{
  for (const personal of [true, false]) {
    for (const [status, contentType, body] of [
      [403, 'text/plain', 'Personal loopback access required'],
      [502, 'text/html', `<html>upstream body ${MARKER}</html>`],
      [503, 'text/plain', ''],
      [422, 'application/json', `{"untrusted":"${MARKER}`],
    ]) {
      await t.test(`${personal ? 'personal' : 'normal'} ${status} ${contentType}`, async ()=>{
        const {client, calls} = clientFor(new Response(body, {status, headers:{'Content-Type':contentType}}), personal);
        await assert.rejects(client.request('status'), error=>{
          assert.equal(error.message, FALLBACK);
          assert.ok(!(error instanceof SyntaxError));
          assert.ok(!error.message.includes(MARKER));
          return true;
        });
        assert.equal(calls.length, 1);
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
      const {client} = clientFor(new Response(JSON.stringify(payload), {status:422}));
      await assert.rejects(client.request('status'), error=>error.message === expected);
    });
  }
});

test('a structured error payload is kept on the error with its status', async ()=>{
  const {client} = clientFor(new Response(JSON.stringify({detail:'Provider failed', result:{ok:false}}), {status:502}));
  await assert.rejects(client.request('status'), error=>{
    assert.equal(error.status, 502);
    assert.deepEqual(error.payload, {detail:'Provider failed', result:{ok:false}});
    return true;
  });
});

test('successful JSON payloads keep their exact existing shape', async t=>{
  for (const payload of [{ok:true, nested:{values:[1, false]}}, null, ['authored'], 'authored']) {
    await t.test(JSON.stringify(payload), async ()=>{
      const {client} = clientFor(new Response(JSON.stringify(payload)));
      assert.deepEqual(await client.request('status'), payload);
    });
  }
});

test('a malformed successful JSON response still rejects rather than becoming success', async ()=>{
  const {client} = clientFor(new Response('not JSON'));
  await assert.rejects(client.request('status'), SyntaxError);
});
