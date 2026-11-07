"""Check a parsed shell file against the M1 schema and type it (Validation and Errors, stage 4).

Reads the public ``tess_dl`` tree and returns the typed model: monitors, Bars and the binder's
:class:`~tess_shell.binder.model.Node` trees. Every problem is collected, one finding each, at
the position of the offending key or value.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping

import tess_dl
from tess_dl import Block, Document, Property

from tess_shell.binder import model as m
from tess_shell.schema import blocks
from tess_shell.schema.findings import Finding, Severity, nearest
from tess_shell.schema.model import (
    PARAM_TYPES,
    BarDef,
    ClassDef,
    EdgeDef,
    FrameBorder,
    FrameDef,
    IconSource,
    ModuleDef,
    MonitorDef,
    PanelDef,
    ParamDecl,
    PopupDef,
    ShellDef,
    StyleDef,
    use_names,
)
from tess_shell.schema.style import apply_style
from tess_shell.schema.tree import position
from tess_shell.schema.values import (
    ValueProblem,
    coerce,
    named_shadows,
    named_sides,
    token_ref,
)

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SURFACES = ("Bar", "Frame", "Panel", "Popup")
_NOT_BUILT = "not built in M1"


class _Ctx:
    def __init__(
        self,
        file: str,
        read_text: Callable[[str], str],
        modules: Mapping[str, ModuleDef] | None = None,
        import_module: Callable[[str], str | None] | None = None,
        load_style: Callable[[str], StyleDef | None] | None = None,
        icons: IconSource | None = None,
    ) -> None:
        self.load_style = load_style
        self.icons = icons
        self.file = file
        self.read_text = read_text
        self.modules: Mapping[str, ModuleDef] = modules or {}
        # the call name of the module file an ``Import:`` names (a path relative to this file)
        self.import_module = import_module
        self.findings: list[Finding] = []
        self.in_module = False  # a module's layout: a bare action name is one of its @actions
        self.in_popup = False  # the blocks of a Popup: Close closes the Popup that holds them
        self.names: dict[str, m.Origin] = {}
        self.selectors: dict[tuple[str, str], m.Origin] = {}

    def origin(self, o: tess_dl.Origin | None) -> m.Origin:
        line, column = position(o)
        return m.Origin(self.file, line, column)

    def add(
        self,
        o: tess_dl.Origin | m.Origin | None,
        rule: str,
        message: str,
        hint: str = "",
        severity: Severity = "error",
    ) -> None:
        if isinstance(o, m.Origin):
            line, column = o.line, o.column
        else:
            line, column = position(o)
        self.findings.append(Finding(self.file, line, column, severity, rule, message, hint))

    def problem(self, o: tess_dl.Origin | None, key: str, exc: ValueProblem) -> None:
        self.add(o, exc.rule, f"{key}: {exc.message}", exc.hint)

    def name(self, prop: Property) -> str | None:
        value = prop.value
        text = value.text if isinstance(value, tess_dl.Word) else None
        if text is None or not _NAME.match(text):
            self.add(
                prop.value_origin,
                "bad-name",
                f"Name must be letters, digits and _, starting with a letter: {prop.value!r}",
                "write a name such as Top_Bar",
            )
            return None
        here = self.origin(prop.key_origin)
        if text in self.names:
            self.add(
                prop.value_origin,
                "name-duplicate",
                f"the name {text} is used twice, first at {self.names[text]}",
                "a Name is unique across the shell",
            )
        else:
            self.names[text] = here
        return text

    def name_ref(self, prop: Property) -> str | None:
        """A reference to a surface's ``Name`` (``Attach_To: Top_Bar``)."""
        value = prop.value
        text = value.text if isinstance(value, tess_dl.Word) else None
        if text is None or not _NAME.match(text):
            self.add(
                prop.value_origin,
                "bad-name",
                f"{prop.key} is the Name of a surface: letters, digits and _",
                f"write {prop.key}: Top_Bar",
            )
            return None
        return text

    def unknown(
        self, origin: tess_dl.Origin | None, key: str, allowed: list[str], what: str
    ) -> None:
        close = nearest(key, allowed)
        hint = (
            f"did you mean {', '.join(close)}?"
            if close
            else f"allowed: {', '.join(sorted(allowed))}"
        )
        self.add(origin, "unknown-key", f"unknown {what} {key}", hint)

    def not_built(
        self, origin: tess_dl.Origin | None, what: str, severity: Severity = "error"
    ) -> None:
        self.add(origin, "not-built", f"{what} is {_NOT_BUILT}", "", severity)


def _choices(block: str, key: str) -> tuple[str, ...]:
    return blocks.CHOICES.get((block, key)) or blocks.CHOICES.get(("*", key)) or ()


def slot_value(ctx: _Ctx, prop: Property) -> m.SlotValue | None:
    """A value written with ``{{ }}`` slots, or ``None`` for a plain value."""
    value = prop.value
    parts: list[str | m.SlotPart] = []
    if isinstance(value, tess_dl.Slot):
        parts.append(m.SlotPart(value.text, origin=ctx.origin(value.text_origin)))
    elif isinstance(value, tess_dl.Template):
        for part in value.parts:
            if isinstance(part, str):
                parts.append(part)
            else:
                parts.append(m.SlotPart(part.text, origin=ctx.origin(part.text_origin)))
    else:
        return None
    return m.SlotValue(tuple(parts), origin=ctx.origin(prop.key_origin))


def _icon(ctx: _Ctx, prop: Property, slot: m.SlotValue | None) -> m.Value | None:
    """``Icon: "mdi:account"``: the name becomes an SVG document read from the icon sets."""
    value = prop.value
    name = value.value if isinstance(value, tess_dl.String) else getattr(value, "text", None)
    if slot is not None or not isinstance(name, str) or not name:
        ctx.add(prop.value_origin, "bad-value", "Icon is an icon name", 'write Icon: "mdi:account"')
        return None
    found = ctx.icons.lookup(name) if ctx.icons is not None else None
    if found is None:
        close = ctx.icons.nearest(name) if ctx.icons is not None else []
        hint = (
            f"did you mean {', '.join(close)}?"
            if close
            else "icon sets are JSON files in the Icons folder of the config directory"
        )
        ctx.add(prop.value_origin, "icon-not-found", f"no icon named {name}", hint)
        return None
    return m.Text(found, origin=ctx.origin(prop.key_origin))


def _typed(
    ctx: _Ctx, block: str, prop: Property, kind: str, read_text: bool = False
) -> m.Value | None:
    slot = slot_value(ctx, prop)
    if kind == "icon":
        return _icon(ctx, prop, slot)
    if slot is not None:
        if read_text:
            ctx.add(
                prop.value_origin,
                "bad-value",
                f"{prop.key} cannot hold a slot",
                "write a file name",
            )
            return None
        return slot
    try:
        if not read_text:
            ref = token_ref(
                prop.value, kind, _choices(block, prop.key), ctx.origin(prop.key_origin)
            )
            if ref is not None:
                return ref
        return coerce(
            kind,
            prop.value,
            ctx.origin(prop.key_origin),
            _choices(block, prop.key),
            ctx.read_text if read_text else None,
        )
    except ValueProblem as exc:
        ctx.problem(prop.value_origin, prop.key, exc)
        return None


def _scalar_block_keys(
    ctx: _Ctx, block: Block, table: Mapping[str, str], what: str
) -> dict[str, m.Value]:
    """The keys of an inline ``Style { }``; ``Border { Width, Color }`` is flattened (D78)."""
    out: dict[str, m.Value] = {}
    for entry in block.entries:
        if isinstance(entry, Property):
            kind = table.get(entry.key)
            if kind is None:
                ctx.unknown(entry.key_origin, entry.key, list(table), f"{what} key")
                continue
            value = _typed(ctx, what, entry, kind)
            if value is not None:
                out[entry.key] = value
        elif isinstance(entry, Block):
            if entry.type == "Border":
                for sub in entry.entries:
                    if isinstance(sub, Property) and sub.key in ("Width", "Color"):
                        flat = f"Border_{sub.key}"
                        if flat not in table:
                            ctx.unknown(sub.key_origin, flat, list(table), f"{what} key")
                            continue
                        value = _typed(ctx, what, sub, table[flat])
                        if value is not None:
                            out[flat] = value
                    elif isinstance(sub, Property):
                        ctx.unknown(sub.key_origin, sub.key, ["Width", "Color"], "Border key")
            elif entry.type in table and table[entry.type] in ("sides", "bleed"):
                try:
                    out[entry.type] = named_sides(entry, ctx.origin(entry.origin))
                except ValueProblem as exc:
                    ctx.problem(entry.origin, entry.type, exc)
            elif entry.type in table and table[entry.type] == "shadows":
                try:
                    out[entry.type] = named_shadows(entry, ctx.origin(entry.origin))
                except ValueProblem as exc:
                    ctx.problem(entry.origin, entry.type, exc)
            else:
                ctx.unknown(entry.origin, entry.type, list(table), f"{what} key")
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    return out


def _part(ctx: _Ctx, slot: tess_dl.Slot) -> m.SlotPart:
    return m.SlotPart(slot.text, origin=ctx.origin(slot.text_origin))


def _body(ctx: _Ctx, entries: tuple[tess_dl.Entry, ...]) -> tuple[Child, ...]:
    """The blocks of an ``If`` or ``For`` body. A module call inside one is not built yet: it
    would need a module use to appear and go away while the shell runs."""
    out: list[Child] = []
    for entry in entries:
        if isinstance(entry, Block):
            node = _block(ctx, entry)
            if isinstance(node, m.UseNode):
                ctx.not_built(entry.origin, "a module call inside If or For")
            elif node is not None:
                out.append(node)
        elif isinstance(entry, tess_dl.If):
            out.append(_if(ctx, entry))
        elif isinstance(entry, tess_dl.For):
            out.append(_for(ctx, entry))
        elif isinstance(entry, Property):
            what = "Import" if entry.key == "Import" else f"the key {entry.key}"
            ctx.not_built(entry.key_origin, f"{what} inside If or For")
    return tuple(out)


