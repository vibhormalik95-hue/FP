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
error text. Every key that a route of this process uses is remembered in memory,
and every error text, receipt and record file passes a scrubber that removes it.
The call allowance is a counter in this process, not a billing limit.

Another adapter needs one ``RouteAdapter`` and one ``register_route`` call; see
``docs/model-routes.md``.
"""
from __future__ import annotations

import atexit
from copy import deepcopy
from datetime import datetime, timezone
import difflib
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
                       'Put the reported name in "model", or add it to "accept_reported_models" in the route file '
                       'to accept and record the difference.'),
    'allowance_exhausted': ('The call allowance of this run is used.',
                            'Start the server again for a new run, or raise "max_calls" in the route file.'),
    'cli_not_found': ('The command-line program was not found.',
                      'Install it, or put its full path in the route file.'),
    'cli_not_signed_in': ('The command-line program is not signed in.',
                          'Start the program once in a terminal and sign in, then try again.'),
    'cli_failed': ('The command-line program ended with an error.',
                   'Read the message. Run the same program by hand to see more.'),
    'record_failed': ('A record file of this run could not be written.',
                      'Check the record folder and the free space of the disk, then start the server again. '
                      'No further call is made in this run.'),
    'route_failed': ('The route failed in an unexpected way.',
                     'Try again. If it continues, report it with the receipt of the call. '
                     'This is a defect of the route, not of the provider.'),
    'stopped': ('The application is stopping, so no model call is made.',
                'Start the application again.'),
}

ENV_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')
MODEL_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/@+\-\[\]]{0,199}')
_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_JSON_SPACE = ' \t\r\n'


# --------------------------------------------------------------------------
# Text for a terminal, a page and a file
# --------------------------------------------------------------------------

def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def ascii_text(value):
    """Text that every console can print.

    Characters outside ASCII become escapes. So do control characters: a reply,
    a model name or a provider message is not trusted, and an escape sequence in
    it could otherwise move the cursor or hide a line of the terminal.
    """
    text = str(value).encode('ascii', 'backslashreplace').decode('ascii')
    return _CONTROL.sub(lambda match: f'\\x{ord(match.group()):02x}', text)


def one_line(value, limit=600):
    text = ' '.join(str(value).split())
    return text if len(text) <= limit else text[:limit - 3] + '...'


# --------------------------------------------------------------------------
# Credentials: what looks like one, and how one is removed from a text
# --------------------------------------------------------------------------

# Shapes of credentials, found anywhere in a text. The last alternative is a
# long run of letters and digits in both cases with no separator, which is the
# form of a key that has no known prefix.
_KEY_SHAPES = re.compile(
    r'(?i:bearer)\s+(?=[A-Za-z0-9_\-.=+/]*[0-9])[A-Za-z0-9_\-.=+/]{8,}'
    r'|\b(?:sk|pk|rk)[-_][A-Za-z0-9_\-*.]{8,}'
    r'|\b(?:gsk|xai|hf|ghp|gho|ghu|ghs|ghr|glpat|pat)[-_][A-Za-z0-9_\-]{16,}'
    r'|\bAIza[0-9A-Za-z_\-]{20,}'
    r'|\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}'
    r'|(?<![A-Za-z0-9])(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]{40,}(?![A-Za-z0-9])')
# A setting of the route file with one of these names would hold a credential.
_SECRET_SETTING = re.compile(r'(?i)^(x[-_])?(api[-_]?key|key|token|secret|passw(or)?d|passwd|authorization|bearer|'
                             r'credentials?|access[-_]?token|auth[-_]?token|client[-_]?secret)$')
# The same question for a name inside "extra_body" or inside a JSON text. A
# provider can have request fields such as "prompt_cache_key" or "max_tokens";
# they are not credentials, so only the clear names are refused there.
_SECRET_FIELD = re.compile(r'(?i)((^|[-_.])api[-_]?key$|^apikey$|secret|passw(or)?d|^authorization$|bearer|credential|'
                           r'(^|[-_.])token$)')
# A command-line argument that carries a credential, with or without "=value".
_KEY_FLAG = re.compile(r'(?i)^--?(x-)?(api[-_]?key|key|token|auth[-_]?token|access[-_]?token|password|secret|'
                       r'authorization|bearer|credentials?)(=.*)?$')
_HEADER_TEXT = re.compile(r'(?i)\b(authorization|x-api-key|api[-_]?key)\s*[:=]\s*\S')
REMOVED = '[credential removed]'
_SECRETS = []            # every form of every key that a route of this process uses
_SECRETS_LOCK = threading.Lock()


def _forms(value):
    """The key as it is, and as a JSON text or an address would write it."""
    escaped = json.dumps(value)[1:-1]
    return {value, escaped, escaped.replace('/', '\\/'), json.dumps(value, ensure_ascii=False)[1:-1],
            urllib.parse.quote(value, safe='')}


def remember_secret(value):
    """Keep a key in memory so that every later text can be cleaned of it."""
    if not isinstance(value, str) or not value:
        return
    with _SECRETS_LOCK:
        for form in _forms(value):
            # A long key is removed wherever it occurs. A short value is a
            # placeholder for a local server; it is removed only as a whole
            # word, so that a key such as "x" does not empty every sentence.
            pattern = (re.escape(form) if len(form) >= 16
                       else r'(?<![A-Za-z0-9_\-])' + re.escape(form) + r'(?![A-Za-z0-9_\-])')
            if all(pattern != known.pattern for known in _SECRETS):
                _SECRETS.append(re.compile(pattern))
        _SECRETS.sort(key=lambda known: -len(known.pattern))


def scrub(text):
    """Remove every remembered key and everything that has the shape of a key."""
    text = str(text)
    with _SECRETS_LOCK:
        known = list(_SECRETS)
    for pattern in known:
        text = pattern.sub(REMOVED, text)
    return _KEY_SHAPES.sub(REMOVED, text)


def scrub_bytes(data):
    """``(data without any remembered key, whether something was removed)``, for a record file."""
    with _SECRETS_LOCK:
        known = list(_SECRETS)
    changed = False
    for pattern in known:
        cleaned = re.sub(pattern.pattern.encode('utf-8'), REMOVED.encode('ascii'), data)
        changed, data = changed or cleaned != data, cleaned
    return data, changed


def scrub_value(value):
    """A copy of receipt data with every text cleaned."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    if isinstance(value, dict):
        return {scrub(name) if isinstance(name, str) else name: scrub_value(item) for name, item in value.items()}
    return value


