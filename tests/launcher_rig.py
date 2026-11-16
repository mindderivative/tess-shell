"""The launcher on temporary data: the shipped ``Launcher`` Panel and ``Applications`` module in a
headless shell (``tests/widgets_live.py``), over a real :class:`AppService` whose index reads a
TEMPORARY ``applications`` folder of made-up entries and whose starter is a recorder
(:class:`FakeRunner`). Nothing here reads the user's applications, starts a process or touches the
state folder. The test thread is the loop thread: ``Loop.call_soon`` queues what the worker hands
over and ``Desk.settle`` drains it. Not collected by pytest."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tess_shell.binder.images import IMAGES
from tess_shell.schema.default_panels import PANELS
from tess_shell.services.apps import AppService, StartSpec
from tess_shell.services.desktop_entries import ApplicationIndex
from tess_shell.services.icons import IconService
from tests.icon_theme import Dir, svg, write_theme
from tests.widgets_live import Widgets, running

RED = "#ff0000"
ENV = {
    "HOME": "/home/test-user",
    "PATH": "/usr/bin:/bin",
    "LANG": "C",
    "NOTIFY_SOCKET": "/run/systemd/notify",
    "INVOCATION_ID": "abc",
    "JOURNAL_STREAM": "8:1",
    "TESS_SHELL_LAUNCH_RECORD": "/nowhere",
    "XDG_ACTIVATION_TOKEN": "stale",
}
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children {\n"
    "  Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, Children {\n"
    "    Rectangle { Name: Btn, Width: 20, Height: 20 } } }\n"
    f"  {PANELS['Launcher'][1]}\n"
    "} } }\n"
)


class Loop:
    """``call_soon`` for the service and the modules: functions wait until the test drains them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: list[Callable[[], None]] = []

    def call_soon(self, fn: Callable[[], None]) -> None:
        with self._lock:
            self._queue.append(fn)

    def drain(self) -> int:
        with self._lock:
            queued, self._queue = self._queue, []
        for fn in queued:
            fn()
        return len(queued)


@dataclass
class FakeRunner:
    """What the service starts processes with, in a test: it records and starts nothing."""

    programs: set[str] = field(default_factory=lambda: {"fake-app", "xdg-terminal-exec", "sh"})
    scope: bool = True
    fail_scope: bool = False  # the scope start raises OSError (systemd-run failed)
    fail_plain: bool = False
    started: list[StartSpec] = field(default_factory=list)

    def which(self, program: str) -> str | None:
        return f"/usr/bin/{program}" if program in self.programs else None

    def scope_available(self) -> bool:
        return self.scope

    def spawn(self, spec: StartSpec) -> None:
        if spec.scope is not None and self.fail_scope:
            raise OSError("systemd-run: no user manager")
        if spec.scope is None and self.fail_plain:
            raise OSError("cannot start")
        self.started.append(spec)


def write_entry(folder: Path, name: str, **keys: str) -> Path:
    """``<folder>/<name>.desktop``: an application called ``name`` with the extra keys."""
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}"]
    lines += [f"{k}={v}" for k, v in keys.items()]
    path = folder / f"{name.lower().replace(' ', '-')}.desktop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@dataclass
