"""A Bar on a private headless sway: it appears on the matched output, reserves its space, and
goes away when the shell stops (M1 Definition of Done)."""

from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path

import pytest

from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = pytest.mark.tre


def workspace_rect(sway: PrivateSway) -> dict[str, int]:
    out = subprocess.run(
        ["swaymsg", "-t", "get_workspaces"],
        env=sway.env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    focused = [w for w in json.loads(out) if w["focused"]] or json.loads(out)
    rect: dict[str, int] = focused[0]["rect"]
    return rect


def reserved_rect(sway: PrivateSway, before: dict[str, int]) -> dict[str, int]:
    """The workspace rectangle once sway has applied the Bar's zone (it follows the configure)."""
    import time

    deadline = time.monotonic() + 5
    rect = workspace_rect(sway)
    while rect == before and time.monotonic() < deadline:
        time.sleep(0.05)
        rect = workspace_rect(sway)
    return rect


def start(sway: PrivateSway, config: Path) -> Shell:
    return Shell(config, sway.env)


def test_the_bar_reserves_its_space_and_releases_it_on_stop(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    write_example(tmp_path)
    before = workspace_rect(private_sway)
    shell = start(private_sway, tmp_path)
    try:
        shell.wait_for("Bar Top_Bar on HEADLESS-1 configured 1280x32")
        shell.wait_for("step 11 (surfaces): 1 opened")
        during = reserved_rect(private_sway, before)
        assert during["y"] == before["y"] + 32
        assert during["height"] == before["height"] - 32
        assert during["width"] == before["width"]
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    after = workspace_rect(private_sway)
    assert after == before
    assert "closed" in shell.log_text()


def test_the_gap_is_reserved_too(private_sway: PrivateSway, tmp_path: Path) -> None:
    write_example(tmp_path, BODY.replace("Height: 32\n", "Height: 32\n                Gap: 8\n"))
    before = workspace_rect(private_sway)
    shell = start(private_sway, tmp_path)
    try:
        shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")
        # The zone is 40 (32 + the 8 px Gap). sway adds the margin to the zone and reserves 48;
        # the spec's "40" is unverified (Bar > Mapping to tre), so only the lower bound is pinned.
        assert reserved_rect(private_sway, before)["y"] >= before["y"] + 40
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_a_monitor_that_matches_no_output_opens_nothing(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    write_example(tmp_path, BODY.replace("Index: 0", "Index: 3"))
    shell = start(private_sway, tmp_path)
    try:
        shell.wait_for("step 11 (surfaces): 0 opened")
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_a_bind_error_leaves_the_bar_empty_and_the_shell_running(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    # The schema cannot see inside an SVG document; tre refuses it at bind time.
    from tests.shell_samples import HEADER

    body = BODY.replace('Source: "dot.svg"', 'Source: "bad.svg"')
    path = write_example(tmp_path, body)
    (path.parent / "bad.svg").write_text("not an svg")
    path.write_text(HEADER + body)
    shell = start(private_sway, tmp_path)
    try:
        shell.wait_for("is empty: its contents did not bind")
        shell.wait_for("running")
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    assert "valid SVG" in shell.stderr
    assert "Shells/Main_Shell.tdl:27" in shell.stderr


def clock_config(tmp_path: Path, fmt: str) -> Path:
    body = BODY.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }',
        f'Clock {{ format: "{fmt}" }}',
    )
    write_example(tmp_path, body)
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.1\nName: Settings\n---\nSettings { Logging { Level: DEBUG } }\n"
    )
    return tmp_path


def wait_for_count(shell: Shell, pattern: str, count: int, timeout: float) -> None:
    """Read the shell's stderr until ``pattern`` has appeared ``count`` times."""
    import re
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while not shell.lines.empty():
            shell.seen.append(shell.lines.get())
        if len(re.findall(pattern, "".join(shell.seen))) >= count:
            return
        time.sleep(0.1)
    pytest.fail(f"{pattern!r} did not appear {count} times:\n{shell.stderr}")


def test_the_clock_ticks_each_second_from_the_wall_clock(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    import re

    shell = start(private_sway, clock_config(tmp_path, "%H:%M:%S"))
    try:
        wait_for_count(shell, r"Face Text = '", 4, timeout=10)
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    texts = re.findall(r"Face Text = '(\d\d:\d\d:\d\d)'", shell.stderr)
    assert len(texts) >= 4, shell.stderr
    seconds = [int(t[-2:]) for t in texts]
    steps = [(b - a) % 60 for a, b in zip(seconds, seconds[1:], strict=False)]
    assert steps == [1] * len(steps)  # every second, none skipped, none repeated


def test_the_first_run_writes_the_uid_and_keeps_a_backup_outside_the_config(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    config = clock_config(tmp_path, "%H:%M")
    shell_file = config / "Shells" / "Main_Shell.tdl"
    before = shell_file.read_text()
    shell = start(private_sway, config)
    try:
        shell.wait_for("step 12 (modules): started")
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    after = shell_file.read_text()
    (added,) = [line for line in after.splitlines() if line.startswith("UID: ")]
    assert after.replace(added + "\n", "", 1) == before
    backups = private_sway.runtime / "state" / "tesserae-shell" / "backups" / "Shells"
    (backup,) = backups.glob("Main_Shell.tdl.*")
    assert backup.read_text() == before
    import json

    entries = json.loads((config / "registry.json").read_text())["entries"]
    assert entries["file:Shells/Main_Shell.tdl"]["uid"] == added.removeprefix("UID: ")
    assert any(k.startswith("Main_Shell.Main.Top_Bar.Clock_") for k in entries)

    # a second start adds no second line and no second backup
    second = start(private_sway, config)
    try:
        second.wait_for("step 12 (modules): started")
        second.process.send_signal(signal.SIGTERM)
        assert second.finish() == 0
    finally:
        if second.process.poll() is None:
            second.process.kill()
    assert shell_file.read_text() == after
    assert len(list(backups.glob("Main_Shell.tdl.*"))) == 1


TODO_PY = """
from tess_shell import Module


class Todo(Module):
    def start(self):
        self.items = [{"id": 1, "title": "first"}, {"id": 2, "title": "second"}]
        self.send()
        self.ctx.on_tick("second", self.tick)

    def send(self):
        self.ctx.send("items", list(self.items))

    def tick(self):
        n = len(self.items) + 1
        self.items.append({"id": n, "title": f"item {n}"})
        self.send()
"""

TODO_TDL = """
Module {
    FlexBox {
        Name: Row
        Children {
            For w In {{ items }} Key {{ w.id }} {
                Text { Text: {{ w.title }}, Foreground: "#ffffff" }
            }
        }
    }
}
"""


def test_a_for_follows_a_modules_list_while_the_shell_runs(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    from tests.shell_samples import HEADER

    body = BODY.replace('Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }', "Todo { }")
    write_example(tmp_path, body)
    folder = tmp_path / "Modules" / "Todo"
    folder.mkdir(parents=True)
    (folder / "Todo_Module.tdl").write_text(HEADER.replace("Main_Shell", "Todo") + TODO_TDL)
    (folder / "Todo_Module.py").write_text(TODO_PY)
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.1\nName: Settings\n---\nSettings { Logging { Level: DEBUG } }\n"
    )
    shell = start(private_sway, tmp_path)
    try:
        wait_for_count(shell, r"rebuilt Bar Top_Bar", 3, timeout=10)
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    import re

    assert "Traceback" not in shell.stderr
    assert not re.search(r"^(ERROR|CRITICAL|WARNING)\s+\|", shell.stderr, re.M), shell.stderr
    # B1: each appended item creates exactly one node and touches no other (the others are kept)
    stats = re.findall(
        r"rebuilt Bar Top_Bar: (\d+) changed, (\d+) created, (\d+) removed", shell.stderr
    )
    assert len(stats) >= 3 and all(s == ("0", "1", "0") for s in stats), stats


def test_a_shadow_changes_neither_the_reserved_space_nor_the_body(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """ADR-0010: the shadow lives in a transparent margin; sway reserves the same space."""
    body = BODY.replace("Height: 32\n", "Height: 32\n                Gap: 8\n").replace(
        'Style { Fill: "#1f1f1f" }', 'Style { Fill: "#1f1f1f", Elevation: 100% }'
    )
    write_example(tmp_path, body)
    before = workspace_rect(private_sway)
    shell = start(private_sway, tmp_path)
    try:
        shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")
        # Gap 8 + Height 32 reserved 48 without a shadow (D31); the same with one
        assert reserved_rect(private_sway, before)["y"] == before["y"] + 48
        assert "size (0, 105)" in shell.log_text()  # 8 (shadow in the Gap) + 32 + 65 below
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
