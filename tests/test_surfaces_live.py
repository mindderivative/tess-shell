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
