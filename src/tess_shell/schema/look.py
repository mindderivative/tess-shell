"""Read a theme and a stylesheet (Style Schema > Theme Tokens and Stylesheet Selectors).

A theme file holds token groups; each token keeps its written value and is read by the key that
refers to it (``$color.surface`` in a ``Foreground`` is read as a colour). Values are checked here
by their group, so a bad colour in a theme is reported at the theme's own line. A stylesheet holds
``Rule`` blocks; a selector is a type name, a ``.class`` or a ``#name``. Selectors with a state
(``:hovered``) or a part (``::track``) are read and skipped with a warning: they need the events
layer.
"""

from __future__ import annotations

import re

import tess_dl
from tess_dl import Block, Document, Property

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.schema import blocks
from tess_shell.schema.findings import Finding, nearest
from tess_shell.schema.model import MODES, Rule, StylesheetDef, ThemeDef, Token
from tess_shell.schema.shell import _Ctx, _scalar_block_keys
from tess_shell.schema.values import ValueProblem, coerce, named_shadows

GROUPS = ("Color", "Type", "Shape", "Space", "Elevation", "Motion")
_MODE_BLOCKS = {"Light": "light", "Dark": "dark", "High_Contrast": "high_contrast"}
_MODE_BLOCKS["Reduced_Motion"] = "reduced_motion"
DESKTOP = "DESKTOP"  # ``Accent: DESKTOP`` asks for the desktop's accent colour

# the kind a token's written value is checked as, by its place in the theme
_TYPE_LEAF = {
    "font_size": "positive",
    "font_weight": "whole",
    "line_height": "positive",
    "font_family": "font_family",
}


def _kind(path: tuple[str, ...]) -> str | None:
    group, leaf = path[0], path[-1]
    if group == "color":
        return "color"
    if group in ("shape", "space"):
        return "number"
    if group == "type":
        return _TYPE_LEAF.get(leaf)
    if group == "motion":
        return "number" if path[1:2] == ("duration",) else None
    return None


def _flatten(
    ctx: _Ctx,
    block: Block,
    prefix: tuple[str, ...],
    out: dict[str, Token],
    reach: list[Property],
) -> None:
    for entry in block.entries:
        if isinstance(entry, Property):
            path = (*prefix, entry.key.lower())
            kind = _kind(path)
            word = entry.value.text if isinstance(entry.value, tess_dl.Word) else None
            if kind is not None and not (path == ("color", "accent") and word == DESKTOP):
                try:
                    typed = coerce(kind, entry.value, ctx.origin(entry.key_origin))
                    if kind == "positive" and isinstance(typed, m.Number) and typed.value <= 0:
                        raise ValueProblem("bad-value", "must be greater than 0", "")
                except ValueProblem as exc:
                    ctx.problem(entry.value_origin, entry.key, exc)
                    continue
            out[".".join(path)] = Token(entry.value, ctx.origin(entry.key_origin))
        elif isinstance(entry, Block):
            if prefix == ("elevation",) and entry.type == "Max":
                shadows = next(
                    (e for e in entry.entries if isinstance(e, Block) and e.type == "Shadows"), None
                )
                if shadows is None:
                    ctx.add(entry.origin, "missing-key", "Elevation.Max needs a Shadows block", "")
                    continue
                try:
                    out["elevation.max"] = Token(
                        named_shadows(shadows, ctx.origin(entry.origin)),
                        ctx.origin(entry.origin),
                    )
                except ValueProblem as exc:
                    ctx.problem(shadows.origin, "Shadows", exc)
            else:
                _flatten(ctx, entry, (*prefix, entry.type.lower()), out, reach)
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")


def _groups(ctx: _Ctx, block: Block, scope: str) -> dict[str, Token]:
    out: dict[str, Token] = {}
    for entry in block.entries:
        if isinstance(entry, Block) and entry.type in GROUPS:
            _flatten(ctx, entry, (entry.type.lower(),), out, [])
        elif isinstance(entry, Block) and entry.type == "Modes" and scope == "theme":
            continue
        else:
            origin = (
                entry.origin if isinstance(entry, Block) else getattr(entry, "key_origin", None)
            )
            key = entry.type if isinstance(entry, Block) else getattr(entry, "key", "?")
            ctx.unknown(origin, key, [*GROUPS, *(["Modes"] if scope == "theme" else [])], scope)
    return out


