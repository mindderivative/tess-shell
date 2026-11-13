"""Regenerate the M4c interactive widgets gallery and its KWin checklist in /tmp/tess-kwin-m4c-widgets
(not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m4c_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m4c-widgets`` and starts nothing. Two floating Panels show
every M4c widget in each state it has: Button (text, icon and text, icon at the end, icon only,
disabled), Toggle and Checkbox (off, on, disabled off, disabled on), Slider (horizontal, stepped,
disabled, vertical), a List with a selected entry, and a Menu opened from a Button with a
separator, a disabled item, an item that reads ``caller.data`` and two levels of submenu. A ``Probe``
test module prints the last event the widgets raised. Colours are theme tokens (the Default
stylesheet), so the gallery follows Plasma's light and dark. The state directory is
``/tmp/tess-kwin-m4c-widgets/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m4c-widgets")
CFG = ROOT / "gallery"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)

PROBE_TDL = """---
TDL: 0.1
Name: Probe
---

# A test module: the last event a widget raised, and the values it carries.
Module {
    FlexBox {
        Name: Root
        Flex: VERTICAL
        Spacing: 4
        Width: 330
        Children {
            Text { Text: "last event", Width: AUTO, Height: AUTO, Font_Size: 12, Foreground: $color.on_surface_muted }
            Text { Name: Last, Text: {{ last }}, Width: 330, Height: AUTO, Font_Size: 13 }
            Text { Name: Count, Text: {{ count }}, Width: AUTO, Height: AUTO, Font_Size: 12, Foreground: $color.on_surface_muted }
        }
    }
}
"""

PROBE_PY = """from tess_shell import Module, action


class Probe(Module):
    def start(self):
        self.n = 0
        self.ctx.send("last", "nothing yet: press, flip, drag, choose")
        self.ctx.send("count", "0 events")

    def shown(self, what):
        self.n += 1
        self.ctx.log.info(f"Probe: {what}")
        self.ctx.send("last", what)
        self.ctx.send("count", f"{self.n} events")

    @action
    def changed(self, event):
        self.shown(f"{event.args['Who']}: {event.old!r} -> {event.new!r}")

    @action
    def released(self, event):
        self.shown(f"{event.args['Who']} released at {event.value!r} (pressed at {event.old!r})")

    @action
    def clicked(self, event):
        extra = {k: v for k, v in event.args.items() if k != "Who"}
        self.shown(f"{event.args['Who']} clicked" + (f" {extra}" if extra else ""))
