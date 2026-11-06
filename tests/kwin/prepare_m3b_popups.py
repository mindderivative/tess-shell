"""Regenerate the M3b Popup and tooltip KWin checklist setup in /tmp/tess-kwin-m3b/popups (not
collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m3b_popups.py``. It writes one scratch
config (a Bar at the top and a Bar at the bottom, each with buttons that open Popups, a Clock with
``locale: de_DE`` and a tooltip) and two scripts: ``run-popups.sh`` and ``check-popups.sh``.
Nothing is started. It does not touch what ``prepare_m3b.py`` writes.
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

BUTTON_TDL = """---
TDL: 0.1
Name: Menu_Button
---

Module {
    Params {
        # the Name of the Popup a click opens
        popup { Type: string, Default: Menu }
        label { Type: string, Default: "Menu" }
    }
    FlexBox {
        Padding: 4
        Style { Background: $color.primary, Corner_Radius: 4 }
        On_Click: open_it
        Children {
            Text { Text: {{ params.label }}, Font_Size: 13, Foreground: $color.on_primary }
        }
    }
}
"""

BUTTON_PY = """from tess_shell import Module, action


class Menu_Button(Module):
    @action
    def open_it(self, event):
        # the shell supplies the calling use: this opens the Popup beside the button clicked
        use = self.ctx.uses[event.use]
        self.ctx.popup(use.params["popup"])
"""


def row(text: str, close: bool = False) -> str:
    click = ", On_Click: Close" if close else ""
    return (
        f"FlexBox {{ Padding: [0, 3, 0, 3]{click}, Children {{ "
        f'Text {{ Text: "{text}", Width: AUTO, Height: AUTO, Font_Size: 14, '
        "Foreground: $color.on_surface } } }"
    )


def popup(name: str, extra: str, rows: list[str], style: str) -> str:
    body = " ".join(rows)
    return f"""            Popup {{
                Name: {name}
{extra}
                Style {{ Background: $color.surface_raised, Corner_Radius: 8, {style} }}
                Children {{
                    FlexBox {{
                        Name: {name}_Card
                        Flex: VERTICAL
                        Padding: 12
                        Spacing: 4
                        Children {{ {body} }}
                    }}
                }}
            }}
"""


POPUPS = (
    popup(
        "Menu",
        "                Gap: 4",
        [row("Menu: a shadow, Gap 4"), row("click: Close", close=True)],
        "Elevation: 40%",
    )
    + popup("Plain", "                Gap: 4", [row("Plain: no shadow, Gap 4")], "Border_Width: 0")
    + popup(
        "Menu_End",
        "                Alignment: END\n                Gap: 8",
        [row("Alignment END, Gap 8"), row("click: Close", close=True)],
        "Elevation: 40%",
    )
    + popup(
        "Tall",
        "                Max_Height: 150",
        [row(f"Row {i}") for i in range(1, 11)],
        "Elevation: 20%",
    )
    + popup(
        "Hint",
        "                Tooltip: true\n                Alignment: CENTER\n                Gap: 6\n"
        "                Enter_Delay: 400\n                Exit_Delay: 300",
        [row("A tooltip: no focus")],
        "Elevation: 20%",
    )
)


def button(name: str, label: str, popup_name: str, extra: str = "") -> str:
    return f'Menu_Button {{ Name: {name}, popup: {popup_name}, label: "{label}"{extra} }}'


def bar_children(side: str) -> str:
    return "\n".join(
        [
            button(f"{side}_Menu", "Menu", "Menu"),
            button(f"{side}_Plain", "Plain", "Plain"),
            button(f"{side}_Tall", "Tall", "Tall"),
            button(f"{side}_Hint", "Hover me", "Menu", ", Tooltip: Hint"),
            f'Clock {{ Name: {side}_Clock, format: "%H:%M", locale: de_DE }}',
            "Spacer { }",
            button(f"{side}_End", "Right edge", "Menu_End"),
        ]
    )


def bar(name: str, edge: str, children: str) -> str:
    return f"""            Bar {{
                Name: {name}
                Edge: {edge}
                Width: EXPAND
                Height: 36
                Style {{ Fill: $color.surface }}
                Children {{
                    FlexBox {{
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 8
                        Padding: 4
                        Children {{
{children}
                        }}
                    }}
                }}
            }}
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    cfg = ROOT / "popups"
    shutil.rmtree(cfg, ignore_errors=True)
    start = BODY.index("            Bar {")
    end = BODY.index("        }\n    }\n}\n", start)
    body = (
        BODY[:start]
        + POPUPS
        + bar("Top_Bar", "TOP", bar_children("Top"))
        + bar("Bottom_Bar", "BOTTOM", bar_children("Bottom"))
        + BODY[end:]
    )
    write_example(cfg, body)
    (cfg / "settings.tdl").write_text(SETTINGS)
    module = cfg / "Modules" / "Menu_Button"
    module.mkdir(parents=True)
    (module / "Menu_Button_Module.tdl").write_text(BUTTON_TDL)
    (module / "Menu_Button_Module.py").write_text(BUTTON_PY)
    script(
        "run-popups.sh",
        "# Popups and tooltips.  Usage: run-popups.sh   (Ctrl+C stops it)\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3b/state\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3b/popups\n",
    )
    script(
        "check-popups.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3b/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3b/popups\n",
    )
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
