import signal
import threading
import time
from collections.abc import Iterator
from typing import NoReturn

import pytest

from tess_shell.signals import LoopStopper, SignalWatcher


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


def test_stopper_retries_until_the_loop_accepts() -> None:
    calls: list[int] = []
    accepted = threading.Event()

    def try_stop() -> bool:
        calls.append(1)
        if len(calls) < 3:
            return False
        accepted.set()
        return True

    stopper = LoopStopper(try_stop, interval=0.01)
    stopper.request()
    assert accepted.wait(5)
    time.sleep(0.1)
    assert len(calls) == 3  # no retries after the stop was accepted


def test_stopper_gives_up_when_the_loop_finished() -> None:
    calls: list[int] = []
    stopper = LoopStopper(lambda: calls.append(1) or False, interval=0.01)
    stopper.request()
    stopper.loop_finished()
    time.sleep(0.1)
    settled = len(calls)
    time.sleep(0.1)
    assert len(calls) == settled


def test_stopper_does_not_start_a_thread_when_stop_succeeds() -> None:
    before = threading.active_count()
    stopper = LoopStopper(lambda: True)
    stopper.request()
    assert threading.active_count() == before and stopper.requested.is_set()