def scrubber(*secrets):
    """Remember the given keys and return the function that cleans a text.

    The function also masks anything shaped like a credential, because a
    provider can echo part of a key in its own message.
    """
    for value in secrets:
        remember_secret(value)
    return scrub


class RouteError(ParserOperationalError):
    """A route failure that a person can act on.

    ``category`` is one key of ``CATEGORIES``. ``message`` says what happened and
    ``action`` says what to do. ``str(error)`` is the two together. Both texts
    are cleaned of every remembered key, bounded and made printable ASCII when
    the error is built, so the text is safe to show on a page: ``page_safe``.
    """
    page_safe = True

    def __init__(self, category, message=None, action=None):
        if category not in CATEGORIES:
            raise ValueError('Unknown route error category')
        sentence, default_action = CATEGORIES[category]
        self.category = category
        self.message = ascii_text(one_line(scrub(message or sentence)))
        self.action = ascii_text(one_line(scrub(action or default_action)))
        self.http_status = None
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
# Stop: a stop signal ends running calls and prevents new ones
# --------------------------------------------------------------------------

_STOP = {'requested': False}
_WATCHED = {}            # token -> [deadline or None, cancel(reason), already cancelled]
_WATCH_LOCK = threading.Lock()
_WATCHER = {'thread': None, 'next': 0}


def request_stop():
    """Ask every route of this process to stop. Safe to call from a signal handler.

    It only sets a flag. A watcher thread sees the flag within a fraction of a
    second and ends the running calls; a new call is refused.
    """
    _STOP['requested'] = True


def stop_requested():
    return _STOP['requested']


def reset_stop():
    """Allow calls again. For a test, and for a program that keeps running after a stop."""
    _STOP['requested'] = False