def _if(ctx: _Ctx, entry: tess_dl.If) -> m.IfNode:
    return m.IfNode(
        condition=_part(ctx, entry.condition),
        body=_body(ctx, entry.body),
        else_body=None if entry.else_body is None else _body(ctx, entry.else_body),
        origin=ctx.origin(entry.origin),
    )


def _for(ctx: _Ctx, entry: tess_dl.For) -> m.ForNode:
    body = _body(ctx, entry.body)
    head = next((n.kind for n in body if isinstance(n, m.Node)), "For")
    if not _NAME.match(entry.variable):
        ctx.add(
            entry.origin,
            "bad-name",
            f"the loop variable {entry.variable!r} must be letters, digits and _",
            "write For item In {{ items }} Key {{ item.id }}",
        )
    return m.ForNode(
        variable=entry.variable,
        items=_part(ctx, entry.items),
        key=_part(ctx, entry.key),
        name=head,
        body=body,
        origin=ctx.origin(entry.origin),
    )


def _imports(ctx: _Ctx, entry: Property) -> list[Child]:
    """``Import: Clock_Module.tdl`` or a list of them: each embeds that module, called with its
    defaults, at this position (Module File > Using a Module)."""
    value = entry.value
    items = list(value.items) if isinstance(value, tess_dl.List) else [value]
    out: list[Child] = []
    for item in items:
        text = item.value if isinstance(item, tess_dl.String) else getattr(item, "text", None)
        if not isinstance(text, str):
            ctx.add(entry.value_origin, "bad-value", "Import names a file", "write a file name")
            continue
        if text.endswith("_Shell.tdl"):
            ctx.not_built(item.origin or entry.value_origin, "Import of a shell file")
            continue
        found = ctx.import_module(text) if ctx.import_module is not None else None
        if found is None:
            ctx.add(
                item.origin or entry.value_origin,
                "import-not-found",
                f"Import: {text} is not a module file",
                "a path is relative to this file and names a _Module.tdl",
            )
            continue
        out.append(m.UseNode(found, origin=ctx.origin(entry.key_origin)))
    return out


def _children(
    ctx: _Ctx, holder: Block, child_types: Callable[[Block], Child | None]
) -> list[Child]:
    out: list[Child] = []
    for entry in holder.entries:
        if isinstance(entry, Block):
            node = child_types(entry)
            if node is not None:
                out.append(node)
        elif isinstance(entry, Property) and entry.key == "Import":
            out.extend(_imports(ctx, entry))
        elif isinstance(entry, Property):
            ctx.add(
                entry.key_origin,
                "unknown-key",
                f"Children holds blocks, not the key {entry.key}",
                "write a block such as FlexBox { }",
            )
        elif isinstance(entry, tess_dl.If):
            out.append(_if(ctx, entry))
        elif isinstance(entry, tess_dl.For):
            out.append(_for(ctx, entry))
    return out


Child = m.Node | m.UseNode | m.IfNode | m.ForNode

_PARAM_KINDS = {"string": "text", "number": "number", "boolean": "bool"}


def _use(ctx: _Ctx, block: Block) -> m.UseNode | None:
    """A call of a module: the head is its name, the keys are its params (Module File)."""
    module = ctx.modules[block.type]
    name: str | None = None
    params: dict[str, m.Value] = {}
    tooltip: m.TooltipRef | None = None
    for entry in block.entries:
        if isinstance(entry, Property):
            key = entry.key
            if key == "Name":
                name = ctx.name(entry)
            elif key == "Tooltip":
                tooltip = _tooltip_name(ctx, entry, f"a use of {module.name}")
            elif key in ("Style", "Class") or key.startswith("On_"):
                ctx.not_built(entry.key_origin, f"{key} on a module call")
            elif key in module.params:
                decl = module.params[key]
                if slot_value(ctx, entry) is not None:
                    ctx.not_built(entry.value_origin, "a slot in a module param")
                    continue
                try:
                    params[key] = coerce(
                        _PARAM_KINDS[decl.type], entry.value, ctx.origin(entry.key_origin)
                    )
                except ValueProblem as exc:
                    ctx.problem(entry.value_origin, key, exc)
            else:
                allowed = ["Name", *module.params]
                ctx.unknown(entry.key_origin, key, allowed, f"param of {module.name}")
        elif isinstance(entry, Block) and entry.type == "Tooltip":
            tooltip = _tooltip_block(ctx, entry)
        elif isinstance(entry, Block):
            ctx.unknown(entry.origin, entry.type, ["Name", *module.params], f"key of {module.name}")
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    for decl in module.params.values():
        if decl.name not in params and decl.default is None:
            ctx.add(
                block.origin,
                "missing-key",
                f"{module.name} needs the param {decl.name}",
                f"write {decl.name}: ...",
            )
    return m.UseNode(
        module.name, name=name, params=params, tooltip=tooltip, origin=ctx.origin(block.origin)
    )


def _block(ctx: _Ctx, block: Block) -> Child | None:
    row = blocks.BLOCKS.get(block.type)
    if row is None and block.type in ctx.modules:
        return _use(ctx, block)
    if row is None:
        ctx.unknown(block.origin, block.type, [*blocks.BLOCKS, *ctx.modules], "block")
        return None
    prop_keys, style_keys = row
    allowed = [*prop_keys, *style_keys, "Name", "Style", "Children"]
    name: str | None = None
    props: dict[str, m.Value] = {}
    style: dict[str, m.Value] = {}
    style_at: dict[str, tess_dl.Origin | None] = {}
    prop_at: dict[str, tess_dl.Origin | None] = {}
    classes: list[str] = []
    handlers: dict[str, m.Handler] = {}
    children: list[Child] = []
    tooltip: m.TooltipRef | None = None
    for entry in block.entries:
        if isinstance(entry, Property):
            key = entry.key
            if key == "Name":
                name = ctx.name(entry)
            elif key == "Style":
                ctx.not_built(entry.key_origin, "a Style file on a block (a module has one)")
            elif key == "Class":
                classes.extend(_class_names(ctx, entry))
            elif key.startswith("On_"):
                handler = _handler(ctx, block.type, key, entry.key_origin, entry.value)
                if handler is not None:
                    handlers[key] = handler
            elif key == "Tooltip":
                tooltip = _tooltip_name(ctx, entry, f"a {block.type}", block.type)
            elif key in prop_keys or key in style_keys:
                kind = prop_keys.get(key) or style_keys[key]
                value = _typed(ctx, block.type, entry, kind, read_text=kind == "svg_source")
                if value is not None:
                    props[key] = value
                    prop_at[key] = entry.key_origin
            else:
                ctx.unknown(entry.key_origin, key, allowed, f"key in {block.type}")
        elif isinstance(entry, Block):
            if entry.type.startswith("On_"):
                handler = _handler(ctx, block.type, entry.type, entry.origin, entry)
                if handler is not None:
                    handlers[entry.type] = handler
            elif entry.type == "Tooltip":
                tooltip = _tooltip_block(ctx, entry, block.type)
            elif entry.type == "Style":
                for k, v in _scalar_block_keys(ctx, entry, style_keys, block.type).items():
                    style[k] = v
                for sub in entry.entries:
                    if isinstance(sub, Property):
                        style_at[sub.key] = sub.key_origin
            elif entry.type == "Children":
                if block.type not in ("Box", "FlexBox"):
                    ctx.add(entry.origin, "bad-children", f"{block.type} cannot have children", "")
                else:
                    children = _children(ctx, entry, lambda b: _block(ctx, b))
            elif entry.type in ("Padding", "Margin") and entry.type in prop_keys:
                try:
                    props[entry.type] = named_sides(entry, ctx.origin(entry.origin))
                    prop_at[entry.type] = entry.origin
                except ValueProblem as exc:
                    ctx.problem(entry.origin, entry.type, exc)
            elif entry.type == "Shadows" and "Shadows" in {**prop_keys, **style_keys}:
                try:
                    props["Shadows"] = named_shadows(entry, ctx.origin(entry.origin))
                    prop_at["Shadows"] = entry.origin
                except ValueProblem as exc:
                    ctx.problem(entry.origin, "Shadows", exc)
            elif entry.type == "Border" and "Border_Width" in {**prop_keys, **style_keys}:
                flat = _scalar_block_keys(
                    ctx, tess_dl.Block("Style", (entry,)), style_keys, block.type
                )
                props.update(flat)
            else:
                ctx.unknown(entry.origin, entry.type, allowed, f"block in {block.type}")
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    written = {e.key for e in block.entries if isinstance(e, Property)}
    for need in blocks.REQUIRED.get(block.type, ()):
        options = (need,) if isinstance(need, str) else need
        if not any(k in props or k in written for k in options):
            wanted = " or ".join(options)
            ctx.add(
                block.origin,
                "missing-key",
                f"{block.type} needs {wanted}",
                f"write {options[0]}: ...",
            )
    if block.type == "SVG" and "Source" in written and "Icon" in written:
        ctx.add(block.origin, "bad-key", "an SVG has a Source or an Icon, not both", "keep one")
    if "Shadows" in props and "Elevation" in props:
        ctx.add(
            prop_at.get("Elevation"),
            "shadow-both",
            f"Elevation and Shadows are both written ({ctx.origin(prop_at.get('Shadows'))}); "
            "Shadows wins",
            "keep one of the two",
            "warning",
        )
        del props["Elevation"]
    for key in props.keys() & style.keys():
        ctx.add(
            style_at.get(key),
            "style-duplicate",
            f"{key} is written both in the block ({ctx.origin(prop_at.get(key))}) and in its Style",
            "keep one of the two",
        )
    return m.Node(
        block.type,
        name=name,
        props=props,
        style=style,
        children=tuple(children),
        classes=tuple(classes),
        handlers=handlers,
        tooltip=tooltip,
        origin=ctx.origin(block.origin),
    )


