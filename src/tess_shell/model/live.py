"""Slots become links, conditions and repeaters become structure (TEL Integration).

Compile once, evaluate to build, re-evaluate only what changed. A use whose layout has no ``If``
or ``For`` keeps one link per slot and changes one node property at a time. A use that has one is
resolved again whole when anything its slots, conditions or headers read changes, and the binder's
``View.rebuild`` keeps what is the same.

Imports ``tess_el``; never ``tess_re``. The surfaces call :meth:`LiveTree.resolve` before a build
or rebuild and :meth:`LiveTree.apply_changes` when the store reports changes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import tess_el
from loguru import logger

from tess_shell.binder import model as m
from tess_shell.model import args
from tess_shell.model.args import TEL_LANGUAGE
from tess_shell.model.expand import CallFactory, Expanded, ExpandedTooltip, _ephemeral
from tess_shell.model.look import Look, resolve
from tess_shell.model.store import Change, ValueStore
from tess_shell.model.uses import MapScope, Use, UseScope
from tess_shell.schema import blocks
from tess_shell.schema.values import ValueProblem, from_python


@dataclass(slots=True)
class Link:
    """One slotted value: the node it feeds, the key, the compiled parts and what they last read."""

    use: str
    node_id: str
    block: str
    key: str
    kind: str
    choices: tuple[str, ...]
    origin: m.Origin
    parts: tuple[str | tess_el.Expression, ...]
    single: bool
    reads: frozenset[str] = frozenset()
    last: m.Value | None = None


@dataclass(frozen=True, slots=True)
class Changes:
    """What a store change means for a surface: node updates, or a rebuild of the whole tree."""

    updates: list[tuple[str, str, m.Value]]
    rebuild: bool


@dataclass(frozen=True, slots=True)
class _Ctx:
    use: str  # the key of the use whose layout is being resolved
    scope: Any | None = None  # a TEL scope of an entry; None is the use's own scope
    prefix: str = ""  # prepended to the ids inside a For entry
    dynamic: bool = False  # inside an If or For: no fast-path links
    entries: tuple[Any, ...] = ()  # the For entries around the block, outermost first
    outer: _Ctx | None = None  # where the call of the module being resolved was written
    trail: str = ""  # the For blocks and entries around, by place and name: the key of a use


def _touches(reads: frozenset[str] | set[str], key: str) -> bool:
    """A change to ``key`` matches a read of ``key`` or of a path under it."""
    return any(r == key or r.startswith(key + ".") for r in reads)


def _plain(value: m.Value) -> Any:
    """The Python value of an evaluated param (a string, a number or a boolean)."""
    if isinstance(value, m.Text | m.Number | m.Bool):
        return value.value
    raise TypeError(f"not a param value: {value!r}")


def _pos(origin: m.Origin) -> tess_el.Origin:
    return tess_el.Origin(origin.file, origin.line, origin.column)


@dataclass(slots=True)
class LiveTree:
    store: ValueStore
    uses: Mapping[str, Use]
    links: list[Link] = field(default_factory=list)
    by_use: dict[str, list[Link]] = field(default_factory=dict)
    reads: dict[str, set[str]] = field(default_factory=dict)  # per use: everything any slot read
    structural: set[str] = field(default_factory=set)  # uses with an If or For in their layout
    repeaters: dict[str, tuple[tess_el.Repeater, tess_el.RepeaterState]] = field(
        default_factory=dict
    )
    conditions: dict[str, tess_el.Condition] = field(default_factory=dict)
    # params written as slots on a call: what each use's params hold now (over its declared
    # defaults), and the links that keep them current; a link's ``use`` is the scope it reads
    # (the use that holds the call) and its ``node_id`` the use whose param it feeds
    dynamic_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    param_links: list[Link] = field(default_factory=list)
    errors: int = 0
    look: Look | None = None  # the theme tokens a ``$group.name`` reads
    # a Popup's content: the ``caller`` record its slots read (Events and Actions > caller.data)
    caller: Mapping[str, Any] | None = None
    _owner: Mapping[str, str] = field(default_factory=dict)
    # the uses made for the entries of a For (Module File > Using a Module in a Structure): the
    # ones the last resolve made, what each call expanded to (kept while its entry lasts), and
    # who is told when one comes or its params change
    dyn_uses: dict[str, Use] = field(default_factory=dict)
    activate: Callable[[Use], None] | None = None
    _calls: dict[str, Expanded] = field(default_factory=dict)
    _known: dict[str, Use] = field(default_factory=dict)
    _factory: CallFactory | None = None
    _dyn_tips: dict[str, ExpandedTooltip] = field(default_factory=dict)
    _tips_out: dict[str, ExpandedTooltip] | None = None
    _roots_out: dict[str, str] | None = None
    _call_roots: dict[str, str] = field(default_factory=dict)  # use key -> its root block id
    _tips_added: set[str] = field(default_factory=set)

    # -- resolve ------------------------------------------------------------------------------

    def resolve(self, expanded: Expanded) -> list[m.Node]:
        """The expanded tree with every slot replaced by its value, every ``If`` by the branch that
        shows and every ``For`` by one copy of its body per entry."""
        self.links.clear()
        self.by_use.clear()
        self.reads.clear()
        self.structural.clear()
        self._owner = expanded.owner
        self._factory = expanded.factory
        self._tips_out = expanded.tooltips
        self._roots_out = expanded.roots
        seen = self.dyn_uses
        self.dyn_uses = {}
        self._params(expanded.uses)
        nodes, problems = resolve(self._list(tuple(expanded.nodes), None), self.look)
        for key in [k for k in self._calls if k not in self.dyn_uses]:
            del self._calls[key]  # its entry is gone
        for key in seen.keys() - self.dyn_uses.keys():
            self._known.pop(key, None)
            gone = self._call_roots.pop(key, None)
            if gone is not None and self._roots_out is not None:
                self._roots_out.pop(key, None)
        for problem in problems:
            self.errors += 1
            hint = f" ({problem.hint})" if problem.hint else ""
            logger.warning(f"{problem.origin}: {problem.message}{hint}")
        return nodes

    def release(self) -> None:
        """The surface this tree resolved is gone (a Popup closed): take back what its entries added
        to the shared :class:`Expanded` (their root blocks and tooltips)."""
        for key in self._call_roots:
            if self._roots_out is not None:
                self._roots_out.pop(key, None)
        for name in self._tips_added:
            if self._tips_out is not None:
                self._tips_out.pop(name, None)
        self._tips_added.clear()
        self._call_roots.clear()

    def _scope(self, use: str) -> UseScope:
        shell = {"caller": self.caller} if self.caller is not None else None
        known = self.dyn_uses.get(use) or self.uses[use]
        params = known.params
        if use in self.dynamic_params:
            params = {**params, **self.dynamic_params[use]}
        return UseScope(params, self.store.snapshot(use), shell)

    # -- params written as slots ----------------------------------------------------------------

    def _params(self, uses: Sequence[Use]) -> None:
        """Evaluate the params the calls of ``uses`` wrote as slots, outer calls first, so a
        param that reads another call's param finds it. A Popup's own blocks read ``caller``."""
        self.param_links.clear()
        self.dynamic_params.clear()
        for use in uses:
            for name, (slot, kind) in use.slots.items():
                link = self._compile(use.outer, use.key, "params", name, kind, slot)
                if link is None:
                    continue
                scope = (
                    None
                    if use.outer
                    else MapScope({"caller": self.caller} if self.caller is not None else {})
                )
                typed = self._evaluate(link, scope)
                if typed is None:
                    continue  # the declared default stays; the reason was logged
                link.last = typed
                self.dynamic_params.setdefault(use.key, {})[name] = _plain(typed)
                if use.outer:
                    self.param_links.append(link)

    def _refresh_params(self, changes: Sequence[Change]) -> list[Change]:
        """The changes of the keys ``changes`` make to the params of calls that read them: each
        becomes a change of ``params`` of the use it feeds, which in turn may feed another."""
        queue = list(changes)
        extra: list[Change] = []
        i = 0
        while i < len(queue):
            change = queue[i]
            i += 1
            for link in self.param_links:
                if link.use != change.use or not _touches(link.reads, change.key):
                    continue
                typed = self._evaluate(link)
                if typed is None or typed == link.last:
                    continue
                link.last = typed
                self.dynamic_params.setdefault(link.node_id, {})[link.key] = _plain(typed)
                fed = Change(link.node_id, "params")
                queue.append(fed)
                extra.append(fed)
        return extra

    def _list(
        self, nodes: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...], ctx: _Ctx | None
    ) -> list[m.Node]:
        out: list[m.Node] = []
        for node in nodes:
            if isinstance(node, m.Node):
                out.append(self._node(node, ctx))
            elif isinstance(node, m.IfNode):
                out.extend(self._if(node, ctx))
            elif isinstance(node, m.ForNode):
                out.extend(self._for(node, ctx))
            else:
                out.extend(self._call(node, ctx))
        return out

    def _call(self, node: m.UseNode, ctx: _Ctx | None) -> list[m.Node]:
        """A module call in the body of a ``For``: the use for this entry (made now, when the
        entry's key is known, and kept while the entry lasts) and its blocks. The key of the use
        comes from the use that holds the For and the entry's place in it, so the same entry has
        the same use however the list is reordered, and the keyed diff keeps its nodes."""
        factory = self._factory
        outer = (self.dyn_uses.get(ctx.use) or self.uses.get(ctx.use)) if ctx else None
        if factory is None or ctx is None or outer is None:
            return []
        label = node.name or f"{node.module}_{node.ordinal}"
        name = f"{outer.name}.{ctx.trail}{label}"
        key = f"{node.module}@{_ephemeral(name)}"
        made = self._calls.get(key)
        if made is None:
            made = self._calls[key] = factory.make(node, outer, key, name)
            for error in made.errors:
                self._report(error)
            self._dyn_tips.update(made.tooltips)
            self._call_roots.update({u: f"{ctx.prefix}{n}" for u, n in made.roots.items()})
        if self._roots_out is not None:
            # a Popup can open beside an entry's use: its root block's id carries the entry's prefix
            self._roots_out.update({u: f"{ctx.prefix}{n}" for u, n in made.roots.items()})
        base = ctx.scope if ctx.scope is not None else self._scope(ctx.use)
        for i, planned in enumerate(made.uses):
            scope = base if i == 0 else None
            params = dict(planned.params)
            for pname, (slot, kind) in planned.slots.items():
                link = self._compile(planned.outer, planned.key, "params", pname, kind, slot)
                if link is None:
                    continue
                typed = self._evaluate(link, scope)
                self.reads.setdefault(planned.outer, set()).update(link.reads)
                if typed is not None:
                    params[pname] = _plain(typed)
            use = dataclasses.replace(planned, params=params, slots={})
            self.dyn_uses[use.key] = use
            self.structural.add(use.outer)
            if self._known.get(use.key) != use:
                self._known[use.key] = use
                if self.activate is not None:
                    self.activate(use)
        return self._list(tuple(made.nodes), ctx)

    def _node(self, node: m.Node, ctx: _Ctx | None) -> m.Node:
        if node.owner is not None:  # the use the block was written in (the caller, for content)
            use = node.owner
        else:
            use = ctx.use if ctx else self._owner.get(node.name or "", "")
        # a block of a Popup in a shell file has no module: its slots read ``caller`` alone
        popup_scope = MapScope({"caller": self.caller}) if self.caller is not None else None
        here = ctx or _Ctx(use, scope=None if use else popup_scope)
        if node.owner is not None and ctx is not None and ctx.use != use:
            # a module's layout inside another's, or the caller's content inside a module's: the
            # scope of the use the block was written in, not of the layout around it
            here = _Ctx(
                use,
                scope=None if use else popup_scope,
                prefix=ctx.prefix,
                dynamic=ctx.dynamic,
                outer=ctx,
            )
            caller: _Ctx | None = ctx
            while caller is not None and caller.use != use:
                caller = caller.outer
            if caller is not None:
                # content written on a call inside a For entry reads the entry's variables
                here = dataclasses.replace(caller, prefix=ctx.prefix, dynamic=ctx.dynamic)
        if use and here.dynamic:
            # a block of a module called inside an If or For: it has no link of its own (it may
            # not be there next turn), so a change to what that module's slots read resolves the
            # tree again
            self.structural.add(use)
        name = f"{here.prefix}{node.name}" if node.name and here.prefix else node.name
        if name is not None and node.name in self._dyn_tips and self._tips_out is not None:
            self._tips_out[name] = self._dyn_tips[node.name]  # the tooltip of an entry's block
            self._tips_added.add(name)
        props = dict(node.props)
        style = dict(node.style)
        for scope, table in (("props", props), ("style", style)):
            for key, value in list(table.items()):
                if not isinstance(value, m.SlotValue):
                    continue
                del table[key]
                if not use and here.scope is None:
                    continue
                typed = self._slot(node, name, scope, key, value, here)
                if typed is not None:
                    table[key] = typed
        children = self._list(node.children, dataclasses.replace(here, use=use) if use else None)
        handlers = node.handlers
        if node.handlers and (use or here.entries):
            handlers = {
                k: dataclasses.replace(
                    h,
                    use=h.use if h.forwarded else use or h.use,
                    # a handler written on a call reads the entry the call is in
                    entries=ctx.entries if h.forwarded and ctx is not None else here.entries,
                )
                for k, h in node.handlers.items()
            }
        for handler in handlers.values():
            for exc in args.check(handler):  # a typo in an argument is found at load
                self._report(exc)
        return dataclasses.replace(
            node, name=name, props=props, style=style, children=tuple(children), handlers=handlers
        )

    def _slot(
        self,
        node: m.Node,
        name: str | None,
        scope: str,
        key: str,
        value: m.SlotValue,
        ctx: _Ctx,
    ) -> m.Value | None:
        row = blocks.table(node.kind)
        kind = (row[0] if scope == "props" else row[1]).get(key) if row else None
        if kind is None and row is not None:
            kind = (row[1] if scope == "props" else row[0]).get(key)
        if kind is None:
            return None
        link = self._compile(ctx.use, name or "", node.kind, key, kind, value)
        if link is None:
            return None
        typed = self._evaluate(link, ctx.scope)
        if not ctx.dynamic and name is not None:
            self.links.append(link)
            self.by_use.setdefault(ctx.use, []).append(link)
            link.last = typed
        self.reads.setdefault(ctx.use, set()).update(link.reads)
        return typed

    def _compile(
        self, use: str, node_id: str, block: str, key: str, kind: str, value: m.SlotValue
    ) -> Link | None:
        parts: list[str | tess_el.Expression] = []
        for part in value.parts:
            if isinstance(part, str):
                parts.append(part)
                continue
            try:
                parts.append(
                    tess_el.compile_expression(
                        part.text, language=TEL_LANGUAGE, origin=_pos(part.origin)
                    )
                )
            except tess_el.TelError as exc:
                self._report(exc)
                return None
        return Link(
            use=use,
            node_id=node_id,
            block=block,
            key=key,
            kind=kind,
            choices=blocks.CHOICES.get((block, key)) or blocks.CHOICES.get(("*", key)) or (),
            origin=value.origin,
            parts=tuple(parts),
            single=value.single,
        )

    # -- If and For ---------------------------------------------------------------------------

    def _condition(self, use: str, node: m.IfNode) -> tess_el.Condition | None:
        assert node.condition is not None
        key = f"{use}|{node.origin}"
        found = self.conditions.get(key)
        if found is None:
            try:
                found = tess_el.compile_condition(
                    node.condition.text,
                    language=TEL_LANGUAGE,
                    origin=_pos(node.condition.origin),
                )
            except tess_el.TelError as exc:
                self._report(exc)
                return None
            self.conditions[key] = found
        return found

    def _if(self, node: m.IfNode, ctx: _Ctx | None) -> list[m.Node]:
        use = node.use or (ctx.use if ctx else "")
        here = dataclasses.replace(ctx or _Ctx(use), use=use, dynamic=True)
        if not use or node.condition is None:
            return []
        self.structural.add(use)
        condition = self._condition(use, node)
        chosen: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...] = ()
        if condition is not None:
            scope = here.scope if here.scope is not None else self._scope(use)
            try:
                tracked = tess_el.select_tracked([condition], scope)
                self.reads.setdefault(use, set()).update(tracked.reads)
                if tracked.value == 0:
                    chosen = node.body
                elif node.else_body is not None:
                    chosen = node.else_body
            except tess_el.TelError as exc:
                self._report(exc)
                self.reads.setdefault(use, set()).update(getattr(exc, "reads", ()) or ())
        return self._list(chosen, here)

    def _for(self, node: m.ForNode, ctx: _Ctx | None) -> list[m.Node]:
        use = node.use or (ctx.use if ctx else "")
        here = dataclasses.replace(ctx or _Ctx(use), use=use, dynamic=True)
        if not use or node.items is None or node.key is None:
            return []
        self.structural.add(use)
        state_key = f"{here.prefix}{use}|{node.origin}"
        pair = self.repeaters.get(state_key)
        if pair is None:
            try:
                repeater = tess_el.compile_repeater_parts(
                    node.variable,
                    node.items.text,
                    key=node.key.text,
                    name=node.name,
                    language=TEL_LANGUAGE,
                    names_origin=_pos(node.origin),
                    items_origin=_pos(node.items.origin),
                    key_origin=_pos(node.key.origin),
                )
            except tess_el.TelError as exc:
                self._report(exc)
                return []
            pair = (repeater, tess_el.RepeaterState())
            self.repeaters[state_key] = pair
        repeater, state = pair
        base = here.scope if here.scope is not None else self._scope(use)
        try:
            tracked = repeater.reconcile_tracked(base, state)
        except tess_el.TelError as exc:
            self._report(exc)
            self.reads.setdefault(use, set()).update(getattr(exc, "reads", ()) or ())
            return []
        self.reads.setdefault(use, set()).update(tracked.reads)
        result = tracked.value
        self.repeaters[state_key] = (repeater, result.state)
        out: list[m.Node] = []
        for entry in result.entries:
            prefix = f"{here.prefix}for{node.origin.line}.{node.origin.column}/{entry.name}/"
            inner = dataclasses.replace(
                here,
                scope=entry.scope(base),
                prefix=prefix,
                entries=(*here.entries, entry),
                trail=f"{here.trail}for{node.ordinal}.{entry.name}.",
            )
            roots = self._list(node.body, inner)
            for i, root in enumerate(roots):
                if root.name is None:  # an entry's blocks are matched by the entry's name
                    root = dataclasses.replace(root, name=f"{prefix}#{i}")
                if "Key" not in root.props:  # the entry's key, which a list chooses it by
                    key = m.Text(str(entry.key), origin=root.origin)
                    root = dataclasses.replace(root, props={**root.props, "Key": key})
                out.append(root)
        return out

    # -- evaluate -----------------------------------------------------------------------------

    def _report(self, exc: Exception) -> None:
        self.errors += 1
        hint = getattr(exc, "hint", "")
        where = f"{getattr(exc, 'file', '')}:{getattr(exc, 'line', 0)}:{getattr(exc, 'column', 0)}"
        message = getattr(exc, "message", str(exc))
        logger.warning(f"{where}: {message}" + (f" ({hint})" if hint else ""))

    def _icon(self, link: Link, value: object) -> m.Value | None:
        """An icon name a module sent, as the SVG document of the icon (the same lookup a name
        written in a file goes through). A param with no name holds the empty text (the module
        shows nothing); a block's key gets an empty document."""
        if not isinstance(value, str):
            raise ValueProblem(
                "bad-value", f"expected an icon name, the slot gave a {type(value).__name__}"
            )
        if link.block == "params" and not value:
            return m.Text("", origin=link.origin)
        icons = self.look.icons if self.look is not None else None
        if icons is None:
            raise ValueProblem("bad-value", "this shell has no icon sets to look a name up in")
        return m.Text(icons.document(value), origin=link.origin)

    def _evaluate(self, link: Link, scope: Any | None = None) -> m.Value | None:
        """Evaluate ``link``; keep ``reads`` current; ``None`` on an error."""
        scope = scope if scope is not None else self._scope(link.use)
        reads: set[str] = set()
        results: list[Any] = []
        failed = False
        for part in link.parts:
            if isinstance(part, str):
                results.append(part)
                continue
            try:
                tracked = part.evaluate_tracked(scope)
            except tess_el.TelError as exc:
                reads.update(getattr(exc, "reads", ()) or ())
                if not failed:
                    self._report(exc)
                failed = True
                continue
            reads.update(tracked.reads)
            results.append(tracked.value)
        link.reads = frozenset(reads)
        if failed:
            return None
        try:
            if link.single:
                value = results[0]
                if value is None:  # ``{{ x if y else None }}``: the key is left as it is
                    return None
            else:
                value = "".join(r if isinstance(r, str) else str(r) for r in results)
            if link.kind == "icon":
                return self._icon(link, value)
            return from_python(link.kind, value, link.origin, link.choices)
        except ValueProblem as exc:
            self.errors += 1
            hint = f" ({exc.hint})" if exc.hint else ""
            logger.warning(f"{link.origin}: {link.key}: {exc.message}{hint}")
            return None

    # -- update -------------------------------------------------------------------------------

    def apply_changes(self, changes: list[Change]) -> Changes:
        """What the changed keys mean: the ``View.update`` entries for the links they touch, or
        ``rebuild`` when a use with an ``If`` or ``For`` read one of them."""
        by_use: dict[str, set[str]] = {}
        for change in [*changes, *self._refresh_params(changes)]:
            by_use.setdefault(change.use, set()).add(change.key)
        out: list[tuple[str, str, m.Value]] = []
        rebuild = False
        for use, keys in by_use.items():
            if use in self.structural:
                if any(_touches(self.reads.get(use, set()), key) for key in keys):
                    rebuild = True
                continue
            for link in self.by_use.get(use, ()):
                if not any(_touches(link.reads, key) for key in keys):
                    continue
                typed = self._evaluate(link)
                if typed is None or typed == link.last:
                    continue
                link.last = typed
                out.append((link.node_id, link.key, typed))
        return Changes(out, rebuild)
