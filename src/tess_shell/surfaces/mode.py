"""Shortcut mode as a state machine (Focus and Keyboard > Shortcut Mode).

Pure: no tre, no D-Bus, no clock. The surface manager holds one :class:`ShortcutMode`, feeds it the
shell's surfaces in Tab order (``surfaces/focus.py``) and applies each change it announces
(keyboard focus, the Frame's peeks, the focus ring).

The state is two names:

* ``mode``: the one surface whose ``Shortcut_Mode`` is true, or ``None`` when the shell is not in
  shortcut mode. Never two (rule 1).
* ``focus``: the surface that has the shell's focus inside the mode (the one that takes the
  keyboard). It starts on the Frame, or the surface a developer chose (rule 4), moves with
  ``Next_Focus`` and ``Previous_Focus`` while the Frame is in the mode (rule 5), and is the
  surface ``Set_Shortcut_Mode`` acts on (rule 6).

The maintainer's rules, 2026-11-10:

1. At most one ``Shortcut_Mode: true`` exists; setting one true sets every other false.
2. Setting a surface false when no other is true turns shortcut mode off for the whole shell.
3. ``Enter_Shortcut_Mode`` sets the lowest level (the Frame) true; ``Exit_Shortcut_Mode`` sets every
   one false and leaves the mode.
4. The Frame has the initial focus; a developer may name another surface.
5. In the mode, ``Next_Focus`` and ``Previous_Focus`` move focus through the surfaces in
   ``Tab_Index`` order.
6. ``Set_Shortcut_Mode`` toggles ``Shortcut_Mode`` of the focused surface: false to true turns the
   Frame's off (rule 1); true to false turns the whole mode off (rule 2), it does not go back to
   the Frame.

Rule 7 (every peek of a Frame in the mode shows) is the manager's.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from tess_shell.schema.keys import MODIFIER_ORDER, Chord, ChordError, parse_chord
from tess_shell.surfaces.focus import next_surface


@dataclass(frozen=True, slots=True)
class ModeState:
    """Where the mode is: the surface in shortcut mode and the surface that has focus, both
    ``None`` while the shell is not in the mode."""

    mode: str | None = None
    focus: str | None = None

    @property
    def on(self) -> bool:
        return self.mode is not None


OFF = ModeState()


def chord_of(
    key: str | None, ctrl: bool = False, alt: bool = False, shift: bool = False, meta: bool = False
) -> Chord | None:
    """The key press a tre key event is, as a :class:`Chord` (the form ``Shortcuts`` writes): tre's
    snake_case names (``arrow_left``, ``page_up``, ``f5``, ``enter``) and the character a key
    produces (``a``, ``A`` with Shift) become the canonical key names. ``None`` for a key that has
    no name there (a lone modifier, a dead key, a symbol that needs Shift to type)."""
    if not key:
        return None
    if len(key) == 1:
        name = {" ": "Space", "+": "Plus"}.get(key, key.upper())
    else:
        name = key.removeprefix("arrow_").replace("_", "")
    held = [m for m, on in zip(MODIFIER_ORDER, (ctrl, alt, shift, meta), strict=True) if on]
    try:
        return parse_chord("+".join([*held, name]))
    except ChordError:
        return None


class ShortcutMode:
    """The mode of one shell. ``on_change(old, new)`` is called after every change of the state (not
    when a call leaves it as it was). A call with a name that is no surface does nothing and says
    so by returning ``False``."""

    def __init__(self, on_change: Callable[[ModeState, ModeState], None] | None = None) -> None:
        self.on_change = on_change
        self.state = OFF
        self.order: list[str] = []  # every surface, in Tab order
        self.lowest: str | None = None  # the lowest level: the first Frame, else the first surface
        self.default: str | None = None  # the surface that starts with focus (rule 4)
        self.written: dict[str, bool] = {}  # ``Shortcut_Mode`` as the files write it, by Name

    # -- what the shell holds ---------------------------------------------------------------------

    @property
    def mode(self) -> str | None:
        return self.state.mode

    @property
    def focus(self) -> str | None:
        return self.state.focus

    @property
    def on(self) -> bool:
        return self.state.on

    @property
    def navigating(self) -> bool:
        """Whether ``Next_Focus`` and ``Previous_Focus`` move between surfaces: the lowest level
        (the Frame) is the one in the mode. In a surface's own mode they move inside it."""
        return self.state.mode is not None and self.state.mode == self.lowest

    def _set(self, mode: str | None, focus: str | None) -> bool:
        new = ModeState(mode, focus) if mode is not None else OFF
        old = self.state
        if new == old:
            return False
        self.state = new
        if self.on_change is not None:
            self.on_change(old, new)
        return True

    # -- the actions ------------------------------------------------------------------------------

    def enter(self) -> bool:
        """``Enter_Shortcut_Mode`` (rule 3): the lowest level is in the mode and the focus is on the
        default surface, or the lowest level (rule 4). Pressed inside a surface's own mode, it goes
        back to the lowest level (Focus and Keyboard > Shortcut Mode, the consequence note)."""
        if self.lowest is None:
            return False
        focus = self.default if self.default in self.order else self.lowest
        self._set(self.lowest, focus)
        return True

    def exit(self) -> bool:
        """``Exit_Shortcut_Mode``: every ``Shortcut_Mode`` false, the mode left. ``False`` when the
        shell was not in the mode."""
        return self._set(None, None)

    def set_mode(self, name: str, value: bool) -> bool:
        """Set ``Shortcut_Mode`` of ``name`` (rules 1 and 2, and what ``ctx.focus.set_mode`` does).
        True: the surface is the one in the mode and has the focus. False: if it is the one in the
        mode the whole shell leaves the mode; if it was false already nothing happens. ``False``
        when ``name`` is no surface."""
        if name not in self.order:
            return False
        if value:
            self._set(name, name)
        elif self.state.mode == name:
            self._set(None, None)
        return True

    def toggle_focused(self) -> bool:
        """``Set_Shortcut_Mode`` (rule 6): toggle ``Shortcut_Mode`` of the focused surface.
        ``False`` when no surface has focus (the shell is not in the mode)."""
        focus = self.state.focus
        if focus is None:
            return False
        return self.set_mode(focus, self.state.mode != focus)

    def step(self, forward: bool, usable: Callable[[str], bool] = lambda name: True) -> str | None:
        """``Next_Focus`` (``forward``) or ``Previous_Focus`` (rule 5): the surface after or before
        the focused one in Tab order that is ``usable`` (a hidden Panel is not), going round.
        ``None`` when the Frame is not the one in the mode (nothing moves between surfaces then),
        or no surface can take the focus."""
        if not self.navigating or not self.order:
            return None
        count, focus = len(self.order), self.state.focus
        at = self.order.index(focus) if focus in self.order else (-1 if forward else 0)
        for _ in range(count):
            at = (at + (1 if forward else -1)) % count
            if usable(self.order[at]):
                self._set(self.state.mode, self.order[at])
                return self.order[at]
        return None

    # -- what happens to the surfaces -------------------------------------------------------------

    def gone(self, name: str, remaining: Sequence[str]) -> None:
        """The surface ``name`` closed; ``remaining`` are the surfaces still open. If it was the one
        in the mode, the mode ends (rule 2); if it only had the focus, the focus goes to the next
        surface in Tab order, or the mode ends when none is left (Failure Modes)."""
        mode, focus = self.state.mode, self.state.focus
        if mode is None or name not in (mode, focus):
            return
        if mode == name:
            self._set(None, None)
            return
        target = next_surface([n for n in self.order if n == name or n in remaining], name)
        if target is None:
            self._set(None, None)
        else:
            self._set(mode, target)

    # -- the files --------------------------------------------------------------------------------

    def configure(
        self,
        order: Sequence[str],
        lowest: str | None,
        written: Mapping[str, bool],
    ) -> None:
        """The shell was planned (at load) or planned again (a hot reload): ``order`` is every
        surface in Tab order, ``lowest`` the lowest level, ``written`` the ``Shortcut_Mode`` each
        surface writes, in document order.

        The first plan makes the surface the files write true the one in the mode (the first of
        them when several do: the loader warned). A later plan changes only what the files
        changed: a surface newly true takes the mode (rule 1), a surface newly false leaves it when
        it had it (rule 2); a surface the files did not touch keeps what the run made of it. A
        mode on a surface that is gone from the files ends.
        """
        first = not self.written and not self.order
        before, previous = self.written, self.order
        self.order, self.lowest = list(order), lowest
        self.written = dict(written)
        if self.default is not None and self.default not in self.order:
            self.default = None
        mode, focus = self.state.mode, self.state.focus
        if mode is not None and mode not in self.order:
            self._set(None, None)
        elif focus is not None and focus not in self.order:
            alive = [n for n in previous if n == focus or n in self.order]
            target = next_surface(alive, focus)
            self._set(mode, target) if target is not None else self._set(None, None)
        newly = [n for n, v in written.items() if v and not before.get(n, False)]
        if first:
            newly = [n for n, v in written.items() if v][:1]
        if newly:
            self.set_mode(newly[0], True)
            return
        for name, value in before.items():
            if value and not written.get(name, False) and self.state.mode == name:
                self.set_mode(name, False)