def read_theme(document: Document, file: str) -> tuple[ThemeDef | None, list[Finding]]:
    """Type a parsed ``<Name>_Theme.tdl`` (root block ``Theme { }``)."""
    ctx = _Ctx(file, lambda _: "")
    root = document.root
    if root.type != "Theme":
        ctx.add(
            root.origin,
            "theme-root",
            f"the root block is {root.type}, not Theme",
            "write Theme { }",
        )
        return None, ctx.findings
    tokens = _groups(ctx, root, "theme")
    modes: dict[str, dict[str, Token]] = {}
    for entry in root.entries:
        if not (isinstance(entry, Block) and entry.type == "Modes"):
            continue
        for mode in entry.entries:
            if isinstance(mode, Block) and mode.type in _MODE_BLOCKS:
                modes[_MODE_BLOCKS[mode.type]] = _groups(ctx, mode, "mode")
            else:
                origin = (
                    mode.origin if isinstance(mode, Block) else getattr(mode, "key_origin", None)
                )
                key = mode.type if isinstance(mode, Block) else getattr(mode, "key", "?")
                ctx.unknown(origin, key, list(_MODE_BLOCKS), "Modes")
    name = _meta_name(document, file)
    if any(f.severity == "error" for f in ctx.findings):
        return None, ctx.findings
    assert name is not None
    return ThemeDef(name, file, tokens, modes), ctx.findings


def _meta_name(document: Document, file: str) -> str | None:
    for entry in document.metadata.entries:
        if isinstance(entry, Property) and entry.key == "Name":
            v = entry.value
            return v.text if isinstance(v, tess_dl.Word) else getattr(v, "value", None)
    return None


def effective_tokens(
    theme: ThemeDef, appearance: Appearance, fallback: ThemeDef | None = None
) -> dict[str, Token]:
    """The theme's tokens for the desktop's current look. A token the theme lacks comes from
    ``fallback`` (the ``Default`` theme), token by token, in the fallback's own current look
    (D42)."""
    tokens = _effective(theme, appearance)
    if fallback is not None and fallback is not theme:
        tokens = {**_effective(fallback, appearance), **tokens}
    return tokens


def _effective(theme: ThemeDef, appearance: Appearance) -> dict[str, Token]:
    """One theme's tokens: the base values, then the light or dark mode, then high contrast, then
    reduced motion (which also sets every duration to 0)."""
    tokens = dict(theme.tokens)
    order: list[str] = []
    if appearance.scheme in ("light", "dark"):
        order.append(appearance.scheme)
    if appearance.high_contrast:
        order.append("high_contrast")
    if appearance.reduced_motion:
        order.append("reduced_motion")
    for mode in order:
        tokens.update(theme.modes.get(mode, {}))
    accent = tokens.get("color.accent")
    if (
        accent is not None
        and isinstance(accent.value, tess_dl.Word)
        and accent.value.text == DESKTOP
    ):
        # ``Accent: DESKTOP`` follows the desktop; with no desktop accent it is the primary colour
        if appearance.accent is not None:
            r, g, b = appearance.accent
            written: tess_dl.Value = tess_dl.String(f"#{r:02x}{g:02x}{b:02x}", "")
            tokens["color.accent"] = Token(written, accent.origin)
        elif "color.primary" in tokens:
            tokens["color.accent"] = tokens["color.primary"]
        else:
            del tokens["color.accent"]
    if appearance.reduced_motion:
        for path, token in list(tokens.items()):
            if path.startswith("motion.duration."):
                tokens[path] = Token(tess_dl.Number(0, "0"), token.origin)
    return tokens


# -- stylesheets ------------------------------------------------------------------------------

_SELECTOR = re.compile(
    r"^(?P<head>[#.]?)(?P<name>[A-Za-z][A-Za-z0-9_]*)(?P<part>::[A-Za-z_]+)?(?P<state>:[A-Za-z_]+)?$"
)

# the states a rule can name that no block can be in yet, and why
_STATES_NOT_BUILT = {"focused": "no block can take focus yet (keyboard focus is M6)"}

# every style key of every block, with its kind; the kinds agree across blocks
STYLE_UNION: dict[str, str] = {k: v for row in blocks.BLOCKS.values() for k, v in row[1].items()}


