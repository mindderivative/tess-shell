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
* a second Panel, ``Fields``, on the right: the text fields (A2). The ``TextInput`` module normal, with
  a placeholder, read-only, a password, limited to 8 characters and disabled; the ``TextField``
  block with ``Overflow`` SCROLL, ELLIPSIS and CLIP over a long line; the ``TextEditor`` module
  wrapping by word and not wrapping, and disabled; and an ``Echo`` module (a test module) that shows
  the last ``On_Changed``, ``On_Submit`` and ``On_Text_Commit`` it received. The Panel has no
  ``Keyboard`` key: it holds text fields, so the shell gives it ``on_demand``.
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
    "  Appearance { Stylesheets: [Default, Gallery, Gallery_Fields], Follow_Desktop: true }\n}\n"
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

FIELDS_STYLESHEET = """---
TDL: 0.1
Name: Gallery_Fields
---

# The hint of every TextInput is the primary colour here (the part ::placeholder), so the part can be
# seen. A TextField takes its look from the theme: no rule colours the fields themselves.
Stylesheet {
    Rule { Selector: "TextInput::placeholder", Foreground: $color.primary }
    Rule { Selector: "TextInput::placeholder:disabled", Foreground: $color.on_surface_muted }
}
"""

ECHO_TDL = """---
TDL: 0.1
Name: Echo
---

# A test module: the text events of the fields, as the last one that arrived.
Module {
    FlexBox {
        Name: Root
        Flex: VERTICAL
        Spacing: 4
        Width: 270
        Children {
            Text { Text: "last event", Width: AUTO, Height: AUTO, Font_Size: 12, Foreground: $color.on_surface_muted }
            Text { Name: Last, Text: {{ last }}, Width: 270, Height: AUTO, Font_Size: 13 }
            Text { Name: Count, Text: {{ count }}, Width: AUTO, Height: AUTO, Font_Size: 12, Foreground: $color.on_surface_muted }
        }
    }
}
"""

