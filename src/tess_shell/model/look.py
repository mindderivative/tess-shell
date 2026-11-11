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
from tess_shell.schema.model import ModuleDef, Rule, StylesheetDef, ThemeDef, Token
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
    fallback: ThemeDef | None = None  # the Default theme, for a token the chosen one lacks

    @property
    def max_shadows(self) -> m.Shadows | None:
        token = self.tokens.get("elevation.max")
        return token.value if token is not None and isinstance(token.value, m.Shadows) else None

    def with_appearance(self, appearance: Appearance) -> Look:
        """The same theme and rules for a new light or dark setting, accent or motion flag."""
        return make_look(self.theme, self.sheets, appearance, self.fallback)


def make_look(
    theme: ThemeDef,
    sheets: Sequence[StylesheetDef],
    appearance: Appearance,
    fallback: ThemeDef | None = None,
) -> Look:
    return Look(
        theme,
        tuple(sheets),
        appearance,
        effective_tokens(theme, appearance, fallback),
        tuple(rule for sheet in sheets for rule in sheet.rules),
        fallback,
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


def _motion(
    node: m.Node, props: dict[str, m.Value], style: dict[str, m.Value], look: Look | None
) -> None:
    """The motion a block asks for, as it is with this look: a ``Transition`` with no ``Duration``
    takes the theme's medium duration (200 ms without a theme), and under reduced motion every
    duration is 0 and a Marquee does not scroll (Accessibility > Rules, 7)."""
    reduced = look is not None and look.appearance.reduced_motion
    if "Transition" in props or "Transition" in style:
        table = props if "Duration" in props else style
        if "Duration" not in table:
            origin = (props.get("Transition") or style["Transition"]).origin
            medium: m.Value = m.Number(200, origin=origin)
            if look is not None:
                try:
                    medium = _ref_value(m.TokenRef("motion.duration.medium", "number"), look.tokens)
                except TokenProblem:
                    pass  # a theme with no motion tokens: the default stands
            table["Duration"] = medium
        if reduced:
            table["Duration"] = m.Number(0, origin=table["Duration"].origin)
    if reduced and node.kind == m.MARQUEE:
        props["Animated"] = m.Bool(False, origin=node.origin)


def _resolve_node(node: m.Node, look: Look | None, errors: list[m.BindError]) -> m.Node:
    props = resolve_style(node.props, look, errors)
    style = resolve_style(node.style, look, errors)
    _motion(node, props, style, look)
    return dataclasses.replace(
        node,
        props=props,
        style=style,
        states={s: resolve_style(v, look, errors) for s, v in node.states.items()},
        children=tuple(
            _resolve_node(c, look, errors) for c in node.children if isinstance(c, m.Node)
        ),
    )


# -- stylesheet rules --------------------------------------------------------------------------


def _matches(rule: Rule, node: m.Node) -> bool:
    if rule.kind == "module":
        return False  # applied to a module's root blocks by :func:`apply_module_rules`
    if rule.kind == "type":
        return rule.target == node.kind
    if rule.kind == "class":
        return rule.target in node.classes
    return node.name == rule.target


def _allowed(kind: str, key: str) -> bool:
    row = blocks.BLOCKS.get(kind)
    return row is not None and (key in row[0] or key in row[1])


def apply_rules(
    children: tuple[Child, ...], rules: Sequence[Rule], module: str = ""
) -> tuple[Child, ...]:
    """Fold the matching rules into each block's ``style``. A name beats a class beats a type; of
    two rules of one weight the later wins. A key the block already has (written on it, or from
    its own style) is not touched, and a key the block does not take is skipped.

    ``module`` is the call name when ``children`` are a module's layout: a block that declares
    ``Part: track`` there also takes the rules of ``Module::track`` (and ``Module::track:hovered``),
    which weigh more than a class or type rule on that block (:attr:`Rule.specificity`)."""
    if not rules:
        return children
    return tuple(_rules_child(c, rules, module) for c in children)


def _rules_child(node: Child, rules: Sequence[Rule], module: str) -> Child:
    if isinstance(node, m.UseNode):
        if not node.children:
            return node
        # the blocks written on a call (``Children { }``) are styled like any others
        return dataclasses.replace(node, children=apply_rules(node.children, rules, module))
    if isinstance(node, m.IfNode):
        return dataclasses.replace(
            node,
            body=apply_rules(node.body, rules, module),
            else_body=(
                None if node.else_body is None else apply_rules(node.else_body, rules, module)
            ),
        )
    if isinstance(node, m.ForNode):
        return dataclasses.replace(node, body=apply_rules(node.body, rules, module))
    hits = [r for r in rules if _matches(r, node)]
    if module and node.part:
        hits += [
            r for r in rules if r.part == node.part and r.kind == "module" and r.target == module
        ]
    # a TextField in a module has the part ``placeholder``: ``TextInput::placeholder`` colours the
    # hint text, so its ``Foreground`` is the field's ``Placeholder_Foreground``
    hint = [
        r
        for r in rules
        if module
        and node.kind == m.FIELD
        and r.part == PLACEHOLDER_PART
        and r.kind == "module"
        and r.target == module
    ]
    return dataclasses.replace(
        node,
        style=_fold(node, hits, hint),
        states=_fold_states(node, hits, hint),
        children=apply_rules(node.children, rules, module),
    )


# the part every TextField of a module has: the hint shown while the field is empty
PLACEHOLDER_PART = "placeholder"


def _merge(kind: str, hits: Sequence[Rule]) -> dict[str, m.Value]:
    """The keys a block of ``kind`` takes from ``hits``: a name beats a class beats a module beats
    a type; of one weight the later rule wins. A word the block's key does not take (``SCROLL`` for
    a Text's ``Overflow``) is skipped: one rule serves every block that has the key."""
    ordered = sorted(enumerate(hits), key=lambda t: (t[1].specificity, t[0]))
    merged: dict[str, m.Value] = {}
    for _, rule in ordered:
        for key, value in rule.values.items():
            if not _allowed(kind, key):
                continue
            words = blocks.CHOICES.get((kind, key))
            if words and isinstance(value, m.Enum) and value.name not in words:
                continue
            merged[key] = value
    return merged


def _placeholder(kind: str, hint: Sequence[Rule], state: str) -> dict[str, m.Value]:
    """What the ``::placeholder`` rules (``hint``) give a TextField in ``state`` (``""`` is the
    base look): the part has the text colour and nothing else."""
    merged = _merge(kind, [r for r in hint if r.state == state])
    value = merged.get("Foreground")
    return {} if value is None else {"Placeholder_Foreground": value}


def _fold(node: m.Node, hits: Sequence[Rule], hint: Sequence[Rule] = ()) -> dict[str, m.Value]:
    """``node.style`` with the keys of ``hits`` below it (a name beats a class beats a module
    beats a type; of one weight the later rule wins; the block's own keys win over all). A rule
    with a state does not belong here: see :func:`_fold_states`. ``hint`` are a TextField's
    ``::placeholder`` rules, which sit below the rest."""
    merged = {
        **_placeholder(node.kind, hint, ""),
        **_merge(node.kind, [r for r in hits if not r.state]),
    }
    below = {k: v for k, v in merged.items() if k not in node.props and k not in node.style}
    return {**below, **node.style}


def _fold_states(
    node: m.Node, hits: Sequence[Rule], hint: Sequence[Rule] = ()
) -> Mapping[str, Mapping[str, m.Value]]:
    """``node.states`` with the state rules among ``hits`` added, a state at a time, by the same
    precedence as the base style. A state value is not held back by the block's own style: it is
    the look while the state holds, on top of whatever the block shows otherwise."""
    states = {s: dict(v) for s, v in node.states.items()}
    for state in m.STATES:
        merged = {
            **_placeholder(node.kind, hint, state),
            **_merge(node.kind, [r for r in hits if r.state == state]),
        }
        if merged:
            states[state] = {**merged, **states.get(state, {})}
    return states if states else node.states


def apply_module_rules(roots: Sequence[Child], module: str, rules: Sequence[Rule]) -> list[Child]:
    """The rules that name ``module`` applied to its root blocks. A key the root block does not
    take passes to the first block inside it that does, along the first child of each (so
    ``Icon { Foreground: ... }`` colours the SVG a FlexBox holds, and ``Badge { Foreground }`` its
    digits); an inner block is otherwise styled by a type, class or name rule (D40)."""
    mine = [r for r in rules if r.kind == "module" and r.target == module and not r.part]
    if not mine:
        return list(roots)
    return [_down(root, mine) if isinstance(root, m.Node) else root for root in roots]


def _down(node: Child, hits: Sequence[Rule]) -> Child:
    """``node`` with the keys of ``hits`` it takes folded in; what it does not take goes on to its
    first child (to both branches of an ``If``)."""
    if isinstance(node, m.IfNode):
        return dataclasses.replace(
            node,
            body=_down_first(node.body, hits),
            else_body=None if node.else_body is None else _down_first(node.else_body, hits),
        )
    if not isinstance(node, m.Node):
        return node
    folded = dataclasses.replace(
        node, style=_fold(node, hits), states=_fold_states(node, hits)
    )
    rest = [
        dataclasses.replace(
            r, values={k: v for k, v in r.values.items() if not _allowed(node.kind, k)}
        )
        for r in hits
    ]
    rest = [r for r in rest if r.values]
    if rest and node.children:
        return dataclasses.replace(folded, children=_down_first(node.children, rest))
    return folded


def _down_first(children: tuple[Child, ...], hits: Sequence[Rule]) -> tuple[Child, ...]:
    if not children:
        return children
    return (_down(children[0], hits), *children[1:])


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
        tables.extend((node.props, node.style, *node.states.values()))
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


def check_states(
    children: Sequence[Child], rules: Sequence[Rule], module: str = ""
) -> list[Finding]:
    """A warning for each ``:hovered`` or ``:pressed`` style the rules give a block that tre sends
    no pointer events (a ``Text``): the state would never hold, so the rule does nothing there.
    ``module`` is the call name when ``children`` are a module's layout."""
    if not any(r.state for r in rules):
        return []
    ruled: Sequence[Child] = apply_rules(tuple(children), rules, module)
    if module:
        ruled = apply_module_rules(ruled, module, rules)
    found: list[Finding] = []
    for node in _walk(ruled):
        if not node.states or node.kind not in m.NO_POINTER_BLOCKS:
            continue
        for state, values in node.states.items():
            if state in m.FLAG_STATES:  # these need no pointer: a Text can be disabled or chosen
                continue
            o = next(iter(values.values())).origin if values else node.origin
            found.append(
                Finding(
                    o.file,
                    o.line,
                    o.column,
                    "warning",
                    "state-never-applies",
                    f"a :{state} style reaches a {node.kind}, which tre sends no pointer events",
                    "put the state rule on the Box or FlexBox around the text",
                )
            )
    return found


def check_parts(modules: Mapping[str, ModuleDef], rules: Sequence[Rule]) -> list[Finding]:
    """An error for each ``Module::part`` rule that names a part the module's layout does not
    declare (with the nearest part names): the rule would style nothing."""
    found: list[Finding] = []
    for rule in rules:
        if not rule.part or rule.kind != "module":
            continue
        module = modules.get(rule.target)
        if module is None or rule.part in module.parts:
            continue
        close = nearest(rule.part, module.parts)
        o = rule.origin
        found.append(
            Finding(
                o.file,
                o.line,
                o.column,
                "error",
                "unknown-part",
                f"{rule.target} has no part {rule.part}",
                f"did you mean {', '.join(close)}?"
                if close
                else (
                    f"its parts: {', '.join(module.parts)}"
                    if module.parts
                    else f"{rule.target} declares no parts: write Part: {rule.part} on a block"
                ),
            )
        )
    return found
