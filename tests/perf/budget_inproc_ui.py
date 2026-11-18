"""In-process budget measures of the surfaces and the files (B11, B16, B18, B19): motion tokens,
the Popup on headless tre windows, the bind of a 3,101-node tree and the config load."""

from __future__ import annotations

import gc
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import tess_dl
from loguru import logger
from tess_re import Node as TreNode
from tess_re import Window
from tests.perf.budget_report import Reading
from tests.shell_samples import BODY, HEADER, SVG, write_example

from tess_shell.appearance import Appearance
from tess_shell.binder.build import build
from tess_shell.binder.model import Length, Node, Number, Text
from tess_shell.config.discovery import shipped_dir
from tess_shell.config.settings import load_settings
from tess_shell.scanner import scan
from tess_shell.schema.look import effective_tokens, read_theme
from tess_shell.schema.shell import read_shell

FRAME_MS = 1000 / 60
DEFAULT_THEME = shipped_dir() / "Themes" / "Default_Theme.tdl"

# -- B11 ----------------------------------------------------------------------------------------

VAULT_DURATIONS = {"short": 100.0, "medium": 200.0, "long": 400.0}


def motion_durations() -> dict[str, float]:
    """``motion.duration.*`` of the shipped Default theme, in milliseconds."""
    result = tess_dl.parse(DEFAULT_THEME.read_text(), path=str(DEFAULT_THEME))
    assert result.document is not None
    theme, findings = read_theme(result.document, str(DEFAULT_THEME))
    assert theme is not None, findings
    tokens = effective_tokens(theme, Appearance())
    return {name: float(tokens[f"motion.duration.{name}"].value.value) for name in VAULT_DURATIONS}  # type: ignore[union-attr]


def measure_b11(quick: bool) -> list[Reading]:
    got = motion_durations()
    out: list[Reading] = []
    for name, limit in VAULT_DURATIONS.items():
        what = f"Duration.{name.title()} of the shipped Default theme"
        out.append(Reading("B11", what + " (at most)", [got[name]], "ms", limit, "max"))
        out.append(
            Reading("B11", what + " (at least)", [got[name]], "ms", limit, "max", at_least=True)
        )
    return out


# -- B16 ----------------------------------------------------------------------------------------


def open_descriptors() -> int:
    return len(os.listdir("/proc/self/fd"))


def open_threads() -> int:
    return len(os.listdir("/proc/self/task"))


def count_objects(*names: str) -> dict[str, int]:
    gc.collect()
    found = dict.fromkeys(names, 0)
    for obj in gc.get_objects():
        name = type(obj).__name__
        if name in found:
            found[name] += 1
    return found


def popup_rig() -> Any:
    from tests.test_popup import CARD, rig

    logger.remove()
    return next(rig(f"Popup {{ Name: Menu, Gap: 4, Alignment: END, Children {{ {CARD} }} }}"))


def open_costs(count: int) -> tuple[list[float], list[float]]:
    """Loop-thread milliseconds of ``popups.call`` (the open: measure, build, window) and of the
    call that closes it, ``count`` times each, on the headless Bar of ``tests/test_popup.py``."""
    r = popup_rig()
    opens: list[float] = []
    closes: list[float] = []
    for _ in range(count):
        started = time.perf_counter()
        op = r.call()
        opens.append((time.perf_counter() - started) * 1000)
        assert op is not None
        op.window.advance(16)
        started = time.perf_counter()
        r.call()
        closes.append((time.perf_counter() - started) * 1000)
        r.advance(16)
    return opens, closes