def watch(cancel, deadline=None):
    """Register a running call. ``cancel(reason)`` ends it; ``reason`` is "stop" or "deadline".

    ``deadline`` is a value of ``time.monotonic()``. Return a token for ``unwatch``.
    """
    with _WATCH_LOCK:
        _WATCHER['next'] += 1
        token = _WATCHER['next']
        _WATCHED[token] = [deadline, cancel, False]
        if _WATCHER['thread'] is None or not _WATCHER['thread'].is_alive():
            _WATCHER['thread'] = threading.Thread(target=_watch_loop, name='model-route-watcher', daemon=True)
            _WATCHER['thread'].start()
    return token


def unwatch(token):
    with _WATCH_LOCK:
        _WATCHED.pop(token, None)


def _due(now):
    """The calls to end now, each one time: ``[(cancel, reason)]``."""
    found = []
    with _WATCH_LOCK:
        for entry in _WATCHED.values():
            reason = 'stop' if _STOP['requested'] else 'deadline' if entry[0] is not None and now >= entry[0] else None
            if reason and not entry[2]:
                entry[2] = True
                found.append((entry[1], reason))
    return found


def _watch_loop():
    while True:
        time.sleep(0.1)
        for cancel, reason in _due(time.monotonic()):
            try:
                cancel(reason)
            except Exception:   # noqa: BLE001  (a failed cancel must not end the watcher)
                pass


def cancel_running(reason='stop'):
    """End every running call now, in this thread. Used when the program exits."""
    with _WATCH_LOCK:
        entries = [entry for entry in _WATCHED.values() if not entry[2]]
        for entry in entries:
            entry[2] = True
    for entry in entries:
        try:
            entry[1](reason)
        except Exception:   # noqa: BLE001
            pass


def _at_exit():
    request_stop()
    cancel_running('stop')


atexit.register(_at_exit)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def reject(message, action=None):
    raise RouteError('configuration', message, action)


_KEY_ADVICE = 'Put the key in an environment variable and name that variable in "api_key_env".'


def refuse_secrets(value, where='the route file', *, top=True):
    """Refuse a credential in a configuration, at any depth.

    A setting or a request field with the name of a credential is refused. So
    is a text that holds the shape of a key anywhere, and a JSON text that holds
    one inside. This cannot find every key: a key with no known shape that is
    shorter than 40 characters passes here, and ``build_route`` then compares the
    file with the key that it was given.
    """
    if isinstance(value, dict):
        for name, item in value.items():
            if not isinstance(name, str):
                reject('The route file has a name that is not text.')
            if name != 'api_key_env' and (_SECRET_SETTING if top else _SECRET_FIELD).search(name):
                reject(f'A credential must not be in {where} (found the name "{one_line(name, 40)}").', _KEY_ADVICE)
            refuse_secrets(item, where, top=False)
    elif isinstance(value, list):
        for item in value:
            refuse_secrets(item, where, top=False)
    elif isinstance(value, str):
        if _KEY_SHAPES.search(value) or _HEADER_TEXT.search(value):
            reject(f'A value in {where} looks like a credential.', _KEY_ADVICE)
        if value.lstrip()[:1] in ('{', '['):
            try:
                inner = json.loads(value)
            except (ValueError, RecursionError):
                inner = None
            if isinstance(inner, (dict, list)):
                refuse_secrets(inner, where, top=False)


def refuse_key_arguments(parts, name):
    """Refuse a command-line argument that carries a credential, such as ``--api-key``."""
    for part in parts:
        if isinstance(part, str) and _KEY_FLAG.fullmatch(part.strip()):
            reject(f'The setting "{name}" holds an argument that carries a credential ({one_line(part.split("=")[0], 40)}).',
                   'A program of this route signs in by itself. If it needs a key, set the key in an environment '
                   'variable and name that variable in "pass_environment".')


def take(raw, allowed, kind):
    """Refuse unknown keys so that a typing error is not silently ignored."""
    unknown = sorted(set(raw) - set(allowed))
    if unknown:
        close = difflib.get_close_matches(unknown[0], sorted(allowed), n=1, cutoff=0.8)
        reject(f'The route file has a setting that the "{kind}" route does not know: ' + ', '.join(unknown[:5]) + '.',
               (f'Did you mean "{close[0]}"? ' if close else '') + 'Remove it or correct its name. Known settings: '
               + ', '.join(sorted(allowed)) + '.')


