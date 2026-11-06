"""``View.rebuild``: compare a new typed tree with what is built, change only what differs
(Render Binder Design > The Keyed Diff).

Identity of a child: its ``Name`` if it has one, else its block word and how many earlier siblings
share that word. A kept child gets the properties that differ in one ``Window.apply``; a changed
block word, or a property the new tree no longer sets, makes the child a replacement; the rest are
created with ``Window.build`` and the others removed. Nothing is touched until the whole new tree
has been checked, and a failure while applying leaves the old tree whole.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tess_shell.binder.build import Entry, View, Wire, _Index, _plan, entry_states, make_entry
from tess_shell.binder.model import BindError, BindFailed, ForNode, IfNode, Node, Origin, UseNode

if TYPE_CHECKING:
    from tess_re import Node as TreNode


def _key(node: Node, seen: dict[str, int]) -> str:
    if node.name is not None:
        return f"name:{node.name}"
    seen[node.kind] = seen.get(node.kind, 0) + 1
    return f"{node.kind}#{seen[node.kind]}"


@dataclass(frozen=True, slots=True)
class RebuildStats:
    """What a rebuild did: nodes whose properties were set, nodes created, nodes removed."""

    changed: int = 0
    created: int = 0
    removed: int = 0

    def __str__(self) -> str:
        return f"{self.changed} changed, {self.created} created, {self.removed} removed"


@dataclass(slots=True)
class _Plan:
    changes: list[tuple[TreNode, dict[str, Any]]] = field(default_factory=list)
    creates: list[tuple[Entry, dict[str, Any]]] = field(default_factory=list)
    removed: list[Entry] = field(default_factory=list)
    parents: list[tuple[TreNode, list[Entry]]] = field(default_factory=list)
    # a kept node's wire, its new state styles and the base values a state is holding for it
    restates: list[tuple[Wire, dict[str, dict[str, Any]], dict[str, Any]]] = field(
        default_factory=list
    )


def _diff(
    old: list[Entry],
    new_nodes: list[Node],
    specs: list[dict[str, Any]],
    parent: TreNode,
    plan: _Plan,
) -> list[Entry]:
    by_key: dict[str, Entry] = {}
    seen: dict[str, int] = {}
    for entry in old:
        by_key[_key(entry.typed, seen)] = entry
    seen = {}
    result: list[Entry] = []
    for node, spec in zip(new_nodes, specs, strict=True):
        key = _key(node, seen)
        props: dict[str, Any] = spec["props"]
        kept = by_key.get(key)
        replace = (
            kept is None
            or kept.typed.kind != node.kind
            or bool(kept.props.keys() - props.keys())  # tre cannot unset a property
        )
        if kept is not None and not replace:
            del by_key[key]
            assert kept.tre is not None
            changed = {n: v for n, v in props.items() if n not in kept.props or kept.props[n] != v}
            states = entry_states(node)
            if kept.wire is not None and (states or kept.wire.states):
                # what a state holds is not set under it; the wire keeps the new value for the end
                held = {n: changed.pop(n) for n in list(changed) if n in kept.wire.saved}
                plan.restates.append((kept.wire, states, held))
            if changed:
                plan.changes.append((kept.tre, changed))
            kids = [c for c in node.children if isinstance(c, Node)]
            entry = Entry(node, kept.tre, dict(props), [], kept.wire, states)
            if entry.wire is not None:
                entry.wire.handlers = node.handlers
            entry.children = _diff(kept.children, kids, spec.get("children", []), kept.tre, plan)
            result.append(entry)
            continue
        if kept is not None:
            del by_key[key]
            plan.removed.append(kept)
        fresh = Entry(node, None, dict(props), [], states=entry_states(node))
        plan.creates.append((fresh, spec))
        result.append(fresh)
    plan.removed.extend(by_key.values())
    plan.parents.append((parent, result))
    return result


def _destroy(entry: Entry) -> None:
    if entry.tre is not None:
        entry.tre.destroy()


def rebuild(view: View, nodes: Sequence[Node | UseNode | IfNode | ForNode]) -> RebuildStats:
    errors: list[BindError] = []
    specs: list[dict[str, Any]] = []
    seen: dict[str, Origin] = {}
    typed: list[Node] = []
    for node in nodes:
        spec = _plan(node, "spec", {}, errors, _Index(), seen)
        if spec is not None and isinstance(node, Node):
            specs.append(spec)
            typed.append(node)
    if errors:
        errors.sort(key=lambda e: (e.origin.file, e.origin.line, e.origin.column))
        raise BindFailed(errors)

    plan = _Plan()
    window = view.window
    new_entries = _diff(view.entries, typed, specs, view.parent or window.root, plan)

    built: list[tuple[Entry, TreNode]] = []
    try:
        for fresh, spec in plan.creates:
            try:
                tre, _ = window.build(spec)
            except ValueError as exc:
                raise BindFailed([BindError(str(exc), fresh.typed.origin)]) from exc
            built.append((fresh, tre))
        if plan.changes:
            try:
                window.apply(plan.changes)
            except ValueError as exc:
                raise BindFailed(
                    [BindError(str(exc), typed[0].origin if typed else Origin("<tre>", 1, 1))]
                ) from exc
    except BindFailed:
        for _, tre in built:
            tre.destroy()
        raise

    for wire, states, held in plan.restates:
        wire.restate(states, held)  # a node keeps the state the pointer has it in, restyled
    for fresh, tre in built:
        sub = make_entry(fresh.typed, _spec_of(fresh, plan), tre)
        fresh.tre, fresh.children = tre, sub.children
    for parent, entries in plan.parents:
        wanted = [e.tre for e in entries if e.tre is not None]
        if parent.children() != wanted:
            parent.set_children(wanted)
    for entry in plan.removed:
        _destroy(entry)
    view.entries = new_entries
    view.reindex()
    return RebuildStats(len(plan.changes), len(plan.creates), len(plan.removed))


def _spec_of(fresh: Entry, plan: _Plan) -> dict[str, Any]:
    for entry, spec in plan.creates:
        if entry is fresh:
            return spec
    raise AssertionError("a created entry has a spec")
