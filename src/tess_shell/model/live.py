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
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import tess_el
from loguru import logger

from tess_shell.binder import model as m
from tess_shell.model.expand import Expanded
from tess_shell.model.look import Look, resolve
from tess_shell.model.store import Change, ValueStore
from tess_shell.model.uses import Use, UseScope
from tess_shell.schema import blocks
from tess_shell.schema.values import ValueProblem, from_python

TEL_LANGUAGE = "0.1"


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


def _touches(reads: frozenset[str] | set[str], key: str) -> bool:
    """A change to ``key`` matches a read of ``key`` or of a path under it."""
    return any(r == key or r.startswith(key + ".") for r in reads)


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
    errors: int = 0
    look: Look | None = None  # the theme tokens a ``$group.name`` reads
    _owner: Mapping[str, str] = field(default_factory=dict)

    # -- resolve ------------------------------------------------------------------------------

    def resolve(self, expanded: Expanded) -> list[m.Node]:
        """The expanded tree with every slot replaced by its value, every ``If`` by the branch that
        shows and every ``For`` by one copy of its body per entry."""
        self.links.clear()
        self.by_use.clear()
        self.reads.clear()
        self.structural.clear()
        self._owner = expanded.owner
        nodes, problems = resolve(self._list(tuple(expanded.nodes), None), self.look)
        for problem in problems:
            self.errors += 1
            hint = f" ({problem.hint})" if problem.hint else ""
            logger.warning(f"{problem.origin}: {problem.message}{hint}")
        return nodes

    def _scope(self, use: str) -> UseScope:
        return UseScope(self.uses[use].params, self.store.snapshot(use))

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
        return out

    def _node(self, node: m.Node, ctx: _Ctx | None) -> m.Node:
        use = ctx.use if ctx else self._owner.get(node.name or "", "")
        here = ctx or _Ctx(use)
        name = f"{here.prefix}{node.name}" if node.name and here.prefix else node.name
        props = dict(node.props)
        style = dict(node.style)
        for scope, table in (("props", props), ("style", style)):
            for key, value in list(table.items()):
                if not isinstance(value, m.SlotValue):
                    continue
                del table[key]
                if not use:
                    continue
                typed = self._slot(node, name, scope, key, value, here)
                if typed is not None:
                    table[key] = typed
        children = self._list(node.children, dataclasses.replace(here, use=use) if use else None)
        handlers = (
            {k: dataclasses.replace(h, use=use) for k, h in node.handlers.items()}
            if use and node.handlers
            else node.handlers
        )
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
        row = blocks.BLOCKS.get(node.kind)
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
            inner = dataclasses.replace(here, scope=entry.scope(base), prefix=prefix)
            roots = self._list(node.body, inner)
            for i, root in enumerate(roots):
                if root.name is None:  # an entry's blocks are matched by the entry's name
                    root = dataclasses.replace(root, name=f"{prefix}#{i}")
                out.append(root)
        return out

    # -- evaluate -----------------------------------------------------------------------------

    def _report(self, exc: Exception) -> None:
        self.errors += 1
        hint = getattr(exc, "hint", "")
        where = f"{getattr(exc, 'file', '')}:{getattr(exc, 'line', 0)}:{getattr(exc, 'column', 0)}"
        message = getattr(exc, "message", str(exc))
        logger.warning(f"{where}: {message}" + (f" ({hint})" if hint else ""))

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
            else:
                value = "".join(r if isinstance(r, str) else str(r) for r in results)
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
        for change in changes:
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
