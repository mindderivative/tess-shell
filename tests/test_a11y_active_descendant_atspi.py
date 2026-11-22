"""The Launcher as a screen reader sees it: the AT-SPI contract of the active descendant (M7j,
ADR-0023), of ``ctx.announce`` and of the click catcher (M7k), read from the real accessibility
tree and signals of a real shell.

A real shell on a private headless sway publishes its tree on a private AT-SPI bus
(``tests/atspi_env.py``); ``busctl`` plays the screen reader (the same D-Bus calls Orca makes:
``GetChildren``, ``GetRole``, ``GetState``, and the ``StateChanged``, ``ActiveDescendantChanged``
and ``Announcement`` signals). Keys come from ``wtype``. Nothing here reaches the user's session or
the real accessibility bus.

What this proves is the AT-SPI contract, NOT Orca's speech: Orca itself is not installed, and
whether it reads a layer surface that is not the focused window is the maintainer's M7g line.

How tre expresses the relation (tre 0.6.10, TRE-REQ-023): the field's ``active_descendant`` moves
the AT-SPI ``focused`` state to the row, while the application's keyboard focus (and the text
cursor) stays in the field; it sends no ``ActiveDescendantChanged``. The test asserts that form.
"""

from __future__ import annotations

import json
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests import atspi_env
from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_launcher_live import keys, reach, share_without_applications
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not atspi_env.available(), reason="no private AT-SPI environment"),
    pytest.mark.skipif(shutil.which("wtype") is None, reason="no wtype (a virtual keyboard)"),
]

# AT-SPI role numbers (ATSPI_ROLE_*) and state numbers (ATSPI_STATE_*)
DIALOG, LIST, LIST_ITEM, ENTRY, PANEL = 16, 98, 32, 79, 39  # LIST: the list box (role listbox)
FOCUSED, SELECTED = 12, 23
INTERACTIVE = {ENTRY, LIST, LIST_ITEM, 43}  # entry, list, list item, push button
APPS = ("Fake One", "Fake Two", "Other")


