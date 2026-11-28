"""The preview model: what the shell would show for a configuration, as plain data.

``preview(config, overrides, outputs)`` reads the configuration with the shell's own pipeline
(``scan``, the look, the placement of every Bar and Panel) and returns a :class:`PreviewModel`: the
outputs, the Monitor blocks and the outputs they land on, every surface with its anchor, size,
margin, exclusive zone and layer, the area left for windows (the desktop) of each output, the
theme's tokens, the module slots of each surface as placeholders (no live data) and the findings
``check`` would print. A tool that draws a mockup (the configuration app) uses it and holds none of
these rules itself.

Nothing here opens a window, touches the compositor or imports a toolkit. ``overrides`` maps a
file's path to the text an editor holds for it: the preview reads that text instead of the disk's,
for a file that does not exist yet as well. A configuration with errors still gives what resolves:
the findings say what did not, and a surface that gets no geometry has a ``status`` that says why.

The shape of ``to_dict()`` is documented by ``describe()`` (also the ``preview`` entry of the
schema export) and versioned by ``PREVIEW_VERSION`` (``schema/preview_shape.py``): a key is added
without a bump, a key is changed or removed with one."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.config import overlay
from tess_shell.config.settings import load_settings
from tess_shell.model.look import apply_rules
from tess_shell.scanner import Scan, build_look, scan
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import (
    BarDef,
    FrameDef,
    ModuleDef,
    MonitorDef,
    PanelDef,
    PopupDef,
    ShellDef,
)
from tess_shell.schema.preview_shape import PREVIEW_VERSION, describe
from tess_shell.surfaces.bar import Geometry, body_rect
from tess_shell.surfaces.manager import _place, assign

Json = dict[str, Any]
_OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}
_MARGIN_AT = {"top": 0, "right": 1, "bottom": 2, "left": 3}


@dataclass(frozen=True, slots=True)
class VirtualOutput:
    """An output to preview on: a name a ``Monitor`` can select (``Connector``), its size in
    logical pixels and its scale."""

    name: str = "Preview-1"
    width: int = 1920
    height: int = 1080
    scale: float = 1.0
    description: str = ""


@dataclass(frozen=True, slots=True)
class PreviewModel:
    """The result; ``to_dict()`` is the plain-data form a drawing tool reads."""

    findings: tuple[Finding, ...] = ()
    outputs: tuple[VirtualOutput, ...] = ()
    appearance: Json = field(default_factory=dict)
    tokens: Json = field(default_factory=dict)
    shell: Json | None = None
    monitors: tuple[Json, ...] = ()
    surfaces: tuple[Json, ...] = ()
    popups: tuple[Json, ...] = ()
    desktop: tuple[Json, ...] = ()

    def to_dict(self) -> Json:
        return {
            "preview_version": PREVIEW_VERSION,
            "findings": [_finding(f) for f in self.findings],
            "outputs": [
                {
                    "name": o.name,
                    "width": o.width,
                    "height": o.height,
                    "scale": o.scale,
                    "description": o.description,
                }
                for o in self.outputs
            ],
            "appearance": self.appearance,
            "tokens": self.tokens,
            "shell": self.shell,
            "monitors": list(self.monitors),
            "surfaces": list(self.surfaces),
            "popups": list(self.popups),
            "desktop": list(self.desktop),
        }


def preview(
    config: Path,
    overrides: Mapping[Path, str] | None = None,
    outputs: Sequence[VirtualOutput] = (VirtualOutput(),),
    appearance: Appearance | None = None,
) -> PreviewModel:
    """What ``config`` (a configuration folder) would show on ``outputs``, with ``overrides``
    (path -> text) read instead of the files. Never raises for a configuration error: an
    unreadable ``settings.tdl`` gives the findings and nothing else."""
    config = Path(config)
    with overlay.overlaid(overrides or {}):
        settings, found = load_settings(config)
        if settings is None:
            return PreviewModel(findings=tuple(found), outputs=tuple(outputs))
        result = scan(settings, config)
        findings = [*found, *result.findings]
        try:
            look = build_look(result, settings, appearance or Appearance())
        except KeyError:  # the theme or a stylesheet is missing: the scan has said so
            look = None
    main = result.shells.get(settings.main_shell_path) if settings.main_shell_path else None
    tokens = _tokens(look)
    state: Json = {
        "scheme": look.appearance.scheme if look else "default",
        "density": look.appearance.density if look else settings.appearance.density.lower(),
        "theme": settings.appearance.theme,
        "stylesheets": list(settings.appearance.stylesheets),
    }
    if main is None:
        return PreviewModel(
            tuple(findings), tuple(outputs), state, tokens, None, (), (), (), _desktop(outputs, [])
        )
    ctx = _Ctx(result, look)
    monitors, surfaces, popups, reserved = _monitors(main, outputs, ctx)
    return PreviewModel(
        tuple(findings),
        tuple(outputs),
        state,
        tokens,
        {"name": main.name, "file": main.file},
        tuple(monitors),
        tuple(surfaces),
        tuple(popups),
        _desktop(outputs, reserved),
    )


# -- the walk ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Ctx:
    scan: Scan
    look: Any

    def rules(self, children: Sequence[Any]) -> Sequence[Any]:
        """The blocks with the stylesheets' rules folded into their style, as the shell plans
        them."""
        if self.look is None or not self.look.rules:
            return children
        return apply_rules(tuple(children), self.look.rules)

    def module(self, name: str) -> ModuleDef | None:
        found = self.scan.modules.get(name)
        return found.definition if found else None


def _monitors(
    shell: ShellDef, outputs: Sequence[VirtualOutput], ctx: _Ctx
) -> tuple[list[Json], list[Json], list[Json], list[tuple[str, str, float]]]:
    monitors: list[Json] = []
    surfaces: list[Json] = []
    popups: list[Json] = []
    reserved: list[tuple[str, str, float]] = []  # (output, edge, pixels)
    landed = {id(mon): idx for mon, idx in assign(shell.monitors, outputs)}
    for monitor in shell.monitors:
        indices = landed.get(id(monitor), [])
        monitors.append(
            {
                "name": monitor.name,
                "index": monitor.index,
                "connector": monitor.connector,
                "description": monitor.description,
                "outputs": [outputs[i].name for i in indices],
                "status": "ok" if indices else "skipped: matches no output",
            }
        )
        for i in indices:
            out = outputs[i]
            hosts = {
                use: surface.name
                for surface in monitor.surfaces
                if isinstance(surface, BarDef)
                for use in _use_names(surface.children)
            }
            geometries, failed = _place(
                monitor.surfaces, ctx.look, (out.width, out.height), hosts, None, None
            )
            for surface in monitor.surfaces:
                geometry = geometries.get(surface.name)
                if geometry is None:
                    surfaces.append(_failed(surface, monitor, out, failed.get(surface.name, "")))
                    continue
                surfaces.append(_surface(surface, geometry, monitor, out, ctx))
                if surface.visible and getattr(surface, "meld", False) is False:
                    edge = _edge(geometry)
                    if edge and geometry.exclusive_zone > 0:
                        pixels = geometry.exclusive_zone + geometry.margin[_MARGIN_AT[edge]]
                        reserved.append((out.name, edge, pixels))
            for frame in monitor.frames:
                surfaces.append(_frame(frame, monitor, out, ctx))
                if frame.visible:
                    for side, thick, margin in zip(
                        ("left", "top", "right", "bottom"),
                        frame.thickness,
                        frame.margin,
                        strict=True,
                    ):
                        if thick > 0:
                            reserved.append((out.name, side, thick + margin))
            for popup in monitor.popups:
                popups.append(_popup(popup, monitor, out, ctx))
    return monitors, surfaces, popups, reserved


def _edge(geometry: Geometry) -> str | None:
    """The edge a surface reserves: its ``exclusive_edge``, else the one anchored edge whose
    opposite is not anchored."""
    if geometry.exclusive_edge:
        return geometry.exclusive_edge
    anchors = set(geometry.anchor)
    free = [e for e in anchors if _OPPOSITE.get(e) not in anchors]
    return free[0] if len(free) == 1 else None


def _desktop(
    outputs: Sequence[VirtualOutput], reserved: list[tuple[str, str, float]]
) -> tuple[Json, ...]:
    """The area of each output that windows get: the output minus the exclusive zones."""
    out: list[Json] = []
    for o in outputs:
        taken = {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0}
        for name, edge, pixels in reserved:
            if name == o.name and edge in taken:
                taken[edge] += pixels
        width = max(o.width - taken["left"] - taken["right"], 0)
        height = max(o.height - taken["top"] - taken["bottom"], 0)
        out.append(
            {
                "output": o.name,
                "x": _num(taken["left"]),
                "y": _num(taken["top"]),
                "width": _num(width),
                "height": _num(height),
            }
        )
    return tuple(out)


def _surface(
    surface: BarDef | PanelDef,
    geometry: Geometry,
    monitor: MonitorDef,
    out: VirtualOutput,
    ctx: _Ctx,
) -> Json:
    body = body_rect(geometry, (out.width, out.height))
    is_bar = isinstance(surface, BarDef)
    data: Json = {
        "kind": "bar" if is_bar else "panel",
        "name": surface.name,
        "monitor": monitor.name,
        "output": out.name,
        "status": "ok",
        "visible": surface.visible,
        "layer": surface.layer.lower(),
        "anchor": sorted(geometry.anchor),
        "size": [_num(geometry.size[0]), _num(geometry.size[1])],
        "margin": [_num(v) for v in geometry.margin],
        "exclusive_zone": _num(geometry.exclusive_zone),
        "exclusive_edge": geometry.exclusive_edge,
        "rect": {
            "x": _num(body.x),
            "y": _num(body.y),
            "width": _num(body.width),
            "height": _num(body.height),
        },
        "content_sized": list(geometry.content),
        "warnings": list(geometry.warnings),
        "style": _style(surface.style, ctx),
        "blocks": _blocks(ctx.rules(surface.children), ctx),
    }
    if isinstance(surface, PanelDef):
        data["attach_to"] = surface.attach_to
        data["meld"] = surface.meld
        data["movable"] = surface.movable
    else:
        data["edge"] = surface.edge.lower()
    return data


def _failed(surface: BarDef | PanelDef, monitor: MonitorDef, out: VirtualOutput, why: str) -> Json:
    return {
        "kind": "bar" if isinstance(surface, BarDef) else "panel",
        "name": surface.name,
        "monitor": monitor.name,
        "output": out.name,
        "status": f"skipped: {why}" if why else "skipped",
        "visible": surface.visible,
        "layer": surface.layer.lower(),
        "blocks": [],
    }


def _frame(frame: FrameDef, monitor: MonitorDef, out: VirtualOutput, ctx: _Ctx) -> Json:
    def sides(v: Sequence[float]) -> Json:
        return dict(zip(("left", "top", "right", "bottom"), (_num(x) for x in v), strict=True))

    def corners(v: Sequence[float]) -> Json:
        return dict(
            zip(
                ("top_left", "top_right", "bottom_right", "bottom_left"),
                (_num(x) for x in v),
                strict=True,
            )
        )

    def border(b: Any) -> Json | None:
        return None if b is None else {"width": _num(b.width), "color": _plain(b.color, ctx)}

    return {
        "kind": "frame",
        "name": frame.name,
        "monitor": monitor.name,
        "output": out.name,
        "status": "ok",
        "visible": frame.visible,
        "layer": "bottom",
        "thickness": sides(frame.thickness),
        "margin": sides(frame.margin),
        "outer_radius": corners(frame.outer_radius),
        "inner_radius": corners(frame.inner_radius),
        "inner_border": border(frame.inner_border),
        "outer_border": border(frame.outer_border),
        "style": _style(frame.style, ctx),
        "edges": {
            side: {
                "thickness": None if e.thickness is None else _num(e.thickness),
                "name": e.name,
                "blocks": _blocks(e.children, ctx),
            }
            for side, e in sorted(frame.edges.items())
        },
        "melds": [meld.name for meld in frame.melds],
        "blocks": [],
    }


def _popup(popup: PopupDef, monitor: MonitorDef, out: VirtualOutput, ctx: _Ctx) -> Json:
    """A Popup of the Monitor as a static card: its placement rules and its blocks. Where it opens
    depends on the block that calls it, so it has no rectangle."""
    return {
        "name": popup.name,
        "monitor": monitor.name,
        "output": out.name,
        "attach": popup.attach.lower(),
        "alignment": popup.alignment.lower(),
        "gap": _num(popup.gap),
        "width": _plain(popup.width, ctx),
        "height": _plain(popup.height, ctx),
        "max_width": _num(popup.max_width),
        "max_height": _num(popup.max_height),
        "tooltip": popup.tooltip,
        "style": _style(popup.style, ctx),
        "blocks": _blocks(popup.children, ctx),
    }


# -- blocks and values ---------------------------------------------------------------------------


def _use_names(children: Sequence[Any]) -> list[str]:
    out: list[str] = []
    for child in children:
        if isinstance(child, m.UseNode) and child.name:
            out.append(child.name)
        out.extend(_use_names(getattr(child, "children", ()) or ()))
        out.extend(_use_names(getattr(child, "body", ()) or ()))
        out.extend(_use_names(getattr(child, "else_body", None) or ()))
    return out


def _blocks(children: Sequence[Any], ctx: _Ctx) -> list[Json]:
    return [b for child in children if (b := _block(child, ctx)) is not None]


def _block(node: Any, ctx: _Ctx) -> Json | None:
    if isinstance(node, m.Node):
        return {
            "type": "block",
            "kind": node.kind,
            "name": node.name,
            "classes": list(node.classes),
            "part": node.part,
            "props": {k: _plain(v, ctx) for k, v in sorted(node.props.items())},
            "style": _style(node.style, ctx),
            "tooltip": _tooltip(node.tooltip, ctx),
            "children": _blocks(node.children, ctx),
        }
    if isinstance(node, m.UseNode):
        return {
            "type": "module",
            "module": node.module,
            "name": node.name,
            "label": _label(node, ctx),
            "params": _params(node, ctx),
            "common": {k: _plain(v, ctx) for k, v in sorted(node.common.items())},
            "tooltip": _tooltip(node.tooltip, ctx),
            "children": _blocks(node.children, ctx),
        }
    if isinstance(node, m.IfNode):
        return {
            "type": "if",
            "condition": node.condition.text if node.condition else None,
            "children": _blocks(node.body, ctx),
            "else": None if node.else_body is None else _blocks(node.else_body, ctx),
        }
    if isinstance(node, m.ForNode):
        return {
            "type": "for",
            "items": node.items.text if node.items else None,
            "children": _blocks(node.body, ctx),
        }
    return None


def _params(node: m.UseNode, ctx: _Ctx) -> Json:
    """The params of a module call: what is written over what the module declares as default. A
    slot (``<| ... |>``) is data the running shell fills: it stays a ``{"slot": text}``."""
    out: Json = {}
    definition = ctx.module(node.module)
    if definition is not None:
        for name, decl in definition.params.items():
            if decl.default is not None:
                out[name] = _plain(decl.default, ctx)
    for name, value in node.params.items():
        out[name] = _plain(value, ctx)
    return dict(sorted(out.items()))


def _label(node: m.UseNode, ctx: _Ctx) -> str:
    """What a mockup writes in a module's slot: its ``Label`` or ``Text`` param when it is plain
    text, else the module's name."""
    params = _params(node, ctx)
    for key in ("Label", "Text", "Format"):
        value = params.get(key)
        if isinstance(value, str) and value:
            return value
    return node.name or node.module


