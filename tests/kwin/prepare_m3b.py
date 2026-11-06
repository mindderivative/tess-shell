"""Regenerate the M3b Panel KWin checklist setup in /tmp/tess-kwin-m3b (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m3b.py``. It writes one scratch config
(``panels``: a Bar with two buttons, an OSD, a launcher and a desktop widget) and the short
scripts the M3 Build Log checklist names. Nothing is started.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import BODY, write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m3b")
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
LABEL = 'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }'
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default] }\n}\n"
)

# Two buttons in the Bar: a box takes the click (a Text takes none), the Text sits inside it.
BUTTONS = """FlexBox {
    Name: Launcher_Button
    Padding: 4
    Style { Background: $color.primary, Corner_Radius: 4 }
    On_Click { Action: Toggle, Target: Launcher }
    Children { Text { Text: "Launcher", Font_Size: 13, Foreground: $color.on_primary } }
}
FlexBox {
    Name: Osd_Button
    Padding: 4
    Style { Background: $color.primary, Corner_Radius: 4 }
    On_Click { Action: Show, Target: Volume_OSD }
    Children { Text { Text: "OSD", Font_Size: 13, Foreground: $color.on_primary } }
}
FlexBox {
    Name: Calendar_Button
    Padding: 4
    Style { Background: $color.primary, Corner_Radius: 4 }
    On_Click { Action: Toggle, Target: Calendar }
    Children { Text { Text: "Calendar", Font_Size: 13, Foreground: $color.on_primary } }
}
FlexBox {
    Name: Note_Button
    Padding: 4
    Style { Background: $color.primary, Corner_Radius: 4 }
    On_Click { Action: Toggle, Target: Note }
    Children { Text { Text: "Note", Font_Size: 13, Foreground: $color.on_primary } }
}
Clock { Name: Clock_One }"""

PANELS = """
            Panel {
                Name: Volume_OSD
                Layer: OVERLAY
                Anchor: [BOTTOM]
                Inset: [0, 0, 0, 80]
                Width: 260
                Height: 60
                Input_Region: []
                Hide_After: 2000
                Style { Background: $color.surface_raised, Corner_Radius: 12, Elevation: 40% }
                Children {
                    FlexBox {
                        Padding: 16
                        Children { Text { Text: "Volume 40", Font_Size: 18, Foreground: $color.on_surface } }
                    }
                }
            }
            Panel {
                Name: Launcher
                Layer: OVERLAY
                Keyboard: EXCLUSIVE
                Width: 600
                Height: 300
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 16, Elevation: 60% }
                Children {
                    FlexBox {
                        Padding: 24
                        Children { Text { Text: "Launcher: press Escape to close", Font_Size: 18, Foreground: $color.on_surface } }
                    }
                }
            }
            Panel {
                Name: Calendar
                Layer: OVERLAY
                Width: 200
                Height: 120
                Attach_To: Clock_One
                Attach: BOTTOM
                Gap: 8
                Alignment: CENTER
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 20% }
                Children {
                    FlexBox {
                        Padding: 12
                        Children { Text { Text: "Under the clock", Font_Size: 14, Foreground: $color.on_surface } }
                    }
                }
            }
            Panel {
                Name: Note
                Layer: OVERLAY
                Width: 140
                Height: 60
                Attach_To: Calendar
                Attach: RIGHT
                Gap: 6
                Alignment: START
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 20% }
                Children {
                    FlexBox {
                        Padding: 12
                        Children { Text { Text: "Beside it", Font_Size: 14, Foreground: $color.on_surface } }
                    }
                }
            }
            Panel {
                Name: Clock_Widget
                Layer: BOTTOM
                Anchor: [TOP, LEFT]
                Inset: [60, 120, 0, 0]
                Width: 220
                Height: 90
                Style { Background: $color.surface_raised, Corner_Radius: 12, Elevation: 30% }
                Children {
                    FlexBox {
                        Padding: 16
                        Children { Text { Text: "Desktop widget", Font_Size: 16, Foreground: $color.on_surface } }
                    }
                }
            }
"""


def btn(name: str, label: str, action: str, target: str) -> str:
    return f"""FlexBox {{
    Name: {name}
    Padding: 4
    Style {{ Background: $color.primary, Corner_Radius: 4 }}
    On_Click {{ Action: {action}, Target: {target} }}
    Children {{ Text {{ Text: "{label}", Font_Size: 13, Foreground: $color.on_primary }} }}
}}"""


MOTION_BUTTONS = "\n".join(
    [
        btn("Drawer_Button", "Drawer", "Toggle", "Drawer"),
        btn("Fade_Button", "Fade", "Toggle", "Fader"),
        btn("Side_Button", "Side", "Toggle", "Side_Slide"),
        btn("Quick_Button", "Quick", "Toggle", "Quick"),
    ]
)


def card(name: str, text: str, extra: str, width: int = 220, height: int = 70) -> str:
    return f"""            Panel {{
                Name: {name}
                Layer: OVERLAY
                Width: {width}
                Height: {height}
{extra}
                Style {{ Background: $color.surface_raised, Corner_Radius: 10, Elevation: 20% }}
                Children {{
                    FlexBox {{
                        Padding: 14
                        Children {{ Text {{ Text: "{text}", Font_Size: 14, Foreground: $color.on_surface }} }}
                    }}
                }}
            }}