def _handler(
    ctx: _Ctx,
    block: str,
    key: str,
    origin: tess_dl.Origin | None,
    value: tess_dl.Value | Block,
) -> m.Handler | None:
    """An ``On_<Event>`` value: a bare action name, or a block ``{ Action: name, arg: value }``
    (Events and Actions > A Handler). An unknown event, an event this block cannot raise, a
    built-in action that is not built yet, and (in a shell file) any other name are errors."""
    if key not in blocks.EVENT_KEYS:
        ctx.unknown(origin, key, list(blocks.EVENT_KEYS), "event key")
        return None
    if key not in blocks.BLOCK_EVENTS.get(block, ()):
        raised = ", ".join(blocks.BLOCK_EVENTS.get(block, ()))
        hint = f"it raises: {raised}" if raised else f"put {key} on the FlexBox or Box around it"
        ctx.add(origin, "event-not-raised", f"a {block} does not raise {key}", hint)
        return None
    args: dict[str, object] = {}
    if isinstance(value, Block):
        action_prop = next(
            (e for e in value.entries if isinstance(e, Property) and e.key == "Action"), None
        )
        if action_prop is None:
            ctx.add(
                value.origin,
                "missing-key",
                f"{key} needs an Action",
                f"write {key} {{ Action: name }}",
            )
            return None
        action_value, at = action_prop.value, action_prop.value_origin
        for e in value.entries:
            if not isinstance(e, Property) or e.key == "Action":
                continue
            plain = _plain(e.value)
            if plain is None:
                ctx.add(
                    e.value_origin,
                    "bad-value",
                    f"{e.key}: an argument is a string, a number or true or false",
                    "",
                )
                return None
            args[e.key] = plain
    else:
        action_value, at = value, origin
    name = action_value.text if isinstance(action_value, tess_dl.Word) else None
    if name is None or not _NAME.match(name):
        ctx.add(
            at,
            "bad-name",
            f"{key} names an action: letters, digits and _",
            f"write {key}: Open_Launcher",
        )
        return None
    if name in blocks.BUILTIN_ACTIONS:
        if name not in blocks.BUILTIN_BUILT:
            ctx.not_built(at, f"the built-in action {name}")
            return None
        if name == "Close":
            return _close(ctx, key, args, at, origin)
        target = args.get("Target")
        if not isinstance(target, str):
            ctx.add(
                at,
                "missing-key",
                f"the action {name} needs a Target, the Name of a Panel",
                f"write {key} {{ Action: {name}, Target: Launcher }}",
            )
            return None
        return m.Handler(name, args, builtin=True, origin=ctx.origin(origin))
    if not ctx.in_module:
        ctx.add(
            at,
            "unknown-action",
            f"{key}: {name} is not an action a shell file can name",
            f"a shell file names the built-in actions: {', '.join(blocks.BUILTIN_ACTIONS)}",
        )
        return None
    return m.Handler(name, args, origin=ctx.origin(origin))


def _close(
    ctx: _Ctx,
    key: str,
    args: dict[str, object],
    at: tess_dl.Origin | None,
    origin: tess_dl.Origin | None,
) -> m.Handler | None:
    """``Close``: closes the Popup that holds the block, so it takes no ``Target`` and means
    something only in a Popup's blocks (or in a module's layout, which a Popup may use)."""
    if "Target" in args:
        ctx.add(
            at,
            "bad-key",
            "Close takes no Target: it closes the Popup that holds the block",
            "remove Target",
        )
        return None
    if not (ctx.in_popup or ctx.in_module):
        ctx.add(
            at,
            "close-outside-popup",
            f"{key}: Close closes the Popup that holds the block, and this block is in none",
            "write it in a Popup's Children; Hide closes a Panel",
        )
        return None
    return m.Handler("Close", args, builtin=True, origin=ctx.origin(origin))


def _plain(value: tess_dl.Value) -> object | None:
    if isinstance(value, tess_dl.String):
        return value.value
    if isinstance(value, tess_dl.Number):
        return value.value
    if isinstance(value, tess_dl.Word) and value.text in ("true", "false"):
        return value.text == "true"
    if isinstance(value, tess_dl.Word):
        return value.text
    return None


def _class_names(ctx: _Ctx, entry: Property) -> list[str]:
    """``Class: text_style`` or ``Class: [a, b]``."""
    value = entry.value
    items = list(value.items) if isinstance(value, tess_dl.List) else [value]
    names: list[str] = []
    for item in items:
        text = item.value if isinstance(item, tess_dl.String) else getattr(item, "text", None)
        if isinstance(text, str) and _NAME.match(text):
            names.append(text)
        else:
            ctx.add(entry.value_origin, "bad-name", "a class name is letters, digits and _", "")
    return names


def _style_def(ctx: _Ctx, block: Block) -> StyleDef:
    """The body of ``Style { }``: ``Classes { name { Kind: Text, ... } }`` and, per block type,
    default values (``Text { Font_Size: 16 }``)."""
    defaults: dict[str, dict[str, m.Value]] = {}
    classes: dict[str, ClassDef] = {}
    known = ["Classes", *blocks.BLOCKS]
    for entry in block.entries:
        if isinstance(entry, Block) and entry.type == "Classes":
            for cls in entry.entries:
                if not isinstance(cls, Block):
                    continue
                kind_prop = next(
                    (e for e in cls.entries if isinstance(e, Property) and e.key == "Kind"), None
                )
                kind = getattr(kind_prop.value, "text", None) if kind_prop is not None else None
                if kind not in blocks.BLOCKS:
                    ctx.add(
                        (kind_prop.value_origin if kind_prop else cls.origin),
                        "bad-value" if kind_prop else "missing-key",
                        f"the class {cls.type} needs Kind: one of {', '.join(blocks.BLOCKS)}",
                        "write Kind: Text",
                    )
                    continue
                body = tess_dl.Block(
                    cls.type,
                    tuple(
                        e for e in cls.entries if not (isinstance(e, Property) and e.key == "Kind")
                    ),
                )
                values = _scalar_block_keys(ctx, body, blocks.BLOCKS[kind][1], kind)
                classes[cls.type] = ClassDef(kind, values, ctx.origin(cls.origin))
        elif isinstance(entry, Block) and entry.type in blocks.BLOCKS:
            table = blocks.BLOCKS[entry.type][1]
            defaults.setdefault(entry.type, {}).update(
                _scalar_block_keys(ctx, entry, table, entry.type)
            )
        elif isinstance(entry, Block):
            ctx.unknown(entry.origin, entry.type, known, "block in Style")
        elif isinstance(entry, Property):
            ctx.unknown(entry.key_origin, entry.key, known, "key in Style")
    return StyleDef(ctx.file, defaults, classes)


def read_style(document: Document, file: str) -> tuple[StyleDef | None, list[Finding]]:
    """Type a parsed ``<Name>_Style.tdl`` (root block ``Style { }``)."""
    ctx = _Ctx(file, lambda _: "")
    root = document.root
    if root.type != "Style":
        ctx.add(
            root.origin,
            "style-root",
            f"the root block is {root.type}, not Style",
            "write Style { }",
        )
        return None, ctx.findings
    style = _style_def(ctx, root)
    if any(f.severity == "error" for f in ctx.findings):
        return None, ctx.findings
    return style, ctx.findings


_BAR_KEYS: dict[str, str] = {
    "Edge": "enum",
    "Width": "length",
    "Height": "length",
    "Layer": "enum",
    "Alignment": "enum",
    "Offset": "number",
    "Gap": "number",
    "Reserve": "bool",
    "Min_Width": "bound",
    "Min_Height": "bound",
    "Max_Width": "bound",
    "Max_Height": "bound",
}
_BAR_CHOICES: dict[str, tuple[str, ...]] = {
    "Edge": ("TOP", "BOTTOM", "LEFT", "RIGHT"),
    "Layer": ("BOTTOM", "TOP", "OVERLAY"),
    "Alignment": ("START", "CENTER", "END"),
}


def _bar(ctx: _Ctx, block: Block) -> BarDef | None:
    allowed = ["Name", "Style", "Children", *_BAR_KEYS, *blocks.BAR_NOT_BUILT]
    name: str | None = None
    values: dict[str, m.Value] = {}
    style: dict[str, m.Value] = {}
    children: list[Child] = []
    for entry in block.entries:
        if isinstance(entry, Property):
            key = entry.key
            if key == "Name":
                name = ctx.name(entry)
            elif key == "Style":
                ctx.not_built(entry.key_origin, "a Style file")
            elif key in blocks.BAR_NOT_BUILT:
                ctx.not_built(entry.key_origin, f"the Bar key {key}", "warning")
            elif key in _BAR_KEYS:
                try:
                    values[key] = coerce(
                        _BAR_KEYS[key],
                        entry.value,
                        ctx.origin(entry.key_origin),
                        _BAR_CHOICES.get(key, ()),
                    )
                except ValueProblem as exc:
                    ctx.problem(entry.value_origin, key, exc)
            else:
                ctx.unknown(entry.key_origin, key, allowed, "key in Bar")
        elif isinstance(entry, Block):
            if entry.type == "Style":
                style = _scalar_block_keys(ctx, entry, blocks.BAR_STYLE, "Bar")
            elif entry.type == "Children":
                children = _children(ctx, entry, lambda b: _block(ctx, b))
            elif entry.type in blocks.BAR_NOT_BUILT:
                ctx.not_built(entry.origin, f"the Bar key {entry.type}", "warning")
            else:
                ctx.unknown(entry.origin, entry.type, allowed, "block in Bar")
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    if name is None and not any(isinstance(e, Property) and e.key == "Name" for e in block.entries):
        ctx.add(block.origin, "missing-key", "a Bar needs a Name", "write Name: Top_Bar")
    missing = [k for k in ("Edge", "Width", "Height") if k not in values]
    for key in missing:
        if not any(isinstance(e, Property) and e.key == key for e in block.entries):
            ctx.add(block.origin, "missing-key", f"a Bar needs {key}", f"write {key}: ...")
    if name is None or missing:
        return None

    def px(key: str) -> float | None:
        v = values.get(key)
        return v.px if isinstance(v, m.Length) else None

    def num(key: str) -> float | None:
        v = values.get(key)
        return float(v.value) if isinstance(v, m.Number) else None

    def word(key: str, default: str | None) -> str | None:
        v = values.get(key)
        return v.name if isinstance(v, m.Enum) else default

    reserve = values.get("Reserve")
    edge = word("Edge", "TOP")
    assert edge is not None
    return BarDef(
        name=name,
        origin=ctx.origin(block.origin),
        edge=edge,
        width=values["Width"],
        height=values["Height"],
        layer=word("Layer", "TOP") or "TOP",
        alignment=word("Alignment", None),
        offset=num("Offset"),
        gap=num("Gap") or 0,
        reserve=reserve.value if isinstance(reserve, m.Bool) else True,
        min_width=px("Min_Width"),
        min_height=px("Min_Height"),
        max_width=px("Max_Width"),
        max_height=px("Max_Height"),
        style=style,
        children=tuple(children),
    )


