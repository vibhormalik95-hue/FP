"""CLI routes: a program on this computer answers each request.

Two profiles exist.

``claude-code``  The Claude Code CLI in print mode with ``--output-format json``.
                 The whole request goes to standard input. The default flags are
                 a small documented set: one turn, no tools, no customisations of
                 the user, no saved session.
``generic``      Any program that reads a prompt on standard input and writes the
                 reply to standard output.

Each call starts one process and never a second one. The program gets a reduced
environment, so that an API key in the environment of the server does not
change which account the program uses. Name further variables in
``pass_environment`` when a program needs them.

A running program is ended, with the programs that it started, at the time
limit, when it writes more than the response limit, and when the application
stops. If the server process itself is killed by the system, it cannot end the
program; the program then runs to its own end.

The flags were read in the Claude Code CLI reference on 14 November 2026 (UTC).
The real CLI was not run from the workspace where this was written: the tests
use a stand-in program that prints the same kind of result object. Nothing
here was run on Windows or macOS.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from feedctrl import model_routes as routes
from feedctrl.model_adapters import _decode, _json
from feedctrl.model_routes import RouteError

# The request text is on standard input; this short argument only says so. It
# holds letters and spaces only, because a Windows command shim hands arguments
# to cmd.exe, which gives a meaning to many other characters.
QUERY = 'Follow the instructions in the input and reply with exactly one JSON object and nothing else'
# Flags that an older version of the CLI may not know. Without "--tools" the
# route denies every tool by a rule, so no setting can give the model a tool.
OMITTABLE = ('--max-turns', '--safe-mode', '--no-session-persistence', '--permission-mode', '--no-chrome', '--tools')
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
# "extra_args" is for a diagnostic flag such as --verbose. It cannot give the
# model a tool or a permission, change the model, the prompt, the session or
# the output format, or repeat a flag that the route sets itself.
PROTECTED_FLAGS = frozenset({
    '-p', '--print', '--output-format', '--input-format', '--json-schema', '--include-partial-messages',
    '--replay-user-messages', '--model', '--fallback-model', '--effort', '--max-turns', '--max-budget-usd',
    '--safe-mode', '--no-session-persistence', '--no-chrome', '--chrome', '--ide',
    '--tools', '--allowedTools', '--allowed-tools', '--disallowedTools', '--disallowed-tools',
    '--permission-mode', '--permission-prompt-tool', '--dangerously-skip-permissions',
    '--allow-dangerously-skip-permissions', '--add-dir', '--mcp-config', '--strict-mcp-config', '--plugin-dir',
    '--agents', '--agent', '--settings', '--setting-sources',
    '--system-prompt', '--system-prompt-file', '--append-system-prompt', '--append-system-prompt-file',
    '-c', '--continue', '-r', '--resume', '--session-id', '--fork-session', '--teleport', '--remote'})
# What a signed-in program needs to find its own files, a proxy and its certificates.
# No variable that holds an API key or a sign-in token is in this list.
ENV_ALLOW = ('SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC', 'PATHEXT', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA',
             'PROGRAMFILES', 'PROGRAMFILES(X86)', 'PROGRAMW6432', 'COMMONPROGRAMFILES', 'ALLUSERSPROFILE',
             'USERPROFILE', 'USERNAME', 'HOMEDRIVE', 'HOMEPATH', 'HOME', 'USER', 'LOGNAME', 'SHELL', 'PATH',
             'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM', '__CF_USER_TEXT_ENCODING',
             'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'XDG_RUNTIME_DIR',
             'CLAUDE_CONFIG_DIR', 'CLAUDE_CODE_GIT_BASH_PATH', 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY', 'https_proxy',
             'http_proxy', 'no_proxy', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'NODE_EXTRA_CA_CERTS')
# The prompt is UTF-8. A Python program on Windows reads standard input in the
# code page of the console unless it is told otherwise.
ENV_SET = {'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
ERROR_LIMIT = 1_000_000          # bytes of standard error that are kept
_SHELL_MEANING = set('&|<>^%!"\r\n')
_SHIM_ADVICE = ('Remove the characters & | < > ^ % ! " from the arguments, or put the program file itself '
                '(not the .cmd or .bat file) in the route file.')
# Words of the result text of a failed call, read in this order.
_OVERLOADED = ('overloaded', 'error: 529', 'error 529', 'error: 503', 'error 503', 'service unavailable')
_BILLING = ('credit balance', 'billing', 'payment required')
_LIMITED = ('usage limit', 'rate limit', 'rate_limit', 'limit reached', 'limit resets', 'too many requests',
            'error: 429', 'error 429')
_NOT_SIGNED_IN = ('not logged in', 'please run /login', 'run /login', 'invalid api key', 'authentication_error',
                  'token has expired', 'not authenticated', 'login required', 'please log in', 'please sign in',
                  'no credentials')
_SIGN_IN_ADVICE = ('Run "claude auth login" in a terminal (or start "claude" once and sign in), then try again. '
                   'If the CLI signs in through an environment variable, name that variable in "pass_environment" '
                   'in the route file.')


def resolve_program(command, *, os_name=None, which=shutil.which):
    """The full path of a program, from a path or from a name on PATH; ``None`` when it is not found.

    The result is absolute, because a call runs the program from another
    folder. ``~`` stands for the home folder. On Windows a path without an
    extension is completed to the program file beside it (``claude`` to
    ``claude.exe`` or ``claude.cmd``): the file without an extension that npm
    writes there is a shell text that Windows cannot start.
    """
    os_name = os.name if os_name is None else os_name
    expanded = os.path.expanduser(command)
    separators = ('/', '\\') if os_name == 'nt' else tuple(filter(None, (os.sep, os.altsep)))
    if os.path.isabs(expanded) or any(mark in expanded for mark in separators):
        full = os.path.abspath(expanded)
        if os_name == 'nt' and not Path(full).suffix:
            found = which(os.path.basename(full), path=os.path.dirname(full))
            return os.path.abspath(found) if found else None
        return full if Path(full).is_file() else None
    found = which(expanded)
    return os.path.abspath(found) if found else None


def is_shim(executable):
    return Path(executable).suffix.lower() in ('.cmd', '.bat')


def environment(config):
    names = (*ENV_ALLOW, *(config.get('pass_environment') or []))
    return {**ENV_SET, **{name: os.environ[name] for name in names if name in os.environ}}


def kill_tree(process):
    """Stop a program and the programs that it started. Best effort."""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        process.kill()
    except OSError:
        pass


def run_program(argv, data, env, cwd, timeout, limit):
    """Run one program once. Return ``(exit code, standard output, standard error)``.

    Both outputs are read while the program runs. Standard output over
    ``limit`` bytes ends the program. Standard error is kept up to a fixed size;
    the rest is read and dropped, so that the program is not held up. The
    program ends at the time limit and when the application stops.
    """
    own_group = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt'
                 else {'start_new_session': True})
    name = Path(argv[0]).name
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=cwd, env=env, **own_group)
    except FileNotFoundError:
        raise RouteError('cli_not_found', f'The program "{name}" was not found.') from None
    except OSError as error:
        raise RouteError('cli_failed', f'The program "{name}" could not be started ({type(error).__name__}).',
                         'Check that the route file names a program file. On Windows that is a .exe, .cmd or .bat '
                         'file; on macOS and Linux the file needs the permission to run.') from None
    state = {'out': bytearray(), 'err': bytearray(), 'err_cut': False, 'reason': None}

    def end(reason):
        if state['reason'] is None:
            state['reason'] = reason
        kill_tree(process)

    def feed():
        try:
            process.stdin.write(data)
        except (OSError, ValueError):
            pass   # the program ended or did not read its input
        finally:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass

    def read_output():
        try:
            while True:
                block = process.stdout.read1(65536)
                if not block:
                    return
                state['out'] += block[:limit + 1 - len(state['out'])]
                if len(state['out']) > limit:
                    end('flood')
                    return
        except (OSError, ValueError):
            pass

    def read_error():
        try:
            while True:
                block = process.stderr.read1(65536)
                if not block:
                    return
                room = ERROR_LIMIT - len(state['err'])
                state['err'] += block[:max(room, 0)]
                state['err_cut'] = state['err_cut'] or len(block) > room
        except (OSError, ValueError):
            pass

    workers = [threading.Thread(target=work, daemon=True) for work in (feed, read_output, read_error)]
    deadline = time.monotonic() + timeout
    token = routes.watch(end, deadline)   # the watcher also ends the program when the application exits
    for worker in workers:
        worker.start()
    try:
        while True:
            try:
                process.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                if routes.stop_requested():
                    end('stop')
                elif time.monotonic() >= deadline:
                    end('deadline')
    except BaseException:
        # Ctrl+C in the thread that waits (a program such as the route trial):
        # the program runs in its own session, so no signal reached it.
        end('stop')
        raise
    finally:
        routes.unwatch(token)
    for worker in workers:
        worker.join(timeout=5)
    if any(worker.is_alive() for worker in workers):
        # The program ended, but a program that it started still holds its output open.
        kill_tree(process)
        for worker in workers:
            worker.join(timeout=5)
    if not any(worker.is_alive() for worker in workers):
        for stream in (process.stdout, process.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
    if state['reason'] == 'stop':
        raise RouteError('stopped', f'The application is stopping. The program "{name}" was stopped.')
    if state['reason'] == 'deadline':
        raise RouteError('timeout', f'The program "{name}" did not finish within {timeout:g} s. It was stopped.')
    if state['reason'] == 'flood':
        raise RouteError('reply_too_large', f'The program "{name}" wrote more than {limit} bytes. It was stopped.')
    error = bytes(state['err']) + (b'\n[standard error was cut at %d bytes]\n' % ERROR_LIMIT if state['err_cut'] else b'')
    return process.returncode, bytes(state['out']), error


def _lines(raw):
    return [line.strip() for line in raw.decode('utf-8', 'replace').splitlines() if line.strip()]


def _tail(raw):
    lines = _lines(raw)
    return routes.one_line(routes.scrub(lines[-1]), 300) if lines else ''


def _result_object(raw):
    """``(object, problem)`` for the output of the CLI, read by the one reply rule.

    ``problem`` is ``None``, ``'not_json'`` (the output is not one JSON object)
    or ``'not_strict'`` (it repeats a key, or holds a number that is not finite).
    A byte-order mark before the object is accepted, as it is for a relayed reply.
    """
    try:
        value = _decode(raw.decode('utf-8-sig'))
    except json.JSONDecodeError:
        return None, 'not_json'
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None, 'not_strict'
    return (value, None) if isinstance(value, dict) else (None, 'not_json')


def _lenient_object(raw):
    """The output as JSON without the strict rule. Only for the text of a failure message."""
    try:
        value = json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _refuse_shell_characters(executable, parts):
    """A .cmd or .bat file hands its arguments to cmd.exe; refuse what cmd.exe would read as a command."""
    if is_shim(executable) and any(set(part) & _SHELL_MEANING for part in parts):
        routes.reject('A value for the command line holds a character that cmd.exe gives a meaning to.', _SHIM_ADVICE)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def _empty_to_none(value):
    return value or None


def _cli_validate(raw):
    profile = routes.choice_setting(raw, 'profile', ('claude-code', 'generic'), None)
    common = {'route', 'profile', 'model', 'pass_environment', 'max_calls', 'timeout_seconds', 'max_request_bytes',
              'max_response_bytes'}
    limits = routes.common_limits(raw, timeout=600)
    passed = _empty_to_none(sorted(set(routes.list_setting(raw, 'pass_environment', 20, 64, pattern=routes.ENV_NAME))))
    model = routes.text_setting(raw, 'model', 200, pattern=routes.MODEL_NAME)
    if profile == 'generic':
        routes.take(raw, common | {'argv'}, 'cli (profile generic)')
        argv = raw.get('argv')
        if (not isinstance(argv, list) or not 1 <= len(argv) <= 40
                or any(not isinstance(part, str) or len(part) > 2000 or any(ord(char) < 32 for char in part) for part in argv)
                or not argv[0].strip()):
            routes.reject('The setting "argv" must be the program and its arguments as a list of texts, '
                          'for example ["ollama", "run", "llama3.1:8b", "--format", "json"].')
        routes.refuse_key_arguments(argv[1:], 'argv')
        return {'profile': profile, 'argv': list(argv), 'model': model, 'pass_environment': passed, **limits}
    routes.take(raw, common | {'command', 'effort', 'structured_output', 'max_budget_usd', 'omit_flags', 'extra_args',
                               'allow_reported_model_mismatch', 'accept_reported_models'}, 'cli (profile claude-code)')
    omit = sorted(set(routes.list_setting(raw, 'omit_flags', len(OMITTABLE), 40)))
    if set(omit) - set(OMITTABLE):
        routes.reject('The setting "omit_flags" can name only: ' + ', '.join(OMITTABLE) + '.',
                      'A flag that removes the tools of the model cannot be left out.')
    extra = routes.list_setting(raw, 'extra_args', 20, 500)
    routes.refuse_key_arguments(extra, 'extra_args')
    for part in extra:
        flag = part.split('=', 1)[0]
        if flag in PROTECTED_FLAGS:
            routes.reject(f'The setting "extra_args" must not hold {flag}.',
                          'The route sets the model, the output format, the prompt and the session itself, and it gives '
                          'the model no tool and no permission. Use the settings of the route file for the model, the '
                          'effort and the limits.')
    return {'profile': profile, 'command': routes.text_setting(raw, 'command', 500, default='claude'), 'model': model,
            'effort': routes.choice_setting(raw, 'effort', (None, *EFFORTS), None),
            'structured_output': routes.choice_setting(raw, 'structured_output', ('prompt', 'json_schema'), 'prompt'),
            'max_budget_usd': routes.number_setting(raw, 'max_budget_usd', 0.01, 1000, None, integer=False),
            'omit_flags': _empty_to_none(omit),
            'extra_args': _empty_to_none(extra),
            'allow_reported_model_mismatch': routes.flag_setting(raw, 'allow_reported_model_mismatch') or None,
            'accept_reported_models': routes.accepted_models_setting(raw),
            'pass_environment': passed, **limits}


def claude_arguments(config, executable, schema_text=None):
    """The arguments for one print-mode call. The request text is never among them."""
    omit = set(config.get('omit_flags') or [])
    args = ['-p', QUERY, '--output-format', 'json', '--model', config['model']]
    # The structured-output step of the CLI can need a turn of its own.
    turns = '1' if schema_text is None else '3'
    for flag, value in (('--max-turns', turns), ('--safe-mode', None), ('--no-session-persistence', None),
                        ('--permission-mode', 'dontAsk'), ('--no-chrome', None)):
        if flag not in omit:
            args += [flag] if value is None else [flag, value]
    # The model only writes text, so it gets no tools. An empty argument is not
    # reliable through a Windows command shim, and an older CLI may not know
    # "--tools"; in both cases one deny rule removes every tool.
    if is_shim(executable) or '--tools' in omit:
        args += ['--disallowedTools', '*']
    else:
        args += ['--tools', '', '--disallowedTools', 'mcp__*']
    if config.get('effort'):
        args += ['--effort', config['effort']]
    if config.get('max_budget_usd') is not None:
        args += ['--max-budget-usd', f'{config["max_budget_usd"]:g}']
    if schema_text is not None:
        args += ['--json-schema', schema_text]
    return args + list(config.get('extra_args') or [])


def _claude_program(config):
    executable = resolve_program(config['command'])
    if executable is None:
        raise RouteError('cli_not_found', f'The program "{config["command"]}" was not found.',
                         'Install the Claude Code CLI, or put the full path of the program in "command" in the route file.')
    if is_shim(executable):
        if config['structured_output'] == 'json_schema':
            routes.reject('"structured_output": "json_schema" puts the schema on the command line. '
                          'That is not safe through a .cmd or .bat file.',
                          'Set "structured_output" to "prompt", or put the full path of the program file itself in "command".')
        _refuse_shell_characters(executable, (config['model'], *(config.get('extra_args') or [])))
    return executable


# --------------------------------------------------------------------------
# Claude Code CLI, print mode
# --------------------------------------------------------------------------

def _claude_failure(code, envelope, err):
    """Say why a call failed, from the exit code, the result object and standard error.

    The cause is read from the result text of the failed call. Without a result
    object it is read from the last line that the program wrote. A word in a
    diagnostic line elsewhere does not decide the cause.
    """
    option = re.search(r"unknown option '?(--?[A-Za-z][A-Za-z0-9-]*)'?", err.decode('utf-8', 'replace'), re.I)
    if option:
        flag = option.group(1)
        return RouteError('cli_failed', f'This version of the CLI does not know the option {flag}.',
                          f'Update the CLI, or add "{flag}" to "omit_flags" in the route file.' if flag in OMITTABLE else
                          f'Update the CLI, or remove {flag} from "extra_args" and the settings that add it.')
    result = envelope.get('result') if envelope and isinstance(envelope.get('result'), str) else ''
    subtype = envelope.get('subtype') if envelope else None
    shown = routes.one_line(routes.scrub(result), 200) or _tail(err) or 'no message'
    said = (result or (_lines(err) or [''])[-1]).lower()
    if subtype == 'error_max_turns':
        return RouteError('cli_failed', 'The CLI stopped at its turn limit before it gave an answer.',
                          'Try again. If it continues, add "--max-turns" to "omit_flags" in the route file.')
    if subtype == 'error_max_budget_usd':
        return RouteError('cli_failed', 'The CLI stopped at the cost limit of this call.',
                          'Raise "max_budget_usd" in the route file.')
    if any(word in said for word in _OVERLOADED):
        return RouteError('provider_overloaded', f'The CLI reports that the provider is overloaded: {shown}')
    if any(word in said for word in _BILLING):
        return RouteError('billing', f'The CLI reports a billing problem of the account: {shown}')
    if any(word in said for word in _LIMITED):
        return RouteError('rate_limited', f'The CLI reports a usage or rate limit of the account: {shown}',
                          'Wait until the limit resets, or use another route.')
    if any(word in said for word in _NOT_SIGNED_IN):
        return RouteError('cli_not_signed_in', f'The CLI did not accept its sign-in state: {shown}', _SIGN_IN_ADVICE)
    return RouteError('cli_failed', f'The CLI ended with exit code {code}: {shown}')


def _answer_model(envelope, config):
    """``(names, the reported name that stands for the requested model, rule, problem)``.

    The CLI reports each model that it used, with its output tokens. The
    requested model must be among them, and when several are reported it must
    be the one with the most output tokens: a helper model may take part, but a
    fallback model that wrote the answer is another model.
    """
    usage = envelope.get('modelUsage') if isinstance(envelope.get('modelUsage'), dict) else {}
    written = {name: (entry.get('outputTokens') if isinstance(entry, dict) and type(entry.get('outputTokens')) is int
                      and entry['outputTokens'] >= 0 else 0)
               for name, entry in usage.items() if isinstance(name, str)}
    names = sorted(written)
    model, accepted = config['model'], config.get('accept_reported_models')
    for wanted in ('equal', 'default_tag', 'dated_snapshot', 'accepted_by_setting'):
        for name in names:
            if routes.model_rule(model, name, accepted) != wanted:
                continue
            others = {other: count for other, count in written.items() if other != name}
            if others and max(others.values()) >= written[name]:
                most = max(others, key=others.get)
                return names, None, None, (f'The CLI reports several models. "{most}" wrote {others[most]} output '
                                           f'tokens and the requested "{model}" wrote {written[name]}.')
            return names, name, wanted, None
    return names, None, None, (f'The route file names the model "{model}", and the CLI reports '
                               + (', '.join(names) or 'no model name') + '.')


def _claude_build(config, record_dir):
    executable = _claude_program(config)
    recorder, receipts = routes.Recorder(record_dir), []
    allowance = routes.CallAllowance(config['max_calls'])
    mode = config['structured_output']

    def transport(ordinal, payload, schema, receipt):
        prompt = routes.render_prompt(payload, schema).encode('utf-8')
        if len(prompt) > config['max_request_bytes']:
            raise RouteError('bad_request', f'The request has {len(prompt)} bytes. The limit of this route is '
                             f'{config["max_request_bytes"]} bytes. Nothing was sent and nothing was cut.',
                             'Choose a smaller evidence scope, or raise "max_request_bytes" in the route file.')
        schema_text = _json(schema).decode('utf-8') if mode == 'json_schema' else None
        args = claude_arguments(config, executable, schema_text)
        recorder.write(ordinal, 'stdin.txt', prompt)
        receipt.update(program=Path(executable).name, structured_output=mode,
                       arguments=['<schema>' if part == schema_text else part for part in args],
                       stdin_sha256=hashlib.sha256(prompt).hexdigest(), stdin_bytes=len(prompt),
                       passed_environment_names=sorted(environment(config)))
        # An empty folder: the CLI then finds no project instructions, hooks or servers.
        with tempfile.TemporaryDirectory(prefix='feedctrl-cli-', ignore_cleanup_errors=True) as workdir:
            code, out, err = run_program([executable, *args], prompt, environment(config), workdir,
                                         config['timeout_seconds'], config['max_response_bytes'])
        recorder.write_after(ordinal, 'stdout.txt', out, receipt)
        recorder.write_after(ordinal, 'stderr.txt', err, receipt)
        receipt.update(exit_code=code, stdout_sha256=hashlib.sha256(out).hexdigest(), stdout_bytes=len(out))
        envelope, problem = _result_object(out)
        if envelope is not None:
            names, answered, rule, mismatch = _answer_model(envelope, config)
            receipt.update(
                cli_result={name: envelope[name] for name in ('type', 'subtype', 'is_error', 'num_turns', 'stop_reason',
                                                              'duration_ms')
                            if type(envelope.get(name)) in (bool, int) or (isinstance(envelope.get(name), str)
                                                                             and len(envelope[name]) <= 60)},
                usage=routes.bounded_counts(envelope.get('usage'), ('input_tokens', 'output_tokens',
                                                                    'cache_creation_input_tokens', 'cache_read_input_tokens')),
                reported_models=[routes.one_line(name, 200) for name in names][:10],
                reported_model=answered, model_match_rule=rule)
            if type(envelope.get('total_cost_usd')) in (int, float) and 0 <= envelope['total_cost_usd'] < 1e6:
                receipt.update(estimated_cost_usd=envelope['total_cost_usd'],
                               estimated_cost_note='estimate of the CLI, not a bill')
        if (code != 0 or envelope is None or envelope.get('type') != 'result' or envelope.get('subtype') != 'success'
                or envelope.get('is_error') is not False):
            if code == 0 and problem == 'not_strict':
                raise RouteError('reply_not_json', 'The output of the CLI repeats a key or holds a number that is not finite.',
                                 'Try again, or set "structured_output" to "prompt" in the route file.')
            if code == 0 and envelope is None:
                first = routes.one_line(routes.scrub((_lines(out) or ['nothing'])[0]), 120)
                raise RouteError('unexpected_reply', f'The CLI output was not one JSON result object. It started with: {first}',
                                 'If that line is a notice of the CLI, remove its cause (for example update the CLI). '
                                 'Check that "command" is the Claude Code CLI, and run the check.')
            raise _claude_failure(code, envelope if envelope is not None else _lenient_object(out), err)
        if mismatch:
            if not config.get('allow_reported_model_mismatch'):
                raise RouteError('model_mismatch', mismatch,
                                 'Put the reported full name in "model" (not a short alias), or add it to '
                                 '"accept_reported_models". "allow_reported_model_mismatch": true accepts and records '
                                 'any difference.')
            receipt['model_match_rule'] = 'difference_allowed_by_setting'
        if mode == 'json_schema':
            if not isinstance(envelope.get('structured_output'), dict):
                raise RouteError('reply_not_json', 'The CLI returned no structured output. The model may have declined.')
            return _json(envelope['structured_output']).decode('utf-8')
        if not isinstance(envelope.get('result'), str):
            raise RouteError('reply_not_json', 'The CLI result holds no text.')
        return envelope['result']

    infer = routes.make_infer(config=config, transport=transport, recorder=recorder, receipts=receipts,
                              allowance=allowance, serial=True)
    identity = routes.identity_for(config, 'local-cli-claude-code',
                                   'Model name as requested; the models that the CLI reports for each call are in its '
                                   'receipt. One process for each call; the requests that the CLI itself sends are not '
                                   'counted. No attestation of weights or account.')
    return infer, identity, receipts


# --------------------------------------------------------------------------
# Any program: prompt on standard input, reply on standard output
# --------------------------------------------------------------------------

def _generic_program(config):
    program = resolve_program(config['argv'][0])
    if program is None:
        raise RouteError('cli_not_found', f'The program "{config["argv"][0]}" was not found.',
                         'Install it, or put its full path first in "argv" in the route file.')
    _refuse_shell_characters(program, config['argv'][1:])
    return program


def _generic_build(config, record_dir):
    argv = [_generic_program(config), *config['argv'][1:]]
    recorder, receipts = routes.Recorder(record_dir), []
    allowance = routes.CallAllowance(config['max_calls'])

    def transport(ordinal, payload, schema, receipt):
        prompt = routes.render_prompt(payload, schema).encode('utf-8')
        if len(prompt) > config['max_request_bytes']:
            raise RouteError('bad_request', f'The request has {len(prompt)} bytes. The limit of this route is '
                             f'{config["max_request_bytes"]} bytes. Nothing was sent and nothing was cut.',
                             'Choose a smaller evidence scope, or raise "max_request_bytes" in the route file.')
        recorder.write(ordinal, 'stdin.txt', prompt)
        receipt.update(program=Path(argv[0]).name, stdin_sha256=hashlib.sha256(prompt).hexdigest(),
                       stdin_bytes=len(prompt), passed_environment_names=sorted(environment(config)))
        code, out, err = run_program(argv, prompt, environment(config), None, config['timeout_seconds'],
                                     config['max_response_bytes'])
        recorder.write_after(ordinal, 'stdout.txt', out, receipt)
        recorder.write_after(ordinal, 'stderr.txt', err, receipt)
        receipt.update(exit_code=code, stdout_sha256=hashlib.sha256(out).hexdigest(), stdout_bytes=len(out))
        if code != 0:
            raise RouteError('cli_failed', f'The program ended with exit code {code}: {_tail(err) or "no message"}')
        try:
            return out.decode('utf-8-sig')   # a byte-order mark is accepted, as it is for a relayed reply
        except UnicodeDecodeError:
            raise RouteError('reply_not_json', 'The output of the program is not UTF-8 text.',
                             'Make the program write UTF-8.') from None

    infer = routes.make_infer(config=config, transport=transport, recorder=recorder, receipts=receipts,
                              allowance=allowance, serial=True)
    identity = routes.identity_for(config, 'local-cli-generic',
                                   'Model name as declared in the route file; the program does not report it. '
                                   'No attestation of the model.')
    return infer, identity, receipts


def _cli_build(config, *, api_key=None, record_dir=None, relay_dir=None):
    return (_generic_build if config['profile'] == 'generic' else _claude_build)(config, record_dir)


# --------------------------------------------------------------------------
# Check and description
# --------------------------------------------------------------------------

def _cli_check(config, *, api_key=None, step):
    try:
        if config['profile'] == 'generic':
            program = _generic_program(config)
            step('program', True, f'The program was found: {Path(program).name}.')
            return True
        executable = _claude_program(config)
        code, out, err = run_program([executable, '--version'], b'', environment(config), None, 30, 100_000)
    except RouteError as error:
        step('program', False, error.message, error.action)
        return False
    name = Path(executable).name
    if code != 0:
        step('program', False, f'"{name} --version" ended with exit code {code}: {_tail(err) or "no message"}',
             'Check that "command" in the route file is the Claude Code CLI.')
        return False
    step('program', True, f'{name} answered. Version: {_tail(out) or "not printed"}.')
    try:
        code, out, err = run_program([executable, 'auth', 'status'], b'', environment(config), None, 30, 100_000)
    except RouteError:
        step('sign-in', True, 'The sign-in state could not be read with this CLI version. The test call decides.')
        return True
    state = _lenient_object(out)
    if code == 0:
        method = state.get('authMethod') if state else None
        step('sign-in', True, 'The CLI reports that it is signed in'
             + (f' (method: {routes.one_line(method, 40)})' if isinstance(method, str) else '') + '.')
        return True
    said = ' '.join(_lines(out) + _lines(err)).lower()
    if code == 1 and ((state is not None and state.get('loggedIn') is False) or any(word in said for word in _NOT_SIGNED_IN)):
        step('sign-in', False, 'The CLI reports that it is not signed in.',
             _SIGN_IN_ADVICE.replace('then try again', 'then run the check again'))
        return False
    step('sign-in', True, 'This CLI version did not report a sign-in state. The test call decides.')
    return True


def _cli_describe(config):
    if config['profile'] == 'generic':
        return ['Program: ' + ' '.join(config['argv']), f'Model, as declared in the route file: {config["model"]}',
                f'{config["timeout_seconds"]:g} s for one call; the prompt goes to standard input as UTF-8']
    lines = [f'Program: {config["command"]} (Claude Code CLI, print mode, one process for each call)',
             f'Model: {config["model"]}' + (f'; effort {config["effort"]}' if config.get('effort') else ''),
             f'Structured output: {config["structured_output"]}; {config["timeout_seconds"]:g} s for one call']
    if config.get('omit_flags') or config.get('extra_args'):
        lines.append('Flags left out: ' + (', '.join(config.get('omit_flags') or []) or 'none')
                     + '; added: ' + (' '.join(config.get('extra_args') or []) or 'none'))
    if config.get('accept_reported_models'):
        lines.append('Reported model names that are accepted: ' + ', '.join(config['accept_reported_models']))
    return lines


routes.register_route('cli', routes.RouteAdapter(_cli_validate, _cli_build, _cli_check, _cli_describe,
                                                 lambda config: None))
