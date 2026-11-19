"""The reload of a running shell, in this process and with no compositor: the real ``Reloader``,
``SurfaceManager``, ``ModuleHost`` and ``ValueStore`` over a private configuration folder, and a
real ``tess_re.App`` (never run) that is given every window, as the shell does. Not collected by
pytest.

What the rig stands in for, and what it keeps:

* ``Reloader._apply`` is what the file watcher's reload runs on the loop thread (``trigger`` reads
  and checks the files on the watcher's thread, then queues it); the rig calls ``prepare`` and
  ``_apply`` one after the other, so a reload here is the reload of the running shell minus the
  debounce and the thread hop.
* ``App.add_window`` is the real one. tre's ``App`` keeps each window it was given for good, which
  is the thing a reload that closes and opens Panels shows; a stub app that forgets the window
  (``tests/test_panel.py``) cannot.
* ``Window.close()`` does nothing without a running loop; the loop delivers ``closed`` to a window
  that was closed, so after each reload :meth:`settle` does the same for the windows no surface
  names, then lets the live windows run their first timers (``advance``).
"""

from __future__ import annotations

import gc
import os
import re
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest import mock

import tess_re

from tess_shell.appearance import Appearance
from tess_shell.config.paths import ensure_config_dir
from tess_shell.config.registry import Registry
from tess_shell.config.settings import load_settings
from tess_shell.config.uids import assign_uids
from tess_shell.model.store import ValueStore
from tess_shell.modules.host import ModuleHost
from tess_shell.modules.ticks import TimeSource
from tess_shell.reloader import Outcome, Reloader
from tess_shell.scanner import build_look, scan
from tess_shell.surfaces.manager import SurfaceManager
from tess_shell.watch import OwnWrites
from tests.perf.budget_rig import SETTINGS, shell_text, surfaces_panels
from tests.test_panel import StubApp

BAR = 'Text { Text: "Tesserae", Font_Size: 14 }'
UID = re.compile(r"^UID: (\S+)", re.MULTILINE)


def private_environment(root: Path) -> dict[str, str]:
    """The folders the shell writes to, all under ``root``: the home, XDG's and the runtime
    folder. Set them before :class:`ReloadRig` is made."""
    out = {}
    for name, folder in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_RUNTIME_DIR", "run"),
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)
        out[name] = str(root / folder)
    return out


@contextmanager
def private_session(root: Path) -> Iterator[None]:
    """:func:`private_environment` for the length of the block, with no display."""
    with mock.patch.dict(os.environ, private_environment(root)):
        os.environ.pop("WAYLAND_DISPLAY", None)
        os.environ.pop("DISPLAY", None)
        yield


class RealApp(StubApp):
    """The stub's outputs, and a real ``tess_re.App`` that keeps the windows it is given."""

    def __init__(self) -> None:
        self.app = tess_re.App()
        self.windows: list[Any] = []

    def add_window(self, window: Any) -> None:
        self.windows.append(window)
        self.app.add_window(window)