"""


def dot(name: str, colour: str, inset: str) -> str:
    return f"""            Panel {{
                Name: {name}
                Layer: OVERLAY
                Anchor: [TOP, RIGHT]
                Inset: [0, {inset}, 24, 0]
                Width: 120
                Height: 30
                Input_Region: []
                Visible: false
                Style {{ Background: "{colour}", Corner_Radius: 6 }}
                Children {{ FlexBox {{ Padding: 6 }} }}
            }}
"""


MOTION = (
    card(
        "Drawer",
        "Drawer: slides down from the Bar",
        "                Attach_To: Top_Bar\n                Attach: BOTTOM\n                Alignment: START\n"
        "                Gap: 8\n                Visible: false\n"
        "                Animation { Type: SLIDE, Duration: 300 }\n"
        "                On_Open { Action: Show, Target: Opening }\n"
        "                On_Visible { Action: Show, Target: Visible_Now }\n"
        "                On_Close { Action: Hide, Target: Opening }\n"
        "                On_Hidden { Action: Hide, Target: Visible_Now }",
    )
    + dot("Opening", "#d65a5a", "60")
    + dot("Visible_Now", "#5ab86e", "100")
    + card(
        "Fader",
        "Fader: fades in and out",
        "                Anchor: [TOP, RIGHT]\n                Inset: [0, 160, 24, 0]\n"
        "                Visible: false\n                Animation { Type: FADE, Duration: 400 }",
    )
    + card(
        "Side_Slide",
        "Side: slides in from the left edge",
        "                Anchor: [LEFT]\n                Inset: [0, 0, 0, 0]\n"
        "                Visible: false\n                Animation { Type: SLIDE, Duration: 300 }",
        height=200,
    )
    + card(
        "Quick",
        "Quick: no animation",
        "                Anchor: [BOTTOM]\n                Inset: [0, 0, 0, 60]\n"
        "                Visible: false",
    )
    + """            Panel {
                Name: Pin
                Layer: BOTTOM
                Width: 200
                Height: 80
                Movable: true
                Style { Background: $color.surface_raised, Corner_Radius: 12, Elevation: 30% }
                Children {
                    FlexBox {
                        Padding: 14
                        Children { Text { Text: "Drag me (I remember where)", Font_Size: 14, Foreground: $color.on_surface } }
                    }
                }
            }
"""
)


HOVER = """---
TDL: 0.1
Name: Hover
---
Stylesheet {
    Rule { Selector: "#Drawer_Button:hovered", Background: $color.accent }
    Rule {
        Selector: "#Drawer_Button:pressed"
        Background: $color.warning
        Border_Width: 2
        Border_Color: $color.on_surface
    }
}
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    cfg = ROOT / "panels"
    shutil.rmtree(cfg, ignore_errors=True)
    body = BODY.replace(LABEL, BUTTONS).replace(
        'Style { Fill: "#1f1f1f" }', "Style { Fill: $color.surface }"
    )
    body = body.replace("            Bar {", PANELS + "            Bar {", 1)
    write_example(cfg, body)
    (cfg / "settings.tdl").write_text(SETTINGS)
    keep = ROOT / "panels_keep"  # the same config, with the first hide route (D44)
    shutil.rmtree(keep, ignore_errors=True)
    shutil.copytree(cfg, keep)
    (keep / "settings.tdl").write_text(
        SETTINGS.replace(
            "  Appearance { Stylesheets: [Default] }\n",
            "  Appearance { Stylesheets: [Default] }\n  Debug { Panel_Hide: KEEP }\n",
        )
    )
    motion = ROOT / "motion"
    shutil.rmtree(motion, ignore_errors=True)
    mbody = BODY.replace(LABEL, MOTION_BUTTONS).replace(
        'Style { Fill: "#1f1f1f" }', "Style { Fill: $color.surface }"
    )
    mbody = mbody.replace("            Bar {", MOTION + "            Bar {", 1)
    write_example(motion, mbody)
    (motion / "settings.tdl").write_text(
        SETTINGS.replace("Stylesheets: [Default]", "Stylesheets: [Default, Hover]")
    )
    (motion / "Stylesheets").mkdir()
    (motion / "Stylesheets" / "Hover_Stylesheet.tdl").write_text(HOVER)
    script(
        "run-motion.sh",
        "# Animation, Panel events and Movable.  Usage: run-motion.sh   (Ctrl+C stops it)\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3b/state\n"
        "# the saved position of the Pin lives in /tmp/tess-kwin-m3b/motion/registry.json;\n"
        "# delete that file to forget it\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3b/motion\n",
    )
    script(
        "run.sh",
        "# Usage: run.sh    (Ctrl+C or kill -TERM stops it)\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3b/state   # keeps UID backups out of yours\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3b/panels\n",
    )
    script(
        "run-keep.sh",
        "# The first hide route: a hidden Panel keeps its surface (Debug { Panel_Hide: KEEP }).\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3b/state\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3b/panels_keep\n",
    )
    script(
        "probe-hide.sh",
        "# Which way of hiding a layer surface repaints? Click a button to hide a card, again to\n"
        "# show it; each toggle prints a frame time or NO FRAME. Ctrl+C stops it.\n"
        f"exec {BIN}/python {REPO}/tests/kwin/probe_hide.py\n",
    )
    script(
        "check.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3b/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3b/panels\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3b/panels_keep\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3b/motion\n",
    )
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
