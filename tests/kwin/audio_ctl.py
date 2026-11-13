"""``python audio_ctl.py CONTROL_SOCKET REQUEST...``: send one request line to the fake sound server
of the Audio KWin kit (``tests/kwin/fake_pulse_server.py``) and print its answer; exit 1 on an
error. Standard library only. Not collected by pytest."""

from __future__ import annotations

import socket
import sys


def main() -> int:
    path, *words = sys.argv[1:]
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(10)
        sock.connect(path)
        sock.sendall((" ".join(words) + "\n").encode())
        answer = sock.makefile().readline().strip()
    print(answer)
    return 1 if answer.startswith("error") else 0


if __name__ == "__main__":
    sys.exit(main())
