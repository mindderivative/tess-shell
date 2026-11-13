"""Test configuration. A bare ``pytest`` never reaches the real desktop session.

The suite opens windows, starts shells, talks D-Bus, sends pointer events and reads the clipboard,
all of it on a private headless sway and private buses. A real ``WAYLAND_DISPLAY`` or ``DISPLAY``
in the environment could send any of that to the maintainer's own desktop (a test once did: the
real clipboard and the real pointer). So:

* a run with ``WAYLAND_DISPLAY`` or ``DISPLAY`` set is REFUSED, unless
  ``TESS_SHELL_TESTS_REAL_SESSION=1`` says the person running it knows (run the suite as
  ``env -u WAYLAND_DISPLAY -u DISPLAY pytest``);
* whatever the variable says, the process loses the real session bus, points the system bus at a
  socket that is not there, and gets a private runtime, state and config directory, so no test can
  write to the real ones. A test that needs a bus or a compositor makes its own (``PrivateSway``,
  ``tests/fake_dbus.py``); the real ``DBUS_*`` variables are never passed on.
"""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.sway import PrivateSway, SwayUnavailable

ALLOW = "TESS_SHELL_TESTS_REAL_SESSION"
_private: Path | None = None


def pytest_configure(config: pytest.Config) -> None:
    global _private
    shown = [v for v in ("WAYLAND_DISPLAY", "DISPLAY") if os.environ.get(v)]
    if shown and os.environ.get(ALLOW) != "1":
        pytest.exit(
            f"refusing to run: {', '.join(shown)} names a real display, and the suite could drive "
            f"it (windows, pointer, clipboard). Run: env -u WAYLAND_DISPLAY -u DISPLAY pytest "
            f"(or set {ALLOW}=1 if you mean it).",
            returncode=3,
        )
    _private = Path(tempfile.mkdtemp(prefix="tess-tests-"))
    os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = f"unix:path={_private}/no-system-bus"
    for name, sub in (
        ("XDG_RUNTIME_DIR", "run"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_CONFIG_HOME", "config"),
    ):
        path = _private / sub
        path.mkdir(mode=0o700)
        os.environ[name] = str(path)


def pytest_unconfigure(config: pytest.Config) -> None:
    if _private is not None:
        shutil.rmtree(_private, ignore_errors=True)


@pytest.fixture
def private_sway() -> Iterator[PrivateSway]:
    sway = PrivateSway()
    try:
        sway.start()
    except SwayUnavailable as exc:
        pytest.skip(str(exc))
    try:
        yield sway
    finally:
        sway.stop()
