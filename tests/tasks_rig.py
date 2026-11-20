"""A shell with the shipped Tasks on private buses (Tasks Module): the fake KWin of
``tests/fake_kwin.py`` (its ``/Scripting``, a fake script, and the virtual desktop manager the
module reads), the shell's real control interface, KWin service and window service, the real icon
service on a temporary theme and a temporary ``applications`` folder, and the headless Bar of
``tests/widgets_live.py``. Never touches the real buses or KWin. Not collected by pytest."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tess_shell.binder.images import IMAGES
from tess_shell.services.control import ControlService
from tess_shell.services.desktop_entries import ApplicationIndex
from tess_shell.services.icons import IconService
from tess_shell.services.kwin import KWinService
from tess_shell.services.windows import WindowService
from tests.fake_dbus import FakeObject
from tests.fake_kwin import FakeKWin
from tests.icon_theme import Dir, svg, write_theme
from tests.modules_rig import VDM, VDM_INTERFACE, Desk, desk
from tests.test_control import FakeCommands
from tests.widgets_live import Widgets, running

RED, BLUE = "#ff0000", "#0000ff"


@dataclass
class TasksDesk:
    d: Desk
    fake: FakeKWin
    vdm: FakeObject
    desktops: list[str]  # the ids of the virtual desktops
    kwin: KWinService
    windows: WindowService
    control: ControlService
    icons: IconService
    theme: Path  # the base folder of the temporary icon themes
    applications: Path  # the temporary ``applications`` folder

    def entry(self, app: str, icon: str, name: str = "App", **keys: str) -> None:
        """A desktop entry for ``app`` in the temporary folder."""
        lines = ["[Desktop Entry]", "Type=Application", f"Name={name}", f"Icon={icon}"]
        lines += [f"{k}={v}" for k, v in keys.items()]
        (self.applications / f"{app}.desktop").write_text("\n".join(lines) + "\n")
        self.icons.apps.invalidate()

    def start_kwin(self) -> None:
        """Load the script the way the shell does at start (after the control interface is up)."""
        self.d.service.submit(self.kwin.start()).result(10)

    def settle(self, w: Widgets | None, predicate: Any, timeout: float = 5.0) -> bool:
        return self.d.settle(w, predicate, timeout)


@contextmanager
def tasks_desk(
    tmp_path: Path, *, desktops: tuple[str, ...] = ("Main", "Code"), theme: str | None = "Fake"
) -> Iterator[TasksDesk]:
    base = tmp_path / "icons"
    write_theme(
        base,
        "Fake",
        [Dir("scalable/apps", 48, "Scalable", {"fake-icon.svg": svg(RED)})],
        inherits=["hicolor"],
    )
    write_theme(
        base,
        "Other",
        [Dir("scalable/apps", 48, "Scalable", {"fake-icon.svg": svg(BLUE)})],
        inherits=["hicolor"],
    )
    write_theme(base, "hicolor", [Dir("scalable/apps", 48, "Scalable", {})])
    applications = tmp_path / "data" / "applications"
    applications.mkdir(parents=True)
    with desk() as d:
        fake = FakeKWin(d.session)
        ids = [f"desktop-{i}" for i in range(len(desktops))]
        vdm = fake.service.add(
            VDM,
            VDM_INTERFACE,
            properties={
                "desktops": ("a(uss)", [[i, ids[i], desktops[i]] for i in range(len(desktops))]),
                "current": ("s", ids[0]),
            },
            signals={"currentChanged": "s", "countChanged": "u"},
            writable=["current"],
        )
        fake.up()
        kwin = KWinService(
            d.service,
            d.pump.call_soon,
            runtime_dir=tmp_path / "run",
            action_linger=0.05,
            silent_after=60.0,
        )
        windows = WindowService(kwin)
        control = ControlService(d.service, d.pump.call_soon, FakeCommands(), "x", None, kwin)  # type: ignore[arg-type]
        assert d.service.submit(control.start()).result(10)
        control.set_state("running")
        icons = IconService(
            IMAGES.register,
            theme=theme,
            bases=[base],
            pixmaps=None,
            config_home=tmp_path / "config",  # never the real kdeglobals
            apps=ApplicationIndex(folders=[applications], locale="", desktops=()),
        )
        try:
            yield TasksDesk(d, fake, vdm, ids, kwin, windows, control, icons, base, applications)
        finally:
            try:
                d.service.submit(kwin.stop()).result(10)
            finally:
                try:
                    d.service.submit(control.stop()).result(10)
                finally:
                    fake.close()


@contextmanager
def tasks_shell(t: TasksDesk, children: str = "Tasks { }", **kwargs: Any) -> Iterator[Widgets]:
    with running(
        children,
        dbus=t.d.layer,
        icon_port=t.icons,
        windows=t.windows,
        **kwargs,
    ) as w:
        try:
            yield w
        finally:
            w.host.stop_all()
