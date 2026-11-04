import time
import pytest
import startup_imports
from liquid_data import bounded_call


def test_local_import_retries_only_known_module_race(monkeypatch):
    calls=[]
    def load(name):
        calls.append(name)
        if len(calls)==1:raise KeyError('terminal_view')
        return 'loaded'
    monkeypatch.setattr(startup_imports.importlib,'import_module',load)
    assert startup_imports.import_local('terminal_view')=='loaded'
    assert len(calls)==2
    monkeypatch.setattr(startup_imports.importlib,'import_module',lambda name:(_ for _ in ()).throw(KeyError('Symbol')))
    with pytest.raises(KeyError,match='Symbol'):startup_imports.import_local('terminal_view')


def test_provider_deadline_does_not_wait_for_worker():
    from threading import Event
    release=Event()
    started=time.monotonic()
    try:
        with pytest.raises(TimeoutError):bounded_call(release.wait,timeout=.02)
        assert time.monotonic()-started<.5
    finally:release.set()
