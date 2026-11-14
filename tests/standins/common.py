"""Shared parts of the stand-in servers and programs.

A stand-in is not a model. It answers with the hand-written rehearsal replies
of ``scripts/demo_scripted_replies.py`` or with a fixed object for the
connection test. Each one says so in its output. They exist so that the wire
format and the failure handling of a route can be tested without a provider.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from feedctrl.model_routes import OUTPUT_MARKER  # noqa: E402

NOTE = 'STAND-IN, NOT A MODEL'
DEFAULT_MODEL = 'standin-authored-replies-not-a-model'
NO_REPLY = NOTE + ': this stand-in has hand-written replies only for the bundled scenario requests.'
INPUT_HEADING = '\n\nINPUT (verbatim JSON from the application)\n\n'
INSTRUCTION_HEADING = 'INSTRUCTIONS (verbatim from the application)\n\n'
# Changes to a good reply, to test the one reply rule of the routes.
REPLY_FAULTS = ('fenced', 'prose', 'duplicate_key', 'wrong_schema', 'not_json', 'empty')


def split_system(system_text):
    """``(application instruction, schema)`` from a system text that a route rendered."""
    head, marker, tail = system_text.rpartition(OUTPUT_MARKER)
    if not marker:
        raise ValueError('The system text holds no schema marker')
    return head.rsplit('\n\nReturn exactly one JSON object', 1)[0], json.loads(tail.strip())


def from_messages(system_text, user_text):
    """Rebuild ``(payload, schema)`` from the two texts of a chat request."""
    instruction, schema = split_system(system_text)
    return {'system': instruction, **json.loads(user_text)}, schema


def from_prompt(prompt):
    """Rebuild ``(payload, schema)`` from the single text that a CLI route writes to standard input."""
    head, heading, body = prompt.partition(INPUT_HEADING)
    if not heading or not head.startswith(INSTRUCTION_HEADING):
        raise ValueError('The prompt does not have the expected parts')
    return from_messages(head[len(INSTRUCTION_HEADING):], body)


def reply_for(payload, schema, replies):
    """The hand-written reply for this request, or ``None``."""
    if sorted(schema.get('required', [])) == ['ok'] and set(schema.get('properties', {})) == {'ok'}:
        return {'ok': True}  # the connection test of feedctrl.model_routes.check_route
    if replies == 'scripted':
        scripts = str(ROOT / 'scripts')
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import demo_scripted_replies
        return demo_scripted_replies.lookup(payload, schema)
    return None


def faulty(text, fault):
    """Return the reply text with one fault, for the tests of the reply rule."""
    if fault == 'fenced':
        return '```json\n' + text + '\n```'
    if fault == 'prose':
        return 'Here is the answer.\n' + text
    if fault == 'duplicate_key':
        value = json.loads(text)
        first = next(iter(value))
        return '{' + json.dumps(first) + ':' + json.dumps(value[first]) + ',' + text.strip()[1:]
    if fault == 'wrong_schema':
        return '{"unexpected": true}'
    if fault == 'not_json':
        return 'I cannot answer in JSON.'
    if fault == 'empty':
        return ''
    return text


def write_launcher(folder, script, name='claude'):
    """Write a small program file that starts a stand-in script with this Python.

    A CLI route starts a program by its path. On Windows the launcher is a
    ``.cmd`` file, which is also the form of the npm launcher of real CLIs.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        path = folder / (name + '.cmd')
        path.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding='ascii')
    else:
        path = folder / name
        path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding='ascii')
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


class StandInServer:
    """A small HTTP server on 127.0.0.1 that records what it received."""

    def __init__(self, respond, *, port=0):
        self.requests = []   # {'method', 'path', 'headers' (lower-case names), 'body' (JSON or None)}
        self.lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def _serve(self):
                length = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(length) if length else b''
                try:
                    body = json.loads(raw.decode('utf-8')) if raw else None
                except ValueError:
                    body = None
                record = {'method': self.command, 'path': self.path, 'body': body,
                          'headers': {name.lower(): value for name, value in self.headers.items()}}
                with owner.lock:
                    owner.requests.append(record)
                    number = len(owner.requests)
                answer = respond(record, number)
                if answer is None:   # the fault "drop": close without an answer
                    self.close_connection = True
                    self.connection.close()
                    return
                status, headers, payload = answer
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')
                self.send_response(status)
                for name, value in {'Content-Type': 'application/json', **headers}.items():
                    self.send_header(name, value)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(data)
                self.close_connection = True

            do_GET = do_POST = _serve

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.server.daemon_threads = True
        self.server.handle_error = lambda *args: None   # a fault mode can close a connection on purpose
        self.port = self.server.server_port
        self.url = f'http://127.0.0.1:{self.port}'
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


def serve_forever(server, description):
    """Run a stand-in server from the command line until Ctrl+C."""
    server.start()
    print(f'{NOTE}. {description}', flush=True)
    print(f'Listening on {server.url} . Press Ctrl+C to stop.', flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
