"""Replace each module call with the module's layout (Module File > Using a Module).

Every named node inside a use gets the use's key as a prefix, so two uses of one module never
share a node id. A node that holds a slot and has no name gets a generated one, because the binder
updates a node by id. Slots are left in place; :mod:`tess_shell.model.live` evaluates them.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from tess_shell.binder import model as m
from tess_shell.model.uses import Use, plain_param
from tess_shell.schema.model import ModuleDef

MAX_DEPTH = 8


@dataclass(slots=True)
class Expanded:
    nodes: list[m.Node] = field(default_factory=list)
    uses: list[Use] = field(default_factory=list)
    owner: dict[str, str] = field(default_factory=dict)  # node id -> use key
    errors: list[m.BindError] = field(default_factory=list)


def _has_slot(node: m.Node) -> bool:
    return any(isinstance(v, m.SlotValue) for v in (*node.props.values(), *node.style.values()))


class _Expander:
    def __init__(
        self,
        modules: Mapping[str, ModuleDef],
        uid_of: Callable[[str], str],
        monitor: str,
    ) -> None:
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
    ) -> list[m.Node]:
        result: list[m.Node] = []
        for node in nodes:
            if isinstance(node, m.UseNode):
                result.extend(self._use(node, path, stack))
            elif isinstance(node, m.Node):
                result.append(self._node(node, path, use, stack))
            else:
                result.append(node)  # type: ignore[arg-type]  # If and For: the binder refuses them
        return result

    def _node(self, node: m.Node, path: str, use: Use | None, stack: tuple[str, ...]) -> m.Node:
        name = node.name
        if use is not None:
            if name is not None:
                name = f"{use.key}/{name}"
            elif _has_slot(node):
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
        children = self._walk(node.children, path, use, stack)
        return dataclasses.replace(node, name=name, children=tuple(children))

    def _use(self, call: m.UseNode, path: str, stack: tuple[str, ...]) -> list[m.Node]:
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
        return self._walk(module.children, name, use, (*stack, call.module))


def expand(
    nodes: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...],
    path: str,
    modules: Mapping[str, ModuleDef],
    uid_of: Callable[[str], str],
    monitor: str,
) -> Expanded:
    """Expand the children of one surface. ``path`` is the surface's dotted name."""
    expander = _Expander(modules, uid_of, monitor)
    expander.run(nodes, path)
    return expander.out
