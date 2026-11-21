"""The scroll of a Marquee (Standard Modules > Marquee text).

A Marquee is a box that clips and the text inside it (``model.marquee``). The runner measures both
once the layout is known (``layout_width``) and, when the text is wider than the box and the block
may animate, moves the text with tre's own animation: one ``animate`` of ``translate_x`` per leg at
``Speed`` pixels a second, and a timer for each ``Pause``. Python runs when a leg ends, never per
frame, and while the text fits, while the Marquee is disabled or under reduced motion nothing runs
at all and the window draws no frame.

* ``Loop: RESTART``: wait at the start, scroll to the end, wait, jump back and again.
* ``Loop: BOUNCE``: wait, scroll to the end, wait, scroll back, wait, and again.
* ``Direction: LEFT`` moves the text to the left (the start shows first); ``RIGHT`` moves it to the
  right (the end shows first).
* The pointer over the box pauses the scroll where it is (the text stops, a pending wait is
  held); the pointer leaving resumes it (AC-MOD-MQT-7).
* Not scrolling (disabled, reduced motion, or ``Animated: false``) a text that does not fit shows
  with an ellipsis, and the tooltip of the block may show the whole text (``tooltip_gate``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from tess_shell.binder.model import Bool, Enum, Node, Number

if TYPE_CHECKING:
    from tess_re import Node as TreNode
    from tess_re import TimerHandle, Window

DEFAULT_SPEED = 30.0  # pixels a second
DEFAULT_PAUSE = 1500  # milliseconds
FIT = 0.5  # pixels of text over the box that still count as fitting


class MarqueeRunner:
    """One Marquee's scroll: ``configure`` it from its typed block and ``refresh`` it when
    something that decides it may have changed."""

    def __init__(self, window: Window, box: TreNode, text: TreNode) -> None:
        self.window = window
        self.box = box
        self.text = text
        self.speed = DEFAULT_SPEED
        self.pause = DEFAULT_PAUSE
        self.direction = "LEFT"
        self.loop = "RESTART"
        self.animated = True
        self.blocked = False
        self.state = "new"  # new, fits, running or static
        self.timer: TimerHandle | None = None
        self.token = 0  # a leg that finishes under an older token is ignored
        self._seen: tuple[Any, ...] = ()
        self.legs = 0  # legs started since the start (for tests)
        self.hooked = False  # the box's pointer hooks are added
        self.paused = False  # the pointer is over the box
        self._resume: Callable[[], None] | None = (
            None  # what the leg or wait in progress goes on with
        )

    # -- what the block says --------------------------------------------------------------------

    def configure(self, typed: Node, blocked: bool) -> None:
        def number(key: str, default: float) -> float:
            value = typed.props.get(key)
            return float(value.value) if isinstance(value, Number) else default

        def word(key: str, default: str) -> str:
            value = typed.props.get(key)
            return value.name if isinstance(value, Enum) else default

        animated = typed.props.get("Animated")
        self.speed = number("Speed", DEFAULT_SPEED)
        self.pause = int(number("Pause", DEFAULT_PAUSE))
        self.direction = word("Direction", "LEFT")
        self.loop = word("Loop", "RESTART")
        self.animated = animated.value if isinstance(animated, Bool) else True
        self.blocked = blocked

    def tooltip_gate(self) -> bool:
        """Whether the block's tooltip may open: it shows the whole text a Marquee that does not
        scroll cannot (it is cut with an ellipsis)."""
        return self.state == "static"

    # -- measuring and starting -----------------------------------------------------------------

    def _signature(self) -> tuple[Any, ...]:
        try:
            return (
                self.text.get("text"),
                round(float(self.box.get("layout_width")), 1),
                self.speed,
                self.pause,
                self.direction,
                self.loop,
                self.animated,
                self.blocked,
            )
        except ValueError:  # a node that is gone
            return ()

    def refresh(self, force: bool = False) -> None:
        """Measure again and begin, change or end the scroll if what decides it changed."""
        signature = self._signature()
        if not signature or (not force and signature == self._seen):
            return
        self._seen = signature
        self._stop()
        try:
            self._measure_and_start()
        except ValueError:
            self.state = "new"

    def _measure_and_start(self) -> None:
        # the text at its own width, where it starts, to be measured
        self.text.set(width="fit-content", overflow="clip", translate_x=0)
        over = float(self.text.get("layout_width")) - float(self.box.get("layout_width"))
        if over <= FIT:
            self.state = "fits"
            return
        if self.animated and not self.blocked:
            self.state = "running"
            self._begin(over)
            return
        # it does not fit and may not move: cut it with an ellipsis at the box's width
        self.state = "static"
        self.text.set(width="100%", overflow="ellipsis")

    def hover(self, over: bool) -> None:
        """The pointer came onto the box or left it: pause the scroll where it is, or go on."""
        if over == self.paused:
            return
        self.paused = over
        if self.state != "running":
            return
        if over:
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None
            try:
                self.text.stop_animation("translate_x")  # a no-op while a wait is pending
            except ValueError:
                pass
        elif self._resume is not None:
            resume, self._resume = self._resume, None
            resume()

    def _stop(self) -> None:
        self.token += 1
        self._resume = None
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        if self.state == "running":
            try:
                self.text.stop_animation("translate_x")
            except ValueError:
                pass

    def stop(self) -> None:
        """The node is going away or the view is disposed: cancel everything."""
        self._stop()
        self.state = "new"
        self._seen = ()

    # -- the scroll -----------------------------------------------------------------------------

    def _begin(self, distance: float) -> None:
        start, end = (0.0, -distance) if self.direction == "LEFT" else (-distance, 0.0)
        token = self.token

        def live() -> bool:
            return token == self.token

        def wait(then: Any) -> None:
            if not live():
                return
            self._resume = lambda: wait(then)
            if not self.paused:
                self.timer = self.window.after(self.pause, then)

        def leg(to: float, then: Any) -> None:
            self.timer = None
            if not live():
                return
            self._resume = lambda: leg(to, then)
            if self.paused:
                return
            here = float(self.text.get("translate_x") or 0.0)
            left = max(int(abs(to - here) / self.speed * 1000), 1)  # all of it, or what is left
            self.legs += 1
            try:
                self.text.animate(
                    "translate_x", to, left, "linear", on_complete=lambda: arrived(then)
                )
            except ValueError:
                self.state = "new"

        def arrived(then: Any) -> None:
            if live():
                self._resume = None
                then()

        def forward() -> None:
            leg(end, at_end)

        def at_end() -> None:
            wait(back)

        def back() -> None:
            self.timer = None
            if not live():
                return
            if self.loop == "BOUNCE":
                leg(start, at_start)
                return
            try:
                self.text.set(translate_x=start)  # RESTART: jump back
            except ValueError:
                self.state = "new"
                return
            at_start()

        def at_start() -> None:
            wait(forward)

        self.text.set(translate_x=start)
        at_start()
