"""The Workspaces: KWin's virtual desktops as a row of buttons (Workspaces Module). It reads
``org.kde.KWin`` ``/VirtualDesktopManager`` once, then follows ``PropertiesChanged`` and the three
desktop signals: no timer, no thread. The callbacks run on the ``dbus`` thread; a click sets the
``current`` property through the layer and returns at once. One instance serves every use.

Keys sent: ``desktops`` (a list of records ``id``, ``number`` (1-based), ``name``, ``label``,
``current``), ``current`` (an id) and ``ready`` (a valid list was read). ``available`` is the
layer's: true while KWin is on the session bus. A layout shows itself with
``If {{ available and ready }}``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

KWIN = "org.kde.KWin"
PATH = "/VirtualDesktopManager"
INTERFACE = "org.kde.KWin.VirtualDesktopManager"
# On the maintainer's KWin the mark did not follow Ctrl+F2 (2026-11-13): the properties say
# ``emits-change`` but ``currentChanged`` and ``countChanged`` are signals too, and they are what
# moves the mark here, whether or not ``PropertiesChanged`` also arrives.
SIGNALS = (
    "desktopCreated",
    "desktopRemoved",
    "desktopDataChanged",
    "currentChanged",
    "countChanged",
)


def records(raw: object, current: str) -> list[dict[str, Any]]:
    """The desktop list as it arrives: ``a(uss)`` or ``a(iss)`` (a number, an id, a name; the
    number is not used: the position in the list is). Raises ``ValueError`` for any other shape, an
    empty list or a repeated id."""
    if not isinstance(raw, Sequence) or isinstance(raw, str) or not raw:
        raise ValueError("expected a non-empty list of (number, id, name)")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, item in enumerate(raw):
        ok = (
            isinstance(item, Sequence)
            and not isinstance(item, str)
            and len(item) == 3
            and isinstance(item[0], int)
            and not isinstance(item[0], bool)
            and isinstance(item[1], str)
            and isinstance(item[2], str)
            and item[1] != ""
        )
        if not ok:
            raise ValueError(f"entry {position} is not (number, id, name): {item!r}")
        _, desktop_id, name = item
        if desktop_id in seen:
            raise ValueError(f"the id {desktop_id!r} is listed twice")
        seen.add(desktop_id)
        number = position + 1
        out.append(
            {
                "id": desktop_id,
                "number": number,
                "name": name,
                "label": name if name else str(number),  # an empty name shows the number
                "current": desktop_id == current,
            }
        )
    return out


class Workspaces(Module):
    def __init__(self) -> None:
        self.props: dict[str, Any] = {}
        self.sent: dict[str, Any] = {}
        self.ids: frozenset[str] = frozenset()
        self.refused: set[object] = set()
        self.warned: set[str] = set()
        self.pending = False
        self.good: Any = None  # the last desktop list that was readable

    def start(self) -> None:
        # defaults, so a layout reading any key has a value before KWin has answered
        self.publish({"desktops": [], "current": "", "ready": False})
        self.bus = self.ctx.dbus.session()
        self.vdm = self.bus.proxy(KWIN, PATH, INTERFACE)
        self.vdm.on_property_changed(self.changed)
        for member in SIGNALS:
            self.vdm.on_signal(member, self.signalled)

    def use_added(self, use: UseRecord) -> None:
        for key, value in self.sent.items():
            self.ctx.send(key, value, use=use)

    # -- on the dbus thread -------------------------------------------------------------------

    def changed(self, values: Mapping[str, Any]) -> None:
        self.props.update(values)
        current = self.props.get("current")
        current = current if isinstance(current, str) else ""
        update: dict[str, Any] = {"current": current}
        if "desktops" in self.props:
            try:
                listed = records(self.props["desktops"], current)
                self.good = self.props["desktops"]
            except ValueError as exc:
                self.warn_once(f"the property desktops is not understood ({exc}); keeping the last")
                self.props["desktops"] = self.good  # the last list that was readable, if any
                listed = records(self.good, current) if self.good is not None else []
            if listed:
                self.ids = frozenset(d["id"] for d in listed)
                update["desktops"] = listed
                update["ready"] = True
        self.publish(update)

    def signalled(self, *body: object) -> None:
        """A desktop was created, removed or changed, or the current one changed: read the list and
        ``current`` again, once for a burst."""
        if not self.pending:
            self.pending = True
            self.bus.run(self.refresh())

    async def refresh(self) -> None:
        self.pending = False
        try:
            desktops = await self.vdm.get("desktops", fresh=True)
            current = await self.vdm.get("current", fresh=True)
        except Exception as exc:  # KWin left: the layer has said so and hides the module
            self.ctx.log.debug(f"could not read the desktops ({exc})")
            return
        self.changed({"desktops": desktops, "current": current})

    def publish(self, values: Mapping[str, Any]) -> None:
        """Send what changed since the last send: a refresh that changes nothing sends nothing."""
        for key, value in values.items():
            if key not in self.sent or self.sent[key] != value:
                self.sent[key] = value
                self.ctx.send(key, value)

    def warn_once(self, message: str) -> None:
        if message not in self.warned:
            self.warned.add(message)
            self.ctx.log.warning(message)

    # -- on the loop thread -------------------------------------------------------------------

    @action
    def switch(self, event: Any) -> None:
        """A click on a desktop's button: set KWin's ``current`` to its id. The call runs on the
        ``dbus`` thread; the mark moves when KWin's ``PropertiesChanged`` says so."""
        target = event.args.get("Id")
        if not isinstance(target, str) or target not in self.ids:
            if target not in self.refused:
                self.refused.add(target)
                self.ctx.log.warning(f"switch: {target!r} is not one of the desktops; ignored")
            return
        self.bus.run(self.vdm.set("current", target, "s")).add_done_callback(self.switched)

    def switched(self, future: Future[None]) -> None:
        if future.cancelled():
            return
        problem = future.exception()
        if problem is not None:
            self.warn_once(f"switching the desktop failed: {problem}")
