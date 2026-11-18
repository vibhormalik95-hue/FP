"""Choose, check and show the model route of the application.

    python scripts/model_route.py setup
        Answer a few questions. The answers are written to model-route.json.
        The file never holds an API key.

    python scripts/model_route.py check [--no-test-call]
        Confirm that the route works: the settings, the key when one is needed,
        the server or program, and one very small request to the model.

    python scripts/model_route.py show
        Print the route that the file selects.

"setup" also works without questions, for example:

    python scripts/model_route.py setup --route openai-compatible --preset ollama --model llama3.1:8b
    python scripts/model_route.py setup --route anthropic --model MODEL-NAME
    python scripts/model_route.py setup --route cli --profile claude-code --model MODEL-NAME
    python scripts/model_route.py setup --route relay --declared-model NAME --transport-note "by hand from a chat"

With options, "setup" writes the file and then runs the check, unless
--no-check is given. An API key is read from an environment variable when the
application starts, or typed into a hidden prompt. See docs/model-routes.md.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feedctrl import model_routes  # noqa: E402
from feedctrl.model_routes import RouteError  # noqa: E402

DEFAULT_PATH = ROOT / model_routes.DEFAULT_FILE
SERVERS = {'1': ('ollama', 'http://127.0.0.1:11434/v1'), '2': ('lm-studio', 'http://127.0.0.1:1234/v1')}
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
YES = ('y', 'yes')
TRIES = 8   # answers to one question; a script that feeds no usable answer must not loop for ever


def attempts():
    """Count the answers to one question. Stop after ``TRIES`` answers that cannot be used."""
    for _ in range(TRIES):
        yield
    raise SystemExit(f'No usable answer after {TRIES} tries. Nothing was written. Run the setup again.')


def split_windows(text):
    """Split a command line by the rules of Windows programs.

    Double quotes group words anywhere in an argument. A backslash is an
    ordinary character, except before a double quote.
    """
    parts, current, quoted, slashes, started = [], [], False, 0, False
    for char in text:
        if char == '\\':
            slashes, started = slashes + 1, True
            continue
        if char == '"':
            current.append('\\' * (slashes // 2))
            if slashes % 2:
                current.append('"')
            else:
                quoted = not quoted
            slashes, started = 0, True
            continue
        current.append('\\' * slashes)
        slashes = 0
        if char in ' \t' and not quoted:
            if started:
                parts.append(''.join(current))
            current, started = [], False
        else:
            current.append(char)
            started = True
    current.append('\\' * slashes)
    if quoted:
        raise ValueError('No closing quotation')
    if started:
        parts.append(''.join(current))
    return parts


def split_command(text, *, os_name=None):
    """A command line as a list. Quotes group words on every system."""
    try:
        parts = split_windows(text) if (os_name or os.name) == 'nt' else shlex.split(text)
    except ValueError:
        raise RouteError('configuration', 'The command line has a quotation mark that is not closed.',
                         'Type the command again. Put a path that holds a space in double quotes.') from None
    if not parts:
        raise RouteError('configuration', 'The command line is empty.', 'Type the program and its arguments.')
    return parts


def listed_models(config, key=None):
    """Model names that the endpoint lists, or an empty list. Never raises."""
    try:
        from feedctrl import route_http
        normal = model_routes.validate_config({**config, 'model': config.get('model') or 'placeholder'})
        if normal['route'] == 'anthropic' and not key:
            return []
        return route_http.model_names(normal, key)
    except Exception:   # noqa: BLE001  (a list of names is a help for the questions, never a reason to stop)
        return []


def choose(ask, out, question, choices, default='1'):
    """Ask until the answer is one of the numbered choices."""
    for _ in attempts():
        out(question)
        for number, label in choices:
            out(f'  {number}  {label}')
        answer = (ask(f'Choice [{default}]: ') or '').strip() or default
        if answer in dict(choices):
            return answer
        out('Type one of the numbers.')


def text(ask, question, default=None, *, out=None, problem=None):
    """Ask until the answer is not empty and ``problem(answer)`` finds nothing wrong.

    ``problem`` returns a sentence for the terminal, or ``None``. The sentence
    never repeats the answer: an answer can be a key that was pasted by mistake.
    """
    for _ in attempts():
        answer = (ask(f'{question}{f" [{default}]" if default else ""}: ') or '').strip() or (default or '')
        if not answer:
            continue
        found = problem(answer) if problem else None
        if not found:
            return answer
        if out:
            out(found)


def _model_problem(answer):
    if not model_routes.MODEL_NAME.fullmatch(answer):
        return 'That is not a model name. A model name has no space; type it as the provider or the server writes it.'
    try:
        model_routes.refuse_secrets(answer)
    except RouteError:
        return 'That looks like a key, not a model name. Type the model name.'
    return None


def ask_variable(ask, out, default=None):
    """The NAME of the environment variable that holds the key. A pasted key is never repeated."""
    def problem(answer):
        try:
            model_routes.key_env_setting({'api_key_env': answer})
        except RouteError:
            return ('That is not the name of an environment variable. Type the NAME, for example '
                    f'{default or "MY_PROVIDER_API_KEY"}. Do not type the key itself.')
        return None

    def cleaned(prompt):
        # "$NAME", "$env:NAME" and "%NAME%" are how a shell reads the variable; the name is the part inside.
        answer = (ask(prompt) or '').strip()
        for prefix in ('$env:', '$'):
            if answer.startswith(prefix):
                answer = answer[len(prefix):]
        return answer[1:-1] if len(answer) > 2 and answer[0] == answer[-1] == '%' else answer

    return text(cleaned, 'Name of the environment variable that holds your key', default, out=out, problem=problem)


def ask_address(ask, out, question):
    """``(address, whether an unencrypted connection to another computer was accepted)``."""
    for _ in attempts():
        answer = (ask(question + ': ') or '').strip()
        if not answer:
            continue
        try:
            return model_routes.url_setting({'base_url': answer}, 'base_url'), False
        except RouteError as error:
            if 'not this computer' not in error.message:
                out('That is not a usable address. Type it again, for example http://127.0.0.1:11434/v1 '
                    'or https://HOST/v1.')
                continue
        host = model_routes.address_host(answer) or 'that computer'
        out(f'The address uses http, and {model_routes.ascii_text(host)} is not this computer. '
            'The requests then travel without encryption.')
        if (ask('Accept an unencrypted connection? [y/N]: ') or '').strip().lower() in YES:
            return model_routes.url_setting({'base_url': answer}, 'base_url', allow_insecure=True), True


def pick_model(ask, out, names, example):
    names = names[:30]
    if not names:
        return text(ask, f'Exact model name (for example {example})', out=out, problem=_model_problem)
    out('The endpoint lists these models:')
    for number, name in enumerate(names, 1):
        out(f'  {number}  {model_routes.ascii_text(name)}')
    for _ in attempts():
        answer = text(ask, 'Number of the model, or another exact model name', out=out,
                      problem=lambda value: None if value.isdigit() else _model_problem(value))
        if not answer.isdigit():
            return answer
        if 1 <= int(answer) <= len(names):
            return names[int(answer) - 1]
        out(f'Type a number from 1 to {len(names)}, or an exact model name.')


def key_may_go(ask, out, name, host, purpose):
    """Name the host that would receive the key, and ask before anything is sent."""
    out(f'{purpose} sends the key from {name} to {model_routes.ascii_text(host)}.')
    return (ask('Continue? [y/N]: ') or '').strip().lower() in YES


def wizard(ask=input, out=print, environ=None, models=listed_models):
    """Ask the questions and return the raw settings. Nothing is written here."""
    environ = os.environ if environ is None else environ
    kind = choose(ask, out, 'How will the application reach a model?', [
        ('1', 'A command-line program on this computer (Claude Code CLI or another program)'),
        ('2', 'A hosted provider with my own API key (OpenAI-compatible API or the Anthropic API)'),
        ('3', 'A model server on this computer or on my network (Ollama, LM Studio or another OpenAI-compatible server)'),
        ('4', 'By hand: I carry each request to a chat application and bring the reply back (file relay)')])
    if kind == '1':
        which = choose(ask, out, 'Which program?', [('1', 'Claude Code CLI (the "claude" command, signed in to my own account)'),
                                                    ('2', 'Another program that reads a prompt on standard input')])
        if which == '1':
            config = {'route': 'cli', 'profile': 'claude-code', 'command': text(ask, 'Command or full path of the CLI', 'claude'),
                      'model': text(ask, 'Full model name, as the CLI reports it (not a short alias)', out=out,
                                    problem=_model_problem)}
            for _ in attempts():
                effort = (ask('Effort (low, medium, high, xhigh, max; empty = the default of the CLI): ') or '').strip()
                if not effort or effort in EFFORTS:
                    break
                out('Type one of: ' + ', '.join(EFFORTS) + '. Or type nothing for the default of the CLI.')
            if effort:
                config['effort'] = effort
            return config
        out('Example: ollama run llama3.1:8b --format json')
        out('Put a path that holds a space in double quotes.')
        for _ in attempts():
            try:
                argv = split_command(text(ask, 'The command line of the program'))
                model_routes.refuse_key_arguments(argv[1:], 'argv')
                model_routes.refuse_secrets(argv)
                break
            except RouteError as error:
                out(error.message + ' ' + error.action)
        return {'route': 'cli', 'profile': 'generic', 'argv': argv,
                'model': text(ask, 'Name of the model that this program uses (your declaration)', out=out,
                              problem=_model_problem)}
    if kind == '2':
        which = choose(ask, out, 'Which provider?', [('1', 'OpenAI API'), ('2', 'Anthropic API'),
                                                     ('3', 'Another provider with an OpenAI-compatible API')])
        if which == '2':
            config = {'route': 'anthropic', 'api_key_env': ask_variable(ask, out, 'ANTHROPIC_API_KEY')}
            host = 'api.anthropic.com'
        elif which == '1':
            config = {'route': 'openai-compatible', 'preset': 'openai', 'api_key_env': ask_variable(ask, out, 'OPENAI_API_KEY')}
            host = 'api.openai.com'
        else:
            address, insecure = ask_address(ask, out, 'Base address of the API, ending with /v1')
            config = {'route': 'openai-compatible', 'preset': 'custom', 'base_url': address}
            if insecure:
                config['allow_insecure_http'] = True
            # No default: the key of one provider must not go to another provider by a pressed Enter key.
            out('This provider has its own key. Name the variable that holds the key for this provider.')
            config['api_key_env'] = ask_variable(ask, out)
            host = model_routes.address_host(address) or address
        name = config['api_key_env']
        key = (environ.get(name) or '').strip()
        names = []
        if not key:
            out(f'{name} is not set in this terminal. The model names cannot be listed now.')
        elif key_may_go(ask, out, name, host, 'A list of the model names'):
            names = models(config, key)
            if not names:
                out('The endpoint gave no model list.')
        config['model'] = pick_model(ask, out, names, 'a name from the model list of the provider')
        if which == '2':
            workspace = (ask('Workspace ID, only for a key that is not bound to one workspace (empty = none): ') or '').strip()
            if workspace and model_routes.MODEL_NAME.fullmatch(workspace):
                config['anthropic_workspace_id'] = workspace
        return config
    if kind == '3':
        which = choose(ask, out, 'Which server?', [('1', 'Ollama (http://127.0.0.1:11434/v1)'),
                                                   ('2', 'LM Studio (http://127.0.0.1:1234/v1)'), ('3', 'Another address')])
        if which == '3':
            address, insecure = ask_address(ask, out, 'Base address of the server, ending with /v1')
            config = {'route': 'openai-compatible', 'preset': 'custom', 'base_url': address}
            if insecure:
                config['allow_insecure_http'] = True
        else:
            config = {'route': 'openai-compatible', 'preset': SERVERS[which][0], 'base_url': SERVERS[which][1]}
        names = models(config)
        if not names:
            out('The server did not answer with a model list. Start it, or type the name by hand.')
        config['model'] = pick_model(ask, out, names, 'llama3.1:8b')
        return config
    return {'route': 'relay', 'declared_model': text(ask, 'Name of the model that you will use (your declaration)'),
            'transport_note': text(ask, 'How a request reaches the model', 'copied by hand into a chat application')}


def from_flags(args):
    config = {'route': args.route}
    for name in ('preset', 'base_url', 'model', 'api_key_env', 'structured_output', 'profile', 'command',
                 'declared_model', 'transport_note', 'effort', 'max_calls', 'timeout_seconds', 'max_output_tokens'):
        if getattr(args, name) is not None:
            config[name] = getattr(args, name)
    if args.program:
        config['argv'] = split_command(args.program)
    for item in args.set or []:
        name, separator, value = item.partition('=')
        if not separator:
            raise SystemExit('--set needs NAME=VALUE, for example --set allow_insecure_http=true')
        try:
            config[name] = json.loads(value)
        except ValueError:
            config[name] = value
    return config


def read_key(config, interactive):
    """``(key, problem)`` for a check: from the environment, or a hidden prompt at a terminal."""
    try:
        return model_routes.resolve_api_key(config, ask=getpass.getpass if interactive else None), None
    except RouteError as error:
        return None, error


def run_check(config, *, test_call=True, out=print, interactive=None):
    interactive = sys.stdin.isatty() if interactive is None else interactive
    key, problem = read_key(config, interactive)
    return model_routes.check_route(config, api_key=key, key_error=problem, test_call=test_call, out=out)


def setup(args, ask=input, out=print):
    path = Path(args.file)
    shown = model_routes.ascii_text(path)
    if path.exists() and not args.yes:
        if args.route or (ask(f'{model_routes.ascii_text(path.name)} exists. Replace it? [y/N]: ') or '').strip().lower() not in YES:
            raise SystemExit(f'{shown} exists and was not changed. Add --yes to replace it.')
    try:
        config = model_routes.validate_config(from_flags(args) if args.route else wizard(ask, out))
        model_routes.save_config(path, config)
    except RouteError as error:
        raise SystemExit(model_routes.ascii_text(error)) from None
    out(f'\nWritten: {shown}')
    for line in model_routes.describe(config):
        out('  ' + line)
    name = model_routes.needs_api_key(config)
    host = model_routes.ascii_text(model_routes.address_host(config.get('base_url')) or 'the endpoint')
    if name:
        out('\nThe key is not in the file. Set it for this terminal before you start:')
        out(f'  Windows PowerShell:  $env:{name} = "paste-the-key-here"')
        out(f'  macOS or Linux:      export {name}="paste-the-key-here"')
        out('Or leave it unset: the check and the start then ask for the key with a hidden prompt.')
    if args.no_check:
        return 0
    if not args.route:
        question = (f'\nCheck the connection now? The check sends the key from {name} to {host}. [Y/n]: ' if name
                    else '\nCheck the connection now? [Y/n]: ')
        if (ask(question) or '').strip().lower() in ('n', 'no'):
            return 0
    out('')
    return 0 if run_check(config, out=out)['ok'] else 1


def check(args, out=print):
    try:
        config = model_routes.load_config(args.file)
    except RouteError as error:
        out('FAILED  configuration: ' + model_routes.ascii_text(error))
        return 1
    result = run_check(config, test_call=not args.no_test_call, out=out)
    out('\nResult: ' + verdict(result))
    return 0 if result['ok'] else 1


def verdict(result):
    """One sentence. "The route works" only after a real model answer to the test call."""
    if not result['ok']:
        return 'the route does not work yet. Read the lines marked FAILED.'
    if result.get('model_response'):
        unverified = result.get('unverified') or []
        return 'the route works: the model answered the test call.' + (
            f' (Not verified by its own step: {", ".join(unverified)}; the answer of the model shows that it works.)'
            if unverified else '')
    reason = {'skipped': 'the test call was not requested',
              'not_run': 'this route has no test call (an operator answers the relay)'}.get(result.get('test_call'),
                                                                                         'no test call was made')
    unverified = result.get('unverified') or []
    return ('no step failed, but the route is not proven to work: ' + reason + ', so no model answer was checked'
            + (f'; not verified: {", ".join(unverified)}' if unverified else '') + '.')


def show(args, out=print):
    try:
        config = model_routes.load_config(args.file)
    except RouteError as error:
        raise SystemExit(model_routes.ascii_text(error)) from None
    out(f'Route file: {model_routes.ascii_text(args.file)}')
    for line in model_routes.describe(config):
        out('  ' + line)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='model_route.py', description=__doc__.split('\n\n')[0])
    steps = parser.add_subparsers(dest='step', required=True)
    for name, function in (('setup', setup), ('check', check), ('show', show)):
        step = steps.add_parser(name)
        step.add_argument('--file', '--route-file', dest='file', default=str(DEFAULT_PATH),
                          help='the route file; default: model-route.json in the repository root')
        step.set_defaults(run=function)
        if name == 'check':
            step.add_argument('--no-test-call', action='store_true', help='do not send the small test request')
        if name == 'setup':
            step.add_argument('--yes', action='store_true', help='replace an existing route file')
            step.add_argument('--no-check', action='store_true', help='write the file and do not check the connection')
            step.add_argument('--route', choices=model_routes.ROUTE_KINDS, help='with this option no question is asked')
            step.add_argument('--preset', choices=('openai', 'ollama', 'lm-studio', 'custom'))
            step.add_argument('--base-url')
            step.add_argument('--model')
            step.add_argument('--api-key-env', help='NAME of the environment variable that holds the key')
            step.add_argument('--structured-output', choices=('json_schema', 'json_object', 'prompt'))
            step.add_argument('--profile', choices=('claude-code', 'generic'))
            step.add_argument('--command', help='the Claude Code CLI: a command name or a full path')
            step.add_argument('--program', help='profile generic: the whole command line in one quoted text')
            step.add_argument('--declared-model')
            step.add_argument('--transport-note')
            step.add_argument('--effort', choices=EFFORTS)
            step.add_argument('--max-calls', type=int)
            step.add_argument('--timeout-seconds', type=float)
            step.add_argument('--max-output-tokens', type=int)
            step.add_argument('--set', action='append', metavar='NAME=VALUE', help='any other setting; the value is JSON')
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except EOFError:
        # A question was asked and no terminal could answer it.
        raise SystemExit('A question could not be answered: this program has no terminal to read from. '
                         'Run it in a terminal, or give the settings as options (see "setup --help").') from None
    except KeyboardInterrupt:
        raise SystemExit('Stopped.') from None


if __name__ == '__main__':
    sys.exit(main())