def text_setting(raw, name, limit, *, required=True, pattern=None, default=None):
    value = raw.get(name, default)
    if value is None and not required:
        return None
    if (not isinstance(value, str) or not value.strip() or len(value) > limit or value != value.strip()
            or _CONTROL.search(value) or (pattern is not None and not pattern.fullmatch(value))):
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
        named = ', '.join(str(choice) for choice in choices if choice is not None)
        reject(f'The setting "{name}" must be one of: {named}.'
               + (' Leave it out for the default.' if None in choices else ''))
    return value


def list_setting(raw, name, limit, item_limit, *, pattern=None):
    value = raw.get(name, [])
    if (not isinstance(value, list) or len(value) > limit
            or any(not isinstance(item, str) or len(item) > item_limit or _CONTROL.search(item)
                   or (pattern is not None and not pattern.fullmatch(item)) for item in value)):
        reject(f'The setting "{name}" must be a list of at most {limit} short texts.')
    return list(value)


def accepted_models_setting(raw):
    """Exact model names that a reply may report in place of the requested name."""
    names = list_setting(raw, 'accept_reported_models', 20, 200, pattern=MODEL_NAME)
    return sorted(set(names)) or None


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


def address_host(value):
    """The host name of an address, or ``None`` when the text is not an address."""
    try:
        return urllib.parse.urlsplit(str(value).strip()).hostname
    except ValueError:
        return None


def url_setting(raw, name, *, default=None, allow_insecure=False):
    """An http(s) address without credentials, query or fragment; no trailing slash."""
    value = raw.get(name, default)
    example = 'an address such as http://127.0.0.1:11434/v1'
    if not isinstance(value, str) or not value.strip() or len(value) > 500 or _CONTROL.search(value):
        reject(f'The setting "{name}" must be {example}.')
    try:
        parts = urllib.parse.urlsplit(value.strip())
        host, _ = parts.hostname, parts.port
    except ValueError:
        reject(f'The setting "{name}" is not a valid address. It must be {example}.')
    if parts.scheme not in ('http', 'https') or not host or parts.query or parts.fragment:
        reject(f'The setting "{name}" must be an http or https address without a query.')
    if parts.username is not None or parts.password is not None:
        reject(f'The address in "{name}" must not hold a user name or a password.')
    if parts.scheme == 'http' and not is_loopback(host) and not allow_insecure:
        reject(f'The address in "{name}" uses http for a host that is not this computer.',
               'Use https, or set "allow_insecure_http" to true if you accept an unencrypted connection.')
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'), '', ''))


def key_env_setting(raw, *, default=None):
    """The NAME of the variable that holds the key. A pasted key is refused."""
    name = raw.get('api_key_env', default)
    if name is None:
        return None
    # A variable name is words with underscores. A long text with digits and
    # no underscore, or anything with the shape of a key, is a pasted key.
    looks_like_key = isinstance(name, str) and (bool(_KEY_SHAPES.search(name)) or (
        len(name) >= 20 and '_' not in name and re.search('[0-9]', name) is not None))
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
        reject('The setting "extra_body" must not replace a field that the route sets itself: ' + ', '.join(clash) + '.',
               'Use the setting of the route file for that field, or remove it from "extra_body".')
    return deepcopy(value)


def validate_config(raw):
    """Return a normalised copy of a route configuration, or raise ``RouteError``.

    A setting with the name of a credential is refused first. Then the route
    kind refuses each setting that it does not know, so that a typing error
    gets its own message. Then every value is searched for a credential.
    Settings that are off or not set are left out of the result.
    """
    if not isinstance(raw, dict):
        reject('The route file must hold one JSON object.')
    for name in raw:
        if not isinstance(name, str):
            reject('The route file has a name that is not text.')
        if name != 'api_key_env' and _SECRET_SETTING.search(name):
            reject(f'A credential must not be in the route file (found the name "{one_line(name, 40)}").', _KEY_ADVICE)
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
    except OSError as error:
        reject(f'The route file {ascii_text(path)} cannot be read ({type(error).__name__}).',
               'Check the file and its permissions.')
    return validate_config(raw)


def save_config(path, config):
    """Write the normalised configuration. A configuration cannot hold a secret."""
    text = json.dumps(validate_config(config), indent=2, ensure_ascii=True) + '\n'
    try:
        Path(path).write_text(text, encoding='utf-8', newline='\n')
    except OSError as error:
        reject(f'The route file {ascii_text(path)} cannot be written ({type(error).__name__}).',
               'Choose a folder that exists and that you can write to.')


