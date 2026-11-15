"""Pinned qualification-module loader; external caller must pin this file first."""
import hashlib
import importlib
from pathlib import Path
import sys
from threading import Lock

ROOT=Path(__file__).absolute().parents[1]
QUALIFICATION_SHA256='bb179c50acae02d5d9e83130271621f0c5061c45cc61ace5684d029339f48523'
INIT_SHA256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
_loaded=None
_lock=Lock()

class BootstrapError(ValueError):
    pass

def _file(path,expected):
    for part in (path,*path.parents):
        if part.is_symlink():raise BootstrapError('identity_failed')
        junction=getattr(part,'is_junction',None)
        if sys.platform=='win32' and not callable(junction):raise BootstrapError('identity_failed')
        if callable(junction) and junction():raise BootstrapError('identity_failed')
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise BootstrapError('identity_failed')

def _load():
    global _loaded
    with _lock:
        init=ROOT/'diagnostic'/'__init__.py'; path=ROOT/'diagnostic'/'qualification.py'
        _file(init,INIT_SHA256);_file(path,QUALIFICATION_SHA256)
        package=sys.modules.get('diagnostic')
        if package is None or Path(package.__file__).resolve()!=init.resolve():raise BootstrapError('identity_failed')
        key='diagnostic.qualification'
        if _loaded is None:
            if key in sys.modules:raise BootstrapError('preloaded_module')
            module=importlib.import_module(key)
        else:
            module=_loaded
            if sys.modules.get(key) is not module:raise BootstrapError('identity_failed')
        _file(path,QUALIFICATION_SHA256)
        if Path(getattr(module,'__file__','')).resolve()!=path.resolve():raise BootstrapError('identity_failed')
        for name in ('preflight','bind_once','verify_package'):
            f=getattr(module,name,None)
            if not callable(f) or Path(getattr(getattr(f,'__code__',None),'co_filename','')).resolve()!=path.resolve():
                raise BootstrapError('identity_failed')
        module.verify_package()
        _loaded=module
        return module

def preflight(**context):
    return _load().preflight(**context)

def bind_once(**arguments):
    return _load().bind_once(**arguments)
