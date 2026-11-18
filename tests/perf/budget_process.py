"""The budgets read on the whole shell as a process (``tests/perf/read_budgets.py`` runs these).

Each ``measure_*`` takes the :class:`Plan` and the sandbox and returns :class:`Reading` objects.
They run ``tesserae-shell`` as a child in the private sway with the fakes of ``budget_rig`` and
read ``/proc``, the stderr of the shell and the datagrams it sends to its ``NOTIFY_SOCKET``; they
never touch the real session. Not collected by pytest.
"""

from __future__ import annotations

import contextlib
import json
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from tests.perf import budget_rig as br
from tests.perf.budget_report import Reading

SECONDS_PER_MINUTE = 60.0
WATCHDOG_SCALE = "TESS_SHELL_TEST_WATCHDOG_SCALE"
CALLBACKS_OUT = "TESS_BUDGET_CALLBACKS_OUT"
MIB = 1024.0


@dataclass(frozen=True, slots=True)
class Plan:
    """How long and how often each measure runs: ``--quick`` is the smoke, the default the real
    reading. ``estimate`` is what the process-level measures take, in seconds."""

    quick: bool
    idle_seconds: float
    idle_settle: float
    idle_runs: tuple[tuple[str, int], ...]  # (scene, repeats)
    start_runs: int
    reload_saves: int
    callback_seconds: float
    control_calls: int
    watchdog_runs: int
    watchdog_scale: float
    surface_runs: int

    @classmethod
    def make(cls, quick: bool) -> Plan:
        if quick:
            return cls(
                quick=True,
                idle_seconds=12.0,
                idle_settle=3.0,
                idle_runs=(
                    ("bar", 1),
                    ("default", 1),
                    ("supervised", 1),
                    ("wdoff", 1),
                    ("wd2s", 1),
                ),
                start_runs=3,
                reload_saves=5,
                callback_seconds=20.0,
                control_calls=10,
                watchdog_runs=1,
                watchdog_scale=0.2,
                surface_runs=1,
            )
        return cls(
            quick=False,
            idle_seconds=60.0,
            idle_settle=5.0,
            idle_runs=(
                ("none", 2),
                ("bar", 2),
                ("default", 3),
                ("supervised", 2),
                ("wdoff", 2),
                ("wd2s", 2),
                ("seconds", 2),
            ),
            start_runs=10,
            reload_saves=20,
            callback_seconds=45.0,
            control_calls=30,
            watchdog_runs=3,
            watchdog_scale=1.0,
            surface_runs=3,
        )

    @property
    def estimate(self) -> float:
        idle = sum(n * (self.idle_seconds + self.idle_settle + 6) for _, n in self.idle_runs)
        start = (self.start_runs + 1) * 5
        reload = 8 + self.reload_saves * 1.2
        callbacks = 10 + self.callback_seconds
        control = 8 + self.control_calls * 0.3
        watchdog = self.watchdog_runs * (10 + 25 * self.watchdog_scale)
        surfaces = self.surface_runs * 6 * 3.5 + 6
        return idle + start + reload + callbacks + control + watchdog + surfaces


# -- sampling the threads --------------------------------------------------------------------------

GROUPS = (
    "loop (main thread)",
    "watchdog",
    "tre helpers",
    "software renderer",
    "dbus service thread",
    "logging writers",
    "file watcher",
    "time source",
    "signal watcher",
    "other",
)


def group_of(tid: int, pid: int, name: str) -> str:
    if tid == pid:
        return "loop (main thread)"
    if name == "watchdog":
        return "watchdog"
    if name in ("async-io",) or name.startswith(("blocking", "zbus", "tre-")):
        return "tre helpers"
    if name.startswith(("llvmpipe", "python:")):
        return "software renderer"
    if name == "dbus":
        return "dbus service thread"
    if name.startswith("loguru"):
        return "logging writers"
    if name == "file-watcher":
        return "file watcher"
    if name == "time-source":
        return "time source"
    if name == "signal-watcher":
        return "signal watcher"
    return "other"


@dataclass(slots=True)
class Bin:
    """One sampling interval: wall-clock span and the switches each group made in it."""

    begin: float  # time.time()
    end: float
    switches: dict[str, int] = field(default_factory=dict)
    voluntary: dict[str, int] = field(default_factory=dict)


def sample(pid: int, seconds: float, interval: float = 1.0) -> list[Bin]:
    """Per-group context switches of every thread of ``pid``, in bins of ``interval`` seconds."""
    bins: list[Bin] = []
    previous = br.thread_counts(pid)
    mark = time.time()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(max(0.0, min(interval, deadline - time.monotonic())))
        now = br.thread_counts(pid)
        end = time.time()
        row = Bin(mark, end)
        for tid, count in now.items():
            before = previous.get(tid)
            group = group_of(tid, pid, count.name)
            row.switches[group] = (
                row.switches.get(group, 0) + count.switches - (before.switches if before else 0)
            )
            row.voluntary[group] = (
                row.voluntary.get(group, 0) + count.voluntary - (before.voluntary if before else 0)
            )
        bins.append(row)
        previous, mark = now, end
    return bins


