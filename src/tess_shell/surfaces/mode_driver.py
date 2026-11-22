"""What shortcut mode does to the shell's surfaces (Focus and Keyboard > Shortcut Mode).

:class:`~tess_shell.surfaces.mode.ShortcutMode` is the rules; this is what a change of it means for
the windows. When the state changes:

* the surface that has the focus asks for the keyboard (tre's ``keyboard`` window property): the
  mode's keys then arrive on it as key events. The word is ``EXCLUSIVE`` by default: on Wayland a
  layer surface cannot take the keyboard by asking for ``ON_DEMAND`` (the compositor gives that to a
  click), and the mode starts from a key. ``Debug { Mode_Keyboard: ON_DEMAND }`` is the choice for a
  compositor that hands focus over after a global key. When the mode moves on, or ends, the surface
  has the word it was written with again;
* a Frame that is the surface in the mode shows every one of its peeks (``Frames.hold_peeks``);
* the focus ring starts on the first Tab stop of the surface that has the focus;
* the change is announced as a polite status.

The keys of the mode arrive as key events on the windows. They are the ones ``Shortcuts { }`` names
for the five actions (the same keys the desktop's shortcut service may also carry), and Escape,
which leaves the mode when the Frame is the surface in it. Nothing is read from a window the mode
does not hold.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from loguru import logger

from tess_shell.schema.findings import nearest
from tess_shell.schema.keys import Chord, parse_chord
from tess_shell.schema.model import ShellDef
from tess_shell.surfaces.mode import OFF, ModeState, ShortcutMode, chord_of

if TYPE_CHECKING:
    from tess_shell.binder.build import View
    from tess_shell.surfaces.manager import SurfaceManager

ESCAPE = parse_chord("Escape")
KEYBOARD_WAIT_MS = 1500  # how long the compositor has to hand the keyboard over


def surface_flags(shell: ShellDef, names: Sequence[str]) -> dict[str, bool]:
    """``Shortcut_Mode`` as the files write it, for the surfaces in ``names`` (the focus order): in
    document order, so that the first one written true is the first one in the dict."""
    found: list[tuple[int, int, str]] = []
    for monitor in shell.monitors:
        for surface in monitor.surfaces:
            if surface.shortcut_mode is not None:
                at = surface.shortcut_mode
                found.append((at.line, at.column, surface.name))
        for frame in monitor.frames:
            if frame.shortcut_mode is not None:
                found.append((frame.shortcut_mode.line, frame.shortcut_mode.column, frame.name))
            for side, edge in frame.edges.items():
                if edge.shortcut_mode is not None:
                    found.append(
                        (edge.shortcut_mode.line, edge.shortcut_mode.column, f"{frame.name}.{side}")
                    )
    flags = {name: True for _, _, name in sorted(found) if name in names}
    flags.update({name: False for name in names if name not in flags})
    return flags


def lowest_surface(shell: ShellDef, order: Sequence[str]) -> str | None:
    """The lowest level of the shell: the first Frame; with no Frame, the first surface in Tab
    order (the Frame is what the mode starts with; a shell without one starts with a surface)."""
    for monitor in shell.monitors:
        for frame in monitor.frames:
            if frame.name in order:
                return frame.name
    return order[0] if order else None


class ModeDriver:
    """The shortcut mode of one surface manager."""

    def __init__(self, manager: SurfaceManager) -> None:
        self._m = manager
        self.machine = ShortcutMode(self._changed)
        self.keyboard = "EXCLUSIVE"  # the word the surface that has the focus is given
        self.keys: dict[Chord, str] = {}  # a key of the mode -> the fixed action it runs
        self.on_state: Callable[[ModeState], None] | None = None
        self.ready = False  # the windows exist: a change may be applied
        # on a real compositor (the app sets it): a surface that asked for the keyboard and was
        # not given it within ``KEYBOARD_WAIT_MS`` is one warning (Failure Modes). Headless there
        # is no compositor to give it, so a test would always warn.
        self.watch_focus = False
        # the windows that hold the keyboard for the mode, by id: (window, what it was written with)
        self._held: dict[int, tuple[Any, Callable[[], str]]] = {}
        self._status: dict[int, Any] = {}  # the status node of each window, by window id
        self._warned: set[str] = set()

    # -- what the files and the settings give ---------------------------------------------------

    def configure(self, shell: ShellDef | None) -> None:
        """The shell was planned (the start, a reload): the surfaces in Tab order, the lowest level
        and what the files write. Applies what that changes, and makes the windows of the surface
        that has the focus hold the keyboard again (a reload may have made new ones)."""
        order = self._m.focus_order
        if shell is None:
            self.machine.configure([], None, {})
        else:
            self.machine.configure(order, lowest_surface(shell, order), surface_flags(shell, order))
        if self.ready:
            self._apply(self.machine.state, self.machine.state)

    def start(self) -> None:
        """The windows exist (the end of ``build``): a surface written ``Shortcut_Mode: true`` has
        the mode from the start."""
        self.ready = True
        self._apply(OFF, self.machine.state)

    def set_keys(self, bindings: Mapping[Chord, str]) -> None:
        """The keys of the mode: ``Shortcuts { }`` names them, read again at every reload."""
        self.keys = dict(bindings)

    def set_keyboard(self, word: str) -> None:
        self.keyboard = word

    # -- the five actions (a global shortcut runs them through ``ShellCommands``) ---------------

    def actions(self) -> dict[str, Callable[[], None]]:
        """The five fixed actions of Focus and Keyboard, by name."""
        return {
            "Enter_Shortcut_Mode": self.enter,
            "Exit_Shortcut_Mode": self.exit,
            "Set_Shortcut_Mode": self.toggle,
            "Next_Focus": lambda: self.step(True),
            "Previous_Focus": lambda: self.step(False),
        }

    def enter(self) -> None:
        if not self.machine.enter():
            logger.warning("Enter_Shortcut_Mode: the shell has no surface to put in the mode")

    def exit(self) -> None:
        if not self.machine.exit():
            logger.debug("Exit_Shortcut_Mode: the shell is not in shortcut mode; nothing done")

    def toggle(self) -> None:
        if not self.machine.toggle_focused():
            logger.debug("Set_Shortcut_Mode: no surface has the focus; nothing done")

    def step(self, forward: bool) -> None:
        action = "Next_Focus" if forward else "Previous_Focus"
        if not self.machine.on:
            logger.debug(f"{action}: the shell is not in shortcut mode; nothing done")
        elif not self.machine.navigating:
            logger.debug(
                f"{action}: {self.machine.mode} is the surface in shortcut mode, so the keys of "
                "its blocks apply; nothing done"
            )
        elif self.machine.step(forward, self.usable) is None:
            logger.debug(f"{action}: no surface can take the focus; nothing done")

    def set_mode(self, name: str, value: bool, who: str = "Shortcut_Mode") -> bool:
        """``ctx.focus.set_mode``: ``Shortcut_Mode`` of the surface ``name``. ``False`` (and one
        error naming the nearest surfaces) when no surface has that name."""
        if self.machine.set_mode(name, value):
            return True
        close = nearest(name, self.machine.order)
        hint = (
            f"did you mean {', '.join(close)}?"
            if close
            else f"the surfaces: {', '.join(self.machine.order) or 'none'}"
        )
        logger.error(f"{who}: no surface named {name} ({hint})")
        return False

    def get_default(self) -> str | None:
        """The surface that starts with the focus when the mode is entered (``None``: the Frame)."""
        return self.machine.default

    def set_default(self, name: str | None, who: str = "the default focus") -> None:
        """``ctx.focus.default = name``. A name that is no surface is one error naming the nearest
        surfaces and changes nothing."""
        if name is not None and name not in self.machine.order:
            close = nearest(name, self.machine.order)
            hint = (
                f"did you mean {', '.join(close)}?"
                if close
                else f"the surfaces: {', '.join(self.machine.order) or 'none'}"
            )
            logger.error(f"{who}: no surface named {name} ({hint})")
            return
        self.machine.default = name

    # -- the surfaces ----------------------------------------------------------------------------

    def _target(self, name: str | None) -> tuple[Any, View | None, Callable[[], str] | None]:
        """The window that takes the keyboard for the surface ``name``, the view whose first Tab
        stop gets the ring and what the window was written with; ``(None, None, None)`` when the
        surface has no window now (a hidden Panel)."""
        if name is None:
            return None, None, None
        m = self._m
        for s in m.surfaces:
            if s.name == name and s.window is not None and not s.hidden and s.planned is not None:
                return s.window, s.view, lambda s=s: m._keyboard_word(s.planned, s.hidden)
        for st in m.frames.states.values():
            if st.painter is None:
                continue
            if st.plan.frame.name == name:
                return st.painter, None, lambda st=st: st.keyboard
            for host in st.hosts.values():
                if host.plan.kind == "strip" and f"{st.plan.frame.name}.{host.plan.side}" == name:
                    return st.painter, host.surface.view, lambda st=st: st.keyboard
        return None, None, None

    def usable(self, name: str) -> bool:
        return self._target(name)[0] is not None

    def holds(self, window: Any) -> bool:
        """Whether the mode has the keyboard of ``window``: its written ``Keyboard`` is not set
        while it does (a reload that sets it would take the keyboard from the mode)."""
        return id(window) in self._held

    def gone(self, name: str) -> None:
        """The surface ``name`` has no window now (a Panel was hidden, a window closed): the mode
        ends if it was the one in it, else the focus moves on if it had it."""
        remaining = [n for n in self.machine.order if n != name and self.usable(n)]
        self.machine.gone(name, remaining)

    def closed(self, name: str, window: Any) -> None:
        """The ``window`` of the surface ``name`` closed. A surface made again under its name (a
        reload that changed its layer) is not gone."""
        if window is not None:
            self._held.pop(id(window), None)
            self._status.pop(id(window), None)
        target = self._target(name)[0]
        if target is None or target is window:
            self.gone(name)

    # -- applying a change -----------------------------------------------------------------------

    def _frame_in(self, name: str | None) -> str | None:
        frames = {st.plan.frame.name for st in self._m.frames.states.values()}
        return name if name in frames else None

    def _changed(self, old: ModeState, new: ModeState) -> None:
        shown = f"mode {new.mode}, focus {new.focus}" if new.on else "off"
        logger.info(f"shortcut mode: {shown}")
        self._apply(old, new)
        if self.on_state is not None:
            self.on_state(new)

    def _apply(self, old: ModeState, new: ModeState) -> None:
        if not self.ready:
            return
        before, after = self._frame_in(old.mode), self._frame_in(new.mode)
        if before is not None and before != after:
            self._m.frames.hold_peeks(before, False)
        if after is not None:
            self._m.frames.hold_peeks(after, True)
        self._hold_keyboard(new)
        self._ring(new)
        if old != new:
            self._announce(old, new)

    def _hold_keyboard(self, new: ModeState) -> None:
        window, _, written = self._target(new.focus if new.on else None)
        for key in [k for k in self._held if window is None or k != id(window)]:
            held, restore = self._held.pop(key)
            self._give_back(held, restore)
        if window is None:
            if new.on:
                logger.warning(
                    f"shortcut mode: {new.focus} has no window to take the keyboard; "
                    "its keys do not arrive"
                )
            return
        assert written is not None
        word = self.keyboard.lower()
        if id(window) not in self._held:
            self._held[id(window)] = (window, written)
        try:
            if window.get("keyboard") != word:
                window.set(keyboard=word)
                logger.info(f"shortcut mode: {new.focus} takes the keyboard ({word})")
                if self.watch_focus and new.focus is not None:
                    self._expect_keyboard(window, new.focus, word)
        except (ValueError, RuntimeError) as exc:
            logger.warning(f"shortcut mode: {new.focus} cannot take the keyboard ({exc})")

    def _expect_keyboard(self, window: Any, name: str, word: str) -> None:
        """The compositor decides which layer surface has the keyboard. If ``name`` still has the
        focus of the mode and the OS has not made its window active when the wait is over, the mode
        keys do not arrive: one warning (Focus and Keyboard > Failure Modes)."""
        owner = name.partition(".")[0]  # a strip is in its Frame's window

        def check() -> None:
            state = self.machine.state
            if not state.on or state.focus != name or self._m.focused == owner:
                return
            if name in self._warned:
                return
            self._warned.add(name)
            logger.warning(
                f"shortcut mode: the compositor did not give {name} the keyboard ({word}) within "
                f"{KEYBOARD_WAIT_MS} ms, so the keys of the mode do not arrive; the pointer "
                "still reaches the shell (Debug { Mode_Keyboard } is the setting to try)"
            )

        try:
            window.after(KEYBOARD_WAIT_MS, check)
        except ValueError, RuntimeError:
            logger.debug("shortcut mode: the keyboard wait could not be set", exc_info=True)

    @staticmethod
    def _give_back(window: Any, written: Callable[[], str]) -> None:
        try:
            word = written()
            if window.get("keyboard") != word:
                window.set(keyboard=word)
                logger.info(f"shortcut mode: a window has its keyboard back ({word})")
        except ValueError, RuntimeError:  # the window closed with its output: nothing to give
            logger.debug("shortcut mode: a window was already gone", exc_info=True)

    def _ring(self, new: ModeState) -> None:
        if not new.on or new.focus is None:
            return
        view = self._target(new.focus)[1]
        if view is not None and not view.disposed:
            view.focus_first()

    # -- the status (Accessibility: entering and leaving the mode is a polite status) ------------

    def _announce(self, old: ModeState, new: ModeState) -> None:
        if new.on:
            text = f"Shortcut mode on, {new.focus}" if not old.on else f"{new.focus}"
            window = self._target(new.focus)[0]
        else:
            text, window = "Shortcut mode off", self._target(old.focus)[0]
        if window is None:
            return
        node = self._status.get(id(window))
        try:
            if node is None:
                node = window.create(
                    "text",
                    text="",
                    live="polite",
                    position="absolute",
                    left=0,
                    top=0,
                    width=1,
                    height=1,
                    opacity=0,
                )
                window.root.add_child(node)
                self._status[id(window)] = node
            node.set(text=text)
        except ValueError, RuntimeError:  # the window is gone
            self._status.pop(id(window), None)
            logger.debug("shortcut mode: the status could not be set", exc_info=True)

    def _landmark(self, event: Any) -> bool:
        """F6 and Shift+F6 move between the shell's surfaces (Keyboard Navigation: landmark
        cycling, TSH-015) from a surface that has the keyboard: the mode is entered if it is not on,
        and the focus goes to the next surface in ``Focus_Order`` (Shift: the previous one). In the
        mode they are Next_Focus and Previous_Focus. Ctrl, Alt and Meta with F6 are not ours. True
        when the key was used."""
        if (
            getattr(event, "ctrl", False)
            or getattr(event, "alt", False)
            or getattr(event, "meta", False)
        ):
            return False
        forward = not getattr(event, "shift", False)
        if not self.machine.on:
            self.enter()
            if not self.machine.on:
                return False
        if self.machine.navigating:
            self.step(forward)
        stop = getattr(event, "stop", None)
        if callable(stop):
            stop()
        return True

    # -- the keys that arrive on a window ----------------------------------------------------------

    def on_key(self, event: Any) -> bool:
        """A key event on a window of the shell. While the shell is in shortcut mode, the keys the
        mode knows run their action; ``True`` when it did (the event does not go on). Escape leaves
        the mode when the Frame (the lowest level) is the surface in it; in another surface's own
        mode Escape is that surface's."""
        if getattr(event, "key", None) == "f6" and self._landmark(event):
            return True
        if not self.machine.on:
            return False
        chord = chord_of(
            getattr(event, "key", None),
            bool(getattr(event, "ctrl", False)),
            bool(getattr(event, "alt", False)),
            bool(getattr(event, "shift", False)),
            bool(getattr(event, "meta", False)),
        )
        if chord is None:
            return False
        action = self.keys.get(chord)
        if action is None and chord == ESCAPE and self.machine.navigating:
            action = "Exit_Shortcut_Mode"
        if action is None:
            return False
        if action in ("Next_Focus", "Previous_Focus") and not self.machine.navigating:
            return False  # a surface's own mode: its Tab and arrows are the surface's, not ours
        hook = self.actions().get(action)
        if hook is None:
            return False
        logger.debug(f"shortcut mode: key {chord} -> {action}")
        hook()
        stop = getattr(event, "stop", None)
        if callable(stop):
            stop()
        return True
