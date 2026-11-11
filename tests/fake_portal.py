"""A fake ``org.freedesktop.portal.Desktop`` on a private bus (tests/fake_dbus.py), for the portal
reader's tests.

The real portal is never touched: the daemon is ``dbus-daemon`` on its own socket.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from dbus_fast import Variant

from tess_shell.services.portal import NAMESPACE, PATH, PORTAL, REGISTRY, SETTINGS
from tests.fake_dbus import HAVE_DAEMON, FakeBus, FakeObject, fake_bus, wait_for

__all__ = ["HAVE_DAEMON", "Portal", "fake_portal", "wait_for"]


class Portal:
    """The fake service: ``set`` changes a value and emits ``SettingChanged``; ``settings.calls``
    and ``registry.ids`` say what the reader asked."""

    def __init__(self, bus: FakeBus) -> None:
        self.values: dict[str, Variant] = {
            "color-scheme": Variant("u", 1),
            "accent-color": Variant("(ddd)", [0.25, 0.5, 1.0]),
            "contrast": Variant("u", 0),
            "reduced-motion": Variant("u", 0),
        }
        self.service = bus.service(PORTAL)
        self.calls: list[str] = []
        self.ids: list[str] = []
        self.settings: Any = _Calls(
            self.service.add(
                PATH,
                SETTINGS,
                methods={"ReadAll": (["as"], "a{sa{sv}}", self._read_all)},
                signals={"SettingChanged": "ssv"},
            ),
            self.calls,
        )
        self.registry: Any = _Registry(
            self.service.add(
                PATH, REGISTRY, methods={"Register": (["s", "a{sv}"], "", self._register)}
            ),
            self.ids,
        )

    def _read_all(self, namespaces: list[str]) -> dict[str, dict[str, Variant]]:
        self.calls.append("ReadAll")
        return {NAMESPACE: dict(self.values)}

    def _register(self, app_id: str, options: dict[str, Variant]) -> None:
        self.calls.append("Register")
        self.ids.append(app_id)

    def up(self) -> None:
        self.service.up()

    def down(self) -> None:
        self.service.down()

    def set(self, key: str, value: Variant) -> None:
        self.values[key] = value
        self.settings.obj.emit("SettingChanged", NAMESPACE, key, value)


class _Calls:
    def __init__(self, obj: FakeObject, calls: list[str]) -> None:
        self.obj = obj
        self.calls = calls


class _Registry:
    def __init__(self, obj: FakeObject, ids: list[str]) -> None:
        self.obj = obj
        self.ids = ids


@contextmanager
def fake_portal(*, running: bool = True) -> Iterator[tuple[str, Portal]]:
    with fake_bus() as bus:
        portal = Portal(bus)
        if running:
            portal.up()
        yield bus.address, portal
