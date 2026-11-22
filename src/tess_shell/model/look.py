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
from tess_shell.binder.focus import takes_ring
from tess_shell.binder.shadow import scale
from tess_shell.model.icons import RuntimeIcons
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
    icons: RuntimeIcons | None = None  # where a name a module sends becomes an SVG document

    @property
    def max_shadows(self) -> m.Shadows | None:
        token = self.tokens.get("elevation.max")
        return token.value if token is not None and isinstance(token.value, m.Shadows) else None

    def level_shadows(self, level: str) -> m.Shadows | None:
        """The shadows of ``LEVEL_0`` to ``LEVEL_5``: none for 0, else the theme's token
        ``elevation.level_n``; ``None`` when the theme and the Default theme lack it."""
        if level == "LEVEL_0":
            return m.Shadows(())
        token = self.tokens.get(f"elevation.{level.lower()}")
        return token.value if token is not None and isinstance(token.value, m.Shadows) else None

    def with_appearance(self, appearance: Appearance) -> Look:
        """The same theme and rules for a new light or dark setting, accent or motion flag."""
        appearance = dataclasses.replace(appearance, density=self.appearance.density)
        if self.appearance.scheme_override is not None:  # ``Appearance.Scheme``: the user's choice
            appearance = dataclasses.replace(
                appearance,
                scheme=self.appearance.scheme_override,
                scheme_override=self.appearance.scheme_override,
            )
        return make_look(self.theme, self.sheets, appearance, self.fallback, self.icons)

    def at_density(self, density: str | None) -> Look:
        """The same look at another density level (a surface's own ``Density``); this look when
        ``density`` is ``None`` or the level it has."""
        if density is None or density == self.appearance.density:
            return self
        return make_look(
            self.theme,
            self.sheets,
            dataclasses.replace(self.appearance, density=density),  # type: ignore[arg-type]
            self.fallback,
            self.icons,
        )


def make_look(
    theme: ThemeDef,
    sheets: Sequence[StylesheetDef],
    appearance: Appearance,
    fallback: ThemeDef | None = None,
    icons: RuntimeIcons | None = None,
) -> Look:
    return Look(
        theme,
        tuple(sheets),
        appearance,
        effective_tokens(theme, appearance, fallback),
        tuple(rule for sheet in sheets for rule in sheet.rules),
        fallback,
        icons,
    )


# -- resolving a reference ---------------------------------------------------------------------


class TokenProblem(Exception):
    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


def _ref_value(ref: m.TokenRef, tokens: Mapping[str, Token], key: str = "") -> m.Value:
    """The value of the token ``ref`` names, read as ``key`` reads it (its kind) and judged by the
    range of ``key`` and of its kind, like a value written in the file (``schema.ranges``)."""
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
        return coerce(ref.kind, token.value, ref.origin, ref.choices, key=key)
    except ValueProblem as exc:
        raise TokenProblem(
            f"${ref.path} cannot be used here: {exc.message}", f"defined at {token.origin}"
        ) from exc


# a state layer key and the theme token that is its opacity (State Layers, ADR-0009)
LAYER_TIME = {  # the fade of each layer: tre's per-state timings (0.6.12)
    "Hover_Layer": ("Hover_Layer_Ms", "state.hover_ms"),
    "Pressed_Layer": ("Pressed_Layer_Ms", "state.pressed_ms"),
    "Focus_Layer": ("Focus_Layer_Ms", "state.focus_ms"),
}
LAYER_OPACITY = {
    "Hover_Layer": "state.hover",
    "Pressed_Layer": "state.pressed",
    "Focus_Layer": "state.focus",
}