def _tooltip(ref: Any, ctx: _Ctx) -> Json | None:
    if ref is None:
        return None
    return {
        "popup": ref.name,
        "text": _plain(ref.description, ctx) if ref.description is not None else None,
    }


def _style(style: Mapping[str, Any] | None, ctx: _Ctx) -> Json:
    return {k: _plain(v, ctx) for k, v in sorted((style or {}).items())}


def _hex(c: m.Color) -> str:
    base = f"#{c.r:02X}{c.g:02X}{c.b:02X}"
    return base if c.a == 255 else f"{base}{c.a:02X}"


def _plain(value: Any, ctx: _Ctx | None = None) -> Any:
    """A value as plain data: a number of pixels, a percentage or word as text, a colour as
    ``#RRGGBB[AA]``, a token reference as ``{"token", "value"}`` (the value of the theme in use), a
    slot as ``{"slot": text}`` (data the running shell fills)."""
    match value:
        case None:
            return None
        case m.Length(px):
            return _num(px)
        case m.Percent(v):
            return f"{_num(v)}%"
        case m.Auto():
            return "auto"
        case m.Expand():
            return "expand"
        case m.Color():
            return _hex(value)
        case m.Enum(name):
            return name.lower()
        case m.Bool(v) | m.Number(v) | m.Text(v):
            return _num(v) if isinstance(v, float) else v
        case m.Sides(left, top, right, bottom):
            return {
                "left": _num(left),
                "top": _num(top),
                "right": _num(right),
                "bottom": _num(bottom),
            }
        case m.Seq(items):
            return [_plain(i, ctx) for i in items]
        case m.Shadows(items):
            return {"shadows": len(items)}
        case m.TokenRef(path):
            token = ctx.look.tokens.get(path) if ctx is not None and ctx.look is not None else None
            return {"token": path, "value": None if token is None else _token_value(token.value)}
        case m.SlotValue(parts):
            return {"slot": "".join(p if isinstance(p, str) else p.text for p in parts)}
    if isinstance(value, bool | int | float | str):
        return _num(value) if isinstance(value, float) else value
    if isinstance(value, tuple | list):
        return [_plain(v, ctx) for v in value]
    return _token_value(value)


def _num(v: Any) -> Any:
    """A whole number as an int: ``12.0`` is ``12`` in the data."""
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def _token_value(value: Any) -> Any:
    """The plain value of a theme token (tess_dl values: strings, numbers, words, lists)."""
    if isinstance(value, tess_dl.List):
        return [_token_value(v) for v in value.items]
    for attr in ("value", "text"):
        inner = getattr(value, attr, None)
        if isinstance(inner, bool | int | float | str):
            return _num(inner)
    return None


def _tokens(look: Any) -> Json:
    if look is None:
        return {}
    out: Json = {}
    for path in sorted(look.tokens):
        value = _token_value(look.tokens[path].value)
        if value is not None:  # a shadow list is not drawn by a mockup
            out[path] = value
    return out


def _finding(f: Finding) -> Json:
    return {
        "file": f.file,
        "line": f.line,
        "column": f.column,
        "severity": f.severity,
        "rule": f.rule,
        "message": f.message,
        "hint": f.hint,
    }


__all__ = ["PREVIEW_VERSION", "PreviewModel", "VirtualOutput", "describe", "preview"]