def public_config(config):
    return deepcopy(validate_config(config))


def describe(config):
    """Lines for the terminal. No secret can appear: the configuration holds none."""
    config = validate_config(config)
    adapter = _adapter(config['route'])
    lines = [f'Route: {config["route"]}', *adapter.describe(config)]
    name = adapter.key_env(config)
    if config['route'] in ('openai-compatible', 'anthropic'):
        host = address_host(config.get('base_url')) or 'the endpoint'
        lines.append(f'API key: read from the environment variable {name}; sent only to {host}; never stored' if name
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
    remember_secret(value)
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise RouteError('authentication', f'The value of {name} holds a space or a line break.',
                         'Copy the key again without the text around it. Do not include the word "Bearer".')
    if not value.isascii() or not value.isprintable():
        raise RouteError('authentication', f'The value of {name} holds a character that is not a printable ASCII character.',
                         'Copy the key again. A copy from a document can add a character that cannot be seen.')
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
        if not isinstance(api_key, str) or not api_key:
            raise RouteError('authentication', 'The API key is empty.', 'Copy the key again.')
        remember_secret(api_key)
        if any(char.isspace() for char in api_key) or not api_key.isascii() or not api_key.isprintable():
            raise RouteError('authentication', 'The API key holds white space or a character that is not printable ASCII.',
                             'Copy the key again without the text around it.')
        # A preset label can also be a local-server placeholder ("lm-studio").
        # Exclude only that label, not arbitrary short keys or request fields.
        values = {field: value for field, value in config.items() if field != 'preset'}
        encoded = _json(_values_only(values)).decode('utf-8')
        if any(form in encoded for form in _forms(api_key)):
            reject('The route file holds the API key itself.',
                   'Remove the key from the file. Keep it only in the environment variable.')
    infer, identity, receipts = adapter.build(config, api_key=api_key, record_dir=record_dir, relay_dir=relay_dir)
    for field in ('backend', 'model', 'digest'):
        if not isinstance(identity.get(field), str) or not identity[field].strip():
            raise ValueError('A route identity needs backend, model and digest')
    return (infer if log is None else _logged(infer, log)), identity, receipts


def _values_only(value):
    """The values of a configuration without its setting names, for the search for a key."""
    if isinstance(value, dict):
        return [_values_only(item) for item in value.values()]
    if isinstance(value, list):
        return [_values_only(item) for item in value]
    return value


def _logged(infer, log):
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
                      else one_line(scrub(str(error) or type(error).__name__)))
            log(ascii_text(scrub(f'[model route] call {number} FAILED after {seconds:.1f} s. {detail}')))
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
    """Apply the one reply rule: exactly one JSON object that matches the schema.

    Only the white space of JSON (space, tab, line feed, carriage return) may
    stand around the object.
    """
    if not isinstance(text, str) or not text.strip(_JSON_SPACE):
        raise RouteError('reply_not_json', 'The model returned no text.')
    stripped = text.strip(_JSON_SPACE)
    start = one_line(scrub(stripped), 60)
    try:
        value = _decode(stripped)
    except json.JSONDecodeError:
        if stripped.startswith('```'):
            raise RouteError('reply_not_json', 'The reply was wrapped in a Markdown code fence. It is not repaired.') from None
        raise RouteError('reply_not_json', f'The reply was not exactly one JSON object. It started with: {start}') from None
    except RecursionError:
        raise RouteError('reply_not_json', 'The reply JSON is nested too deeply to read.',
                         'Use a model that follows the schema of the request.') from None
    except ValueError:
        raise RouteError('reply_not_json', 'The reply JSON repeats a key or holds a value that is not a finite number.',
                         'Use a model that follows the schema of the request.') from None
    if not isinstance(value, dict):
        raise RouteError('reply_not_json', 'The reply was JSON but not an object.')
    try:
        value = _response_snapshot(value)
    except ValueError as error:
        # The limits of the application are fixed. A higher byte limit of the
        # route does not change them, so each cause gets its own sentence.
        if 'byte budget' in str(error) or 'text budget' in str(error):
            raise RouteError('reply_too_large', 'The reply JSON holds more text than the application accepts '
                             '(2,000,000 characters). This limit is fixed.',
                             'Choose a smaller evidence scope.') from None
        if 'structure budget' in str(error):
            raise RouteError('reply_not_json', 'The reply JSON is nested deeper than 64 levels or has more than '
                             '50,000 parts. This limit is fixed.',
                             'Use a model that follows the schema of the request.') from None
        raise RouteError('reply_not_json', 'The reply JSON holds a number that is not finite, for example 1e999.',
                         'Use a model that follows the schema of the request.') from None
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: [str(part) for part in error.absolute_path])
    if errors:
        where = '/'.join(str(part) for part in errors[0].absolute_path) or '(top level)'
        raise RouteError('reply_schema_mismatch', 'The reply did not match the schema of the request at '
                         f'{where}: {one_line(scrub(errors[0].message), 200)}')
    return value


