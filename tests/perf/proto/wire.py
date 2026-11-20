"""The pipe between the shell and one module process (prototype of posture B).

FORMAT: JSON lines over one ``AF_UNIX`` ``SOCK_STREAM`` socketpair (one object per line, UTF-8, no
newline inside a value because ``json.dumps`` escapes it). Chosen over a framed binary format
because the payloads are small and plain (a value is a string, a number, a boolean, a list or a
dict: the ``ctx.send`` contract), a line is greppable in a failure, and the standard library parses
it at about 1 million small objects a second; the one binary payload (a tray icon's pixmap bytes) is
tagged ``{"$b": "<base64>"}``. What JSON loses: the difference between a tuple and a list, and the
integer keys of a dict (they become text); both are listed in the report as part of the cost of B.

A socketpair rather than two pipes: one file descriptor each side, both directions, and a closed
peer reads as end of file on both sides, which is how a crashed process is noticed at once.

``Channel.send`` never blocks the caller: the object is encoded and put in a queue, and a writer
thread joins whatever is queued into one ``sendall``. Under load that batches many values into one
syscall; when idle the writer thread sleeps on a condition (no timer, no wake-up).
"""

from __future__ import annotations

import base64
import json
import socket
import threading
from collections import deque
from collections.abc import Callable
from typing import Any


def _default(value: object) -> Any:
    if isinstance(value, bytes | bytearray | memoryview):
        return {"$b": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, set | frozenset):
        return sorted(value)
    raise TypeError(f"{type(value).__name__} cannot cross the pipe")


def _hook(obj: dict[str, Any]) -> Any:
    if len(obj) == 1 and "$b" in obj:
        return base64.b64decode(obj["$b"])
    return obj


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":"), default=_default).encode() + b"\n"


def decode(line: bytes) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(line, object_hook=_hook)
    return result


class Channel:
    """One end of the socketpair. ``on_message(message)`` runs on the reader thread; ``on_close()``
    once, on the reader thread, when the peer is gone or :meth:`close` was called."""

    def __init__(
        self,
        sock: socket.socket,
        on_message: Callable[[dict[str, Any]], None],
        on_close: Callable[[], None],
        name: str,
    ) -> None:
        self._sock = sock
        self._on_message = on_message
        self._on_close = on_close
        self._queue: deque[bytes] = deque()
        self._cond = threading.Condition()
        self._closed = False
        self._reader = threading.Thread(target=self._read, name=f"{name}-read", daemon=True)
        self._writer = threading.Thread(target=self._write, name=f"{name}-write", daemon=True)

    def start(self) -> None:
        self._reader.start()
        self._writer.start()

    @property
    def closed(self) -> bool:
        return self._closed

    def send(self, message: dict[str, Any]) -> bool:
        """Queue ``message``; False (and nothing queued) once the channel is closed. An object that
        cannot be encoded raises ``TypeError`` here, in the caller, not in the writer thread."""
        data = encode(message)
        with self._cond:
            if self._closed:
                return False
            self._queue.append(data)
            self._cond.notify()
        return True

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _write(self) -> None:
        while True:
            with self._cond:
                while not self._queue and not self._closed:
                    self._cond.wait()
                if self._closed and not self._queue:
                    return
                batch = b"".join(self._queue)
                self._queue.clear()
            try:
                self._sock.sendall(batch)
            except OSError:
                self.close()
                return

    def _read(self) -> None:
        try:
            with self._sock.makefile("rb", buffering=1 << 16) as stream:
                for line in stream:
                    try:
                        message = decode(line)
                    except ValueError:
                        continue
                    self._on_message(message)
        except OSError:
            pass
        finally:
            self.close()
            self._on_close()


def encode_error(exc: BaseException) -> dict[str, Any]:
    """An exception as plain data: its class name, its message and the line in the module's own
    file where it was raised (0 when unknown)."""
    line = 0
    tb = exc.__traceback__
    while tb is not None:
        line = tb.tb_lineno
        tb = tb.tb_next
    return {"type": type(exc).__name__, "msg": str(exc), "line": line}
