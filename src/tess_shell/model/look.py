"""The look: theme tokens, stylesheet rules and what they do to a tree (Style Schema).

Three steps, each pure. :func:`apply_rules` folds the stylesheet rules into every block's style at
plan time, below the block's own style (priority: theme, stylesheet, style, inline). :func:`resolve`
replaces each ``$group.name`` reference with the token's value just before binding, so a change of
the desktop's light or dark setting is one new :class:`Look` and one rebuild, not a re-read of the
files. :func:`check_tokens` finds a reference to a missing token or of the wrong kind before the
shell runs.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.binder.shadow import scale
from tess_shell.schema import blocks
from tess_shell.schema.findings import Finding, nearest
from tess_shell.schema.look import effective_tokens
from tess_shell.schema.model import Rule, StylesheetDef, ThemeDef, Token
from tess_shell.schema.values import ValueProblem, coerce

Child = m.Node | m.UseNode | m.IfNode | m.ForNode


# -- the active look --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Look:
    theme: ThemeDef
    sheets: tuple[StylesheetDef, ...]
    appearance: Appearance
    tokens: Mapping[str, Token]
    rules: tuple[Rule, ...] = ()

    @property
    def max_shadows(self) -> m.Shadows | None:
        token = self.tokens.get("elevation.max")
        return token.value if token is not None and isinstance(token.value, m.Shadows) else None

    def with_appearance(self, appearance: Appearance) -> Look:
        """The same theme and rules for a new light or dark setting, accent or motion flag."""
        return make_look(self.theme, self.sheets, appearance)


def make_look(theme: ThemeDef, sheets: Sequence[StylesheetDef], appearance: Appearance) -> Look:
    return Look(
        theme,
        tuple(sheets),
        appearance,
        effective_tokens(theme, appearance),
        tuple(rule for sheet in sheets for rule in sheet.rules),
    )


# -- resolving a reference ---------------------------------------------------------------------


class TokenProblem(Exception):
    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


def _ref_value(ref: m.TokenRef, tokens: Mapping[str, Token]) -> m.Value:
    token = tokens.get(ref.path)
    if token is None:
        close = nearest(ref.path, tokens)
        raise TokenProblem(
            f"no token named ${ref.path}",
            f"did you mean {', '.join('$' + c for c in close)}?"
            if close
            else "the theme's groups are Color, Type, Shape, Space, Elevation and Motion",
        )
    if isinstance(token.value, m.Shadows):
        if ref.kind == "shadows":
            return token.value
        raise TokenProblem(f"${ref.path} is a list of shadows, not a {ref.kind}")
    try:
        return coerce(ref.kind, token.value, ref.origin, ref.choices)
    except ValueProblem as exc:
        raise TokenProblem(
            f"${ref.path} cannot be used here: {exc.message}", f"defined at {token.origin}"
        ) from exc


def resolve_style(
    style: Mapping[str, m.Value], look: Look | None, report: list[m.BindError] | None = None
) -> dict[str, m.Value]:
    """``style`` with every token reference replaced; a reference that cannot be resolved is
    dropped (the key keeps its default) and reported."""
    out: dict[str, m.Value] = {}
    for key, value in style.items():
        if isinstance(value, m.TokenRef):
            if look is None:
                continue
            try:
                value = _ref_value(value, look.tokens)
            except TokenProblem as exc:
                if report is not None:
                    report.append(m.BindError(f"{key}: {exc.message}", value.origin, exc.hint))
                continue
        if key == "Elevation" and isinstance(value, m.Percent) and look is not None:
            top = look.max_shadows
            if top is not None:  # the theme's own Max replaces the built-in one
                out["Shadows"] = out.get("Shadows") or scale(top, value.value, value.origin)
                continue
        out[key] = value
    return out


def resolve(nodes: Sequence[m.Node], look: Look | None) -> tuple[list[m.Node], list[m.BindError]]:
    """The tree with every token reference resolved; the errors name each reference left out."""
    errors: list[m.BindError] = []
    return [_resolve_node(n, look, errors) for n in nodes], errors


def _resolve_node(node: m.Node, look: Look | None, errors: list[m.BindError]) -> m.Node:
    return dataclasses.replace(
        node,
        props=resolve_style(node.props, look, errors),
        style=resolve_style(node.style, look, errors),
        children=tuple(
            _resolve_node(c, look, errors) for c in node.children if isinstance(c, m.Node)
        ),
    )


# -- stylesheet rules --------------------------------------------------------------------------


def _matches(rule: Rule, node: m.Node) -> bool:
    if rule.kind == "type":
        return rule.target == node.kind
    if rule.kind == "class":
        return rule.target in node.classes
    return node.name == rule.target


def _allowed(kind: str, key: str) -> bool:
    row = blocks.BLOCKS.get(kind)
    return row is not None and (key in row[0] or key in row[1])


def apply_rules(children: tuple[Child, ...], rules: Sequence[Rule]) -> tuple[Child, ...]:
    """Fold the matching rules into each block's ``style``. A name beats a class beats a type; of
    two rules of one weight the later wins. A key the block already has (written on it, or from
    its own style) is not touched, and a key the block does not take is skipped."""
    if not rules:
        return children
    return tuple(_rules_child(c, rules) for c in children)


def _rules_child(node: Child, rules: Sequence[Rule]) -> Child:
    if isinstance(node, m.UseNode):
        return node
    if isinstance(node, m.IfNode):
        return dataclasses.replace(
            node,
            body=apply_rules(node.body, rules),
            else_body=None if node.else_body is None else apply_rules(node.else_body, rules),
        )
    if isinstance(node, m.ForNode):
        return dataclasses.replace(node, body=apply_rules(node.body, rules))
    hits = sorted(
        ((r.specificity, i, r) for i, r in enumerate(rules) if _matches(r, node)),
        key=lambda t: (t[0], t[1]),
    )
    merged: dict[str, m.Value] = {}
    for _, _, rule in hits:
        for key, value in rule.values.items():
            if _allowed(node.kind, key):
                merged[key] = value
    below = {k: v for k, v in merged.items() if k not in node.props and k not in node.style}
    children = apply_rules(node.children, rules)
    if not below:
        return dataclasses.replace(node, children=children)
    return dataclasses.replace(node, style={**below, **node.style}, children=children)


# -- checking references before the shell runs ------------------------------------------------


def _walk(children: Sequence[Child]) -> list[m.Node]:
    out: list[m.Node] = []
    for c in children:
        if isinstance(c, m.Node):
            out.append(c)
            out.extend(_walk(c.children))
        elif isinstance(c, m.IfNode):
            out.extend(_walk(c.body))
            out.extend(_walk(c.else_body or ()))
        elif isinstance(c, m.ForNode):
            out.extend(_walk(c.body))
    return out


def check_tokens(
    children: Sequence[Child],
    tokens: Mapping[str, Token],
    extra: Mapping[str, m.Value] | None = None,
) -> list[Finding]:
    """A finding for each reference to a missing token or one of the wrong kind. ``extra`` is a
    surface's own style."""
    found: list[Finding] = []
    tables: list[Mapping[str, m.Value]] = [extra] if extra else []
    for node in _walk(children):
        tables.extend((node.props, node.style))
    for table in tables:
        for key, value in table.items():
            if not isinstance(value, m.TokenRef):
                continue
            try:
                _ref_value(value, tokens)
            except TokenProblem as exc:
                o = value.origin
                found.append(
                    Finding(
                        o.file,
                        o.line,
                        o.column,
                        "error",
                        "bad-token",
                        f"{key}: {exc.message}",
                        exc.hint,
                    )
                )
    return found
