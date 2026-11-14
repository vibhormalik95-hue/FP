"""Model routes: how the app reaches a language model, chosen in one small file.

A route is a transport. It returns ``(infer, identity, receipts)`` exactly as the
providers in ``feedctrl.demo_providers`` do, so the recommendation logic and the
interface need no change when a route is added. Four kinds are built in:

``relay``              the existing file queue; a person carries each request
``cli``                a program on this computer: the Claude Code CLI in print
                       mode, or any program that reads a prompt on standard input
``openai-compatible``  ``POST {base_url}/chat/completions`` (local model servers
                       and hosted providers that offer this API)
``anthropic``          ``POST /v1/messages`` of the Anthropic API

One reply rule holds for every route. The reply text must be exactly one JSON
object. It is decoded strictly and validated against the schema of the request.
There is no repair, no fence removal, no automatic retry and no fallback to
another mode or model. A rejected reply is an error that says what to change.

A credential comes from an environment variable or from a hidden prompt. It is
never written to the route file, the identity, a receipt, a record file or an
error text. The call allowance is a counter in this process, not a billing limit.

Another adapter needs one ``RouteAdapter`` and one ``register_route`` call; see
``docs/model-routes.md``.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Callable, NamedTuple
import urllib.parse

from jsonschema import Draft202012Validator

from feedctrl.controls import ParserOperationalError
from feedctrl.indirect_grounding import _response_snapshot
from feedctrl.model_adapters import _decode, _hash, _json

ROUTE_KINDS = ('openai-compatible', 'anthropic', 'cli', 'relay')
DEFAULT_FILE = 'model-route.json'
# The stand-in servers and programs read the schema that follows this line.
OUTPUT_MARKER = 'JSON Schema of the reply:'

# category -> (what happened, what the user should do). A closed vocabulary:
# the interface, the receipts and the documentation use these names.
CATEGORIES = {
    'configuration': ('The route file is not valid.',
                      'Correct the route file, or write a new one with "python scripts/model_route.py setup".'),
    'not_reachable': ('The model endpoint did not answer.',
                      'Check the address in the route file and that the server is running.'),
    'tls': ('The secure connection to the endpoint failed.',
            'Check the address and the certificates of this computer or network. On macOS with Python from python.org, '
            'run "Install Certificates.command" in the Python folder of Applications.'),
    'timeout': ('The model did not answer within the time limit.',
                'Try again, or raise "timeout_seconds" in the route file.'),
    'authentication': ('The provider rejected the API key.',
                       'Check the key in the environment variable, then start again.'),
    'permission': ('The provider refused this request for this account.',
                   'Check that the account may use this model and this endpoint.'),
    'billing': ('The provider reports a billing or quota problem.',
                'Check the credit, the payment details and the spend limits of the account.'),
    'model_not_found': ('The endpoint did not find the model.',
                        'Run the check to see the model names, and correct "model" in the route file.'),
    'bad_request': ('The endpoint rejected the request.',
                    'Read the provider message and change the named setting in the route file.'),
    'structured_output_unsupported': ('The endpoint does not accept this structured-output setting.',
                                      'Set "structured_output" in the route file to another value and run the check.'),
    'rate_limited': ('The provider limits the request rate of this account.',
                     'Wait a minute, then try again.'),
    'provider_overloaded': ('The provider is overloaded at this time.',
                            'Wait a few minutes, then try again.'),
    'provider_error': ('The provider had an internal error.',
                       'Try again. If it continues, look at the status page of the provider.'),
    'redirect_refused': ('The endpoint answered with a redirect, and a redirect is not followed.',
                         'Put the final address in "base_url".'),
    'reply_truncated': ('The reply stopped at the output limit before it was complete.',
                        'Raise "max_output_tokens" in the route file, or choose a smaller evidence scope.'),
    'reply_refused': ('The model declined to answer this request.',
                      'Change the request. Nothing was applied.'),
    'reply_not_json': ('The reply was not exactly one JSON object.',
                       'Use a structured-output setting that the endpoint supports, or a model that follows the format.'),
    'reply_schema_mismatch': ('The reply was JSON but did not match the schema of the request.',
                              'Try again, or use a model that follows a JSON schema. Nothing was applied.'),
    'reply_too_large': ('The reply was larger than the response limit of this route.',
                        'Raise "max_response_bytes" in the route file if this size is expected.'),
    'unexpected_reply': ('The endpoint answered in a form that this route does not know.',
                         'Check that the route kind matches the server, and run the check.'),
    'model_mismatch': ('The reply reports another model than the route file names.',
                       'Put the reported name in "model", or set "allow_reported_model_mismatch" to true to accept and record it.'),
    'allowance_exhausted': ('The call allowance of this run is used.',
                            'Start the server again for a new run, or raise "max_calls" in the route file.'),
    'cli_not_found': ('The command-line program was not found.',
                      'Install it, or put its full path in the route file.'),
    'cli_not_signed_in': ('The command-line program is not signed in.',
                          'Start the program once in a terminal and sign in, then try again.'),
    'cli_failed': ('The command-line program ended with an error.',
                   'Read the message. Run the same program by hand to see more.'),
}

_SECRET_NAME = re.compile(r'(?i)(api[_-]?key$|secret|passw(or)?d|authorization|bearer|credential|(^|[_-])token$|(^|[_-])key$)')
_SECRET_VALUE = re.compile(r'(?i)^\s*(sk-[A-Za-z0-9_\-]{8,}|bearer\s+\S{8,})')
_MASK = re.compile(r'(?i)(bearer\s+)[A-Za-z0-9_\-.=*]{8,}|\b(sk|pk|rk)-[A-Za-z0-9_\-*.]{8,}')
ENV_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')
MODEL_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/@+\-\[\]]{0,199}')


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def ascii_text(value):
    """Text that every console can print; other characters become escapes."""
    return str(value).encode('ascii', 'backslashreplace').decode('ascii')


def one_line(value, limit=600):
    text = ' '.join(str(value).split())
    return text if len(text) <= limit else text[:limit - 3] + '...'


def scrubber(*secrets):
    """Return a function that removes the given secret values from a text.

    It also masks anything shaped like a bearer token or an ``sk-`` key, because
    a provider can echo part of a credential in its own error message.
    """
    values = [value for value in secrets if isinstance(value, str) and len(value) >= 4]

    def clean(text):
        text = str(text)
        for value in values:
            text = text.replace(value, '[credential removed]')
        return _MASK.sub('[credential removed]', text)

    return clean


class RouteError(ParserOperationalError):
    """A route failure that a person can act on.

    ``category`` is one key of ``CATEGORIES``. ``message`` says what happened and
    ``action`` says what to do. ``str(error)`` is the two together. Callers must
    pass provider text through a scrubber first; no credential belongs here.
    """

    def __init__(self, category, message=None, action=None):
        if category not in CATEGORIES:
            raise ValueError('Unknown route error category')
        sentence, default_action = CATEGORIES[category]
        self.category = category
        self.message = one_line(message or sentence)
        self.action = one_line(action or default_action)
        super().__init__(f'{self.message} {self.action}')


class RouteAdapter(NamedTuple):
    """What one route kind supplies. ``build`` returns ``(infer, identity, receipts)``."""
    validate: Callable   # (raw: dict) -> normalised dict; raises RouteError('configuration')
    build: Callable      # (config, *, api_key, record_dir, relay_dir) -> (infer, identity, receipts)
    check: Callable      # (config, *, api_key, step) -> bool; reports reachability through step(name, ok, detail, action)
    describe: Callable   # (config) -> list[str] for the terminal; no secrets
    key_env: Callable    # (config) -> name of the environment variable that holds the key, or None


_REGISTRY = {}


def register_route(kind, adapter):
    """Add a route kind. The app, the launcher and the check then accept it."""
    if not isinstance(kind, str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,40}', kind):
        raise ValueError('A route kind is a short lower-case name')
    if not isinstance(adapter, RouteAdapter) or not all(callable(part) for part in adapter):
        raise ValueError('A RouteAdapter with five callables is required')
    _REGISTRY[kind] = adapter


def _adapter(kind):
    if kind not in _REGISTRY:
        if kind in ('openai-compatible', 'anthropic'):
            from feedctrl import route_http  # noqa: F401  (registers its adapters)
        elif kind == 'cli':
            from feedctrl import route_cli  # noqa: F401
        elif kind == 'relay':
            register_route('relay', RouteAdapter(_relay_validate, _relay_build, _relay_check,
                                                 _relay_describe, lambda config: None))
    if kind not in _REGISTRY:
        raise RouteError('configuration', f'The route kind "{one_line(kind, 60)}" is not known.',
                         'Use one of: ' + ', '.join(sorted({*ROUTE_KINDS, *_REGISTRY})) + '.')
    return _REGISTRY[kind]


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def reject(message, action=None):
    raise RouteError('configuration', message, action)


def refuse_secrets(value, where='the route file'):
    """Refuse a key name or a value that looks like a credential, at any depth."""
    if isinstance(value, dict):
        for name, item in value.items():
            if not isinstance(name, str):
                reject('The route file has a name that is not text.')
            if _SECRET_NAME.search(name) and name != 'api_key_env':
                reject(f'A credential must not be in {where} (found the name "{one_line(name, 40)}").',
                       'Put the key in an environment variable and name that variable in "api_key_env".')
            refuse_secrets(item, where)
    elif isinstance(value, list):
        for item in value:
            refuse_secrets(item, where)
    elif isinstance(value, str) and _SECRET_VALUE.search(value):
        reject(f'A value in {where} looks like a credential.',
               'Put the key in an environment variable and name that variable in "api_key_env".')


def take(raw, allowed, kind):
    """Refuse unknown keys so that a typing error is not silently ignored."""
    unknown = sorted(set(raw) - set(allowed))
    if unknown:
        reject(f'The route file has a setting that the "{kind}" route does not know: ' + ', '.join(unknown[:5]) + '.',
               'Remove it or correct its name. Known settings: ' + ', '.join(sorted(allowed)) + '.')


def text_setting(raw, name, limit, *, required=True, pattern=None, default=None):
    value = raw.get(name, default)
    if value is None and not required:
        return None
    if (not isinstance(value, str) or not value.strip() or len(value) > limit or value != value.strip()
            or any(ord(char) < 32 for char in value) or (pattern is not None and not pattern.fullmatch(value))):
        reject(f'The setting "{name}" is missing or not valid.')
    return value


def number_setting(raw, name, low, high, default, *, integer=True):
    value = raw.get(name, default)
    if value is None:
        return None
    good = type(value) is int if integer else type(value) in (int, float)
    if not good or not low <= value <= high:
        reject(f'The setting "{name}" must be {"a whole number" if integer else "a number"} from {low} to {high}.')
    return value


def flag_setting(raw, name):
    value = raw.get(name, False)
    if type(value) is not bool:
        reject(f'The setting "{name}" must be true or false.')
    return value


def choice_setting(raw, name, choices, default):
    value = raw.get(name, default)
    if value not in choices:
        reject(f'The setting "{name}" must be one of: ' + ', '.join(str(choice) for choice in choices) + '.')
    return value


def list_setting(raw, name, limit, item_limit, *, pattern=None):
    value = raw.get(name, [])
    if (not isinstance(value, list) or len(value) > limit
            or any(not isinstance(item, str) or len(item) > item_limit or any(ord(char) < 32 for char in item)
                   or (pattern is not None and not pattern.fullmatch(item)) for item in value)):
        reject(f'The setting "{name}" must be a list of at most {limit} short texts.')
    return list(value)


def common_limits(raw, *, timeout=600, max_calls=40):
    return {'max_calls': number_setting(raw, 'max_calls', 1, 500, max_calls),
            'timeout_seconds': number_setting(raw, 'timeout_seconds', 1, 1800, timeout, integer=False),
            'max_request_bytes': number_setting(raw, 'max_request_bytes', 1000, 5_000_000, 400_000),
            'max_response_bytes': number_setting(raw, 'max_response_bytes', 1000, 20_000_000, 2_000_000)}


def is_loopback(host):
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def url_setting(raw, name, *, default=None, allow_insecure=False):
    """An http(s) address without credentials, query or fragment; no trailing slash."""
    value = raw.get(name, default)
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        reject(f'The setting "{name}" must be an address such as http://127.0.0.1:11434/v1.')
    parts = urllib.parse.urlsplit(value.strip())
    try:
        host, _ = parts.hostname, parts.port
    except ValueError:
        host = None
    if parts.scheme not in ('http', 'https') or not host or parts.query or parts.fragment:
        reject(f'The setting "{name}" must be an http or https address without a query.')
    if parts.username is not None or parts.password is not None:
        reject(f'The address in "{name}" must not hold a user name or a password.')
    if parts.scheme == 'http' and not is_loopback(host) and not allow_insecure:
        reject(f'The address in "{name}" uses http for a host that is not this computer.',
               'Use https, or set "allow_insecure_http" to true if you accept an unencrypted connection.')
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'), '', ''))


def key_env_setting(raw, *, default=None):
    name = raw.get('api_key_env', default)
    if name is None:
        return None
    looks_like_key = (isinstance(name, str) and len(name) >= 24 and re.search('[a-z]', name) is not None
                      and re.search('[0-9]', name) is not None)
    if not isinstance(name, str) or not ENV_NAME.fullmatch(name) or looks_like_key:
        reject('"api_key_env" must be the NAME of an environment variable, not the key itself.',
               'Example: "api_key_env": "OPENAI_API_KEY". Set the key itself in that variable.')
    return name


def extra_body_setting(raw, reserved):
    value = raw.get('extra_body', {})
    if not isinstance(value, dict) or any(not isinstance(name, str) for name in value):
        reject('The setting "extra_body" must be an object of additional request fields.')
    try:
        size = len(_json(value))
    except (TypeError, ValueError):
        size = None
    if size is None or size > 4000:
        reject('The setting "extra_body" must be plain JSON of at most 4000 bytes.')
    clash = sorted(set(value) & set(reserved))
    if clash:
        reject('The setting "extra_body" must not replace a field that the route sets itself: ' + ', '.join(clash) + '.')
    return deepcopy(value)


def validate_config(raw):
    """Return a normalised copy of a route configuration, or raise ``RouteError``.

    Unknown settings are refused. A credential field or a value that looks like
    a credential is refused. Defaults are filled in, so that the saved file
    shows every setting that is in effect.
    """
    if not isinstance(raw, dict):
        reject('The route file must hold one JSON object.')
    refuse_secrets(raw)
    kind = raw.get('route')
    if not isinstance(kind, str):
        reject('The route file needs the setting "route".', 'Use one of: ' + ', '.join(ROUTE_KINDS) + '.')
    config = _adapter(kind).validate(deepcopy(raw))
    refuse_secrets(config)
    return {'route': kind, **{name: config[name] for name in sorted(config) if name != 'route' and config[name] is not None}}


def load_config(path):
    path = Path(path)
    if not path.is_file():
        reject(f'The route file {ascii_text(path)} does not exist.',
               'Write one with "python scripts/model_route.py setup".')
    try:
        raw = _decode(path.read_text(encoding='utf-8-sig'))
    except (ValueError, UnicodeDecodeError, RecursionError):
        reject(f'The route file {ascii_text(path)} is not valid JSON in UTF-8.')
    return validate_config(raw)


def save_config(path, config):
    """Write the normalised configuration. A configuration cannot hold a secret."""
    text = json.dumps(validate_config(config), indent=2, ensure_ascii=True) + '\n'
    Path(path).write_text(text, encoding='utf-8', newline='\n')


def public_config(config):
    return deepcopy(validate_config(config))


def describe(config):
    """Lines for the terminal. No secret can appear: the configuration holds none."""
    config = validate_config(config)
    adapter = _adapter(config['route'])
    lines = [f'Route: {config["route"]}', *adapter.describe(config)]
    name = adapter.key_env(config)
    if config['route'] in ('openai-compatible', 'anthropic'):
        lines.append(f'API key: read from the environment variable {name}; never stored' if name
                     else 'API key: none (a local server needs no key)')
    lines.append(f'Call allowance for one run: {config["max_calls"]} (a counter in this program, not a billing limit)')
    return [ascii_text(line) for line in lines]


def needs_api_key(config):
    """The name of the environment variable that must hold the key, or ``None``."""
    config = validate_config(config)
    return _adapter(config['route']).key_env(config)


def resolve_api_key(config, environ=None, ask=None):
    """Read the key from the environment, or ask for it with a hidden prompt.

    ``ask`` is a function such as ``getpass.getpass``. It is used only when it
    is given and the variable is not set. The key stays in memory.
    """
    name = needs_api_key(config)
    if name is None:
        return None
    environ = os.environ if environ is None else environ
    value = (environ.get(name) or '').strip()
    if not value and ask is not None:
        value = (ask(f'API key for {name} (hidden; kept in memory for this run only): ') or '').strip()
    if not value:
        raise RouteError('authentication', f'The environment variable {name} is not set.',
                         f'Set {name} to your API key in this terminal, then start again. '
                         'See docs/model-routes.md for the command on Windows and on macOS.')
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise RouteError('authentication', f'The value of {name} holds a space or a line break.',
                         'Copy the key again without the text around it.')
    return value


def build_route(config, *, api_key=None, record_dir=None, relay_dir=None, log=None):
    """Return ``(infer, identity, receipts)`` for a route configuration.

    Nothing is sent here. ``record_dir`` is a new or empty folder; when given,
    the route writes the exact request body and the raw reply of each call
    there, without any header. ``relay_dir`` is needed for the relay route.
    ``log`` is a function for one ASCII line about each call, for a terminal;
    an endpoint of the app can shorten an error, and this line keeps it whole.
    """
    config = validate_config(config)
    adapter = _adapter(config['route'])
    name = adapter.key_env(config)
    if name and not api_key:
        raise RouteError('authentication', f'This route needs an API key from the environment variable {name}.',
                         f'Set {name} in this terminal, then start again.')
    if api_key is not None:
        if not isinstance(api_key, str) or not api_key or any(char.isspace() for char in api_key):
            raise RouteError('authentication', 'The API key is empty or holds white space.',
                             'Copy the key again without the text around it.')
        if api_key in json.dumps(config):
            reject('The route file holds the API key itself.',
                   'Remove the key from the file. Keep it only in the environment variable.')
    infer, identity, receipts = adapter.build(config, api_key=api_key, record_dir=record_dir, relay_dir=relay_dir)
    for field in ('backend', 'model', 'digest'):
        if not isinstance(identity.get(field), str) or not identity[field].strip():
            raise ValueError('A route identity needs backend, model and digest')
    return (infer if log is None else _logged(infer, log, scrubber(api_key))), identity, receipts


def _logged(infer, log, clean):
    """Report each call in one line. The line passes the scrubber once more."""
    counter = {'calls': 0}

    def reported(payload, schema):
        counter['calls'] += 1
        number, started = counter['calls'], time.monotonic()
        try:
            result = infer(payload, schema)
        except Exception as error:
            seconds = time.monotonic() - started
            detail = (f'{error.category}: {error.message} What to do: {error.action}' if isinstance(error, RouteError)
                      else one_line(str(error) or type(error).__name__))
            log(ascii_text(clean(f'[model route] call {number} FAILED after {seconds:.1f} s. {detail}')))
            raise
        log(f'[model route] call {number} answered in {time.monotonic() - started:.1f} s; the reply passed the format checks')
        return result

    return reported


# --------------------------------------------------------------------------
# Shared rules for every adapter
# --------------------------------------------------------------------------

def split_payload(payload):
    if (not isinstance(payload, dict) or not isinstance(payload.get('system'), str)
            or not payload['system'].strip()):
        raise ValueError('Explicit system prompt required')
    return payload['system'], {name: value for name, value in payload.items() if name != 'system'}


def check_schema(schema):
    if not isinstance(schema, dict) or schema.get('type') != 'object':
        raise ValueError('Object response schema required')
    Draft202012Validator.check_schema(schema)


def output_instruction(schema):
    """The one fixed sentence that every route adds, followed by the schema."""
    return ('Return exactly one JSON object and nothing else. Do not use Markdown, a code fence, '
            'or any text before or after the object. The object must match the JSON Schema below.\n'
            + OUTPUT_MARKER + '\n' + _json(schema).decode('utf-8'))


def render_messages(payload, schema):
    """``(system text, user text)`` for a chat API. The user text is the input as JSON."""
    system, body = split_payload(payload)
    return system + '\n\n' + output_instruction(schema), _json(body).decode('utf-8')


def render_prompt(payload, schema):
    """One text for a program that reads its prompt on standard input.

    It has the same three parts as ``scripts/relay_tools.py`` gives to a person:
    the instruction, the schema sentence, then the input as JSON.
    """
    system, body = split_payload(payload)
    return ('INSTRUCTIONS (verbatim from the application)\n\n' + system + '\n\n' + output_instruction(schema)
            + '\n\nINPUT (verbatim JSON from the application)\n\n' + _json(body).decode('utf-8') + '\n')


def parse_reply(text, schema):
    """Apply the one reply rule: exactly one JSON object that matches the schema."""
    if not isinstance(text, str) or not text.strip():
        raise RouteError('reply_not_json', 'The model returned no text.')
    stripped = text.strip()
    start = ascii_text(one_line(stripped, 60))
    try:
        value = _decode(stripped)
    except json.JSONDecodeError:
        if stripped.startswith('```'):
            raise RouteError('reply_not_json', 'The reply was wrapped in a Markdown code fence. It is not repaired.') from None
        raise RouteError('reply_not_json', f'The reply was not exactly one JSON object. It started with: {start}') from None
    except (ValueError, RecursionError):
        raise RouteError('reply_not_json', 'The reply JSON repeats a key, holds a number that is not finite, '
                                           'or is nested too deeply.') from None
    if not isinstance(value, dict):
        raise RouteError('reply_not_json', 'The reply was JSON but not an object.')
    try:
        value = _response_snapshot(value)
    except ValueError:
        raise RouteError('reply_too_large', 'The reply JSON is larger than the application accepts.') from None
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: [str(part) for part in error.absolute_path])
    if errors:
        where = '/'.join(str(part) for part in errors[0].absolute_path) or '(top level)'
        raise RouteError('reply_schema_mismatch', 'The reply did not match the schema of the request at '
                         f'{ascii_text(where)}: {ascii_text(one_line(errors[0].message, 200))}')
    return value


_SNAPSHOT = re.compile(r'-\d[0-9.\-]*|:latest')


def model_matches(requested, reported):
    """Equal names, or a dated snapshot of the requested name (``name-2026-01-01``, ``name:latest``)."""
    return (isinstance(reported, str) and isinstance(requested, str) and reported.startswith(requested)
            and (reported == requested or bool(_SNAPSHOT.fullmatch(reported[len(requested):]))))


def require_model(requested, reported, allow_mismatch):
    if allow_mismatch or model_matches(requested, reported):
        return
    shown = ascii_text(one_line(reported, 120)) if isinstance(reported, str) and reported else 'no model name'
    raise RouteError('model_mismatch', f'The route file names the model "{ascii_text(requested)}", '
                                       f'and the reply reports {shown}.')


class CallAllowance:
    """One counter for a run. It cannot refill itself."""

    def __init__(self, max_calls):
        self.max_calls, self._used, self._lock = max_calls, 0, threading.Lock()

    @property
    def used(self):
        with self._lock:
            return self._used

    def reserve(self):
        with self._lock:
            if self._used >= self.max_calls:
                raise RouteError('allowance_exhausted', f'The call allowance of this run ({self.max_calls} calls) is used.')
            self._used += 1
            return self._used


class Recorder:
    """Write the exact bytes of each call to a new or empty folder; never overwrite."""

    def __init__(self, record_dir):
        self.root = None if record_dir is None else Path(record_dir)
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)
            if any(self.root.iterdir()):
                reject(f'The record folder {ascii_text(self.root)} is not empty.',
                       'Give a new folder for each run, so that no record is overwritten.')

    def write(self, ordinal, name, data):
        if self.root is not None:
            with open(self.root / f'call-{ordinal:04d}-{name}', 'xb') as handle:
                handle.write(data)


def bounded_counts(value, names):
    """Only named non-negative whole numbers from a provider's usage object."""
    if not isinstance(value, dict):
        return {}
    return {name: value[name] for name in names if type(value.get(name)) is int and 0 <= value[name] <= 2 ** 53}