def _layer_colour(color: m.Color, token: Token | None) -> m.Color:
    """A state layer colour at the opacity of its state token. A colour that already has an alpha
    (``"#FFFFFF14"``) is the author's own and is kept."""
    value = getattr(token, "value", None)
    opacity = getattr(value, "value", None)
    if color.a != 255 or not isinstance(opacity, int | float):
        return color
    return m.Color(color.r, color.g, color.b, round(255 * float(opacity)), origin=color.origin)


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
                value = _ref_value(value, look.tokens, key)
            except TokenProblem as exc:
                if report is not None:
                    report.append(m.BindError(f"{key}: {exc.message}", value.origin, exc.hint))
                continue
        if key == "Elevation" and isinstance(value, m.Enum) and look is not None:
            shadows = look.level_shadows(value.name)
            if shadows is None:
                if report is not None:
                    report.append(
                        m.BindError(
                            f"Elevation: the theme has no shadows for {value.name}",
                            value.origin,
                            "a theme's Elevation group holds Level_1 to Level_5",
                        )
                    )
                continue
            out["Shadows"] = out.get("Shadows") or shadows
            continue
        if key in LAYER_OPACITY and isinstance(value, m.Color) and look is not None:
            value = _layer_colour(value, look.tokens.get(LAYER_OPACITY[key]))
            time_key, time_token = LAYER_TIME[key]
            if time_key not in style and time_token in look.tokens:
                out[time_key] = _ref_value(m.TokenRef(time_token, "number"), look.tokens)
        if key == "Elevation" and isinstance(value, m.Percent) and look is not None:
            top = look.max_shadows
            if top is not None:  # the theme's own Max replaces the built-in one
                out["Shadows"] = out.get("Shadows") or scale(top, value.value, value.origin)
                continue
        out[key] = value
    return out


def resolve(nodes: Sequence[m.Node], look: Look | None) -> tuple[list[m.Node], list[m.BindError]]:
    """The tree with every token reference resolved; the errors name each reference left out.
    A block that takes keyboard focus gets the focus ring as its ``:focused`` look."""
    errors: list[m.BindError] = []
    ring = focus_ring(look)
    return [_resolve_node(n, look, errors, ring) for n in nodes], errors


# the focus ring when the theme has no tokens to build it from (Focus Ring: 3 px, 2 px off)
_RING_COLOR = m.Color(0x5B, 0x97, 0xC9, 255)
_RING_WIDTH = 3
_RING_OFFSET = 2


def focus_ring(look: Look | None) -> dict[str, m.Value]:
    """The ring that shows keyboard focus (Focus and Keyboard > Focusable Things and the Focus
    Ring): tre's outline, drawn outside the block so it shifts no layout and needs no
    ``Shadows``: ``space.focus_ring_width`` wide, ``space.focus_ring_offset`` off the block, in
    ``color.primary``.
    A theme without those tokens gets the Default theme's values."""
    origin = m.Origin("<focus ring>", 1, 1)
    found: dict[str, m.Value] = {
        "Outline_Color": _RING_COLOR,
        "Outline_Width": m.Number(_RING_WIDTH, origin=origin),
        "Outline_Offset": m.Number(_RING_OFFSET, origin=origin),
    }
    if look is not None:
        for key, path, kind in (
            ("Outline_Color", "color.primary", "color"),
            ("Outline_Width", "space.focus_ring_width", "number"),
            ("Outline_Offset", "space.focus_ring_offset", "number"),
        ):
            try:
                value = _ref_value(m.TokenRef(path, kind), look.tokens)
            except TokenProblem:
                continue  # a theme with no such token: the default stands
            if isinstance(value, m.Color | m.Number):
                found[key] = value
    return found


# the scrollbar of a scroll view: its style key, the theme token (group ``scrollbar``) it is read
# from, and for the colours the colour token (Scrollbar and Scroll Container)
_SCROLLBAR_NUMBERS = {
    "Scrollbar_Width": "scrollbar.width",
    "Scrollbar_Hit_Width": "scrollbar.hit_width",
    "Scrollbar_Margin": "scrollbar.margin",
    "Scrollbar_Min_Length": "scrollbar.min_length",
    "Scrollbar_Gutter": "scrollbar.gutter",
    "Scrollbar_Radius": "scrollbar.radius",
    "Scrollbar_Opacity": "scrollbar.opacity",
    "Scrollbar_Opacity_Hover": "scrollbar.opacity_hover",
    "Scrollbar_Opacity_Drag": "scrollbar.opacity_drag",
    "Scroll_Wheel_Notch": "scrollbar.wheel_notch",
    "Scroll_Key_Line": "scrollbar.key_line",
    "Scroll_Page_Fraction": "scrollbar.page_fraction",
}
_SCROLLBAR_COLOURS = ("Scrollbar_Fill", "Scrollbar_Fill_Hover", "Scrollbar_Fill_Drag")
SCROLLBAR_THUMB = "color.on_surface_muted"  # the spec's on_surface_variant


