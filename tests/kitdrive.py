"""Helpers for the drivers a kit runs (standard library only; copied into a kit folder as
``kitdrive.py`` by :func:`tests.kitlib.write_kit`): start the shell inside the step's sandbox, read
its log, press keys and click on a PRIVATE KWin, and report ``PASS name`` / ``FAIL name: why`` lines
that a step's expectation reads.

Everything here uses the environment the runner built for the step (a private bus, a private
runtime directory, ``WAYLAND_DISPLAY`` of the private compositor); nothing reaches a real session.
Input needs ``pywayland``: it runs in tre's virtual environment (``TRE_PY``), through KWin's own
``org_kde_kwin_fake_input`` (``fake_input_server.py``, beside this file)."""

from __future__ import annotations

import os
import queue
import re
import signal
import subprocess
import threading
import time
from collections.abc import Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: evdev key codes (linux/input-event-codes.h) of the keys the drivers press
KEYS: dict[str, int] = {
    "Escape": 1,
    "Backspace": 14,
    "Tab": 15,
    "Enter": 28,
    "Ctrl": 29,
    "Shift": 42,
    "Alt": 56,
    "Space": 57,
    "Home": 102,
    "Up": 103,
    "PageUp": 104,
    "End": 107,
    "Down": 108,
    "PageDown": 109,
    "Meta": 125,
    **{c: code for c, code in zip("1234567890", range(2, 12), strict=True)},
    **{c: code for c, code in zip("qwertyuiop", range(16, 26), strict=True)},
    **{c: code for c, code in zip("asdfghjkl", range(30, 39), strict=True)},
    **{c: code for c, code in zip("zxcvbnm", range(44, 51), strict=True)},
}
for _n in range(1, 13):
    KEYS[f"F{_n}"] = 58 + _n if _n <= 10 else 87 + (_n - 11)


class Timeout(Exception):
    pass


class Report:
    """``PASS name`` / ``FAIL name: why`` lines on standard output; ``code`` is the exit code."""

    def __init__(self) -> None:
        self.failures = 0

    def ok(self, name: str, detail: str = "") -> None:
        print(f"PASS {name}" + (f": {detail}" if detail else ""), flush=True)

    def fail(self, name: str, why: str) -> None:
        self.failures += 1
        print(f"FAIL {name}: {why}", flush=True)

    def check(self, name: str, condition: bool, why: str = "", detail: str = "") -> bool:
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, why or "the condition is false")
        return condition

    def note(self, text: str) -> None:
        print(f"NOTE {text}", flush=True)

    @property
    def code(self) -> int:
        return 1 if self.failures else 0


