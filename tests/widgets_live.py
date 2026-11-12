"""A running manager with the shipped standard modules (Label, TextBox, ProgressBar, Badge, Marquee
text, Icon, Image, Expander and the text fields), the Default stylesheet and a ``Driver`` module
whose layout is given by the test and whose Python sends values: the display widgets tests drive a
real tre window headless (``advance``, ``simulate``, ``snapshot``), no compositor. Not collected by
pytest."""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tess_dl
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.files.icons import IconSets
from tess_shell.model.icons import RuntimeIcons
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.modules.host import ModuleHost
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.look import read_stylesheet, read_theme
from tess_shell.schema.model import ModuleDef, StyleDef
from tess_shell.schema.shell import read_module, read_module_params, read_shell, read_style
from tess_shell.services.api import DBusPort
from tess_shell.surfaces.manager import SurfaceManager
from tests.shell_samples import HEADER
from tests.test_panel import StubApp
from tests.test_popup import SHELL

SHIPPED = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped"
STANDARD = (
    "Label",
    "TextBox",
    "ProgressBar",
    "Badge",
    "Marquee_Text",
    "Icon",
    "Image",
    "Expander",
    "Button",
    "Toggle",
    "Checkbox",
    "Slider",
    "List",
    "Menu",
    "MenuItem",
    "TextInput",
    "TextEditor",
    "Battery",
    "Workspaces",
)
THEME = (SHIPPED / "Themes" / "Default_Theme.tdl").read_text()
DEFAULT_SHEET = (SHIPPED / "Stylesheets" / "Default_Stylesheet.tdl").read_text()

DRIVER_PY = """
from tess_shell import Module, action

class Driver(Module):
    def __init__(self):
        self.seen = []

    @action
    def pressed(self, event):
        self.seen.append(("pressed", event.use, dict(event.args)))

    @action
    def changed(self, event):
        self.seen.append(("changed", event.use, event.old, event.new, event.value))
"""


@dataclass
class Widgets:
    manager: SurfaceManager
    host: ModuleHost
    store: ValueStore
    lines: list[str] = field(default_factory=list)
    problems: list[Any] = field(default_factory=list)
    uses: list[str] = field(default_factory=list)

    @property
    def bar(self) -> Any:
        return next(s for s in self.manager.surfaces if s.name == "Top_Bar")

    @property
    def window(self) -> Any:
        return self.bar.window

    @property
    def view(self) -> Any:
        return self.bar.view

    def log(self) -> str:
        return "\n".join(self.lines)

    def warnings(self) -> list[str]:
        return [x for x in self.lines if "| WARNING " in x or "| ERROR " in x]

    def advance(self, ms: float = 16) -> None:
        self.window.advance(ms)

    def send(self, key: str, value: object, use: str | None = None) -> None:
        """Send a value to the Driver (every use, or ``use``) and let the surface show it."""
        self.host.loaded["Driver"].instance.ctx.send(key, value, use=use)
        self.flush()

    def flush(self) -> None:
        self.manager.on_change(self.store.flush())

    def node(self, suffix: str) -> Any:
        """The one tre node whose id ends with ``suffix`` (``Root``, ``Fill``...)."""
        found = [n for k, n in self.view.nodes.items() if k.split("/")[-1] == suffix]
        assert len(found) == 1, (suffix, [k for k in self.view.nodes])
        return found[0]

    def nodes(self, suffix: str) -> list[Any]:
        return [n for k, n in self.view.nodes.items() if k.split("/")[-1] == suffix]

    def of_use(self, module: str, suffix: str, index: int = 0) -> Any:
        """The node ``suffix`` of the ``index``-th use of ``module``."""
        keys = sorted(k for k in self.view.nodes if k.startswith(f"{module}@"))
        found = [k for k in keys if k.split("/")[-1] == suffix]
        return self.view.nodes[found[index]]


def _style_loader(name: str) -> Callable[[str], StyleDef | None]:
    """The ``Style: <file>`` of a shipped module, read from its folder."""

    def load(text: str) -> StyleDef | None:
        path = SHIPPED / name / text
        if not path.is_file():
            return None
        doc = tess_dl.parse(path.read_text(), path=str(path)).document
        assert doc is not None
        style, findings = read_style(doc, str(path))
        assert style is not None, findings
        return style

    return load