def _panel(ctx: _Ctx, block: Block) -> PanelDef | None:
    allowed = [
        "Name",
        "Style",
        "Children",
        *blocks.PANEL_KEYS,
        *blocks.PANEL_NOT_BUILT_ERROR,
        *blocks.PANEL_NOT_BUILT_WARNING,
    ]
    name: str | None = None
    values: dict[str, m.Value] = {}
    anchors: tuple[str, ...] = ()
    attach_to: str | None = None
    written: set[str] = set()  # the keys the Panel wrote, for the Attach_To rules
    style: dict[str, m.Value] = {}
    children: list[Child] = []
    handlers: dict[str, m.Handler] = {}
    animation = ("NONE", 200.0)
    for entry in block.entries:
        if isinstance(entry, Property):
            key = entry.key
            written.add(key)
            if key == "Name":
                name = ctx.name(entry)
            elif key.startswith("On_"):
                handler = _handler(ctx, "Panel", key, entry.key_origin, entry.value)
                if handler is not None:
                    handlers[key] = handler
            elif key == "Style":
                ctx.not_built(entry.key_origin, "a Style file")
            elif key in blocks.PANEL_NOT_BUILT_ERROR:
                ctx.not_built(entry.key_origin, f"the Panel key {key}")
            elif key in blocks.PANEL_NOT_BUILT_WARNING:
                ctx.not_built(entry.key_origin, f"the Panel key {key}", "warning")
            elif key == "Anchor":
                anchors = _anchors(ctx, entry)
                written.add(key)
            elif key == "Attach_To":
                attach_to = ctx.name_ref(entry)
                written.add(key)
            elif key == "Input_Region":
                values[key] = _input_region(ctx, entry)  # type: ignore[assignment]
            elif key in blocks.PANEL_KEYS:
                try:
                    values[key] = coerce(
                        blocks.PANEL_KEYS[key],
                        entry.value,
                        ctx.origin(entry.key_origin),
                        blocks.PANEL_CHOICES.get(key, ()),
                    )
                except ValueProblem as exc:
                    ctx.problem(entry.value_origin, key, exc)
            else:
                ctx.unknown(entry.key_origin, key, allowed, "key in Panel")
        elif isinstance(entry, Block):
            if entry.type == "Style":
                style = _scalar_block_keys(ctx, entry, blocks.PANEL_STYLE, "Panel")
            elif entry.type == "Children":
                children = _children(ctx, entry, lambda b: _block(ctx, b))
            elif entry.type.startswith("On_"):
                handler = _handler(ctx, "Panel", entry.type, entry.origin, entry)
                if handler is not None:
                    handlers[entry.type] = handler
            elif entry.type == "Animation":
                written.add("Animation")
                animation = _animation(ctx, entry)
            elif entry.type == "Inset":
                written.add("Inset")
                try:
                    values["Inset"] = named_sides(entry, ctx.origin(entry.origin))
                except ValueProblem as exc:
                    ctx.problem(entry.origin, "Inset", exc)
            elif entry.type in blocks.PANEL_NOT_BUILT_ERROR:
                ctx.not_built(entry.origin, f"the Panel key {entry.type}")
            elif entry.type in blocks.PANEL_NOT_BUILT_WARNING:
                written.add(entry.type)
                ctx.not_built(entry.origin, f"the Panel key {entry.type}", "warning")
            else:
                ctx.unknown(entry.origin, entry.type, allowed, "block in Panel")
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    if name is None and not any(isinstance(e, Property) and e.key == "Name" for e in block.entries):
        ctx.add(block.origin, "missing-key", "a Panel needs a Name", "write Name: Launcher")
    melded = values.get("Meld")
    is_meld = isinstance(melded, m.Bool) and melded.value
    size_keys = ("Depth", "Length") if is_meld else ("Width", "Height")
    for key in size_keys:
        if key not in values and not any(
            isinstance(e, Property) and e.key == key for e in block.entries
        ):
            ctx.add(block.origin, "missing-key", f"a Panel needs {key}", f"write {key}: 300")
    for key in ("Width", "Height") if is_meld else ("Depth", "Length"):
        if key in written:
            hint = (
                "a melded Panel is sized by Depth (away from the Frame's edge) and Length "
                "(along it); write Depth and Length"
                if is_meld
                else "Depth and Length size a Panel with Meld: true; write Width and Height"
            )
            ctx.add(
                block.origin,
                "meld-size" if is_meld else "meld-size-orphan",
                f"{key} is not a size of this Panel"
                if is_meld
                else f"{key} only sizes a Panel with Meld: true",
                hint,
            )
    for key in size_keys:
        v = values.get(key)
        if isinstance(v, m.Auto | m.Expand):
            ctx.add(
                v.origin,
                "not-built",
                f"{type(v).__name__.upper()} as a Panel {key} is {_NOT_BUILT}",
                "",
            )
    if attach_to is not None:
        if "Attach" not in written:
            ctx.add(
                block.origin,
                "missing-key",
                "a Panel with Attach_To needs Attach",
                "write Attach: BOTTOM (the target's edge it meets: LEFT, RIGHT, TOP or BOTTOM)",
            )
        for key in blocks.PANEL_PLACED_KEYS:
            if key in written:
                ctx.add(
                    block.origin,
                    "attach-placed",
                    f"a Panel with Attach_To is placed by its target, so {key} has no meaning",
                    f"remove {key}, or remove Attach_To",
                )
    else:
        for key in blocks.PANEL_ATTACH_KEYS:
            if key in written:
                ctx.add(
                    block.origin,
                    "attach-orphan",
                    f"{key} is the placement against a target and needs Attach_To",
                    "write Attach_To: <a surface's Name>",
                )
    movable = values.get("Movable")
    if isinstance(movable, m.Bool) and movable.value and attach_to is not None:
        ctx.add(
            block.origin,
            "movable-attached",
            "a Panel placed by Attach_To cannot also be Movable",
            "only a Panel placed by Anchor and Inset (or floating) has a position to save",
        )
    layer = values.get("Layer")
    if is_meld:
        _check_meld(ctx, block, written, attach_to, handlers, style)
    if name is None or any(k not in values for k in size_keys):
        return None

    def word(key: str, default: str) -> str:
        v = values.get(key)
        return v.name if isinstance(v, m.Enum) else default

    inset = values.get("Inset")
    if isinstance(inset, m.Length):
        sides = (inset.px,) * 4
    elif isinstance(inset, m.Sides):
        sides = (inset.left, inset.top, inset.right, inset.bottom)
    else:
        sides = (0, 0, 0, 0)
    hide = values.get("Hide_After")
    visible = values.get("Visible")
    region = values.get("Input_Region")
    gap = values.get("Gap")
    return PanelDef(
        name=name,
        origin=ctx.origin(block.origin),
        layer=layer.name if isinstance(layer, m.Enum) else "TOP",
        anchor=anchors,
        inset=sides,
        width=values.get("Width"),  # type: ignore[arg-type]
        height=values.get("Height"),  # type: ignore[arg-type]
        depth=values.get("Depth"),  # type: ignore[arg-type]
        length=values.get("Length"),  # type: ignore[arg-type]
        keyboard=word("Keyboard", "NONE"),
        input=region.value if isinstance(region, m.Text) else "WHOLE",
        visible=visible.value if isinstance(visible, m.Bool) else True,
        hide_after=float(hide.value) if isinstance(hide, m.Number) else None,
        style=style,
        children=tuple(children),
        attach_to=attach_to,
        meld=is_meld,
        attach=word("Attach", "") or None,
        gap=float(gap.value) if isinstance(gap, m.Number) else 0,
        alignment=word("Alignment", "CENTER"),
        movable=movable.value if isinstance(movable, m.Bool) else False,
        animation=animation[0],
        duration=float(animation[1]),
        handlers=handlers,
    )


def _check_meld(
    ctx: _Ctx,
    block: Block,
    written: set[str],
    attach_to: str | None,
    handlers: Mapping[str, m.Handler],
    style: Mapping[str, m.Value],
) -> None:
    """A Panel with ``Meld: true`` is drawn inside the Frame it is attached to (Frame > Hosted
    Melding). A ``Margin`` stops the meld; what only a window of its own can do is not built."""
    if attach_to is None:
        ctx.add(
            block.origin,
            "meld-target",
            "Meld: true needs Attach_To naming a Frame",
            "write Attach_To: <the Name of a Frame of this Monitor>",
        )
    if "Margin" in written:
        ctx.add(
            block.origin,
            "meld-margin",
            "a Margin on the Frame-facing side stops the meld: the Panel would not grow out of "
            "the Frame",
            "remove the Margin to meld, or Meld to keep a separate Panel",
        )
    for key in blocks.PANEL_MELD_NOT_BUILT:
        if key in written:
            ctx.not_built(block.origin, f"{key} on a Panel with Meld: true")
    if handlers:
        ctx.not_built(block.origin, "events (On_*) on a Panel with Meld: true")
    if "Layer" in written:
        ctx.not_built(
            block.origin,
            "Layer on a Panel with Meld: true (it is in the Frame's surface)",
            "warning",
        )
    for key in blocks.PANEL_MELD_IGNORED_STYLE:
        if key in style:
            ctx.add(
                getattr(style[key], "origin", None) or block.origin,
                "not-built",
                f"{key} on a Panel with Meld: true is ignored: the Panel is drawn in the Frame's "
                "colour and border",
                "",
                "warning",
            )


