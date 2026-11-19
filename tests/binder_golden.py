"""What the binder builds, written out as plain data, for the golden test of the bind cost work
(``tests/test_binder_golden.py``): for each fixture, every entry of the built view (the typed
kind, the tre properties it was given, its state styles, its motion, what its wire listens for)
and what tre itself says about the node (``Node.get`` of every property the binder sets).

Not collected by pytest. ``python -m tests.binder_golden`` rewrites
``tests/fixtures/binder_golden.json`` from the code as it is: only do that for a deliberate change
of what the binder builds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import Entry, View, build
from tests.widgets_live import running

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "binder_golden.json"

# properties the binder sets on tre nodes after the build, besides those of the spec
EXTRA_PROPS = (
    "tab_index",
    "visible",
    "focusable",
    "hit_testable",
    "disabled",
    "pressed",
    "read_only",
    "a11y_hidden",
    "checked",
    "selected",
    "value",
    "expanded",
    "role",
    "label",
)


def plain(value: Any) -> Any:
    """JSON-able, stable: no object addresses."""
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, list | tuple):
        return [plain(v) for v in value]
    if isinstance(value, set | frozenset):
        return sorted(plain(v) for v in value)
    text = repr(value)
    assert "0x" not in text, f"an unstable repr: {text}"
    return text


def idle(entry: Entry, wire: Any) -> bool:
    """A wire that does nothing: no listener, hook, handler, state style, transition, name or flag.
    The binder gives such a node no wire (``_inert``), so it counts as ``None`` either way."""
    return (
        entry.typed.name is None
        and not (wire.wired or wire.hooks or wire.always or wire.handlers or wire.states)
        and wire.motion is None
        and not (wire.disabled or wire.checked or wire.selected or wire.owned or wire.part)
        and not (wire.mirror or wire.focus_to or wire.focus_target or wire.on_block)
        and not (wire.tip_key or wire.tip_auto or wire.tooltip_gate)
    )


def wire_of(entry: Entry) -> Any:
    wire = entry.wire
    if wire is None or idle(entry, wire):
        return None
    return {
        "wired": sorted(wire.wired),
        "states": plain(wire.states),
        "tip_key": wire.tip_key,
        "tip_auto": wire.tip_auto,
        "disabled": wire.disabled,
        "inherited": wire.inherited,
        "part": wire.part,
        "checked": wire.checked,
        "selected": wire.selected,
        "owned": wire.owned,
        "in_checked": wire.in_checked,
        "in_selected": wire.in_selected,
        "label": wire.label,
        "hooks": {k: len(v) for k, v in sorted(wire.hooks.items())},
        "always": {k: len(v) for k, v in sorted(wire.always.items())},
        "handlers": sorted(wire.handlers),
        "shown": plain(wire.shown),
        "saved": plain(wire.saved),
        "mirror": wire.mirror is not None,
        "focus_to": wire.focus_to is not None,
        "focus_target": wire.focus_target is not None,
        "on_block": wire.on_block is not None,
        "tooltip_gate": wire.tooltip_gate is not None,
        "field_text": wire.field_text,
        "focused": wire.focused,
        "motion": wire.motion is not None,
    }


def motion_of(entry: Entry) -> Any:
    motion = entry.motion
    if motion is None:
        return None
    return {
        "props": sorted(motion.props),
        "duration": motion.duration,
        "easing": repr(motion.easing),
    }


def dump_entry(entry: Entry, controls: dict[Any, str]) -> dict[str, Any]:
    tre = entry.tre
    names = sorted({*entry.props, *EXTRA_PROPS})
    seen: dict[str, Any] = {}
    if tre is not None:
        for name in names:
            try:
                seen[name] = plain(tre.get(name))
            except (ValueError, KeyError, TypeError) as exc:
                seen[name] = f"!{type(exc).__name__}"
    return {
        "kind": entry.typed.kind,
        "name": entry.typed.name,
        "has_tre": tre is not None,
        "props": plain(entry.props),
        "states": plain(entry.states),
        "motion": motion_of(entry),
        "rank": entry.rank,
        "wire": wire_of(entry),
        "control": controls.get(tre, ""),
        "tre": seen,
        "children": [dump_entry(c, controls) for c in entry.children],
    }


def dump_view(view: View) -> dict[str, Any]:
    controls = {tre: type(ctl).__name__ for tre, ctl in view.controls.items()}
    return {
        "entries": [dump_entry(e, controls) for e in view.entries],
        "nodes": sorted(view.nodes),
        "kinds": plain(view.kinds),
        "applied": plain(view.applied),
        "wires": sorted(view.wires),
        "motions": sorted(view.motions),
        "dynamic": plain(view.dynamic),
        "controls": sorted(controls.values()),
        "runners": len(view.runners),
        "tab_stops": len(view.tab_stops()),
        "roots": len(view.roots),
    }


# -- fixtures -------------------------------------------------------------------------------

ENTRIES = " ".join(
    f"FlexBox {{ Class: list_item, Key: k{i}, Height: 30, Children "
    f'{{ Text {{ Text: "Entry {i}", Width: AUTO, Height: AUTO }} }} }}'
    for i in range(1, 4)
)
CLICK = 'On_Click { Action: Call, Target: "Driver.pressed" }'
CHANGED = 'On_Changed { Action: Call, Target: "Driver.changed" }'

# TDL layouts run in the shell's real headless Bar (standard modules, Default stylesheet)
LAYOUTS: dict[str, str] = {
    "display": (
        'Label { Name: L, Text: "Hello", Width: 80, Tooltip: "tip" } '
        "Label { Text: x, Enabled: false } "
        "ProgressBar { Value: 25, Min: 0, Max: 50, Label: Upload } "
        "Badge { Count: 7 } Badge { Dot: true } "
        'Icon { Icon: "mdi:home", Size: 24 } '
        'Marquee_Text { Text: "a very long text that does not fit in a hundred pixels", '
        "Width: 100 } "
        'Marquee_Text { Text: "fits", Width: 100, Enabled: false }'
    ),
    "buttons": (
        f'Button {{ Name: One, Text: "Open", Icon: "mdi:home", {CLICK} }} '
        f'Button {{ Text: "Off", Enabled: false, {CLICK} }} '
        f"Toggle {{ Name: T, Label: t, {CHANGED} }} Checkbox {{ Text: Remember, {CHANGED} }} "
        "Slider { Value: 25, Min: 0, Max: 50, Step: 5, Label: Volume } Slider { Enabled: false }"
    ),
    "list_menu": (
        f"List {{ Height: 90, Label: Files, {CHANGED}, Children {{ {ENTRIES} }} }} "
        'Menu { Children { MenuItem { Text: "New" } MenuItem { Separator: true } '
        'MenuItem { Text: "Open" } } } '
        "Expander { Content_Fade: false, Children { Label { Text: x } } }"
    ),
    "fields": (
        'TextInput { Name: Ed, Text: "abc", Placeholder: p } Button { Name: Go, Text: "g" } '
        'TextEditor { Text: "x" } TextInput { Enabled: false, Text: "y" }'
    ),
    "disabled_nest": (
        'FlexBox { Enabled: false, Children { Button { Text: "a", '
        + CLICK
        + ' } FlexBox { Children { Label { Text: "b" } Toggle { } } } } } '
        "FlexBox { Role: BUTTON, Tab_Index: 2 } FlexBox { Role: BUTTON, Tab_Index: 1 } "
        "FlexBox { Visible: false, Children { Label { Text: h } } }"
    ),
}


def direct_trees() -> dict[str, list[m.Node]]:
    """Typed trees bound without the model: states, motion, handlers, hidden, Tab_Index."""
    handler = m.Handler("pressed")
    fill = m.Color(10, 20, 30, 255)
    hot = m.Color(40, 50, 60, 255)

    def row(r: int, wide: int) -> m.Node:
        return m.Node(
            "FlexBox",
            name=f"R{r}",
            props={"Flex": m.Enum("HORIZONTAL"), "Spacing": m.Number(2)},
            style={"Background": fill} if r % 2 else {},
            states={"hovered": {"Background": hot}} if r % 3 == 0 else {},
            handlers={"On_Click": handler} if r % 2 == 0 else {},
            children=tuple(
                m.Node(
                    "Text",
                    name=f"T{r}_{c}" if c == 0 else None,
                    props={"Text": m.Text(f"{r}.{c}")},
                    style={"Font_Size": m.Number(12), "Foreground": hot},
                    states={"disabled": {"Foreground": fill}} if c % 4 == 0 else {},
                )
                for c in range(wide)
            ),
        )

    big = [
        m.Node(
            "FlexBox",
            props={"Width": m.Length(1000), "Tab_Index": m.Number(3)},
            children=tuple(row(r, 5) for r in range(6)),
        )
    ]
    motion = [
        m.Node(
            "FlexBox",
            name="M",
            props={"Width": m.Length(40), "Height": m.Length(40), "Visible": m.Bool(False)},
            style={
                "Background": fill,
                "Transition": m.Seq((m.Text("Background"),)),
                "Duration": m.Number(120),
            },
            states={"hovered": {"Background": hot}},
        ),
        m.Node("Spacer", props={"Width": m.Length(5)}),
        m.Node("Rectangle", props={"Width": m.Length(5), "Height": m.Length(5), "Fill": hot}),
    ]
    return {"big_small": big, "motion_hidden": motion}


def window_for(w: int = 400, h: int = 200) -> Window:
    return Window(w, h)


def dump_all() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, children in LAYOUTS.items():
        with running(children) as w:
            out[f"layout:{name}"] = dump_view(w.view)
    for name, tree in direct_trees().items():
        window = window_for()
        view = build(tree, window)
        out[f"direct:{name}"] = dump_view(view)
        view.dispose()
    return out


def main() -> int:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(dump_all(), indent=1, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
