"""The shell's global shortcuts through KDE's shortcut service (Global Shortcuts > Registration).

The shell is one component, ``tesserae-shell``, of ``org.kde.kglobalaccel``: each action it declares
(``Toggle_Launcher``, ``Enter_Shortcut_Mode``, a handler of the user's own) is registered with the
service, which grabs the keys; a key press comes back as one ``globalShortcutPressed`` signal and is
handed to the loop with ``call_soon`` to run as the same command the control interface runs.

Everything here runs on the ``dbus`` service thread through :class:`~tess_shell.services.bus.Bus`.
The work done when a press arrives is a lookup and a ``call_soon``; nothing in this module has a
timer, so a connected, quiet service wakes the thread never.

What is sent, and why (all of it from the spec, never read from the real service):

* ``doRegister(as)`` with four strings (component, action, component friendly name, action friendly
  name), then ``setShortcutKeys(asa(ai)u)`` twice, as the client library does: the active keys with
  ``SetPresent`` (2) and the default keys with ``IsDefault`` (8). ``NoAutoloading`` (4) is never
  sent, so a key the user changed in System Settings survives a restart. The first call returns the
  keys the service actually set: an empty answer for a requested key means the desktop (or another
  application) owns it, so the action stays registered with no key and one warning names it. The
  shell never takes a key.
* ``getComponent("tesserae-shell")`` gives the object path of the component (never derived); the
  shell listens to ``globalShortcutPressed`` on it, and to ``yourShortcutsChanged`` on
  ``/kglobalaccel`` for its own component (a key the user changed is used by the service at the
  next press: nothing is sent again).
* A changed key in the settings unregisters the action and registers it anew (the user's saved key
  of the old default is forgotten with it); a removed action is unregistered; an unchanged one is
  not touched. At start, the actions of the component the shell no longer declares are
  unregistered (``shortcutNames`` on the component); the shell touches no other component.
* The owner of the service name changes (``kglobalacceld`` or KWin restarted): everything is
  registered again. A stop makes every action inactive (``setInactive``), keeping the component and
  the user's keys.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from tess_shell.schema.keys import Chord
from tess_shell.services.api import ServiceError
from tess_shell.services.bus import Bus, MatchKey, ServiceThread, Unsubscribe

COMPONENT = "tesserae-shell"
COMPONENT_FRIENDLY = "Tesserae Shell"
SERVICE = "org.kde.kglobalaccel"
SERVICE_PATH = "/kglobalaccel"
SERVICE_INTERFACE = "org.kde.KGlobalAccel"
COMPONENT_INTERFACE = "org.kde.kglobalaccel.Component"
SET_PRESENT = 2  # SetShortcutFlag: the action is present (this application owns it now)
NO_AUTOLOADING = 4  # never sent: it would drop the key the user saved
IS_DEFAULT = 8  # the keys of the call are the defaults
STOP_TIMEOUT = 1.0  # seconds the stop sequence gives the service (Shell Start and Stop)
SAMPLES = 512  # presses whose handling time is kept (``callback_ns``)


@dataclass(frozen=True, slots=True)
class Action:
    """One action the shell declares. ``id`` is what the desktop sees (``Toggle_Launcher``) and
    ``friendly`` its text; ``kind`` is ``fixed``, ``toggle``, ``show``, ``hide`` or ``handler``;
    ``target`` a surface's Name or the fixed action's name. ``keys`` are the keys to register: empty
    for an action declared with no key, or whose key is shared with another action of the shell
    (neither gets it). ``handler`` is what a ``handler`` entry runs (opaque here) and ``where`` the
    ``file:line:column`` of the declaration, for the messages; neither takes part in the comparison
    that decides whether the action is registered again."""

    id: str
    friendly: str
    kind: str
    target: str
    keys: tuple[Chord, ...] = ()
    handler: Any = field(default=None, compare=False)
    where: str = field(default="", compare=False)


def friendly_text(name: str) -> str:
    """``Toggle_Launcher`` as ``Toggle Launcher``."""
    return name.replace("_", " ")


def _flatten(keys: Any) -> list[int]:
    """The key codes of the ``a(ai)`` the service answers with (``[[ [codes] ], ...]``)."""
    found: list[int] = []
    for struct in keys or ():
        for sequence in struct:
            found.extend(int(k) for k in sequence if k)
    return found


class ShortcutService:
    """One per shell. ``press(action)`` is called on the loop thread (through ``call_soon``) for
    each key press of an action the shell declared."""

    def __init__(
        self,
        service: ServiceThread,
        call_soon: Callable[[Callable[[], None]], None],
        press: Callable[[Action], None],
    ) -> None:
        self._service = service
        self._call_soon = call_soon
        self._press = press
        self._desired: dict[str, Action] = {}
        self._enabled = True
        self._started = False
        self._registered: dict[str, Action] = {}  # what the service holds now, by id
        self._failed: dict[str, Action] = {}  # actions the service refused: not tried again
        self._attached = False  # the service has an owner and the shell is registered with it
        self._cleaned = False  # the stale actions of the component were removed
        self._missing_said = False
        self._unwatch: Unsubscribe | None = None
        self._unpress: Unsubscribe | None = None
        self._unchanged: Unsubscribe | None = None
        self._path: str | None = None
        self._lock: asyncio.Lock | None = None
        self._accepting = False  # presses are taken between the end of start and the stop
        self._unknown: set[str] = set()
        self._off_said = False
        # what the tests read
        self.callback_ns: deque[int] = deque(maxlen=SAMPLES)  # time spent on each press, ns
        self.keys_now: dict[str, tuple[int, ...]] = {}  # keys the service reports for our actions
        self.registrations = 0  # actions registered (doRegister calls that went through)
        self.presses = 0  # presses handed to the loop

    @property
    def bus(self) -> Bus:
        return self._service.session

    @property
    def registered(self) -> frozenset[str]:
        """The ids of the actions registered with the service now."""
        return frozenset(self._registered)

    @property
    def attached(self) -> bool:
        return self._attached

    # -- the API (any thread) ---------------------------------------------------------------------

    async def start(self, actions: Sequence[Action], enabled: bool) -> None:
        """Service thread (the shell awaits it before the surfaces are shown): register the
        actions, subscribe, and begin to take presses. Never raises: a missing service is one
        warning and no shortcuts."""
        self._lock = asyncio.Lock()
        self._desired = {a.id: a for a in actions}
        self._enabled = enabled
        self._started = True
        await self._sync()
        self._accepting = True

    def update(self, actions: Sequence[Action], enabled: bool) -> None:
        """Any thread (the reload): bring the registrations to ``actions``. A new action is
        registered, a changed key replaced, a removed action unregistered, an unchanged one left
        alone; ``enabled`` false makes every action inactive and drops the subscriptions."""
        batch = tuple(actions)
        self._service.post(lambda: self._update(batch, enabled))

    def begin_stop(self) -> None:
        """Any thread: from now on a press is dropped (the shell is stopping)."""
        self._accepting = False

    async def stop(self) -> None:
        """Service thread, at most ``STOP_TIMEOUT`` seconds: make every action inactive (the
        component and the user's keys stay) and drop the subscriptions."""
        self._accepting = False
        self._started = False
        try:
            await asyncio.wait_for(self._stop(), STOP_TIMEOUT)
        except (TimeoutError, ServiceError) as exc:
            logger.debug(f"shortcuts: stopping did not go through ({exc!r})")
        self._drop_subscriptions()

    # -- the service thread -----------------------------------------------------------------------

    def _update(self, actions: Sequence[Action], enabled: bool) -> None:
        if not self._started:
            return
        self._desired = {a.id: a for a in actions}
        self._enabled = enabled
        task = asyncio.ensure_future(self._sync())
        task.add_done_callback(self._done)

    @staticmethod
    def _done(task: asyncio.Future[None]) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.opt(exception=task.exception()).error("shortcuts: a task failed")

    async def _sync(self) -> None:
        """Make the service's registrations the desired ones. One at a time: an owner change and a
        reload can come together."""
        assert self._lock is not None
        async with self._lock:
            if not self._started:
                return
            if not self._enabled:
                await self._detach()
                return
            self._off_said = False
            if not await self._attach():
                return
            await self._reconcile()

    async def _attach(self) -> bool:
        """Follow the service's name, and say if it has an owner."""
        if self._unwatch is None:
            try:
                self._unwatch = await self.bus.watch(SERVICE, self._owner_changed)
            except ServiceError as exc:
                logger.warning(
                    f"shortcuts: the session bus is not reachable ({exc}): no global keys; the "
                    "commands still work"
                )
                return False
        if self.bus.owner(SERVICE) is None:
            self._attached = False
            if not self._missing_said:
                self._missing_said = True
                logger.warning(
                    f"shortcuts: no {SERVICE} on the session bus: no global keys; the shell runs "
                    "and `tesserae-shell toggle <name>` still works"
                )
            return False
        self._missing_said = False
        self._attached = True
        return True

    async def _detach(self) -> None:
        """``Global_Shortcuts`` is false: every action inactive (the user's keys stay), no
        subscription, no further call."""
        if self._registered and self._attached:
            await self._inactivate()
        self._registered.clear()
        self._cleaned = False
        self._drop_subscriptions()
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        self._attached = False
        if not self._off_said:
            self._off_said = True
            logger.info("shortcuts: Global_Shortcuts is false: nothing is registered")

    def _drop_subscriptions(self) -> None:
        if self._unpress is not None:
            self._unpress()
            self._unpress = None
        if self._unchanged is not None:
            self._unchanged()
            self._unchanged = None
        self._path = None

    async def _stop(self) -> None:
        if self._attached and self._registered and self.bus.owner(SERVICE) is not None:
            await self._inactivate()
        self._registered.clear()
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None

    async def _inactivate(self) -> None:
        for action in list(self._registered.values()):
            try:
                await self._call("setInactive", "as", [self._ids(action)])
            except ServiceError as exc:
                logger.debug(f"shortcuts: setInactive {action.id} did not go through ({exc})")
                break  # the service is gone or slow: the rest would fail the same way

    def _owner_changed(self, old: str | None, new: str | None) -> None:
        """The service left, came, or was replaced: what it knew of the shell is gone (its
        ``present`` flags at least), so everything is registered again once it has an owner."""
        if not self._started or not self._enabled:
            return
        self._registered.clear()
        self._failed.clear()
        self._cleaned = False
        self._drop_subscriptions()
        if new is None:
            self._attached = False
            logger.info(f"shortcuts: {SERVICE} left the session bus")
            return
        self._missing_said = False
        logger.info(f"shortcuts: {SERVICE} is back: registering again")
        task = asyncio.ensure_future(self._sync())
        task.add_done_callback(self._done)

    # -- registration -----------------------------------------------------------------------------

    @staticmethod
    def _ids(action: Action) -> list[str]:
        return [COMPONENT, action.id, COMPONENT_FRIENDLY, action.friendly]

    @staticmethod
    def _sequences(keys: Sequence[Chord]) -> list[list[list[int]]]:
        """The ``a(ai)`` of the keys: one key sequence of one key each."""
        return [[[chord.qt]] for chord in keys]

    async def _call(
        self, member: str, signature: str, body: Sequence[Any], path: str = SERVICE_PATH
    ) -> list[Any]:
        interface = SERVICE_INTERFACE if path == SERVICE_PATH else COMPONENT_INTERFACE
        return await self.bus.call(SERVICE, path, interface, member, signature, body)

    async def _reconcile(self) -> None:
        desired = self._desired
        # removed, or the key changed: out (a changed key is registered anew below)
        for id_, have in list(self._registered.items()):
            want = desired.get(id_)
            if want is not None and want.keys == have.keys:
                self._registered[id_] = want  # the handler may have changed: nothing is sent
                continue
            try:
                await self._call("unregister", "ss", [COMPONENT, id_])
            except ServiceError as exc:
                logger.warning(f"shortcuts: could not unregister {id_} ({exc})")
            del self._registered[id_]
            logger.info(f"shortcuts: {id_} {'removed' if want is None else 'changed'}")
        for id_ in [i for i in self._failed if i not in desired or self._failed[i] != desired[i]]:
            del self._failed[id_]
        for id_, action in desired.items():
            if id_ in self._registered or id_ in self._failed:
                continue
            if await self._register(action):
                self._registered[id_] = action
            else:
                self._failed[id_] = action
            if not self._attached:  # the service left meanwhile
                return
        await self._component()

    async def _register(self, action: Action) -> bool:
        """``doRegister`` and the two ``setShortcutKeys`` of one action. A failure skips this
        action only."""
        ids = self._ids(action)
        try:
            await self._call("doRegister", "as", [ids])
            sequences = self._sequences(action.keys)
            got = await self._call("setShortcutKeys", "asa(ai)u", [ids, sequences, SET_PRESENT])
            set_keys = _flatten(got[0] if got else [])
            await self._call("setShortcutKeys", "asa(ai)u", [ids, sequences, IS_DEFAULT])
        except ServiceError as exc:
            logger.warning(f"shortcuts: could not register {action.id} ({exc}); it is skipped")
            return False
        self.registrations += 1
        self.keys_now[action.id] = tuple(set_keys)
        if action.keys and not set_keys:
            keys = ", ".join(chord.text for chord in action.keys)
            logger.warning(
                f"shortcuts: {action.id}: the key {keys} is taken by the desktop or another "
                "application: the action is registered with no key (choose one in System "
                "Settings)"
            )
        return True

    async def _component(self) -> None:
        """The component's object path (asked, never derived), the actions it holds that the shell
        no longer declares, and the two signals."""
        if self._path is not None and self._cleaned:
            return
        try:
            reply = await self._call("getComponent", "s", [COMPONENT])
        except ServiceError as exc:
            logger.debug(f"shortcuts: no component yet ({exc})")
            return
        path = str(reply[0])
        if not self._cleaned:
            try:
                listed = await self.bus.call(SERVICE, path, COMPONENT_INTERFACE, "shortcutNames")
                names = listed[0]
            except ServiceError as exc:
                logger.debug(f"shortcuts: could not list the component's actions ({exc})")
                names = []
            for name in names:
                if name in self._desired:
                    continue
                try:
                    await self._call("unregister", "ss", [COMPONENT, str(name)])
                except ServiceError as exc:
                    logger.warning(f"shortcuts: could not remove the stale action {name} ({exc})")
                else:
                    logger.info(f"shortcuts: removed {name}, which is no longer declared")
            self._cleaned = True
        if self._path != path or self._unpress is None:
            if self._unpress is not None:
                self._unpress()
            self._path = path
            self._unpress = await self.bus.subscribe(
                MatchKey(SERVICE, path, COMPONENT_INTERFACE, "globalShortcutPressed"),
                self._pressed,
            )
        if self._unchanged is None:
            self._unchanged = await self.bus.subscribe(
                MatchKey(SERVICE, SERVICE_PATH, SERVICE_INTERFACE, "yourShortcutsChanged"),
                self._keys_changed,
            )

    # -- signals (service thread) -----------------------------------------------------------------

    def _pressed(self, message: Any) -> None:
        """``globalShortcutPressed(component, action, timestamp)``: look the action up and hand it
        to the loop. Nothing else happens on this thread."""
        started = time.perf_counter_ns()
        try:
            component, name = str(message.body[0]), str(message.body[1])
            if component != COMPONENT:
                return
            if not self._accepting:
                logger.debug(f"shortcuts: {name} pressed while the shell is starting or stopping")
                return
            action = self._desired.get(name)
            if action is None:
                if name not in self._unknown:
                    self._unknown.add(name)
                    logger.debug(f"shortcuts: a press of {name}, which the shell does not declare")
                return
            self.presses += 1
            self._call_soon(lambda: self._run(action))
        finally:
            self.callback_ns.append(time.perf_counter_ns() - started)

    def _run(self, action: Action) -> None:
        """Loop thread."""
        try:
            self._press(action)
        except Exception:
            logger.opt(exception=True).error(f"shortcuts: {action.id} raised")

    def _keys_changed(self, message: Any) -> None:
        """``yourShortcutsChanged(actionId, newKeys)``: the user changed a key of ours in System
        Settings. The service uses it at the next press; this only remembers it."""
        try:
            ids, keys = message.body[0], message.body[1]
            if len(ids) < 2 or ids[0] != COMPONENT:
                return
            codes = tuple(_flatten(keys))
        except (IndexError, TypeError):
            return
        self.keys_now[str(ids[1])] = codes
        logger.debug(f"shortcuts: the key of {ids[1]} was changed in the desktop's settings")