# A dated snapshot name is the requested name plus a date, as providers write
# it: name-20260806 or name-2026-08-06. A version suffix such as "-5" is not a
# date: "model-5" and "model-5-5" are two models.
_DATED = re.compile(r'-(?:19|20)\d\d(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])'
                    r'|-(?:19|20)\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])')


def model_rule(requested, reported, accepted=()):
    """Why a reported model name counts as the requested one, or ``None``.

    ``equal``: the same name. ``default_tag``: the requested name plus
    ``:latest``, the default tag of Ollama. ``dated_snapshot``: the requested
    name plus a date. ``accepted_by_setting``: an exact name from
    ``accept_reported_models``. Nothing else matches.
    """
    if not isinstance(requested, str) or not isinstance(reported, str) or not reported:
        return None
    if reported == requested:
        return 'equal'
    if reported == requested + ':latest':
        return 'default_tag'
    if reported.startswith(requested) and _DATED.fullmatch(reported[len(requested):]):
        return 'dated_snapshot'
    if reported in (accepted or ()):
        return 'accepted_by_setting'
    return None


def model_matches(requested, reported, accepted=()):
    return model_rule(requested, reported, accepted) is not None


def require_model(requested, reported, allow_mismatch=False, accepted=()):
    """Return the rule that accepts the reported name, or raise ``model_mismatch``."""
    rule = model_rule(requested, reported, accepted)
    if rule:
        return rule
    if allow_mismatch:
        return 'difference_allowed_by_setting'
    shown = one_line(reported, 120) if isinstance(reported, str) and reported else 'no model name'
    raise RouteError('model_mismatch', f'The route file names the model "{requested}", and the reply reports {shown}.',
                     'If that is the model you want, put the reported name in "model", or add it to '
                     '"accept_reported_models" in the route file. "allow_reported_model_mismatch": true accepts and '
                     'records any difference.')


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


_IGNORED_ENTRIES = ('.DS_Store', 'Thumbs.db', 'desktop.ini')   # files that a file browser adds to a folder


class Recorder:
    """Write the exact bytes of each call to a new or empty folder; never overwrite.

    Every file passes the scrubber. After a failed write no further call is
    made in the run, because its record would be incomplete.
    """

    def __init__(self, record_dir):
        self.root = None if record_dir is None else Path(record_dir)
        self.failed = None
        if self.root is None:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            entries = [path for path in self.root.iterdir() if path.name not in _IGNORED_ENTRIES]
        except OSError as error:
            raise RouteError('record_failed', f'The record folder {self.root} cannot be used ({type(error).__name__}).',
                             'Give a new folder for the records, or "none" for no records.') from None
        if entries:
            reject(f'The record folder {self.root} is not empty.',
                   'Give a new folder for each run, so that no record is overwritten.')

    def _problem(self, reason):
        self.failed = reason
        return RouteError('record_failed', f'A record file in {self.root} could not be written ({reason}).')

    def require_ready(self):
        """Raise before a call when its record could not be written."""
        if self.root is None:
            return
        if self.failed:
            raise self._problem(self.failed)
        if not self.root.is_dir():
            raise self._problem('the folder does not exist any more')

    def write(self, ordinal, name, data):
        """Write one file. Return whether a key was removed from it. Raise ``record_failed`` when it cannot be written."""
        if self.root is None:
            return False
        data, changed = scrub_bytes(data)
        try:
            with open(self.root / f'call-{ordinal:04d}-{name}', 'xb') as handle:
                handle.write(data)
        except OSError as error:
            raise self._problem(type(error).__name__) from None
        return changed

    def write_after(self, ordinal, name, data, receipt):
        """Write a file of a call whose reply exists already. A failure is noted; the reply is kept."""
        try:
            return self.write(ordinal, name, data)
        except RouteError:
            receipt['record_incomplete'] = True
            return False