"""

HEAD = 'Text {{ Text: "{t}", Width: AUTO, Height: AUTO, Font_Size: 15, Font_Weight: 500 }}'


def changed(who: str) -> str:
    return f'On_Changed {{ Action: Call, Target: "Probe.changed", Who: "{who}" }}'


def released(who: str) -> str:
    return f'On_Released {{ Action: Call, Target: "Probe.released", Who: "{who}" }}'


def clicked(who: str, **args: str) -> str:
    extra = "".join(f', {k}: "{v}"' for k, v in args.items())
    return f'On_Click {{ Action: Call, Target: "Probe.clicked", Who: "{who}"{extra} }}'


def row(caption: str, *items: str) -> str:
    cap = (
        f'Text {{ Text: "{caption}", Width: 84, Height: AUTO, Font_Size: 12, '
        "Foreground: $color.on_surface_muted }"
    )
    return f"FlexBox {{ Spacing: 12, Align_Items: CENTER, Children {{ {cap} {' '.join(items)} }} }}"


LEFT_ROWS = [
    HEAD.format(t="M4c controls"),
    row(
        "Button",
        f'Button {{ Text: "Save", {clicked("Save")} }}',
        f'Button {{ Text: "Open", Icon: "mdi:home", {clicked("Open")} }}',
        f'Button {{ Text: "Next", Icon: "mdi:chevron-right", Icon_Position: END, {clicked("Next")} }}',
        f'Button {{ Icon: "mdi:account", Label: "Account", {clicked("Account")} }}',
        'Button { Text: "Off", Enabled: false }',
    ),
    row(
        "Toggle",
        f'Toggle {{ Label: "off", {changed("Toggle off")} }}',
        f'Toggle {{ Label: "on", Checked: true, {changed("Toggle on")} }}',
        'Toggle { Label: "disabled", Enabled: false }',
        'Toggle { Label: "disabled on", Checked: true, Enabled: false }',
    ),
    row(
        "Checkbox",
        f'Checkbox {{ Text: "Remember", {changed("Checkbox")} }}',
        f'Checkbox {{ Text: "Checked", Checked: true, {changed("Checkbox 2")} }}',
    ),
    row(
        "",
        'Checkbox { Text: "Disabled", Enabled: false }',
        'Checkbox { Text: "Disabled on", Checked: true, Enabled: false }',
    ),
    row(
        "Slider",
        f'Slider {{ Value: 30, Label: "Volume", {changed("Volume")} {released("Volume")} }}',
        f'Slider {{ Value: 50, Step: 10, Width: 120, Label: "Stepped", {changed("Step 10")} {released("Step 10")} }}',
        'Slider { Value: 70, Width: 120, Enabled: false, Label: "Disabled" }',
    ),
    row(
        "Vertical",
        f'Slider {{ Orientation: VERTICAL, Value: 40, Height: 90, Label: "Upright", {changed("Upright")} }}',
        'Slider { Orientation: VERTICAL, Value: 60, Height: 90, Enabled: false, Label: "Upright off" }',
    ),
    "Probe { }",
]

ENTRIES = " ".join(
    f"FlexBox {{ Class: list_item, Key: k{i}, Height: 28, Children {{ "
    f'Text {{ Text: "Entry number {i}", Width: AUTO, Height: AUTO }} }} }}'
    for i in range(1, 11)
)

RIGHT_ROWS = [
    HEAD.format(t="M4c list and menu"),
    row(
        "List",
        f'List {{ Width: 200, Height: 150, Selected: "k2", Label: "Entries", {changed("List")}, '
        f"Children {{ {ENTRIES} }} }}",
        'List { Width: 130, Height: 150, Selection: NONE, Label: "Plain", Children { '
        'FlexBox { Class: list_item, Key: a, Height: 28, Children { Text { Text: "No choice", Width: AUTO, Height: AUTO } } } '
        'FlexBox { Class: list_item, Key: b, Height: 28, Children { Text { Text: "Selection: NONE", Width: AUTO, Height: AUTO } } } } }',
    ),
    row(
        "Menu",
        'Button { Text: "File", Icon: "mdi:menu-down", Icon_Position: END, '
        'On_Click { Action: Show, Target: File_Menu, Data { Title: "File" } } }',
        'Button { Text: "Edit", Icon: "mdi:menu-down", Icon_Position: END, '
        "On_Click { Action: Toggle, Target: Edit_Menu } }",
    ),
]

POPUP_STYLE = "Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 20% }"


def action_item(text: str, **keys: str) -> str:
    extra = "".join(f", {k}: {v}" for k, v in keys.items())
    return f'MenuItem {{ Text: "{text}"{extra}, {clicked(text)} }}'


FILE_MENU = f"""Popup {{
    Name: File_Menu
    Gap: 4
    {POPUP_STYLE}
    Children {{
        Menu {{
            Label: "File"
            Children {{
                MenuItem {{ Text: {{{{ "Menu for " + caller.data.Title }}}}, Enabled: false }}
                {action_item("New", Icon='"mdi:home"', Shortcut_Text='"Ctrl+N"')}
                {action_item("Open", Shortcut_Text='"Ctrl+O"')}
                MenuItem {{ Separator: true }}
                MenuItem {{ Text: "Share", Submenu: Share_Menu }}
                MenuItem {{ Text: "Print", Enabled: false, {clicked("Print")} }}
                MenuItem {{ Separator: true }}
                {action_item("Quit")}
            }}
        }}
    }}
}}"""
SHARE_MENU = f"""Popup {{
    Name: Share_Menu
    Gap: 4
    {POPUP_STYLE}
    Children {{
        Menu {{
            Children {{
                {action_item("Mail")}
                {action_item("Chat")}
                MenuItem {{ Text: "More", Submenu: More_Menu }}
            }}
        }}
    }}
}}"""
MORE_MENU = f"""Popup {{
    Name: More_Menu
    Gap: 4
    {POPUP_STYLE}
    Children {{
        Menu {{
            Children {{
                {action_item("Deep one")}
                {action_item("Deep two")}
            }}
        }}
    }}
}}"""
EDIT_MENU = f"""Popup {{
    Name: Edit_Menu
    Gap: 4
    {POPUP_STYLE}
    Children {{
        Menu {{
            Children {{
                {action_item("Cut", Shortcut_Text='"Ctrl+X"')}
                {action_item("Copy", Shortcut_Text='"Ctrl+C"')}
                {action_item("Paste", Shortcut_Text='"Ctrl+V"')}
            }}
        }}
    }}
}}"""

LEFT = (
    "Panel { Name: Controls, Layer: TOP, Anchor: [TOP, LEFT], Inset: [24, 24, 0, 0], Width: 660, "
    "Height: 540, Style { Background: $color.surface, Corner_Radius: 12, Elevation: 30% }, "
    "Children { FlexBox { Flex: VERTICAL, Padding: 16, Spacing: 12, Children { "
    + " ".join(LEFT_ROWS)
    + " } } } }"
)
RIGHT = (
    "Panel { Name: Lists, Layer: TOP, Anchor: [TOP, LEFT], Inset: [704, 24, 0, 0], Width: 480, "
    "Height: 330, Style { Background: $color.surface, Corner_Radius: 12, Elevation: 30% }, "
    "Children { FlexBox { Flex: VERTICAL, Padding: 16, Spacing: 12, Children { "
    + " ".join(RIGHT_ROWS)
    + " } } } }"
)
BODY = (
    f"Shell {{ Monitor {{ Name: Main, Index: 0, Children {{ {LEFT} {RIGHT} "
    f"{FILE_MENU} {SHARE_MENU} {MORE_MENU} {EDIT_MENU} }} }} }}\n"
)

CHECKLIST = """M4c interactive widgets gallery: one look each.  Start it with /tmp/tess-kwin-m4c-widgets/run.sh.
Do these in light and in dark (Plasma's colour scheme; every colour is a theme token). Two Panels:
"M4c controls" at the left, "M4c list and menu" to its right.  The last line of the Probe says what
each widget raised.

 1  Button: "Save"; "Open" with a house icon before the text; "Next" with a chevron after the text;
    an icon-only account button; a faint "Off". Point at "Save": its border turns blue; hold the
    button on it: the fill is greyer and the border stays blue; release: the Probe says
    "Save clicked". Press on "Save", move out and release outside: no click is reported. The faint
    "Off" does nothing when pressed.
 2  Toggle: four switches, off, on (blue track, thumb at the right), faint off, faint on. Click the
    first: the thumb slides right in about 0.2 s and the track turns blue, the Probe says
    "Toggle off: False -> True" once; click again: it slides back.  The faint ones do not react.
 3  Checkbox: "Remember" (empty box), "Checked" (blue box with a white check mark), "Disabled" and
    "Disabled on" (both faint). Click "Remember" on the box and then on its label: it flips both
    times and the Probe says "Checkbox: False -> True", then "True -> False".
 4  Slider: a 160 px slider at 30 (blue fill, round handle). Press on the track away from the handle:
    the handle jumps there and the Probe says "Volume: 30 -> ..." once. Drag the handle left and
    right: it follows the pointer, also when the pointer leaves the slider sideways while the
    button is held; the value never leaves 0 to 100. The second slider moves in steps of 10 (50 -> 60 ...).
    While you drag, the Probe shows a new "Volume: a -> b" for each value; when you let go it adds ONE
    line "Volume released at <final value> (pressed at <value before the press>)". Let go with the
    pointer well outside the slider (above it, below it, outside the Panel): that line still comes,
    once. A click on the track gives one "Volume: ..." line and then one "released" line; a click on
    the handle without moving gives only the "released" line, with the same two values.
    The handle shows a grey ring when pointed at and a thicker white ring while pressed. The third
    is faint with a grey handle and does not react.
 5  Vertical sliders: the first is at 40 (the fill is from the bottom); dragging up raises it to 100
    at the top. The second is faint.
 6  List: ten entries in a 150 px box, "Entry number 2" outlined in blue (selected). Turn the
    mouse wheel over the list: it scrolls and stops at the ends. Click "Entry number 5": the blue
    outline moves there and the Probe says "List: 'k2' -> 'k5'"; click it again: nothing new. Point at an
    entry: its background lightens. The second list ("Selection: NONE") chooses nothing.
 7  Menu: press "File": a menu opens under the button: a faint "Menu for File" (read from
    caller.data), "New" with a house and "Ctrl+N" at the end, "Open", a rule, "Share" with an arrow, a
    faint "Print", a rule, "Quit". Point at an item: its row is lit.
 8  Point at "Share" and rest: after a quarter of a second a submenu opens to its right ("Mail",
    "Chat", "More" with an arrow); rest on "More": a third menu opens. Rest the pointer on "New" for
    a third of a second: the submenu closes.  A click on "Share" opens it at once.
 9  Click "Chat" in the submenu: the Probe says "Chat clicked" and every menu closes. Press "File"
    again, then press anywhere outside: every menu closes. Press "File", then "Edit": the first
    closes and the second opens (one at a time).
10  Switch Plasma light to dark: everything follows. The log has no ERROR.
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_gallery(cfg: Path) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BODY)
    (cfg / "settings.tdl").write_text(SETTINGS)
    folder = cfg / "Modules" / "Probe"
    folder.mkdir(parents=True)
    (folder / "Probe_Module.tdl").write_text(PROBE_TDL)
    (folder / "Probe_Module.py").write_text(PROBE_PY)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_gallery(CFG)
    (ROOT / "checklist-m4c.txt").write_text(CHECKLIST)
    script(
        "run.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m4c-widgets/state\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m4c-widgets/gallery\n",
    )
    script(
        "check.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m4c-widgets/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m4c-widgets/gallery\n",
    )
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
