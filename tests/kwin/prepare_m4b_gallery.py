"""Regenerate the M4b display widgets gallery and its KWin checklist in /tmp/tess-kwin-m4b (not
collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m4b_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m4b`` and starts nothing. One floating Panel shows every
display widget of M4b in each state it has: Label, TextBox, ProgressBar, Badge, Marquee text, Icon,
Image (a png, a jpeg, a gif, a webp, a bad file), the Circle, Ring and Path blocks, an Expander
opened by a ``Toggler`` test module, a string Tooltip and a Spacer. Colours are theme tokens (the
Default stylesheet), so the gallery follows Plasma's light and dark. The state directory is
``/tmp/tess-kwin-m4b/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m4b")
CFG = ROOT / "gallery"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
FIX = REPO / "tests" / "fixtures"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)

TOGGLER_TDL = """---
TDL: 0.1
Name: Toggler
---

# A test module: a pressed tile flips `open`, which an Expander follows (its Expanded param is a slot).
Module {
    FlexBox {
        Name: Root
        Flex: VERTICAL
        Spacing: 6
        Children {
            FlexBox {
                Name: Tile
                Width: 150
                Height: 30
                Align_Items: CENTER
                Justify_Content: CENTER
                Style { Background: $color.surface_raised, Border_Width: 1, Border_Color: $color.outline, Corner_Radius: 6 }
                On_Click: flip
                Children { Text { Text: "Open / close", Width: AUTO, Height: AUTO } }
            }
            Expander {
                Name: Fold
                Expanded: {{ open }}
                Children {
                    FlexBox {
                        Padding: 10
                        Style { Background: $color.surface_raised, Corner_Radius: 6 }
                        Children { Text { Text: "The content eases in and out", Width: AUTO, Height: AUTO } }
                    }
                }
            }
        }
    }
}
"""
TOGGLER_PY = """from tess_shell import Module, action


class Toggler(Module):
    def start(self):
        self.open = False
        self.ctx.send("open", False)

    @action
    def flip(self, event):
        self.open = not self.open
        self.ctx.send("open", self.open)