def make_infer(*, config, transport, recorder, receipts, allowance, serial=False):
    """Wrap one transport in the rules that every route shares.

    ``transport(ordinal, payload, schema, receipt)`` sends one request and
    returns the reply text. It adds what it learns to ``receipt`` as it goes, so
    that a failed call still leaves its HTTP status or exit code behind.
    """
    lock = threading.Lock() if serial else None

    def call(payload, schema):
        payload, schema = deepcopy(payload), deepcopy(schema)
        _, body = split_payload(payload)
        check_schema(schema)
        ordinal = allowance.reserve()
        receipt = {'ordinal': ordinal, 'route': config['route'], 'started_utc': utc(),
                   'request_sha256': _hash({'system': payload['system'], 'payload': body, 'schema': schema}),
                   'schema_sha256': _hash(schema), 'requested_model': config.get('model'),
                   'reported_model': None, 'outcome': 'started'}
        receipts.append(receipt)
        started = time.monotonic()
        try:
            result = parse_reply(transport(ordinal, payload, schema, receipt), schema)
            receipt['outcome'] = 'parsed_transport_only'
            return result
        except RouteError as error:
            receipt.update(outcome='error', error_category=error.category)
            raise
        except Exception as error:
            # A defect in an adapter must not carry request text or a header into a message.
            receipt.update(outcome='error', error_category='provider_error', error_type=type(error).__name__)
            raise RouteError('provider_error', f'The route failed in an unexpected way ({type(error).__name__}).') from None
        finally:
            receipt['elapsed_seconds'] = round(time.monotonic() - started, 3)
            receipt['finished_utc'] = utc()
            try:
                recorder.write(ordinal, 'receipt.json', json.dumps(receipt, indent=2, sort_keys=True).encode('utf-8'))
            except OSError:
                receipt['receipt_file_written'] = False

    def infer(payload, schema):
        if lock is None:
            return call(payload, schema)
        with lock:
            return call(payload, schema)

    return infer


