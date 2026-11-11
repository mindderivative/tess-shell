"""Regenerate the M4a widgets gallery and its KWin checklist in /tmp/tess-kwin-m4a/gallery (not
collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m4a_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m4a`` and starts nothing:

* ``gallery/``: the config directory. One floating Panel shows every block that exists today (Box,
  FlexBox, Rectangle, SVG with an icon, Text and Spacer) in each state it has: normal, ``:hovered``,
  ``:pressed`` and ``:disabled`` (``Enabled: false``); a ``Meter`` module (a test module) whose
  parts ``track`` and ``fill`` are styled with ``Meter::track`` and ``Meter::fill:hovered`` and the
  like; a ``Pad`` module whose button runs ``Call`` with arguments (the Python action writes what it
  received to the log and to the Panel) and whose second button opens a Popup that reads
  ``caller.data``. The colours are theme tokens, so the gallery follows Plasma's light and dark.
  Text fields are not in it: they wait for the new tre properties (TRE-REQ-016).
* ``run.sh``: run the shell. ``check.sh``: the files are valid.
* ``checklist-m4a.txt``: one look per widget with the exact line to see.

The state directory is ``/tmp/tess-kwin-m4a/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m4a")
CFG = ROOT / "gallery"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default, Gallery], Follow_Desktop: true }\n}\n"
)

STYLESHEET = """---
TDL: 0.1
Name: Gallery
---

# The states of every tile of the gallery (class tile), one rule each. A key a block does not take
# (Background on a Rectangle, Fill on a Box) is skipped for that block, so one rule serves all. The
# last six rules style the parts of the Meter module (Module::part, each with its states).
Stylesheet {
    Rule { Selector: ".tile:hovered", Background: $color.accent, Fill: $color.accent, Border_Color: $color.on_surface }
    Rule {
        Selector: ".tile:pressed"
        Background: $color.accent
        Fill: $color.accent
        Border_Width: 3
        Border_Color: $color.warning
    }
    Rule {
        Selector: ".tile:disabled"
        Background: $color.surface
        Fill: $color.surface
        Border_Color: $color.outline
        Opacity: 0.55
    }
    Rule { Selector: ".icon:hovered", Foreground: $color.primary }
    Rule { Selector: ".icon:pressed", Foreground: $color.warning }
    Rule { Selector: ".icon:disabled", Foreground: $color.on_surface_muted, Opacity: 0.55 }
    Rule { Selector: "Text:disabled", Foreground: $color.on_surface_muted, Opacity: 0.55 }
    Rule { Selector: "#Call_Button:hovered", Background: $color.primary }
    Rule { Selector: "#Call_Button:pressed", Background: $color.accent, Border_Width: 3 }
    Rule { Selector: "#Menu_Button:hovered", Background: $color.primary }
    Rule { Selector: "#Menu_Button:pressed", Background: $color.accent, Border_Width: 3 }
    Rule { Selector: "#Menu_Call:hovered", Background: $color.primary }
    Rule { Selector: "#Menu_Close:hovered", Background: $color.primary }

    Rule { Selector: "Meter::track", Fill: $color.outline, Corner_Radius: 5 }
    Rule { Selector: "Meter::fill", Fill: $color.success, Corner_Radius: 5 }
    Rule { Selector: "Meter::fill:hovered", Fill: $color.primary }
    Rule { Selector: "Meter::fill:pressed", Fill: $color.warning, Border_Width: 2, Border_Color: $color.on_surface }
    Rule { Selector: "Meter::track:disabled", Opacity: 0.4 }
    Rule { Selector: "Meter::fill:disabled", Fill: $color.on_surface_muted, Opacity: 0.4 }
}
"""

METER_TDL = """---
TDL: 0.1
Name: Meter
---

