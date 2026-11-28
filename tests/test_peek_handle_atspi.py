"""The Peek handle as a screen reader presses it (AC-PEK-16): a real shell with a Frame and a melded
Panel with a ``Peek { Trigger: CLICK }`` on a private headless sway publishes its tree on a private
AT-SPI bus (``tests/atspi_env.py``); ``busctl`` plays the screen reader: it finds the button named
"Expand Dock", presses it with the Action interface's ``DoAction`` (what Orca's "activate" does) and
reads the name change to "Collapse Dock". Nothing here reaches the real session or the real
accessibility bus; this proves the AT-SPI contract, not Orca's speech."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests import atspi_env
from tests.shell_samples import write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not atspi_env.available(), reason="no private AT-SPI environment"),
    pytest.mark.skipif(shutil.which("sway") is None, reason="no sway"),
]
PUSH_BUTTON = 43
BODY = """
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Frame {
                Name: Screen_Frame
                Thickness: [6, 34, 6, 12]
                Inner_Radius: 14
                Inner_Border { Width: 2, Color: "#4682b4" }
                Style { Background: "#12171d" }
            }
            Panel {
                Name: Dock
                Meld: true
                Attach_To: Screen_Frame
                Attach: BOTTOM
                Alignment: CENTER
                Length: 320
                Depth: 56
                Peek { Size: 12, Trigger: CLICK, Handle: CHEVRON }
                Animation { Type: SLIDE, Duration: 200 }
                Children { FlexBox { Width: EXPAND, Children { Text { Text: "dock" } } } }
            }
        }
    }
}
"""


def until(
    predicate: Callable[[], object],
    what: str,
    timeout: float = 20,
    retry: Callable[[], object] | None = None,
) -> None:
    """Poll until ``predicate`` holds; ``retry`` runs every 4 s while it does not."""
    start = time.monotonic()
    deadline = start + timeout
    nudged = start
    while time.monotonic() < deadline:
        if predicate():
            return
        if retry is not None and time.monotonic() - nudged >= 4:
            nudged = time.monotonic()
            retry()
        time.sleep(0.1)
    pytest.fail(f"never saw: {what}")


def test_a_screen_reader_presses_the_peek_handle_and_the_name_follows(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    write_example(tmp_path, BODY)
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.2\nName: S\n---\nSettings { Logging { Level: DEBUG } }\n"
    )
    session = atspi_env.AtspiEnvironment()

    def dump() -> list[tuple[int | None, str | None]]:
        root = ("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
        apps = session.children(*root)
        return [(r, n) for _, r, n, _, _ in session.tree(*apps[0], limit=9)] if apps else []

    def button(name: str) -> tuple[str, str] | None:
        root = ("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
        apps = session.children(*root)
        if not apps:
            return None
        for _, role, found, dest, path in session.tree(*apps[0], limit=9):
            if role == PUSH_BUTTON and found == name:
                return (dest, path)
        return None

    env = {**private_sway.env, **session.env()}
    try:
        shell = Shell(tmp_path, env)
        try:
            shell.wait_for("running")
            session.enable()  # what turning a screen reader on does

            def screen_reader_again() -> None:
                # "running" is logged before the shell listens for a screen reader: one that came
                # in that gap is missed, so turn it off and on again until the tree is published
                session.enable(False)
                session.enable()

            try:
                until(
                    lambda: button("Expand Dock"),
                    "the handle as a button named Expand Dock",
                    retry=screen_reader_again,
                )
            except pytest.fail.Exception:
                print("TREE", dump())
                print("LOG", shell.stderr[-2500:])
                raise
            node = button("Expand Dock")
            assert node is not None
            assert session.do_action(*node) is True  # the screen reader's activate
            until(lambda: button("Collapse Dock"), "the name following the press: Collapse Dock")
            assert button("Expand Dock") is None
        finally:
            if shell.process.poll() is None:
                shell.process.kill()  # our own child
                shell.process.wait()
    finally:
        session.close()
