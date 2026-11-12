"""Regenerate the Battery icon bisect probe in /tmp/tess-kwin-m5b-dot (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5b_dotprobe.py``. It writes a scratch
config and two scripts under ``/tmp/tess-kwin-m5b-dot`` and starts nothing.

On the maintainer's KWin the Battery's icon is not drawn at ``low`` and ``critical`` (where the
icon is coloured and a dot sits beside it) and is drawn at every other level. A headless tree and a
private sway draw it. This is the same look with FIXED values and no module and no D-Bus: one Bar,
36 px high, that shows side by side, each labelled with a letter, the ``battery-10`` icon of the
shipped ``mdi`` set in the variants below. Say which letters show the icon.

* A: the icon alone, ``Foreground`` warning (amber).
* B: the icon and a ``Circle`` (Diameter 6, warning) in a horizontal FlexBox, Spacing 4: the look
  the Battery has now.
* C: as B, the Circle replaced by a ``Rectangle`` 6 by 6 with Corner_Radius 3.
* D: as B, the Circle first (the dot before the icon).
* E: as B, a Circle of Diameter 7.
* F: as B, the icon wrapped in its own FlexBox 16 by 16.
* G: the icon and a Text (the normal look, the control), ``Foreground`` text colour.
* H: as B, the icon with no ``Foreground`` (the default colour).
* I: ONE icon whose document holds the dot (a ``<circle>`` in the SVG itself), no Foreground.
* J: as I with ``Foreground`` warning (the design that replaces the Circle).
* K: as A, the colour in the document itself (no ``Foreground``, no currentColor).
* L: the icon alone with ``Foreground`` the text colour (a ``Foreground`` that equals the default).

Colours are theme tokens, so the Bar follows Plasma's light and dark (K's one literal colour is in
its SVG document, which is the point of K). ``run.sh`` runs the shell on your real session bus
only to get the surface (this config has no module and asks for no service); ``check.sh`` checks
the files. The state directory is ``/tmp/tess-kwin-m5b-dot/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tess_shell.config.discovery import shipped_dir  # noqa: E402
from tess_shell.files.icons import IconSets  # noqa: E402
from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m5b-dot")
CFG = ROOT / "gallery"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)
ICON = "mdi:battery-10"
AMBER_LITERAL = "#e6bb6a"

WARN = "Foreground: $color.warning"
SVG16 = "Width: 16, Height: 16"
DOT = "Circle { Diameter: 6, Fill: $color.warning }"


def svg(extra: str = WARN, source: str = f'Icon: "{ICON}"', size: str = SVG16) -> str:
    return "SVG { " + ", ".join(part for part in (source, size, extra) if part) + " }"


def row(*parts: str) -> str:
    return (
        "FlexBox { Flex: HORIZONTAL, Spacing: 4, Align_Items: CENTER, Children { "
        + " ".join(parts)
        + " } }"
    )


def composed_document(icons: IconSets, colour: str | None = None) -> str:
    """The battery icon and a dot to its right in one document (viewBox 36 by 24: at 16 px high the
    dot is 6 px across)."""
    doc = icons.lookup(ICON)
    assert doc is not None
    body = doc.split(">", 1)[1].rsplit("</svg>", 1)[0]
    fill = colour or "currentColor"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 24" width="36" height="24">'
        + body.replace("currentColor", fill)
        + f'<circle cx="30" cy="12" r="4.5" fill="{fill}"/></svg>'
    )


def literal_document(icons: IconSets, colour: str) -> str:
    doc = icons.lookup(ICON)
    assert doc is not None
    return doc.replace("currentColor", colour)


def variants() -> dict[str, str]:
    composed = 'Source: "dot_composed.svg"'
    literal = 'Source: "dot_literal.svg"'
    wide = "Width: 24, Height: 16"
    return {
        "A": row(svg()),
        "B": row(svg(), DOT),
        "C": row(
            svg(), "Rectangle { Width: 6, Height: 6, Fill: $color.warning, Corner_Radius: 3 }"
        ),
        "D": row(DOT, svg()),
        "E": row(svg(), "Circle { Diameter: 7, Fill: $color.warning }"),
        "F": row("FlexBox { Width: 16, Height: 16, Children { " + svg() + " } }", DOT),
        "G": row(
            svg("Foreground: $color.on_surface"),
            'Text { Text: "15 %", Foreground: $color.on_surface }',
        ),
        "H": row(svg(""), DOT),
        "I": row(svg("", composed, wide)),
        "J": row(svg(WARN, composed, wide)),
        "K": row(svg("", literal)),
        "L": row(svg("Foreground: $color.on_surface")),
    }


def body() -> str:
    cells = []
    for letter, cell in variants().items():
        label = f'Text {{ Text: "{letter}", Font_Size: 12, Foreground: $color.on_surface }}'
        cells.append(row(label, cell))
    items = "\n                            ".join(cells)
    return f"""
Shell {{
    Monitor {{
        Name: Main
        Index: 0
        Children {{
            Bar {{
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Style {{ Background: $color.surface }}
                Children {{
                    FlexBox {{
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 20
                        Padding: [8, 4, 8, 4]
                        Align_Items: CENTER
                        Children {{
                            {items}
                        }}
                    }}
                }}
            }}
        }}
    }}
}}
"""


CHECKLIST = """Battery icon probe: ONE question per letter.  Do it in dark and in light.
Start /tmp/tess-kwin-m5b-dot/run.sh; the Bar shows letters A to L, each followed by a battery
icon (the 10 % one, a nearly empty battery) in some form.  A letter with its icon missing is the
answer; write down every letter whose icon is NOT drawn (a letter with only a dot, or nothing,
beside it).

 A  is the amber icon drawn?
 B  is the amber icon drawn (a dot after it)?
 C  is the amber icon drawn (a small rounded square after it)?
 D  is the icon drawn (a dot before it)?
 E  is the amber icon drawn (a bigger dot after it)?
 F  is the amber icon drawn (a dot after it)?
 G  is the icon drawn, in the text colour, with "15 %" after it?
 H  is the icon drawn (default colour; a dot after it)?
 I  is the icon drawn, with a dot inside the same picture (default colour)?
 J  is the amber icon drawn, with a dot inside the same picture?
 K  is the amber icon drawn?
 L  is the icon drawn in the text colour?

Reply with the letters whose icon is NOT drawn (for example "B C F H") and whether the answer was
the same in light and in dark.  Stop the shell with Ctrl+C.
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_probe(cfg: Path) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    shells = write_example(cfg, body()).parent
    icons = IconSets([shipped_dir() / "Icons"])
    (shells / "dot_composed.svg").write_text(composed_document(icons))
    (shells / "dot_literal.svg").write_text(literal_document(icons, AMBER_LITERAL))
    (cfg / "settings.tdl").write_text(SETTINGS)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_probe(CFG)
    (ROOT / "checklist.txt").write_text(CHECKLIST)
    state = f"export XDG_STATE_HOME={ROOT}/state\n"
    script("run.sh", state + f"exec {BIN}/tesserae-shell run --config-dir {CFG}\n")
    script("check.sh", state + f"{BIN}/tesserae-shell check --config-dir {CFG}\n")


if __name__ == "__main__":
    main()
