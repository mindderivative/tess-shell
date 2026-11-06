"""Replace each module call with the module's layout (Module File > Using a Module).

Every named node inside a use gets the use's key as a prefix, so two uses of one module never
share a node id. A node that holds a slot and has no name gets a generated one, because the binder
updates a node by id. Slots are left in place; :mod:`tess_shell.model.live` evaluates them.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from tess_shell.binder import model as m
from tess_shell.model.look import apply_module_rules
from tess_shell.model.uses import Use, plain_param
from tess_shell.schema.model import ModuleDef, Rule

MAX_DEPTH = 8


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
    ) -> None:
        self.attach_targets = attach_targets
        self.mark_roots = mark_roots
        self.rules = rules
        self.modules = modules
        self.uid_of = uid_of
        self.monitor = monitor
        self.out = Expanded()
        self._counts: dict[str, int] = {}

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
                result.extend(self._use(node, path, stack))
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
        return dataclasses.replace(
            node,
            body=tuple(self._walk(node.body, path, use, stack, dynamic=True)),
            use=use.key if use else "",
        )

    def _node(
        self,
        node: m.Node,
        path: str,
        use: Use | None,
        stack: tuple[str, ...],
        dynamic: bool = False,
    ) -> m.Node:
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
        elif _has_slot(node):
            for v in (*node.props.values(), *node.style.values()):
                if isinstance(v, m.SlotValue):
                    self.out.errors.append(
                        m.BindError("a slot outside a module is not built yet", v.origin)
                    )
        if node.tooltip is not None:
            name = self._tooltip(node, name, path, use, stack, dynamic)
        children = self._walk(node.children, path, use, stack, dynamic)
        return dataclasses.replace(node, name=name, children=tuple(children), tooltip=None)

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
            nodes = self._walk(ref.popup.children, path, use, stack)
        self.out.tooltips[node_id] = ExpandedTooltip(ref, nodes, use.key if use else "")

    def _use(
        self, call: m.UseNode, path: str, stack: tuple[str, ...]
    ) -> list[m.Node | m.IfNode | m.ForNode]:
        module = self.modules[call.module]
        if call.module in stack or len(stack) >= MAX_DEPTH:
            chain = " -> ".join((*stack, call.module))
            self.out.errors.append(m.BindError(f"module calls form a cycle: {chain}", call.origin))
            return []
        count = self._counts.get(f"@{path}/{call.module}", 0) + 1
        self._counts[f"@{path}/{call.module}"] = count
        label = call.name or f"{call.module}_{count}"
        name = f"{path}.{label}"
        key = f"{call.module}@{self.uid_of(name)}"
        params = {
            p.name: plain_param(call.params.get(p.name, p.default))  # type: ignore[arg-type]
            for p in module.params.values()
        }
        use = Use(key, call.module, name, params, self.monitor, call.origin)
        self.out.uses.append(use)
        roots = self._walk(module.children, name, use, (*stack, call.module))
        roots = apply_module_rules(roots, call.module, self.rules)  # type: ignore[assignment]
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
) -> Expanded:
    """Expand the children of one surface. ``path`` is the surface's dotted name.
    ``attach_targets`` are the ``Name`` of the uses a Panel is attached to; ``mark_roots`` gives
    every use's first root block an id (``Expanded.roots``), for a Popup to open beside."""
    expander = _Expander(modules, uid_of, monitor, rules, attach_targets, mark_roots)
    expander.run(nodes, path)
    return expander.out
