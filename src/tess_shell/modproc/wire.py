"""The pipe between the shell and one module process.

FORMAT: JSON lines over one ``AF_UNIX`` ``SOCK_STREAM`` socketpair (one object per line, UTF-8; a
newline inside a value is escaped by ``json.dumps``). JSON because the payloads are small and plain,
a line is greppable in a failure, the standard library parses it at about a million small objects a
second, and it is safe to read from a less trusted process: **the shell never unpickles or evaluates
anything a child sends**. What JSON lacks is tagged, so a value comes out as it went in:

* ``{"$b": "<base64>"}`` bytes (a tray icon's pixmap);
* ``{"$t": [...]}`` a tuple (a D-Bus call with several results is a tuple, and a module tells the
  two apart);
* ``{"$d": [[k, v], ...]}`` a dict with a key that is not a string (JSON would turn it into text),
  and also a dict whose only key is one of these tags.

A socketpair rather than two pipes: one descriptor each side, both directions, and a closed peer
reads as end of file on both sides, which is how a crashed process is noticed at once.

``Channel.send`` never blocks the caller: the line is encoded and queued, and a writer thread joins
whatever is queued into one ``sendall`` (under load many values become one syscall; idle, the writer
sleeps on a condition). The queue has a byte cap: past it the channel is closed with
``reason == "overflow"`` (the peer is not reading: for the shell, the child is hung). A line over
:data:`MAX_LINE` bytes, or one that is not JSON, is a protocol error: the line is dropped, and
:data:`MAX_BAD_IN_A_ROW` of them in a row close the channel with ``reason == "protocol"``.

Standard library only.
"""

from __future__ import annotations

import base64
import json
import socket
import threading
from collections import deque
from collections.abc import Callable
from typing import Any

MAX_LINE = 16 * 1024 * 1024  # bytes in one line (an icon pixmap is a few hundred KB)
QUEUE_CAP = 8 * 1024 * 1024  # bytes waiting to be written before the peer counts as not reading
MAX_BAD_IN_A_ROW = 3  # undecodable or oversize lines in a row that close the channel

_TAGS = ("$b", "$t", "$d")


