"""The whole path: a desktop setting changes on the bus, and the running shell's Bar changes
(private sway for the surface, a private bus with a fake Settings portal for the desktop)."""

from __future__ import annotations

import signal
import time
from pathlib import Path

import pytest
from dbus_fast import Variant

from tests.fake_portal import HAVE_DAEMON, fake_portal
from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_reload_live import stamp
from tests.test_run import Shell

pytestmark = [pytest.mark.tre, pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")]

SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\n"
    "Settings { Logging { Level: DEBUG }  Appearance { Follow_Desktop: %s } }\n"
)
THEMED = BODY.replace('Style { Fill: "#1f1f1f" }', "Style { Fill: $color.surface }")


def start(sway: PrivateSway, cfg: Path, address: str, follow: bool = True) -> Shell:
    write_example(cfg, THEMED)
    (cfg / "settings.tdl").write_text(SETTINGS % str(follow).lower())
    env = {**sway.env, "DBUS_SESSION_BUS_ADDRESS": address}
    return Shell(cfg, env)


def finish(shell: Shell) -> None:
    shell.process.send_signal(signal.SIGTERM)
    assert shell.finish() == 0


def test_a_scheme_change_on_the_bus_reaches_the_bar_within_100_ms(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_portal() as (address, portal):
        shell = start(private_sway, tmp_path, address)
        try:
            shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")  # the loop is running
            shell.wait_for("portal: appearance")  # the first read: dark
            assert "Register" in portal.settings.calls
            sent = time.time()
            portal.set("color-scheme", Variant("u", 2))
            shell.wait_for("look: scheme light")
            line = next(x for x in shell.seen if "look: scheme light" in x)
            assert stamp(line) - sent < 0.1, f"{(stamp(line) - sent) * 1000:.0f} ms"
            portal.set("reduced-motion", Variant("u", 1))
            shell.wait_for("reduced motion True")
            finish(shell)
        finally:
            if shell.process.poll() is None:
                shell.process.kill()
    # the engine's own wgpu noise on a headless compositor is not the shell's: only its log lines
    assert not any("| ERROR " in x for x in shell.seen), "".join(shell.seen)


def test_follow_desktop_false_never_calls_the_portal(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_portal() as (address, portal):
        shell = start(private_sway, tmp_path, address, follow=False)
        try:
            shell.wait_for("step 11 (surfaces): 1 opened")
            time.sleep(0.3)
            assert portal.settings.calls == []
            portal.set("color-scheme", Variant("u", 2))
            time.sleep(0.3)
            assert not any("look: scheme" in x for x in shell.seen)
            finish(shell)
        finally:
            if shell.process.poll() is None:
                shell.process.kill()


def test_with_no_portal_the_shell_runs_with_the_default_look_and_one_warning(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_portal(running=False) as (address, _portal):
        shell = start(private_sway, tmp_path, address)
        try:
            shell.wait_for("step 11 (surfaces): 1 opened")
            shell.wait_for("running")
            finish(shell)
        finally:
            if shell.process.poll() is None:
                shell.process.kill()
    warnings = [x for x in shell.seen if "WARNING" in x and "portal:" in x]
    assert len(warnings) == 1, warnings
