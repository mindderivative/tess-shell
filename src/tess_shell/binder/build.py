"""Build a typed tree into tre nodes (Render Binder Design > Building).

All problems are collected first, each at the position of its key; if there are any, nothing is
built, so a surface never half-builds. tre's own ``ValueError`` (which names a path such as
``spec.children[2]``) is translated back to a position through an index made while planning.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tess_shell.binder.convert import CONVERTERS
from tess_shell.binder.marquee import MarqueeRunner
from tess_shell.binder.model import (
    DECORATIVE,
    FIELD,
    FIELD_INPUT,
    FIELD_LINE,
    MARQUEE,
    MARQUEE_TEXT,
    NO_POINTER_BLOCKS,
    BindError,
    BindFailed,
    ForNode,
    Handler,
    IfNode,
    Node,
    Origin,
    SlotValue,
    TokenRef,
    UseNode,
    Value,
)
from tess_shell.binder.motion import Motion, motion_of
from tess_shell.binder.motion import check as check_motion
from tess_shell.binder.motion import start as start_motion
from tess_shell.binder.shapes import POSTS
from tess_shell.binder.tables import BLOCKS, BlockRow, KeyRow

if TYPE_CHECKING:
    from tess_re import Node as TreNode
    from tess_re import Window

    from tess_shell.binder.rebuild import RebuildStats

_TRE_ERROR = re.compile(
    r"^build: (?P<path>spec(?:\.children\[\d+\])*)(?P<id>\.id)?: (?P<message>.*)$", re.DOTALL
)
_TRE_PROP = re.compile(r"node property `(?P<prop>\w+)`")


@dataclass(slots=True)
class _Index:
    """Spec path to the node's origin, and the origin of each tre property's TDL key."""

    nodes: dict[str, Origin] = field(default_factory=dict)
    props: dict[tuple[str, str], Origin] = field(default_factory=dict)
    named: dict[str, tuple[str, dict[str, Any]]] = field(default_factory=dict)


# tre's pointer events that move a node between its style states, and what each does to the wire
_STATE_EVENTS = (
    ("pointer_enter", "enter"),
    ("pointer_leave", "leave"),
    ("pointer_down", "down"),
    ("pointer_up", "up"),
    ("pointer_cancel", "cancel"),
)


@dataclass(slots=True)
class Wire:
    """What a built node's listeners read: the current handlers (a reload replaces them without
    touching the listeners), the tre events that already have a listener and the node's style
    states.

    ``states`` holds the converted tre properties of each state (``hovered``, ``pressed``,
    ``disabled``). While the pointer is over the node ``hovered`` shows; while a button is down on
    it ``pressed`` shows on top; while the block is disabled ``disabled`` shows over both.
    ``saved`` remembers the value each forced property had before a state took it, so the end of
    the state puts it back exactly. A state listener never stops an event.

    A disabled block (``Enabled: false``, ``disabled``) and every block under one is *blocked*:
    tre only sets the accessibility state, so the shell stops the pointer itself (Block Reference
    > State). A blocked node takes no ``hovered`` or ``pressed`` state, runs none of its hooks
    (so no tooltip opens over it) and swallows the ``click`` that reaches it: its ``On_Click``
    does not run and no block behind or above it hears that click. The ``pointer_down`` and
    ``pointer_up`` still bubble (a Popup is dismissed by a press anywhere on the surface).
    """

    handlers: Mapping[str, Handler]
    wired: set[str] = field(default_factory=set)
    states: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    tre: TreNode | None = None
    window: Window | None = None
    hovered: bool = False
    pressed: bool = False
    shown: dict[str, Any] = field(default_factory=dict)  # the properties a state forces now
    saved: dict[str, Any] = field(default_factory=dict)  # their values before it did
    hooks: dict[str, list[Callable[[], None]]] = field(default_factory=dict)
    disabled: bool = False  # the block's own ``Enabled: false``
    inherited: bool = False  # a block above it is disabled
    part: bool = False  # the node is a module's named part (``Part: track``)
    # a TextField's text input: told when the field becomes blocked or free (it must stop taking
    # keys, not only clicks)
    on_block: Callable[[bool], None] | None = None
    # a TextField's box: the text input that takes the focus when the box is pressed, and the
    # wire that shows the box's hover and press (the text input's style states follow the box)
    focus_target: TreNode | None = None
    mirror: Wire | None = None
    # a Marquee's box: whether its tooltip may open now (it shows the whole text that is cut)
    tooltip_gate: Callable[[], bool] | None = None

    @property
    def blocked(self) -> bool:
        """The pointer does nothing here: the block, or one above it, is disabled."""
        return self.disabled or self.inherited

    def listen(self) -> None:
        """Listen for what moves the node between its states, once. These listeners only read the
        pointer: none stops the event, so a click still bubbles and reaches ``On_Click``."""
        if self.tre is None:
            return
        for event, action in _STATE_EVENTS:
            key = f"state:{event}"
            if key not in self.wired:
                self.wired.add(key)
                self.tre.on(event, self._listener(action))

    def _listener(self, action: str) -> Callable[[Any], None]:
        do: Callable[[], None] = getattr(self, action)
        return lambda _event: do()

    def add_hook(self, event: str, fn: Callable[[], None]) -> None:
        """Call ``fn`` after the node's ``enter``, ``leave``, ``down`` or ``up`` (``cancel`` calls
        the ``up`` hooks). A node takes one tre listener per event, so anything that needs the
        pointer on a built node goes through here."""
        if event not in ("enter", "leave", "down", "up"):
            raise ValueError(f"no hook for {event}")
        self.hooks.setdefault(event, []).append(fn)
        self.listen()

    def _run(self, event: str) -> None:
        for fn in self.hooks.get(event, ()):
            fn()

    def enter(self) -> None:
        if self.blocked:
            return
        self.hovered = True
        self.refresh()
        self._run("enter")

    def leave(self) -> None:
        if self.blocked:  # a node that became blocked was already cleared and told
            return
        self.hovered = self.pressed = False
        self.refresh()
        self._run("leave")

    def down(self) -> None:
        if self.blocked:
            return
        self.hovered = self.pressed = True  # a press is over the node, whatever enter said
        self.refresh()
        self._run("down")

    def up(self) -> None:
        if self.blocked:
            return
        self.pressed = False
        self.refresh()
        self._run("up")

    def sync(self, disabled: bool, inherited: bool, part: bool) -> None:
        """The node's ``Enabled`` and that of the blocks above it, as they are now. A node that
        becomes blocked while the pointer is on it is cleared at once (its stored pre-state values
        come back) and its ``leave`` and ``up`` hooks run, so a pending tooltip is cancelled.
        Becoming enabled again changes nothing but the look: the state is taken up again with the
        next pointer event (tre sends no event for a pointer that is already there)."""
        was = self.blocked
        was_hovered, was_pressed = self.hovered, self.pressed
        self.disabled, self.inherited, self.part = disabled, inherited, part
        newly = self.blocked and not was
        if newly:
            self.hovered = self.pressed = False
        self.refresh()
        if newly:
            if was_pressed:
                self._run("up")
            if was_hovered:
                self._run("leave")
        if self.on_block is not None and self.blocked != was:
            self.on_block(self.blocked)

    def cancel(self) -> None:
        """The press became a move or resize of the window: no up or click follows."""
        self.up()

    def focus_field(self) -> None:
        """A press on a TextField's box (its padding, or its border) gives the text input the
        focus, as a press on the text itself does."""
        target = self.focus_target
        if target is not None and not target.get("focused"):
            target.focus()

    def follow(self, event: str) -> None:
        """The state of the wire that follows this one (a TextField's text input)."""
        if self.mirror is not None:
            getattr(self.mirror, event)()

    def wanted(self) -> dict[str, Any]:
        """The properties the current state forces: hovered's, with pressed's on top and, when
        the block is disabled, disabled's over both. A part of a module takes ``disabled`` when
        the module is disabled, not only when the part itself is (Style Schema > Stylesheet
        Selectors, ``Slider::handle:disabled``)."""
        out: dict[str, Any] = {}
        if self.hovered or self.pressed:
            out.update(self.states.get("hovered", {}))
        if self.pressed:
            out.update(self.states.get("pressed", {}))
        if self.disabled or (self.part and self.inherited):
            out.update(self.states.get("disabled", {}))
        return out

    def refresh(self) -> None:
        """Make the node show what the current state asks and nothing it no longer asks."""
        tre, window = self.tre, self.window
        if tre is None or window is None:
            return
        wanted = self.wanted()
        changes: dict[str, Any] = {n: self.saved.pop(n) for n in self.shown if n not in wanted}
        for name, value in wanted.items():
            if name not in self.saved:
                self.saved[name] = tre.get(name)
            if name not in self.shown or self.shown[name] != value:
                changes[name] = value
        self.shown = wanted
        if changes:
            window.apply([(tre, changes)])

    def restate(self, states: Mapping[str, Mapping[str, Any]], base: Mapping[str, Any]) -> None:
        """A reload changed the state styles (``states``) and, for some properties a state holds,
        the base value (``base``): keep the node in the state it is in, with the new look."""
        self.saved.update({n: v for n, v in base.items() if n in self.saved})
        self.states = states
        self.refresh()


@dataclass(slots=True)
class Entry:
    """One built node: its typed source, the tre node, the tre props it was given, and its
    children. The tree of entries is what ``View.rebuild`` compares a new typed tree with."""

    typed: Node
    tre: TreNode | None
    props: dict[str, Any]
    children: list[Entry] = field(default_factory=list)
    wire: Wire | None = None
    states: dict[str, dict[str, Any]] = field(default_factory=dict)  # tre props per style state
    motion: Motion | None = None  # what eases when a value of the node changes


def field_input(box: Entry) -> Entry | None:
    """The text input of a built TextField: in the line box that is the box's one child."""
    for line in box.children:
        if line.typed.kind == FIELD_LINE:
            return next((c for c in line.children if c.typed.kind == FIELD_INPUT), None)
    return None


@dataclass(slots=True)
class View:
    """What was built: the attached roots and the named nodes."""

    window: Window
    roots: list[TreNode]
    nodes: dict[str, TreNode]
    kinds: dict[str, str] = field(default_factory=dict)  # node id -> block word
    applied: dict[str, dict[str, Any]] = field(default_factory=dict)  # node id -> tre props set
    entries: list[Entry] = field(default_factory=list)
    wires: dict[str, Wire] = field(default_factory=dict)  # node id -> its wire
    motions: dict[str, Motion] = field(default_factory=dict)  # node id -> its transition
    runners: dict[TreNode, MarqueeRunner] = field(default_factory=dict)  # a Marquee's box -> scroll
    disposed: bool = False
    parent: TreNode | None = None  # where the roots are attached; ``window.root`` when None
    sink: Callable[[Handler, str, Any], None] | None = None  # (handler, event key, tre event)

    def rebuild(self, nodes: Sequence[Node | UseNode | IfNode | ForNode]) -> RebuildStats:
        """Make the view show ``nodes``, changing only what differs (Render Binder Design > The
        Keyed Diff). Raises :class:`BindFailed` and changes nothing if any value is wrong."""
        from tess_shell.binder.rebuild import rebuild

        return rebuild(self, nodes)

    def reindex(self) -> None:
        """Rebuild the id maps from the entries."""
        self.nodes.clear()
        self.kinds.clear()
        self.applied.clear()
        self.wires.clear()
        self.motions.clear()
        self.roots = [e.tre for e in self.entries if e.tre is not None]

        def walk(entries: list[Entry]) -> None:
            for e in entries:
                self._wire(e)
                name = e.typed.name
                if name is not None and e.tre is not None:
                    self.nodes[name] = e.tre
                    self.kinds[name] = e.typed.kind
                    self.applied[name] = e.props  # the same dict: an update changes both
                    if e.wire is not None:
                        self.wires[name] = e.wire
                    if e.motion is not None:
                        self.motions[name] = e.motion
                walk(e.children)

        walk(self.entries)
        self._sync(self.entries)
        self._marquees()

    def _marquees(self) -> None:
        """Keep one scroll runner per Marquee, configured from its block, and let each measure and
        begin, change or end its scroll if what decides it changed."""
        live: dict[TreNode, MarqueeRunner] = {}
        fresh: list[MarqueeRunner] = []

        def walk(entries: list[Entry]) -> None:
            for e in entries:
                if e.typed.kind == MARQUEE and e.tre is not None and e.children:
                    text = e.children[0].tre
                    if text is not None:
                        runner = self.runners.get(e.tre)
                        if runner is None:
                            runner = MarqueeRunner(self.window, e.tre, text)
                            fresh.append(runner)
                        runner.text = text
                        live[e.tre] = runner
                        runner.configure(e.typed, e.wire.blocked if e.wire else False)
                        if e.wire is not None:
                            e.wire.tooltip_gate = runner.tooltip_gate
                walk(e.children)

        walk(self.entries)
        for box, runner in self.runners.items():
            if box not in live:
                runner.stop()
        self.runners = live
        for runner in live.values():
            runner.refresh()
        for runner in fresh:  # the first layout of a new surface may come after the build
            self.window.after(100, runner.refresh)

    def _wire(self, entry: Entry) -> None:
        """Give a node with handlers or state styles its tre listeners; a listener looks the
        handler up when the event arrives, so a reload that changes the handler needs no new
        listener."""
        if entry.tre is None:
            return
        if entry.wire is None:
            entry.wire = Wire(entry.typed.handlers, tre=entry.tre, window=self.window)
        wire = entry.wire
        wire.states = entry.states
        if entry.typed.kind == FIELD_INPUT:
            self._ensure_field_events(entry)  # its states follow its box, which listens
        else:
            if any(state != "disabled" for state in wire.states):  # ``disabled`` needs no pointer
                wire.listen()
            self._ensure_click(entry)
            if entry.typed.kind == FIELD:
                self._wire_field(entry)

    def _wire_field(self, entry: Entry) -> None:
        """A TextField's box: a press gives the text input the focus, and the box's hover and
        press are the text input's too (its ``Foreground`` states). The wires are looked up when
        an event arrives, so a rebuild that replaces the text input needs no new listener."""
        assert entry.wire is not None
        wire = entry.wire
        inner = field_input(entry)
        if inner is not None:
            self._wire(inner)  # the walk reaches the children after their box
        wire.focus_target = inner.tre if inner is not None else None
        wire.mirror = inner.wire if inner is not None else None
        if "field" not in wire.wired:
            wire.wired.add("field")
            wire.add_hook("down", wire.focus_field)

            def follower(event: str, wire: Wire = wire) -> Callable[[], None]:
                return lambda: wire.follow(event)

            for event in ("enter", "leave", "down", "up"):
                wire.add_hook(event, follower(event))
        if inner is not None and inner.wire is not None:

            def block(blocked: bool, box: Entry = entry) -> None:
                self._block_field(box, blocked)

            inner.wire.on_block = block  # told by the next ``_sync``

    def _block_field(self, box: Entry, blocked: bool) -> None:
        """A disabled TextField takes no pointer and no keys (tre's ``disabled`` is an
        accessibility state only): its text input is read-only, takes no hit, says it is
        disabled, and gives up the focus. Enabled again, it has what the file declared."""
        inner = field_input(box)
        if inner is None or inner.tre is None or box.tre is None:
            return
        declared = inner.props
        changes: dict[str, Any] = {
            "hit_testable": not blocked,
            "disabled": blocked or bool(declared.get("disabled")),
            "read_only": blocked or bool(declared.get("read_only")),
        }
        self.window.apply([(inner.tre, changes)])
        if blocked and inner.tre.get("focused"):
            # tre has no way to drop the focus but to give it away: the box takes it (a box that
            # no key or press can reach) and is not focusable again
            box.tre.set(focusable=True)
            box.tre.focus()
            box.tre.set(focusable=False)

    def _ensure_field_events(self, entry: Entry) -> None:
        """The text input's ``change``, ``submit`` and ``input`` listeners (``On_Changed``,
        ``On_Submit``, ``On_Text_Commit``), one each, once the node has a handler for it. A
        disabled field raises nothing, and a read-only one raises no commit."""
        wire, tre = entry.wire, entry.tre
        if tre is None or wire is None:
            return
        for event, key in (
            ("change", "On_Changed"),
            ("submit", "On_Submit"),
            ("input", "On_Text_Commit"),
        ):
            token = f"field:{event}"
            if token in wire.wired or key not in wire.handlers:
                continue
            wire.wired.add(token)

            def listener(raw: Any, wire: Wire = wire, key: str = key, tre: TreNode = tre) -> None:
                handler = wire.handlers.get(key)
                if handler is None or wire.blocked or self.sink is None:
                    return
                if key == "On_Text_Commit" and tre.get("read_only"):
                    return  # nothing was inserted
                self.sink(handler, key, raw)

            tre.on(event, listener)

    def _sync(self, entries: list[Entry], inherited: bool = False) -> None:
        """Tell every wire whether its block, or one above it, is disabled (``Enabled: false`` is
        tre's ``disabled`` in the node's properties). A disabled block gets a ``click`` listener
        whatever its handlers, to swallow the click."""
        for e in entries:
            own = bool(e.props.get("disabled"))
            if e.wire is not None:
                # a text input is a part of its field: it shows ``disabled`` when the field is
                part = bool(e.typed.part) or e.typed.kind in (FIELD_INPUT, MARQUEE_TEXT)
                e.wire.sync(own, inherited, part)
                self._ensure_click(e)
            self._sync(e.children, inherited or own)

    def _ensure_click(self, entry: Entry) -> None:
        """The one ``click`` listener of a node that has an ``On_Click`` or is disabled. It
        stops the event: tre's click bubbles to every ancestor's listener, and a clickable inside
        a clickable takes its click alone (as Material 3 expects), even when the handler raises.
        A disabled node swallows the click without running anything."""
        wire = entry.wire
        if entry.tre is None or wire is None or "On_Click" in wire.wired:
            return
        if "On_Click" not in wire.handlers and not wire.disabled:
            return
        wire.wired.add("On_Click")

        def listener(event: Any, wire: Wire = wire) -> None:
            stop = getattr(event, "stop", None)
            if wire.blocked:
                if stop is not None:
                    stop()
                return
            handler = wire.handlers.get("On_Click")
            if handler is None:  # the node was disabled once and has no handler now
                return
            try:
                if self.sink is not None:
                    self.sink(handler, "On_Click", event)
            finally:
                if stop is not None:
                    stop()

        entry.tre.on("click", listener)

    def update(self, changes: Sequence[tuple[str, str, Value]]) -> list[BindError]:
        """Set new typed values on named nodes: ``(node id, TDL key, value)``.

        Each is converted by the same table row that built the node. A value that converts to what
        the node already has makes no call; the rest go to tre in one ``Window.apply``. A bad
        value is returned as an error and leaves that property as it was.
        """
        errors: list[BindError] = []
        by_node: dict[str, dict[str, Any]] = {}
        for node_id, key, value in changes:
            kind = self.kinds.get(node_id)
            row = BLOCKS.get(kind) if kind else None
            key_row = (row.style.get(key) or row.keys.get(key)) if row else None
            if row is None or key_row is None or node_id not in self.nodes:
                errors.append(BindError(f"cannot update {key} on {node_id}", value.origin))
                continue
            converted = _convert(key, key_row, value, errors)
            if converted is None:
                continue
            have = self.applied.setdefault(node_id, {})
            fresh = {n: v for n, v in converted.items() if n not in have or have[n] != v}
            if kind == FIELD_INPUT and "text" in fresh:
                tre = self.nodes[node_id]
                if tre.get("text") == fresh["text"]:
                    # the module echoes what the user typed: setting it again would put the caret
                    # at the end of the text
                    have["text"] = fresh.pop("text")
            wire = self.wires.get(node_id)
            if wire is not None and wire.saved:
                # a state holds some of these: the base value waits under it
                held = {n: v for n, v in fresh.items() if n in wire.saved}
                wire.saved.update(held)
                have.update(held)
                fresh = {n: v for n, v in fresh.items() if n not in held}
            if fresh:
                by_node.setdefault(node_id, {}).update(fresh)
        if by_node:
            eased: dict[str, dict[str, Any]] = {}
            for node_id, props in by_node.items():
                motion = self.motions.get(node_id)
                if motion is not None and any(n in motion.props for n in props):
                    eased[node_id] = {n: v for n, v in props.items() if n in motion.props}
            try:
                self.window.apply(
                    [
                        (self.nodes[i], {n: v for n, v in p.items() if n not in eased.get(i, ())})
                        for i, p in by_node.items()
                    ]
                )
            except ValueError as exc:
                for node_id in by_node:
                    errors.append(BindError(f"{node_id}: {exc}", Origin("<tre>", 1, 1)))
                return errors
            for node_id, props in by_node.items():
                self.applied[node_id].update(props)
            for node_id, props in eased.items():
                left = start_motion(self.nodes[node_id], props, self.motions[node_id])
                if left:  # tre could not ease these: they jump
                    self.nodes[node_id].set(**left)
            if any("disabled" in props for props in by_node.values()):
                self._sync(self.entries)  # a block above may have been disabled or enabled
                self._marquees()
            else:
                for node_id in by_node:
                    runner = self._runner_of(node_id)
                    if runner is not None:
                        runner.refresh()
        return errors

    def _runner_of(self, node_id: str) -> MarqueeRunner | None:
        """The scroll of the Marquee that the node ``node_id`` is, or is the text of."""
        kind = self.kinds.get(node_id)
        tre = self.nodes.get(node_id)
        if tre is None or kind not in (MARQUEE, MARQUEE_TEXT):
            return None
        box = tre if kind == MARQUEE else tre.parent()
        return self.runners.get(box) if box is not None else None

    def dispose(self) -> None:
        """Free the whole subtree. Safe to call twice."""
        if self.disposed:
            return
        self.disposed = True
        for runner in self.runners.values():
            runner.stop()
        self.runners.clear()
        for root in self.roots:
            root.destroy()
        self.roots.clear()
        self.nodes.clear()


def _suggest(word: str, choices: Sequence[str]) -> str:
    close = difflib.get_close_matches(word, list(choices), n=3, cutoff=0.5)
    if close:
        return f"did you mean {', '.join(close)}?"
    return f"allowed: {', '.join(sorted(choices))}"


def _convert(key: str, row: KeyRow, value: Value, errors: list[BindError]) -> dict[str, Any] | None:
    if isinstance(value, SlotValue):
        errors.append(BindError(f"{key}: a slot was not evaluated", value.origin))
        return None
    if isinstance(value, TokenRef):
        errors.append(BindError(f"{key}: the token ${value.path} was not resolved", value.origin))
        return None
    try:
        return CONVERTERS[row.convert](value, row.tre, row.choices)
    except BindError as exc:
        errors.append(BindError(f"{key}: {exc.message}", exc.origin, exc.hint))
        return None


def convert_states(node: Node, errors: list[BindError]) -> dict[str, dict[str, Any]]:
    """The tre properties of each of ``node``'s style states, by the table row that converts the
    same key in the base style. An empty state is left out."""
    row = BLOCKS.get(node.kind)
    out: dict[str, dict[str, Any]] = {}
    if row is None:
        return out
    for state, values in node.states.items():
        props: dict[str, Any] = {}
        for key, value in values.items():
            key_row = row.style.get(key)
            if key_row is None:
                hint = _suggest(key, list(row.style))
                errors.append(
                    BindError(
                        f"unknown key {key} in the {state} style of {node.kind}", value.origin, hint
                    )
                )
                continue
            converted = _convert(key, key_row, value, errors)
            if converted is not None:
                props.update(converted)
        if props:
            out[state] = props
    return out


def entry_states(node: Node) -> dict[str, dict[str, Any]]:
    """What a built node shows and listens for: its converted state styles. A kind tre sends no
    pointer events (a ``Text``) has no ``hovered`` or ``pressed``; its ``disabled`` still shows."""
    states = convert_states(node, [])
    if node.kind in NO_POINTER_BLOCKS:
        return {s: v for s, v in states.items() if s == "disabled"}
    return states


def _plan(
    node: Node | UseNode | IfNode | ForNode,
    path: str,
    extra: dict[str, Any],
    errors: list[BindError],
    index: _Index,
    seen: dict[str, Origin],
) -> dict[str, Any] | None:
    if isinstance(node, UseNode):
        hint = "the model expands a module call before binding"
        errors.append(
            BindError(f"the module call {node.module} was not expanded", node.origin, hint)
        )
        return None
    if isinstance(node, IfNode | ForNode):
        word = "If" if isinstance(node, IfNode) else "For"
        hint = "the model resolves it to the blocks that show before binding"
        errors.append(BindError(f"{word} was not resolved", node.origin, hint))
        return None
    index.nodes[path] = node.origin
    row: BlockRow | None = BLOCKS.get(node.kind)
    if row is None:
        errors.append(
            BindError(f"unknown block {node.kind}", node.origin, _suggest(node.kind, list(BLOCKS)))
        )
        return None

    props: dict[str, Any] = {}
    for key in node.props.keys() & node.style.keys():
        errors.append(
            BindError(
                f"{key} is written both in the block and in its Style",
                node.style[key].origin,
                f"keep one; the other is at {node.props[key].origin}",
            )
        )
    for scope, values, allowed in (
        ("", node.props, {**row.style, **row.keys}),  # a style key may be written on the block
        ("Style ", node.style, row.style),
    ):
        for key, value in values.items():
            key_row = allowed.get(key)
            if key_row is None:
                errors.append(
                    BindError(
                        f"unknown {scope}key {key} in {node.kind}",
                        value.origin,
                        _suggest(key, list(allowed)),
                    )
                )
                continue
            converted = _convert(key, key_row, value, errors)
            if converted is None:
                continue
            props.update(converted)
            for tre_name in converted:
                index.props[(path, tre_name)] = value.origin
    convert_states(node, errors)  # a state style is checked like the base style
    errors.extend(check_motion(node))
    for need in row.required:
        options = (need,) if isinstance(need, str) else need
        if not any(k in node.props or k in node.style for k in options):
            errors.append(BindError(f"{node.kind} needs {' or '.join(options)}", node.origin))
    if node.children and not row.children_ok:
        errors.append(BindError(f"{node.kind} cannot have children", node.origin))

    for name, default in row.defaults.items():
        props.setdefault(name, default)
    props.update(row.fixed)
    props.update(extra)
    if node.kind == "Spacer":  # no pointer events unless it has a click to run
        props.setdefault("hit_testable", "On_Click" in node.handlers)
    if node.kind in DECORATIVE:  # an image or a shape is not announced unless it has a Label
        props.setdefault("a11y_hidden", "label" not in props)
    if row.post:
        POSTS[row.post](props, node)

    spec: dict[str, Any] = {"kind": row.tre_kind, "props": props}
    block_word = node.kind
    if node.name is not None:
        if node.name in seen:
            errors.append(BindError(f'the name "{node.name}" is used twice', node.origin))
        seen[node.name] = node.origin
        spec["id"] = node.name
        index.named[node.name] = (block_word, props)
    children: list[dict[str, Any]] = []
    for child in node.children:
        child_path = f"{path}.children[{len(children)}]"
        planned = _plan(child, child_path, dict(row.child_props), errors, index, seen)
        if planned is not None:
            children.append(planned)
    if children:
        spec["children"] = children
    return spec


def _translate(exc: ValueError, index: _Index, fallback: Origin) -> BindError:
    message = str(exc)
    m = _TRE_ERROR.match(message)
    if m is None:
        return BindError(message, fallback)
    path = m["path"]
    origin = index.nodes.get(path, fallback)
    if m["id"]:
        return BindError(m["message"], origin)
    prop = _TRE_PROP.search(m["message"])
    if prop and (path, prop["prop"]) in index.props:
        origin = index.props[(path, prop["prop"])]
    return BindError(m["message"], origin)


def build(
    nodes: Sequence[Node | UseNode | IfNode | ForNode],
    window: Window,
    parent: TreNode | None = None,
) -> View:
    """Bind ``nodes`` under ``parent`` (default ``window.root``). Raises :class:`BindFailed` and
    builds nothing if any value is wrong."""
    errors: list[BindError] = []
    plans: list[tuple[dict[str, Any], _Index, Origin]] = []
    seen: dict[str, Origin] = {}
    for node in nodes:
        index = _Index()
        spec = _plan(node, "spec", {}, errors, index, seen)
        if spec is not None:
            plans.append((spec, index, node.origin))
    if errors:
        errors.sort(key=lambda e: (e.origin.file, e.origin.line, e.origin.column))
        raise BindFailed(errors)

    built: list[tuple[TreNode, dict[str, TreNode]]] = []
    try:
        for spec, index, origin in plans:
            try:
                built.append(window.build(spec))
            except ValueError as exc:
                raise BindFailed([_translate(exc, index, origin)]) from exc
    except BindFailed:
        for root, _ in built:
            root.destroy()
        raise
    view = View(window, [], {}, parent=parent)
    typed_roots = [n for n in nodes if isinstance(n, Node)]
    for node, (spec, _, _), (root, _named) in zip(typed_roots, plans, built, strict=True):
        view.entries.append(make_entry(node, spec, root))
        (parent or window.root).add_child(root)
    view.reindex()
    return view


def make_entry(node: Node, spec: dict[str, Any], tre: TreNode) -> Entry:
    """The entry of a built node and, below it, of its children (the spec and the tre node mirror
    the typed tree one to one)."""
    kids = [c for c in node.children if isinstance(c, Node)]
    specs = spec.get("children", [])
    tre_kids = tre.children() if kids else []
    return Entry(
        node,
        tre,
        dict(spec["props"]),
        [make_entry(c, sp, t) for c, sp, t in zip(kids, specs, tre_kids, strict=True)],
        states=entry_states(node),
        motion=motion_of(node),
    )