def _animation(ctx: _Ctx, block: Block) -> tuple[str, float]:
    """``Animation { Type: SLIDE, Duration: 200 }``: the type defaults to SLIDE, the duration to
    200 ms (Panel > Configuration); ``NONE`` or a duration of 0 is no animation."""
    kind, duration = "SLIDE", 200.0
    for entry in block.entries:
        if isinstance(entry, Property) and entry.key == "Type":
            try:
                value = coerce(
                    "enum", entry.value, ctx.origin(entry.key_origin), blocks.PANEL_ANIMATION_TYPES
                )
            except ValueProblem as exc:
                ctx.problem(entry.value_origin, "Type", exc)
                continue
            if isinstance(value, m.Enum):
                kind = value.name
        elif isinstance(entry, Property) and entry.key == "Duration":
            try:
                value = coerce("number", entry.value, ctx.origin(entry.key_origin), ())
            except ValueProblem as exc:
                ctx.problem(entry.value_origin, "Duration", exc)
                continue
            if isinstance(value, m.Number):
                duration = float(value.value)
        else:
            key = entry.key if isinstance(entry, Property) else getattr(entry, "type", "?")
            ctx.unknown(
                getattr(entry, "key_origin", None) or getattr(entry, "origin", None),
                key,
                ["Type", "Duration"],
                "key in Animation",
            )
    return ("NONE", 0.0) if kind == "NONE" or duration <= 0 else (kind, duration)


def _tooltip_hosts(ctx: _Ctx, origin: tess_dl.Origin | None, kind: str | None) -> bool:
    """A Tooltip opens when the pointer enters its block, so the block must raise pointer events;
    a Text raises none (tre: it takes no listener)."""
    if kind is None or kind in blocks.BLOCK_EVENTS:
        return True
    ctx.add(
        origin,
        "event-not-raised",
        f"a {kind} raises no pointer events, so it cannot have a Tooltip",
        "put the Tooltip on the FlexBox or Box around it",
    )
    return False


def _tooltip_name(
    ctx: _Ctx, entry: Property, what: str, kind: str | None = None
) -> m.TooltipRef | None:
    """``Tooltip: Clock_Tooltip``: the ``Name`` of a Popup of the shell, which opens as this
    block's or use's tooltip. A file name (``Clock_Tooltip.tdl``) is not built."""
    if not _tooltip_hosts(ctx, entry.key_origin, kind):
        return None
    value = entry.value
    text = value.value if isinstance(value, tess_dl.String) else getattr(value, "text", None)
    if isinstance(text, str) and text.endswith(".tdl"):
        ctx.not_built(entry.value_origin, f"Tooltip: {text} (a Popup in a file)")
        return None
    if not isinstance(text, str) or not _NAME.match(text):
        ctx.add(
            entry.value_origin,
            "bad-name",
            "Tooltip is the Name of a Popup, or an inline Tooltip { } block",
            "write Tooltip: Clock_Tooltip",
        )
        return None
    if ctx.in_module:
        ctx.not_built(
            entry.value_origin,
            f"naming a Popup in {what} inside a module (a module does not know the shell's "
            "Popups; write the Tooltip { } block)",
        )
        return None
    return m.TooltipRef(name=text, origin=ctx.origin(entry.key_origin))


def _tooltip_block(ctx: _Ctx, block: Block, kind: str | None = None) -> m.TooltipRef | None:
    """``Tooltip { Children { ... } }``: an inline Popup that is a tooltip."""
    if not _tooltip_hosts(ctx, block.origin, kind):
        return None
    popup = _popup(ctx, block, inline=True)
    return None if popup is None else m.TooltipRef(popup=popup, origin=ctx.origin(block.origin))


def _adjust(ctx: _Ctx, entry: Property) -> tuple[str, ...] | None:
    """``Adjust: [FLIP_Y, SLIDE_X]`` or one word: what the compositor may do to keep the popup
    on screen; ``[]`` asks for nothing."""
    value = entry.value
    items = list(value.items) if isinstance(value, tess_dl.List) else [value]
    out: list[str] = []
    for item in items:
        word = item.text if isinstance(item, tess_dl.Word) else None
        if word not in blocks.POPUP_ADJUST:
            ctx.add(
                entry.value_origin,
                "bad-value",
                f"Adjust is {', '.join(blocks.POPUP_ADJUST)}, one or a list",
                "write Adjust: [FLIP_Y, SLIDE_X]",
            )
            return None
        if word.lower() in out:
            ctx.add(entry.value_origin, "bad-value", f"Adjust names {word} twice", "")
            return None
        out.append(word.lower())
    return tuple(out)


def _popup(ctx: _Ctx, block: Block, inline: bool = False) -> PopupDef | None:
    """A ``Popup { }`` of a Monitor, or the ``Tooltip { }`` block of a block or use (``inline``:
    it has no ``Name`` and is a tooltip by being one)."""
    what = "Tooltip" if inline else "Popup"
    allowed = [
        "Style",
        "Children",
        *(k for k in blocks.POPUP_KEYS if not (inline and k == "Tooltip")),
        *blocks.POPUP_NOT_BUILT,
        *(() if inline else ("Name",)),
    ]
    name: str | None = None
    values: dict[str, m.Value] = {}
    adjust: tuple[str, ...] | None = None
    written: set[str] = set()
    style: dict[str, m.Value] = {}
    children: list[Child] = []
    for entry in block.entries:
        if isinstance(entry, Property):
            key = entry.key
            written.add(key)
            if key == "Name" and not inline:
                name = ctx.name(entry)
            elif key == "Style":
                ctx.not_built(entry.key_origin, "a Style file")
            elif key in blocks.POPUP_NOT_BUILT:
                ctx.not_built(entry.key_origin, f"the {what} key {key}")
            elif key == "Adjust":
                adjust = _adjust(ctx, entry)
            elif key in blocks.POPUP_KEYS and not (inline and key == "Tooltip"):
                try:
                    values[key] = coerce(
                        blocks.POPUP_KEYS[key],
                        entry.value,
                        ctx.origin(entry.key_origin),
                        blocks.POPUP_CHOICES.get(key, ()),
                    )
                except ValueProblem as exc:
                    ctx.problem(entry.value_origin, key, exc)
            else:
                ctx.unknown(entry.key_origin, key, allowed, f"key in {what}")
        elif isinstance(entry, Block):
            if entry.type == "Style":
                style = _scalar_block_keys(ctx, entry, blocks.POPUP_STYLE, what)
            elif entry.type == "Children":
                before = ctx.in_popup
                ctx.in_popup = True
                try:
                    children = _children(ctx, entry, lambda b: _block(ctx, b))
                finally:
                    ctx.in_popup = before
            elif entry.type in blocks.POPUP_NOT_BUILT:
                ctx.not_built(entry.origin, f"the {what} key {entry.type}")
            else:
                ctx.unknown(entry.origin, entry.type, allowed, f"block in {what}")
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    if not inline and name is None and "Name" not in written:
        ctx.add(block.origin, "missing-key", "a Popup needs a Name", "write Name: Tray_Menu")
    for key in ("Width", "Height"):
        v = values.get(key)
        if isinstance(v, m.Percent | m.Expand):
            ctx.add(
                v.origin,
                "not-built",
                f"{type(v).__name__.upper()} as a {what} {key} is {_NOT_BUILT}",
                "write pixels or AUTO",
            )
    for key in ("Max_Width", "Max_Height"):
        v = values.get(key)
        if isinstance(v, m.Percent):
            ctx.add(v.origin, "not-built", f"a percentage as {key} is {_NOT_BUILT}", "write pixels")
    if (name is None and not inline) or any(
        isinstance(values.get(k), m.Percent | m.Expand) for k in ("Width", "Height")
    ):
        return None

    def flag(key: str, default: bool) -> bool:
        v = values.get(key)
        return v.value if isinstance(v, m.Bool) else default

    def num(key: str, default: float) -> float:
        v = values.get(key)
        return float(v.value) if isinstance(v, m.Number) else default

    def bound(key: str, default: float) -> float:
        v = values.get(key)
        return v.px if isinstance(v, m.Length) else default

    def word(key: str, default: str) -> str:
        v = values.get(key)
        return v.name if isinstance(v, m.Enum) else default

    tooltip = inline or flag("Tooltip", False)  # a tooltip: no focus, opens and closes on hover
    return PopupDef(
        name=name or "",
        origin=ctx.origin(block.origin),
        attach=word("Attach", "BOTTOM"),
        alignment=word("Alignment", "START"),
        gap=num("Gap", 0),
        adjust=("flip_y", "slide_x") if adjust is None else adjust,
        width=values.get("Width") or m.Auto(),
        height=values.get("Height") or m.Auto(),
        max_width=bound("Max_Width", 300),
        max_height=bound("Max_Height", 400),
        focus=flag("Focus", not tooltip),
        tooltip=tooltip,
        open_on_enter=flag("Open_On_Enter", tooltip),
        enter_delay=num("Enter_Delay", 500),
        close_on_exit=flag("Close_On_Exit", tooltip),
        exit_delay=num("Exit_Delay", 200),
        style=style,
        children=tuple(children),
    )


def _tooltip_refs(children: tuple[Child, ...]) -> list[tuple[m.TooltipRef, bool]]:
    """Every Tooltip written in ``children`` at any depth, with whether it names a Popup."""
    found: list[tuple[m.TooltipRef, bool]] = []
    for node in children:
        if isinstance(node, m.Node | m.UseNode) and node.tooltip is not None:
            found.append((node.tooltip, node.tooltip.name is not None))
        if isinstance(node, m.Node):
            found.extend(_tooltip_refs(node.children))
            if node.tooltip is not None and node.tooltip.popup is not None:
                found.extend(_tooltip_refs(node.tooltip.popup.children))
        elif isinstance(node, m.UseNode) and node.tooltip and node.tooltip.popup is not None:
            found.extend(_tooltip_refs(node.tooltip.popup.children))
        elif isinstance(node, m.IfNode):
            found.extend(_tooltip_refs(node.body))
            found.extend(_tooltip_refs(node.else_body or ()))
        elif isinstance(node, m.ForNode):
            found.extend(_tooltip_refs(node.body))
    return found