ECHO_PY = """from tess_shell import Module, action


def short(text, limit=34):
    text = text or ""
    return repr(text if len(text) <= limit else text[: limit - 1] + "...")


class Echo(Module):
    def start(self):
        self.n = 0
        self.ctx.send("last", "nothing yet: click a field and type")
        self.ctx.send("count", "0 events")

    def shown(self, what):
        self.n += 1
        self.ctx.log.info(f"Echo: {what}")
        self.ctx.send("last", what)
        self.ctx.send("count", f"{self.n} events")

    @action
    def changed(self, event):
        self.shown(f"changed: {short(event.old)} -> {short(event.new)}")

    @action
    def submit(self, event):
        self.shown("submit (Enter)")

    @action
    def commit(self, event):
        self.shown(f"commit: {short(event.text)}")
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

LONG = "The quick brown fox jumps over the lazy dog and then does it all over again, twice"
PARAGRAPH = (
    "A text editor wraps a long line by word at the width of its box, a new line starts a new "
    "paragraph, and a text longer than the box scrolls down to the caret."
)
EVENTS = (
    'On_Changed { Action: Call, Target: "Echo.changed" } '
    'On_Submit { Action: Call, Target: "Echo.submit" } '
    'On_Text_Commit { Action: Call, Target: "Echo.commit" }'
)


# the events of a field that cannot submit: a limited, read-only, password or disabled one
CHANGES = (
    'On_Changed { Action: Call, Target: "Echo.changed" } '
    'On_Text_Commit { Action: Call, Target: "Echo.commit" }'
)


def field_row(caption: str, field: str) -> str:
    return (
        "FlexBox { Flex: VERTICAL, Spacing: 3, Children { "
        f'Text {{ Text: "{caption}", Width: AUTO, Height: AUTO, Font_Size: 12, '
        "Foreground: $color.on_surface_muted } " + field + " } }"
    )


def block_field(name: str, overflow: str, enabled: bool = True) -> str:
    off = "" if enabled else "Enabled: false, "
    return (
        f'TextField {{ Name: {name}, {off}Width: 270, Text: "{LONG}", '
        f"Style {{ Overflow: {overflow} }} }}"
    )


SINGLE = [
    field_row(
        "TextInput: click it and type; Enter submits",
        f'TextInput {{ Name: In_Normal, Width: 270, Text: "hello", {EVENTS} }}',
    ),
    field_row(
        "placeholder (the part ::placeholder is blue)",
        'TextInput { Name: In_Hint, Width: 270, Placeholder: "Search..." }',
    ),
    field_row(
        "Read_Only: select and copy, no typing",
        f'TextInput {{ Name: In_Read, Width: 270, Read_Only: true, Text: "read only text", {CHANGES} }}',
    ),
    field_row(
        "Password: bullets, no copy",
        f'TextInput {{ Name: In_Pass, Width: 270, Password: true, Text: "secret", {CHANGES} }}',
    ),
    field_row(
        "Max_Length: 8",
        f'TextInput {{ Name: In_Max, Width: 270, Max_Length: 8, Placeholder: "8 characters", {CHANGES} }}',
    ),
    field_row(
        "Enabled: false", f'TextInput {{ Name: In_Off, Width: 270, Enabled: false, Text: "disabled", {CHANGES} }}'
    ),
    field_row(
        "Overflow SCROLL (the default): scrolls to the caret", block_field("F_Scroll", "SCROLL")
    ),
    field_row(
        "Overflow ELLIPSIS: cut with ... until focused", block_field("F_Ellipsis", "ELLIPSIS")
    ),
    field_row("Overflow CLIP: cut, never scrolls", block_field("F_Clip", "CLIP")),
]

MULTI = [
    field_row(
        "TextEditor, Wrap WORD (default)",
        f'TextEditor {{ Name: Ed_Word, Width: 270, Lines: 4, Text: "{PARAGRAPH}", '
        'On_Changed { Action: Call, Target: "Echo.changed" } }',
    ),
    field_row(
        "TextEditor, Wrap NONE: scrolls sideways",
        f'TextEditor {{ Name: Ed_None, Width: 270, Lines: 3, Wrap: NONE, Text: "{PARAGRAPH}" }}',
    ),
    field_row(
        "TextEditor, Enabled: false",
        f'TextEditor {{ Name: Ed_Off, Width: 270, Lines: 2, Enabled: false, '
        f'Text: "disabled editor", {CHANGES} }}',
    ),
    "Echo { Name: Echo_One }",
]

FIELDS_COLUMN = (
    "FlexBox { Flex: VERTICAL, Padding: 16, Spacing: 10, Children { "
    'Text { Text: "M4a text fields: TextInput, TextEditor, TextField", Width: AUTO, Height: AUTO, '
    "Font_Size: 15, Font_Weight: 500 } "
    "FlexBox { Spacing: 16, Align_Items: START, Children { "
    "FlexBox { Flex: VERTICAL, Spacing: 8, Children { " + " ".join(SINGLE) + " } } "
    "FlexBox { Flex: VERTICAL, Spacing: 8, Children { " + " ".join(MULTI) + " } } "
    "} } } }"
)

FIELDS_PANEL = (
    "Panel { Name: Fields, Layer: TOP, Anchor: [TOP, RIGHT], Inset: [0, 24, 24, 0], Width: 640, "
    "Height: 600, Style { Background: $color.surface, Corner_Radius: 12, Elevation: 30% }, "
    "Children { " + FIELDS_COLUMN + " } }"
)

PANEL = (
    "Panel { Name: Gallery, Layer: TOP, Anchor: [TOP, LEFT], Inset: [24, 24, 0, 0], Width: 640, "
    "Height: 500, "
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
            {FIELDS_PANEL}
            {POPUP}
        }}
    }}
}}
"""