def identity_for(config, backend, limit):
    shown = public_config(config)
    return {'backend': backend, 'model': shown.get('model') or shown.get('declared_model'),
            'digest': _hash(shown), 'digest_kind': 'configuration_sha256_not_model_weights',
            'identity_limit': limit, 'live_model': True, 'route': shown}


# --------------------------------------------------------------------------
# Relay route: the existing file queue, selected through a route file
# --------------------------------------------------------------------------

def _relay_validate(raw):
    take(raw, {'route', 'declared_model', 'transport_note', 'max_calls', 'timeout_seconds'}, 'relay')
    return {'declared_model': text_setting(raw, 'declared_model', 150),
            'transport_note': text_setting(raw, 'transport_note', 500),
            # The relay provider itself accepts at most ten calls and 1800 seconds.
            'max_calls': number_setting(raw, 'max_calls', 1, 10, 10),
            'timeout_seconds': number_setting(raw, 'timeout_seconds', 1, 1800, 1800, integer=False)}


def _relay_build(config, *, api_key=None, record_dir=None, relay_dir=None):
    from feedctrl import demo_providers
    if relay_dir is None:
        reject('The relay route needs a new folder for its request and reply files.')
    spool = Path(relay_dir)
    spool.mkdir(parents=True, exist_ok=True)
    try:
        return demo_providers.relay_provider(spool, declared_model=config['declared_model'],
                                             transport_note=config['transport_note'], max_calls=config['max_calls'],
                                             timeout=config['timeout_seconds'])
    except ValueError as error:
        reject(str(error))