def _defs(driver: str, extra: dict[str, str]) -> dict[str, ModuleDef]:
    texts: dict[str, str] = {
        name: (SHIPPED / name / f"{name}_Module.tdl").read_text() for name in STANDARD
    }
    texts["Driver"] = "---\nTDL: 0.1\nName: Driver\n---\n" + driver
    texts.update(extra)
    icons = IconSets([SHIPPED / "Icons"])
    stubs: dict[str, ModuleDef] = {}
    for name, text in texts.items():
        doc = tess_dl.parse(text, path=f"Modules/{name}_Module.tdl").document
        assert doc is not None
        stub = read_module_params(doc, f"{name}.tdl")
        assert stub is not None
        stubs[name] = stub
    defs: dict[str, ModuleDef] = {}
    for name, text in texts.items():
        doc = tess_dl.parse(text, path=f"Modules/{name}_Module.tdl").document
        assert doc is not None
        found, findings = read_module(doc, f"{name}.tdl", stubs, None, _style_loader(name), icons)
        assert found is not None, findings
        defs[name] = found
    return defs


@contextmanager
def running(
    children: str,
    driver: str = "Module { FlexBox { Name: Root, Width: 10, Height: 10 } }",
    extra: dict[str, str] | None = None,
    sheet: str | None = DEFAULT_SHEET,
    extra_sheet: str | None = None,
    appearance: Appearance | None = None,
    popups: str = "",
    driver_py: str = DRIVER_PY,
    dbus: DBusPort | None = None,
) -> Iterator[Widgets]:
    """The shell of ``tests.test_popup`` with ``children`` in its Bar, every standard module and a
    ``Driver`` module (layout ``driver``, Python ``driver_py``) loaded by a real module host."""
    defs = _defs(driver, extra or {})
    result = tess_dl.parse(HEADER + SHELL % (children, popups), path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    icons = IconSets([SHIPPED / "Icons"])
    shell, findings = read_shell(
        result.document, "Shells/Main_Shell.tdl", lambda p: "", defs, None, icons
    )
    assert shell is not None, findings
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    the_theme, _ = read_theme(doc, "T_Theme.tdl")
    assert the_theme is not None
    sheets = []
    for text in (sheet, extra_sheet):
        if text is None:
            continue
        sdoc = tess_dl.parse(text, path="S_Stylesheet.tdl").document
        assert sdoc is not None
        parsed, findings = read_stylesheet(sdoc, "S_Stylesheet.tdl", set(defs))
        assert parsed is not None, findings
        sheets.append(parsed)
    look = make_look(the_theme, sheets, appearance or Appearance(), None, RuntimeIcons(icons))
    store = ValueStore()
    manager = SurfaceManager(StubApp(), defs, lambda k: k, store, look)  # type: ignore[arg-type]
    with tempfile.TemporaryDirectory() as tmp:
        host = ModuleHost(store, TimeSource(), Path(tmp))

        def route(handler: m.Handler, key: str, raw: object) -> None:
            if handler.builtin:
                manager.run_builtin(handler, raw)
            else:
                host.dispatch(handler, key, raw)

        manager.sink = route
        host.popups = manager.popups
        host.dbus = dbus
        live = Widgets(manager, host, store)
        sink = logger.add(lambda message: live.lines.append(str(message).rstrip()), level="DEBUG")
        try:
            uses = manager.plan(shell)
            live.uses = [u.key for u in uses]
            by_module: dict[str, list[Any]] = {}
            for use in uses:
                by_module.setdefault(use.module, []).append(use)
            by_module.setdefault("Driver", [])
            for name, module_uses in by_module.items():
                if name == "Driver":
                    py = Path(tmp) / "Driver_Module.py"
                    py.write_text(driver_py)
                else:
                    py = SHIPPED / name / f"{name}_Module.py"
                loaded, problems = host.load(defs[name], py, f"uid-{name}", module_uses)
                assert loaded is not None, problems
            live.problems = host.check_calls(manager.planned_handlers())
            live.problems += host.start_all()
            store.flush()
            manager.build()
            live.window.advance(16)
            yield live
        finally:
            logger.remove(sink)