CHECKLIST = """M4a widgets gallery: one look each.  Start it with /tmp/tess-kwin-m4a/run.sh, stop with Ctrl+C.
Do these in light and in dark (Plasma's colour scheme; the gallery follows it, every colour is a token).
The text fields are the second Panel, on the right: rows 12 to 20.

Row   Look
----  ------------------------------------------------------------------------------------------
1     The Panel "Gallery" is at the top left and the Panel "Fields" at the top right. Gallery has a
      heading and a header row: normal, hovered, pressed, disabled.
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
12    Fields panel, keyboard. The log has "Panel Fields ...: keyboard on_demand, it holds a text field"
      (the Panel writes no Keyboard key). Click the first TextInput ("hello"): a caret shows in it and
      the field's border is the primary colour while the pointer is over it. Type "abc": each key
      shows in the field and the Echo text (bottom right) reads "changed: 'helloa' -> 'helloab'" and
      so on, with "commit: 'b'" before it. Backspace and the arrow keys work. Press Enter: Echo reads
      "submit (Enter)". Click a TextEditor and press Enter: a new line, and Echo does not say submit.
13    Selection and paste. Drag across text with the pointer: it is highlighted. Ctrl+A in a field
      selects all; Ctrl+C then click another field and Ctrl+V: the text arrives and Echo reports it as
      "changed: ... -> ..." (a paste is one change). Ctrl+X cuts. Ctrl+V into the read-only and the
      disabled fields does nothing.
14    ONE input-method check (M4 Brief, A2): with an input method installed (fcitx5, ibus or a Plasma
      one; for example a Chinese or Japanese one, or a compose key sequence for a dead key), type in
      the first TextInput: the preview (preedit) shows at the caret with the candidate window beside
      it, and committing it inserts the text; Echo shows "commit: '...'" and "changed: ...". Say
      which input method you used and what you saw.
15    The read-only field: click it, type, press Backspace: nothing changes and Echo does not move;
      Ctrl+A and Ctrl+C work (paste elsewhere to see it). The password field shows bullets; select all and
      copy, then paste in another field: nothing new is pasted. The placeholder row shows "Search..." in
      the primary colour (the part ::placeholder) until you type, and again when you delete it.
16    The limited field (Max_Length 8): type ten letters: it stops at eight, and Echo shows changes
      only up to eight characters.
17    The disabled fields (a TextInput and a TextEditor, faint at half opacity): point at one (no
      hover look), click it and type: no caret, no text, nothing in Echo. If you have clicked another
      field first, that one keeps the keyboard; the disabled one never takes it.
18    The three long lines. SCROLL: click it, press End: the text scrolls to keep the caret visible; click
      another field: it shows its start again. ELLIPSIS: unfocused it ends with "..."; click it: the
      line is whole and scrolls with the caret; click away: "..." again. CLIP: unfocused it is cut at
      the edge; click it and press End: the caret goes past the edge and the text does not scroll
      (that is what CLIP is for).
19    The TextEditors. WORD wraps the paragraph at the box width, by word; type more than 4 lines:
      the box scrolls down to the caret. NONE keeps the paragraph on one line and scrolls sideways.
      Up and Down in a wrapped line move by LOGICAL line, not by wrapped line (a known tre limit, expected).
20    Switch Plasma's colour scheme light to dark and back with the Panel open: the fields' fill, outline,
      text, caret, selection and the hints follow it at once, and what you typed is still there. The
      log shows no ERROR or WARNING line for the whole run.
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_gallery(cfg: Path) -> None:
    """The gallery's config directory (shell file, the stylesheets, the three test modules, settings)."""
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BODY)
    (cfg / "settings.tdl").write_text(SETTINGS)
    (cfg / "Stylesheets").mkdir()
    (cfg / "Stylesheets" / "Gallery_Stylesheet.tdl").write_text(STYLESHEET)
    (cfg / "Stylesheets" / "Gallery_Fields_Stylesheet.tdl").write_text(FIELDS_STYLESHEET)
    for name, tdl, py in (
        ("Meter", METER_TDL, METER_PY),
        ("Pad", PAD_TDL, PAD_PY),
        ("Echo", ECHO_TDL, ECHO_PY),
    ):
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