def measure_b16(quick: bool) -> list[Reading]:
    count = 30 if quick else 200
    opens, closes = open_costs(count)
    where = "loop-thread time of popups.call on a headless tre PopupWindow"
    note = (
        "no compositor: the time to a configured, drawn popup needs a live sway and the whole "
        "shell process; this is the loop-thread share of the click to the open"
    )
    return [
        Reading("B16", f"open of a Popup, {where}", opens, "ms", 2 * FRAME_MS, "median",
                note=note + "; limit = two frames (33.3 ms), the vault says one or two"),
        Reading("B16", f"close of a Popup, {where}", closes, "ms"),
        Reading(
            "B16",
            "an open Popup draws no frames while nothing changes",
            [],
            "",
            reason=(
                "headless windows draw no frames: Window.frame_stats records only after "
                "App.run() opens the window, which needs a compositor; the in-process rig has "
                "none. Not measured (no invented counter)"
            ),
        ),
    ]  # fmt: skip


def popup_residue(cycles: int) -> dict[str, int]:
    """What ``cycles`` open/close turns leave behind (differences after minus before)."""
    r = popup_rig()

    def cycle() -> None:
        op = r.call()
        op.window.advance(16)
        del op
        r.call()
        r.advance(16)

    for _ in range(5):  # warm up: imports, caches, first measure
        cycle()
    gc.collect()
    before = (open_threads(), open_descriptors(), len(r.bar.view.nodes), sys.getallocatedblocks())
    objects = count_objects("OpenPopup", "PopupWindow")
    for _ in range(cycles):
        cycle()
    gc.collect()
    after = (open_threads(), open_descriptors(), len(r.bar.view.nodes), sys.getallocatedblocks())
    left = count_objects("OpenPopup", "PopupWindow")
    return {
        "threads": after[0] - before[0],
        "fds": after[1] - before[1],
        "bar_nodes": after[2] - before[2],
        "blocks_per_cycle": (after[3] - before[3]) // cycles,
        "open_popups": left["OpenPopup"] - objects["OpenPopup"],
        "popup_windows": left["PopupWindow"] - objects["PopupWindow"],
        "live_trees": len(r.popups.lives()),
    }


def measure_b16_closed(quick: bool) -> list[Reading]:
    cycles = 20 if quick else 200
    res = popup_residue(cycles)
    note = f"after {cycles} open/close cycles, headless"
    out = []
    for key in ("threads", "fds", "bar_nodes", "open_popups", "popup_windows", "live_trees"):
        out.append(
            Reading("B16", f"closed Popup holds nothing: growth of {key}", [float(res[key])],
                    "count", 0.0, "max", note=note)
        )  # fmt: skip
    out.append(
        Reading("B16", "closed Popup holds nothing: Python blocks left per cycle",
                [float(res["blocks_per_cycle"])], "blocks",
                note="tre holds handler wrappers of a closed headless window (about 20 per open)")
    )  # fmt: skip
    return out


# -- B18 ----------------------------------------------------------------------------------------


def big_tree() -> list[Node]:
    """One FlexBox of 31 rows, each a FlexBox of 99 Text nodes: 1 + 31 + 3,069 = 3,101 nodes."""
    rows = tuple(
        Node(
            "FlexBox",
            children=tuple(
                Node("Text", props={"Text": Text(f"{r}.{c}")}, style={"Font_Size": Number(12)})
                for c in range(99)
            ),
        )
        for r in range(31)
    )
    return [Node("FlexBox", props={"Width": Length(1000)}, children=rows)]


def count_nodes(nodes: list[Node]) -> int:
    return sum(1 + count_nodes([c for c in n.children if isinstance(c, Node)]) for n in nodes)


def example_tree() -> list[Node]:
    parsed = tess_dl.parse(HEADER + BODY, path="Shells/Main_Shell.tdl")
    assert parsed.document is not None
    shell, _ = read_shell(parsed.document, "Shells/Main_Shell.tdl", lambda _: SVG)
    assert shell is not None
    return list(shell.monitors[0].surfaces[0].children)  # type: ignore[arg-type,union-attr]


def _wrap(value: Any, calls: dict[str, int]) -> Any:
    """What a counted call returns: nodes (alone, in a list or a tuple, or as dict values) are
    counted too."""
    if isinstance(value, TreNode):
        return CountingNode(value, calls)
    if isinstance(value, list | tuple):
        return type(value)(_wrap(v, calls) for v in value)
    if isinstance(value, dict):
        return {k: _wrap(v, calls) for k, v in value.items()}
    return value


