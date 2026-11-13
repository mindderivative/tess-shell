"""A shell with the shipped Tray on a private session bus (Tray Module): a fake watcher, fake items,
the real icon service on a temporary theme folder, the real tray host service and the headless Bar
of ``tests/widgets_live.py`` with a real module host. Never touches the real buses. Not collected by
pytest."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tess_shell.binder.images import IMAGES
from tess_shell.services.icons import IconService
from tess_shell.services.tray import TrayService
from tests.fake_sni import Item, Watcher, add_item, add_watcher
from tests.icon_theme import Dir, svg, write_theme
from tests.modules_rig import Desk, desk
from tests.widgets_live import Widgets, running

PID = 4242
HOST_NAME = f"org.kde.StatusNotifierHost-{PID}"
# the Popups a Tray needs in the shell file (Tray_Menu > the three Popups)
POPUPS = " ".join(
    f"Popup {{ Name: {name}, Attach: BOTTOM, Max_Height: 600, "
    "Style { Background: $color.surface_raised, Corner_Radius: 8 }, "
    f"Children {{ Tray_Menu {{ Level: {level} }} }} }}"
    for name, level in (("Tray_Menu", 1), ("Tray_Menu_2", 2), ("Tray_Menu_3", 3))
)


@dataclass
class TrayDesk:
    d: Desk
    icons: IconService
    tray: TrayService
    watcher: Watcher
    theme: Path  # the base folder of the temporary icon theme

    def item(self, suffix: str = "1-1", **kw: Any) -> Item:
        """A fake item on the session bus (not up yet)."""
        return add_item(self.d.session, suffix, **kw)


def default_theme(base: Path) -> None:
    """A theme ``Fake`` with ``fake-icon`` as an SVG (and an unrelated one in hicolor)."""
    write_theme(
        base,
        "Fake",
        [Dir("scalable/apps", 48, "Scalable", {"fake-icon.svg": svg("#ff0000")})],
        inherits=["hicolor"],
    )
    write_theme(
        base,
        "hicolor",
        [
            Dir(
                "scalable/apps",
                48,
                "Scalable",
                {"app-quit.svg": svg("#0000ff"), "hi-icon.svg": svg("#00ffff")},
            )
        ],
    )


@contextmanager
def tray_desk(tmp_path: Path, *, watcher_up: bool = True) -> Iterator[TrayDesk]:
    base = tmp_path / "icons"
    default_theme(base)
    with desk() as d:
        watcher = add_watcher(d.session)
        if watcher_up:
            watcher.up()
        icons = IconService(IMAGES.register, theme="Fake", bases=[base], pixmaps=None)
        tray = TrayService(d.service, pid=PID)
        yield TrayDesk(d, icons, tray, watcher, base)


@contextmanager
def tray_shell(t: TrayDesk, children: str = "Tray { }", **kwargs: Any) -> Iterator[Widgets]:
    kwargs.setdefault("popups", POPUPS)
    with running(
        children,
        dbus=t.d.layer,
        icon_port=t.icons,
        tray=t.tray,
        **kwargs,
    ) as w:
        try:
            yield w
        finally:
            w.host.stop_all()
