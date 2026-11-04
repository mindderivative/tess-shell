"""Slots become links: compile once, evaluate to build, re-evaluate only what changed
(TEL Integration > Compiling, The Link Table and Updates).

Imports ``tess_el``; never ``tess_re``. The surfaces call :meth:`LiveTree.resolve` before the
build and :meth:`LiveTree.apply_changes` when the store reports changes, and hand the result to
``View.update``.
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


def _touches(reads: frozenset[str], key: str) -> bool:
    """A change to ``key`` matches a read of ``key`` or of a path under it."""
    return any(r == key or r.startswith(key + ".") for r in reads)


@dataclass(slots=True)
class LiveTree:
    store: ValueStore
    uses: Mapping[str, Use]
    links: list[Link] = field(default_factory=list)
    by_use: dict[str, list[Link]] = field(default_factory=dict)
    errors: int = 0

    # -- build --------------------------------------------------------------------------------

    def resolve(self, expanded: Expanded) -> list[m.Node]:
        """The expanded nodes with every slot replaced by its first value (or left unset)."""
        return [self._node(n, expanded.owner) for n in expanded.nodes]

    def _node(self, node: m.Node, owner: Mapping[str, str]) -> m.Node:
        props = dict(node.props)
        style = dict(node.style)
        use = owner.get(node.name or "")
        for scope, table in (("props", props), ("style", style)):
            for key, value in list(table.items()):
                if not isinstance(value, m.SlotValue):
                    continue
                del table[key]
                if use is None or node.name is None:
                    continue
                link = self._link(use, node, scope, key, value)
                if link is None:
                    continue
                typed = self._evaluate(link)
                if typed is not None:
                    table[key] = typed
                    link.last = typed
        children = tuple(
            self._node(c, owner) if isinstance(c, m.Node) else c for c in node.children
        )
        return dataclasses.replace(node, props=props, style=style, children=children)

    def _link(
        self, use: str, node: m.Node, scope: str, key: str, value: m.SlotValue
    ) -> Link | None:
        row = blocks.BLOCKS.get(node.kind)
        kind = (row[0] if scope == "props" else row[1]).get(key) if row else None
        if kind is None and row is not None:
            kind = (row[1] if scope == "props" else row[0]).get(key)
        if kind is None or node.name is None:
            return None
        parts: list[str | tess_el.Expression] = []
        for part in value.parts:
            if isinstance(part, str):
                parts.append(part)
                continue
            origin = tess_el.Origin(part.origin.file, part.origin.line, part.origin.column)
            try:
                parts.append(
                    tess_el.compile_expression(part.text, language=TEL_LANGUAGE, origin=origin)
                )
            except tess_el.TelError as exc:
                self._report(exc)
                return None
        link = Link(
            use=use,
            node_id=node.name,
            block=node.kind,
            key=key,
            kind=kind,
            choices=blocks.CHOICES.get((node.kind, key)) or blocks.CHOICES.get(("*", key)) or (),
            origin=value.origin,
            parts=tuple(parts),
            single=value.single,
        )
        self.links.append(link)
        self.by_use.setdefault(use, []).append(link)
        return link

    # -- evaluate -----------------------------------------------------------------------------

    def _report(self, exc: Exception) -> None:
        self.errors += 1
        hint = getattr(exc, "hint", "")
        where = f"{getattr(exc, 'file', '')}:{getattr(exc, 'line', 0)}:{getattr(exc, 'column', 0)}"
        message = getattr(exc, "message", str(exc))
        logger.warning(f"{where}: {message}" + (f" ({hint})" if hint else ""))

    def _evaluate(self, link: Link) -> m.Value | None:
        """Evaluate ``link`` in its use's scope; keep ``reads`` current; ``None`` on an error."""
        use = self.uses[link.use]
        scope = UseScope(use.params, self.store.snapshot(link.use))
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
            logger.warning(
                f"{link.origin}: {link.key}: {exc.message}" + (f" ({exc.hint})" if exc.hint else "")
            )
            return None

    # -- update -------------------------------------------------------------------------------

    def apply_changes(self, changes: list[Change]) -> list[tuple[str, str, m.Value]]:
        """The ``View.update`` entries for the links the changed keys touch; only links whose value
        really changed are returned. A link that errors keeps its last value."""
        by_use: dict[str, set[str]] = {}
        for change in changes:
            by_use.setdefault(change.use, set()).add(change.key)
        out: list[tuple[str, str, m.Value]] = []
        for use, keys in by_use.items():
            for link in self.by_use.get(use, ()):
                if not any(_touches(link.reads, key) for key in keys):
                    continue
                typed = self._evaluate(link)
                if typed is None or typed == link.last:
                    continue
                link.last = typed
                out.append((link.node_id, link.key, typed))
        return out
