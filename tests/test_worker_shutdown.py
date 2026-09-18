"""Ctrl+C reaches the worker processes too, and must not look like a crash.

Each worker blocks in stop.wait(), so an interrupt raises KeyboardInterrupt
inside worker_loop. Uncaught, multiprocessing prints a traceback per worker and
the process exits non-zero, which reads as a failure during an ordinary shutdown.
"""

import pytest

from cognitive_os.core.config import Settings
from cognitive_os.workers import runtime


class Spy:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    dispose = close


@pytest.fixture
def worker(monkeypatch):
    provider, engine = Spy(), Spy()
    # OpenAIVisualProvider subclasses OpenAIDraftProvider, so let that module bind the
    # real base class before the name is replaced; worker_loop imports it per call.
    import cognitive_os.infrastructure.ai.openai_visual  # noqa: F401

    monkeypatch.setattr("cognitive_os.infrastructure.ai.openai_drafts.OpenAIDraftProvider",
                        lambda settings: provider)
    monkeypatch.setattr(runtime, "create_engine", lambda *a, **kw: engine)
    settings = Settings(_env_file=None, environment="test",
                        database_url="postgresql+psycopg://user@localhost:5432/cognitive")
    return settings, provider, engine


class NeverStops:
    def is_set(self):
        return False

    def wait(self, timeout=None):
        return False


def test_interrupt_shuts_the_worker_down_quietly(worker, monkeypatch):
    settings, provider, engine = worker

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("cognitive_os.workers.consolidation.run_once", interrupted)
    # Returns instead of propagating, so multiprocessing prints no traceback.
    runtime.worker_loop(settings, "consolidate", NeverStops())
    assert provider.closed and engine.closed


def test_ordinary_failures_still_retry_without_stopping(worker, monkeypatch):
    settings, provider, engine = worker
    calls = []

    def failing(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("provider down")

    class StopsAfterRetry:
        def is_set(self):
            return len(calls) >= 2

        def wait(self, timeout=None):
            return False

    monkeypatch.setattr("cognitive_os.workers.consolidation.run_once", failing)
    runtime.worker_loop(settings, "consolidate", StopsAfterRetry())
    # KeyboardInterrupt is not Exception, so the retry path is untouched.
    assert len(calls) == 2
    assert provider.closed and engine.closed