# A test module for ::part: the track and the fill are parts, and the module is disabled as a whole.
Module {
    Params {
        enabled { Type: boolean, Default: true }
    }
    Box {
        Name: Root
        Width: 180
        Height: 14
        Enabled: {{ params.enabled }}
        Children {
            Rectangle { Name: Track, Part: track, Width: 180, Height: 14 }
            Rectangle { Name: Fill, Part: fill, Width: 110, Height: 14, Align_Self: START }
        }
    }
}
"""

METER_PY = """from tess_shell import Module


class Meter(Module):
    pass
"""

PAD_TDL = """---
TDL: 0.1
Name: Pad
---

# Call with arguments, and a Popup that reads caller.data.
Module {
    Params {
        label { Type: string, Default: "from the Pad" }
    }
    FlexBox {
        Name: Root
        Spacing: 12
        Align_Items: CENTER
        Children {
            FlexBox {
                Name: Call_Button
                Width: 150
                Height: 34
                Align_Items: CENTER
                Justify_Content: CENTER
                Style { Background: $color.surface_raised, Border_Width: 1, Border_Color: $color.outline, Corner_Radius: 6 }
                On_Click { Action: Call, Target: "Pad.log_press", Label: {{ params.label }}, Amount: 5, Kind: {{ event.name }} }
                Children { Text { Text: "Call with arguments", Width: AUTO, Height: AUTO } }
            }
            FlexBox {
                Name: Menu_Button
                Width: 190
                Height: 34
                Align_Items: CENTER
                Justify_Content: CENTER
                Style { Background: $color.surface_raised, Border_Width: 1, Border_Color: $color.outline, Corner_Radius: 6 }
                On_Click: open_menu
                Children { Text { Text: "Open the popup (caller.data)", Width: AUTO, Height: AUTO } }
            }
            Text { Name: Last, Text: {{ last }}, Width: AUTO, Height: AUTO }
        }
    }
}
"""

PAD_PY = """from tess_shell import Module, action


class Pad(Module):
    def start(self):
        self.ctx.send("last", "no call yet")

    @action
    def log_press(self, event):
        text = ", ".join(f"{k}={v}" for k, v in sorted(event.args.items()))
        self.ctx.log.info(f"Pad.log_press received: {text}")
        self.ctx.send("last", f"received: {text}")

    @action
    def open_menu(self, event):
        self.ctx.popup("Data_Menu", data={"Title": "Hello from the Pad", "Count": 3})
