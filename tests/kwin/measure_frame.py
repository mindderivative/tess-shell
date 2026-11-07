"""Measure the Frame's cost: one full-output painter and four reservers (M3c C1, G8; not
collected by pytest).

Run it on KWin through the generated ``/tmp/tess-kwin-m3c/measure.sh`` (``prepare_m3c_frame.py``),
or by hand: ``uv run python tests/kwin/measure_frame.py --output=HDMI-A-1``. It opens the same
windows the shell does (the painter draws the real ring of ``tess_shell.surfaces.ring``) and
prints, labelled, what the Frame costs:

* the process's resident memory (``VmRSS``, ``VmHWM``, and the proportional share ``Pss`` from
  ``smaps_rollup``, which splits the memory the GPU stack shares) before any window and idle with
  the windows open, plus the same summed over every child process (tre may start helpers) and
  the thread count,
* tre's video memory for the shared device (``frame_stats()['memory']``),
* the CPU time used in 5 s of idling (user plus system, whole process and children),
* the frames each window drew in 3 s of idling (``frame_stats()['frames']``): a static ring
  should draw none,
* then, unless ``--auto``, it stays open so the work area can be checked by eye: maximise a
  window; it must stop inside the ring on all four sides. Ctrl+C stops it.

``--morph`` plays the first melded body's grow-out and retreat (an ``svg`` whose ``d`` morphs,
driven by ``svg_time`` in the engine) in a loop for 3 s after the idle samples and prints the cost
of the frames drawn meanwhile (``frame_stats()['recent']``), next to the same for a node that only
translates; it needs a painter (``--melds`` defaults to 1). ``--melds=N`` (0 to 8) melds N bodies of 100 x 40 px into the opening (top and bottom at the start,
centre and end, left and right at the centre), the way a hosted Panel is drawn, and prints what the
one-contour path costs: the time to build it, its size, the number of ``warning`` events tre sent
the painter (a 256-rectangle input-region cap shows up there) and the cost of the painter's last
frame. Options: ``--output=NAME`` (default: tre's choice), ``--thickness=N`` (default 24),
``--only=painter|reservers`` (measure one kind alone, to split the cost), ``--auto`` (stop after
the report; for a private compositor), ``--settle=S`` (seconds before the first sample, 2).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from importlib.metadata import version
from typing import Any

import tess_re

from tess_shell.surfaces.ring import MeldSpec, RingSpec, ring

ARGS = {a.split("=", 1)[0]: (a.split("=", 1) + [""])[1] for a in sys.argv[1:]}
OUTPUT = ARGS.get("--output") or None
THICKNESS = int(ARGS.get("--thickness") or 24)
ONLY = ARGS.get("--only") or None
AUTO = "--auto" in ARGS
SETTLE = float(ARGS.get("--settle") or 2)
MORPH = "--morph" in ARGS  # play the first body's grow-out in a loop for 3 s and report the frames
MELDS = int(ARGS.get("--melds") or (1 if MORPH else 0))  # bodies melded into the opening, 0 to 8
IDLE_CPU = 5.0
IDLE_FRAMES = 3.0
TICK = os.sysconf("SC_CLK_TCK")


def say(text: str = "") -> None:
    print(text, flush=True)


# -- /proc readers ------------------------------------------------------------------------------


def status(pid: int | str = "self") -> dict[str, int]:
    """``VmRSS``, ``VmHWM`` and ``Threads`` of a process (kB and count)."""
    out: dict[str, int] = {}
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                key, _, rest = line.partition(":")
                if key in ("VmRSS", "VmHWM", "Threads"):
                    out[key] = int(rest.split()[0])
    except OSError:
        pass
    return out


def pss_kb(pid: int | str = "self") -> int | None:
    try:
        with open(f"/proc/{pid}/smaps_rollup") as f:
            for line in f:
                if line.startswith("Pss:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return None


def descendants(root: int) -> list[int]:
    """Every process below ``root`` (tre may start helper processes)."""
    parents: dict[int, int] = {}
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                with open(f"/proc/{entry}/stat") as f:
                    parents[int(entry)] = int(f.read().rsplit(")", 1)[1].split()[1])
            except OSError, ValueError:
                continue
    found: list[int] = []
    todo = [root]
    while todo:
        pid = todo.pop()
        for child, parent in parents.items():
            if parent == pid:
                found.append(child)
                todo.append(child)
    return found


def memory(label: str) -> dict[str, int]:
    me = status()
    kids = descendants(os.getpid())
    kid_rss = sum(status(p).get("VmRSS", 0) for p in kids)
    pss = pss_kb()
    row = {
        "rss": me.get("VmRSS", 0),
        "hwm": me.get("VmHWM", 0),
        "threads": me.get("Threads", 0),
        "children": len(kids),
        "children_rss": kid_rss,
        "pss": pss or 0,
    }
    say(
        f"{label:34} RSS {row['rss'] / 1024:7.1f} MiB   peak {row['hwm'] / 1024:7.1f} MiB   "
        f"Pss {row['pss'] / 1024:7.1f} MiB   threads {row['threads']}   "
        f"child processes {row['children']} (RSS {kid_rss / 1024:.1f} MiB)"
    )
    return row


def cpu() -> float:
    t = os.times()
    return t.user + t.system + t.children_user + t.children_system


# -- the windows --------------------------------------------------------------------------------

app = tess_re.App()
handle = app.thread_handle()
outputs = list(app.outputs())
chosen = next((o for o in outputs if OUTPUT in (None, o.name)), None)
if chosen is None:
    sys.exit(f"no output named {OUTPUT}; the outputs are {[o.name for o in outputs]}")
SIZE = (chosen.width, chosen.height)

say(f"{time.strftime('%H:%M:%S')} Frame measurement (tesserae-engine {version('tesserae-engine')})")
say(
    f"output {chosen.name} {SIZE[0]}x{SIZE[1]} logical, scale {chosen.scale_factor}; "
    f"thickness {THICKNESS}; windows: "
    f"{'painter' if ONLY != 'reservers' else ''}"
    f"{' + ' if ONLY is None else ''}{'4 reservers' if ONLY != 'painter' else ''}"
)
baseline = memory("before any window")

windows: dict[str, Any] = {}
results: dict[str, Any] = {}
if ONLY != "reservers":
    _PLACES = (
        ("top", "START"),
        ("top", "CENTER"),
        ("top", "END"),
        ("bottom", "START"),
        ("bottom", "CENTER"),
        ("bottom", "END"),
        ("left", "CENTER"),
        ("right", "CENTER"),
    )
    melds = tuple(
        MeldSpec(side, 100, 40, alignment, (8, 8, 8, 8)) for side, alignment in _PLACES[:MELDS]
    )
    t0 = time.perf_counter()
    shape = ring(
        RingSpec(
            thickness=(THICKNESS, THICKNESS, THICKNESS, THICKNESS),
            inner_radius=(THICKNESS, THICKNESS, THICKNESS, THICKNESS),
            outer_border=1,
            inner_border=1,
            melds=melds,
        ),
        SIZE,
    )
    built_ms = (time.perf_counter() - t0) * 1000
    say(
        f"ring with {MELDS} melds: built in {built_ms:.2f} ms; path data "
        f"{len(shape.fill) + len(shape.inner_border) + len(shape.outer_border)} characters; "
        f"{sum(1 for b in shape.bodies if b is not None)} bodies placed; {shape.warnings}"
    )
    painter = tess_re.LayerWindow(
        "tesserae-shell.frame.measure",
        layer="top",
        anchor=("top", "right", "bottom", "left"),
        size=(0, 0),
        exclusive_zone=-1,
        keyboard="none",
        input_region="auto",
        output=chosen.name,
    )
    for data, colour in (
        (shape.outer_border, (255, 255, 255, 60)),
        (shape.fill, (20, 24, 30, 255)),
        (shape.inner_border, (137, 180, 250, 255)),
    ):
        node = painter.create(
            "path",
            data=data,
            fill=colour,
            hit_shape="painted",
            position="absolute",
            left=0,
            top=0,
            width=SIZE[0],
            height=SIZE[1],
        )
        painter.root.add_child(node)
    windows["painter"] = painter
    warnings: list[str] = []
    painter.on("warning", lambda e: warnings.append(f"{e.key}: {e.message}"))
    results["warnings"] = warnings
if ONLY != "painter":
    zone = THICKNESS + 2
    for side, anchors, size in (
        ("left", ("left", "top", "bottom"), (1, 0)),
        ("top", ("top", "left", "right"), (0, 1)),
        ("right", ("right", "top", "bottom"), (1, 0)),
        ("bottom", ("bottom", "left", "right"), (0, 1)),
    ):
        windows[side] = tess_re.LayerWindow(
            f"tesserae-shell.frame.measure.{side}",
            layer="top",
            anchor=anchors,
            size=size,
            exclusive_zone=zone,
            keyboard="none",
            input_region=[],
            output=chosen.name,
        )
for window in windows.values():
    app.add_window(window)

main = next(iter(windows.values()))


def frames() -> dict[str, int]:
    return {name: int(w.frame_stats()["frames"]) for name, w in windows.items()}


def sample_idle_memory() -> None:
    say()
    row = memory("windows open, idle")
    say(
        f"{'  added by the windows':34} RSS {(row['rss'] - baseline['rss']) / 1024:+7.1f} MiB   "
        f"Pss {(row['pss'] - baseline['pss']) / 1024:+7.1f} MiB"
    )
    stats = main.frame_stats()
    mem = stats.get("memory")
    if mem:
        say(
            f"tre video memory (shared device): allocated "
            f"{mem['allocated_bytes'] / 2**20:.1f} MiB, reserved {mem['reserved_bytes'] / 2**20:.1f} MiB"
            f"; biggest: {[(b['name'], round(b['bytes'] / 2**20, 1)) for b in mem['largest'][:3]]}"
        )
    else:
        say("tre video memory: not reported by this backend")
    results["cpu0"], results["t0"] = cpu(), time.monotonic()
    say(f"{time.strftime('%H:%M:%S')} idling for {IDLE_CPU:.0f} s to measure CPU time ...")
    main.after(int(IDLE_CPU * 1000), sample_cpu)


def sample_cpu() -> None:
    used = cpu() - results["cpu0"]
    wall = time.monotonic() - results["t0"]
    say(
        f"CPU time in {wall:.1f} s of idle: {used * 1000:.0f} ms "
        f"({100 * used / wall:.2f} % of one core)"
    )
    results["frames0"] = frames()
    say(f"counting frames for {IDLE_FRAMES:.0f} s ...")
    main.after(int(IDLE_FRAMES * 1000), sample_frames)


def sample_frames() -> None:
    after = frames()
    if "painter" in windows:
        last = windows["painter"].frame_stats().get("last")
        say(f"painter's last frame: {last}")
        say(f"painter warnings (an input-region cap would be here): {results['warnings']}")
    drawn = {k: after[k] - results["frames0"][k] for k in after}
    say(f"frames drawn in {IDLE_FRAMES:.0f} s of idle: {drawn}  (a static ring should draw none)")
    memory("after the idle samples")
    if MORPH and "painter" in windows:
        run_morph()
        return
    say()
    say(
        f"work area: with the zones reserved ({THICKNESS + 2} px on each side with a reserver),"
        " maximise a window now: it must stop inside the ring on all four sides."
    )
    if AUTO:
        handle.stop()
    else:
        say("Ctrl+C stops the measurement.")


def stats_line(label: str, window: Any) -> None:
    recent = window.frame_stats()["recent"]
    say(
        f"{label}: {recent['count']} frames, {recent['fps']:.0f} fps; cpu_ms mean "
        f"{recent['cpu_ms']['mean']:.2f} p95 {recent['cpu_ms']['p95']:.2f} max "
        f"{recent['cpu_ms']['max']:.2f}; total_ms mean {recent['total_ms']['mean']:.1f} p95 "
        f"{recent['total_ms']['p95']:.1f}; stages {recent['stage_ms']}"
    )


def run_morph() -> None:
    """Loop the body's svg morph, then a plain translate of a box, for 3 s each."""
    painter = windows["painter"]
    f0, b0 = shape.morph({0: 0.0})  # type: ignore[misc]
    f1, b1 = shape.morph({0: 1.0})  # type: ignore[misc]
    w, h = SIZE
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<path fill="#14181e" d="{f0}"><animate attributeName="d" values="{f0};{f1}" dur="1s" '
        'fill="freeze"/></path>'
        f'<path fill="#89b4fa" d="{b0}"><animate attributeName="d" values="{b0};{b1}" dur="1s" '
        'fill="freeze"/></path></svg>'
    )
    node = painter.create(
        "svg",
        svg=document,
        position="absolute",
        left=0,
        top=0,
        width=w,
        height=h,
        hit_testable=False,
    )
    painter.root.add_child(node)
    state = {"on": True, "end": time.monotonic() + 3.0}
    painter.frame_stats(reset=True)

    def loop(forward: bool = True) -> None:
        if time.monotonic() > state["end"]:
            stats_line("svg morph (the ring's contour with a growing body)", painter)
            plain()
            return
        node.animate(
            "svg_time",
            1.0 if forward else 0.0,
            300,
            (0.4, 0.0, 0.2, 1.0),
            lambda: loop(not forward),
        )

    def plain() -> None:
        node.set(visible=False)
        box = painter.create(
            "box",
            position="absolute",
            left=100,
            top=100,
            width=100,
            height=40,
            fill=(255, 0, 0, 255),
        )
        painter.root.add_child(box)
        painter.frame_stats(reset=True)
        end = time.monotonic() + 3.0

        def back(forward: bool = True) -> None:
            if time.monotonic() > end:
                stats_line("a box that only translates", painter)
                say()
                say("Ctrl+C stops the measurement." if not AUTO else "done")
                if AUTO:
                    handle.stop()
                return
            box.animate(
                "translate_y",
                40.0 if forward else 0.0,
                300,
                (0.4, 0.0, 0.2, 1.0),
                lambda: back(not forward),
            )

        back()

    say("morphing for 3 s ...")
    loop()


main.after(int(SETTLE * 1000), sample_idle_memory)

# the event loop blocks the main thread in the engine, so Ctrl+C needs the shell's signal watcher
from tess_shell.signals import SignalWatcher  # noqa: E402


def force() -> None:
    os._exit(130)


watcher = SignalWatcher(handle.stop, force)  # type: ignore[arg-type]
watcher.start()
threading.current_thread().name = "measure-main"
try:
    app.run(keep_alive=True)
finally:
    watcher.close()
say("stopped")
