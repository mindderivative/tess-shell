"""The preview model of a fixed configuration, written out as JSON for the golden test
(``tests/test_preview.py``). Not collected by pytest. ``python -m tests.preview_golden`` rewrites
``tests/fixtures/preview_golden.json``: only do that for a deliberate change of the model's shape
(``PREVIEW_VERSION``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tess_shell.preview import VirtualOutput, preview
from tests.shell_samples import BODY, HEADER, SVG

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "preview_golden.json"
CONFIG = Path("/preview-config")  # a folder that does not exist: the files are in memory

RICH = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Children { FlexBox { Width: EXPAND, Children { Clock { Name: Clock } } } }
            }
            Panel {
                Name: Dock
                Layer: TOP
                Anchor: [BOTTOM]
                Inset: [0, 0, 0, 12]
                Width: 400
                Height: 56
                Children { FlexBox { Width: EXPAND } }
            }
            Frame {
                Name: Ring
                Thickness: [4, 0, 4, 4]
                Inner_Radius: 12
                Inner_Border { Width: 2, Color: "#4682b4" }
            }
            Popup { Name: Tip, Attach: BOTTOM, Children { Text { Text: "hello" } } }
        }
    }
}
"""


def example() -> dict[Path, str]:
    return {
        CONFIG / "Shells" / "Main_Shell.tdl": HEADER + BODY,
        CONFIG / "Shells" / "dot.svg": SVG,
    }


def rich() -> dict[Path, str]:
    return {CONFIG / "Shells" / "Main_Shell.tdl": HEADER + RICH}


def model(files: dict[Path, str]) -> dict:  # type: ignore[type-arg]
    return preview(CONFIG, files, [VirtualOutput("Preview-1", 1920, 1080)]).to_dict()


def main() -> int:
    data = {"example": model(example()), "rich": model(rich())}
    GOLDEN.write_text(json.dumps(data, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
