"""Checks across module files."""

from __future__ import annotations

from collections.abc import Mapping

from tess_shell.binder import model as m
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef


def module_cycles(modules: Mapping[str, ModuleDef]) -> list[Finding]:
    """A module that calls itself, through any chain of calls and imports, is an error naming the
    chain (Module File > Errors). Each cycle is reported once."""

    def calls(nodes: tuple[m.Node | m.UseNode | m.IfNode | m.ForNode, ...]) -> list[str]:
        out: list[str] = []
        for node in nodes:
            if isinstance(node, m.UseNode):
                out.append(node.module)
            elif isinstance(node, m.Node):
                out.extend(calls(node.children))
        return out

    graph = {name: calls(definition.children) for name, definition in modules.items()}
    findings: list[Finding] = []
    reported: set[frozenset[str]] = set()
    state: dict[str, int] = {}  # 1 on the path, 2 done

    def visit(name: str, path: list[str]) -> None:
        if state.get(name) == 2 or name not in graph:
            return
        if state.get(name) == 1:
            cycle = [*path[path.index(name) :], name]
            key = frozenset(cycle)
            if key not in reported:
                reported.add(key)
                first = modules[cycle[0]]
                origin = first.origin
                findings.append(
                    Finding(
                        first.file,
                        origin.line,
                        origin.column,
                        "error",
                        "import-cycle",
                        f"modules call each other in a circle: {' -> '.join(cycle)}",
                        "remove one of the calls or imports",
                    )
                )
            return
        state[name] = 1
        for nxt in graph[name]:
            visit(nxt, [*path, name])
        state[name] = 2

    for name in graph:
        visit(name, [])
    return findings
