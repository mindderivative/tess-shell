"""``Auto_Hide`` of a Bar (Auto Hide, Bar > Auto-hide; decided 2026-10-27).

The pointer leaving a Bar starts a timer of ``Auto_Hide_Delay`` ms; when it ends the Bar slides out
past its screen edge (the edge margin runs to ``STRIP - thickness``) and then gives its space back
(``exclusive_zone`` 0), so windows reflow once. What stays on the screen is a ``STRIP`` px hover
strip that takes the pointer: touching it brings the Bar back (the zone first, then the slide in).
A Bar that is in use does not hide: one that holds the keyboard, has a Popup of its own open, or
is in a shell that is in shortcut mode stays; the delay is looked at again each time it runs out.

A Bar that the user hid (``Hide``, ``Visible: false``) is not this: it has no strip and only a
command shows it. ``Surface.auto_out`` is True from the start of the slide out to the start of
the slide in.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger

from tess_shell.schema.model import BarDef

if TYPE_CHECKING:
    from tess_shell.surfaces.manager import Surface, SurfaceManager

STRIP = 1  # px of the Bar left on the screen edge while it is out: the pointer's way back
FADE_EASE_OUT = (0.4, 0.0, 1.0, 1.0)  # the easing of a Bar going out
FADE_EASE_IN = (0.0, 0.0, 0.2, 1.0)  # ... and coming back
_MARGIN: dict[
    str, tuple[Literal["margin_top", "margin_right", "margin_bottom", "margin_left"], int]
] = {
    "TOP": ("margin_top", 0),
    "RIGHT": ("margin_right", 1),
    "BOTTOM": ("margin_bottom", 2),
    "LEFT": ("margin_left", 3),
}


class AutoHide:
    def __init__(self, manager: SurfaceManager, full_input: Callable[[Surface], Any]) -> None:
        self._m = manager
        self._full_input = full_input
        # shortcut mode holds every Bar out (it reveals the hidden ones, and keeps them)
        self.holds: Callable[[Surface], bool] = lambda s: self._m.mode.machine.on

    # -- what a Bar asks ------------------------------------------------------------------------

    @staticmethod
    def applies(s: Surface) -> bool:
        """Whether ``s`` is a shown Bar that hides itself."""
        bar = s.planned.bar if s.planned else None
        return isinstance(bar, BarDef) and bar.auto_hide and s.window is not None and not s.hidden

    def _held(self, s: Surface) -> bool:
        if self._m.focused == s.name:
            return True
        current = self._m.popups.current
        if current is not None and current.parent is s:
            return True
        return self.holds(s)

    # -- the pointer ----------------------------------------------------------------------------

    def wire(self, s: Surface) -> None:
        """The pointer on the Bar's window (tre: ``pointer_enter`` and ``pointer_leave`` fire for
        the node and what is in it, not between the node and its children)."""
        assert s.window is not None
        s.window.root.on("pointer_enter", lambda _e: self.entered(s))
        s.window.root.on("pointer_leave", lambda _e: self.left(s))

    def entered(self, s: Surface) -> None:
        self.cancel(s)
        if s.auto_out and not s.hidden:
            self.reveal(s)

    def left(self, s: Surface) -> None:
        if self.applies(s) and not s.auto_out and not s.covered:
            self.arm(s)

    def arm(self, s: Surface, delay: float | None = None) -> None:
        """(Re)start the delay; ``delay`` ms, else the Bar's ``Auto_Hide_Delay``."""
        self.cancel(s)
        bar = s.planned.bar if s.planned else None
        if s.window is None or not isinstance(bar, BarDef):
            return
        ms = bar.auto_hide_delay if delay is None else delay
        s.autohide_timer = s.window.after(ms, lambda: self._due(s))

    @staticmethod
    def cancel(s: Surface) -> None:
        if s.autohide_timer is not None:
            s.autohide_timer.cancel()
            s.autohide_timer = None

    def _due(self, s: Surface) -> None:
        s.autohide_timer = None
        if not self.applies(s) or s.auto_out:
            return
        if self._held(s):
            self.arm(s)  # in use: look again after another delay
            return
        self.out(s)

    # -- the slide ------------------------------------------------------------------------------

    def _instant(self, s: Surface) -> bool:
        """No animation: the desktop asks for reduced motion, or the Bar's ``Animation`` is NONE
        (or has a duration of 0)."""
        look = self._m._look
        if look is not None and look.appearance.reduced_motion:
            return True
        bar = s.planned.bar if s.planned else None
        return not isinstance(bar, BarDef) or bar.animation == "NONE" or bar.duration <= 0

    @staticmethod
    def _thickness(s: Surface) -> int:
        bar = s.planned.bar if s.planned else None
        assert isinstance(bar, BarDef) and s.planned is not None
        out_w, out_h = s.planned.output.width, s.planned.output.height
        size = s.geometry.size
        if bar.edge in ("TOP", "BOTTOM"):
            return size[1] or out_h
        return size[0] or out_w

    def strip(self, s: Surface) -> list[tuple[int, int, int, int]]:
        """The ``input_region`` of a Bar that is out: the strip along its full length."""
        bar = s.planned.bar if s.planned else None
        assert isinstance(bar, BarDef) and s.planned is not None
        out_w, out_h = s.planned.output.width, s.planned.output.height
        w = s.geometry.size[0] or out_w
        h = s.geometry.size[1] or out_h
        t = self._thickness(s)
        return {
            "TOP": [(0, t - STRIP, w, STRIP)],  # the part of the window still on the screen
            "BOTTOM": [(0, 0, w, STRIP)],
            "LEFT": [(t - STRIP, 0, STRIP, h)],
            "RIGHT": [(0, 0, STRIP, h)],
        }[bar.edge]

    def out(self, s: Surface) -> None:
        """Go out (slide or fade, as the Bar's ``Animation`` says), then release the zone and leave
        the strip."""
        bar = s.planned.bar if s.planned else None
        if s.window is None or not isinstance(bar, BarDef) or s.auto_out:
            return
        s.auto_out = True
        s.generation += 1
        generation, window = s.generation, s.window
        prop, index = _MARGIN[bar.edge]
        far = STRIP - self._thickness(s)
        margin = list(s.geometry.margin)
        margin[index] = far
        ms = int(bar.duration)
        logger.info(f"Bar {s.planned.where if s.planned else s.name} goes out ({bar.animation})")

        def done() -> None:
            if s.generation == generation and s.window is window and s.auto_out:
                # off the screen but for the strip, and opaque again for the way back; the space
                # back, once
                window.set(margin=tuple(margin), exclusive_zone=0, input_region=self.strip(s))
                window.root.set(opacity=1.0)

        if self._instant(s):
            done()
        elif bar.animation == "FADE":
            window.root.animate("opacity", 0.0, ms, FADE_EASE_OUT, done)
        else:
            window.animate(prop, far, ms, FADE_EASE_OUT)
            window.after(ms, done)

    def reveal(self, s: Surface, instant: bool = False) -> None:
        """Come back: the zone and the input first, then slide in or fade in to rest."""
        bar = s.planned.bar if s.planned else None
        if s.window is None or not isinstance(bar, BarDef) or not s.auto_out:
            return
        s.auto_out = False
        s.generation += 1
        generation, window = s.generation, s.window
        prop, index = _MARGIN[bar.edge]
        rest = s.geometry.margin
        ms = int(bar.duration)
        window.set(
            exclusive_zone=s.geometry.exclusive_zone,
            input_region=self._full_input(s),
        )
        logger.info(f"Bar {s.planned.where if s.planned else s.name} comes back ({bar.animation})")
        if instant or self._instant(s):
            window.set(margin=rest)
            window.root.set(opacity=1.0)
            return
        if bar.animation == "FADE":
            window.set(margin=rest)
            if (
                window.root.get("opacity") == 1.0
            ):  # a fade out that was cut short goes on from there
                window.root.set(opacity=0.0)
            window.root.animate("opacity", 1.0, ms, FADE_EASE_IN)
        else:
            window.animate(prop, rest[index], ms, FADE_EASE_IN)

        def done() -> None:
            if s.generation == generation and s.window is window:
                window.set(margin=rest)  # exactly at rest
                window.root.set(opacity=1.0)

        window.after(ms, done)

    # -- shortcut mode (ADR-0021: a hidden Bar is revealed by the mode) --------------------------

    def mode_entered(self) -> None:
        """Entering shortcut mode brings every Bar that slid out back and keeps it while the mode
        lasts; the delay of a Bar still waiting to hide is cancelled."""
        for s in self._m.surfaces:
            if not self.applies(s):
                continue
            self.cancel(s)
            if s.auto_out:
                s.mode_revealed = True
                self.reveal(s)

    def mode_left(self) -> None:
        """Leaving the mode (or Escape) starts the delay of each Bar the mode brought back."""
        for s in self._m.surfaces:
            if s.mode_revealed:
                s.mode_revealed = False
                if self.applies(s) and not s.auto_out:
                    self.arm(s)