def near_minute(row: Bin, before: float = 1.0, after: float = 3.0) -> bool:
    """Does the bin overlap the second a minute ticks (a Clock showing minutes) and the burst
    after it? Those bins are the 'ticks' that D19 leaves out of the idle budget."""
    boundary = (row.begin // SECONDS_PER_MINUTE + 1) * SECONDS_PER_MINUTE
    if row.begin % SECONDS_PER_MINUTE < after:  # the bin starts just after a boundary
        boundary -= SECONDS_PER_MINUTE
    return row.begin < boundary + after and row.end > boundary - before


# -- B01, B02, B07, B13, B20, B22, B23, B25: the shell at idle -------------------------------------

SCENES = {
    "none": ("none", {}, "no surface (no main shell)", 0),
    "bar": ("bar", {}, "one Bar with a Clock (minute) and a Text", 1),
    "default": ("default", {}, "the default shell: eight modules and the Launcher", 2),
    "supervised": (
        "default",
        {"WATCHDOG_USEC": "15000000"},
        "the default shell under systemd's watchdog (WATCHDOG_USEC=15 s, as the unit sets it)",
        2,
    ),
    "seconds": (
        "seconds",
        {},
        "the default shell with the Clock showing seconds (a tick every second)",
        2,
    ),
    "wd2s": (
        "default",
        {WATCHDOG_SCALE: "2"},
        "the default shell with the watchdog's times doubled (tick 2 s, warn 4 s, restart 20 s): "
        "the heartbeat slowed to every 2 s",
        2,
    ),
    "wdoff": (
        "default",
        {WATCHDOG_SCALE: "1000"},
        "the default shell with the watchdog's times scaled by 1000 (the thread never wakes)",
        2,
    ),
}


@dataclass(slots=True)
class IdleRun:
    scene: str
    seconds: float
    cpu_percent: float
    rate_all: float  # switches per second, the whole window
    rate_between: float  # the same without the bins of a minute tick
    voluntary_between: float
    groups_between: dict[str, float]  # switches per second per group, without the minute bins
    group_totals: dict[str, int]  # switches over the whole window per group (voluntary)
    skipped_seconds: float
    threads: int
    rss_kib: int
    pss_kib: int
    pings: int
    window_seconds: float


def idle_run(rig: br.Rig, plan: Plan, scene: str) -> IdleRun:
    kind, env, _, surfaces = SCENES[scene]
    cfg = br.write_config(rig.root, kind, folder=f"cfg-idle-{scene}-{time.monotonic_ns()}")
    with br.running(rig, cfg, env=env) as shell:
        shell.wait_ready()
        for _ in range(100):  # every surface is configured: the first frames are drawn
            if shell.count("configured") >= surfaces:
                break
            time.sleep(0.1)
        time.sleep(plan.idle_settle)
        ticks0 = br.cpu_ticks(shell.pid)
        t0 = time.monotonic()
        pings0 = sum("WATCHDOG=1" in text for _, text in list(shell.notifications))
        bins = sample(shell.pid, plan.idle_seconds)
        elapsed = time.monotonic() - t0
        ticks1 = br.cpu_ticks(shell.pid)
        pings = sum("WATCHDOG=1" in text for _, text in list(shell.notifications)) - pings0
        rss, pss = br.memory_kib(shell.pid)
        threads = len(br.thread_counts(shell.pid))
        shell.terminate()
    kept = [b for b in bins if not near_minute(b)]
    kept_time = sum(b.end - b.begin for b in kept) or 1.0
    total_time = sum(b.end - b.begin for b in bins) or 1.0
    groups: dict[str, float] = {}
    totals: dict[str, int] = {}
    for group in GROUPS:
        groups[group] = sum(b.switches.get(group, 0) for b in kept) / kept_time
        totals[group] = sum(b.voluntary.get(group, 0) for b in bins)
    return IdleRun(
        scene=scene,
        seconds=elapsed,
        cpu_percent=100 * (ticks1 - ticks0) / br.CLOCK_TICKS / elapsed,
        rate_all=sum(sum(b.switches.values()) for b in bins) / total_time,
        rate_between=sum(sum(b.switches.values()) for b in kept) / kept_time,
        voluntary_between=sum(sum(b.voluntary.values()) for b in kept) / kept_time,
        groups_between=groups,
        group_totals=totals,
        skipped_seconds=total_time - kept_time,
        threads=threads,
        rss_kib=rss,
        pss_kib=pss,
        pings=pings,
        window_seconds=total_time,
    )


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def measure_idle(plan: Plan, rig: br.Rig) -> list[Reading]:
    runs: dict[str, list[IdleRun]] = defaultdict(list)
    for scene, repeats in plan.idle_runs:
        for _ in range(repeats):
            runs[scene].append(idle_run(rig, plan, scene))
    out: list[Reading] = []
    window = f"{plan.idle_seconds:g} s window after {plan.idle_settle:g} s of settling"
    for scene, scene_runs in runs.items():
        label = f"{SCENES[scene][2]}, {window}"
        out.append(
            Reading(
                "B01",
                label,
                [r.cpu_percent for r in scene_runs],
                "% of one core",
                0.5,
                note="utime + stime of every thread; the clock tick is 10 ms, so a 60 s window "
                "reads in steps of 0.017 %",
            )
        )
        out.append(
            Reading(
                "B02",
                f"{label}: between ticks (bins around the minute tick left out)",
                [r.rate_between for r in scene_runs],
                "per s",
                None if scene == "seconds" else 5.0,
                note=(
                    "a tick every second: there is no 'between ticks', so no verdict. "
                    if scene == "seconds"
                    else ""
                )
                + f"voluntary and involuntary switches of every thread; "
                f"{median([r.skipped_seconds for r in scene_runs]):.0f} s of the window left out",
            )
        )
        out.append(
            Reading(
                "B02",
                f"{label}: the whole window, tick included (information: D19 reads between ticks)",
                [r.rate_all for r in scene_runs],
                "per s",
                note="threads: " + ", ".join(sorted({str(r.threads) for r in scene_runs})),
            )
        )
    for scene in ("none", "bar", "default", "supervised"):
        if scene not in runs:
            continue
        label = SCENES[scene][2]
        mine = runs[scene]
        out.append(
            Reading(
                "B07",
                f"resident memory, {label}",
                [r.rss_kib / MIB for r in mine],
                "MiB RSS",
                note="read at the end of the idle window; includes the engine, the software "
                "Vulkan driver and its render threads",
            )
        )
        out.append(
            Reading(
                "B07",
                f"proportional memory (PSS), {label}",
                [r.pss_kib / MIB for r in mine],
                "MiB PSS",
                note="PSS splits the pages shared with other processes (the driver libraries)",
            )
        )
    if runs.get("seconds"):
        out.append(
            Reading(
                "B22",
                "time-source thread with the Clock showing seconds: voluntary switches per second",
                [r.group_totals["time source"] / r.window_seconds for r in runs["seconds"]],
                "per s",
                note="the Clock's tick is one a second: the time source must not wake faster than "
                "the finest unit shown (one wake-up per tick is expected)",
            )
        )
    default = runs.get("default", [])
    if default:
        out.extend(
            idle_attribution(
                default, runs.get("supervised", []), runs.get("wdoff", []), runs.get("wd2s", [])
            )
        )
        out.extend(thread_rows(default, plan))
    return out


def idle_attribution(
    default: list[IdleRun],
    supervised: list[IdleRun],
    wdoff: list[IdleRun],
    slow: list[IdleRun],
) -> list[Reading]:
    """B25 and where the idle wake-ups of the default shell are."""
    out: list[Reading] = []
    for group in GROUPS:
        rates = [r.groups_between[group] for r in default]
        if median(rates) > 0 or group in ("loop (main thread)", "watchdog"):
            out.append(
                Reading(
                    "B02",
                    f"default shell, between ticks: the {group}",
                    rates,
                    "per s",
                    note="where the wake-ups are (context switches by thread group)",
                )
            )
    note = (
        "the loop is woken by the heartbeat's call_soon: it is the loop thread's share. "
        "tre's own helper threads (blocking-N: the OS-preference watcher) are a floor the shell "
        "does not control"
    )
    out.append(
        Reading(
            "B25",
            "watchdog thread, default shell, between ticks",
            [r.groups_between["watchdog"] for r in default],
            "per s",
            note="the thread wakes once per tick (1 s)",
        )
    )
    out.append(
        Reading(
            "B25",
            "loop thread, default shell, between ticks",
            [r.groups_between["loop (main thread)"] for r in default],
            "per s",
            note=note,
        )
    )
    if wdoff:
        out.append(
            Reading(
                "B25",
                "loop thread, watchdog off, between ticks",
                [r.groups_between["loop (main thread)"] for r in wdoff],
                "per s",
                note="the same shell with the watchdog's times scaled by 1000",
            )
        )
        out.append(
            Reading(
                "B25",
                "whole shell with the watchdog minus whole shell without it",
                [median([r.rate_between for r in default]) - r.rate_between for r in wdoff],
                "per s",
                note="the heartbeat and the watchdog's own cost in wake-ups: loop plus thread plus "
                "whatever tre wakes for the queued call (one paired difference per run without)",
            )
        )
    if slow:
        out.append(
            Reading(
                "B25",
                "whole shell with the heartbeat slowed to every 2 s (the watchdog's times doubled)",
                [r.rate_between for r in slow],
                "per s",
                note="what the slowing would leave: the same default shell, TESS_SHELL_TEST_"
                "WATCHDOG_SCALE=2; the stall warning would come at 4 s and the restart at 20 s, "
                "so this is the wake-up saving only: a real change keeps 2 s and 10 s",
            )
        )
        out.append(
            Reading(
                "B25",
                "wake-ups saved per second by a 2 s heartbeat (default minus slowed)",
                [median([r.rate_between for r in default]) - r.rate_between for r in slow],
                "per s",
                note="paired with the median of the default runs",
            )
        )
    if supervised:
        out.append(
            Reading(
                "B25",
                "whole shell under the systemd watchdog (WATCHDOG_USEC 15 s), between ticks",
                [r.rate_between for r in supervised],
                "per s",
                note="the unit's setting; the same heartbeat plus a datagram every 7.5 s",
            )
        )
        out.append(
            Reading(
                "B25",
                "WATCHDOG=1 datagrams per second (supervised)",
                [r.pings / r.window_seconds for r in supervised],
                "per s",
                note="the vault says one every WatchdogSec / 2 = 7.5 s (0.133 per s)",
            )
        )
    return out


def thread_rows(default: list[IdleRun], plan: Plan) -> list[Reading]:
    """B13, B20, B22, B23: the threads the shell owns do not wake at idle."""
    window = f"{plan.idle_seconds:g} s idle window"

    def total(group: str) -> list[float]:
        return [float(r.group_totals[group]) for r in default]

    return [
        Reading(
            "B13",
            f"dbus service thread of the default shell, voluntary switches in the {window}",
            total("dbus service thread"),
            "switches",
            0.0,
            stat="max",
            note="fake buses with no signal traffic; the thread also serves Audio, the tray host, "
            "the control interface and the shortcuts",
        ),
        Reading(
            "B20",
            f"logging writer threads, voluntary switches in the {window}",
            total("logging writers"),
            "switches",
            0.0,
            stat="max",
            note="no record is written at idle: the writers sleep until one arrives",
        ),
        Reading(
            "B23",
            f"file watcher threads, voluntary switches in the {window}",
            total("file watcher"),
            "switches",
            0.0,
            stat="max",
            note="the watchers block in select and wake on a file event only",
        ),
        Reading(
            "B22",
            f"time-source thread, voluntary switches in the {window} (a Clock showing minutes)",
            total("time source"),
            "switches",
            note="a Clock with %H:%M subscribes to the minute: a 60 s window holds one tick "
            "(a few switches); the time source never wakes faster than the finest unit shown",
        ),
    ]


# -- B03, B04, B05: start and stop -----------------------------------------------------------------

STEPS = (
    ("starting tesserae-shell", "the process printed its first line (interpreter and imports)"),
    ("loaded ", "settings and shell files read and validated"),
    ("step 10 (model)", "the model of uses and modules"),
    ("step 11 (surfaces)", "the surfaces created"),
    ("step 12 (modules)", "the modules started"),
    ("running", "the shell reports running"),
)


def exit_codes(codes: list[int | None]) -> str:
    seen = sorted({str(c) for c in codes if c is not None})
    return ", ".join(seen or ["-"]) + (" (a run had to be killed)" if None in codes else "")


def measure_start_stop(plan: Plan, rig: br.Rig) -> list[Reading]:
    cfg = br.write_config(rig.root, "default", folder="cfg-start")
    first: list[float] = []
    ready: list[float] = []
    stops: list[float] = []
    codes: list[int | None] = []
    steps: dict[str, list[float]] = defaultdict(list)
    for index in range(plan.start_runs + 1):
        with br.running(rig, cfg) as shell:
            took_ready = shell.wait_ready()
            configured = shell.wait_line("configured") - shell.started
            for text, _ in STEPS:
                when = shell.find(text)
                if when is not None and index > 0:
                    steps[text].append(when - shell.started)
            time.sleep(1.0)  # the shell is up: a stop of a shell that finished starting
            took, code = shell.terminate()
        if index == 0:
            continue  # the cold start: files are read and compiled for the first time
        first.append(configured)
        ready.append(took_ready)
        stops.append(took)
        codes.append(code)
    out = [
        Reading(
            "B03",
            "default shell: Popen to the first surface configured by the compositor",
            first,
            "s",
            1.0,
            note=f"{plan.start_runs} starts after one discarded cold start (warm cache); the "
            "first surface is the first 'configured' line",
        ),
        Reading(
            "B04",
            "default shell: Popen to READY=1 on NOTIFY_SOCKET",
            ready,
            "s",
            2.0,
            note="READY=1 follows step 12, the modules started",
        ),
        Reading(
            "B05",
            "default shell: SIGTERM to the process gone",
            stops,
            "s",
            10.0,
            stat="max",
            note=f"exit codes: {exit_codes(codes)}",
        ),
    ]
    for text, meaning in STEPS:
        if steps[text]:
            out.append(
                Reading(
                    "B03",
                    f"step of the start: '{text}': {meaning}",
                    steps[text],
                    "s",
                    note="seconds from Popen; the log's own steps",
                )
            )
    return out


# -- B06: hot reload -------------------------------------------------------------------------------

RELOADED = re.compile(r"reloaded[^(]*\(([^)]*)\) in (\d+) ms")


def reload_lines(shell: br.Shell) -> list[tuple[float, re.Match[str]]]:
    """The summary lines of the reloader, ``reloaded (Main_Shell.tdl) in 7 ms`` (the surfaces log
    their own ``reloaded: 0 changed`` lines)."""
    found = []
    for when, line in list(shell.lines):
        match = RELOADED.search(line)
        if match:
            found.append((when, match))
    return found


def measure_reload(plan: Plan, rig: br.Rig) -> list[Reading]:
    cfg = br.write_config(rig.root, "ten", folder="cfg-reload")
    shell_file = cfg / "Shells" / "Main_Shell.tdl"
    apply_ms: list[float] = []
    end_to_end: list[float] = []
    with br.running(rig, cfg) as shell:
        shell.wait_ready()
        for _ in range(200):
            if shell.count("configured") >= 10:
                break
            time.sleep(0.1)
        time.sleep(1.0)
        heights = ("34", "36")
        for index in range(plan.reload_saves):
            before = len(reload_lines(shell))
            old, new = heights[index % 2], heights[(index + 1) % 2]
            text = shell_file.read_text()
            assert f"Height: {old}," in text
            saved = time.monotonic()
            shell_file.write_text(text.replace(f"Height: {old},", f"Height: {new},", 1))
            deadline = time.monotonic() + 10
            while len(reload_lines(shell)) <= before and time.monotonic() < deadline:
                time.sleep(0.005)
            lines = reload_lines(shell)
            if len(lines) <= before:
                raise RuntimeError("no reload line after a save:\n" + shell.stderr()[-1500:])
            when, match = lines[before]
            apply_ms.append(float(match.group(2)))
            end_to_end.append((when - saved) * 1000)
            time.sleep(0.5)
        shell.terminate()
    return [
        Reading(
            "B06",
            "10 surfaces (a Bar and 9 shown Panels): the reload's own time after the debounce",
            apply_ms,
            "ms",
            100.0,
            note="validate, diff and set, from the log line 'reloaded (...) in N ms'; whole "
            "milliseconds, so a 0.4 ms reload reads 0",
        ),
        Reading(
            "B06",
            "10 surfaces: from the save to the 'reloaded' line (debounce 200 ms included)",
            end_to_end,
            "ms",
            300.0,
            note="the spec's acceptance is 'about 300 ms from the save to the change'; the log "
            "line is when the shell finished applying, the compositor's reflow follows",
        ),
    ]


# -- B09, B12 (loop side), B22: callbacks and commands on the loop ---------------------------------

UPOWER = ("org.freedesktop.UPower", "/org/freedesktop/UPower/devices/DisplayDevice")
UPOWER_INTERFACE = "org.freedesktop.UPower.Device"
KWIN_VDM = ("org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager")


def busctl(address: str, *args: str) -> None:
    subprocess.run(
        ["busctl", f"--address={address}", *args],
        capture_output=True,
        timeout=10,
        check=False,
        stdin=subprocess.DEVNULL,
    )


def client(rig: br.Rig, cfg: Path, *args: str) -> tuple[float, str, int]:
    """One run of the thin client (``tesserae-shell ARGS``): wall seconds, output, exit code."""
    began = time.monotonic()
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", *args, "--config-dir", str(cfg)],
        env=rig.env(),
        cwd=br.REPO,
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    return time.monotonic() - began, done.stdout + done.stderr, done.returncode


def stimulate(rig: br.Rig, cfg: Path, seconds: float) -> int:
    """Things that make the default shell's modules run: the battery and the desktop change on
    the fake buses, the control interface toggles the Launcher and calls an Audio action."""
    deadline = time.monotonic() + seconds
    count = 0
    while time.monotonic() < deadline:
        count += 1
        busctl(
            rig.system_bus,
            "set-property",
            *UPOWER,
            UPOWER_INTERFACE,
            "Percentage",
            "d",
            str(55 + count % 30),
        )
        busctl(
            rig.session_bus,
            "set-property",
            *KWIN_VDM[:2],
            KWIN_VDM[2],
            "current",
            "s",
            f"d{count % 3}",
        )
        client(rig, cfg, "toggle", "Launcher")
        client(rig, cfg, "call", "Audio", "set_volume", str(30 + count % 40))
        time.sleep(0.3)
    return count


@dataclass(slots=True)
class CallbackData:
    rows: list[tuple[str, str, float, float]]
    ready_at: float
    stimuli: int


def callback_run(plan: Plan, rig: br.Rig) -> CallbackData:
    cfg = br.write_config(rig.root, "seconds", folder="cfg-callbacks")
    out = rig.root / "callbacks.json"
    env = {CALLBACKS_OUT: str(out)}
    with br.running(rig, cfg, module="tests.perf.budget_shell", env=env) as shell:
        shell.wait_ready()
        ready_at = shell.wait_line("running")
        for _ in range(100):
            if shell.count("configured") >= 2:
                break
            time.sleep(0.1)
        time.sleep(2.0)
        stimuli = stimulate(rig, cfg, plan.callback_seconds)
        shell.terminate()
    rows = [(a, b, float(c), float(d)) for a, b, c, d in json.loads(out.read_text())]
    return CallbackData(rows, ready_at, stimuli)


def top_entries(rows: list[tuple[str, str, float, float]], count: int = 3) -> str:
    worst: dict[tuple[str, str], float] = {}
    for module, entry, _, took in rows:
        key = (module, entry)
        worst[key] = max(worst.get(key, 0.0), took)
    best = sorted(worst.items(), key=lambda kv: -kv[1])[:count]
    return ", ".join(f"{m}.{e} {t * 1000:.1f} ms" for (m, e), t in best)


def measure_callbacks(plan: Plan, rig: br.Rig) -> list[Reading]:
    data = callback_run(plan, rig)
    modules = [r for r in data.rows if r[0] != "command"]
    steady = [r for r in modules if r[2] >= data.ready_at]
    startup = [r for r in modules if r[2] < data.ready_at]
    ms_steady = [r[3] * 1000 for r in steady]
    ms_start = [r[3] * 1000 for r in startup]
    out: list[Reading] = []
    what = (
        f"the default shell with a Clock showing seconds, {len(steady)} module callbacks after "
        f"'running' ({data.stimuli} rounds of battery, desktop, toggle and call)"
    )
    if ms_steady:
        out.append(
            Reading(
                "B09",
                f"{what}: 99th percentile",
                ms_steady,
                "ms",
                4.0,
                stat="p99",
                note=f"heaviest: {top_entries(steady)}",
            )
        )
        out.append(
            Reading(
                "B09",
                f"{what}: the slowest",
                ms_steady,
                "ms",
                4.0,
                stat="max",
                note="a single callback preempted by another process counts here",
            )
        )
    if ms_start:
        out.append(
            Reading(
                "B09",
                f"the {len(startup)} callbacks of the start (import, __init__, start of every "
                "module, at step 12): the slowest",
                ms_start,
                "ms",
                4.0,
                stat="max",
                note=f"heaviest: {top_entries(startup)}; the loop is held while a module starts",
            )
        )
    ticks = [r[3] * 1000 for r in modules if r[0] == "Clock" and "tick" in r[1]]
    if ticks:
        out.append(
            Reading(
                "B22",
                f"Clock tick callbacks on the loop ({len(ticks)} ticks, seconds and minutes)",
                ticks,
                "ms",
                1.0,
                stat="p99",
                note="the Clock's tick and tick_seconds entry points",
            )
        )
    commands = [r[3] * 1000 for r in data.rows if r[0] == "command" and r[1] == "surface"]
    if commands:
        out.append(
            Reading(
                "B12",
                f"loop callback of a `toggle Launcher` ({len(commands)} toggles): "
                "ShellCommands.surface",
                commands,
                "ms",
                1.0,
                stat="p99",
                note="shows or hides the Launcher Panel (one lookup and the tre calls)",
            )
        )
    return out


# -- B12, B21: the control interface and the thin client -------------------------------------------


def measure_control(plan: Plan, rig: br.Rig) -> list[Reading]:
    cfg = br.write_config(rig.root, "default", folder="cfg-control")
    toggles: list[float] = []
    statuses: list[float] = []
    bare: list[float] = []
    with br.running(rig, cfg) as shell:
        shell.wait_ready()
        for _ in range(100):
            if shell.count("configured") >= 2:
                break
            time.sleep(0.1)
        time.sleep(2.0)
        for _ in range(3):  # warm: the first calls read the files into the page cache
            client(rig, cfg, "status")
        for _ in range(plan.control_calls):
            took, _, code = client(rig, cfg, "toggle", "Launcher")
            assert code == 0
            toggles.append(took * 1000)
            took, _, code = client(rig, cfg, "status")
            assert code == 0
            statuses.append(took * 1000)
            time.sleep(0.05)
        shell.terminate()
    for _ in range(plan.control_calls):
        began = time.monotonic()
        subprocess.run([sys.executable, "-c", "pass"], capture_output=True, check=True)
        bare.append((time.monotonic() - began) * 1000)
    return [
        Reading(
            "B12",
            f"`tesserae-shell toggle Launcher` end to end, start to exit ({len(toggles)} calls)",
            toggles,
            "ms",
            100.0,
            note="python -m tess_shell, the thin client, against the running default shell",
        ),
        Reading(
            "B21",
            f"`tesserae-shell status`, client start to exit ({len(statuses)} calls)",
            statuses,
            "ms",
            note="the vault says about 20 ms for a client that makes one call",
        ),
        Reading(
            "B21",
            "reference: `python -c pass`",
            bare,
            "ms",
            note="the interpreter's own start on this machine (the vault measured 7.6 ms)",
        ),
    ]


# -- B10: the watchdog -----------------------------------------------------------------------------

STALL_PY = '''"""A module that holds the loop: it sleeps in a tick callback when asked."""

import os
import time
from pathlib import Path

from tess_shell import Module


class Stall(Module):
    def start(self):
        self.ctx.on_tick("second", self.tick)

    def tick(self):
        trigger = Path(os.environ["TESS_STALL_DIR"]) / "go"
        if not trigger.exists():
            return
        trigger.unlink()
        (trigger.parent / "began").write_text(str(time.monotonic()))
        time.sleep(float(os.environ["TESS_STALL_SECONDS"]))
'''
STALL_TDL = 'Module { Text { Text: "x" } }\n'
STALL_WARNING = re.compile(r"loop stalled for (\d+) s")


def measure_watchdog(plan: Plan, rig: br.Rig) -> list[Reading]:
    scale = plan.watchdog_scale
    stall_seconds = 12.0 * scale if scale < 1 else 12.0
    logs: list[float] = []
    triggers: list[float] = []
    for run in range(plan.watchdog_runs):
        cfg = br.write_config(rig.root, "bar", folder=f"cfg-watchdog-{run}")
        folder = cfg / "Modules" / "Stall"
        folder.mkdir(parents=True)
        (folder / "Stall_Module.py").write_text(STALL_PY)
        (folder / "Stall_Module.tdl").write_text(
            "---\nTDL: 0.2\nShell: 0.1\nName: Stall\n---\n" + STALL_TDL
        )
        shell_file = cfg / "Shells" / "Main_Shell.tdl"
        shell_file.write_text(shell_file.read_text().replace("Spacer { }", "Spacer { } Stall { }"))
        probe = rig.root / f"stall-{run}"
        probe.mkdir()
        env = {
            "WATCHDOG_USEC": "15000000",
            "TESS_STALL_DIR": str(probe),
            "TESS_STALL_SECONDS": f"{stall_seconds:g}",
        }
        if scale < 1:
            env[WATCHDOG_SCALE] = f"{scale:g}"
        with br.running(rig, cfg, env=env) as shell:
            shell.wait_ready()
            shell.wait_line("running")
            time.sleep(2.0)
            (probe / "go").write_text("")
            deadline = time.monotonic() + 15
            while not (probe / "began").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            began = float((probe / "began").read_text())  # time.monotonic() of the module
            warn = shell.wait_line("loop stalled for", timeout=stall_seconds + 10, after=began)
            logs.append((warn - began) / scale)
            trigger_at = None
            end = time.monotonic() + stall_seconds + 10
            while trigger_at is None and time.monotonic() < end:
                for when, text in list(shell.notifications):
                    if "WATCHDOG=trigger" in text and when >= began:
                        trigger_at = when
                time.sleep(0.02)
            if trigger_at is None:
                raise RuntimeError("no WATCHDOG=trigger:\n" + shell.stderr()[-2000:])
            triggers.append((trigger_at - began) / scale)
            shell.terminate(timeout=stall_seconds + 20)
    scaled = (
        f" (smoke: the watchdog's times scaled by {scale:g} and the values scaled back)"
        if scale < 1
        else ""
    )
    return [
        Reading(
            "B10",
            f"first log line after the loop was blocked{scaled}",
            logs,
            "s",
            3.0,
            stat="max",
            note="the budget is 'a stall of 2 s logs'; the limit is 2 s plus one heartbeat "
            "period (1 s), the watchdog's own resolution, as the last beat was up to 1 s before "
            "the block began",
        ),
        Reading(
            "B10",
            f"WATCHDOG=trigger sent after the loop was blocked{scaled}",
            triggers,
            "s",
            11.0,
            stat="max",
            note="the budget is 'a stall of 10 s asks for the restart'; the limit is 10 s plus "
            "one heartbeat period",
        ),
    ]


# -- B17, B26: surfaces ----------------------------------------------------------------------------


def surface_child(rig: br.Rig, kind: str, *flags: str) -> dict[str, object]:
    done = subprocess.run(
        [sys.executable, "-m", "tests.perf.budget_surfaces", kind, "0", *flags],
        env=rig.sway.env,
        cwd=br.REPO,
        capture_output=True,
        text=True,
        timeout=90,
        stdin=subprocess.DEVNULL,
    )
    for line in reversed(done.stdout.splitlines()):
        if line.startswith("{"):
            result: dict[str, object] = json.loads(line)
            return result
    raise RuntimeError(f"no result from budget_surfaces {kind}: {done.stderr[-800:]}")


def set_resolution(rig: br.Rig, resolution: str) -> None:
    subprocess.run(
        ["swaymsg", "output", "HEADLESS-1", "resolution", resolution],
        env=rig.sway.env,
        capture_output=True,
        check=True,
    )


def measure_surfaces(plan: Plan, rig: br.Rig) -> list[Reading]:
    cases = (
        ("1280x720", "bar", "a 1280 x 32 Bar", "about 18 MiB"),
        ("1280x720", "small", "a 200 x 100 window", "about 31 MiB"),
        ("1280x720", "big", "a full-screen surface at 1280 x 720", ""),
        ("3840x2160", "big", "a full-screen surface at 3840 x 2160 (4K)", "about 177 MiB"),
        ("3840x2160", "bar", "a 3840 x 32 Bar at 4K", ""),
    )
    out: list[Reading] = []
    try:
        for resolution, kind, label, reference in cases:
            set_resolution(rig, resolution)
            runs = [surface_child(rig, kind) for _ in range(plan.surface_runs)]
            allocated = [float(str(r["allocated_bytes"])) / 2**20 for r in runs]
            frames = [float(str(r["idle_frames"])) for r in runs]
            note = (
                "tre's frame_stats()['memory'] of the process's one shared device, one window "
                "open; the first window carries the device's fixed buffers"
            )
            if reference:
                note += f"; the vault has {reference} for this on tre 0.5.8"
            out.append(Reading("B17", f"video memory, {label}", allocated, "MiB", note=note))
            out.append(
                Reading(
                    "B17",
                    f"frames drawn in 1 s of idling, {label}",
                    frames,
                    "frames",
                    0.0,
                    stat="max",
                    note="an idle surface draws no frames (Goals G4)",
                )
            )
            if kind == "big" and resolution == "3840x2160":
                out.append(
                    Reading(
                        "B07",
                        f"resident memory of one tre process with {label} and nothing else",
                        [float(str(r["rss_kib"])) / MIB for r in runs],
                        "MiB RSS",
                        note="the engine's floor for one window",
                    )
                )
        set_resolution(rig, "1280x720")
        runs = [surface_child(rig, "bar", "--animate") for _ in range(plan.surface_runs)]
        recent = [r["recent"] for r in runs if isinstance(r.get("recent"), dict)]
        for key, stat, label in (("total_ms", "p95", "p95"), ("total_ms", "max", "worst")):
            values = [float(r[key][stat]) for r in recent]  # type: ignore[index]
            out.append(
                Reading(
                    "B26",
                    f"time of a frame while a node moves every 16 ms ({label} of the last 240)",
                    values,
                    "ms",
                    16.7 if stat == "p95" else None,
                    note="a 1280 x 32 Bar on the software Vulkan driver (llvmpipe), a pessimistic "
                    "stand-in for a GPU; one frame at 60 Hz is 16.7 ms",
                )
            )
        out.append(
            Reading(
                "B26",
                "CPU time of a frame while a node moves every 16 ms (mean)",
                [float(r["cpu_ms"]["mean"]) for r in recent],  # type: ignore[index]
                "ms",
                note="tre's own account of the CPU part of the frame",
            )
        )
    finally:
        with contextlib.suppress(Exception):
            set_resolution(rig, "1280x720")
    return out


# -- not measured ----------------------------------------------------------------------------------


def not_measured() -> list[Reading]:
    return [
        Reading.not_measured(
            "B08",
            "looping icons at once",
            "applies only when the `mli` icon format ships; no module of the shell loops an icon "
            "today (Risk Register R-24 is open until tre adds a sampling cap), so there is "
            "nothing to count; the idle wake-up and frame counts above cover the rest",
        ),
    ]
