"""Telling systemd that the shell is ready or stopping (Shell Start and Stop > Telling Systemd).

The protocol of ``sd_notify(3)`` is one datagram on the Unix socket named by ``NOTIFY_SOCKET``, so
the shell needs no library for it. With the variable unset nothing is sent. A name that starts with
``@`` is an abstract socket (the first byte of the address is a NUL); any other must be an absolute
path. Standard library only: ``tess_shell.app`` calls it at the end of the start sequence and at
the start of the stop sequence.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Mapping

READY = "READY=1"
STOPPING = "STOPPING=1"

SEND_TIMEOUT = 1.0  # seconds; a full receive queue must not hold the start or the stop


def notify_address(environ: Mapping[str, str] | None = None) -> str | None:
    """The socket address ``NOTIFY_SOCKET`` names, as ``socket`` wants it (an abstract name
    begins with a NUL byte), or ``None`` when it is unset, empty or not a form systemd uses."""
    env = os.environ if environ is None else environ
    name = env.get("NOTIFY_SOCKET", "")
    if name.startswith("@"):
        return "\0" + name[1:]
    if name.startswith("/"):
        return name
    return None


def notify(state: str, environ: Mapping[str, str] | None = None) -> bool | None:
    """Send ``state`` (``READY=1``, ``STOPPING=1``) to ``NOTIFY_SOCKET``.

    ``None``: the variable is unset (or not an address): nothing was sent and nothing is wrong.
    ``True``: the datagram was sent. ``False``: the variable is set and the send failed; the shell
    logs it and goes on, since a unit that waits for READY=1 then times out by itself.
    """
    address = notify_address(environ)
    if address is None:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC) as sock:
            sock.settimeout(SEND_TIMEOUT)
            sock.sendto(state.encode("utf-8"), address)
    except OSError:
        return False
    return True