def _check_tooltips(ctx: _Ctx, monitors: list[MonitorDef]) -> None:
    """``Tooltip: Name`` names a Popup of the same Monitor that opens on enter (a Popup with
    ``Tooltip: true``, or ``Open_On_Enter: true``)."""
    for monitor in monitors:
        popups = {p.name: p for p in monitor.popups}
        trees: list[tuple[Child, ...]] = [s.children for s in monitor.surfaces]
        trees.extend(p.children for p in monitor.popups)
        for frame in monitor.frames:  # strips and melded Panels are content too
            trees.extend(e.children for e in frame.edges.values())
            trees.extend(p.children for p in frame.melds)
        for tree in trees:
            for ref, by_name in _tooltip_refs(tree):
                if not by_name:
                    continue
                target = popups.get(ref.name or "")
                if target is None:
                    ctx.add(
                        ref.origin,
                        "tooltip-unknown",
                        f"Tooltip names {ref.name}, which is no Popup of Monitor {monitor.name}",
                        "the Popups here are: " + (", ".join(sorted(popups)) or "none"),
                    )
                elif not target.open_on_enter:
                    ctx.add(
                        ref.origin,
                        "tooltip-not-hover",
                        f"Popup {target.name} is used as a Tooltip but does not open on enter",
                        f"write Tooltip: true (or Open_On_Enter: true) in {target.name}",
                    )


def _frame_sides(ctx: _Ctx, key: str, value: m.Value, origin: tess_dl.Origin | None) -> m.Value:
    """Sides of a Frame (``Thickness``, ``Margin``): none below 0."""
    sides = _sides_of(value)
    if any(x < 0 for x in sides):
        ctx.add(origin, "bad-value", f"{key} is 0 or more", "")
    return value


def _sides_of(value: m.Value | None) -> tuple[float, float, float, float]:
    if isinstance(value, m.Length):
        return (float(value.px),) * 4
    if isinstance(value, m.Sides):
        return (value.left, value.top, value.right, value.bottom)
    return (0, 0, 0, 0)


def _corners_of(value: m.Value | None) -> tuple[float, float, float, float]:
    if isinstance(value, m.Length):
        return (float(value.px),) * 4
    if isinstance(value, m.Seq):
        a, b, c, d = (float(x.px) for x in value.items if isinstance(x, m.Length))
        return (a, b, c, d)
    return (0, 0, 0, 0)


def _frame_border(ctx: _Ctx, block: Block) -> FrameBorder | None:
    """``Inner_Border { Width: 2, Color: "#ffffff22" }``; a colour may be a token."""
    width: float | None = None
    color: m.Value | None = None
    for entry in block.entries:
        if isinstance(entry, Property):
            if entry.key == "Width":
                try:
                    value = coerce("number", entry.value, ctx.origin(entry.key_origin))
                except ValueProblem as exc:
                    ctx.problem(entry.value_origin, entry.key, exc)
                    continue
                assert isinstance(value, m.Number)
                if value.value < 0:
                    ctx.add(entry.value_origin, "bad-value", "Width is 0 or more", "")
                else:
                    width = float(value.value)
            elif entry.key == "Color":
                typed = _typed(ctx, "Frame", entry, "color")
                if isinstance(typed, m.SlotValue):
                    ctx.add(entry.value_origin, "bad-value", "a Frame has no slots", "")
                else:
                    color = typed
            else:
                ctx.unknown(
                    entry.key_origin, entry.key, list(blocks.FRAME_BORDER_KEYS), "border key"
                )
        elif isinstance(entry, Block):
            ctx.unknown(entry.origin, entry.type, list(blocks.FRAME_BORDER_KEYS), "border key")
    if width is None:
        ctx.add(block.origin, "missing-key", f"{block.type} needs a Width", "write Width: 2")
        return None
    if color is None:
        ctx.add(
            block.origin, "missing-key", f"{block.type} needs a Color", 'write Color: "#ffffff22"'
        )
        return None
    return FrameBorder(width, color)


def _frame(ctx: _Ctx, block: Block) -> FrameDef | None:
    allowed = [
        "Name",
        "Style",
        "Inner_Border",
        "Outer_Border",
        "Edges",
        *blocks.FRAME_KEYS,
        *blocks.FRAME_NOT_BUILT_ERROR,
        *blocks.FRAME_NOT_BUILT_WARNING,
    ]
    name: str | None = None
    values: dict[str, m.Value] = {}
    style: dict[str, m.Value] = {}
    borders: dict[str, FrameBorder] = {}
    edges: dict[str, EdgeDef] = {}
    for entry in block.entries:
        if isinstance(entry, Property):
            key = entry.key
            if key == "Name":
                name = ctx.name(entry)
            elif key == "Style":
                ctx.not_built(entry.key_origin, "a Style file")
            elif key == "Edges":
                ctx.add(
                    entry.value_origin, "bad-value", "Edges is a block", "write Edges { Top { } }"
                )
            elif key in blocks.FRAME_NOT_BUILT_ERROR:
                ctx.not_built(entry.key_origin, f"the Frame key {key}")
            elif key in blocks.FRAME_NOT_BUILT_WARNING:
                ctx.not_built(entry.key_origin, f"the Frame key {key}", "warning")
            elif key in blocks.FRAME_KEYS:
                try:
                    value = coerce(
                        blocks.FRAME_KEYS[key],
                        entry.value,
                        ctx.origin(entry.key_origin),
                        blocks.FRAME_CHOICES.get(key, ()),
                    )
                except ValueProblem as exc:
                    ctx.problem(entry.value_origin, key, exc)
                    continue
                if key in ("Thickness", "Margin", "Padding"):
                    _frame_sides(ctx, key, value, entry.value_origin)
                elif key in ("Corner_Radius", "Inner_Radius") and any(
                    x < 0 for x in _corners_of(value)
                ):
                    ctx.add(entry.value_origin, "bad-value", f"{key} is 0 or more", "")
                values[key] = value
            elif key in ("Inner_Border", "Outer_Border"):
                ctx.add(
                    entry.value_origin,
                    "bad-value",
                    f"{key} is a block with Width and Color",
                    f'write {key} {{ Width: 1, Color: "#ffffff22" }}',
                )
            else:
                ctx.unknown(entry.key_origin, key, allowed, "key in Frame")
        elif isinstance(entry, Block):
            kind = entry.type
            if kind == "Style":
                style = _scalar_block_keys(ctx, entry, blocks.FRAME_STYLE, "Frame")
            elif kind == "Edges":
                edges = _edges(ctx, entry)
            elif kind in ("Thickness", "Margin", "Padding"):
                try:
                    named = named_sides(entry, ctx.origin(entry.origin))
                except ValueProblem as exc:
                    ctx.problem(entry.origin, kind, exc)
                    continue
                values[kind] = _frame_sides(ctx, kind, named, entry.origin)
            elif kind in ("Inner_Border", "Outer_Border"):
                border = _frame_border(ctx, entry)
                if border is not None:
                    borders[kind] = border
            elif kind in blocks.FRAME_NOT_BUILT_ERROR:
                ctx.not_built(entry.origin, f"the Frame key {kind}")
            elif kind in blocks.FRAME_NOT_BUILT_WARNING:
                ctx.not_built(entry.origin, f"the Frame key {kind}", "warning")
            else:
                ctx.unknown(entry.origin, kind, allowed, "block in Frame")
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    saw = {e.key for e in block.entries if isinstance(e, Property)} | {
        e.type for e in block.entries if isinstance(e, Block)
    }
    if name is None and "Name" not in saw:
        ctx.add(block.origin, "missing-key", "a Frame needs a Name", "write Name: Screen_Frame")
    if "Thickness" not in saw:
        ctx.add(block.origin, "missing-key", "a Frame needs a Thickness", "write Thickness: 8")
    for key in blocks.FRAME_STYLE_NOT_BUILT:
        if key in style:
            ctx.not_built(getattr(style[key], "origin", None), f"{key} on a Frame")
    for key, value in style.items():
        if key not in blocks.FRAME_STYLE_NOT_BUILT and isinstance(value, m.SlotValue):
            ctx.add(value.origin, "bad-value", "a Frame has no slots", "")
    short = [k for k in ("Border_Width", "Border_Color") if k in style]
    if short and "Inner_Border" in borders:
        ctx.add(
            block.origin,
            "frame-border-twice",
            f"the Frame has an Inner_Border and {short[0]} in its Style, which is shorthand for it",
            "write the inner border once",
        )
    if "Border_Width" in style:
        width = style["Border_Width"]
        if isinstance(width, m.Number) and width.value >= 0:
            color = style.get("Border_Color")
            if color is None:
                ctx.add(
                    block.origin,
                    "missing-key",
                    "Border_Width in a Frame's Style needs a Border_Color",
                    'write Border_Color: "#ffffff22"',
                )
            else:
                borders.setdefault("Inner_Border", FrameBorder(float(width.value), color))
        elif not isinstance(width, m.Number):
            ctx.add(getattr(width, "origin", None), "bad-value", "Border_Width is a number", "")
        else:
            ctx.add(width.origin, "bad-value", "Border_Width is 0 or more", "")
    elif "Border_Color" in style:
        ctx.add(
            block.origin,
            "missing-key",
            "Border_Color in a Frame's Style needs a Border_Width",
            "write Border_Width: 1",
        )
    background = style.get("Background")
    if background is not None and not isinstance(background, m.Color | m.TokenRef):
        ctx.add(
            getattr(background, "origin", None),
            "bad-value",
            "the Frame's Background is a colour or a token",
            "a gradient is not built",
        )
    if name is None or "Thickness" not in values:
        return None
    thickness = _sides_of(values["Thickness"])
    for side, edge in edges.items():
        index = ("left", "top", "right", "bottom").index(side)
        total = edge.thickness if edge.thickness is not None else thickness[index]
        if edge.children and total <= 0:
            ctx.add(
                edge.origin,
                "frame-strip-thickness",
                f"the {side} strip has Children but no thickness",
                "write Thickness in the strip, or a Thickness for that side of the Frame",
            )
    if "Padding" in values and not any(e.children for e in edges.values()):
        ctx.add(
            block.origin,
            "not-built",
            "Padding has no effect: no side of the Frame is a strip",
            "",
            "warning",
        )
    visible = values.get("Visible")
    return FrameDef(
        name=name,
        origin=ctx.origin(block.origin),
        thickness=_sides_of(values["Thickness"]),
        margin=_sides_of(values.get("Margin")),
        outer_radius=_corners_of(values.get("Corner_Radius")),
        inner_radius=_corners_of(values.get("Inner_Radius")),
        inner_border=borders.get("Inner_Border"),
        outer_border=borders.get("Outer_Border"),
        visible=visible.value if isinstance(visible, m.Bool) else True,
        style=style,
        padding=_sides_of(values.get("Padding")),
        edges=edges,
    )


