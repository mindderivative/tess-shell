"""Regenerate the M3a KWin checklist setup in /tmp/tess-kwin-m3a (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m3a.py``. It writes four scratch
configs (theme, shadow, plain, nofollow) and the short scripts the checklist in the M3 Build Log
names: ``run.sh``, ``check.sh`` and the ``edit-*.sh`` files. Nothing is started.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import BODY, write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m3a")
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
LABEL = 'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }'
FILL = 'Style { Fill: "#1f1f1f" }'
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {{\n  Logging {{ Level: DEBUG }}\n"
    "  Appearance {{ {appearance} }}\n}}\n"
)
WARM = """---
TDL: 0.1
Name: Warm
---
Theme {
    Color { Surface: "#3b2a1a", On_Surface: "#ffe9c7", Primary: "#ffb347", Accent: DESKTOP }
    Shape { Small: 6 }
    Elevation { Max { Shadows { Shadow { Color: "#000000a0", X: 0, Y: 12, Blur: 30 } } } }
}
"""
LOOK = (
    'Text { Text: "Theme test", Font_Size: 14 }\n'
    "Rectangle { Width: 14, Height: 14, Fill: $color.primary, Corner_Radius: $shape.small }\n"
    "Rectangle { Width: 14, Height: 14, Fill: $color.accent, Corner_Radius: $shape.small }"
)

EDIT = '''import sys
from pathlib import Path

cfg = Path("/tmp/tess-kwin-m3a/theme")
settings, shell = cfg / "settings.tdl", cfg / "Shells" / "Main_Shell.tdl"


def swap(path: Path, on: str, off: str) -> None:
    """Switch a file between two texts: each run turns the one it finds into the other."""
    text = path.read_text()
    path.write_text(text.replace(on, off) if on in text else text.replace(off, on))


case = sys.argv[1]
if case == "warm":
    swap(settings, "Theme: Warm, Stylesheets: [Default]", "Stylesheets: [Default]")
elif case == "badtoken":
    shell.write_text(shell.read_text().replace("$color.surface", "$color.surfce"))
elif case == "fixtoken":
    shell.write_text(shell.read_text().replace("$color.surfce", "$color.surface"))
elif case == "elevation":
    swap(shell, "Fill: $color.surface, Elevation: 100% }", "Fill: $color.surface }")
print("edited:", case)
'''


def make(
    name: str, children: str, fill: str, appearance: str, gap: str = "", themes: bool = False
) -> None:
    cfg = ROOT / name
    shutil.rmtree(cfg, ignore_errors=True)
    body = BODY.replace(LABEL, children).replace(FILL, fill)
    if gap:
        body = body.replace("Height: 32\n", "Height: 32\n" + gap)
    write_example(cfg, body)
    (cfg / "settings.tdl").write_text(SETTINGS.format(appearance=appearance))
    if themes:
        (cfg / "Themes").mkdir()
        (cfg / "Themes" / "Warm_Theme.tdl").write_text(WARM)


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    sheets = "Stylesheets: [Default]"
    gap = "                Gap: 8\n"
    make("theme", LOOK, "Style { Fill: $color.surface }", sheets, themes=True)
    make("shadow", LOOK, "Style { Fill: $color.surface, Elevation: 100% }", sheets, gap)
    make("plain", LOOK, "Style { Fill: $color.surface }", sheets, gap)
    make("nofollow", LOOK, "Style { Fill: $color.surface }", f"{sheets}, Follow_Desktop: false")
    (ROOT / "edit.py").write_text(EDIT)
    script(
        "run.sh",
        "# Usage: run.sh theme|shadow|plain|nofollow    (Ctrl+C or kill -TERM stops it)\n"
        'variant="${1:?variant: theme, shadow, plain or nofollow}"\n'
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3a/state   # keeps UID backups out of yours\n"
        f'exec {BIN}/tesserae-shell run --config-dir "/tmp/tess-kwin-m3a/$variant"\n',
    )
    for case in ("warm", "badtoken", "fixtoken", "elevation"):
        script(f"edit-{case}.sh", f"exec {BIN}/python /tmp/tess-kwin-m3a/edit.py {case}\n")
    script(
        "check.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3a/state\n"
        "for v in theme shadow plain nofollow; do\n"
        f'  {BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3a/$v || echo "FAILED: $v"\n'
        "done\n",
    )
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
