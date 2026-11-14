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

The flags were read in the Claude Code CLI reference on 14 November 2026 (UTC).
The real CLI was not run from the workspace where this was written: the tests
use a stand-in program that prints the same kind of result object.
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

from feedctrl import model_routes as routes
from feedctrl.model_adapters import _json
from feedctrl.model_routes import RouteError

# The request text is on standard input; this short argument only says so. It
# holds letters and spaces only, because a Windows command shim hands arguments
# to cmd.exe, which gives a meaning to many other characters.
QUERY = 'Follow the instructions in the input and reply with exactly one JSON object and nothing else'
OMITTABLE = ('--max-turns', '--safe-mode', '--no-session-persistence', '--permission-mode', '--no-chrome',
             '--tools', '--disallowedTools')
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
# What a signed-in program needs to find its own files, a proxy and its certificates.
# No variable that holds an API key is in this list.
ENV_ALLOW = ('SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC', 'PATHEXT', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA',
             'USERPROFILE', 'USERNAME', 'HOMEDRIVE', 'HOMEPATH', 'HOME', 'USER', 'LOGNAME', 'SHELL', 'PATH',
             'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM', '__CF_USER_TEXT_ENCODING',
             'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'XDG_RUNTIME_DIR',
             'CLAUDE_CONFIG_DIR', 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY', 'https_proxy', 'http_proxy', 'no_proxy',
             'SSL_CERT_FILE', 'SSL_CERT_DIR', 'NODE_EXTRA_CA_CERTS')
_SHELL_MEANING = set('&|<>^%!"\r\n')
_SIGN_IN_WORDS = ('/login', 'log in', 'logged in', 'not logged', 'sign in', 'signed in', 'authenticat', 'api key',
                  'oauth', 'credential')


def resolve_program(command):
    """The full path of a program, from a path or from a name on PATH; ``None`` when it is not found."""
    if os.path.isabs(command) or os.sep in command or (os.altsep and os.altsep in command):
        return command if Path(command).is_file() else None
    return shutil.which(command)


def is_shim(executable):
    return Path(executable).suffix.lower() in ('.cmd', '.bat')