class Reader:
    """The screen reader's view of the shell's application on the private AT-SPI bus."""

    def __init__(self, env: atspi_env.AtspiEnvironment) -> None:
        self.env = env
        self.names: dict[str, str] = {}  # object path -> name, kept for reading the signals later

    def app(self) -> tuple[str, str] | None:
        root = ("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
        apps = self.env.children(*root)
        return apps[0] if apps else None

    def nodes(self) -> list[tuple[int, int | None, str | None, str, str]]:
        app = self.app()
        found = self.env.tree(*app, limit=9) if app else []
        for _, _, name, _, path in found:
            if name:
                self.names[path] = name
        return found

    def of(self, role: int, name: str) -> tuple[str, str] | None:
        for _, r, n, dest, path in self.nodes():
            if r == role and n == name:
                return (dest, path)
        return None

    def rows(self) -> list[tuple[str, tuple[str, str]]]:
        return [(n or "", (d, p)) for _, r, n, d, p in self.nodes() if r == LIST_ITEM]

    def states(self, node: tuple[str, str]) -> set[int]:
        return self.env.states(*node)


def until(predicate: Callable[[], object], what: str, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail(f"never saw: {what}")


def test_the_launcher_through_the_eyes_of_a_screen_reader(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    data = tmp_path / "data" / "applications"
    data.mkdir(parents=True)
    for name in APPS:
        (data / f"{name.lower().replace(' ', '-')}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={name}\nExec=/bin/true\n"
        )
    launcher = (
        "Panel { Name: Launcher, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 480, "
        "Height: AUTO, Max_Height: 400, Visible: false, Children { Applications { } } }"
    )
    write_example(
        tmp_path,
        BODY.replace("            Bar {", f"            {launcher}\n            Bar {{", 1),
    )
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.2\nName: S\n---\nSettings { Logging { Level: DEBUG } }\n"  # default stylesheet
    )
    session = atspi_env.AtspiEnvironment()
    reader = Reader(session)
    shell_env = {
        **private_sway.env,
        **session.env(),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_DATA_DIRS": f"{tmp_path / 'data'}:{share_without_applications(tmp_path)}",
        "PYTEST_CURRENT_TEST": "a11y",  # the starter only records (services/apps.py)
        "TESS_SHELL_LAUNCH_RECORD": str(tmp_path / "launches.jsonl"),
    }
    try:
        states = session.monitor("StateChanged")
        active = session.monitor("ActiveDescendantChanged")
        said = session.monitor("Announcement")
        shell = Shell(tmp_path, shell_env)
        try:
            shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")
            session.enable()  # what turning a screen reader on does
            until(lambda: reader.of(DIALOG, "Top Bar") or reader.app(), "the application")
            subprocess.run(
                [sys.executable, "-m", "tess_shell", "toggle", "Launcher"],
                env=shell_env,
                timeout=20,
                check=True,
            )
            shell.wait_for("Panel Launcher on HEADLESS-1 shown")
            # a virtual keyboard that stays: the seat loses its keyboard (and the focused state
            # with it) each time the short-lived ``wtype`` of ``keys`` exits
            holder = subprocess.Popen(
                ["wtype", "-k", "F24", "-s", "300000"], env=dict(private_sway.env)
            )

            # -- 4: the Launcher's own names and roles; nothing unlabelled that can be operated --
            until(lambda: reader.of(ENTRY, "Search applications"), "the search field")
            until(lambda: len(reader.rows()) == len(APPS), "three rows")
            assert reader.of(DIALOG, "Launcher"), "the Panel is a dialog named Launcher"
            assert reader.of(LIST, "Results"), "the list is named Results"
            assert [n for n, _ in reader.rows()] == list(APPS)
            unnamed = [(r, p) for _, r, n, _, p in reader.nodes() if r in INTERACTIVE and not n]
            assert unnamed == [], f"operable nodes with no name: {unnamed}"
            # the click catcher (a layer surface of ours, under the Launcher) exposes nothing: its
            # root is a11y_hidden, so the empty window node tre keeps for the surface has no name,
            # no child and nothing a screen reader can reach (tre cannot leave the window node out
            # yet: reported as a candidate)
            app = reader.app()
            assert app is not None
            windows = {w: session.name(*w) for w in session.children(*app)}
            # tre 0.6.11 names the window node of a layer surface after its namespace
            catcher = "tesserae-shell.catcher.Launcher"
            named = sorted(n for n in windows.values() if n and n != catcher)
            assert named == ["Launcher", "Top Bar"], windows
            (bare,) = [w for w, n in windows.items() if not n or n == catcher]
            assert session.children(*bare) == [], "the click catcher has a child in the tree"
            assert not session.states(*bare) & {FOCUSED, SELECTED}, (
                "and it is neither focused nor selected"
            )

            # -- 1 and 3: the active descendant, and where focus is --
            def selected() -> list[str]:
                return [n for n, node in reader.rows() if SELECTED in reader.states(node)]

            def focused_rows() -> list[str]:
                return [n for n, node in reader.rows() if FOCUSED in reader.states(node)]

            field = reader.of(ENTRY, "Search applications")
            assert field is not None
            until(lambda: selected() == ["Fake One"], "the first row selected")
            reach(private_sway, shell)  # sway gives the exclusive surface the keyboard: one Down
            # tre moves the AT-SPI focused state to the active descendant, and back: the row
            # holds it, the field does not (the keyboard and caret stay in the field)
            until(lambda: selected() == ["Fake Two"], "Down selects the second row")
            until(lambda: focused_rows() == ["Fake Two"], "and the relation follows it")
            assert FOCUSED not in reader.states(field)
            keys(private_sway, "-k", "Up")
            until(lambda: selected() == ["Fake One"] and focused_rows() == ["Fake One"], "Up")
            # typing narrows the list: the relation is on the new first row
            keys(private_sway, "fake")
            until(lambda: [n for n, _ in reader.rows()] == ["Fake One", "Fake Two"], "narrowed")
            until(lambda: focused_rows() == ["Fake One"], "the relation on the first result")
            # no result: the relation is cleared and the field has the focused state again
            keys(private_sway, "zzz")
            until(lambda: reader.rows() == [], "no rows")
            field = reader.of(ENTRY, "Search applications")
            assert field is not None
            until(lambda: FOCUSED in reader.states(field), "the field is focused again")
            # Escape clears the field and a second one hides the Launcher (unchanged)
            keys(private_sway, "-k", "Escape")
            shell.wait_for("escape: the field is cleared")
            keys(private_sway, "-k", "Escape")
            shell.wait_for("escape: the panel hides")
            shell.process.send_signal(signal.SIGTERM)
            assert shell.finish() == 0
        finally:
            holder.terminate()
            holder.wait(timeout=10)
            if shell.process.poll() is None:
                shell.process.kill()
        events = state_events(states.lines(), reader.names)
        spoken = said.announcements()
        moved = active.lines()
    finally:
        session.close()
    # the signals, in the order they were sent: a Down moves "selected" and then the focused state
    # (the AT-SPI form of the active descendant) from one row to the next, and an Up back
    assert in_order(
        events,
        [
            {("Fake One", "focused", 1)},  # the Launcher opens with the relation on the first row
            {("Fake One", "selected", 0), ("Fake Two", "selected", 1)},  # Down
            {("Fake Two", "focused", 1), ("Fake One", "focused", 0)},
            {("Fake One", "selected", 1), ("Fake Two", "selected", 0)},  # Up
            {("Fake One", "focused", 1), ("Fake Two", "focused", 0)},
            {("Search applications", "focused", 1)},  # no result: the field has it again
        ],
    ), events
    # tre (AccessKit) expresses the relation by moving the focused state, not by this signal
    assert moved == [], moved
    # ctx.announce: once per change, polite, the row with its place (the documented fallback of
    # the relation: a screen reader hears the row as the focused item AND as this announcement)
    assert spoken == [("Fake Two, 2 of 3", 1), ("Fake One, 1 of 3", 1), ("No results", 1)], spoken


def in_order(events: list[tuple[str, str, int]], groups: list[set[tuple[str, str, int]]]) -> bool:
    """Whether every group comes, in order, after the one before: the signals of one group may
    arrive in either order (the two sides of one move), the groups may not."""
    position = 0
    for group in groups:
        found = []
        for want in group:
            at = next((i for i in range(position, len(events)) if events[i] == want), None)
            if at is None:
                return False
            found.append(at)
        position = max(found) + 1 if len(group) > 1 else found[0] + 1
    return True


def state_events(lines: list[str], names: dict[str, str]) -> list[tuple[str, str, int]]:
    """``(object name, state, 1 or 0)`` of each ``StateChanged`` signal, in order."""
    out = []
    for line in lines:
        try:
            message = json.loads(line)
            state, on = message["payload"]["data"][0], message["payload"]["data"][1]
        except ValueError, KeyError, IndexError, TypeError:
            continue
        out.append((names.get(message["path"], message["path"][-8:]), state, on))
    return out
