"""A fake ``org.kde.kglobalaccel`` on a private bus (M6c, Global Shortcuts). The real service is
never read, called or monitored: every name, signature and argument here is the one the spec lists
(``Global Shortcuts > What the Service Offers``, ``The u Flags in Plain Words``), and every test of
the shortcuts and the hand-check kit's fake desktop use this, never the session bus.

``/kglobalaccel`` (``org.kde.KGlobalAccel``): ``doRegister(as)``, ``getComponent(s) -> o``,
``setShortcutKeys(asa(ai)u) -> a(ai)``, ``shortcutKeys(as) -> a(ai)``,
``isGlobalShortcutAvailable(is) -> b``, ``setInactive(as)``, ``unRegister(as)``, ``unregister(ss)``
and the signals ``yourShortcutsChanged(asa(ai))`` and ``yourShortcutGotChanged(asai)``. A component
is an object ``/component/<name>`` (``org.kde.kglobalaccel.Component``) with the properties
``uniqueName`` and ``friendlyName``, the methods ``shortcutNames``, ``allShortcutInfos``,
``invokeShortcut``, ``isActive`` and ``cleanUp`` and the signal ``globalShortcutPressed(s s x)``.

It behaves like the real service on the points the shell depends on:

* a key another component owns (``own``) comes back EMPTY from ``setShortcutKeys``;
* a key the user changed in System Settings (``user_changes``) is kept, and restored when the action
  registers again with the flags not including ``NoAutoloading`` (4); ``unregister`` forgets it;
* an action registered and not present (``setInactive``, a service that restarted) stays known;
* the service can leave and come back (``stop``, ``start``, ``restart``);
* every call is recorded (``calls``) with the arguments as the wire carried them.

``FakeKGlobalAccel`` makes its service on a :class:`tests.fake_dbus.FakeBus`; its handlers run on
the fake thread, so the state is read from the test thread when the service is quiet (``wait_for``).
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from dbus_fast import DBusError

from tests.fake_dbus import FakeBus, FakeObject, FakeService

NAME = "org.kde.kglobalaccel"
PATH = "/kglobalaccel"
INTERFACE = "org.kde.KGlobalAccel"
COMPONENT_INTERFACE = "org.kde.kglobalaccel.Component"
SET_PRESENT = 2
NO_AUTOLOADING = 4
IS_DEFAULT = 8


@dataclass(frozen=True)
class Call:
    """One call the fake received: the member, its arguments, and when."""

    member: str
    args: tuple[Any, ...]
    at: float = 0.0

    @property
    def flags(self) -> int | None:
        return int(self.args[2]) if self.member == "setShortcutKeys" else None


@dataclass
class ActionState:
    unique: str
    friendly: str
    keys: list[int] = field(default_factory=list)  # the active keys
    defaults: list[int] = field(default_factory=list)
    present: bool = False


@dataclass
class ComponentState:
    unique: str
    friendly: str
    actions: dict[str, ActionState] = field(default_factory=dict)


def object_path(component: str) -> str:
    """``/component/`` and the unique name with every character that is not a letter or a digit
    replaced by ``_`` (seen on the real service: ``org_kde_dolphin_desktop``)."""
    return "/component/" + re.sub(r"[^A-Za-z0-9]", "_", component)


def _sequences(keys: list[int]) -> list[Any]:
    return [[[k]] for k in keys]


def _codes(sequences: Any) -> list[int]:
    return [int(k) for struct in sequences for sequence in struct for k in sequence if k]


class FakeKGlobalAccel:
    """The fake service. ``calls`` is every call in order; ``components`` the registry, by unique
    name; ``owned`` the keys other components hold (a Qt key integer to the owner's name)."""

    def __init__(self, bus: FakeBus) -> None:
        self.bus = bus
        self.service: FakeService = bus.service(NAME)
        self.calls: list[Call] = []
        self.components: dict[str, ComponentState] = {}
        self.saved: dict[tuple[str, str], list[int]] = {}  # what the user chose, by (component, id)
        self.owned: dict[int, str] = {}
        self.refuse: set[str] = set()  # members that raise an error (a refused registration)
        self.refuse_actions: set[str] = set()  # action ids whose doRegister raises
        self._lock = threading.RLock()
        self._objects: dict[str, FakeObject] = {}
        self.main = self.service.add(
            PATH,
            INTERFACE,
            methods={
                "doRegister": (["as"], "", self._do_register),
                "getComponent": (["s"], "o", self._get_component),
                "setShortcutKeys": (["as", "a(ai)", "u"], "a(ai)", self._set_keys),
                "shortcutKeys": (["as"], "a(ai)", self._shortcut_keys),
                "isGlobalShortcutAvailable": (["i", "s"], "b", self._available),
                "setInactive": (["as"], "", self._set_inactive),
                "unRegister": (["as"], "", self._un_register),
                "unregister": (["s", "s"], "", self._unregister),
            },
            signals={"yourShortcutsChanged": "asa(ai)", "yourShortcutGotChanged": "asai"},
        )

    # -- the test's controls (any thread) ---------------------------------------------------------

    def start(self) -> None:
        """Take the name on the bus (the service is up)."""
        self.service.up()

    def stop(self) -> None:
        """The service goes away: the connection closes and with it every action's ``present``."""
        self._forget_presence()
        self.service.drop()

    def restart(self) -> None:
        """``kglobalacceld`` or KWin restarted: the registry stays (it is in the user's config), no
        action is present, the name is owned by a new connection."""
        self._forget_presence()
        self.service.restart()

    def own(self, key: int, owner: str = "kwin") -> None:
        """Another component holds ``key`` (a Qt key integer): a request for it comes back empty."""
        with self._lock:
            self.owned[key] = owner

    def release(self, key: int) -> None:
        with self._lock:
            self.owned.pop(key, None)

    def preregister(
        self, component: str, action: str, friendly: str = "", keys: tuple[int, ...] = ()
    ) -> None:
        """An action that is already in the registry (an earlier run of the shell, or another
        application): not present."""
        with self._lock:
            state = self._component(component, component)
            state.actions[action] = ActionState(action, friendly or action, list(keys), list(keys))
        self._export(component)

    def user_changes(self, component: str, action: str, keys: tuple[int, ...]) -> None:
        """The user changed (or cleared) a key in System Settings: it is saved, becomes the active
        key at once, and ``yourShortcutsChanged`` is emitted."""
        with self._lock:
            self.saved[(component, action)] = list(keys)
            state = self.components[component]
            act = state.actions[action]
            act.keys = list(keys)
            ids = [component, action, state.friendly, act.friendly]
        self._emit_main("yourShortcutsChanged", ids, _sequences(list(keys)))

    def press(self, action: str, component: str = "tesserae-shell", timestamp: int = 1) -> None:
        """A key press the service saw: ``globalShortcutPressed`` on the component."""
        obj = self._objects[object_path(component)]
        obj.emit("globalShortcutPressed", component, action, timestamp)

    def press_key(self, key: int, timestamp: int = 1) -> bool:
        """The user presses ``key``: whichever present action of any component holds it gets the
        signal. Returns whether one did."""
        with self._lock:
            hit = next(
                (
                    (c.unique, a.unique)
                    for c in self.components.values()
                    for a in c.actions.values()
                    if a.present and key in a.keys
                ),
                None,
            )
        if hit is None:
            return False
        self.press(hit[1], hit[0], timestamp)
        return True

    def of(self, member: str) -> list[Call]:
        with self._lock:
            return [c for c in self.calls if c.member == member]

    def action(self, component: str, action: str) -> ActionState | None:
        with self._lock:
            state = self.components.get(component)
            return None if state is None else state.actions.get(action)

    def keys_of(self, component: str, action: str) -> list[int]:
        found = self.action(component, action)
        return [] if found is None else list(found.keys)

    def names(self, component: str = "tesserae-shell") -> list[str]:
        with self._lock:
            state = self.components.get(component)
            return [] if state is None else list(state.actions)

    def present(self, component: str = "tesserae-shell") -> list[str]:
        with self._lock:
            state = self.components.get(component)
            return [] if state is None else [n for n, a in state.actions.items() if a.present]

    def clear_calls(self) -> None:
        with self._lock:
            self.calls.clear()

    # -- state, on the fake thread ----------------------------------------------------------------

    def _forget_presence(self) -> None:
        with self._lock:
            for state in self.components.values():
                for act in state.actions.values():
                    act.present = False

    def _log(self, member: str, *args: Any) -> None:
        with self._lock:
            self.calls.append(Call(member, args, time.monotonic()))
        if member in self.refuse:
            raise DBusError("org.kde.kglobalaccel.Refused", f"{member} is refused (a test)")

    def _component(self, unique: str, friendly: str) -> ComponentState:
        state = self.components.get(unique)
        if state is None:
            state = self.components[unique] = ComponentState(unique, friendly)
        return state

    def _export(self, unique: str) -> FakeObject:
        """The component's object (made once, on the first ``doRegister``)."""
        path = object_path(unique)
        existing = self._objects.get(path)
        if existing is not None:
            return existing
        state = self.components[unique]

        def names() -> list[str]:
            self._log_on(path, "shortcutNames")
            with self._lock:
                return list(self.components[unique].actions)

        def invoke(name: str) -> bool:
            self._log_on(path, "invokeShortcut", name)
            with self._lock:
                known = name in self.components[unique].actions
            if known:
                self._emit(path, "globalShortcutPressed", unique, name, int(time.time() * 1000))
            return known

        def active() -> bool:
            self._log_on(path, "isActive")
            with self._lock:
                return any(a.present for a in self.components[unique].actions.values())

        def clean_up() -> None:
            self._log_on(path, "cleanUp")
            with self._lock:
                self.components.pop(unique, None)
                self.saved = {k: v for k, v in self.saved.items() if k[0] != unique}

        def infos() -> list[Any]:
            self._log_on(path, "allShortcutInfos")
            return []

        obj = self.service.add(
            path,
            COMPONENT_INTERFACE,
            properties={
                "uniqueName": ("s", state.unique),
                "friendlyName": ("s", state.friendly),
            },
            methods={
                "shortcutNames": ([], "as", names),
                "allShortcutInfos": ([], "a(ssssssasasi)", infos),
                "invokeShortcut": (["s"], "b", invoke),
                "isActive": ([], "b", active),
                "cleanUp": ([], "", clean_up),
            },
            signals={
                "globalShortcutPressed": "ssx",
                "globalShortcutReleased": "ssx",
                "globalShortcutRepeated": "ssx",
            },
        )
        self._objects[path] = obj
        bus = self.service._bus
        if bus is not None and bus.connected:
            bus.export(path, obj._build())
        return obj

    def _log_on(self, path: str, member: str, *args: Any) -> None:
        self._log(f"{path}:{member}", *args)

    def _emit(self, path: str, signal: str, *args: Any) -> None:
        """Emit from inside a handler (the fake thread): no hop to another thread."""
        obj = self._objects.get(path)
        if obj is not None and obj._iface is not None:
            getattr(obj._iface, signal)(*args)

    def _emit_main(self, signal: str, *args: Any) -> None:
        async def go() -> None:
            assert self.main._iface is not None
            getattr(self.main._iface, signal)(*args)

        self.service.thread.run(go())

    def _state_of(self, ids: list[str]) -> tuple[ComponentState, ActionState]:
        if len(ids) < 2:
            raise DBusError(
                "org.freedesktop.DBus.Error.InvalidArgs", "an action id has four strings"
            )
        state = self.components.get(ids[0])
        act = None if state is None else state.actions.get(ids[1])
        if state is None or act is None:
            raise DBusError("org.kde.kglobalaccel.NoSuchAction", f"no action {ids[:2]}")
        return state, act

    # -- the interface ----------------------------------------------------------------------------

    def _do_register(self, ids: list[str]) -> None:
        self._log("doRegister", list(ids))
        if len(ids) > 1 and ids[1] in self.refuse_actions:
            raise DBusError("org.kde.kglobalaccel.Refused", f"{ids[1]} is refused (a test)")
        if len(ids) != 4 or not ids[0] or not ids[1]:
            raise DBusError(
                "org.freedesktop.DBus.Error.InvalidArgs", "doRegister needs four strings"
            )
        with self._lock:
            state = self._component(ids[0], ids[2])
            state.actions.setdefault(ids[1], ActionState(ids[1], ids[3]))
            state.actions[ids[1]].friendly = ids[3]
            state.friendly = ids[2]
        self._export(ids[0])

    def _get_component(self, unique: str) -> str:
        self._log("getComponent", unique)
        if unique not in self.components:
            raise DBusError("org.kde.kglobalaccel.NoSuchComponent", f"no component {unique}")
        return object_path(unique)

    def _set_keys(self, ids: list[str], sequences: list[Any], flags: int) -> list[Any]:
        self._log("setShortcutKeys", list(ids), [list(s) for s in sequences], int(flags))
        with self._lock:
            state, act = self._state_of(list(ids))
            wanted = _codes(sequences)
            if flags & IS_DEFAULT:
                act.defaults = list(wanted)
                return _sequences(list(wanted))
            if not flags & NO_AUTOLOADING and (state.unique, act.unique) in self.saved:
                wanted = list(self.saved[(state.unique, act.unique)])  # the user's key wins
            taken = {
                k
                for c in self.components.values()
                if c is not state
                for a in c.actions.values()
                for k in a.keys
            }
            kept = [k for k in wanted if k not in self.owned and k not in taken]
            act.keys = kept
            if flags & SET_PRESENT:
                act.present = True
            return _sequences(kept)

    def _shortcut_keys(self, ids: list[str]) -> list[Any]:
        self._log("shortcutKeys", list(ids))
        with self._lock:
            return _sequences(list(self._state_of(list(ids))[1].keys))

    def _available(self, key: int, component: str) -> bool:
        self._log("isGlobalShortcutAvailable", int(key), component)
        with self._lock:
            return key not in self.owned

    def _set_inactive(self, ids: list[str]) -> None:
        self._log("setInactive", list(ids))
        with self._lock:
            self._state_of(list(ids))[1].present = False

    def _un_register(self, ids: list[str]) -> None:
        self._log("unRegister", list(ids))
        self._remove(ids[0], ids[1])

    def _unregister(self, component: str, action: str) -> None:
        self._log("unregister", component, action)
        self._remove(component, action)

    def _remove(self, component: str, action: str) -> None:
        with self._lock:
            state = self.components.get(component)
            if state is not None:
                state.actions.pop(action, None)
            self.saved.pop((component, action), None)
