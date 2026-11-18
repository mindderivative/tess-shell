"""The watchdog (Crash Recovery and Watchdog > Detecting a Hang, The systemd side): what it logs,
when it asks for a restart, when it pings. A fake clock and a fake loop make every case exact; one
test runs the real thread against a real blocked "loop" thread."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterator

import pytest
from loguru import logger

from tess_shell.modules.running import CallbackRecord
from tess_shell.notify import WATCHDOG, WATCHDOG_TRIGGER, watchdog_interval
from tess_shell.watchdog import (
    SCALE_VARIABLE,
    Heartbeat,
    Timing,
    Watchdog,
    dump_tracebacks,
    timing_from_environment,
)


@pytest.fixture
def logged() -> Iterator[list[tuple[str, str]]]:
    """(level, message) of everything the watchdog logs."""
    records: list[tuple[str, str]] = []
    sink = logger.add(
        lambda m: records.append((m.record["level"].name, m.record["message"])), level="DEBUG"
    )
    yield records
    logger.remove(sink)


class Rig:
    """A watchdog over a fake clock and a fake loop. ``tick`` is one second: the watchdog looks,
    then the loop (when ``alive``) runs what was queued for it."""

    def __init__(self, interval: float | None = 15.0, supervised: bool = True) -> None:
        self.now = 1000.0
        self.alive = True
        self.queue: list[Callable[[], None]] = []
        self.sent: list[tuple[float, str]] = []
        self.dumps: list[float] = []
        self.callbacks = CallbackRecord(lambda *_: None, clock=self.clock)
        self.watchdog = Watchdog(
            Heartbeat(self.clock),
            self.callbacks.running,
            self.queue.append,
            interval=interval,
            supervised=supervised,
            clock=self.clock,
            send=self.send,
            dump=self.dump,
        )

    def clock(self) -> float:
        return self.now

    def send(self, state: str) -> bool:
        self.sent.append((self.now, state))
        return True

    def dump(self) -> str:
        self.dumps.append(self.now)
        return "THE TRACEBACKS"

    def run_loop(self) -> None:
        queued, self.queue[:] = list(self.queue), []
        for fn in queued:
            fn()

    def start(self) -> None:
        self.watchdog.begin()

    def tick(self, seconds: int = 1) -> None:
        for _ in range(seconds):
            self.now += 1.0
            self.watchdog.poll()
            if self.alive:
                self.run_loop()

    def pings(self) -> list[float]:
        return [t for t, s in self.sent if s == WATCHDOG]

    def triggers(self) -> list[float]:
        return [t for t, s in self.sent if s == WATCHDOG_TRIGGER]


def warnings_of(records: list[tuple[str, str]]) -> list[str]:
    return [m for lvl, m in records if m.startswith("loop stalled")]


# -- a healthy loop -------------------------------------------------------------------------------


def test_a_healthy_loop_logs_nothing_and_is_pinged_at_half_the_interval(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig(interval=15.0)
    rig.start()
    rig.tick(30)
    assert warnings_of(logged) == [] and rig.triggers() == [] and rig.dumps == []
    pings = rig.pings()
    gaps = [b - a for a, b in zip(pings, pings[1:], strict=False)]
    assert len(pings) >= 4 and all(7.5 <= g <= 8.5 for g in gaps), pings  # every 7.5 s, on a tick


# -- the stall: what is logged ------------------------------------------------------------------


def test_a_stall_of_two_seconds_names_the_module_the_entry_point_and_how_long(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig()
    rig.start()
    rig.tick(10)  # the heartbeat is at t=10
    rig.alive = False
    rig.now += 0.5
    rig.callbacks.enter("Hang", "Hang.sleepy")  # the loop is now stuck in this callback
    rig.now -= 0.5
    rig.tick(1)
    assert warnings_of(logged) == []  # a second old: not yet
    rig.tick(1)
    (first,) = warnings_of(logged)
    assert first.startswith("loop stalled for 2 s")
    assert "module Hang" in first and "entry point Hang.sleepy" in first
    assert "running for 1.5 s" in first
    assert ("WARNING", first) in logged


def test_the_warning_comes_again_every_five_seconds_and_not_in_between(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig(interval=None, supervised=False)
    rig.start()
    rig.tick(5)
    rig.alive = False
    rig.tick(9)  # stalled from t=5: warnings at 2 s and 7 s of age; the decision at 10 s is later
    seconds = [m.split()[3] for m in warnings_of(logged) if "no supervisor" not in m]
    assert seconds == ["2", "7"]


def test_the_tracebacks_of_every_thread_go_to_the_log_with_the_first_warning(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig()
    rig.start()
    rig.tick(3)
    rig.alive = False
    rig.tick(2)
    assert len(rig.dumps) == 1
    assert any("THE TRACEBACKS" in m for _, m in logged)


def test_with_no_module_callback_running_the_warning_says_so(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig()
    rig.start()
    rig.tick(3)
    rig.alive = False
    rig.tick(2)
    (first,) = warnings_of(logged)
    assert "no module callback is running" in first


def test_a_loop_that_comes_back_is_told_and_a_second_stall_warns_again(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig()
    rig.start()
    rig.tick(3)
    rig.alive = False
    rig.tick(3)
    rig.alive = True
    rig.tick(2)
    assert any("loop is running again after" in m for _, m in logged)
    rig.alive = False
    rig.tick(3)
    assert len(warnings_of(logged)) == 2


# -- the decision at 10 s -------------------------------------------------------------------------


def test_at_ten_seconds_under_a_watchdog_the_shell_asks_systemd_once(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig(interval=15.0)
    rig.start()
    rig.tick(3)
    stall_began = rig.now
    rig.alive = False
    rig.tick(30)
    assert rig.triggers() == [pytest.approx(stall_began + 10)]  # once, at ten seconds of age
    assert any(lvl == "ERROR" and "asking systemd to restart" in m for lvl, m in logged)
    assert not any("no supervisor" in m for _, m in logged)


def test_with_no_watchdog_the_decision_is_a_log_line_and_nothing_is_sent(
    logged: list[tuple[str, str]],
) -> None:
    """WATCHDOG_USEC unset: not WATCHDOG=1, not WATCHDOG=trigger (nothing at all) goes out; the
    tracebacks come again every 30 s."""
    rig = Rig(interval=None, supervised=False)
    rig.start()
    rig.tick(3)
    began = rig.now
    rig.alive = False
    rig.tick(75)
    assert rig.sent == []
    assert [m for _, m in logged if "no supervisor" in m] == [
        "loop stalled for 10 s, no supervisor can restart it"
    ]
    assert rig.dumps == [
        pytest.approx(began + 2),  # with the first warning
        pytest.approx(began + 10),  # with the decision
        pytest.approx(began + 40),  # then every 30 s
        pytest.approx(began + 70),
    ]


# -- the pings ------------------------------------------------------------------------------------


def test_pings_stop_by_themselves_while_the_heartbeat_is_older_than_five_seconds() -> None:
    rig = Rig(interval=4.0)  # a ping every 2 s, so the cut-off is visible
    rig.start()
    rig.tick(10)
    healthy = rig.pings()
    assert healthy[-1] >= rig.now - 2
    stalled_from = rig.now
    rig.alive = False
    rig.tick(9)
    stalled = [t for t in rig.pings() if t > stalled_from]
    assert stalled, "pings go on while the heartbeat is young"
    assert all(t - stalled_from < 5 for t in stalled), stalled  # none once it is 5 s old
    assert stalled[-1] - stalled_from >= 3  # ... and the young ones were sent


def test_pings_start_again_when_the_loop_does() -> None:
    rig = Rig(interval=4.0)
    rig.start()
    rig.tick(3)
    rig.alive = False
    rig.tick(9)
    before = len(rig.pings())
    rig.alive = True
    rig.tick(5)
    assert len(rig.pings()) > before


def test_no_ping_before_the_loop_has_run_a_beat_is_not_judged() -> None:
    """A start sequence is not a stall: until ``start`` (the loop's first turn) the watchdog has
    nothing to judge, and ``start`` itself pings at once."""
    rig = Rig(interval=15.0)
    assert rig.sent == []
    rig.start()
    assert rig.pings() == [rig.now]


def test_the_stop_sequence_is_not_a_stall_and_the_pings_go_on(
    logged: list[tuple[str, str]],
) -> None:
    rig = Rig(interval=4.0)
    rig.start()
    rig.tick(3)
    rig.alive = False  # the loop has ended: the shell stops its modules
    rig.watchdog.begin_stop()
    rig.tick(20)
    assert warnings_of(logged) == [] and rig.triggers() == []
    assert rig.pings()[-1] >= rig.now - 2  # still pinging: a slow stop has its own timeouts


def test_only_one_beat_is_queued_at_a_time() -> None:
    rig = Rig()
    rig.start()
    rig.alive = False
    rig.tick(15)
    assert len(rig.queue) == 1  # fifteen polls queued one callback, not fifteen


# -- what the environment asks for --------------------------------------------------------------


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"WATCHDOG_USEC": "15000000"}, 15.0),
        ({"WATCHDOG_USEC": "2500000", "WATCHDOG_PID": "{pid}"}, 2.5),
        ({"WATCHDOG_USEC": "15000000", "WATCHDOG_PID": "1"}, None),  # meant for another process
        ({}, None),
        ({"WATCHDOG_USEC": ""}, None),
        ({"WATCHDOG_USEC": "0"}, None),
        ({"WATCHDOG_USEC": "soon"}, None),
        ({"WATCHDOG_USEC": "-5"}, None),
    ],
)
def test_the_interval_comes_from_watchdog_usec(environ: dict[str, str], expected: float) -> None:
    env = {k: v.replace("{pid}", str(os.getpid())) for k, v in environ.items()}
    assert watchdog_interval(env) == expected


def test_a_watchdog_needs_both_variables_to_ping_or_ask(logged: list[tuple[str, str]]) -> None:
    def make(environ: dict[str, str]) -> Watchdog:
        return Watchdog.from_environment(Heartbeat(), lambda: None, lambda fn: None, environ)

    both = make({"WATCHDOG_USEC": "15000000", "NOTIFY_SOCKET": "/run/x/notify"})
    assert both.supervised and both.interval == 15.0
    assert not make({"NOTIFY_SOCKET": "/run/x/notify"}).supervised  # a socket but no watchdog
    assert not make({}).supervised
    assert not make({"WATCHDOG_USEC": "15000000"}).supervised
    assert any("WATCHDOG_USEC is set but NOTIFY_SOCKET is not" in m for _, m in logged)


def test_the_test_scale_multiplies_every_time_and_nothing_else_does(
    logged: list[tuple[str, str]],
) -> None:
    assert timing_from_environment({}) == Timing()
    assert timing_from_environment({SCALE_VARIABLE: "banana"}) == Timing()
    assert timing_from_environment({SCALE_VARIABLE: "0"}) == Timing()
    scaled = timing_from_environment({SCALE_VARIABLE: "0.1"})
    assert (scaled.warn, scaled.restart, scaled.fresh, scaled.tick) == pytest.approx(
        (0.2, 1.0, 0.5, 0.1)
    )
    assert any(SCALE_VARIABLE in m for _, m in logged)  # it says so: it is a test setting


# -- the real thread against a real blocked loop -------------------------------------------------


def test_the_thread_finds_a_callback_that_blocks_a_real_loop_thread(
    logged: list[tuple[str, str]],
) -> None:
    """The thread, the real clock and ``faulthandler``: a "loop" thread runs what the watchdog
    queues for it and is then stuck inside a module callback until the test lets it go. The
    watchdog warns naming the module and the entry point, logs a traceback that shows the function
    the loop is stuck in, asks systemd to restart, and pings no more once the heartbeat is old."""
    queue: list[Callable[[], None]] = []
    wake = threading.Event()
    release = threading.Event()
    stop = threading.Event()
    trigger_seen = threading.Event()
    sent: list[tuple[float, str]] = []

    def call_soon(fn: Callable[[], None]) -> None:
        queue.append(fn)
        wake.set()

    def send(state: str) -> bool:
        sent.append((time.monotonic(), state))
        if state == WATCHDOG_TRIGGER:
            trigger_seen.set()
        return True

    callbacks = CallbackRecord(lambda *_: None)

    def stuck_in_the_module() -> None:
        release.wait(30)

    def loop() -> None:
        while not stop.is_set():
            wake.wait(0.05)
            wake.clear()
            while queue:
                queue.pop(0)()
            if hang.is_set():
                hang.clear()
                callbacks.run("Hang", "Hang.sleepy", stuck_in_the_module)

    hang = threading.Event()
    watchdog = Watchdog(
        Heartbeat(),
        callbacks.running,
        call_soon,
        interval=0.4,
        supervised=True,
        timing=Timing().scaled(0.05),  # tick 50 ms, 100 ms, 250 ms, 500 ms, 1.5 s, 250 ms
        send=send,
        dump=dump_tracebacks,
    )
    thread = threading.Thread(target=loop, name="fake-loop", daemon=True)
    thread.start()
    try:
        call_soon(watchdog.start)  # as the shell does: on the loop's first turn
        deadline = time.monotonic() + 10
        while not any(s == WATCHDOG for _, s in sent) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert any(s == WATCHDOG for _, s in sent), "no ping while the loop is healthy"
        hang.set()
        assert trigger_seen.wait(10), f"no WATCHDOG=trigger; log: {logged}"
        triggered_at = sent[-1][0]
        pings_before = sum(1 for _, s in sent if s == WATCHDOG)
        time.sleep(0.5)  # the heartbeat is much older than 250 ms: nothing more is sent
        assert sum(1 for _, s in sent if s == WATCHDOG) == pings_before
        assert sent[-1] == (triggered_at, WATCHDOG_TRIGGER)  # one trigger, last thing sent
    finally:
        release.set()
        watchdog.stop()
        stop.set()
        thread.join(5)
    text = "\n".join(m for _, m in logged)
    first = next(m for _, m in logged if m.startswith("loop stalled"))
    assert "module Hang" in first and "entry point Hang.sleepy" in first
    assert "stuck_in_the_module" in text  # the traceback of the stuck thread names the function
    assert "fake-loop" in text