"""

LONG = "A long text that does not fit in its box, so it scrolls while it must"


def row(caption: str, *items: str) -> str:
    cap = (
        f'Text {{ Text: "{caption}", Width: 150, Height: AUTO, Font_Size: 12, '
        "Foreground: $color.on_surface_muted }"
    )
    return f"FlexBox {{ Spacing: 12, Align_Items: CENTER, Children {{ {cap} {' '.join(items)} }} }}"


ROWS = [
    'Text { Text: "M4b display widgets", Width: AUTO, Height: AUTO, Font_Size: 15, Font_Weight: 500 }',
    row("Label", 'Label { Text: "normal" }', 'Label { Text: "disabled", Enabled: false }',
        'Label { Text: "a clipped long label", Width: 70 }'),
    row("TextBox", 'TextBox { Text: "A text box wraps a long text by word at its width", Width: 180 }',
        'TextBox { Text: "Max_Lines 2: one two three four five six seven eight", Width: 120, Max_Lines: 2 }'),
    row("ProgressBar", "ProgressBar { Value: 30 }", "ProgressBar { Value: 75 }",
        "ProgressBar { Value: 75, Enabled: false }"),
    row("Badge", "Badge { Count: 3 }", "Badge { Count: 120 }", "Badge { Dot: true }",
        "Badge { Count: 0, Show_Zero: true }", "Badge { Count: 0 }"),
    row("Marquee text", f'Marquee_Text {{ Text: "{LONG}", Width: 140 }}',
        f'Marquee_Text {{ Text: "{LONG}", Width: 140, Loop: BOUNCE }}',
        f'Marquee_Text {{ Text: "{LONG}", Width: 140, Enabled: false }}',
        'Marquee_Text { Text: "fits", Width: 140 }'),
    row("Icon", 'Icon { Icon: "mdi:home", Size: 24 }', 'Icon { Icon: "mdi:account", Size: 32 }',
        'Icon { Icon: "mdi:home", Size: 24, Enabled: false }', 'Icon { Icon: "mdi:no-such-icon-here", Size: 24 }'),
    row("Image", *[f'Image {{ Source: "{FIX / n}", Width: 48, Height: 48, Fit: FILL }}'
                   for n in ("png.png", "jpeg.jpg", "gif.gif", "webp.webp")],
        f'Image {{ Source: "{FIX / "bad.png"}", Width: 48, Height: 48 }}',
        'Image { Placeholder: "#55657A", Width: 48, Height: 48 }'),
    row("Circle, Ring, Path", 'Circle { Diameter: 24, Fill: $color.primary }',
        'Ring { Diameter: 24, Border_Width: 3, Border_Color: $color.success }',
        'Path { Data: "M2,2 L22,2 L12,22 Z", View_Box: [0, 0, 24, 24], Width: 24, Height: 24, Fill: $color.warning }'),
    row("Tooltip", 'Label { Text: "hover me", Tooltip: "A one-line tooltip" }'),
    row("Spacer", "FlexBox { Width: 300, Height: 20, Align_Items: CENTER, Style { Border_Width: 1, Border_Color: $color.outline }, "
        "Children { Circle { Diameter: 12, Fill: $color.primary } Spacer { } Circle { Diameter: 12, Fill: $color.primary } } }"),
    row("Expander", "Toggler { }"),
]

PANEL = (
    "Panel { Name: Gallery, Layer: TOP, Anchor: [TOP, LEFT], Inset: [24, 24, 0, 0], Width: 760, "
    "Height: 640, Style { Background: $color.surface, Corner_Radius: 12, Elevation: 30% }, "
    "Children { FlexBox { Flex: VERTICAL, Padding: 16, Spacing: 10, Children { "
    + " ".join(ROWS)
    + " } } } }"
)
BODY = f"Shell {{ Monitor {{ Name: Main, Index: 0, Children {{ {PANEL} }} }} }}\n"

CHECKLIST = """M4b display widgets gallery: one look each.  Start it with /tmp/tess-kwin-m4b/run.sh.
Do these in light and in dark (Plasma's colour scheme; every colour is a theme token).

 1  Label: "normal", a faint "disabled", and a label cut at 70 px (clipped, no ellipsis).
 2  TextBox: wraps by word; the second one stops after 2 lines.
 3  ProgressBar: three bars, 30 %, 75 %, and a faint disabled one (pill ends).
 4  Badge: 3, 99+, a dot, a 0 that shows (Show_Zero) and one that shows nothing.
 5  Marquee text: the first and second scroll (RESTART jumps back, BOUNCE scrolls back) with a
    pause at each end; the disabled one is cut with "..." and does not move; "fits" is still.
    Point at the disabled one: a tooltip with the whole text opens after a short delay.
 6  Icon: a house, a person, a faint house, and the broken-image icon for the bad name.
 7  Image: a png, a jpeg, a gif (first frame), a webp (left red, right blue), the error image (grey
    square with a red cross) for the bad file, and a grey placeholder.
 8  Circle, Ring (3 px) and a Path triangle.
 9  Tooltip: point at "hover me": a one-line tooltip opens after 500 ms and closes after 200 ms.
10  Spacer: the two dots stay at the ends of the frame.
11  Expander: press "Open / close": the content grows and fades in together; press again while
    it moves: it turns round from where it is. At rest nothing moves.
12  Switch Plasma light to dark: everything follows. The log has no ERROR (one WARNING for the
    bad icon name and one for the bad image file).
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_gallery(cfg: Path) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BODY)
    (cfg / "settings.tdl").write_text(SETTINGS)
    folder = cfg / "Modules" / "Toggler"
    folder.mkdir(parents=True)
    (folder / "Toggler_Module.tdl").write_text(TOGGLER_TDL)
    (folder / "Toggler_Module.py").write_text(TOGGLER_PY)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_gallery(CFG)
    (ROOT / "checklist-m4b.txt").write_text(CHECKLIST)
    script(
        "run.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m4b/state\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m4b/gallery\n",
    )
    script(
        "check.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m4b/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m4b/gallery\n",
    )
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
