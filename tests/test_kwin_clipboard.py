"""Ctrl+C on a selected Text reaches the real clipboard of a real compositor (private KWin; nothing
reaches the real session): ``tests/kwin/probe_clipboard.py`` selects a word of a selectable Text and
runs the shell's ``copy_selection``; ``wl-paste`` (when installed) and tre's ``read_clipboard`` read
back what the compositor holds."""

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
PROBE = Path(__file__).parent / "kwin" / "probe_clipboard.py"


def test_the_selection_of_a_text_is_on_the_clipboard_of_a_real_compositor() -> None:
    with kitlib.private_bus() as bus, kitlib.private_kwin(bus) as kwin:
        process = subprocess.Popen(
            [sys.executable, str(PROBE)],
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
        seen = json.loads(out.strip().splitlines()[-1])
        print(seen)
        assert seen.get("copied") is True, seen
        assert seen.get("read_back") == "clipboard", seen
