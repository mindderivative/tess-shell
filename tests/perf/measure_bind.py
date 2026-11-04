"""Bind time of the M1 example and of a 3,100-node tree (Performance Budgets).

Not collected by pytest. Run from the repo root: ``uv run python tests/perf/measure_bind.py``.
Writes ``tests/perf/bind-results.md``. Reported, not enforced.
"""

from __future__ import annotations

import datetime
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

from tess_shell.binder.build import build  # noqa: E402
from tess_shell.binder.model import Length, Node, Number, Text  # noqa: E402
from tess_shell.schema.shell import read_shell  # noqa: E402


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
        read_shell(parsed.document, "Shells/Main_Shell.tdl", lambda _: SVG)  # type: ignore[arg-type]

    results = {
        "Typing the example file (schema)": timed(read, 200),
        "Binding the example (5 nodes)": timed(lambda: bind(example), 200),
        f"Binding a typed tree of {nodes:,} nodes": timed(lambda: bind(big), 20),
    }
    uname = platform.uname()
    rows = "\n".join(
        f"| {name} | {statistics.median(v):.3f} | {min(v):.3f} | {max(v):.3f} | {len(v)} |"
        for name, v in results.items()
    )
    text = f"""# Bind time

Reported, not enforced. Produced by `tests/perf/measure_bind.py`.

| | |
|---|---|
| Date | {datetime.datetime.now().astimezone().isoformat(timespec="seconds")} |
| Machine | {uname.system} {uname.release} {uname.machine} |
| Python | {platform.python_version()} |

Milliseconds per call, on a headless `tess_re` window (build, attach, then dispose).

| What | Median | Best | Worst | Runs |
|---|---|---|---|---|
{rows}

Binder Design quotes tre's own figure for 3,100 nodes: 5.3 ms through `Window.build` (4.9 ms with
per-node calls); that excludes this binder's table lookups and conversions.
"""
    (HERE / "bind-results.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