def _unwrap(value: Any) -> Any:
    if isinstance(value, CountingNode):
        return value._node
    if isinstance(value, list | tuple):
        return type(value)(_unwrap(v) for v in value)
    return value


class CountingNode:
    """A tre ``Node`` that counts the calls the binder makes on it (``calls`` is shared)."""

    def __init__(self, node: Any, calls: dict[str, int]) -> None:
        self._node = node
        self._calls = calls

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._node, name)
        if not callable(target):
            return target
        calls = self._calls

        def counted(*args: Any, **kwargs: Any) -> Any:
            calls[f"Node.{name}"] = calls.get(f"Node.{name}", 0) + 1
            return _wrap(target(*_unwrap(args), **kwargs), calls)

        return counted


class CountingWindow:
    """A tre ``Window`` that counts the calls the binder makes on it and on the nodes it hands
    out (``root``, what ``build`` returns, children)."""

    def __init__(self, window: Any) -> None:
        self._window = window
        self.calls: dict[str, int] = {}

    @property
    def root(self) -> CountingNode:
        return CountingNode(self._window.root, self.calls)

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._window, name)
        if not callable(target):
            return target

        def counted(*args: Any, **kwargs: Any) -> Any:
            self.calls[f"Window.{name}"] = self.calls.get(f"Window.{name}", 0) + 1
            return _wrap(target(*_unwrap(args), **kwargs), self.calls)

        return counted


def tre_calls(tree: list[Node]) -> dict[str, int]:
    """The tre calls ``build`` makes for ``tree`` (name -> count)."""
    window = CountingWindow(Window(1000, 400))
    view = build(tree, window)  # type: ignore[arg-type]
    calls = dict(window.calls)
    view.dispose()
    return calls


def timed(fn: Callable[[], object], repeats: int) -> list[float]:
    out = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        out.append((time.perf_counter() - started) * 1000)
    return out


def tre_call_costs(repeats: int) -> list[Reading]:
    window = Window(1000, 400)

    # create, timed alone: destroy afterwards, outside the timing
    def create_cost(kind: str, **props: Any) -> list[float]:
        out: list[float] = []
        for _ in range(repeats):
            kept: list[Any] = []
            started = time.perf_counter()
            for _i in range(500):
                kept.append(window.create(kind, **props))
            out.append((time.perf_counter() - started) * 1e6 / 500)
            for node in kept:
                node.destroy()
        return out

    def set_cost() -> list[float]:
        node = window.create("box", width=10)
        out: list[float] = []
        for _ in range(repeats):
            started = time.perf_counter()
            for i in range(500):
                node.set(width=10 + i % 7)
            out.append((time.perf_counter() - started) * 1e6 / 500)
        node.destroy()
        return out

    def add_child_cost() -> list[float]:
        out: list[float] = []
        for _ in range(repeats):
            parent = window.create("box")
            kids = [window.create("box") for _ in range(500)]
            started = time.perf_counter()
            for kid in kids:
                parent.add_child(kid)
            out.append((time.perf_counter() - started) * 1e6 / 500)
            parent.destroy()
        return out

    note = "tess_re called directly on a headless Window, per call, batches of 500"
    return [
        Reading("B18", "tre Window.create('box') per call", create_cost("box"), "us", note=note),
        Reading("B18", "tre Window.create('text') per call", create_cost("text", text="x"), "us",
                note=note),
        Reading("B18", "tre Node.set(width=...) per call", set_cost(), "us", note=note),
        Reading("B18", "tre Node.add_child per call", add_child_cost(), "us", note=note),
    ]  # fmt: skip