class ReloadRig:
    """A shell of a Bar and ``panels`` Panels, running in this process. ``reload`` writes the main
    shell file and applies it the way the reload does."""

    def __init__(self, root: Path, *, bar: str = BAR, panels: int = 9) -> None:
        self.bar = bar
        self.cfg = root / "config" / "tesserae-shell"
        ensure_config_dir(self.cfg)
        (self.cfg / "settings.tdl").write_text(SETTINGS)
        self.file = self.cfg / "Shells" / "Main_Shell.tdl"
        self._uid = ""
        self.write(surfaces_panels(panels))
        settings, findings = load_settings(self.cfg)
        assert settings is not None and settings.main_shell_path is not None, findings
        registry = Registry.open(settings.registry)
        result = scan(settings, self.cfg)
        assert not result.errors, result.findings
        store, ticks = ValueStore(), TimeSource()
        self.app = RealApp()
        look = build_look(result, settings, Appearance())
        self.manager = SurfaceManager(
            self.app,  # type: ignore[arg-type]
            {n: mf.definition for n, mf in result.modules.items()},
            registry.uid_for,
            store,
            look,
            positions=registry,
        )
        host = ModuleHost(store, ticks, self.cfg)
        host.popups = self.manager.popups
        host.surfaces = self.manager
        host.call_soon = lambda fn: fn()
        host.focus = self.manager.mode
        self.manager.sink = lambda h, k, raw: (
            self.manager.run_builtin(h, raw) if h.builtin else host.dispatch(h, k, raw)
        )
        uses = self.manager.plan(result.shells[settings.main_shell_path])
        by_module: dict[str, list[Any]] = {}
        for use in uses:
            by_module.setdefault(use.module, []).append(use)
        uids, _ = assign_uids(
            [mf.path for mf in result.modules.values() if not mf.shipped],
            self.cfg,
            lambda key: registry.uid_for(key, "file"),
            Path(os.environ["XDG_STATE_HOME"]) / "backups",
        )
        for name, module_uses in by_module.items():
            mf = result.modules[name]
            uid = uids.get(mf.path) or registry.uid_for(f"module:{name}", "module")
            host.load(mf.definition, mf.python, uid, module_uses)
        host.start_all()
        store.flush()
        self.manager.dynamic_sink = lambda added, removed: host.dynamic(added, removed)
        self.manager.build()
        store.on_change = self.manager.on_change
        self.reloader = Reloader(
            self.cfg,
            settings,
            True,
            registry,
            self.manager,
            host,
            store,
            OwnWrites(),
            lambda fn: fn(),
            result,
            {},
        )
        self.settle()

    def write(self, panels: str, height: int = 34) -> None:
        text = shell_text(self.bar, panels=panels).replace("Height: 34,", f"Height: {height},")
        if self._uid:  # the shell gave the file its UID at the first reload; keep it
            text = text.replace("Name: Main_Shell\n", f"Name: Main_Shell\nUID: {self._uid}\n", 1)
        self.file.write_text(text)

    def reload(self, panels: str, height: int = 34) -> Outcome:
        """Save the file with ``panels`` and a Bar ``height``, reload, let the loop's turn pass."""
        self.write(panels, height)
        prepared = self.reloader.prepare({self.file})
        assert not hasattr(prepared, "why"), prepared
        outcome = self.reloader._apply(prepared)  # type: ignore[arg-type]
        assert outcome.ok, outcome.message
        if not self._uid and (found := UID.search(self.file.read_text())):
            self._uid = found.group(1)
        self.settle()
        return outcome

    def settle(self) -> None:
        """What the loop does after a reload: ``closed`` for each window no surface names, and the
        live windows' first 300 ms (the timers a new surface starts)."""
        named = {id(s.window) for s in self.manager.surfaces if s.window is not None}
        kept = []
        for window in self.app.windows:
            if id(window) in named:
                kept.append(window)
            else:
                window.simulate("closed")
        self.app.windows = kept
        for window in kept:
            window.advance(300)

    def surface_count(self) -> int:
        return len(self.manager.surfaces)


def count_objects(*names: str) -> dict[str, int]:
    """Live objects of each class name, after a full collection (the collector runs here, on the
    thread that owns tre's objects)."""
    gc.collect()
    wanted = Counter({name: 0 for name in names})
    for obj in gc.get_objects():
        name = type(obj).__name__
        if name in wanted:
            wanted[name] += 1
    return dict(wanted)


def step(rig: ReloadRig, index: int, *, panels: bool = True) -> None:
    """Reload number ``index`` of a run that takes the nine Panels away and brings them back: odd
    reloads have none, even ones all nine. The Bar's height changes with each, as a save would.
    ``panels=False`` leaves the Panels alone and changes only the height (a style)."""
    shown = surfaces_panels(9) if index % 2 == 0 or not panels else ""
    rig.reload(shown, 34 + 2 * (index % 2))
