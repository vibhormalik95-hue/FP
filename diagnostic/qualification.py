"""Inert qualification and explicit one-call runner binding for offline review.

An external, independently reviewed context digest is mandatory. Qualification
is not authorization, a sandbox, application acceptance, or a billing promise.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from threading import Lock

ROOT = Path(__file__).absolute().parents[1]
PINS = {
    'diagnostic/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'diagnostic/diagnostic_transport.py': '46f8e2ad315678a492472135ac4b0246e64eb964b9e0380de9270bd0953555e3',
    'diagnostic/transport_evidence.py': '49db92370df26afd324867e8bfd078c4be94e8970ae40f689864e63e1caaf262',
    'diagnostic/stream_projection.py': 'e527bf52da8d819a0963afa02159d6b5b95908e371bc305f487f966e3256f7b6',
    'diagnostic/rejection_observer.py': '30f6c19924fac26ceea934ca03d79039f52ed042b4d99a641659f670ed5a1440',
    'diagnostic/lifecycle_probe.py': '472ecd7509a4c236c73a135e45aaa354a5ac807f9a0f058bb3fb6deba7863174',
    'diagnostic/lifecycle_composition.py': '35e23ae721830fd369d8b59d8de891db1a263bc35e041759f811b18a18713cea',
    'diagnostic/flow_guard.py': '77f04e078a71d55c857a5abe6c84272358aef6800f5ac15c11b7c9ec6f6d002f',
    'diagnostic/app_binding.py': 'e1f87dc6db394c195e6922a2f8c13a29366184840106ffb6aefde55effcf7fec',
    'diagnostic/source-pins.json': '257dfd8dc2dfa188172c4f869817d4ef4bea76a6529f82a7b71f6d1ea47d8a8e',
    'feedctrl/__init__.py': 'eaabd38e85dd5a5f07362331ac61fb03de4b808055144d328d12e9f8fe5fce39',
    'feedctrl/windows_job_runner.py': '693931dbf1b02e121a38dab0e150857b589071b347fc7f763dfa5c831d9b41b4',
    'feedctrl/windows_job_native.py': 'd081495c2c07dc1645373e111f6253d88b5c490a0f8fe3fdd04ffef1b3be5fb0',
}
_CONTEXT_FIELDS = frozenset(('cli_sha256','settings_sha256','node_sha256','path_sha256',
    'plugin_manifest_sha256','plugin_skill_sha256','hook_activate_sha256',
    'hook_tracker_sha256','hook_config_sha256','hook_sessionstart_command_sha256',
    'hook_prompt_command_sha256','child_env_sha256','max_output_tokens'))
_ENV_ALLOW = ('SYSTEMROOT','WINDIR','APPDATA','LOCALAPPDATA','USERPROFILE',
              'HOMEDRIVE','HOMEPATH','HOME','PATH','TEMP','TMP','TMPDIR')
_ENV_FIXED = {'CLAUDE_CODE_MAX_RETRIES':'0', 'CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES':'0',
    'MAX_STRUCTURED_OUTPUT_RETRIES':'1', 'CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK':'1',
    'CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK':'1', 'DISABLE_AUTOUPDATER':'1'}

class QualificationError(ValueError):
    pass

def _require(ok):
    if not ok:
        raise QualificationError('qualification_failed')

def _safe(path):
    path = Path(path)
    _require(path.is_absolute() and '..' not in path.parts)
    for part in (path, *path.parents):
        _require(not part.is_symlink())
        junction = getattr(part, 'is_junction', None)
        if os.name == 'nt':
            _require(callable(junction))
        _require(not callable(junction) or not junction())
    return path

def _digest(path):
    path = _safe(path)
    _require(path.is_file())
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _hash_string(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None

def verify_package():
    for name, expected in PINS.items():
        _require(_digest(ROOT / name) == expected)
    manifest = json.loads((ROOT / 'diagnostic' / 'source-pins.json').read_bytes(), object_pairs_hook=_unique_pairs)
    _require(type(manifest) is dict and set(manifest) == {'revision', 'identity_scope', 'files'})
    _require(manifest['revision'] == '8a33946147dafb2b4d57c95c4b155a9bd6435a01')
    _require(manifest['identity_scope'] == 'application-runtime-v1')
    files = manifest['files']
    _require(type(files) is dict and len(files) == 46)
    for name, expected in files.items():
        _require(type(name) is str and bool(name) and '\\' not in name)
        parts = name.split('/')
        _require(all(part not in ('', '.', '..') for part in parts) and not name.startswith('/'))
        _require(_hash_string(expected) and _digest(ROOT.joinpath(*parts)) == expected)
    feed = ROOT / 'feedctrl'
    expected_py = {name for name in files if name.startswith('feedctrl/') and name.endswith('.py')}
    actual_py = set()
    for path in feed.rglob('*'):
        _safe(path)
        if path.is_file() and path.suffix.lower() in ('.pyc', '.pyd', '.so', '.dll'):
            raise QualificationError('unexpected_executable_module')
        if path.is_file() and path.suffix.lower() == '.py': actual_py.add(path.relative_to(ROOT).as_posix())
    _require(actual_py == expected_py)

def preflight(*, context_file, context_sha256, cli, workdir, home):
    """Read-only; validates a reviewed private context without returning it."""
    verify_package()
    _require(_hash_string(context_sha256))
    context = _load_context(context_file, context_sha256)
    cli, workdir, home = map(_safe, (cli, workdir, home))
    expected_env = _expected_child_environment(context, home)
    _require(_environment_digest(expected_env) == context['child_env_sha256'])
    _require(_digest(cli) == context['cli_sha256'])
    _require(workdir.is_dir() and not any(workdir.iterdir()))
    settings_path = home / '.claude' / 'settings.json'
    _require(_digest(settings_path) == context['settings_sha256'])
    node = shutil.which('node')
    _require(node is not None and _digest(Path(node).absolute()) == context['node_sha256'])
    _require(hashlib.sha256(os.environ.get('PATH','').encode()).hexdigest() == context['path_sha256'])
    _require(not any(name in os.environ for name in ('FEEDCTRL_DATA','FEEDCTRL_MODEL','FEEDCTRL_CAPTION_SIDECAR')))
    for parent in (workdir, *workdir.parents):
        _require(not (parent / 'CLAUDE.md').exists())
    _require(not (home/'CLAUDE.md').exists())
    _require(not (home/'.claude'/'CLAUDE.md').exists() and not (home/'.claude'/'rules').exists())
    try:
        settings = json.loads(settings_path.read_text(encoding='utf-8'), object_pairs_hook=_unique_pairs)
        registry_path = _safe(home/'.claude'/'plugins'/'installed_plugins.json')
        registry = json.loads(registry_path.read_text(encoding='utf-8'), object_pairs_hook=_unique_pairs)
        enabled = [k for k,v in settings.get('enabledPlugins',{}).items() if v is True]
        _require(len(enabled) == 1 and not settings.get('hooks'))
        records = registry['plugins'][enabled[0]]
        _require(type(records) is list and len(records) == 1)
        plugin = _safe(Path(records[0]['installPath']))
        _require(plugin.resolve().is_relative_to((home/'.claude'/'plugins'/'cache').resolve()))
        manifest = plugin/'.claude-plugin'/'plugin.json'
        files = ((manifest,'plugin_manifest_sha256'), (plugin/'skills'/'caveman'/'SKILL.md','plugin_skill_sha256'),
                 (plugin/'hooks'/'caveman-activate.js','hook_activate_sha256'),
                 (plugin/'hooks'/'caveman-mode-tracker.js','hook_tracker_sha256'),
                 (plugin/'hooks'/'caveman-config.js','hook_config_sha256'))
        for path,key in files: _require(_digest(path) == context[key])
        hookdata = json.loads(manifest.read_text(encoding='utf-8'), object_pairs_hook=_unique_pairs)['hooks']
        for event,key in (('SessionStart','hook_sessionstart_command_sha256'),
                          ('UserPromptSubmit','hook_prompt_command_sha256')):
            groups=hookdata[event]
            _require(len(groups)==1 and len(groups[0]['hooks'])==1)
            command=groups[0]['hooks'][0]['command']
            _require(hashlib.sha256(command.encode()).hexdigest()==context[key])
    except (ValueError, OSError, UnicodeError, KeyError, TypeError, AttributeError):
        raise QualificationError('qualification_failed') from None
    return {'qualified': True, 'authorization_established': False,
            'managed_context_verified': False, 'live_calls': 0}

def _unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('duplicate')
        result[key]=value
    return result

def _load_context(path, expected):
    path = _safe(path)
    _require(_hash_string(expected) and path.is_file())
    try:
        data = path.read_bytes()
        _require(len(data) <= 32768 and hashlib.sha256(data).hexdigest() == expected)
        value = json.loads(data, object_pairs_hook=_unique_pairs)
    except (ValueError, OSError, UnicodeError):
        raise QualificationError('qualification_failed') from None
    _require(type(value) is dict and set(value) == _CONTEXT_FIELDS)
    _require(all(_hash_string(v) for k,v in value.items() if k != 'max_output_tokens'))
    tokens=value['max_output_tokens']
    _require(type(tokens) is str and re.fullmatch('[0-9]{1,5}',tokens) is not None and 1 <= int(tokens) <= 32768)
    return value

def _environment_digest(env):
    data=json.dumps(env,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def _expected_child_environment(context, home):
    env={k:os.environ[k] for k in _ENV_ALLOW if k in os.environ}
    homes=[env[k] for k in ('HOME','USERPROFILE') if k in env]
    has_drive='HOMEDRIVE' in env; has_path='HOMEPATH' in env
    _require(has_drive == has_path)
    if has_drive: homes.append(env['HOMEDRIVE'] + env['HOMEPATH'])
    _require(bool(homes))
    expected_home=os.path.normcase(os.path.normpath(str(home)))
    for value in homes:
        _require(bool(value) and os.path.isabs(value) and os.path.normcase(os.path.normpath(value)) == expected_home)
    env.update(_ENV_FIXED)
    env['CLAUDE_CODE_MAX_OUTPUT_TOKENS']=context['max_output_tokens']
    return env

def _require_bootstrap():
    bootstrap=sys.modules.get('diagnostic.bootstrap')
    _require(bootstrap is not None and getattr(bootstrap,'_loaded',None) is sys.modules.get(__name__))
    _require(bootstrap._load() is sys.modules.get(__name__))

class _BoundCalls:
    """One or two serialized attempts, each with its own exclusive marker."""
    def __init__(self, runner, context, marker, max_calls):
        _require(type(max_calls) is int and max_calls in (1, 2))
        self._runner=runner
        self._context=dict(context)
        self._marker=_safe(marker)
        self._max_calls=max_calls
        self._attempted=0
        self._failed=False
        self._lock=Lock()
    def __call__(self, *args):
        with self._lock:
            if self._failed or self._attempted >= self._max_calls:
                raise QualificationError('call_budget_unavailable')
            self._attempted+=1
            try:
                _require_bootstrap()
                preflight(**self._context)
                _require(len(args) == 6 and type(args[0]) is list and args[0]
                         and Path(args[0][0]) == Path(self._context['cli'])
                         and Path(args[3]) == Path(self._context['workdir']))
                reviewed = _load_context(self._context['context_file'], self._context['context_sha256'])
                expected_env = _expected_child_environment(reviewed, _safe(self._context['home']))
                _require(_environment_digest(expected_env) == reviewed['child_env_sha256'])
                _require(type(args[2]) is dict and args[2] == expected_env)
                marker = self._marker if self._attempted == 1 else self._marker.with_name(self._marker.name + '.2')
                _safe(marker)
                try:
                    fd=os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,'O_BINARY',0), 0o600)
                    try:
                        if os.write(fd,b'consumed\n') != 9: raise OSError('incomplete marker')
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                except OSError:
                    raise QualificationError('marker_unavailable') from None
                return self._runner(*args)
            except BaseException:
                self._failed=True
                raise

class _OneCall(_BoundCalls):
    def __init__(self, runner, context, marker):
        super().__init__(runner, context, marker, 1)

class _ObservationView:
    """Preserve lifecycle access and separately expose bounded projection facts."""
    def __init__(self, observed, transport, evidence):
        self._observed, self._transport, self._evidence = observed, transport, evidence
    def __call__(self):
        return self._observed.records()
    def transport_metadata(self):
        try:
            return self._evidence.snapshot(self._transport.records)
        except Exception:
            return {'capture_status': 'unavailable', 'records': []}

def bind_once(*, marker, enable_live=False, max_calls=1, **context):
    """Explicit opt-in; returns a bounded runner, never calls it itself."""
    _require(enable_live is True and os.name == 'nt' and type(max_calls) is int and max_calls in (1, 2))
    _require_bootstrap()
    preflight(**context)
    package=sys.modules.get('diagnostic')
    _require(package is not None and Path(package.__file__).resolve() == (ROOT/'diagnostic'/'__init__.py').resolve())
    marker=_safe(marker)
    _require(marker.parent.is_dir() and not marker.exists() and not marker.with_name(marker.name + '.2').exists())
    _require(not any(n == 'feedctrl' or n.startswith('feedctrl.') for n in sys.modules))
    for name in ('diagnostic_transport','stream_projection','rejection_observer','lifecycle_composition','lifecycle_probe','transport_evidence'):
        _require('diagnostic.'+name not in sys.modules)
    old = list(sys.path)
    try:
        sys.path.insert(0, str(ROOT))
        runner = importlib.import_module('feedctrl.windows_job_runner')
        native = importlib.import_module('feedctrl.windows_job_native')
        composition = importlib.import_module('diagnostic.lifecycle_composition')
        transport = importlib.import_module('diagnostic.diagnostic_transport')
        evidence = importlib.import_module('diagnostic.transport_evidence')
    finally:
        sys.path[:] = old
    verify_package()
    _require(Path(runner.__file__).resolve() == (ROOT/'feedctrl'/'windows_job_runner.py').resolve())
    _require(Path(native.__file__).resolve() == (ROOT/'feedctrl'/'windows_job_native.py').resolve())
    _require(getattr(native,'CleanupUncertain',None) is runner.CleanupUncertain)
    _require(getattr(native.WindowsBackend, '__module__', None) == native.__name__)
    _require(Path(composition.__file__).resolve() == (ROOT/'diagnostic'/'lifecycle_composition.py').resolve())
    _require(Path(transport.__file__).resolve() == (ROOT/'diagnostic'/'diagnostic_transport.py').resolve())
    _require(Path(evidence.__file__).resolve() == (ROOT/'diagnostic'/'transport_evidence.py').resolve())
    _require(transport.rejection_observer.strict is transport.stream_projection)
    observed = composition.ObservedRunner(runner.run_with_backend, native.WindowsBackend)
    wrapped = transport.DiagnosticRunner(observed, runtime_mode='reviewed_hooks')
    return _BoundCalls(wrapped, context, marker, max_calls), _ObservationView(observed, wrapped, evidence)
