import signal
import threading
import time
from collections.abc import Iterator
from typing import NoReturn

import pytest

from tess_shell.signals import EarlyStop, LoopStopper, SignalWatcher


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


# -- a signal while the shell is still starting ---------------------------------------------------
#
# ``EarlyStop`` holds the first SIGTERM or SIGINT of the start (the shell logs "starting" well
# before its signal watcher exists); without it the default action killed the process (exit -15,
# no clean stop), which a slow machine showed one run in a few. These run on the main thread and
# always put the previous handlers back.


@pytest.fixture
def early() -> Iterator[tuple[EarlyStop, list[str]]]:
    log: list[str] = []

    def force() -> NoReturn:
        log.append("force")
        raise SystemExit

    hold = EarlyStop(force)
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    hold.install()
    try:
        yield hold, log
    finally:
        hold.uninstall()
        for sig, handler in before.items():
            signal.signal(sig, handler)  # whatever a test left behind


def test_a_first_signal_of_the_start_is_held_and_nothing_is_killed(
    early: tuple[EarlyStop, list[str]],
) -> None:
    hold, log = early
    assert not hold.requested.is_set()
    signal.raise_signal(signal.SIGTERM)
    assert hold.requested.is_set() and log == []  # still here, and not forced


def test_a_sigint_of_the_start_is_held_too_not_a_keyboard_interrupt(
    early: tuple[EarlyStop, list[str]],
) -> None:
    hold, log = early
    signal.raise_signal(signal.SIGINT)  # Python's default handler would raise KeyboardInterrupt
    assert hold.requested.is_set() and log == []


def test_a_second_signal_of_the_start_forces_so_a_start_that_hangs_can_be_interrupted(
    early: tuple[EarlyStop, list[str]],
) -> None:
    hold, log = early
    signal.raise_signal(signal.SIGTERM)
    with pytest.raises(SystemExit):
        signal.raise_signal(signal.SIGTERM)
    assert log == ["force"]


def test_uninstall_puts_the_handlers_back_and_leaves_one_that_is_not_ours() -> None:
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    hold = EarlyStop(lambda: (_ for _ in ()).throw(SystemExit))
    hold.install()
    try:
        assert signal.getsignal(signal.SIGTERM) == hold._handle
        theirs = signal.signal(signal.SIGINT, lambda *_: None)  # someone else took SIGINT
        assert theirs == hold._handle
        mine = signal.getsignal(signal.SIGINT)
        hold.uninstall()
        assert signal.getsignal(signal.SIGTERM) == before[signal.SIGTERM]
        assert signal.getsignal(signal.SIGINT) is mine  # not ours: left alone
    finally:
        for sig, handler in before.items():
            signal.signal(sig, handler)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_the_watcher_acts_on_a_signal_the_start_held_as_the_first_and_restores_the_originals() -> (
    None
):
    log: list[str] = []
    changed = threading.Event()

    def stop() -> None:
        log.append("stop")
        changed.set()

    def force() -> NoReturn:
        log.append("force")
        changed.set()
        raise SystemExit

    before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    hold = EarlyStop(force)
    hold.install()
    watcher = SignalWatcher(stop, force)
    try:
        signal.raise_signal(signal.SIGTERM)  # during the start: held
        assert log == []
        watcher.start(hold)
        assert changed.wait(5) and log == ["stop"]  # the held one is the first signal
        changed.clear()
        signal.raise_signal(signal.SIGINT)  # so the next one forces
        assert changed.wait(5) and log == ["stop", "force"]
    finally:
        watcher.close()
        hold.uninstall()
        # the originals, not the hold's handler, are what the watcher gives back
        assert {sig: signal.getsignal(sig) for sig in before} == before
