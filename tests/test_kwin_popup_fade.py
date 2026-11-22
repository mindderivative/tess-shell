"""The fade-out of a GRABBING popup on a real KWin (``kwin_wayland --virtual`` in a private session;
nothing reaches the real one): ``tests/kwin/probe_popup_fade.py`` opens a layer surface and a popup
with a grab, fades it out and closes its window when the fade ends, and says what it saw. What the
shell's Popup ``Animation: FADE`` relies on: the window closes when the fade ends (not before), tre
reports ``closed``, and nothing is left holding the keyboard."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests import kitlib

pytestmark = pytest.mark.skipif(
    shutil.which("kwin_wayland") is None or shutil.which("dbus-run-session") is None,
    reason="needs kwin_wayland and dbus-run-session",
)
PROBE = Path(__file__).parent / "kwin" / "probe_popup_fade.py"


def run_probe(fade_ms: int) -> list[list[object]]:
    with kitlib.private_bus() as bus, kitlib.private_kwin(bus) as kwin:
        process = subprocess.Popen(
            [sys.executable, str(PROBE), str(fade_ms)],
            env=kwin.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            out, err = process.communicate(timeout=40)
        finally:
            kitlib.stop_group(process)
        assert process.returncode == 0, err[-800:]
        return json.loads(out.strip().splitlines()[-1])  # type: ignore[no-any-return]


def named(events: list[list[object]], what: str) -> int:
    return int(next(t for w, t in events if str(w).startswith(what)))  # type: ignore[arg-type]


def test_a_grabbing_popup_closes_when_its_fade_ends_and_tre_says_closed() -> None:
    events = run_probe(200)
    print(events)
    asked = named(events, "fade out asked")
    ended = named(events, "fade ended")
    assert 150 <= ended - asked <= 600  # the window stayed for the fade, then closed
    names = [str(w) for w, _ in events]
    assert any(n.startswith("popup closed") for n in names), events
    assert named(events, "popup closed") >= ended  # not closed before the fade ended