def _tag(value: Any) -> Any:
    """``value`` with what JSON lacks tagged (tuples, bytes, dicts with other than string keys)."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, tuple):
        return {"$t": [_tag(v) for v in value]}
    if isinstance(value, list):
        return [_tag(v) for v in value]
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value) and not (
            len(value) == 1 and next(iter(value)) in _TAGS
        ):
            return {k: _tag(v) for k, v in value.items()}
        return {"$d": [[_tag(k), _tag(v)] for k, v in value.items()]}
    if isinstance(value, bytes | bytearray | memoryview):
        return {"$b": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, set | frozenset):
        return [_tag(v) for v in sorted(value)]
    raise TypeError(f"{type(value).__name__} cannot cross the pipe")


def _hook(obj: dict[str, Any]) -> Any:
    if len(obj) == 1:
        if "$t" in obj and isinstance(obj["$t"], list):
            return tuple(obj["$t"])
        if "$b" in obj and isinstance(obj["$b"], str):
            return base64.b64decode(obj["$b"])
        if "$d" in obj and isinstance(obj["$d"], list):
            return {_key(k): v for k, v in obj["$d"]}
    return obj


def _key(k: Any) -> Any:
    return tuple(k) if isinstance(k, list) else k


def encode(message: dict[str, Any]) -> bytes:
    """One line, tagged: for everything but the hot path."""
    return json.dumps(_tag(message), separators=(",", ":")).encode() + b"\n"


def encode_plain(message: dict[str, Any]) -> bytes:
    """One line with no tagging pass: for a message whose payload was checked to be plain data (a
    ``ctx.send`` value: strings, numbers, booleans, lists and dicts with string keys)."""
    return json.dumps(message, separators=(",", ":")).encode() + b"\n"


def decode(line: bytes) -> dict[str, Any]:
    result = json.loads(line, object_hook=_hook)
    if not isinstance(result, dict):
        raise ValueError("a message is a JSON object")
    return result


class Channel:
    """One end of the socketpair. ``on_message(message)`` runs on the reader thread;
    ``on_close()`` once, on the reader thread, when the peer is gone or :meth:`close` was called;
    ``reason`` then says why: ``"eof"``, ``"closed"``, ``"overflow"`` or ``"protocol"``.
    ``on_bad(text)`` hears each line that was dropped."""

    def __init__(
        self,
        sock: socket.socket,
        on_message: Callable[[dict[str, Any]], None],
        on_close: Callable[[], None],
        name: str,
        *,
        on_bad: Callable[[str], None] | None = None,
        queue_cap: int = QUEUE_CAP,
        max_line: int = MAX_LINE,
    ) -> None:
        self._sock = sock
        self._on_message = on_message
        self._on_close = on_close
        self._on_bad = on_bad
        self._queue_cap = queue_cap
        self._max_line = max_line
        self._queue: deque[bytes] = deque()
        self._queued = 0
        self._writing = False
        self._cond = threading.Condition()
        self._closed = False
        self.reason = ""
        self._reader = threading.Thread(target=self._read, name=f"{name}-read", daemon=True)
        self._writer = threading.Thread(target=self._write, name=f"{name}-write", daemon=True)

    def start(self) -> None:
        self._reader.start()
        self._writer.start()

    @property
    def closed(self) -> bool:
        return self._closed

    def send(self, message: dict[str, Any], *, plain: bool = False) -> bool:
        """Queue ``message``; False (and nothing queued) once the channel is closed. An object that
        cannot be encoded raises ``TypeError`` here, in the caller, not in the writer thread."""
        return self.send_bytes(encode_plain(message) if plain else encode(message))

    def send_bytes(self, data: bytes) -> bool:
        with self._cond:
            if self._closed:
                return False
            self._queue.append(data)
            self._queued += len(data)
            overflow = self._queued > self._queue_cap
            self._cond.notify()
        if overflow:
            self.close("overflow")
            return False
        return True

    def drain(self, timeout: float) -> None:
        """Wait until everything queued has been written (a process about to exit)."""
        with self._cond:
            self._cond.wait_for(
                lambda: self._closed or (not self._queue and not self._writing), timeout
            )

    def close(self, reason: str = "closed") -> None:
        with self._cond:
            if not self.reason:
                self.reason = reason
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
                self._queued = 0
                self._writing = True
            try:
                self._sock.sendall(batch)
            except OSError:
                self.close("eof")
                return
            finally:
                with self._cond:
                    self._writing = False
                    self._cond.notify_all()

    def _bad(self, text: str) -> bool:
        """A line was dropped; True when the channel gave up on the peer."""
        self._bad_in_a_row += 1
        if self._on_bad is not None:
            self._on_bad(text)
        if self._bad_in_a_row >= MAX_BAD_IN_A_ROW:
            self.close("protocol")
            return True
        return False

    _bad_in_a_row = 0

    def _read(self) -> None:
        try:
            with self._sock.makefile("rb", buffering=1 << 16) as stream:
                limit = self._max_line
                while True:
                    line = stream.readline(limit + 1)
                    if not line:
                        break
                    if len(line) > limit and not line.endswith(b"\n"):
                        # too long: throw the rest of the line away, and count it
                        while True:
                            rest = stream.readline(1 << 16)
                            if not rest or rest.endswith(b"\n"):
                                break
                        if self._bad(f"a line over {limit} bytes"):
                            break
                        continue
                    try:
                        message = decode(line)
                    except ValueError as exc:
                        if self._bad(f"not a message ({exc})"):
                            break
                        continue
                    self._bad_in_a_row = 0
                    self._on_message(message)
        except OSError:
            pass
        finally:
            self.close("eof")
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