def bounded_counts(value, names):
    """Only named non-negative whole numbers from a provider's usage object."""
    if not isinstance(value, dict):
        return {}
    return {name: value[name] for name in names if type(value.get(name)) is int and 0 <= value[name] <= 2 ** 53}


def make_infer(*, config, transport, recorder, receipts, allowance, serial=False):
    """Wrap one transport in the rules that every route shares.

    ``transport(ordinal, payload, schema, receipt)`` sends one request and
    returns the reply text. It adds what it learns to ``receipt`` as it goes, so
    that a failed call still leaves its HTTP status or exit code behind. Every
    text of the receipt and every error text is cleaned of keys here, at the
    place where it leaves the route.
    """
    lock = threading.Lock() if serial else None
    order = threading.Lock()

    def call(payload, schema):
        payload, schema = deepcopy(payload), deepcopy(schema)
        _, body = split_payload(payload)
        check_schema(schema)
        if stop_requested():
            raise RouteError('stopped')
        recorder.require_ready()
        receipt = {'ordinal': None, 'route': config['route'], 'started_utc': None,
                   'request_sha256': _hash({'system': payload['system'], 'payload': body, 'schema': schema}),
                   'schema_sha256': _hash(schema), 'requested_model': config.get('model'),
                   'reported_model': None, 'outcome': 'started'}
        with order:
            # The ordinal and the place in the list are given together, so that
            # the list is in the order of the ordinals under threads.
            receipt['ordinal'] = ordinal = allowance.reserve()
            receipt['started_utc'] = utc()
            receipts.append(receipt)
        started = time.monotonic()
        try:
            result = parse_reply(transport(ordinal, payload, schema, receipt), schema)
            receipt['outcome'] = 'parsed_transport_only'
            return result
        except RouteError as error:
            if stop_requested() and error.category in ('timeout', 'not_reachable', 'cli_failed'):
                error = RouteError('stopped', 'The application is stopping. The running model call was ended.')
            receipt.update(outcome='error', error_category=error.category)
            if error.http_status is not None:
                receipt.setdefault('http_status', error.http_status)
            raise RouteError(error.category, error.message, error.action) from None
        except Exception as error:
            # A defect in an adapter must not carry request text or a header into a message.
            receipt.update(outcome='error', error_category='route_failed', error_type=type(error).__name__)
            raise RouteError('route_failed', f'The route failed in an unexpected way ({type(error).__name__}).') from None
        finally:
            receipt['elapsed_seconds'] = round(time.monotonic() - started, 3)
            receipt['finished_utc'] = utc()
            cleaned = scrub_value(receipt)
            receipt.clear()
            receipt.update(cleaned)
            try:
                recorder.write(ordinal, 'receipt.json', json.dumps(receipt, indent=2, sort_keys=True).encode('utf-8'))
            except RouteError:
                receipt['receipt_file_written'] = False

    def infer(payload, schema):
        if lock is None:
            return call(payload, schema)
        with lock:
            return call(payload, schema)

    return infer


# Settings that can hold a path of this computer or free text. A review and
# the page get their hash, not their value. The terminal shows the value.
PRIVATE_SETTINGS = ('argv', 'command', 'extra_args', 'extra_body')


def identity_for(config, backend, limit):
    shown = public_config(config)
    page = {name: value for name, value in shown.items() if name not in PRIVATE_SETTINGS}
    hidden = {name: _hash(shown[name]) for name in PRIVATE_SETTINGS if name in shown}
    if hidden:
        page['settings_shown_as_sha256'] = hidden
    return {'backend': backend, 'model': shown.get('model') or shown.get('declared_model'),
            'digest': _hash(shown), 'digest_kind': 'configuration_sha256_not_model_weights',
            'identity_limit': limit, 'live_model': True, 'route': page}


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