def measure_b18(quick: bool) -> list[Reading]:
    runs, small = (5, 20) if quick else (60, 200)
    big = big_tree()
    nodes = count_nodes(big)
    example = example_tree()

    def bind(tree: list[Node]) -> None:
        window = Window(1000, 400)
        build(tree, window).dispose()

    big_ms = timed(lambda: bind(big), runs)
    example_ms = timed(lambda: bind(example), small)
    calls_big = tre_calls(big)
    calls_example = tre_calls(example)
    return [
        Reading("B18", f"bind of a typed tree of {nodes:,} nodes (build + attach + dispose)",
                big_ms, "ms", 15.0, "median",
                note="as tests/perf/measure_bind.py, headless window"),
        Reading("B18", "bind of the M1 example (5 nodes)", example_ms, "ms"),
        Reading("B18", f"tre calls the binder makes for the {nodes:,}-node tree",
                [float(sum(calls_big.values()))], "calls",
                note=", ".join(f"{k} x{v}" for k, v in sorted(calls_big.items()))),
        Reading("B18", "tre calls the binder makes for the M1 example",
                [float(sum(calls_example.values()))], "calls",
                note=", ".join(f"{k} x{v}" for k, v in sorted(calls_example.items()))),
        *tre_call_costs(5 if quick else 30),
    ]  # fmt: skip


# -- B19 ----------------------------------------------------------------------------------------


def generated_shell(entries: int) -> str:
    """A shell file of about ``entries`` entries: one Bar with a FlexBox of Texts, Rectangles,
    nested FlexBoxes, and uses of the shipped Clock, Battery and Label."""
    kinds = [
        'Text {{ Text: "t{i}", Font_Size: 14, Foreground: "#ffffff" }}',
        'Rectangle {{ Width: 12, Height: 12, Fill: "#89b4fa", Corner_Radius: 6 }}',
        'FlexBox {{ Flex: HORIZONTAL, Spacing: 4, Children {{ Text {{ Text: "x{i}" }} }} }}',
        "Clock {{ Name: Clock_{i} }}",
        "Battery {{ Name: Battery_{i} }}",
        'Label {{ Name: Label_{i}, Text: "l{i}" }}',
    ]
    kids = "\n".join(kinds[i % len(kinds)].format(i=i) for i in range(entries))
    return (
        "Shell { Monitor { Name: Main, Index: 0, Children {\n"
        "  Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, Children {\n"
        "    FlexBox { Width: EXPAND, Flex: HORIZONTAL, Children {\n"
        f"{kids}\n"
        "    } }\n  } }\n} } }\n"
    )


def measure_b19(quick: bool) -> list[Reading]:
    runs = 5 if quick else 40
    body = generated_shell(300)
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp)
        path = write_example(config, body)
        text = path.read_text()
        settings, _ = load_settings(config)
        assert settings is not None
        first = scan(settings, config)
        errors = [f for f in first.findings if f.severity == "error"]
        assert not errors, errors
        defs = {n: mf.definition for n, mf in first.modules.items()}

        def read() -> None:
            parsed = tess_dl.parse(text, path="Shells/Main_Shell.tdl")
            assert parsed.document is not None
            shell, findings = read_shell(
                parsed.document,
                "Shells/Main_Shell.tdl",
                lambda _: SVG,
                defs,
                None,
                first.icons,  # type: ignore[arg-type]
            )
            assert shell is not None, findings

        parse_ms = timed(lambda: tess_dl.parse(text, path="Shells/Main_Shell.tdl"), runs)
        read_ms = timed(read, runs)
        scan_ms = timed(lambda: scan(settings, config), runs)
    entries = body.count("{")
    note = f"generated shell of about {entries} entries (blocks), shipped modules"
    return [
        Reading("B19", "tess_dl.parse of the shell file", parse_ms, "ms", note=note),
        Reading("B19", "parse + read_shell (typed, modules resolved)", read_ms, "ms", note=note),
        Reading("B19", "scan of the whole config folder (every shipped module and the shell)",
                scan_ms, "ms", note=note + "; the vault states no number: recorded"),
    ]  # fmt: skip
