"""Fold a style into a layout (Style, Theme and Stylesheet Files > Rules).

Priority, lowest to highest: the style file's values for a block type, then its classes in the
order the block names them, then the block's inline ``Style { }``, then keys written on the block
itself (which are shorthand for inline style). A style changes only what it names.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from tess_shell.binder import model as m
from tess_shell.schema.findings import nearest
from tess_shell.schema.model import StyleDef

Report = Callable[[m.Origin, str, str, str], None]
Child = m.Node | m.UseNode | m.IfNode | m.ForNode


def apply_style(
    children: tuple[Child, ...], style: StyleDef | None, report: Report
) -> tuple[Child, ...]:
    return tuple(_apply(child, style, report) for child in children)


def _apply(node: Child, style: StyleDef | None, report: Report) -> Child:
    if isinstance(node, m.IfNode):
        return dataclasses.replace(
            node,
            body=apply_style(node.body, style, report),
            else_body=None
            if node.else_body is None
            else apply_style(node.else_body, style, report),
        )
    if isinstance(node, m.ForNode):
        return dataclasses.replace(node, body=apply_style(node.body, style, report))
    if isinstance(node, m.UseNode):
        return node
    merged: dict[str, m.Value] = {}
    if style is not None:
        merged.update(style.defaults.get(node.kind, {}))
    for name in node.classes:
        found = style.classes.get(name) if style is not None else None
        if found is None:
            where = style.file if style is not None else "the module has no style"
            choices = list(style.classes) if style is not None else []
            close = nearest(name, choices)
            report(
                node.origin,
                "class-not-found",
                f"the class {name} is not defined in {where}",
                f"did you mean {', '.join(close)}?" if close else "define it under Classes { }",
            )
        elif found.kind != node.kind:
            report(
                node.origin,
                "class-kind",
                f"the class {name} is for {found.kind} blocks, not {node.kind}",
                f"it is defined at {found.origin}",
            )
        else:
            merged.update(found.values)
    merged.update(node.style)
    for key in [k for k in merged if k in node.props and k not in node.style]:
        del merged[key]  # a key written on the block wins over the file's value
    children = apply_style(node.children, style, report)
    return dataclasses.replace(node, style=merged, children=children)
