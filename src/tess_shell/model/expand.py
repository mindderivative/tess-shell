"""Replace each module call with the module's layout (Module File > Using a Module).

Every named node inside a use gets the use's key as a prefix, so two uses of one module never
share a node id. A node that holds a slot and has no name gets a generated one, because the binder
updates a node by id. Slots are left in place; :mod:`tess_shell.model.live` evaluates them.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from tess_shell.binder import model as m
from tess_shell.model.field import compose
from tess_shell.model.look import apply_module_rules
from tess_shell.model.marquee import compose as compose_marquee
from tess_shell.model.uses import PARAM_BLANKS, PARAM_SLOT_KINDS, Use, plain_param
from tess_shell.schema import blocks
from tess_shell.schema.model import ModuleDef, Rule

MAX_DEPTH = 8


def _ephemeral(name: str) -> str:
    """The uid of a use made for an entry of a ``For``: its dotted name, with nothing that a node
    id uses as a separator. Such a use exists while its entry does, so it has no place in the
    registry that remembers the uids of the uses in the files."""
    return name.replace("/", ":")


@dataclass(slots=True)
class ExpandedTooltip:
    """A tooltip of a block or a use: what was written (an inline Popup or a Popup's ``Name``)
    and, for an inline one, its content expanded in the scope of the use that holds it, so a
    slot in it reads that use's values."""

    ref: m.TooltipRef
    nodes: list[m.Node | m.IfNode | m.ForNode] = field(default_factory=list)
    use: str = ""  # the key of the use that holds it; empty in a shell file


@dataclass(slots=True)
class Expanded:
    nodes: list[m.Node | m.IfNode | m.ForNode] = field(default_factory=list)
    uses: list[Use] = field(default_factory=list)
    owner: dict[str, str] = field(default_factory=dict)  # node id -> use key
    errors: list[m.BindError] = field(default_factory=list)
    # a use's ``Name`` -> the id of its root node, for a Panel attached to the module
    targets: dict[str, str] = field(default_factory=dict)
    # a use's key -> the id of its first root block: the rectangle a Popup opens beside
    roots: dict[str, str] = field(default_factory=dict)
    # a node id (a block's, or a use's first root block) -> the tooltip it opens on hover
    tooltips: dict[str, ExpandedTooltip] = field(default_factory=dict)
    # the modules called inside a ``For`` (and the modules those call): a use of one is made for
    # each entry while the shell runs, so the module has to be loaded though nothing uses it yet
    dynamic_modules: set[str] = field(default_factory=set)
    # expands a module call of a ``For`` body for one entry (see :class:`CallFactory`)
    factory: CallFactory | None = None


class CallFactory:
    """What the live tree uses to expand a module call that sits in a ``For`` body, once for each
    entry, when the entry's key is known (the call cannot be expanded when the file is read: the
    entries do not exist yet). The expansion is the one a call outside a ``For`` gets, with the
    key and the dotted name the live tree chooses."""

    def __init__(
        self,
        modules: Mapping[str, ModuleDef],
        uid_of: Callable[[str], str],
        monitor: str,
        rules: Sequence[Rule],
    ) -> None:
        self.modules = modules
        self.uid_of = uid_of
        self.monitor = monitor
        self.rules = rules

    def make(self, call: m.UseNode, outer: Use, key: str, name: str) -> Expanded:
        """``call`` as the use ``key`` (dotted name ``name``) of ``outer``'s layout: its blocks in
        ``nodes``, its ``uses`` (the call's own first, then the modules its layout calls), and the
        tooltips, roots and errors of the expansion."""
        sub = _Expander(self.modules, self.uid_of, self.monitor, self.rules)
        sub.out.nodes = sub._use(call, name, (), outer, key, name)  # noqa: SLF001
        return sub.out


def _called(
    nodes: Sequence[Any], modules: Mapping[str, ModuleDef], into: set[str], depth: int = 0
) -> None:
    """The names of the modules called in ``nodes``, and in the layouts of those, at any depth."""
    for node in nodes:
        if isinstance(node, m.UseNode):
            if node.module not in into and node.module in modules and depth < MAX_DEPTH:
                into.add(node.module)
                _called(modules[node.module].children, modules, into, depth + 1)
            _called(node.children, modules, into, depth)
        elif isinstance(node, m.Node):
            _called(node.children, modules, into, depth)
        elif isinstance(node, m.IfNode):
            _called(node.body, modules, into, depth)
            _called(node.else_body or (), modules, into, depth)
        elif isinstance(node, m.ForNode):
            _called(node.body, modules, into, depth)


def _has_content(children: Sequence[Any]) -> bool:
    """Whether a module's layout has a ``Content`` marker."""
    for c in children:
        if isinstance(c, m.Node):
            if c.kind == m.CONTENT or _has_content(c.children):
                return True
        elif isinstance(c, m.IfNode):
            if _has_content(c.body) or _has_content(c.else_body or ()):
                return True
        elif isinstance(c, m.ForNode) and _has_content(c.body):
            return True
    return False


def _has_slot(node: m.Node) -> bool:
    return any(isinstance(v, m.SlotValue) for v in (*node.props.values(), *node.style.values()))


class _Expander:
    def __init__(
        self,
        modules: Mapping[str, ModuleDef],
        uid_of: Callable[[str], str],
        monitor: str,
        rules: Sequence[Rule] = (),
        attach_targets: frozenset[str] = frozenset(),
        mark_roots: bool = False,
        in_popup: bool = False,
    ) -> None:
        self.attach_targets = attach_targets
        self.mark_roots = mark_roots
        # inside a Popup's content a slot may read ``caller`` (Events and Actions > caller.data),
        # so a block of a shell file may hold one; elsewhere a slot needs a module's scope
        self.popup_depth = 1 if in_popup else 0
        self.rules = rules
        self.modules = modules
        self.uid_of = uid_of
        self.monitor = monitor
        self.out = Expanded()
        self._counts: dict[str, int] = {}
        self._in_for = 0  # inside the body of a ``For``: a module call stays a call (see _walk)
        # the content written on the calls being expanded, innermost last: a ``Content`` marker of
        # a module's layout is replaced by the top one
        self._content: list[list[m.Node | m.IfNode | m.ForNode]] = []

    def run(self, nodes: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...], path: str) -> None:
        self.out.nodes = self._walk(nodes, path, None, ())

    def _walk(
        self,
        nodes: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...],
        path: str,
        use: Use | None,
        stack: tuple[str, ...],
        dynamic: bool = False,
    ) -> list[m.Node | m.IfNode | m.ForNode]:
        result: list[m.Node | m.IfNode | m.ForNode] = []
        for node in nodes:
            if isinstance(node, m.UseNode):
                if self._in_for:
                    # only a ``For`` body holds a call: the model expands it for each entry
                    result.append(self._for_call(node, path, stack, use))  # type: ignore[arg-type]
                else:
                    result.extend(self._use(node, path, stack, use))
            elif isinstance(node, m.Node) and node.kind == m.CONTENT:
                result.extend(self._content[-1] if self._content else ())
            elif isinstance(node, m.Node):
                result.append(self._node(node, path, use, stack, dynamic))
            else:
                result.append(self._structure(node, path, use, stack))
        return result

    def _structure(
        self, node: m.IfNode | m.ForNode, path: str, use: Use | None, stack: tuple[str, ...]
    ) -> m.Node | m.IfNode | m.ForNode:
        """An ``If`` or ``For``: its blocks keep their names (given the use's prefix) and slots;
        the model resolves which show, and gives each ``For`` entry its own ids."""
        if use is None:
            self.out.errors.append(
                m.BindError("If and For outside a module are not built yet", node.origin)
            )
        if isinstance(node, m.IfNode):
            else_body = (
                None
                if node.else_body is None
                else tuple(self._walk(node.else_body, path, use, stack, dynamic=True))
            )
            return dataclasses.replace(
                node,
                body=tuple(self._walk(node.body, path, use, stack, dynamic=True)),
                else_body=else_body,
                use=use.key if use else "",
            )
        ordinal = self._next(f"for:{use.key if use else path}")
        self._in_for += 1
        try:
            body = tuple(self._walk(node.body, path, use, stack, dynamic=True))
        finally:
            self._in_for -= 1
        return dataclasses.replace(node, body=body, use=use.key if use else "", ordinal=ordinal)

    def _next(self, counter: str) -> int:
        n = self._counts.get(counter, 0)
        self._counts[counter] = n + 1
        return n

    def _for_call(
        self, call: m.UseNode, path: str, stack: tuple[str, ...], outer: Use | None
    ) -> m.UseNode:
        """A module call in the body of a ``For``: one use for each entry, made when the entries
        are known (:class:`CallFactory`), so the call stays in the tree. It is expanded once here,
        as a use that is thrown away, to find what is wrong with it now: a handler the module's
        root cannot raise, a Content it has no place for, a cycle."""
        if outer is None:
            self.out.errors.append(
                m.BindError("If and For outside a module are not built yet", call.origin)
            )
            return call
        if self.popup_depth:
            self.out.errors.append(
                m.BindError("a module call inside a For in a Popup is not built yet", call.origin)
            )
            return call
        trial = _Expander(self.modules, _ephemeral, self.monitor, self.rules)
        trial._use(call, path, stack, outer, f"{call.module}@trial", f"{path}.trial")  # noqa: SLF001
        self.out.errors.extend(trial.out.errors)
        _called([call], self.modules, self.out.dynamic_modules)
        return dataclasses.replace(call, ordinal=self._next(f"call:{outer.key}"))

    def _node(
        self,
        node: m.Node,
        path: str,
        use: Use | None,
        stack: tuple[str, ...],
        dynamic: bool = False,
    ) -> m.Node:
        # a TextField becomes its box, size text and text input; a Marquee its box and its text
        node = compose_marquee(compose(node))
        name = node.name
        if use is not None:
            if name is not None:
                name = f"{use.key}/{name}"
            elif _has_slot(node) and not dynamic:
                n = self._counts.get(use.key, 0)
                self._counts[use.key] = n + 1
                name = f"{use.key}/#{n}"
            if name is not None:
                self.out.owner[name] = use.key
        elif _has_slot(node) and not self.popup_depth:
            for v in (*node.props.values(), *node.style.values()):
                if isinstance(v, m.SlotValue):
                    self.out.errors.append(
                        m.BindError("a slot outside a module is not built yet", v.origin)
                    )
        if node.tooltip is not None:
            name = self._tooltip(node, name, path, use, stack, dynamic)
        children = self._walk(node.children, path, use, stack, dynamic)
        # the block's slots and handlers read the scope of the use it was written in
        owner = use.key if use is not None else ""
        return dataclasses.replace(
            node, name=name, children=tuple(children), tooltip=None, owner=owner
        )

    def _tooltip(
        self,
        node: m.Node,
        name: str | None,
        path: str,
        use: Use | None,
        stack: tuple[str, ...],
        dynamic: bool,
    ) -> str | None:
        """A block with a ``Tooltip``: it gets an id (the surface finds its tre node by it) and
        the tooltip's own content is expanded in the scope of the use that holds the block."""
        assert node.tooltip is not None
        if dynamic:
            self.out.errors.append(
                m.BindError("a Tooltip inside If or For is not built yet", node.tooltip.origin)
            )
            return name
        if name is None:
            owner = use.key if use is not None else path
            n = self._counts.get(f"tip:{owner}", 0)
            self._counts[f"tip:{owner}"] = n + 1
            name = f"{owner}/#tip{n}"
            if use is not None:
                self.out.owner[name] = use.key
        self._register_tooltip(name, node.tooltip, path, use, stack)
        return name

    def _register_tooltip(
        self, node_id: str, ref: m.TooltipRef, path: str, use: Use | None, stack: tuple[str, ...]
    ) -> None:
        nodes: list[m.Node | m.IfNode | m.ForNode] = []
        if ref.popup is not None:
            self.popup_depth += 1
            try:
                nodes = self._walk(ref.popup.children, path, use, stack)
            finally:
                self.popup_depth -= 1
        self.out.tooltips[node_id] = ExpandedTooltip(ref, nodes, use.key if use else "")

    def _forward(
        self,
        call: m.UseNode,
        children: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...],
        outer: Use | None,
    ) -> tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...]:
        """The module's layout with what is written on its call placed on its root block: the
        handlers (a handler names an action of the module that holds the call, ``outer``, or of
        the module a ``Call`` names) and the common block keys the module does not declare
        (``Width``, ``Enabled``, ``Position``: Standard Modules > Rules That Hold for Every
        Module). A root block that cannot raise an event, or has no such key, is an error at it;
        a root that is itself a module call passes both on."""
        handlers = {
            k: dataclasses.replace(h, use=outer.key if outer else "", forwarded=True)
            for k, h in call.handlers.items()
        }
        root = children[0] if children else None
        if isinstance(root, m.UseNode):
            merged = {**root.handlers, **handlers}
            common = {**root.common, **call.common}
            return (dataclasses.replace(root, handlers=merged, common=common), *children[1:])
        if not isinstance(root, m.Node):
            self.out.errors.append(
                m.BindError(f"{call.module} has no root block to raise an event", call.origin)
            )
            return children
        raised = blocks.BLOCK_EVENTS.get(root.kind, ())
        taken: dict[str, m.Handler] = {}
        controls = any(k in root.props for k in blocks.CONTROL_KEYS)
        for key, handler in handlers.items():
            if key in raised and (
                key != "On_Changed" or controls or root.kind not in blocks.CONTROL_KINDS
            ):
                taken[key] = handler
                continue
            hint = f"it raises: {', '.join(raised)}" if raised else "it raises no event"
            self.out.errors.append(
                m.BindError(
                    f"{call.module} does not raise {key}: its root block is a {root.kind}",
                    handler.origin,
                    hint,
                )
            )
        props = dict(root.props)
        style = dict(root.style)
        table = blocks.table(root.kind)
        for key, value in call.common.items():
            if table is not None and key not in table[0] and key not in table[1]:
                self.out.errors.append(
                    m.BindError(
                        f"{call.module} cannot take {key}: its root block is a {root.kind}",
                        value.origin,
                        f"a {root.kind} has: {', '.join(sorted({*table[0], *table[1]}))}",
                    )
                )
                continue
            props[key] = value
            style.pop(key, None)  # the call's key replaces the layout's, wherever it was written
        hidden = props.get("A11y_Hidden")
        if "Label" in call.common and "A11y_Hidden" not in call.common:
            if isinstance(hidden, m.Bool) and hidden.value:  # decorative unless it has a Label
                props["A11y_Hidden"] = m.Bool(False, origin=hidden.origin)
        placed = dataclasses.replace(root, props=props, style=style)
        return (dataclasses.replace(placed, handlers={**root.handlers, **taken}), *children[1:])

    def _use(
        self,
        call: m.UseNode,
        path: str,
        stack: tuple[str, ...],
        outer: Use | None = None,
        key: str | None = None,
        name: str | None = None,
    ) -> list[m.Node | m.IfNode | m.ForNode]:
        """``call`` replaced by the module's layout. ``key`` and ``name`` are given for a use made
        for an entry of a ``For``; otherwise they come from the position of the call."""
        module = self.modules[call.module]
        if call.module in stack or len(stack) >= MAX_DEPTH:
            chain = " -> ".join((*stack, call.module))
            self.out.errors.append(m.BindError(f"module calls form a cycle: {chain}", call.origin))
            return []
        if key is None or name is None:
            count = self._counts.get(f"@{path}/{call.module}", 0) + 1
            self._counts[f"@{path}/{call.module}"] = count
            label = call.name or f"{call.module}_{count}"
            name = f"{path}.{label}"
            key = f"{call.module}@{self.uid_of(name)}"
        params: dict[str, Any] = {}
        slots: dict[str, tuple[m.SlotValue, str]] = {}
        for p in module.params.values():
            written = call.params.get(p.name, p.default)
            if isinstance(written, m.SlotValue):
                if outer is None and not self.popup_depth:
                    self.out.errors.append(
                        m.BindError("a slot outside a module is not built yet", written.origin)
                    )
                slots[p.name] = (written, PARAM_SLOT_KINDS[p.type])
                written = p.default
            params[p.name] = PARAM_BLANKS[p.type] if written is None else plain_param(written)
        use = Use(
            key,
            call.module,
            name,
            params,
            self.monitor,
            call.origin,
            slots,
            outer.key if outer is not None else "",
        )
        self.out.uses.append(use)
        # the content on the call is the caller's: its slots read the caller's scope
        if call.children and not _has_content(module.children):
            self.out.errors.append(
                m.BindError(
                    f"{call.module} has no place for Children: its layout has no Content block",
                    call.origin,
                )
            )
        content = self._walk(call.children, path, outer, stack) if call.children else []
        layout = (
            self._forward(call, module.children, outer)
            if call.handlers or call.common
            else module.children
        )
        # the module's rules reach its root block as written, before a TextField is split in its
        # parts (its text keys go to the text input)
        layout = tuple(apply_module_rules(layout, call.module, self.rules))
        self._content.append(content)
        try:
            roots = self._walk(layout, name, use, (*stack, call.module))
        finally:
            self._content.pop()
        if call.name in self.attach_targets:
            self._mark_target(call, key, roots)
        if self.mark_roots:
            self._first_root(call, key, roots, "root", "a Popup could open beside")
        if call.tooltip is not None:
            self._mark_tooltip(call, key, roots, name, use, (*stack, call.module))
        return roots

    def _mark_target(
        self, call: m.UseNode, key: str, roots: list[m.Node | m.IfNode | m.ForNode]
    ) -> None:
        """A Panel is attached to this use: its first root block gets an id, so the surface can
        read where tre laid it out."""
        name = self._first_root(call, key, roots, "target", "a Panel could attach to")
        if name is not None:
            self.out.targets[call.name or ""] = name

    def _mark_tooltip(
        self,
        call: m.UseNode,
        key: str,
        roots: list[m.Node | m.IfNode | m.ForNode],
        path: str,
        use: Use,
        stack: tuple[str, ...],
    ) -> None:
        """A tooltip on this use: the use's first root block is what the pointer enters, and the
        tooltip's content is expanded in this use's scope."""
        assert call.tooltip is not None
        name = self._first_root(call, key, roots, "tooltip", "a Tooltip could open on")
        if name is not None:
            self._register_tooltip(name, call.tooltip, path, use, stack)

    def _first_root(
        self,
        call: m.UseNode,
        key: str,
        roots: list[m.Node | m.IfNode | m.ForNode],
        suffix: str,
        purpose: str,
    ) -> str | None:
        """The id of the use's first root block, given one if it has none."""
        for i, root in enumerate(roots):
            if isinstance(root, m.Node):
                if suffix == "tooltip" and root.kind in m.NO_POINTER_BLOCKS:
                    # a text takes no pointer: a box around it is what the pointer enters
                    root = m.Node("FlexBox", children=(root,), origin=root.origin)
                name = root.name or f"{key}/#{suffix}"
                self.out.owner[name] = key
                self.out.roots[key] = name
                roots[i] = dataclasses.replace(root, name=name)
                return name
        self.out.errors.append(
            m.BindError(f"{call.module} has no root block {purpose}", call.origin)
        )
        return None


def expand(
    nodes: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...],
    path: str,
    modules: Mapping[str, ModuleDef],
    uid_of: Callable[[str], str],
    monitor: str,
    rules: Sequence[Rule] = (),
    attach_targets: frozenset[str] = frozenset(),
    mark_roots: bool = False,
    in_popup: bool = False,
) -> Expanded:
    """Expand the children of one surface. ``path`` is the surface's dotted name.
    ``attach_targets`` are the ``Name`` of the uses a Panel is attached to; ``mark_roots`` gives
    every use's first root block an id (``Expanded.roots``), for a Popup to open beside;
    ``in_popup`` says the children are a Popup's content, where a slot may read ``caller``."""
    expander = _Expander(modules, uid_of, monitor, rules, attach_targets, mark_roots, in_popup)
    expander.run(nodes, path)
    expander.out.factory = CallFactory(modules, _ephemeral, monitor, rules)
    return expander.out