def _edges(ctx: _Ctx, block: Block) -> dict[str, EdgeDef]:
    """``Edges { Top { Thickness: 32, Padding: 4, Children { ... } } }``: a side with its own
    thickness, and a strip when it has ``Children``."""
    out: dict[str, EdgeDef] = {}
    for entry in block.entries:
        if not isinstance(entry, Block) or entry.type not in blocks.EDGE_SIDES:
            origin = getattr(entry, "origin", None) or getattr(entry, "key_origin", None)
            ctx.unknown(
                origin,
                getattr(entry, "type", getattr(entry, "key", "?")),
                list(blocks.EDGE_SIDES),
                "side in Edges",
            )
            continue
        side = entry.type.lower()
        if side in out:
            ctx.add(entry.origin, "frame-edge-duplicate", f"Edges names {entry.type} twice", "")
            continue
        thickness: float | None = None
        padding: tuple[float, float, float, float] | None = None
        children: list[Child] = []
        for sub in entry.entries:
            if isinstance(sub, Property):
                if sub.key == "Thickness":
                    try:
                        value = coerce("number", sub.value, ctx.origin(sub.key_origin))
                    except ValueProblem as exc:
                        ctx.problem(sub.value_origin, sub.key, exc)
                        continue
                    assert isinstance(value, m.Number)
                    if value.value < 0:
                        ctx.add(sub.value_origin, "bad-value", "Thickness is 0 or more", "")
                    else:
                        thickness = float(value.value)
                elif sub.key == "Padding":
                    try:
                        value = coerce("sides", sub.value, ctx.origin(sub.key_origin))
                    except ValueProblem as exc:
                        ctx.problem(sub.value_origin, sub.key, exc)
                        continue
                    _frame_sides(ctx, "Padding", value, sub.value_origin)
                    padding = _sides_of(value)
                else:
                    ctx.unknown(
                        sub.key_origin,
                        sub.key,
                        ["Thickness", "Padding", "Children"],
                        f"key in {entry.type}",
                    )
            elif isinstance(sub, Block):
                if sub.type == "Children":
                    children = _children(ctx, sub, lambda b: _block(ctx, b))
                elif sub.type == "Padding":
                    try:
                        named = named_sides(sub, ctx.origin(sub.origin))
                    except ValueProblem as exc:
                        ctx.problem(sub.origin, "Padding", exc)
                        continue
                    padding = _sides_of(_frame_sides(ctx, "Padding", named, sub.origin))
                else:
                    ctx.unknown(
                        sub.origin,
                        sub.type,
                        ["Thickness", "Padding", "Children"],
                        f"key in {entry.type}",
                    )
            elif isinstance(sub, tess_dl.If | tess_dl.For):
                ctx.not_built(sub.origin, "If and For")
        out[side] = EdgeDef(side, ctx.origin(entry.origin), thickness, padding, tuple(children))
    return out


def _anchors(ctx: _Ctx, entry: Property) -> tuple[str, ...]:
    """``Anchor: TOP`` or ``Anchor: [TOP, LEFT]``."""
    value = entry.value
    items = list(value.items) if isinstance(value, tess_dl.List) else [value]
    out: list[str] = []
    for item in items:
        word = item.text if isinstance(item, tess_dl.Word) else None
        if word not in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
            ctx.add(
                entry.value_origin,
                "bad-value",
                "Anchor is TOP, BOTTOM, LEFT or RIGHT, one or a list",
                "write Anchor: [TOP, LEFT]",
            )
            return ()
        if word in out:
            ctx.add(entry.value_origin, "bad-value", f"Anchor names {word} twice", "")
            return ()
        out.append(word)
    return tuple(out)


def _input_region(ctx: _Ctx, entry: Property) -> m.Text | None:
    """``Input_Region: []`` is nothing (clicks pass through), ``AUTO`` the drawn shapes; leaving
    the key out is the whole surface. Rectangles are not built yet."""
    value = entry.value
    if isinstance(value, tess_dl.List) and not value.items:
        return m.Text("NONE", origin=ctx.origin(entry.key_origin))
    if isinstance(value, tess_dl.Word) and value.text == "AUTO":
        return m.Text("AUTO", origin=ctx.origin(entry.key_origin))
    if isinstance(value, tess_dl.List):
        ctx.not_built(entry.value_origin, "Input_Region rectangles")
    else:
        ctx.add(entry.value_origin, "bad-value", "Input_Region is [] or AUTO", "")
    return None


def _monitor(ctx: _Ctx, block: Block) -> MonitorDef | None:
    allowed = ["Name", "Index", "Connector", "Description", "Children"]
    name: str | None = None
    index: int | str | None = None
    connector: str | None = None
    description: str | None = None
    surfaces: list[BarDef | PanelDef] = []
    popups: list[PopupDef] = []
    frames: list[FrameDef] = []
    saw_name = False
    for entry in block.entries:
        if isinstance(entry, Property):
            key = entry.key
            if key == "Name":
                saw_name = True
                name = ctx.name(entry)
            elif key == "Index":
                v = entry.value
                if isinstance(v, tess_dl.Number) and isinstance(v.value, int) and v.value >= 0:
                    index = v.value
                elif isinstance(v, tess_dl.Word) and v.text == "default":
                    index = "default"
                else:
                    ctx.add(
                        entry.value_origin,
                        "bad-value",
                        "Index: a position (0, 1, ...) or default",
                        "",
                    )
            elif key in ("Connector", "Description"):
                v = entry.value
                text = v.value if isinstance(v, tess_dl.String) else getattr(v, "text", None)
                if text is None:
                    ctx.add(entry.value_origin, "bad-value", f"{key} is text", "")
                elif key == "Connector":
                    connector = text
                else:
                    description = text
            else:
                ctx.unknown(entry.key_origin, key, allowed, "key in Monitor")
        elif isinstance(entry, Block):
            if entry.type == "Children":
                for child in entry.entries:
                    if isinstance(child, Block):
                        if child.type == "Bar":
                            bar = _bar(ctx, child)
                            if bar is not None:
                                surfaces.append(bar)
                        elif child.type == "Panel":
                            panel = _panel(ctx, child)
                            if panel is not None:
                                surfaces.append(panel)
                        elif child.type == "Popup":
                            popup = _popup(ctx, child)
                            if popup is not None:
                                popups.append(popup)
                        elif child.type == "Frame":
                            frame = _frame(ctx, child)
                            if frame is not None and frames:
                                ctx.add(
                                    child.origin,
                                    "frame-duplicate",
                                    f"Monitor has a second Frame ({frame.name}); the first is "
                                    f"{frames[0].name}",
                                    "a Monitor has one Frame",
                                )
                            elif frame is not None:
                                frames.append(frame)
                        else:
                            ctx.unknown(child.origin, child.type, list(_SURFACES), "surface")
                    elif isinstance(child, Property) and child.key == "Import":
                        ctx.not_built(child.key_origin, "Import")
                    elif isinstance(child, Property):
                        ctx.unknown(child.key_origin, child.key, list(_SURFACES), "surface")
                    elif isinstance(child, tess_dl.If | tess_dl.For):
                        ctx.not_built(child.origin, "If and For")
            else:
                ctx.unknown(entry.origin, entry.type, allowed, "block in Monitor")
    if not saw_name:
        ctx.add(block.origin, "missing-key", "a Monitor needs a Name", "write Name: Main")
    if name is None:
        return None
    surfaces, frames = _host_melds(ctx, surfaces, frames)
    here = ctx.origin(block.origin)
    for kind, value in (
        ("Index", None if index is None else str(index)),
        ("Connector", connector),
        ("Description", description),
    ):
        if value is None:
            continue
        previous = ctx.selectors.get((kind, value))
        if previous is not None:
            ctx.add(
                block.origin,
                "monitor-duplicate",
                f"two Monitors select the same monitor ({kind}: {value}), "
                f"the first is at {previous}",
                "a monitor is named by one Monitor block",
            )
        else:
            ctx.selectors[(kind, value)] = here
    return MonitorDef(
        name=name,
        origin=here,
        index=index,
        connector=connector,
        description=description,
        surfaces=tuple(surfaces),
        popups=tuple(popups),
        frames=tuple(frames),
    )


def _host_melds(
    ctx: _Ctx, surfaces: list[BarDef | PanelDef], frames: list[FrameDef]
) -> tuple[list[BarDef | PanelDef], list[FrameDef]]:
    """A Panel with ``Meld: true`` is drawn inside its Frame's surface, so it moves from the
    Monitor's surfaces to the ``melds`` of the Frame it names."""
    kept: list[BarDef | PanelDef] = []
    hosted: dict[str, list[PanelDef]] = {}
    for surface in surfaces:
        if not (isinstance(surface, PanelDef) and surface.meld):
            kept.append(surface)
            continue
        if any(f.name == surface.attach_to for f in frames):
            hosted.setdefault(surface.attach_to or "", []).append(surface)
        else:
            ctx.add(
                surface.origin,
                "meld-target",
                f"Panel {surface.name} has Meld: true but Attach_To {surface.attach_to} is no "
                "Frame of this Monitor",
                "a Panel melds into a Frame of its own Monitor",
            )
    return kept, [
        dataclasses.replace(f, melds=tuple(hosted[f.name])) if f.name in hosted else f
        for f in frames
    ]


