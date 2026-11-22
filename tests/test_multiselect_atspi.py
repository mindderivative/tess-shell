"""A multiple-selection List as a screen reader reads it (AC-SLT-8, AC-SLT-9): a real shell on a
private headless sway publishes its tree on a private AT-SPI bus (``tests/atspi_env.py``) and
``busctl`` plays the screen reader. The container is ``multiselectable``, each entry says
``selected`` as the chosen set says, and the engine announces the count once. Nothing here reaches
the real session or the real accessibility bus; this proves the AT-SPI contract, not Orca's
speech."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests import atspi_env
from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not atspi_env.available(), reason="no private AT-SPI environment"),
    pytest.mark.skipif(shutil.which("sway") is None, reason="no sway"),
]
LIST, LIST_ITEM = 31, 32
MULTISELECTABLE, SELECTED = 18, 23
ENTRIES = " ".join(
    f'FlexBox {{ Class: list_item, Key: k{i}, Height: 30, Children {{ Text {{ Text: "Entry {i}", '
    "Width: AUTO, Height: AUTO } } }"
    for i in range(1, 5)
)
PANEL = (
    "Panel { Name: Files, Layer: TOP, Width: 240, Height: 140, Children { List { Label: Files, "
    f'Selection: MULTIPLE, Selected: "k1,k3", Height: 140, Children {{ {ENTRIES} }} }} }} }}'
)


def until(predicate: Callable[[], object], what: str, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail(f"never saw: {what}")


def test_a_multiple_list_is_multiselectable_marks_its_chosen_entries_and_announces_the_count(
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

    def nodes() -> list[tuple[int, int | None, str | None, str, str]]:
        apps = session.children(*root)
        return list(session.tree(*apps[0], limit=9)) if apps else []

    def container() -> tuple[str, str] | None:
        for _, role, name, dest, path in nodes():
            if role == LIST and name == "Files":
                return (dest, path)
        return None

    def selected() -> list[bool]:
        """Whether each entry, in order, says ``selected``."""
        return [
            SELECTED in session.states(dest, path)
            for _, r, _, dest, path in nodes()
            if r == LIST_ITEM
        ]

    env = {**private_sway.env, **session.env()}
    try:
        said = session.monitor("Announcement")
        shell = Shell(tmp_path, env)
        try:
            shell.wait_for("running")
            session.enable()  # what turning a screen reader on does
            until(container, "the list named Files")
            found = container()
            assert found is not None
            assert MULTISELECTABLE in session.states(*found)  # AC-SLT-8
            until(lambda: selected() == [True, False, True, False], "the chosen entries selected")
            time.sleep(1.0)  # the debounce (300 ms) and the signal
        finally:
            if shell.process.poll() is None:
                shell.process.kill()  # our own child
                shell.process.wait()
        spoken = said.announcements()
    finally:
        session.close()
    assert [t for t, _ in spoken] == ["2 selected"], spoken  # AC-SLT-9: once, polite
    assert all(p == 1 for _, p in spoken)
