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

An API key is read from an environment variable when the application starts, or
typed into a hidden prompt. See docs/model-routes.md.
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


def split_command(text):
    """A command line as a list. Quotes group words on every system."""
    if os.name == 'nt':
        return [part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part
                for part in shlex.split(text, posix=False)]
    return shlex.split(text)


def listed_models(config, key=None):
    """Model names that the endpoint lists, or an empty list. Never raises."""
    try:
        from feedctrl import route_http
        normal = model_routes.validate_config({**config, 'model': config.get('model') or 'placeholder'})
        if normal['route'] == 'anthropic' and not key:
            return []
        return route_http.model_names(normal, key)
    except (RouteError, OSError, ValueError):
        return []


def choose(ask, out, question, choices, default='1'):
    """Ask until the answer is one of the numbered choices."""
    while True:
        out(question)
        for number, label in choices:
            out(f'  {number}  {label}')
        answer = (ask(f'Choice [{default}]: ') or '').strip() or default
        if answer in dict(choices):
            return answer
        out('Type one of the numbers.')


def text(ask, question, default=None):
    while True:
        answer = (ask(f'{question}{f" [{default}]" if default else ""}: ') or '').strip() or (default or '')
        if answer:
            return answer


def pick_model(ask, out, names, example):
    names = names[:30]
    if names:
        out('The endpoint lists these models:')
        for number, name in enumerate(names, 1):
            out(f'  {number}  {model_routes.ascii_text(name)}')
        answer = text(ask, 'Number of the model, or another exact model name')
        return names[int(answer) - 1] if answer.isdigit() and 1 <= int(answer) <= len(names) else answer
    return text(ask, f'Exact model name (for example {example})')


def wizard(ask=input, out=print, environ=None, models=listed_models):
    """Ask the questions and return the raw settings. Nothing is written here."""
    environ = os.environ if environ is None else environ
    kind = choose(ask, out, 'How will the application reach a model?', [
        ('1', 'A command-line program on this computer (Claude Code CLI or another program)'),
        ('2', 'A hosted provider with my own API key (OpenAI-compatible API or the Anthropic API)'),
        ('3', 'A model server on this computer (Ollama, LM Studio or another OpenAI-compatible server)'),
        ('4', 'By hand: I carry each request to a chat application and bring the reply back (file relay)')])
    if kind == '1':
        which = choose(ask, out, 'Which program?', [('1', 'Claude Code CLI (the "claude" command, signed in to my own account)'),
                                                    ('2', 'Another program that reads a prompt on standard input')])
        if which == '1':
            config = {'route': 'cli', 'profile': 'claude-code', 'command': text(ask, 'Command or full path of the CLI', 'claude'),
                      'model': text(ask, 'Full model name, as the CLI reports it (not a short alias)')}
            effort = (ask('Effort (low, medium, high, xhigh, max; empty = the default of the CLI): ') or '').strip()
            if effort:
                config['effort'] = effort
            return config
        out('Example: ollama run llama3.1:8b --format json')
        return {'route': 'cli', 'profile': 'generic', 'argv': split_command(text(ask, 'The command line of the program')),
                'model': text(ask, 'Name of the model that this program uses (your declaration)')}
    if kind == '2':
        which = choose(ask, out, 'Which provider?', [('1', 'OpenAI API'), ('2', 'Anthropic API'),
                                                     ('3', 'Another provider with an OpenAI-compatible API')])
        if which == '2':
            config = {'route': 'anthropic', 'api_key_env': text(ask, 'Name of the environment variable that holds your key', 'ANTHROPIC_API_KEY')}
            example = 'a name from the model list of the provider'
        else:
            config = {'route': 'openai-compatible', 'preset': 'openai' if which == '1' else 'custom'}
            if which == '3':
                config['base_url'] = text(ask, 'Base address of the API, ending with /v1')
            config['api_key_env'] = text(ask, 'Name of the environment variable that holds your key', 'OPENAI_API_KEY')
            example = 'a name from the model list of the provider'
        key = (environ.get(config['api_key_env']) or '').strip()
        if not key:
            out(f'{config["api_key_env"]} is not set in this terminal. The model names cannot be listed now.')
        config['model'] = pick_model(ask, out, models(config, key) if key else [], example)
        return config
    if kind == '3':
        which = choose(ask, out, 'Which server?', [('1', 'Ollama (http://127.0.0.1:11434/v1)'),
                                                   ('2', 'LM Studio (http://127.0.0.1:1234/v1)'), ('3', 'Another address')])
        if which == '3':
            config = {'route': 'openai-compatible', 'preset': 'custom',
                      'base_url': text(ask, 'Base address of the server, ending with /v1')}
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


def hidden_key(config, interactive):
    """The key for a check: from the environment, or a hidden prompt at a terminal."""
    try:
        return model_routes.resolve_api_key(config, ask=getpass.getpass if interactive else None)
    except RouteError:
        return None


def run_check(config, *, test_call=True, out=print, interactive=None):
    interactive = sys.stdin.isatty() if interactive is None else interactive
    return model_routes.check_route(config, api_key=hidden_key(config, interactive), test_call=test_call, out=out)


def setup(args, ask=input, out=print):
    path = Path(args.file)
    if path.exists() and not args.yes:
        if args.route or (ask(f'{path.name} exists. Replace it? [y/N]: ') or '').strip().lower() not in ('y', 'yes'):
            raise SystemExit(f'{path} exists and was not changed. Add --yes to replace it.')
    try:
        config = model_routes.validate_config(from_flags(args) if args.route else wizard(ask, out))
        model_routes.save_config(path, config)
    except RouteError as error:
        raise SystemExit(model_routes.ascii_text(error)) from None
    out(f'\nWritten: {path}')
    for line in model_routes.describe(config):
        out('  ' + line)
    name = model_routes.needs_api_key(config)
    if name:
        out('\nThe key is not in the file. Set it for this terminal before you start:')
        out(f'  Windows PowerShell:  $env:{name} = "paste-the-key-here"')
        out(f'  macOS or Linux:      export {name}="paste-the-key-here"')
    if args.no_check:
        return 0
    if not args.route and (ask('\nCheck the connection now? [Y/n]: ') or '').strip().lower() in ('n', 'no'):
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
    out('\nResult: ' + ('the route works.' if result['ok'] else 'the route does not work yet. Read the lines marked FAILED.'))
    return 0 if result['ok'] else 1


def show(args, out=print):
    try:
        config = model_routes.load_config(args.file)
    except RouteError as error:
        raise SystemExit(model_routes.ascii_text(error)) from None
    out(f'Route file: {args.file}')
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
            step.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh', 'max'))
            step.add_argument('--max-calls', type=int)
            step.add_argument('--timeout-seconds', type=float)
            step.add_argument('--max-output-tokens', type=int)
            step.add_argument('--set', action='append', metavar='NAME=VALUE', help='any other setting; the value is JSON')
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == '__main__':
    sys.exit(main())