def read_shell(
    document: Document,
    file: str,
    read_text: Callable[[str], str],
    modules: Mapping[str, ModuleDef] | None = None,
    import_module: Callable[[str], str | None] | None = None,
    icons: IconSource | None = None,
) -> tuple[ShellDef | None, list[Finding]]:
    """Type a parsed shell file. ``read_text`` reads a file named in the shell file (an SVG's
    ``Source``) and raises ``OSError``; the schema does no I/O of its own. ``modules`` are the
    known module files by call name: a block with such a head is a module call."""
    ctx = _Ctx(file, read_text, modules, import_module, None, icons)
    root = document.root
    if root.type != "Shell":
        ctx.add(
            root.origin,
            "shell-root",
            f"the root block is {root.type}, not Shell",
            "write Shell { }",
        )
        return None, ctx.findings
    monitors: list[MonitorDef] = []
    for entry in root.entries:
        if isinstance(entry, Block):
            if entry.type == "Monitor":
                monitor = _monitor(ctx, entry)
                if monitor is not None:
                    monitors.append(monitor)
            else:
                ctx.unknown(entry.origin, entry.type, ["Monitor"], "block in Shell")
        elif isinstance(entry, Property):
            ctx.unknown(entry.key_origin, entry.key, ["Monitor"], "key in Shell")
    _check_attach(ctx, monitors)
    _check_tooltips(ctx, monitors)
    name = document.metadata.get("Name")
    shell_name = getattr(name, "text", None) or getattr(name, "value", "") or ""
    if any(f.severity == "error" for f in ctx.findings):
        return None, ctx.findings
    return ShellDef(file, shell_name, tuple(monitors)), ctx.findings


def _check_attach(ctx: _Ctx, monitors: list[MonitorDef]) -> None:
    """``Attach_To`` names a Bar, a Panel or a module used in a Bar, of the same Monitor; a Panel
    has one target, a target has one attached Panel, and a chain of attached Panels ends at a
    surface that is placed."""
    home: dict[str, tuple[MonitorDef, BarDef | PanelDef]] = {}
    places: dict[str, MonitorDef] = {}  # every name a Panel may attach to, and its Monitor
    for monitor in monitors:
        for surface in monitor.surfaces:
            home[surface.name] = (monitor, surface)
            places[surface.name] = monitor
            if isinstance(surface, BarDef):
                for use in use_names(surface.children):
                    places[use] = monitor
    taken: dict[str, PanelDef] = {}
    frames = {f.name for monitor in monitors for f in monitor.frames}
    for monitor in monitors:
        for panel in monitor.surfaces:
            if not isinstance(panel, PanelDef) or not panel.attach_to:
                continue
            target = panel.attach_to
            if target in frames:
                ctx.add(
                    panel.origin,
                    "not-built",
                    f"Attach_To the Frame {target} (melding a Panel into a Frame) is {_NOT_BUILT}",
                    "attach the Panel to a Bar, or place it with Anchor and Inset",
                )
            elif target == panel.name:
                ctx.add(
                    panel.origin, "attach-self", f"Panel {panel.name} is attached to itself", ""
                )
            elif target not in places:
                ctx.add(
                    panel.origin,
                    "attach-unknown",
                    f"Attach_To names {target}, which is no Bar, Panel or module used in a Bar",
                    "the names here are: " + ", ".join(sorted(places)),
                )
            elif places[target] is not monitor:
                ctx.add(
                    panel.origin,
                    "attach-other-monitor",
                    f"{target} is on Monitor {places[target].name}, Panel {panel.name} on "
                    f"{monitor.name}",
                    "a Panel attaches to a surface of its own Monitor",
                )
            elif target in taken:
                ctx.add(
                    panel.origin,
                    "attach-duplicate",
                    f"{target} already has Panel {taken[target].name} attached "
                    f"({taken[target].origin})",
                    "a target has one attached Panel",
                )
            else:
                taken[target] = panel
    for monitor in monitors:
        for panel in monitor.surfaces:
            seen = {panel.name}
            at = panel
            while isinstance(at, PanelDef) and at.attach_to in home and at.attach_to not in seen:
                seen.add(at.attach_to)
                at = home[at.attach_to][1]
            if isinstance(at, PanelDef) and at.attach_to in seen and at.attach_to in home:
                ctx.add(
                    panel.origin,
                    "attach-cycle",
                    f"Panel {panel.name} is attached in a circle: {' > '.join(sorted(seen))}",
                    "a chain of attached Panels must end at a Bar or an anchored Panel",
                )
                break


def _param_decls(ctx: _Ctx, block: Block) -> dict[str, ParamDecl]:
    out: dict[str, ParamDecl] = {}
    for entry in block.entries:
        if not isinstance(entry, Block):
            if isinstance(entry, Property):
                ctx.add(
                    entry.key_origin,
                    "bad-key",
                    f"Params holds one block per param, not the key {entry.key}",
                    "write text { Type: string }",
                )
            continue
        if entry.type in out:
            ctx.add(entry.origin, "name-duplicate", f"the param {entry.type} is declared twice")
            continue
        type_word: str | None = None
        default: m.Value | None = None
        default_prop: Property | None = None
        for sub in entry.entries:
            if isinstance(sub, Property) and sub.key == "Type":
                type_word = sub.value.text if isinstance(sub.value, tess_dl.Word) else None
                if type_word not in PARAM_TYPES:
                    ctx.add(
                        sub.value_origin,
                        "bad-value",
                        f"a param type is one of {', '.join(PARAM_TYPES)}",
                        f"{', '.join(nearest(str(type_word), PARAM_TYPES))}?" if type_word else "",
                    )
                    type_word = None
            elif isinstance(sub, Property) and sub.key == "Default":
                default_prop = sub
            elif isinstance(sub, Property):
                ctx.unknown(sub.key_origin, sub.key, ["Type", "Default"], "key of a param")
        if type_word is None:
            if not any(isinstance(s, Property) and s.key == "Type" for s in entry.entries):
                ctx.add(
                    entry.origin,
                    "missing-key",
                    f"the param {entry.type} needs a Type",
                    "write Type: string",
                )
            continue
        if default_prop is not None:
            try:
                default = coerce(
                    _PARAM_KINDS[type_word], default_prop.value, ctx.origin(default_prop.key_origin)
                )
            except ValueProblem as exc:
                ctx.problem(default_prop.value_origin, "Default", exc)
        out[entry.type] = ParamDecl(entry.type, type_word, default, ctx.origin(entry.origin))
    return out


def read_module(
    document: Document,
    file: str,
    modules: Mapping[str, ModuleDef] | None = None,
    import_module: Callable[[str], str | None] | None = None,
    load_style: Callable[[str], StyleDef | None] | None = None,
    icons: IconSource | None = None,
) -> tuple[ModuleDef | None, list[Finding]]:
    """Type a parsed ``<Name>_Module.tdl``: ``Module { Params { } Children { } }``, or a single
    layout block written directly in the root (Module File > Structure)."""
    ctx = _Ctx(file, lambda _: "", modules, import_module, load_style, icons)
    ctx.in_module = True
    root = document.root
    if root.type != "Module":
        ctx.add(
            root.origin,
            "module-root",
            f"the root block is {root.type}, not Module",
            "write Module { }",
        )
        return None, ctx.findings
    name_entry = document.metadata.get("Name")
    name = getattr(name_entry, "text", None) or getattr(name_entry, "value", None)
    if not isinstance(name, str) or not _NAME.match(name):
        ctx.add(root.origin, "bad-name", "a module's Name must be letters, digits and _", "")
        return None, ctx.findings
    params: dict[str, ParamDecl] = {}
    children: list[Child] = []
    style: StyleDef | None = None
    style_seen = False
    style_file = ""
    for entry in root.entries:
        if isinstance(entry, Block):
            if entry.type == "Params":
                params = _param_decls(ctx, entry)
            elif entry.type == "Children":
                children.extend(_children(ctx, entry, lambda b: _block(ctx, b)))
            elif entry.type == "Style":
                if style_seen:
                    ctx.add(entry.origin, "style-duplicate", "a module has one Style", "")
                style_seen = True
                style = _style_def(ctx, entry)
            else:
                node = _block(ctx, entry)
                if node is not None:
                    children.append(node)
        elif isinstance(entry, Property):
            if entry.key == "Style":
                text = getattr(entry.value, "text", None) or getattr(entry.value, "value", None)
                if style_seen:
                    ctx.add(entry.key_origin, "style-duplicate", "a module has one Style", "")
                style_seen = True
                if not isinstance(text, str):
                    ctx.add(entry.value_origin, "bad-value", "Style names a file", "")
                elif ctx.load_style is None:
                    ctx.not_built(entry.key_origin, "a Style file here")
                else:
                    style_file = text
                    style = ctx.load_style(text)
                    if style is None:
                        ctx.add(
                            entry.value_origin,
                            "style-not-found",
                            f"the style file {text} could not be read",
                            "a path is relative to the module file; the findings above say why",
                        )
            elif entry.key == "Import":
                ctx.not_built(entry.key_origin, "Import")
            else:
                ctx.unknown(
                    entry.key_origin, entry.key, ["Params", "Children", "Style"], "key in Module"
                )
        elif isinstance(entry, tess_dl.If | tess_dl.For):
            ctx.not_built(entry.origin, "If and For")
    if len(children) != 1 and not any(f.severity == "error" for f in ctx.findings):
        ctx.add(
            root.origin,
            "missing-key",
            "a module has one layout root",
            "write one block in Module { }",
        )
    styled = apply_style(
        tuple(children),
        style,
        lambda origin, rule, message, hint: ctx.add(origin, rule, message, hint),
    )
    if any(f.severity == "error" for f in ctx.findings):
        return None, ctx.findings
    definition = ModuleDef(name, file, ctx.origin(root.origin), params, styled, style_file)
    return definition, ctx.findings


def read_module_params(document: Document, file: str) -> ModuleDef | None:
    """A module's call name and params only, with no layout: the first of two passes, so a layout
    can call any module whatever the order of the files (the findings are the second pass's)."""
    ctx = _Ctx(file, lambda _: "")
    root = document.root
    name_entry = document.metadata.get("Name")
    name = getattr(name_entry, "text", None) or getattr(name_entry, "value", None)
    if root.type != "Module" or not isinstance(name, str) or not _NAME.match(name):
        return None
    params: dict[str, ParamDecl] = {}
    for entry in root.entries:
        if isinstance(entry, Block) and entry.type == "Params":
            params = _param_decls(ctx, entry)
    return ModuleDef(name, file, ctx.origin(root.origin), params, ())