def _relay_check(config, *, api_key=None, step):
    step('relay', True, 'A person carries each request to the model. There is no connection to test.')
    return True


def _relay_describe(config):
    return [f'Model, as the operator declares it: {config["declared_model"]}',
            f'How a request reaches the model: {config["transport_note"]}']


# --------------------------------------------------------------------------
# Connectivity check
# --------------------------------------------------------------------------

TEST_PAYLOAD = {'system': 'This is a connection test of a research application. '
                          'Reply with a JSON object that has the single key "ok" with the value true.',
                'test': 'connection'}
TEST_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['ok'],
               'properties': {'ok': {'type': 'boolean'}}}


def check_route(config, *, api_key=None, test_call=True, out=print):
    """Check a route step by step and print each result in ASCII.

    Steps: the configuration, the credential when one is needed, the endpoint or
    program, and then one very small structured request. Return
    ``{'ok': bool, 'steps': [{'name', 'ok', 'detail', 'action'}]}``. ``ok`` is
    true only when every step passed.
    """
    steps = []

    def step(name, ok, detail, action=''):
        entry = {'name': name, 'ok': bool(ok), 'detail': ascii_text(one_line(detail)),
                 'action': '' if ok else ascii_text(one_line(action))}
        steps.append(entry)
        out(f'{"OK    " if ok else "FAILED"}  {name}: {entry["detail"]}')
        if entry['action']:
            out(f'        What to do: {entry["action"]}')

    def finish():
        return {'ok': all(entry['ok'] for entry in steps), 'steps': steps}

    try:
        config = validate_config(config)
    except RouteError as error:
        step('configuration', False, error.message, error.action)
        return finish()
    adapter = _adapter(config['route'])
    step('configuration', True, '; '.join(describe(config)[:3]))
    name = adapter.key_env(config)
    if name:
        if not api_key:
            step('credential', False, f'The environment variable {name} is not set.',
                 f'Set {name} to your API key in this terminal, then run the check again.')
            return finish()
        step('credential', True, f'A key was read from {name}. It is not shown and not stored.')
    clean = scrubber(api_key)
    try:
        reachable = adapter.check(config, api_key=api_key, step=step)
    except RouteError as error:
        step('endpoint', False, clean(error.message), clean(error.action))
        reachable = False
    if not reachable or config['route'] == 'relay':
        return finish()
    if not test_call:
        out('The test call was not requested. No request was sent to the model.')
        return finish()
    out('The next step sends one very small request to the model. It can use a few tokens.')
    try:
        infer, _, receipts = build_route({**config, 'max_calls': 1}, api_key=api_key)
        started = time.monotonic()
        reply = infer(deepcopy(TEST_PAYLOAD), deepcopy(TEST_SCHEMA))
        seconds = time.monotonic() - started
        reported = receipts[-1].get('reported_model') or receipts[-1].get('reported_models') or 'not reported'
        if reply == {'ok': True}:
            step('test call', True, f'The model returned the requested JSON object in {seconds:.1f} s. '
                                    f'Model reported by the reply: {reported}.')
        else:
            step('test call', False, 'The reply was valid JSON but did not hold "ok": true.',
                 'The model does not follow a simple instruction. Use a stronger model.')
    except RouteError as error:
        step('test call', False, clean(error.message), clean(error.action))
    return finish()
