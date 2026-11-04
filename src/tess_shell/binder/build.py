"""Build a typed tree into tre nodes (Render Binder Design > Building).

All problems are collected first, each at the position of its key; if there are any, nothing is
built, so a surface never half-builds. tre's own ``ValueError`` (which names a path such as
``spec.children[2]``) is translated back to a position through an index made while planning.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tess_shell.binder.convert import CONVERTERS
from tess_shell.binder.model import (
    BindError,
    BindFailed,
    ForNode,
    IfNode,
    Node,
    Origin,
    SlotValue,
    UseNode,
    Value,
)
from tess_shell.binder.tables import BLOCKS, BlockRow, KeyRow

if TYPE_CHECKING:
    from tess_re import Node as TreNode
    from tess_re import Window

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


@dataclass(slots=True)
class View:
    """What was built: the attached roots and the named nodes."""

    window: Window
    roots: list[TreNode]
    nodes: dict[str, TreNode]
    kinds: dict[str, str] = field(default_factory=dict)  # node id -> block word
    applied: dict[str, dict[str, Any]] = field(default_factory=dict)  # node id -> tre props set
    disposed: bool = False

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
            if fresh:
                by_node.setdefault(node_id, {}).update(fresh)
        if by_node:
            try:
                self.window.apply([(self.nodes[i], props) for i, props in by_node.items()])
            except ValueError as exc:
                for node_id in by_node:
                    errors.append(BindError(f"{node_id}: {exc}", Origin("<tre>", 1, 1)))
                return errors
            for node_id, props in by_node.items():
                self.applied[node_id].update(props)
        return errors

    def dispose(self) -> None:
        """Free the whole subtree. Safe to call twice."""
        if self.disposed:
            return
        self.disposed = True
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
    try:
        return CONVERTERS[row.convert](value, row.tre, row.choices)
    except BindError as exc:
        errors.append(BindError(f"{key}: {exc.message}", exc.origin, exc.hint))
        return None


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
        hint = "repeaters and conditions come with M2"
        errors.append(BindError(f"{word} is not supported yet", node.origin, hint))
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
    for key in row.required:
        if key not in node.props and key not in node.style:
            errors.append(BindError(f"{node.kind} needs {key}", node.origin))
    if node.children and not row.children_ok:
        errors.append(BindError(f"{node.kind} cannot have children", node.origin))

    for name, default in row.defaults.items():
        props.setdefault(name, default)
    props.update(row.fixed)
    props.update(extra)

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


def build(nodes: Sequence[Node | UseNode | IfNode | ForNode], window: Window) -> View:
    """Bind ``nodes`` under ``window.root``. Raises :class:`BindFailed` and builds nothing if
    any value is wrong."""
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
    view = View(window, [], {})
    for (_, index, _), _built in zip(plans, built, strict=True):
        for node_id, (block_word, applied) in index.named.items():
            view.kinds[node_id] = block_word
            view.applied[node_id] = dict(applied)
    for root, named in built:
        window.root.add_child(root)
        view.roots.append(root)
        view.nodes.update(named)
    return view
