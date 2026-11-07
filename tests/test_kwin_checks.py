"""The generated KWin check scripts, run against logs like the ones the shell writes."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.kwin.prepare_m3c_hotplug import CHECK

STAMP = "2026-11-06 21:38:{s:02d}.{ms:03d} | INFO     | shell | - | "


def line(second: int, text: str) -> str:
    return STAMP.format(s=second, ms=second * 7 % 1000) + text


# a normal run: the screens come up, DP-1 is unplugged and plugged back, Ctrl+C at 21:38:30 closes
# every window with the reason "stopped"
NORMAL = [
    line(1, "Bar Main_Bar on HDMI-A-1 configured 1920x32"),
    line(1, "Panel Main_Dock on HDMI-A-1 configured 200x60"),
    line(1, "Bar Side_Bar on DP-1 configured 1920x32"),
    line(10, "output DP-1 removed: outputs now HDMI-A-1"),
    line(10, "Bar Side_Bar on DP-1 closed: output DP-1 was removed"),
    line(20, "output DP-1 added: outputs now HDMI-A-1, DP-1"),
    line(20, "Bar Side_Bar on DP-1 is opened: output DP-1 is there"),
    line(20, "Bar Side_Bar on DP-1 configured 1920x32"),
    line(29, "running"),
    line(30, "Panel Side_Dock on DP-1 closed (stopped)"),
    line(30, "Panel Main_Dock on HDMI-A-1 closed (stopped)"),
    line(30, "Bar Side_Bar on DP-1 closed (stopped)"),
    line(30, "Bar Main_Bar on HDMI-A-1 closed (stopped)"),
]


def run(tmp_path: Path, lines: list[str]) -> str:
    logs = tmp_path / "hotplug" / "logs"
    logs.mkdir(parents=True)
    (logs / "log_1.log").write_text("\n".join(lines) + "\n")
    script = tmp_path / "check.sh"
    script.write_text("#!/usr/bin/env bash\n" + CHECK)
    done = subprocess.run(
        ["bash", str(script), "hotplug"],
        env={"TESS_KWIN_ROOT": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    return done.stdout


def verdicts(out: str) -> dict[str, str]:
    return {
        t.split(" ", 1)[1]: t.split(" ", 1)[0]
        for t in out.splitlines()
        if t[:4] in ("PASS", "FAIL")
    }


def test_the_shells_own_stop_at_the_end_is_not_a_close_of_main_bar_or_main_dock(
    tmp_path: Path,
) -> None:
    got = verdicts(run(tmp_path, NORMAL))
    assert got and set(got.values()) == {"PASS"}, got


def test_a_close_before_the_stop_is_still_reported(tmp_path: Path) -> None:
    broken = [*NORMAL[:9], line(15, "Bar Main_Bar on HDMI-A-1 closed: output HDMI-A-1 was removed")]
    got = verdicts(run(tmp_path, broken))
    assert got["Main_Bar never closed (apart from the shell's own stop at the end)"] == "FAIL"
    assert got["Main_Dock never closed (apart from the shell's own stop at the end)"] == "PASS"


def test_a_run_with_no_unplug_is_reported(tmp_path: Path) -> None:
    quiet = [x for x in NORMAL if "output" not in x.split("|")[-1][:8]]
    quiet = [x for x in quiet if " removed" not in x and " added" not in x]
    got = verdicts(run(tmp_path, quiet))
    assert got["the run contains an unplug and a plug (output removed, output added)"] == "FAIL"
