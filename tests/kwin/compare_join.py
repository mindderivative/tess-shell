"""Compare the ways of drawing a melded Panel's join, ``Debug { Frame_Join: SMIL | CONCAVE |
SHADER | STRUCTURE | PARAM }`` (not collected by pytest; Frame > Comparing the Join Options).

Run from the repo root with the project's environment:

    uv run python tests/kwin/compare_join.py                      # headless: frames, hits, size
    uv run python tests/kwin/compare_join.py --live --sway        # + cost on a private headless sway
    uv run python tests/kwin/compare_join.py --live               # + cost on the compositor you are on
    uv run python tests/kwin/compare_join.py --live --join=SHADER --output=HDMI-A-1 --seconds=4
    uv run python tests/kwin/compare_join.py --live --sway --join=PARAM --blend=LINEAR   # the shader ring

(``/tmp/tess-kwin-m3c/compare-join.sh`` runs the second form on KWin; ``prepare_m3c_strips.py``
writes it.) It prints one table per question and starts nothing on the desktop unless ``--live``
is given without ``--sway``.

``--blend=LINEAR`` runs every option with ``Debug { Frame_Blend: LINEAR }`` (the ring and its
bodies drawn by one shader that blends in linear light, ``surfaces/frame_shader.py``): the join is
then the shader's, which has PARAM's shape, so use it with ``--join=PARAM`` (the other options
fall back to paths with a warning). Run the same line with ``--blend=SRGB`` (the default) to compare
the cost.

What it does, for the options named by ``--join`` (default all):

* headless, always: renders the same 300 ms slide of the same melded Panel through the shell's
  own ``SurfaceManager`` at t = 0, 25, 50, 75 and 100 % at display scale 1.0 and 1.5, writes
  zoomed PNG sheets to ``--out`` (default ``/tmp/join-compare``: one sheet per option, scale and
  alignment, plus ``edge_*.png`` with the options side by side), and counts the pixels that differ
  from the SMIL build; simulates clicks through the contour (the body, the opening, a join's
  notch) at rest and half way; counts the lines of each option's code.
* ``--live``: in a fresh process per option and display, opens the real Frame with the option,
  slides the Panel in and out for ``--seconds`` and prints, from ``frame_stats()``, the cost of a
  frame while animating (``total_ms`` and ``cpu_ms``, mean and max), the frames drawn in 2 s once
  it is still (must be 0), the process's RSS and Pss and tre's video memory idle before and after
  the first slide. With ``--sway`` it starts a private headless sway (1920 x 1080) and repeats at
  each ``--scales`` (default 1,1.5); without it, it uses the compositor ``WAYLAND_DISPLAY`` names
  at that output's own scale.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tess_shell.surfaces.join import JOINS  # noqa: E402

FRAME = (
    "Frame { Name: F, Thickness: 24, Inner_Radius: 14, "
    'Inner_Border { Width: 2, Color: "#89b4fa" }, Style { Background: "#1e1e2e" } }'
)
MS = 300  # the slide
BLEND = "SRGB"  # ``--blend``: how the Frame's ring is blended in every scene
CODE = {  # the files that are each option's own code (SMIL's is the class in join.py)
    "SMIL": ("src/tess_shell/surfaces/join.py", "class SmilJoin"),
    "CONCAVE": ("src/tess_shell/surfaces/join_concave.py", None),
    "SHADER": ("src/tess_shell/surfaces/join_shader.py", None),
    "STRUCTURE": ("src/tess_shell/surfaces/join_structure.py", None),
    "PARAM": ("src/tess_shell/surfaces/join_param.py", None),
}
EASING = {  # what each option can do with the slide's easing: they all take tre's cubic-bezier
    "SMIL": "cubic-bezier on svg_time",
    "CONCAVE": "cubic-bezier per property",
    "SHADER": "cubic-bezier on the uniform",
    "STRUCTURE": "cubic-bezier on data",
    "PARAM": "cubic-bezier per parameter",
}


def panel(alignment: str = "CENTER", ms: int = MS, visible: bool = False) -> str:
    return (
        f"Panel {{ Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: {alignment}, "
        f"Length: 160, Depth: 70, {'' if visible else 'Visible: false, '}"
        f"Style {{ Corner_Radius: 12 }}, Animation {{ Type: SLIDE, Duration: {ms} }}, "
        'Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#f38ba8" } } }'
    )


# -- the tables ----------------------------------------------------------------------------------


def table(title: str, header: list[str], rows: list[list[str]]) -> None:
    widths = [max(len(header[i]), *(len(r[i]) for r in rows)) for i in range(len(header))]
    print(f"\n{title}")
    print("  ".join(h.ljust(w) for h, w in zip(header, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)))


# -- headless: frames, hits, size ----------------------------------------------------------------


def headless_scene(join: str, alignment: str, visible: bool = False) -> Any:
    from tess_shell.model.store import ValueStore
    from tess_shell.surfaces.manager import SurfaceManager
    from tests.test_frame import StubApp, look, only
    from tests.test_frame_strips import shell_of

    app = StubApp()
    manager = SurfaceManager(
        app,  # type: ignore[arg-type]
        {},
        lambda key: key[-1],
        ValueStore(),
        look(),
        join_mode=join,
        blend_mode=BLEND,
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(FRAME, panel(alignment, visible=visible)))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    st.painter.snapshot()
    return manager


def act(manager: Any, action: str) -> None:
    from tess_shell.binder.model import Handler

    manager.run_builtin(Handler(action, {"Target": "Tab"}, builtin=True))


def frames_of(join: str, alignment: str, scale: float, show: bool = True) -> list[bytes]:
    """The painter at 0, 25, 50, 75 and 100 % of the slide, as RGBA at ``scale``."""
    from tests.test_frame import only

    manager = headless_scene(join, alignment, visible=not show)
    st = only(manager)
    act(manager, "Show" if show else "Hide")
    got = [st.painter.snapshot(scale=scale)[0]]
    st.painter.advance(1)  # a shader's animation starts on the frame after the request
    done = 1
    for t in (0.25, 0.5, 0.75, 1.0):
        target = round(t * MS) + (60 if t == 1.0 else 0)
        st.painter.advance(target - done)
        done = target
        got.append(st.painter.snapshot(scale=scale)[0])
    return got


def zoom(
    rgba: bytes, width: int, box: tuple[int, int, int, int], factor: int
) -> tuple[bytes, int, int]:
    """A crop of an RGBA image, scaled up by pixel repetition on a checkerboard (so a
    transparent opening is seen as such)."""
    x0, y0, x1, y1 = box
    out = bytearray()
    for y in range(y0, y1):
        row = bytearray()
        for x in range(x0, x1):
            i = (y * width + x) * 4
            r, g, b, a = rgba[i : i + 4]
            back = (255, 0, 255) if ((x // 4 + y // 4) % 2 == 0) else (200, 200, 0)
            al = a / 255
            row += bytes(int(back[k] * (1 - al) + (r, g, b)[k] * al) for k in range(3)) + b"\xff"
        wide = b"".join(bytes(row[p : p + 4]) * factor for p in range(0, len(row), 4))
        out += wide * factor
    return bytes(out), (x1 - x0) * factor, (y1 - y0) * factor


def sheet(images: list[tuple[bytes, int, int]], path: Path) -> None:
    import tess_re.snapshot as snapshot

    height = max(h for _, _, h in images)
    total = sum(w + 4 for _, w, _ in images)
    out = bytearray(b"\x40\x40\x40\xff" * total * height)
    x = 0
    for rgba, w, h in images:
        for y in range(h):
            out[(y * total + x) * 4 : (y * total + x + w) * 4] = rgba[y * w * 4 : (y + 1) * w * 4]
        x += w + 4
    path.write_bytes(snapshot.png_bytes(bytes(out), total, height))


def differing(a: bytes, b: bytes, levels: int = 60) -> int:
    return sum(
        1 for i in range(0, len(a), 4) if max(abs(a[i + k] - b[i + k]) for k in range(4)) > levels
    )


def headless_frames(options: list[str], out: Path, scales: tuple[float, ...]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows: list[list[str]] = []
    reference: dict[tuple[float, str, bool], list[bytes]] = {}
    for scale in scales:
        for alignment in ("CENTER", "START"):
            for show in (True, False):
                for join in ["SMIL", *[o for o in options if o != "SMIL"]]:
                    frames = frames_of(join, alignment, scale, show)
                    key = (scale, alignment, show)
                    if join == "SMIL":
                        reference[key] = frames
                    if show:
                        width = round(400 * scale)
                        box = tuple(round(v * scale) for v in (100, 10, 300, 110))
                        sheet(
                            [zoom(f, width, box, 3 if scale == 1 else 2) for f in frames],  # type: ignore[arg-type]
                            out / f"join_{join}_{scale:g}x_{alignment.lower()}.png",
                        )
                    if join in options:
                        counts = [
                            differing(r, f) for r, f in zip(reference[key], frames, strict=True)
                        ]
                        rows.append(
                            [
                                join,
                                f"{scale:g}",
                                alignment.lower(),
                                "show" if show else "hide",
                                *[str(c) for c in counts],
                            ]
                        )
    table(
        "Pixels that differ from the SMIL build by more than 60 levels (of 120 000), at 0, 25, 50, "
        "75 and 100 % of a 300 ms slide (a shader's, a timer's or a path's animation starts on the "
        "tick after the request: its frames lag by about 1 ms, up to 0.4 px at the steepest part)",
        ["option", "scale", "body at", "slide", "0%", "25%", "50%", "75%", "100%"],
        [r for r in rows if r[0] != "SMIL"],
    )
    # side by side at 50 %: the left join of a centred body, 8x
    for scale in scales:
        width = round(400 * scale)
        box = tuple(round(v * scale) for v in (110, 16, 190, 70))
        images = []
        for join in options:
            f = frames_of(join, "CENTER", scale)[2]
            images.append(zoom(f, width, box, 8 if scale == 1 else 5))  # type: ignore[arg-type]
        sheet(images, out / f"edge_{scale:g}x.png")
    print(f"\nPNG sheets: {out}/join_<OPTION>_<scale>x_<alignment>.png (t = 0, 25, 50, 75, 100 %),")
    print(f"            {out}/edge_<scale>x.png (the options side by side at 50 %, 8x)")


def hit_table(options: list[str]) -> None:
    from tess_shell.surfaces.join import nodes_of
    from tests.test_frame import only

    probes = [
        ("body, inside", (80, 40)),
        ("below far edge, inside the box", (80, 80)),
        ("opening beside the body", (200, 150)),
        ("right join, notch", (191, 33)),
        ("right join, corner", (185, 25)),
        ("left band", (10, 150)),
    ]
    rows: list[list[str]] = []
    for join in options:
        for phase in ("rest", "50 %", "100 %"):
            manager = headless_scene(join, "START", visible=(phase == "rest"))
            st = only(manager)
            if phase != "rest":
                act(manager, "Show")
                st.painter.advance(1)
                st.painter.advance(150 if phase == "50 %" else 400)
            host = next(iter(st.hosts.values()))
            taken: list[str] = []
            watch = [("ring", n) for n in st.nodes] + [("body", host.clip)]
            watch += [("join", n) for n in nodes_of(host.join)]
            for name, node in watch:
                node.on("pointer_down", lambda e, name=name, taken=taken: taken.append(name))
            row = [join, phase]
            for _, (x, y) in probes:
                taken.clear()
                st.painter.simulate("pointer_down", x=x, y=y)
                row.append(taken[0] if taken else "falls through")
            rows.append(row)
    table(
        "What takes a click (START body 160 x 70 flush with the left band; join radius ~14)",
        ["option", "phase", *[name for name, _ in probes]],
        rows,
    )


def code_size(options: list[str]) -> None:
    rows = []
    for join in options:
        path, marker = CODE[join]
        lines = (REPO / path).read_text().splitlines()
        if marker:
            start = next(i for i, line in enumerate(lines) if line.startswith(marker))
            end = next(
                (i for i in range(start + 1, len(lines)) if lines[i] and lines[i][0] != " "),
                len(lines),
            )
            lines = lines[start:end]
        code = [line for line in lines if line.strip() and not line.strip().startswith("#")]
        rows.append([join, Path(path).name, str(len(lines)), str(len(code)), EASING[join]])
    table(
        "Code per option (lines of its own module; the shared interface and the Frame's calls are "
        "the same for all)",
        ["option", "file", "lines", "non-blank, no comment", "easing"],
        rows,
    )


# -- live: one process per option ----------------------------------------------------------------


def kb(name: str) -> int:
    try:
        with open(f"/proc/self/{name}") as f:
            for line in f:
                if line.startswith(("VmRSS:", "Pss:")):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


def memory() -> dict[str, float]:
    return {"rss_mib": kb("status") / 1024, "pss_mib": kb("smaps_rollup") / 1024}


def live_child(
    join: str, output: str | None, seconds: float, idle: float = 2.0, blend: str = "SRGB"
) -> None:
    """Open the Frame with ``join`` on the compositor and print one ``RESULT {...}`` line."""
    import tess_re

    from tess_shell.model.store import ValueStore
    from tess_shell.surfaces.manager import SurfaceManager
    from tests.test_frame import look, only
    from tests.test_frame_strips import shell_of

    app = tess_re.App()
    chosen = next((o for o in app.outputs() if output in (None, o.name)), None)
    if chosen is None:
        sys.exit(f"no output {output}")
    manager = SurfaceManager(
        app,  # type: ignore[arg-type]
        {},
        lambda key: key[-1],
        ValueStore(),
        look(),
        join_mode=join,
        blend_mode=blend,
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(FRAME, panel(visible=True)))
    manager.build()
    handle = app.thread_handle()
    st = only(manager)
    painter = st.painter
    result: dict[str, Any] = {
        "join": join,
        "blend": blend,
        "output": f"{chosen.name} {chosen.width}x{chosen.height}",
        "scale": chosen.scale_factor,
    }

    def vmem() -> float:
        m = painter.frame_stats().get("memory")
        return m["allocated_bytes"] / 2**20 if m else float("nan")

    def settle() -> None:
        result["idle_before"] = {**memory(), "vmem_mib": vmem()}
        painter.frame_stats(reset=True)
        state = {"end": time.monotonic() + seconds}

        def toggle() -> None:
            if time.monotonic() > state["end"]:
                painter.after(MS + 100, stopped)
                return
            act(manager, "Toggle")
            painter.after(MS + 40, toggle)

        toggle()

    def stopped() -> None:
        recent = painter.frame_stats()["recent"]
        result["frames"] = recent["count"]
        result["fps"] = recent["fps"]
        for key in ("total_ms", "cpu_ms"):
            result[key] = {k: recent[key][k] for k in ("mean", "p95", "max")}
        result["stages"] = recent["stage_ms"]
        result["redraws"] = recent.get("redraws")
        if manager.frames.states and any(h.anim for h in only(manager).hosts.values()):
            act(manager, "Show")
        painter.after(MS + 600, still)

    def still() -> None:
        result["frames_at_rest"] = painter.frame_stats()["frames"]
        painter.after(int(idle * 1000), finish)

    def finish() -> None:
        result["idle_frames"] = painter.frame_stats()["frames"] - result["frames_at_rest"]
        result["idle_after"] = {**memory(), "vmem_mib": vmem()}
        print("RESULT " + json.dumps(result), flush=True)
        handle.stop()

    painter.after(1500, settle)
    app.run(keep_alive=True)


def live_run(
    options: list[str],
    output: str | None,
    seconds: float,
    env: dict[str, str],
    idle: float = 2.0,
    blend: str = "SRGB",
) -> list[dict[str, Any]]:
    results = []
    for join in options:
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            f"--child={join}",
            f"--seconds={seconds}",
            f"--idle={idle}",
            f"--blend={blend}",
        ]
        if output:
            cmd.append(f"--output={output}")
        done = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=REPO, timeout=120)
        line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")), None)
        if line is None:
            print(
                f"{join}: no result (exit {done.returncode})\n{done.stderr[-600:]}", file=sys.stderr
            )
            continue
        results.append(json.loads(line[7:]))
    return results


def live_table(results: list[dict[str, Any]]) -> None:
    rows = []
    for r in results:
        before, after = r["idle_before"], r["idle_after"]
        rows.append(
            [
                r["join"] + (f" {r['blend']}" if r.get("blend", "SRGB") != "SRGB" else ""),
                f"{r['scale']:g}",
                str(r["frames"]),
                f"{r['fps']:.0f}",
                f"{r['total_ms']['mean']:.1f} / {r['total_ms']['max']:.1f}",
                f"{r['cpu_ms']['mean']:.2f} / {r['cpu_ms']['max']:.2f}",
                str(r["idle_frames"]),
                f"{before['rss_mib']:.0f} -> {after['rss_mib']:.0f}",
                f"{before['pss_mib']:.0f} -> {after['pss_mib']:.0f}",
                f"{before['vmem_mib']:.1f} -> {after['vmem_mib']:.1f}",
            ]
        )
    where = results[0]["output"] if results else "no output"
    table(
        f"Cost on {where} while a {MS} ms slide loops (frame_stats()['recent'], last 240 frames), "
        "then idle",
        [
            "option",
            "scale",
            "frames",
            "fps",
            "total_ms mean / max",
            "cpu_ms mean / max",
            "idle frames 2 s",
            "RSS MiB idle->after",
            "Pss MiB",
            "video MiB",
        ],
        rows,
    )
    print("\nstages (ms, mean per frame; 'present' is the wait for the display) and redraw kinds:")
    for r in results:
        stages = {
            k: round(v, 2) for k, v in r["stages"].items() if k in ("layout", "draw", "present")
        }
        label = r["join"] + (f" {r['blend']}" if r.get("blend", "SRGB") != "SRGB" else "")
        print(f"  {label:17} {stages}  redraws {r.get('redraws')}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--join", default="all", help="one option or all")
    ap.add_argument("--live", action="store_true", help="measure the cost on a compositor")
    ap.add_argument("--sway", action="store_true", help="with --live: a private headless sway")
    ap.add_argument(
        "--output", default=None, help="with --live: the output (default: tre's choice)"
    )
    ap.add_argument("--seconds", type=float, default=3.0, help="with --live: how long to loop")
    ap.add_argument("--scales", default="1,1.5", help="display scales for the PNGs and --sway")
    ap.add_argument("--out", default="/tmp/join-compare", help="where the PNG sheets go")
    ap.add_argument("--no-headless", action="store_true", help="skip frames, hits and size")
    ap.add_argument("--idle", type=float, default=2.0, help="with --live: seconds of idle to count")
    ap.add_argument(
        "--blend",
        default="SRGB",
        choices=["SRGB", "LINEAR"],
        help="Debug { Frame_Blend } of every run",
    )
    ap.add_argument("--child", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()
    global BLEND
    BLEND = args.blend
    if args.child:
        live_child(args.child, args.output, args.seconds, args.idle, args.blend)
        return
    options: list[str] = list(JOINS) if args.join == "all" else [args.join.upper()]
    for o in options:
        if o not in JOINS:
            sys.exit(f"unknown option {o}; one of {', '.join(JOINS)}")
    scales = tuple(float(s) for s in args.scales.split(","))
    print(
        f"tesserae-engine {version('tesserae-engine')}, options: {', '.join(options)}, "
        f"Frame_Blend: {args.blend}"
    )
    if not args.no_headless:
        # the headless renders never open a window (only App.run does): nothing is shown
        headless_frames(options, Path(args.out), scales)
        hit_table(options)
        code_size(options)
    if not args.live:
        return
    if not args.sway:
        live_table(
            live_run(options, args.output, args.seconds, dict(os.environ), args.idle, args.blend)
        )
        return
    from tests.sway import PrivateSway

    sway = PrivateSway().start()
    try:
        sway.msg("output", "*", "resolution", "1920x1080")
        for scale in scales:
            sway.msg("output", "*", "scale", f"{scale:g}")
            time.sleep(0.5)
            print(f"\n== private sway, output scale {scale:g}")
            live_table(
                live_run(
                    options, sway.output_names()[0], args.seconds, sway.env, args.idle, args.blend
                )
            )
    finally:
        sway.stop()


if __name__ == "__main__":
    main()