class ShellRun:
    """``tesserae-shell run`` in the step's environment; its standard error (the log and, with
    ``WAYLAND_DEBUG=1``, the protocol trace) is read by a thread into ``lines`` and into a file."""

    def __init__(
        self,
        binary: str,
        config: Path,
        env: Mapping[str, str],
        *,
        log: Path | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.binary = binary
        self.config = config
        self.env = {**env, **(extra_env or {})}
        self.lines: list[str] = []
        self.queue: queue.Queue[str] = queue.Queue()
        self.sink = open(log, "w") if log else None  # noqa: SIM115
        self.process = subprocess.Popen(
            [binary, "run", "--config-dir", str(config)],
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.queue.put(line)
            if self.sink:
                self.sink.write(line)
                self.sink.flush()

    def _drain(self) -> None:
        while True:
            try:
                self.lines.append(self.queue.get_nowait())
            except queue.Empty:
                return

    def wait_for(self, pattern: str, *, timeout: float = 40, after: int = 0) -> re.Match[str]:
        """The first line from index ``after`` on that matches ``pattern``; polls the log."""
        deadline = time.monotonic() + timeout
        regex = re.compile(pattern)
        seen = after
        while True:
            self._drain()
            while seen < len(self.lines):
                found = regex.search(self.lines[seen])
                seen += 1
                if found:
                    return found
            if time.monotonic() > deadline:
                raise Timeout(f"never saw /{pattern}/; the log ends:\n{self.tail()}")
            if self.process.poll() is not None and self.queue.empty():
                self._drain()
                if not any(regex.search(ln) for ln in self.lines[after:]):
                    raise Timeout(f"the shell ended; never saw /{pattern}/:\n{self.tail()}")
            time.sleep(0.05)

    def mark(self) -> int:
        """An index into the log: ``wait_for(..., after=mark)`` sees only later lines."""
        self._drain()
        return len(self.lines)

    def since(self, mark: int) -> list[str]:
        self._drain()
        return self.lines[mark:]

    def grep(self, pattern: str, after: int = 0) -> list[str]:
        regex = re.compile(pattern)
        return [ln.rstrip("\n") for ln in self.since(after) if regex.search(ln)]

    def tail(self, n: int = 25) -> str:
        self._drain()
        return "".join(self.lines[-n:])

    def stop(self, timeout: float = 15) -> int:
        """SIGTERM, then wait; kill when it does not end."""
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        time.sleep(0.2)
        self._drain()
        if self.sink:
            self.sink.close()
        return int(self.process.returncode)


def cli(
    binary: str, env: Mapping[str, str], *args: str, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    """``tesserae-shell ARGS`` in ``env`` (a command that talks to the running shell)."""
    return subprocess.run(
        [binary, *args],
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def gdbus(
    env: Mapping[str, str], dest: str, path: str, method: str, *args: str
) -> subprocess.CompletedProcess[str]:
    """``gdbus call`` on the step's (private) session bus."""
    return subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            dest,
            "--object-path",
            path,
            "--method",
            method,
            *args,
        ],
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class Input:
    """Pointer and keys on the private KWin (``fake_input_server.py`` in tre's Python)."""

    def __init__(self, tre_python: str, env: Mapping[str, str]) -> None:
        self.process = subprocess.Popen(
            [tre_python, str(HERE / "fake_input_server.py")],
            env=dict(env),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        assert self.process.stdout is not None
        first = self.process.stdout.readline().strip()
        if first != "ready":
            raise RuntimeError(f"the input helper did not start: {first!r}")

    def _send(self, line: str) -> None:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        if self.process.stdout.readline().strip() != "done":
            raise RuntimeError(f"the input helper did not answer {line!r}")

    def move(self, x: int, y: int) -> None:
        self._send(f"abs {x} {y}")

    def click(self, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self.move(x, y)
            time.sleep(0.1)
        self._send("click")

    def key(self, name: str) -> None:
        self._send(f"key {KEYS[name]}")

    def chord(self, *names: str) -> None:
        """The modifiers down in order, the last key pressed, the modifiers up."""
        *modifiers, last = names
        for name in modifiers:
            self._send(f"down {KEYS[name]}")
        self._send(f"key {KEYS[last]}")
        for name in reversed(modifiers):
            self._send(f"up {KEYS[name]}")

    def type(self, text: str) -> None:
        for char in text:
            if char == " ":
                self.key("Space")
            elif char.isupper():
                self.chord("Shift", char.lower())
            else:
                self.key(char)

    def close(self) -> None:
        try:
            self._send("quit")
        except Exception:  # the helper ends on quit without an answer
            pass
        self.process.kill()


def environ_file(path: Path) -> dict[str, str]:
    """A ``env`` dump (NUL or newline separated ``NAME=value``) as a dict."""
    text = path.read_text(errors="replace")
    sep = "\0" if "\0" in text else "\n"
    return dict(item.split("=", 1) for item in text.split(sep) if "=" in item)


def wait_file(path: Path, timeout: float = 20) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.05)
    return False


def _session(pid: str) -> int | None:
    try:
        with open(f"/proc/{pid}/stat") as handle:
            return int(handle.read().rsplit(")", 1)[1].split()[3])
    except OSError, ValueError, IndexError:
        return None


def kill_started(*needles: str) -> list[int]:
    """Kill every process whose command line names one of ``needles`` (the programs a step started
    and left running on purpose) and everything else in their sessions (a detached start makes its
    own, so its ``sleep`` goes too); returns the pids. Never this process or its session."""
    own = os.getsid(0)
    sessions: set[int] = set()
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                text = handle.read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        sid = _session(entry)
        if sid is not None and sid != own and any(needle in text for needle in needles):
            sessions.add(sid)
    killed: list[int] = []
    for entry in os.listdir("/proc"):
        if entry.isdigit() and _session(entry) in sessions:
            try:
                os.kill(int(entry), signal.SIGKILL)
                killed.append(int(entry))
            except OSError:
                pass
    return killed
