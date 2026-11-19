"""Bind time of the M1 example and of a 3,100-node tree (Performance Budgets).

Not collected by pytest. Run from the repo root: ``uv run python tests/perf/measure_bind.py``.
Writes ``tests/perf/bind-results.md``. Reported, not enforced.
"""

from __future__ import annotations

import datetime
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import tess_dl
from tess_re import Window

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from tests.shell_samples import BODY, HEADER, SVG  # noqa: E402

from tess_shell.binder import build as binder  # noqa: E402
from tess_shell.binder.build import build  # noqa: E402
from tess_shell.binder.model import Length, Node, Number, Text  # noqa: E402
from tess_shell.schema.shell import read_shell  # noqa: E402

# ruff: noqa: E501
# The bind of the 3,101-node tree before and after the bind cost work (tess-shell branch
# ``bind-cost``, 2026-11-19): 100 binds per process, base and new in alternating processes, taken
# while other builders shared the machine (load average 1 to 3 on 24 cores): not quiet-machine
# figures. Median of ``build`` + ``dispose``; ``Worst`` shows the garbage collector's full
# collections, which the many small objects of the old binder made frequent.
HISTORY = """## History (3,101-node tree, ms)

Taken while other builders shared the machine (load average 1 to 3 on 24 cores); base and new in
alternating processes of 100 binds.

| When | Median | Best | Worst | Note |
|---|---|---|---|---|
| 2026-11-04 (M1) | 12.6 | 12.3 | 13.6 | before wires, controls, states, Tab order and focus keys |
| 2026-11-19, M7c reading B18 | 34.4 | 32.1 | 112 | the shell at the start of the bind cost work |
| 2026-11-19, same code, this run | 34.3 to 35.3 | 30.8 to 31.5 | 117 to 123 | 3 processes of 100 binds |
| 2026-11-19, after the bind cost work | 16.1 to 16.8 | 14.8 to 15.0 | 24 to 27 | 3 processes of 100 binds |

Where the 34 ms went before, by step of `build` (medians of 60 binds; the sum is one bind minus
the dispose), and after:

| Step | Before | After | What changed |
|---|---|---|---|
| plan (typed tree to spec) | 11.6 | 5.2 | no path strings or position index, no copy of the child props, nothing done for a node with no state style, no `Transition` or no key that needs checking; `isinstance` with a tuple, not `A \\| B`; one call fewer per key |
| tre `Window.build` | 5.5 | 5.2 | the floor of the engine call |
| entries and attach | 5.9 | 2.4 | the entry takes the spec's props; a leaf shares one empty tuple; no per-node state or motion work |
| wires (`_wire`) | 4.8 | 1.1 | a block that listens for nothing gets no `Wire` |
| controls | 1.5 | 0.3 | one list of entries for all the index passes; the control keys are tested with one set check |
| `_sync` | 4.1 | 0.05 | skips blocks with no wire |
| marquees, Tab order | 0.6 | 0.5 | |
| dispose (tre `destroy`) | 1.1 | 1.0 | the floor |
"""


def big_tree() -> list[Node]:
    """One FlexBox of 31 rows; each row a FlexBox of 99 Text nodes: 1 + 31 + 3,069 = 3,101."""
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


def count(nodes: list[Node]) -> int:
    return sum(1 + count([c for c in n.children if isinstance(c, Node)]) for n in nodes)


def timed(fn: object, repeats: int) -> list[float]:
    out = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()  # type: ignore[operator]
        out.append((time.perf_counter() - start) * 1000)
    return out


def phases(
    tree: list[Node], repeats: int = 60
) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    """Milliseconds each step of ``build`` takes for one root of ``tree`` (the steps, as
    ``binder.build.build`` takes them: plan, tre's ``Window.build``, entries and attach, the
    view's index), and the dispose."""
    plan: list[float] = []
    tre: list[float] = []
    entries: list[float] = []
    index: list[float] = []
    dispose: list[float] = []
    for _ in range(repeats):
        window = Window(1000, 400)
        t0 = time.perf_counter()
        spec = binder._plan(tree[0], "spec", {}, [], None, {})
        assert isinstance(tree[0], Node) and spec is not None
        t1 = time.perf_counter()
        root, _ = window.build(spec)
        t2 = time.perf_counter()
        view = binder.View(window, [], {})
        view.entries.append(binder.make_entry(tree[0], spec, root))
        window.root.add_child(root)
        t3 = time.perf_counter()
        view.reindex()
        t4 = time.perf_counter()
        view.dispose()
        t5 = time.perf_counter()
        plan.append((t1 - t0) * 1000)
        tre.append((t2 - t1) * 1000)
        entries.append((t3 - t2) * 1000)
        index.append((t4 - t3) * 1000)
        dispose.append((t5 - t4) * 1000)
    return plan, tre, entries, index, dispose


def main() -> int:
    parsed = tess_dl.parse(HEADER + BODY, path="Shells/Main_Shell.tdl")
    assert parsed.document is not None
    shell, _ = read_shell(parsed.document, "Shells/Main_Shell.tdl", lambda _: SVG)
    assert shell is not None
    example = list(shell.monitors[0].surfaces[0].children)
    big = big_tree()
    nodes = count(big)

    def bind(tree: list[Node]) -> None:
        window = Window(1000, 400)
        view = build(tree, window)
        view.dispose()

    def read() -> None:
        read_shell(parsed.document, "Shells/Main_Shell.tdl", lambda _: SVG)

    load = os.getloadavg()[0]
    plan, tre_build, entries, index, dispose = phases(big)
    results = {
        "Typing the example file (schema)": timed(read, 200),
        "Binding the example (5 nodes)": timed(lambda: bind(example), 200),
        f"Binding a typed tree of {nodes:,} nodes": timed(lambda: bind(big), 60),
        "  step: planning the spec": plan,
        "  step: tre `Window.build`": tre_build,
        "  step: entries and attach": entries,
        "  step: view index (wires, controls, Tab order)": index,
        "  step: dispose": dispose,
    }
    uname = platform.uname()
    rows = "\n".join(
        f"| {name} | {statistics.median(v):.3f} | {min(v):.3f} | {max(v):.3f} | {len(v)} |"
        for name, v in results.items()
    )
    text = f"""# Bind time

Reported by `tests/perf/measure_bind.py`; the bound the test suite enforces is in
`tests/test_budget_bind.py` (three times the 15 ms target, so a loaded machine does not flake).

| | |
|---|---|
| Date | {datetime.datetime.now().astimezone().isoformat(timespec="seconds")} |
| Machine | {uname.system} {uname.release} {uname.machine} |
| Python | {platform.python_version()} |
| Load average (1 min) before the run | {load:.2f} |

Milliseconds per call, on a headless `tess_re` window (build, attach, then dispose). The rows
under the big tree split one bind into the steps of `binder.build.build`: planning (typed tree to
the spec), tre's `Window.build` of that spec, the entries and the attach, the view's index (wires,
controls, Tab order), and the dispose. They are separate runs of the same steps, so they add up to
the bind row only within the noise.

| What | Median | Best | Worst | Runs |
|---|---|---|---|---|
{rows}

{HISTORY}"""
    (HERE / "bind-results.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
