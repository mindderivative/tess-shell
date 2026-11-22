"""The List's Home, End, Page Up and Page Down with REAL key events: a real shell on a private
headless sway, keys from ``wtype`` (a virtual keyboard: the compositor sends the engine real
``key_down`` events, whose names the shell matches), the chosen entry read from the AT-SPI tree on
a private bus (``tests/atspi_env.py``). The headless tests send names the shell's author chose
(``simulate("key_down", key="home")``, from the engine's documented snake_case names); this one
measures what the engine really says for these keys. Nothing here reaches the user's session."""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests import atspi_env
from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_launcher_live import keys
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not atspi_env.available(), reason="no private AT-SPI environment"),
    pytest.mark.skipif(shutil.which("wtype") is None, reason="no wtype (a virtual keyboard)"),
]
LIST_ITEM, SELECTED = 32, 23
COUNT = 12
ENTRIES = " ".join(
    f'FlexBox {{ Class: list_item, Key: k{i}, Height: 30, Children {{ Text {{ Text: "Entry {i}", '
    "Width: AUTO, Height: AUTO } } }"
    for i in range(1, COUNT + 1)
)
PANEL = (
    "Panel { Name: Files, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 240, Height: 100, "
    f"Children {{ List {{ Label: Files, Height: 100, Children {{ {ENTRIES} }} }} }} }}"
)


def until(predicate: Callable[[], object], what: str, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail(f"never saw: {what}")


def test_home_end_and_the_page_keys_move_the_choice_of_a_list_with_real_key_events(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    write_example(
        tmp_path, BODY.replace("            Bar {", f"            {PANEL}\n            Bar {{", 1)
    )
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.2\nName: S\n---\nSettings { Logging { Level: DEBUG } }\n"
    )
    session = atspi_env.AtspiEnvironment()
    root = ("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")

    def chosen() -> list[int]:
        apps = session.children(*root)
        found = list(session.tree(*apps[0], limit=9)) if apps else []
        rows = [(d, p) for _, r, _, d, p in found if r == LIST_ITEM]
        return [i + 1 for i, node in enumerate(rows) if SELECTED in session.states(*node)]

    env = {**private_sway.env, **session.env()}
    holder = None
    try:
        shell = Shell(tmp_path, env)
        try:
            shell.wait_for("running")
            session.enable()
            # a virtual keyboard that stays, so the seat keeps its keyboard between the keys
            holder = subprocess.Popen(
                ["wtype", "-k", "F24", "-s", "300000"], env=dict(private_sway.env)
            )
            until(lambda: len(session.children(*root)) > 0, "the application")
            # the first Down of a list chooses its first entry: it tells the list has the keys
            for _ in range(20):
                keys(private_sway, "-k", "Tab")
                keys(private_sway, "-k", "Down")
                if chosen() == [1]:
                    break
                time.sleep(0.3)
            until(lambda: chosen() == [1], "the first Down chose the first entry")
            keys(private_sway, "-k", "End")
            until(lambda: chosen() == [COUNT], "End chose the last entry")
            keys(private_sway, "-k", "Home")
            until(lambda: chosen() == [1], "Home chose the first entry")
            keys(private_sway, "-k", "Next")  # Page Down
            until(lambda: len(chosen()) == 1 and chosen()[0] > 1, "Page Down moved the choice")
            keys(private_sway, "-k", "Prior")  # Page Up
            until(lambda: chosen() == [1], "Page Up came back")
        finally:
            if holder is not None:
                holder.terminate()
                holder.wait(timeout=10)
            if shell.process.poll() is None:
                shell.process.kill()  # our own child
                shell.process.wait()
    finally:
        session.close()
