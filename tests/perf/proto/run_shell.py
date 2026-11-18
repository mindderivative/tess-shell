"""``tesserae-shell`` with the posture prototype switched on by the environment (not collected by
pytest). Everything after the module name is the shell's own command line::

    TESS_PROTO_POSTURE=B TESS_PROTO_SERVICES=B2 python -m tests.perf.proto.run_shell run --config-dir D

Read ONLY here and in ``parent.install``:

* ``TESS_PROTO_POSTURE``: ``A`` (default: nothing is patched), ``B`` or ``C``;
* ``TESS_PROTO_SERVICES``: ``B1`` (default) or ``B2``;
* ``TESS_PROTO_PROBE_OUT``: a file; each time the value store hands a value of the ``Probe`` module's
  ``probe`` key to the surfaces, one line ``<monotonic ns after the property set> <value>`` is
  appended (the harness's clock for the value-to-screen latency; the value carries the send time);
* ``TESS_PROTO_WATCH``: the watchdog's poll interval in seconds (default 1.0).

Posture A WITHOUT a probe is the product unchanged: the harness measures start, idle and memory of A
with plain ``python -m tess_shell run``, not with this wrapper.
"""

from __future__ import annotations

import os
import sys
import time


def install_probe(path: str) -> None:
    from tess_shell.model.store import ValueStore

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_APPEND, 0o600)
    original = ValueStore._turn
    last: dict[str, str] = {}

    def _turn(self: ValueStore) -> None:
        original(self)  # the flush and the surfaces' property set (``on_change``)
        done = time.monotonic_ns()
        for use in self._uses.get("Probe", ()):
            value = self.values.get(use, {}).get("probe")
            if isinstance(value, str) and last.get(use) != value:
                last[use] = value
                os.write(fd, f"{done} {value}\n".encode())

    ValueStore._turn = _turn  # type: ignore[method-assign]


def main() -> int:
    posture = os.environ.get("TESS_PROTO_POSTURE", "A")
    services = os.environ.get("TESS_PROTO_SERVICES", "B1")
    if posture != "A":
        from tests.perf.proto.parent import install

        install(posture, services)
    probe = os.environ.get("TESS_PROTO_PROBE_OUT")
    if probe:
        install_probe(probe)
    from tess_shell.cli import main as cli

    return cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
