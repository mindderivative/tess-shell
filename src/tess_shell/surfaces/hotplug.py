"""Monitors coming and going (Data Flow > Monitor Hot-plug, M3c C4).

tre calls ``output_added``, ``output_removed`` and ``output_updated`` on the loop thread. Each one
changes the shell's list of outputs and runs the same steps:

1. plan the whole shell again against the new list (the monitor matcher, so ``Connector``,
   ``Description``, ``Index`` and ``default`` all apply as at start, and an output another
   ``Monitor`` took stays taken);
2. bring the modules to the new set of uses the way a hot reload does (``sync_uses``: a use on
   a removed monitor gets ``use_removed``, a module with no use left is stopped, a use on a new
   monitor gets ``use_added``, a module that was not running is started);
3. compare the new plan with the running surfaces by their key and output: a surface that is in
   both is not touched, unless its output changed size or scale (then its geometry is set live,
   no new window); one that is only in the old plan is closed; one that is only in the new plan
   is opened, exactly as at start.

So a surface of another monitor is never closed, recreated or redrawn, and a monitor that returns
gets new windows (a closed ``LayerWindow`` is dead) at the position the registry saved for
``<Monitor>@<output>``, clamped to the output.

``Index`` is the position in the list tre gives (top to bottom, then left to right), so it is
evaluated again on every change: a ``Monitor { Index: 1 }`` follows whichever screen is second
now, and its surfaces close and open on that screen when the order changes. ``Connector`` and
``Description`` do not move.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from tess_shell.schema.model import PanelDef

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tess_re import Output

    from tess_shell.surfaces.manager import Planned, Surface, SurfaceManager


def _shape(output: Any) -> tuple[Any, ...]:
    """What of an output a surface's geometry depends on."""
    return (
        getattr(output, "width", 0),
        getattr(output, "height", 0),
        getattr(output, "scale_factor", 1.0),
        getattr(output, "transform", "normal"),
    )


def _order(outputs: Sequence[Output]) -> list[Output]:
    """tre's order: top to bottom, then left to right (a stable sort keeps ties as they were)."""
    return sorted(outputs, key=lambda o: (getattr(o, "y", 0), getattr(o, "x", 0)))