def _rule(ctx: _Ctx, block: Block, module_names: set[str]) -> Rule | None:
    selector = next(
        (e for e in block.entries if isinstance(e, Property) and e.key == "Selector"), None
    )
    if selector is None:
        ctx.add(block.origin, "missing-key", "a Rule needs a Selector", 'write Selector: "Text"')
        return None
    text = selector.value.value if isinstance(selector.value, tess_dl.String) else None
    if text is None:
        ctx.add(
            selector.value_origin,
            "bad-value",
            "Selector is a quoted string",
            'write Selector: ".warning"',
        )
        return None
    found = _SELECTOR.match(text.strip())
    if found is None:
        ctx.add(
            selector.value_origin,
            "bad-selector",
            f"'{text}' is not a selector",
            'a selector is "Text", ".class", "#name", with an optional ":state" or "::part"',
        )
        return None
    part = (found["part"] or "::")[2:]
    if part and found["head"]:
        ctx.add(
            selector.value_origin,
            "not-built",
            f"the selector part ::{part} after a {'class' if found['head'] == '.' else '#name'} "
            "is not built: a part is addressed through its module's name",
            f'write "<Module>::{part}", with the module\'s own name; the rule is skipped',
            "warning",
        )
        return None
    if part and found["name"] not in (module_names or ()):
        close = nearest(found["name"], sorted(module_names or ()))
        ctx.add(
            selector.value_origin,
            "bad-selector",
            f"::{part} is a part of a module and {found['name']} is no module",
            f"did you mean {', '.join(close)}?"
            if close
            else "a part selector names a module: Slider::track",
        )
        return None
    state = (found["state"] or ":")[1:]
    if state in _STATES_NOT_BUILT:
        ctx.add(
            selector.value_origin,
            "not-built",
            f"the state :{state} is not built: {_STATES_NOT_BUILT[state]}",
            "the rule is skipped",
            "warning",
        )
        return None
    if state and state not in m.STATES:
        ctx.add(
            selector.value_origin,
            "bad-selector",
            f"':{state}' is not a style state",
            "the states are :hovered, :pressed, :checked, :selected, :focused and :disabled",
        )
        return None
    head, name = found["head"], found["name"]
    kind = {"": "type", ".": "class", "#": "name"}[head]
    body = tess_dl.Block(
        "Rule",
        tuple(e for e in block.entries if not (isinstance(e, Property) and e.key == "Selector")),
    )
    if kind == "type":
        if name in module_names:
            # a module's name styles the module's root blocks at every use (D40); with a part it
            # styles that part's block (``Slider::track``)
            values = _scalar_block_keys(ctx, body, STYLE_UNION, "Rule")
            return Rule("module", name, values, ctx.origin(block.origin), state, part)
        if name not in blocks.BLOCKS:
            ctx.unknown(selector.value_origin, name, [*blocks.BLOCKS], "block in a selector")
            return None
        table = blocks.BLOCKS[name][1]
        for entry in body.entries:
            key = entry.key if isinstance(entry, Property) else getattr(entry, "type", "")
            if key and key not in table and key in STYLE_UNION:
                ctx.add(
                    getattr(entry, "key_origin", None) or getattr(entry, "origin", None),
                    "unknown-key",
                    f"{name} has no style key {key}",
                    f"did you mean {', '.join(nearest(key, table))}?"
                    if nearest(key, table)
                    else f"keys: {', '.join(table)}",
                )
    values = _scalar_block_keys(ctx, body, STYLE_UNION, "Rule")
    return Rule(kind, name, values, ctx.origin(block.origin), state)  # type: ignore[arg-type]


def read_stylesheet(
    document: Document, file: str, module_names: set[str] | None = None
) -> tuple[StylesheetDef | None, list[Finding]]:
    """Type a parsed ``<Name>_Stylesheet.tdl`` (root block ``Stylesheet { }``)."""
    ctx = _Ctx(file, lambda _: "")
    root = document.root
    if root.type != "Stylesheet":
        ctx.add(
            root.origin,
            "stylesheet-root",
            f"the root block is {root.type}, not Stylesheet",
            "write Stylesheet { }",
        )
        return None, ctx.findings
    rules: list[Rule] = []
    for entry in root.entries:
        if isinstance(entry, Block) and entry.type == "Rule":
            rule = _rule(ctx, entry, module_names or set())
            if rule is not None:
                rules.append(rule)
        else:
            origin = (
                entry.origin if isinstance(entry, Block) else getattr(entry, "key_origin", None)
            )
            key = entry.type if isinstance(entry, Block) else getattr(entry, "key", "?")
            ctx.unknown(origin, key, ["Rule"], "Stylesheet")
    name = _meta_name(document, file)
    if any(f.severity == "error" for f in ctx.findings):
        return None, ctx.findings
    assert name is not None
    return StylesheetDef(name, file, tuple(rules)), ctx.findings


__all__ = ["MODES", "effective_tokens", "read_stylesheet", "read_theme"]
