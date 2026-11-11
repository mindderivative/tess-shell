"""A real (virtual) pointer for live tests on the private sway: events the compositor delivers
through the surface's input region, which ``Window.simulate`` does not go through.

A headless sway has no pointer, so a client is offered no ``wl_pointer`` and ``wlrctl`` makes and
drops its device too fast to be noticed. tre's test helper keeps one ``zwlr_virtual_pointer_v1``
alive; it needs ``pywayland``, which the shell's environment does not have, so it runs in tre's
own virtual environment (``$TRE_DIR``, default ``~/Projects/rustDev/projects/tre``). ``available()``
says whether that exists."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

TRE = Path(os.environ.get("TRE_DIR", Path.home() / "Projects/rustDev/projects/tre"))
PYTHON = TRE / ".venv" / "bin" / "python"
SERVER = Path(__file__).with_name("pointer_server.py")


def available() -> bool:
    return PYTHON.exists() and (TRE / "tests" / "wlr_pointer.py").exists()


class VirtualPointer:
    def __init__(self, env: dict[str, str], width: int, height: int) -> None:
        self.size = (width, height)
        env = {**env, "TRE_TESTS": str(TRE / "tests")}
        self.process = subprocess.Popen(
            [str(PYTHON), str(SERVER)],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        assert self.process.stdout is not None
        assert self.process.stdout.readline().strip() == "ready"

    def _send(self, line: str) -> None:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        assert self.process.stdout.readline().strip() == "done"

    def move(self, x: int, y: int, settle: float = 0.05) -> None:
        self._send(f"move {x} {y} {self.size[0]} {self.size[1]}")
        time.sleep(settle)

    def down(self) -> None:
        self._send("down")

    def up(self) -> None:
        self._send("up")

    def click(self) -> None:
        self._send("click")

    def close(self) -> None:
        try:
            self._send("quit")
        except Exception:  # the helper ends on quit without an answer
            pass
        self.process.kill()
