import signal
import threading
from collections.abc import Iterator
from typing import NoReturn

import pytest

from tess_shell.signals import SignalWatcher


class Forced(Exception):
    pass


@pytest.fixture
def events() -> Iterator[tuple[SignalWatcher, list[str], threading.Event]]:
    log: list[str] = []
    changed = threading.Event()

    def stop() -> None:
        log.append("stop")
        changed.set()

    def force() -> NoReturn:
        log.append("force")
        changed.set()
        raise SystemExit  # ends the watcher thread without killing the test process

    watcher = SignalWatcher(stop, force)
    watcher.start()
    try:
        yield watcher, log, changed
    finally:
        watcher.close()


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_first_signal_stops_second_forces(
    events: tuple[SignalWatcher, list[str], threading.Event],
) -> None:
    _, log, changed = events
    signal.raise_signal(signal.SIGTERM)
    assert changed.wait(5)
    assert log == ["stop"]
    changed.clear()
    signal.raise_signal(signal.SIGINT)
    assert changed.wait(5)
    assert log == ["stop", "force"]


def test_close_restores_handlers() -> None:
    before = signal.getsignal(signal.SIGTERM)
    watcher = SignalWatcher(lambda: None, lambda: (_ for _ in ()).throw(SystemExit))
    watcher.start()
    assert signal.getsignal(signal.SIGTERM) is not before
    watcher.close()
    assert signal.getsignal(signal.SIGTERM) is before
