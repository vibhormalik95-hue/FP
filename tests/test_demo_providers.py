"""Scripted and relay providers: transport contracts only, no model and no network."""
import json
import threading
import time

import pytest

from feedctrl import demo_providers as dp
from feedctrl.controls import ParserOperationalError

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['answer'],
          'properties': {'answer': {'type': 'string'}}}
PAYLOAD = {'system': 'Answer the question.', 'question': 'synthetic'}


def relay(tmp_path, **options):
    spool = tmp_path / 'spool'
    spool.mkdir()
    settings = dict(declared_model='declared-model', transport_note='test double', max_calls=2,
                    timeout=3, poll=0.02, settle=0.4)
    settings.update(options)
    return spool, dp.relay_provider(spool, **settings)


def reply_later(spool, ordinal, writer, delay=0.1):
    def work():
        request = spool / f'request-{ordinal:04d}.json'
        while not request.exists():
            time.sleep(0.01)
        time.sleep(delay)
        writer(spool / f'response-{ordinal:04d}.json')
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return thread


def test_relay_round_trip_records_hashes_and_declared_identity(tmp_path):
    spool, (infer, identity, receipts) = relay(tmp_path)
    reply_later(spool, 1, lambda path: path.write_text('{"answer": "ok"}', encoding='utf-8'))
    assert infer(PAYLOAD, SCHEMA) == {'answer': 'ok'}
    request = json.loads((spool / 'request-0001.json').read_text(encoding='utf-8'))
    assert request['system'] == PAYLOAD['system'] and request['payload'] == {'question': 'synthetic'}
    assert request['schema'] == SCHEMA
    assert receipts[0]['outcome'] == 'parsed_transport_only' and len(receipts[0]['response_sha256']) == 64
    assert identity['backend'] == dp.RELAY_BACKEND and identity['live_model'] == 'operator_declared'
    assert 'cannot attest' in identity['identity_limit']
    assert json.loads((spool / 'receipt-0001.json').read_text())['outcome'] == 'parsed_transport_only'


def test_relay_waits_for_a_file_that_is_still_being_written(tmp_path):
    spool, (infer, _, receipts) = relay(tmp_path)

    def slow_writer(path):
        with open(path, 'w', encoding='utf-8') as handle:  # the name exists while the file is empty
            handle.flush()
            time.sleep(0.15)
            handle.write('{"answer":')
            handle.flush()
            time.sleep(0.15)
            handle.write(' "complete"}')
    reply_later(spool, 1, slow_writer)
    assert infer(PAYLOAD, SCHEMA) == {'answer': 'complete'}
    assert receipts[0]['outcome'] == 'parsed_transport_only'


def test_relay_accepts_a_byte_order_mark_but_no_text_around_the_object(tmp_path):
    spool, (infer, _, receipts) = relay(tmp_path)
    reply_later(spool, 1, lambda path: path.write_bytes(b'\xef\xbb\xbf{"answer": "bom"}'))
    assert infer(PAYLOAD, SCHEMA) == {'answer': 'bom'}
    reply_later(spool, 2, lambda path: path.write_text('```json\n{"answer": "fenced"}\n```', encoding='utf-8'))
    with pytest.raises(ParserOperationalError):
        infer(PAYLOAD, SCHEMA)
    assert [r['outcome'] for r in receipts] == ['parsed_transport_only', 'error']


@pytest.mark.parametrize('text', ['{"answer": 1}', '{"answer": "a", "extra": 1}', '{"answer": "a", "answer": "b"}',
                                  '{"answer": NaN}', '["answer"]', 'not json'])
def test_relay_rejects_invalid_replies_without_repair(tmp_path, text):
    spool, (infer, _, receipts) = relay(tmp_path)
    reply_later(spool, 1, lambda path: path.write_text(text, encoding='utf-8'))
    with pytest.raises(ParserOperationalError):
        infer(PAYLOAD, SCHEMA)
    assert receipts[0]['outcome'] == 'error'


def test_relay_refuses_a_reply_that_exists_before_its_request(tmp_path):
    spool = tmp_path / 'spool'
    spool.mkdir()
    infer, _, receipts = dp.relay_provider(spool, declared_model='m', transport_note='n', max_calls=2,
                                           timeout=1, poll=0.02, settle=0.1)
    (spool / 'response-0001.json').write_text('{"answer": "planted"}', encoding='utf-8')
    with pytest.raises(ParserOperationalError):
        infer(PAYLOAD, SCHEMA)
    assert receipts[0]['outcome'] == 'error' and not (spool / 'request-0001.json').exists()


def test_relay_times_out_and_never_exceeds_its_allowance(tmp_path):
    spool, (infer, _, receipts) = relay(tmp_path, max_calls=1, timeout=0.2, settle=0.05)
    with pytest.raises(ParserOperationalError):
        infer(PAYLOAD, SCHEMA)
    assert receipts[0]['error_type'] == 'TimeoutError'
    with pytest.raises(ParserOperationalError, match='allowance exhausted'):
        infer(PAYLOAD, SCHEMA)
    assert len(receipts) == 1 and not (spool / 'request-0002.json').exists()


def test_relay_needs_an_empty_folder_and_explicit_declarations(tmp_path):
    spool = tmp_path / 'spool'
    spool.mkdir()
    (spool / 'old.txt').write_text('left over')
    with pytest.raises(ValueError):
        dp.relay_provider(spool, declared_model='m', transport_note='n', max_calls=1)
    empty = tmp_path / 'empty'
    empty.mkdir()
    for bad in (dict(declared_model=''), dict(transport_note=' '), dict(max_calls=0), dict(timeout=5000)):
        settings = dict(declared_model='m', transport_note='n', max_calls=1)
        settings.update(bad)
        with pytest.raises(ValueError):
            dp.relay_provider(empty, **settings)


def test_scripted_provider_answers_only_known_requests_and_declares_no_model():
    known = {'answer': 'authored'}
    infer, identity, receipts = dp.scripted_provider(
        lambda payload, schema: known if payload.get('question') == 'synthetic' else None, [known])
    assert infer(PAYLOAD, SCHEMA) == known
    with pytest.raises(ParserOperationalError, match='cannot interpret other text'):
        infer({'system': 's', 'question': 'anything else'}, SCHEMA)
    assert identity['live_model'] is False and identity['backend'] == dp.SCRIPTED_BACKEND
    assert [r['answered'] for r in receipts] == [True, False]


def test_bound_factories_share_one_callable_and_map_category_instructions():
    seen = []
    semantic, category = dp.bind_factories(lambda payload, schema: seen.append(payload) or {},
                                           {'backend': 'b', 'model': 'm', 'digest': 'd'})
    category()[0]({'instructions': 'Define.', 'objective': 'o'}, SCHEMA)
    semantic()[0]({'system': 'Act.', 'request': 'r'}, SCHEMA)
    assert seen == [{'system': 'Define.', 'objective': 'o'}, {'system': 'Act.', 'request': 'r'}]
    assert category()[1] == {'backend': 'b', 'model_id': 'm', 'model_revision': 'd'}
    assert semantic.model_identity['backend'] == 'b'
    with pytest.raises(ValueError):
        dp.bind_factories(lambda *_: {}, {'backend': 'b', 'model': '', 'digest': 'd'})
