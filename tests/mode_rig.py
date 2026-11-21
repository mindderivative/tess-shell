"""The rig of the shortcut-mode tests: a Frame with two peeks (a peeking strip and a peeking
melded Panel), two Panels and a Bar, real tre windows over a stub ``App`` and the real surface
manager. Not collected by pytest."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import tess_dl
from loguru import logger

from tess_shell.model.store import ValueStore
from tess_shell.schema.model import ShellDef
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.manager import SurfaceManager
from tests.shell_samples import HEADER
from tests.test_frame import StubApp, look, only
from tests.test_frame_strips import module

FRAME = (
    'Frame { Name: F, Thickness: 20, %s Inner_Border { Width: 2, Color: "#00ff00" }, '
    'Style { Background: "#0000ff" }, Edges { Top { Thickness: 30, Name: TopStrip, '
    "Peek { Size: 8 }, Children { Rectangle { Name: S1, Width: 20, Height: 20, "
    "Focusable: true } } } } }"
)
TAB = (
    "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: LEFT, Alignment: START, Length: 80, "
    "Depth: 40, Peek { Size: 12 }, %s Animation { Type: SLIDE, Duration: 300 }, "
    "Children { Rectangle { Name: Dot, Width: 20, Height: 20 } } }"
)
BAR = (
    "Bar { Name: Top_Bar, Edge: BOTTOM, Width: EXPAND, Height: 24, %s Children { "
    "Rectangle { Name: Btn, Width: 20, Height: 20, Focusable: true } } }"
)
DOCK = (
    "Panel { Name: Dock, Anchor: [BOTTOM, LEFT], Width: 100, Height: 50, Keyboard: ON_DEMAND, "
    "%s Children { Rectangle { Name: B1, Width: 20, Height: 20, Focusable: true } "
    "Rectangle { Name: B2, Width: 20, Height: 20, Focusable: true } } }"
)
LAUNCHER = (
    "Panel { Name: Launcher, Anchor: [TOP, RIGHT], Width: 100, Height: 50, Visible: false, "
    "Keyboard: ON_DEMAND, %s Children { Rectangle { Name: L1, Width: 20, "
    "Height: 20, Focusable: true } } }"
)


def text(frame: str = "", tab: str = "", bar: str = "", dock: str = "", launcher: str = "") -> str:
    """The shell: the extra keys of each surface (``Shortcut_Mode: true,``...) go in the slots."""
    parts = (FRAME % frame, TAB % tab, BAR % bar, DOCK % dock, LAUNCHER % launcher)
    order = "Focus_Order: [F, Dock, Top_Bar, F.top, Launcher]"
    return (
        f"Shell {{ {order} Monitor {{ Name: Main, Index: 0, Children {{ {' '.join(parts)} }} }} }}"
    )


def shell_of(body: str) -> ShellDef:
    result = tess_dl.parse(HEADER + body, path="Shells/Main_Shell.tdl")
    assert result.document is not None and not result.errors
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", lambda _: "", module())
    assert shell is not None, findings
    return shell


@dataclass
class Rig:
    manager: SurfaceManager
    app: StubApp
    lines: list[str]
    _sink: int = 0

    @property
    def mode(self) -> Any:
        return self.manager.mode

    @property
    def state(self) -> tuple[str | None, str | None]:
        s = self.mode.machine.state
        return s.mode, s.focus

    @property
    def frame(self) -> Any:
        return only(self.manager)

    def surface(self, name: str) -> Any:
        return next(s for s in self.manager.surfaces if s.name == name)

    def keyboard(self, name: str) -> str:
        """The keyboard word of the window a surface lives in."""
        if name == "F":
            return str(self.frame.painter.get("keyboard"))
        return str(self.surface(name).window.get("keyboard"))

    def settle(self, ms: int = 700) -> None:
        self.frame.painter.advance(1)
        self.frame.painter.advance(ms)

    def out(self, name: str) -> bool:
        """The peek ``name`` is out and at rest."""
        st = self.frame
        host = next(h for h in st.hosts.values() if h.plan.name == name)
        return host.anim is None and name not in (st.hidden_melds | st.tab_melds)

    def at_rest(self, name: str) -> bool:
        st = self.frame
        host = next(h for h in st.hosts.values() if h.plan.name == name)
        return host.anim is None and name in (st.hidden_melds | st.tab_melds)

    def ring(self, name: str) -> list[str]:
        """The blocks of the surface ``name`` that have keyboard focus."""
        view = self.surface(name).view
        return [k for k, n in view.nodes.items() if n.get("focused")]

    def key(self, name: str, key: str, **mods: bool) -> None:
        """A key event on the window of the surface ``name`` (tre's own ``simulate``)."""
        window = self.frame.painter if name == "F" else self.surface(name).window
        window.simulate("key_down", key=key, **mods)

    def reload(self, body: str) -> None:
        checked = self.manager.check(shell_of(body), module())
        assert checked is not None
        self.manager.apply(checked[0], module(), checked[1])

    def log(self) -> str:
        return "\n".join(self.lines)

    def warnings(self) -> list[str]:
        return [x for x in self.lines if "| WARNING " in x or "| ERROR " in x]


def start(body: str | None = None, mode_keyboard: str = "EXCLUSIVE") -> Rig:
    app = StubApp()
    manager = SurfaceManager(
        app,  # type: ignore[arg-type]
        module(),
        lambda key: key[-1],
        ValueStore(),
        look(),
        blend_mode="SRGB",
        mode_keyboard=mode_keyboard,
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    lines: list[str] = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    manager.plan(shell_of(body or text()))
    manager.build()
    painter = only(manager).painter
    painter.resize(*app.size)
    painter.snapshot()  # lay the peeks out: a slide needs where it goes
    return Rig(manager, app, lines, sink)


Make = Callable[..., Rig]


def rigs() -> Iterator[Make]:
    """The body of the ``rig`` fixture: a maker of rigs that removes their log sinks at the end."""
    made: list[Rig] = []

    def make(body: str | None = None, mode_keyboard: str = "EXCLUSIVE") -> Rig:
        r = start(body, mode_keyboard)
        made.append(r)
        return r

    yield make
    for r in made:
        logger.remove(r._sink)