"""

CAPTION = "Text { Width: 150, Height: AUTO, Font_Size: 13, Foreground: $color.on_surface_muted, Text: %s }"


def tile_style() -> str:
    return (
        "Style { Background: $color.surface_raised, Border_Width: 1, Border_Color: $color.outline, "
        "Corner_Radius: 6 }"
    )


def label(text: str) -> str:
    return f'Text {{ Text: "{text}", Width: AUTO, Height: AUTO, Font_Size: 13 }}'


def box_tile(kind: str, name: str, text: str, enabled: bool) -> str:
    extra = "" if enabled else "Enabled: false, "
    flex = "Align_Items: CENTER, Justify_Content: CENTER, " if kind == "FlexBox" else ""
    child = (
        label(text)
        if kind == "FlexBox"
        else label(text).replace("Text {", "Text { Align_Self: CENTER,")
    )
    return (
        f"{kind} {{ Name: {name}, Class: tile, {extra}{flex}Width: 104, Height: 34, "
        f"{tile_style()}, Children {{ {child} }} }}"
    )


def rect_tile(name: str, enabled: bool) -> str:
    extra = "" if enabled else "Enabled: false, "
    return (
        f"Rectangle {{ Name: {name}, Class: tile, {extra}Width: 104, Height: 34, "
        "Fill: $color.surface_raised, Border_Width: 1, Border_Color: $color.outline, "
        "Corner_Radius: 6 }"
    )


def svg_tile(name: str, enabled: bool) -> str:
    extra = "" if enabled else "Enabled: false, "
    return f'SVG {{ Name: {name}, Class: icon, {extra}Icon: "mdi:home", Width: 34, Height: 34 }}'


def text_tile(name: str, enabled: bool) -> str:
    extra = "" if enabled else "Enabled: false, "
    return f'Text {{ Name: {name}, {extra}Text: "Text", Width: AUTO, Height: AUTO, Font_Size: 14 }}'


def row(caption: str, *items: str) -> str:
    body = " ".join(items)
    return (
        "FlexBox { Spacing: 10, Align_Items: CENTER, Children { "
        + CAPTION % f'"{caption}"'
        + f" {body} }} }}"
    )


def tiles(kind: str) -> list[str]:
    states = (("Normal", True), ("Hover", True), ("Press", True), ("Disabled", False))
    out = []
    for state, enabled in states:
        name = f"{kind}_{state}"
        if kind in ("Box", "FlexBox"):
            out.append(box_tile(kind, name, state.lower(), enabled))
        elif kind == "Rectangle":
            out.append(rect_tile(name, enabled))
        else:
            out.append(svg_tile(name, enabled))
    return out


def spacer_row() -> str:
    square = "Rectangle { Width: 20, Height: 20, Fill: $color.primary, Corner_Radius: 4 }"
    return row(
        "Spacer",
        "FlexBox { Name: Spacer_Frame, Width: 300, Height: 24, Align_Items: CENTER, "
        f"Style {{ Border_Width: 1, Border_Color: $color.outline }}, Children {{ {square} "
        f"Spacer {{ Name: Spacer_Gap }} {square} }} }}",
        label("the Spacer pushes the squares to the ends"),
    )


def header() -> str:
    cells = " ".join(
        f'Text {{ Text: "{t}", Width: 104, Height: AUTO, Font_Size: 12, Foreground: $color.on_surface_muted }}'
        for t in ("normal", "hovered", "pressed", "disabled")
    )
    return row("", cells)


ROWS = f"""Text {{ Text: "M4a widgets gallery: Enabled, :disabled, ::part, Call, caller.data", Width: AUTO, Height: AUTO, Font_Size: 15, Font_Weight: 500 }}
{header()}
{row("Box", *tiles("Box"))}
{row("FlexBox", *tiles("FlexBox"))}
{row("Rectangle", *tiles("Rectangle"))}
{row("SVG (an icon)", *tiles("SVG"))}
{row("Text", text_tile("Text_Normal", True), "Spacer { Width: 70 }", text_tile("Text_Disabled", False), label("takes no pointer: only :disabled"))}
{spacer_row()}
{row("Meter ::parts", "Meter { Name: Meter_On }", "Meter { Name: Meter_Off, enabled: false }", label("enabled | enabled: false"))}
{row("Call, caller.data", "Pad { Name: Pad_One }")}"""

# the gallery's content as one column: in the Panel, and (for the headless test) in a Bar
COLUMN = "FlexBox { Flex: VERTICAL, Padding: 16, Spacing: 12, Children { " + ROWS + " } }"

POPUP = """Popup {
    Name: Data_Menu
    Gap: 4
    Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 20% }
    Children {
        FlexBox {
            Name: Menu_Card
            Flex: VERTICAL
            Padding: 12
            Spacing: 6
            Children {
                Text { Name: Menu_Title, Text: {{ caller.data.Title }}, Width: AUTO, Height: AUTO, Font_Size: 15 }
                Text { Name: Menu_Source, Text: called by {{ caller.module }} at {{ caller.use.name }}, Width: AUTO, Height: AUTO, Font_Size: 12, Foreground: $color.on_surface_muted }
                FlexBox {
                    Name: Menu_Call
                    Padding: 8
                    Style { Background: $color.surface, Corner_Radius: 6 }
                    On_Click { Action: Call, Target: "Pad.log_press", Id: {{ caller.data.Count }}, From: "popup" }
                    Children { Text { Text: "Call with caller.data.Count", Width: AUTO, Height: AUTO } }
                }
                FlexBox {
                    Name: Menu_Close
                    Padding: 8
                    Style { Background: $color.surface, Corner_Radius: 6 }
                    On_Click: Close
                    Children { Text { Text: "Close", Width: AUTO, Height: AUTO } }
                }
            }
        }
    }
}"""

PANEL = (
    "Panel { Name: Gallery, Layer: TOP, Width: 640, Height: 500, "
    "Style { Background: $color.surface, Corner_Radius: 12, Elevation: 30% }, "
    "Children { " + COLUMN + " } }"
)

BODY = f"""
Shell {{
    Monitor {{
        Name: Main
        Index: 0
        Children {{
            {PANEL}
            {POPUP}
        }}
    }}
}}
"""

CHECKLIST = """M4a widgets gallery: one look each.  Start it with /tmp/tess-kwin-m4a/run.sh, stop with Ctrl+C.
Do these in light and in dark (Plasma's colour scheme; the gallery follows it, every colour is a token).
Not in this run: text fields (they wait for the new tre properties, TRE-REQ-016).

Row   Look
----  ------------------------------------------------------------------------------------------
1     The Panel "Gallery" is centred, with a heading and a header row: normal, hovered, pressed, disabled.
2     Box row. Column 1 is a plain tile. Point at column 2: the tile fills with the accent colour (steel
      blue) and its 1 px border turns light (on_surface); leave: the plain tile again. Hold the button
      on column 3: the fill is the accent colour and the border becomes 3 px, orange (warning);
      release: back. Column 4 is dimmed (about half opacity, a quiet border) and does nothing: point
      at it and press, nothing changes. (The Box's text sits at the left: a Box is a one-cell grid.)
3     FlexBox row: the same four.
4     Rectangle row: the same four (a rounded rectangle, no text).
5     SVG row: a house icon four times. Pointing at the second turns it primary blue, holding the third
      turns it orange (warning); the fourth is grey and faint and does not react.
6     Text row: "Text" normal, and "Text" disabled (faint). A Text takes no pointer, so no hover.
7     Spacer row: two squares at the two ends of the framed strip: the Spacer pushes them apart.
8     Meter row (::part). The first bar: a grey track with a green fill. Point at the fill: it turns
      primary; press: orange with a white border; the track does not change. The second bar
      (enabled: false) is faint grey as a whole and does not react to the pointer at all.
9     Call row. Click "Call with arguments": the text to the right reads
      "received: Amount=5, Kind=click, Label=from the Pad" and the log has a line
      "Pad.log_press received: Amount=5, Kind=click, Label=from the Pad". Click it again: the same.
10    Click "Open the popup (caller.data)": a popup opens under the button with "Hello from the Pad",
      then "called by Pad at ...Pad_One". Click "Call with caller.data.Count": the Panel text reads
      "received: From=popup, Id=3" (the popup stays open). Click "Close": the popup closes.
11    Click outside the popup while it is open: it closes. The log shows no ERROR line for any of this
      (grep ERROR in the log).
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_gallery(cfg: Path) -> None:
    """The gallery's config directory (shell file, stylesheet, the two modules, settings)."""
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BODY)
    (cfg / "settings.tdl").write_text(SETTINGS)
    (cfg / "Stylesheets").mkdir()
    (cfg / "Stylesheets" / "Gallery_Stylesheet.tdl").write_text(STYLESHEET)
    for name, tdl, py in (("Meter", METER_TDL, METER_PY), ("Pad", PAD_TDL, PAD_PY)):
        folder = cfg / "Modules" / name
        folder.mkdir(parents=True)
        (folder / f"{name}_Module.tdl").write_text(tdl)
        (folder / f"{name}_Module.py").write_text(py)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_gallery(CFG)
    (ROOT / "checklist-m4a.txt").write_text(CHECKLIST)
    script(
        "run.sh",
        "# The M4a widgets gallery.  Usage: run.sh   (Ctrl+C stops it)\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m4a/state\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m4a/gallery\n",
    )
    script(
        "check.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m4a/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m4a/gallery\n",
    )
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