class OutputWatch:
    """The shell's list of outputs and what to do when it changes. Owned by the manager."""

    def __init__(self, manager: SurfaceManager) -> None:
        self._m = manager
        self.known: list[Output] = []  # the outputs as the last plan or event saw them

    # -- tre's events (loop thread) -----------------------------------------------------------

    def start(self) -> None:
        """Listen for output events. Call after the surfaces are built and before the loop runs;
        an output that came or went since the plan was made is caught up at once."""
        app = self._m._app
        app.on("output_added", self.added)
        app.on("output_removed", self.removed)
        app.on("output_updated", self.updated)
        now = list(app.outputs())
        if [(o.name, _shape(o)) for o in now] != [(o.name, _shape(o)) for o in self.known]:
            self.known = now
            self._run("the outputs changed while the shell started")

    def added(self, output: Output) -> None:
        self.known = _order([o for o in self.known if o.name != output.name] + [output])
        self._run(f"output {output.name} added")

    def removed(self, output: Output) -> None:
        self.known = [o for o in self.known if o.name != output.name]
        self._run(f"output {output.name} removed")

    def updated(self, output: Output) -> None:
        self.known = _order([o for o in self.known if o.name != output.name] + [output])
        self._run(f"output {output.name} changed ({_shape(output)[:2]}, scale {_shape(output)[2]})")

    def _run(self, why: str) -> None:
        try:
            self.changed(why)
        except Exception:
            logger.opt(exception=True).error(f"handling '{why}' failed; check the surfaces")

    # -- the steps ----------------------------------------------------------------------------

    def changed(self, why: str) -> None:
        m = self._m
        names = ", ".join(o.name for o in self.known) or "none"
        logger.info(f"{why}: outputs now {names}")
        if m._shell is None:
            return  # no main shell file: nothing is shown
        planned, uses = m._plan_bars(m._shell, m._modules, m._look, list(self.known))
        for use in uses:
            m._store.add_use(use.module, use.key)
        if m.sync_uses is not None:
            m.sync_uses(uses)
        m.popups.merge_plans(m._popup_plans)
        self._reconcile(planned)
        m._planned = planned
        m.frames.sync(m._frame_plans, m._look)  # the Frames of the outputs that came or went
        keep = {u.key for u in uses}
        for key in [k for k in m._store.values if k not in keep]:
            m._store.remove_use(key)
        m.wake()

    def _reconcile(self, planned: list[Planned]) -> None:
        m = self._m
        all_uses = {u.key: u for p in planned for u in p.expanded.uses}
        all_uses.update(m.popups.uses())
        m._all_uses = all_uses
        old = {s.key: s for s in m.surfaces}
        kept: dict[str, Surface] = {}
        fresh: list[Planned] = []
        for p in planned:
            s = old.get(p.key)
            if s is not None and s.output == p.output.name and s.planned is not None:
                kept[p.key] = old.pop(p.key)
            else:
                fresh.append(p)
        for s in old.values():
            why = (
                f"output {s.output} was removed"
                if s.output not in {o.name for o in self.known}
                else f"its Monitor no longer matches {s.output}"
            )
            self._drop(s, why)
        opened: dict[str, Surface] = {}
        for p in fresh:
            kind = "Panel" if isinstance(p.bar, PanelDef) else "Bar"
            logger.info(f"{kind} {p.where} is opened: output {p.output.name} is there")
            opened[p.key] = m._open(p, all_uses)
        resized: set[str] = set()
        for p in planned:
            if p.key in kept and self._retarget(kept[p.key], p):
                resized.add(p.group)
        m.surfaces = [kept[p.key] if p.key in kept else opened[p.key] for p in planned]
        for group in resized:
            self._replace_attached(group)

    def _drop(self, s: Surface, why: str) -> None:
        m = self._m
        kind = "Panel" if s.planned is not None and isinstance(s.planned.bar, PanelDef) else "Bar"
        where = s.planned.where if s.planned else f"{s.name} on {s.output}"
        had_window = s.window is not None
        m._close(s)
        s.window, s.view, s.body = None, None, None
        logger.info(f"{kind} {where} closed: {why}" + ("" if had_window else " (no window)"))

    def _retarget(self, s: Surface, p: Planned) -> bool:
        """A surface that stays: tell it its output as it is now, and set its geometry live when
        the output's size or scale changed. Returns whether the geometry was recomputed."""
        m = self._m
        assert s.planned is not None
        before = s.planned.output
        s.planned.output = p.output
        if _shape(before) == _shape(p.output):
            return False
        m.popups.parent_closed(s)  # a Popup opened on the old size goes
        s.planned.geometry = p.geometry
        if s.window is None:  # a hidden Panel with no window: the next show uses this
            s.geometry = p.geometry
        else:
            m._sync_body(s, s.planned.bar, p.geometry, s.planned.where)
            s.planned.geometry = s.geometry
        logger.info(
            f"{s.planned.where}: output {p.output.name} is now {_shape(p.output)[0]}x"
            f"{_shape(p.output)[1]} at scale {_shape(p.output)[2]}"
        )
        return True

    def _replace_attached(self, group: str) -> None:
        """A Panel attached to a module is placed from where tre laid the module out; the Bar has
        just been resized, so place it again once it has been laid out."""
        m = self._m
        bar = next(
            (
                s
                for s in m.surfaces
                if s.planned is not None and s.planned.group == group and s.window is not None
            ),
            None,
        )
        if bar is not None and bar.window is not None:
            bar.window.after(50, lambda: m._relayout_attached(group))