class Desk:
    w: Widgets
    apps: AppService
    runner: FakeRunner
    loop: Loop
    folder: Path  # the temporary ``applications`` folder
    counts: Path
    home: Path
    shown: list[str] = field(default_factory=list)

    def settle(self, predicate: Callable[[], object], timeout: float = 5.0) -> bool:
        """Drain what the workers handed over, flush the values and let the Panel draw, until
        ``predicate`` holds (never a fixed sleep)."""
        deadline = time.monotonic() + timeout
        while True:
            self.loop.drain()
            self.w.flush()
            self.window.advance(16)  # the engine runs what it was asked for (a token request)
            if predicate():
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.005)

    @property
    def panel(self) -> Any:
        return self.w.surface("Launcher")

    @property
    def window(self) -> Any:
        return self.panel.window

    def toggle(self) -> None:
        """What a shortcut press does: ``Toggle`` of the Panel named ``Launcher`` (the control
        interface's command)."""
        ok, message = self.w.manager.control_surface("Toggle", "Launcher")
        assert ok, message
        self.window.advance(16)
        self.settle(lambda: True)

    @property
    def hidden(self) -> bool:
        return bool(self.panel.hidden)

    def press(self, key: str, **mods: bool) -> None:
        self.window.simulate("key_down", key=key, **mods)
        self.window.simulate("key_up", key=key, **mods)
        self.w.flush()
        self.window.advance(16)
        self.loop.drain()
        self.w.flush()

    def type(self, text: str) -> None:
        """Committed text arrives as tre's ``input`` event, as a real key press sends it."""
        self.window.simulate("input", text=text)
        self.w.flush()
        self.window.advance(16)
        self.loop.drain()
        self.w.flush()

    # -- what the Panel shows -----------------------------------------------------------------

    def field(self) -> Any:
        """The text input of the search field (the node with a selection that takes the focus)."""
        expanded = self.panel.planned.expanded
        (call,) = [u.key for u in expanded.uses if u.name.endswith(".query")]
        found = [
            n
            for key, n in self.panel.view.nodes.items()
            if key.split("/")[0] == call and _is_input(n) and n.get("focusable")
        ]
        assert len(found) == 1, (found, list(self.panel.view.nodes))
        return found[0]

    def rows(self) -> list[Any]:
        return [n for key, n in self.panel.view.nodes.items() if key.split("/")[-1] == "Row"]

    def names(self) -> list[str]:
        """The names of the rows, in order (the ``Title`` of each)."""
        return [
            str(n.get("text"))
            for key, n in self.panel.view.nodes.items()
            if key.split("/")[-1] == "Title"
        ]

    def selected(self) -> list[str]:
        """The names of the rows marked selected."""
        out = []
        for key, row in self.panel.view.nodes.items():
            if key.split("/")[-1] == "Row" and row.get("selected"):
                out.append(_title_of(self.panel.view, key))
        return out

    def message(self) -> str:
        found = [
            str(n.get("text"))
            for key, n in self.panel.view.nodes.items()
            if key.split("/")[-1] == "Message"
        ]
        return found[0] if found else ""


def _is_input(node: Any) -> bool:
    try:
        node.get("selection")
    except ValueError:  # tre: only a text input has a selection
        return False
    return True


def _title_of(view: Any, row_key: str) -> str:
    prefix = row_key.rsplit("/", 1)[0] + "/"
    for key, node in view.nodes.items():
        if key.startswith(prefix) and key.split("/")[-1] == "Title":
            return str(node.get("text"))
    return ""


@contextmanager
def launcher_desk(
    tmp_path: Path,
    entries: Mapping[str, Mapping[str, str]] | Sequence[str] = (),
    *,
    runner: FakeRunner | None = None,
    env: Mapping[str, str] | None = None,
    ready: bool = True,
) -> Iterator[Desk]:
    """The launcher over ``entries`` (an application's name -> its extra keys; a bare name has
    none) written into a temporary folder. With ``ready`` the desk waits until the index is
    built."""
    folder = tmp_path / "data" / "applications"
    folder.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    items = entries.items() if isinstance(entries, Mapping) else ((n, {}) for n in entries)
    for name, keys in items:
        write_entry(folder, name, **keys)
    base = tmp_path / "icons"
    write_theme(
        base, "hicolor", [Dir("scalable/apps", 48, "Scalable", {"fake-icon.svg": svg(RED)})]
    )
    index = ApplicationIndex(
        folders=[folder], locale="", desktops=(), which=lambda p: f"/usr/bin/{p}"
    )
    icons = IconService(
        IMAGES.register,
        theme="hicolor",
        bases=[base],
        pixmaps=None,
        config_home=tmp_path / "config",
        apps=index,
    )
    loop = Loop()
    runner = runner or FakeRunner()
    counts = tmp_path / "state" / "launcher-counts.json"
    apps = AppService(
        index,
        runner=runner,
        counts=counts,
        call_soon=loop.call_soon,
        env=dict(ENV if env is None else env),
        home=str(home),
    )
    with running(
        "",
        body=BODY,
        home="Launcher",
        icon_port=icons,
        apps=apps,
        # a use's key holds a UID, not the path its blocks are named by, as in a running shell
        uid_of=lambda key: "u" + hashlib.md5(key.encode()).hexdigest()[:12],
        call_soon=loop.call_soon,
    ) as w:
        desk = Desk(w, apps, runner, loop, folder, counts, home)
        try:
            if ready:
                assert desk.settle(lambda: apps.ready)
            yield desk
        finally:
            w.host.stop_all()
            apps.stop()