def scrollbar_style(look: Look | None) -> dict[str, m.Value]:
    """The scrollbar the spec describes, as the style keys of a scroll view (a block's own key or a
    stylesheet rule replaces each): the sizes and opacities of the theme's ``Scrollbar`` group and
    the thumb in the theme's muted ink. With no look, none (tre's own scrollbar)."""
    if look is None:
        return {}
    out: dict[str, m.Value] = {}
    for key, path in _SCROLLBAR_NUMBERS.items():
        try:
            value = _ref_value(m.TokenRef(path, "number"), look.tokens)
        except TokenProblem:
            continue  # a theme with no such token keeps tre's value
        out[key] = value
    try:
        thumb = _ref_value(m.TokenRef(SCROLLBAR_THUMB, "color"), look.tokens)
    except TokenProblem:
        return out
    for key in _SCROLLBAR_COLOURS:
        out[key] = thumb
    return out


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


def _resolve_node(
    node: m.Node, look: Look | None, errors: list[m.BindError], ring: dict[str, m.Value]
) -> m.Node:
    props = resolve_style(node.props, look, errors)
    style = resolve_style(node.style, look, errors)
    _motion(node, props, style, look)
    states = {s: resolve_style(v, look, errors) for s, v in node.states.items()}
    if node.kind == "ScrollBox":  # the spec's scrollbar, under the block's and a rule's own keys
        style = {**scrollbar_style(look), **{k: v for k, v in style.items()}}
        style = {k: v for k, v in style.items() if k not in props}
    if takes_ring(node) and _allowed(node.kind, "Outline_Width"):
        # the ring of keyboard focus, under whatever ``:focused`` rule the file or a stylesheet
        # has (its ``Outline_*`` keys replace the ring's); it does not touch the block's shadows
        states["focused"] = {**ring, **states.get("focused", {})}
    return dataclasses.replace(
        node,
        props=props,
        style=style,
        states=states,
        children=tuple(
            _resolve_node(c, look, errors, ring) for c in node.children if isinstance(c, m.Node)
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


def apply_module_rules(
    roots: Sequence[Child], module: str, rules: Sequence[Rule], target: str | None = None
) -> list[Child]:
    """The rules that name ``module`` applied to its root blocks. A key the root block does not
    take passes to the first block inside it that does, along the first child of each (so
    ``Icon { Foreground: ... }`` colours the SVG a FlexBox holds, and ``Badge { Foreground }`` its
    digits); an inner block is otherwise styled by a type, class or name rule (D40). A module whose
    ``Receives`` names a block (``target``: the first it names) is that block's control: the rules
    go to it, not to the container around it."""
    mine = [r for r in rules if r.kind == "module" and r.target == module and not r.part]
    if not mine:
        return list(roots)
    if target is not None:
        return _at(list(roots), target, mine)
    return [_down(root, mine) if isinstance(root, m.Node) else root for root in roots]


def _at(children: Sequence[Child], name: str, hits: Sequence[Rule]) -> list[Child]:
    """``children`` with the block called ``name`` (wherever it stands) styled by ``hits``."""
    out: list[Child] = []
    for node in children:
        if isinstance(node, m.Node):
            node = (
                _down(node, hits)
                if node.name == name
                else dataclasses.replace(node, children=tuple(_at(node.children, name, hits)))
            )
        elif isinstance(node, m.IfNode):
            node = dataclasses.replace(
                node,
                body=tuple(_at(node.body, name, hits)),
                else_body=None
                if node.else_body is None
                else tuple(_at(node.else_body, name, hits)),
            )
        elif isinstance(node, m.ForNode):
            node = dataclasses.replace(node, body=tuple(_at(node.body, name, hits)))
        out.append(node)
    return out


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
    folded = dataclasses.replace(node, style=_fold(node, hits), states=_fold_states(node, hits))
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
                _ref_value(value, tokens, key)
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
    """A warning for each ``:hovered``, ``:pressed`` or ``:focused`` style the rules give a block
    that tre sends no pointer events and that takes no focus (a ``Text``): the state would never
    hold, so the rule does nothing there (a ``:hovered`` or ``:pressed`` on a module's part is
    not one: the part follows the pointer on its root block). ``module`` is the call name when
    ``children`` are a module's layout."""
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
            if state in m.FLAG_STATES and state != "focused":  # these need no pointer: a Text can
                continue  # be disabled or chosen, never focused
            if node.part and state in ("hovered", "pressed"):
                continue  # a module's part follows the pointer on its root (``View._wire_parts``)
            o = next(iter(values.values())).origin if values else node.origin
            found.append(
                Finding(
                    o.file,
                    o.line,
                    o.column,
                    "warning",
                    "state-never-applies",
                    f"a :{state} style reaches a {node.kind}, which tre sends no "
                    f"{'focus' if state == 'focused' else 'pointer'} events",
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