def _stoppable(infer):
    """Let a stop signal end the wait for a relayed reply.

    The relay provider waits for a reply file for up to 30 minutes. Its wait
    runs in a helper thread, so that a stop of the application is not held up.
    """
    def call(payload, schema):
        if stop_requested():
            raise RouteError('stopped')
        box = {}

        def work():
            try:
                box['result'] = infer(payload, schema)
            except BaseException as error:   # noqa: BLE001  (handed to the caller below)
                box['error'] = error

        worker = threading.Thread(target=work, name='relay-wait', daemon=True)
        worker.start()
        while worker.is_alive():
            worker.join(0.2)
            if stop_requested() and worker.is_alive():
                raise RouteError('stopped', 'The application is stopping. The wait for the relayed reply was ended.')
        if 'error' in box:
            raise box['error']
        return box['result']

    return call


def _relay_build(config, *, api_key=None, record_dir=None, relay_dir=None):
    from feedctrl import demo_providers
    if relay_dir is None:
        reject('The relay route needs a new folder for its request and reply files.',
               'Start the application with the launcher; it makes a new relay folder for each run.')
    spool = Path(relay_dir)
    try:
        spool.mkdir(parents=True, exist_ok=True)
        infer, identity, receipts = demo_providers.relay_provider(
            spool, declared_model=config['declared_model'], transport_note=config['transport_note'],
            max_calls=config['max_calls'], timeout=config['timeout_seconds'])
    except OSError as error:
        reject(f'The relay folder {spool} cannot be used ({type(error).__name__}).',
               'Give a new folder with --relay-dir, or leave the option out.')
    except ValueError as error:
        if 'empty folder' in str(error):
            reject(f'The relay folder {spool} is not empty.',
                   'Give a new folder with --relay-dir, or leave the option out: the launcher then makes a new folder.')
        reject(str(error))
    return _stoppable(infer), identity, receipts


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


def check_route(config, *, api_key=None, test_call=True, out=print, key_error=None):
    """Check a route step by step and print each result in ASCII.

    Steps: the configuration, the credential when one is needed, the endpoint or
    program, and then one very small structured request. Return
    ``{'ok': bool, 'steps': [{'name', 'ok', 'detail', 'action'}]}``. ``ok`` is
    true only when every step passed. ``key_error`` is the ``RouteError`` of a
    key that could not be read; its message is shown in the credential step.
    Every printed and returned text passes the scrubber.
    """
    steps = []
    remember_secret(api_key)

    def step(name, ok, detail, action=''):
        entry = {'name': name, 'ok': bool(ok), 'detail': ascii_text(one_line(scrub(detail))),
                 'action': '' if ok else ascii_text(one_line(scrub(action)))}
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
            if isinstance(key_error, RouteError):
                step('credential', False, key_error.message, key_error.action)
            else:
                step('credential', False, f'The environment variable {name} is not set.',
                     f'Set {name} to your API key in this terminal, then run the check again.')
            return finish()
        step('credential', True, f'A key was read from {name}. It is not shown and not stored.'
             + (' The value is very short for an API key; a local server accepts any value.' if len(api_key) < 16 else ''))
    try:
        reachable = adapter.check(config, api_key=api_key, step=step)
    except RouteError as error:
        step('endpoint', False, error.message, error.action)
        reachable = False
    except Exception as error:   # noqa: BLE001  (a defect of the check must end as one line, not as a trace)
        step('endpoint', False, f'The check failed in an unexpected way ({type(error).__name__}).',
             CATEGORIES['route_failed'][1])
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
        receipt = receipts[-1]
        reported = receipt.get('reported_model') or ', '.join(receipt.get('reported_models') or []) or 'not reported'
        rule = receipt.get('model_match_rule')
        if reply == {'ok': True}:
            step('test call', True, f'The model returned the requested JSON object in {seconds:.1f} s. '
                                    f'Model reported by the reply: {reported}'
                                    + (f' (accepted as the requested model by the rule "{rule}")' if rule else '') + '.')
        else:
            step('test call', False, 'The reply was valid JSON but did not hold "ok": true.',
                 'The model does not follow a simple instruction. Use a stronger model.')
    except RouteError as error:
        step('test call', False, error.message, error.action)
    return finish()
