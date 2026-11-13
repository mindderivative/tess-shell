"""Run the ``audio_sandbox`` tests of the sound client, service and module against a PRIVATE
PipeWire stack, inside the bwrap sandbox of the T-018 spike (``guard.reexec_in_sandbox``):

    env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.spikes.audio.run_sandbox_tests [args]

Outside the sandbox those tests refuse to run (``tests/test_audio_sandbox.py`` calls
``guard.require_sandbox()`` first), and a normal ``pytest`` deselects them (marker
``audio_sandbox``).
"""

from __future__ import annotations

import sys

from tests.spikes.audio.guard import reexec_in_sandbox

if __name__ == "__main__":
    reexec_in_sandbox("tests.spikes.audio.run_sandbox_tests")  # never returns outside the sandbox
    import pytest

    sys.exit(
        pytest.main(
            [
                "-m",
                "audio_sandbox",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "tests/test_audio_sandbox.py",
                *sys.argv[1:],
            ]
        )
    )