def environment(config):
    names = (*ENV_ALLOW, *(config.get('pass_environment') or []))
    return {name: os.environ[name] for name in names if name in os.environ}


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
    """Run one program once. Return ``(exit code, standard output, standard error)``."""
    own_group = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt'
                 else {'start_new_session': True})
    name = routes.ascii_text(Path(argv[0]).name)
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=cwd, env=env, **own_group)
    except FileNotFoundError:
        raise RouteError('cli_not_found', f'The program "{name}" was not found.') from None
    except OSError as error:
        raise RouteError('cli_failed', f'The program "{name}" could not be started ({type(error).__name__}).') from None
    try:
        out, err = process.communicate(data, timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        try:
            process.communicate(timeout=10)
        except (subprocess.SubprocessError, OSError, ValueError):
            pass
        raise RouteError('timeout', f'The program "{name}" did not finish within {timeout:g} s. It was stopped.') from None
    if len(out) > limit:
        raise RouteError('reply_too_large', f'The program "{name}" wrote more than {limit} bytes.')
    return process.returncode, out, err


def _tail(raw, clean):
    lines = [line.strip() for line in raw.decode('utf-8', 'replace').splitlines() if line.strip()]
    return routes.ascii_text(routes.one_line(clean(lines[-1]), 300)) if lines else ''


def _lenient_object(raw):
    try:
        value = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


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
        return {'profile': profile, 'argv': list(argv), 'model': model, 'pass_environment': passed, **limits}
    routes.take(raw, common | {'command', 'effort', 'structured_output', 'max_budget_usd', 'omit_flags', 'extra_args',
                               'allow_reported_model_mismatch'}, 'cli (profile claude-code)')
    omit = sorted(set(routes.list_setting(raw, 'omit_flags', len(OMITTABLE), 40)))
    if set(omit) - set(OMITTABLE):
        routes.reject('The setting "omit_flags" can name only: ' + ', '.join(OMITTABLE) + '.')
    return {'profile': profile, 'command': routes.text_setting(raw, 'command', 500, default='claude'), 'model': model,
            'effort': routes.choice_setting(raw, 'effort', (None, *EFFORTS), None),
            'structured_output': routes.choice_setting(raw, 'structured_output', ('prompt', 'json_schema'), 'prompt'),
            'max_budget_usd': routes.number_setting(raw, 'max_budget_usd', 0.01, 1000, None, integer=False),
            'omit_flags': _empty_to_none(omit),
            'extra_args': _empty_to_none(routes.list_setting(raw, 'extra_args', 20, 500)),
            'allow_reported_model_mismatch': routes.flag_setting(raw, 'allow_reported_model_mismatch') or None,
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
    # reliable through a Windows command shim; there one deny rule removes every tool.
    if is_shim(executable):
        if '--disallowedTools' not in omit:
            args += ['--disallowedTools', '*']
    else:
        if '--tools' not in omit:
            args += ['--tools', '']
        if '--disallowedTools' not in omit:
            args += ['--disallowedTools', 'mcp__*']
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
        raise RouteError('cli_not_found', f'The program "{routes.ascii_text(config["command"])}" was not found.',
                         'Install the Claude Code CLI, or put the full path of the program in "command" in the route file.')
    if is_shim(executable):
        if config['structured_output'] == 'json_schema':
            routes.reject('"structured_output": "json_schema" puts the schema on the command line. '
                          'That is not safe through a .cmd or .bat file.',
                          'Set "structured_output" to "prompt", or put the full path of the program file itself in "command".')
        risky = [part for part in (config['model'], *(config.get('extra_args') or [])) if set(part) & _SHELL_MEANING]
        if risky:
            routes.reject('A value for the command line holds a character that cmd.exe gives a meaning to.',
                          'Remove the characters & | < > ^ % ! " from "extra_args", or use the program file itself.')
    return executable


# --------------------------------------------------------------------------
# Claude Code CLI, print mode
# --------------------------------------------------------------------------

def _claude_failure(code, envelope, err, config, clean):
    """Say why a call failed, from the exit code, the result object and standard error."""
    error_text = err.decode('utf-8', 'replace')
    option = re.search(r"unknown option '?(--?[A-Za-z][A-Za-z0-9-]*)'?", error_text, re.I)
    if option:
        flag = option.group(1)
        return RouteError('cli_failed', f'This version of the CLI does not know the option {flag}.',
                          f'Update the CLI, or add "{flag}" to "omit_flags" in the route file.' if flag in OMITTABLE else
                          f'Update the CLI, or remove {flag} from "extra_args" and the settings that add it.')
    result = envelope.get('result') if envelope and isinstance(envelope.get('result'), str) else ''
    subtype = envelope.get('subtype') if envelope else None
    shown = routes.ascii_text(routes.one_line(clean(result), 200)) or _tail(err, clean) or 'no message'
    if any(word in (result + ' ' + error_text).lower() for word in _SIGN_IN_WORDS):
        return RouteError('cli_not_signed_in', f'The CLI did not accept its sign-in state: {shown}',
                          'Run "claude auth login" in a terminal (or start "claude" once and sign in), then try again.')
    if subtype == 'error_max_turns':
        return RouteError('cli_failed', 'The CLI stopped at its turn limit before it gave an answer.',
                          'Try again. If it continues, add "--max-turns" to "omit_flags" in the route file.')
    if subtype == 'error_max_budget_usd':
        return RouteError('cli_failed', 'The CLI stopped at the cost limit of this call.',
                          'Raise "max_budget_usd" in the route file.')
    return RouteError('cli_failed', f'The CLI ended with exit code {code}: {shown}')


def _claude_build(config, record_dir):
    executable = _claude_program(config)
    clean = routes.scrubber()
    recorder, receipts = routes.Recorder(record_dir), []
    allowance = routes.CallAllowance(config['max_calls'])
    mode, model = config['structured_output'], config['model']

    def transport(ordinal, payload, schema, receipt):
        prompt = routes.render_prompt(payload, schema).encode('utf-8')
        if len(prompt) > config['max_request_bytes']:
            raise RouteError('bad_request', f'The request has {len(prompt)} bytes. The limit of this route is '
                             f'{config["max_request_bytes"]} bytes. Nothing was sent and nothing was cut.',
                             'Choose a smaller evidence scope, or raise "max_request_bytes" in the route file.')
        schema_text = _json(schema).decode('utf-8') if mode == 'json_schema' else None
        args = claude_arguments(config, executable, schema_text)
        recorder.write(ordinal, 'stdin.txt', prompt)
        receipt.update(program=routes.ascii_text(Path(executable).name), structured_output=mode,
                       arguments=['<schema>' if part == schema_text else part for part in args],
                       stdin_sha256=hashlib.sha256(prompt).hexdigest(), stdin_bytes=len(prompt),
                       passed_environment_names=sorted(environment(config)))
        # An empty folder: the CLI then finds no project instructions, hooks or servers.
        with tempfile.TemporaryDirectory(prefix='feedctrl-cli-', ignore_cleanup_errors=True) as workdir:
            code, out, err = run_program([executable, *args], prompt, environment(config), workdir,
                                         config['timeout_seconds'], config['max_response_bytes'])
        recorder.write(ordinal, 'stdout.txt', out)
        recorder.write(ordinal, 'stderr.txt', err)
        receipt.update(exit_code=code, stdout_sha256=hashlib.sha256(out).hexdigest(), stdout_bytes=len(out))
        envelope = _lenient_object(out)
        if envelope is not None:
            models = sorted(name for name in envelope['modelUsage'] if isinstance(name, str)) \
                if isinstance(envelope.get('modelUsage'), dict) else []
            receipt.update(
                cli_result={name: envelope[name] for name in ('type', 'subtype', 'is_error', 'num_turns', 'stop_reason',
                                                              'duration_ms')
                            if type(envelope.get(name)) in (bool, int) or (isinstance(envelope.get(name), str)
                                                                             and len(envelope[name]) <= 60)},
                usage=routes.bounded_counts(envelope.get('usage'), ('input_tokens', 'output_tokens',
                                                                    'cache_creation_input_tokens', 'cache_read_input_tokens')),
                reported_models=[routes.ascii_text(routes.one_line(name, 200)) for name in models][:10],
                reported_model=next((name for name in models if routes.model_matches(model, name)), None))
            if type(envelope.get('total_cost_usd')) in (int, float) and 0 <= envelope['total_cost_usd'] < 1e6:
                receipt.update(estimated_cost_usd=envelope['total_cost_usd'],
                               estimated_cost_note='estimate of the CLI, not a bill')
        if (code != 0 or envelope is None or envelope.get('type') != 'result' or envelope.get('subtype') != 'success'
                or envelope.get('is_error') is not False):
            if code == 0 and envelope is None:
                raise RouteError('unexpected_reply', 'The CLI output was not one JSON result object.',
                                 'Check that "command" is the Claude Code CLI. Run the check.')
            raise _claude_failure(code, envelope, err, config, clean)
        if not config.get('allow_reported_model_mismatch') and receipt['reported_model'] is None:
            raise RouteError('model_mismatch', f'The route file names the model "{model}", and the CLI reports '
                             + (', '.join(receipt['reported_models']) or 'no model name') + '.',
                             'Put the reported full name in "model" (not a short alias), or set '
                             '"allow_reported_model_mismatch" to true to accept and record the difference.')
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
        raise RouteError('cli_not_found', f'The program "{routes.ascii_text(config["argv"][0])}" was not found.',
                         'Install it, or put its full path first in "argv" in the route file.')
    return program


def _generic_build(config, record_dir):
    argv = [_generic_program(config), *config['argv'][1:]]
    clean = routes.scrubber()
    recorder, receipts = routes.Recorder(record_dir), []
    allowance = routes.CallAllowance(config['max_calls'])

    def transport(ordinal, payload, schema, receipt):
        prompt = routes.render_prompt(payload, schema).encode('utf-8')
        if len(prompt) > config['max_request_bytes']:
            raise RouteError('bad_request', f'The request has {len(prompt)} bytes. The limit of this route is '
                             f'{config["max_request_bytes"]} bytes. Nothing was sent and nothing was cut.',
                             'Choose a smaller evidence scope, or raise "max_request_bytes" in the route file.')
        recorder.write(ordinal, 'stdin.txt', prompt)
        receipt.update(program=routes.ascii_text(Path(argv[0]).name), stdin_sha256=hashlib.sha256(prompt).hexdigest(),
                       stdin_bytes=len(prompt), passed_environment_names=sorted(environment(config)))
        code, out, err = run_program(argv, prompt, environment(config), None, config['timeout_seconds'],
                                     config['max_response_bytes'])
        recorder.write(ordinal, 'stdout.txt', out)
        recorder.write(ordinal, 'stderr.txt', err)
        receipt.update(exit_code=code, stdout_sha256=hashlib.sha256(out).hexdigest(), stdout_bytes=len(out))
        if code != 0:
            raise RouteError('cli_failed', f'The program ended with exit code {code}: {_tail(err, clean) or "no message"}')
        try:
            return out.decode('utf-8')
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
    clean = routes.scrubber()
    try:
        if config['profile'] == 'generic':
            program = _generic_program(config)
            step('program', True, f'The program was found: {routes.ascii_text(Path(program).name)}.')
            return True
        executable = _claude_program(config)
        code, out, err = run_program([executable, '--version'], b'', environment(config), None, 30, 100_000)
    except RouteError as error:
        step('program', False, error.message, error.action)
        return False
    name = routes.ascii_text(Path(executable).name)
    if code != 0:
        step('program', False, f'"{name} --version" ended with exit code {code}: {_tail(err, clean) or "no message"}',
             'Check that "command" in the route file is the Claude Code CLI.')
        return False
    step('program', True, f'{name} answered. Version: {_tail(out, clean) or "not printed"}.')
    try:
        code, out, err = run_program([executable, 'auth', 'status'], b'', environment(config), None, 30, 100_000)
    except RouteError:
        step('sign-in', True, 'The sign-in state could not be read with this CLI version. The test call decides.')
        return True
    state = _lenient_object(out)
    if code == 0:
        method = state.get('authMethod') if state else None
        step('sign-in', True, 'The CLI reports that it is signed in'
             + (f' (method: {routes.ascii_text(routes.one_line(method, 40))})' if isinstance(method, str) else '') + '.')
        return True
    if code == 1 and (state is not None or any(word in (out + err).decode('utf-8', 'replace').lower()
                                               for word in _SIGN_IN_WORDS)):
        step('sign-in', False, 'The CLI reports that it is not signed in.',
             'Run "claude auth login" in a terminal (or start "claude" once and sign in), then run the check again.')
        return False
    step('sign-in', True, 'This CLI version did not report a sign-in state. The test call decides.')
    return True


def _cli_describe(config):
    if config['profile'] == 'generic':
        return ['Program: ' + ' '.join(config['argv']), f'Model, as declared in the route file: {config["model"]}',
                f'{config["timeout_seconds"]:g} s for one call; the prompt goes to standard input']
    lines = [f'Program: {config["command"]} (Claude Code CLI, print mode, one process for each call)',
             f'Model: {config["model"]}' + (f'; effort {config["effort"]}' if config.get('effort') else ''),
             f'Structured output: {config["structured_output"]}; {config["timeout_seconds"]:g} s for one call']
    if config.get('omit_flags') or config.get('extra_args'):
        lines.append('Flags left out: ' + (', '.join(config.get('omit_flags') or []) or 'none')
                     + '; added: ' + (' '.join(config.get('extra_args') or []) or 'none'))
    return lines


routes.register_route('cli', routes.RouteAdapter(_cli_validate, _cli_build, _cli_check, _cli_describe,
                                                 lambda config: None))
