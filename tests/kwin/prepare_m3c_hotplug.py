"""Regenerate the M3c monitor hot-plug KWin checklist setup in /tmp/tess-kwin-m3c/hotplug (not
collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m3c_hotplug.py``. It writes two scratch
configs, one that names the monitors by ``Connector`` (``hotplug``) and one that names them by
``Index`` (``hotplug-index``), with scripts ``run-hotplug.sh``, ``run-hotplug-index.sh`` and
``check-hotplug.sh``. Nothing is started.

The shell has a Main monitor (HDMI-A-1, index 0) with a blue Bar and a Dock Panel, and a Side
monitor (DP-1, index 1) with a magenta Bar, a Movable red Dock Panel you can drag, and a Probe
module that writes its life cycle to /tmp/tess-kwin-m3c/probe.log.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import HEADER, SVG  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m3c")
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default] }\n}\n"
)

PROBE_TDL = """---
TDL: 0.1
Name: Probe
---

Module {
    Rectangle { Width: 14, Height: 14, Fill: "#ffd24a", Corner_Radius: 7 }
}
"""

PROBE_PY = '''from datetime import datetime
from pathlib import Path

from tess_shell import Module

LOG = Path("/tmp/tess-kwin-m3c/probe.log")


def note(text):
    with LOG.open("a") as f:
        f.write(f"{datetime.now():%H:%M:%S.%f} {text}\\n")


class Probe(Module):
    """Writes its life cycle: a monitor going away must end with use_removed and stop."""

    def start(self):
        note("start " + ", ".join(sorted(u.name for u in self.ctx.uses.values())))

    def use_added(self, use):
        note("use_added " + use.name)

    def use_removed(self, use):
        note("use_removed " + use.name)

    def stop(self):
        note("stop")
'''


def body(main: str, side: str) -> str:
    return f"""
Shell {{
    Monitor {{
        Name: Main
        {main}
        Children {{
            Bar {{
                Name: Main_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Style {{ Fill: "#1f3a5f" }}
                Children {{
                    FlexBox {{
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 8
                        Padding: 6
                        Children {{
                            Text {{ Text: "MAIN (HDMI-A-1)", Font_Size: 14, Foreground: "#ffffff" }}
                            Spacer {{ }}
                            Clock {{ Name: Main_Clock, format: "%H:%M:%S" }}
                        }}
                    }}
                }}
            }}
            Panel {{
                Name: Main_Dock
                Layer: TOP
                Anchor: [TOP, RIGHT]
                Inset: [0, 60, 40, 0]
                Width: 180
                Height: 70
                Style {{ Fill: "#2d6a4f", Corner_Radius: 8 }}
                Children {{
                    FlexBox {{
                        Padding: 8
                        Children {{
                            Text {{ Text: "Main dock", Font_Size: 14, Foreground: "#ffffff" }}
                        }}
                    }}
                }}
            }}
        }}
    }}
    Monitor {{
        Name: Side
        {side}
        Children {{
            Bar {{
                Name: Side_Bar
                Edge: BOTTOM
                Width: EXPAND
                Height: 36
                Style {{ Fill: "#5f1f3a" }}
                Children {{
                    FlexBox {{
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 8
                        Padding: 6
                        Children {{
                            Text {{ Text: "SIDE (DP-1)", Font_Size: 14, Foreground: "#ffffff" }}
                            Probe {{ Name: Side_Probe }}
                            Spacer {{ }}
                            Clock {{ Name: Side_Clock, format: "%H:%M:%S" }}
                        }}
                    }}
                }}
            }}
            Panel {{
                Name: Side_Dock
                Layer: TOP
                Anchor: [TOP, LEFT]
                Inset: [120, 120, 0, 0]
                Width: 200
                Height: 90
                Movable: true
                Style {{ Fill: "#a4161a", Corner_Radius: 8 }}
                Children {{
                    FlexBox {{
                        Padding: 8
                        Children {{
                            Text {{ Text: "Drag me, then unplug", Font_Size: 14, Foreground: "#ffffff" }}
                        }}
                    }}
                }}
            }}
        }}
    }}
}}
"""


def write_config(name: str, main: str, side: str) -> None:
    cfg = ROOT / name
    shutil.rmtree(cfg, ignore_errors=True)
    shells = cfg / "Shells"
    shells.mkdir(parents=True)
    (shells / "dot.svg").write_text(SVG)
    (shells / "Main_Shell.tdl").write_text(HEADER + body(main, side))
    (cfg / "settings.tdl").write_text(SETTINGS)
    module = cfg / "Modules" / "Probe"
    module.mkdir(parents=True)
    (module / "Probe_Module.tdl").write_text(PROBE_TDL)
    (module / "Probe_Module.py").write_text(PROBE_PY)


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


CHECK = r"""# Reads the newest log of a scratch config and says what the hot-plug did.
# Usage: check-hotplug.sh [hotplug | hotplug-index]
name=${1:-hotplug}
log=$(ls -t /tmp/tess-kwin-m3c/$name/logs/log_*.log 2>/dev/null | head -n 1)
[ -n "$log" ] || { echo "no log under /tmp/tess-kwin-m3c/$name/logs: run the shell first"; exit 2; }
echo "== log: $log"
echo "== what the shell saw and did"
grep -E "output .* (added|removed|changed)|Bar .* (is opened|closed|configured)|Panel .* (is opened|closed|configured|moved)|monitor .* matches no output|no outputs" "$log"
echo "== the module's life cycle (probe.log)"
cat /tmp/tess-kwin-m3c/probe.log 2>/dev/null || echo "(none)"
echo "== verdicts"
fail=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
check "Main_Bar opened exactly once (never recreated by a plug or unplug of the other screen)" \
  '[ "$(grep -c "Bar Main_Bar on HDMI-A-1 configured" "$log")" = 1 ]'
check "Main_Bar never closed" '! grep -q "Bar Main_Bar on HDMI-A-1 closed" "$log"'
check "Main_Dock never closed" '! grep -q "Panel Main_Dock on HDMI-A-1 closed" "$log"'
check "no error in the log" '! grep -q "| ERROR " "$log"'
exit $fail
"""


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    (ROOT / "probe.log").unlink(missing_ok=True)
    write_config("hotplug", "Connector: HDMI-A-1", "Connector: DP-1")
    write_config("hotplug-index", "Index: 0", "Index: 1")
    for name, config in (("run-hotplug.sh", "hotplug"), ("run-hotplug-index.sh", "hotplug-index")):
        script(
            name,
            f"# Monitor hot-plug ({config}).  Usage: {name}   (Ctrl+C stops it)\n"
            "mkdir -p /tmp/tess-kwin-m3c\n: > /tmp/tess-kwin-m3c/probe.log\n"
            "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
            f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3c/{config}\n",
        )
    script("check-hotplug.sh", CHECK)
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
