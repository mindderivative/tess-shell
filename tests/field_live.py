"""A running manager with the shipped TextInput and TextEditor modules and a ``Host`` module that
records what its ``@action`` handlers receive: the text field tests drive a real tre window with
``simulate`` (no compositor). Not collected by pytest."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tess_dl
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.files.icons import IconSets
from tess_shell.model.look import Look, make_look
from tess_shell.model.store import ValueStore
from tess_shell.modules.host import ModuleHost
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.look import read_stylesheet, read_theme
from tess_shell.schema.model import ModuleDef
from tess_shell.schema.shell import read_module, read_module_params, read_shell
from tess_shell.surfaces.manager import SurfaceManager
from tests.shell_samples import HEADER
from tests.test_panel import StubApp
from tests.test_popup import SHELL

SHIPPED = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped"
DARK_THEME = (SHIPPED / "Themes" / "Default_Theme.tdl").read_text()

HOST_PY = """
from tess_shell import Module, action

class Host(Module):
    def __init__(self):
        self.seen = []

    @action
    def changed(self, event):
        self.seen.append(("changed", event.use, event.old, event.new, event.text))

    @action
    def submit(self, event):
        self.seen.append(("submit", event.use, event.old, event.new, event.text))

    @action
    def commit(self, event):
        self.seen.append(("commit", event.use, event.old, event.new, event.text))
"""

HOST_TDL = """Module {
    Params { Text { Type: string, Default: "" } }
    FlexBox { Name: Root, Width: 10, Height: 10 }
}"""


@dataclass
class Fields:
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
    def seen(self) -> list[Any]:
        return self.host.loaded["Host"].instance.seen  # type: ignore[no-any-return]

    def fields(self) -> list[Any]:
        found: list[Any] = []

        def walk(entries: list[Any]) -> None:
            for e in entries:
                if e.typed.kind == m.FIELD:
                    found.append(Field(e))
                walk(e.children)

        walk(self.bar.view.entries)
        return found

    def log(self) -> str:
        return "\n".join(self.lines)

    def advance(self, ms: int = 16) -> None:
        self.window.advance(ms)


@dataclass
class Field:
    """One TextField built: ``box``, ``inp`` (the text input) and ``size`` (the text that gives
    the box the height of its lines, ``None`` when the box has a Height) are tre nodes."""

    entry: Any

    @property
    def box(self) -> Any:
        return self.entry.tre

    def _line(self) -> Any:
        return next(c for c in self.entry.children if c.typed.kind == m.FIELD_LINE)

    @property
    def line(self) -> Any:
        return self._line().tre

    @property
    def inp(self) -> Any:
        return next(c.tre for c in self._line().children if c.typed.kind == m.FIELD_INPUT)

    @property
    def size(self) -> Any:
        found = [c.tre for c in self._line().children if c.typed.kind == m.FIELD_SIZE]
        return found[0] if found else None


def look(theme: str = DARK_THEME, sheet: str | None = None, scheme: str = "dark") -> Look:
    """The look of a theme file (and a stylesheet's text) for a light or dark desktop."""
    doc = tess_dl.parse(theme, path="T_Theme.tdl").document
    assert doc is not None
    the_theme, findings = read_theme(doc, "T_Theme.tdl")
    assert the_theme is not None, findings
    sheets = []
    if sheet is not None:
        sdoc = tess_dl.parse(sheet, path="G_Stylesheet.tdl").document
        assert sdoc is not None
        parsed, findings = read_stylesheet(sdoc, "G_Stylesheet.tdl", {"TextInput", "TextEditor"})
        assert parsed is not None, findings
        sheets.append(parsed)
    return make_look(the_theme, sheets, Appearance(scheme=scheme))  # type: ignore[arg-type]


def _defs(extra: dict[str, str]) -> dict[str, ModuleDef]:
    texts: dict[str, str] = {
        "TextInput": (SHIPPED / "TextInput" / "TextInput_Module.tdl").read_text(),
        "TextEditor": (SHIPPED / "TextEditor" / "TextEditor_Module.tdl").read_text(),
        "Host": "---\nTDL: 0.1\nName: Host\n---\n" + HOST_TDL,
        **extra,
    }
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
        found, findings = read_module(doc, f"{name}.tdl", stubs)
        assert found is not None, findings
        defs[name] = found
    return defs


@contextmanager
def running(
    children: str,
    sheet: str | None = None,
    theme: str = DARK_THEME,
    extra: dict[str, str] | None = None,
    extra_code: dict[str, str] | None = None,
    popups: str = "",
) -> Iterator[Fields]:
    """The shell of ``tests.test_popup`` with ``children`` in its Bar, the shipped TextInput and
    TextEditor and the ``Host`` module loaded by a real module host."""
    defs = _defs(extra or {})
    result = tess_dl.parse(HEADER + SHELL % (children, popups), path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    icons = IconSets([SHIPPED / "Icons"])
    shell, findings = read_shell(
        result.document, "Shells/Main_Shell.tdl", lambda p: "", defs, None, icons
    )
    assert shell is not None, findings
    doc = tess_dl.parse(theme, path="T_Theme.tdl").document
    assert doc is not None
    the_theme, _ = read_theme(doc, "T_Theme.tdl")
    assert the_theme is not None
    sheets = []
    if sheet is not None:
        sdoc = tess_dl.parse(sheet, path="G_Stylesheet.tdl").document
        assert sdoc is not None
        parsed, findings = read_stylesheet(sdoc, "G_Stylesheet.tdl", set(defs))
        assert parsed is not None, findings
        sheets.append(parsed)
    look = make_look(the_theme, sheets, Appearance())
    store = ValueStore()
    manager = SurfaceManager(StubApp(), defs, lambda k: k, store, look)  # type: ignore[arg-type]
    with tempfile.TemporaryDirectory() as tmp:
        host = ModuleHost(store, TimeSource(), Path(tmp))

        def route(handler: m.Handler, key: str, raw: object) -> None:
            if handler.builtin:
                manager.run_builtin(handler)
            else:
                host.dispatch(handler, key, raw)

        manager.sink = route
        host.popups = manager.popups
        live = Fields(manager, host, store)
        sink = logger.add(lambda message: live.lines.append(str(message).rstrip()), level="DEBUG")
        try:
            uses = manager.plan(shell)
            live.uses = [u.key for u in uses]
            by_module: dict[str, list[Any]] = {}
            for use in uses:
                by_module.setdefault(use.module, []).append(use)
            if "Host" not in by_module:
                by_module["Host"] = []
            codes = {"Host": HOST_PY, **(extra_code or {})}
            for name, module_uses in by_module.items():
                py = Path(tmp) / f"{name}_Module.py"
                if name in codes:
                    py.write_text(codes[name])
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
