"""Regenerate the M6a focus KWin check in /tmp/tess-kwin-m6a (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m6a_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m6a`` and starts nothing. The shell file has a Bar with
``Keyboard: ON_DEMAND`` (three Buttons with ``Tab_Index`` in a different order from the page, a
Toggle and a Button that is disabled), a Panel with a TextInput and a Checkbox. Every colour is a
theme token, so it follows Plasma's light and dark.

* ``run.sh``: the shell on your real desktop (it reads only the session bus for light and dark).
* ``check.sh``: ``tesserae-shell check`` on the config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m6a/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m6a")
CFG = ROOT / "gallery"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)

BODY = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 48
                Keyboard: ON_DEMAND
                Tab_Index: 1
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 12
                        Padding: [12, 8, 12, 8]
                        Align_Items: CENTER
                        Children {
                            Button { Name: First, Text: "First", Tab_Index: 3 }
                            Button { Name: Second, Text: "Second", Tab_Index: 1 }
                            Button { Name: Third, Text: "Third", Tab_Index: 2 }
                            Toggle { Label: "Switch" }
                            Button { Text: "Disabled", Enabled: false }
                            Button { Text: "Fourth", Tab_Index: 4 }
                        }
                    }
                }
            }
            Panel {
                Name: Form
                Anchor: TOP
                Inset: [0, 80, 0, 0]
                Width: 360
                Height: 140
                Keyboard: ON_DEMAND
                Tab_Index: 2
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Spacing: 12
                        Padding: 16
                        Children {
                            TextInput { Placeholder: "Type here", Width: 300 }
                            Checkbox { Label: "Agree" }
                        }
                    }
                }
            }
        }
    }
}
"""

CHECKLIST = """M6a Focus: one list, every line to run.  Do it in light and in dark (Plasma's colour
scheme; the ring is the theme's Primary colour, 2 px, outside the block).  Start with
/tmp/tess-kwin-m6a/run.sh.  The Bar has First, Second, Third, a switch, a disabled button and Fourth;
below it a Panel with a text field and a checkbox.

 1  Click the empty part of the Bar, then press Tab: the ring appears on Second, then Third, then
    First, then Fourth (the order of their Tab_Index 1, 2, 3, 4), not on the switch and not on Disabled
    (they have none: they come after the numbered ones, the switch last; Disabled is never reached).
 2  Shift+Tab walks the same ring backwards, and wraps from the first to the last.
 3  CLICK a button with the mouse: it has the keyboard focus (Enter or Space runs it) but NO ring.
    Press Tab: the ring appears on the next one.
 4  The ring does not move anything: the buttons stay where they were when it appears and goes.
 5  Click the text field in the Panel and type: the text appears and the field's border has no ring
    while you click; Shift+Tab off it and Tab back onto it: the ring shows around the field.
 6  Tab inside the Panel does not leave it (the focus goes through the field and the checkbox and
    back); Tab in the Bar does not go into the Panel (one surface is one order).
 7  Disabled shows no ring and Tab skips it.
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_gallery(cfg: Path, body: str = BODY) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, body)
    (cfg / "settings.tdl").write_text(SETTINGS)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_gallery(CFG)
    (ROOT / "checklist.txt").write_text(CHECKLIST)
    state = f"export XDG_STATE_HOME={ROOT}/state\n"
    script("run.sh", state + f"exec {BIN}/tesserae-shell run --config-dir {CFG}\n")
    script("check.sh", state + f"{BIN}/tesserae-shell check --config-dir {CFG}\n")
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
