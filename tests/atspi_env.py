"""A private AT-SPI environment for a live test of what a screen reader would hear.

Adapted from ``tests/atspi_env.py`` of tre (the same author and licence): it touches nothing of
the real desktop. Two throwaway ``dbus-daemon`` processes with no service directories (so nothing is
activated on them), a small stand-in for ``org.a11y.Bus`` on the session one (what
``at-spi-bus-launcher`` provides: the a11y bus's address and the ``IsEnabled`` switch that makes an
application publish its tree), and the real ``at-spi2-registryd`` on the a11y one. A shell started
with ``env()`` publishes its accessibility tree there once ``enable()`` is called, and ``busctl``
plays the screen reader.

Needs ``dbus-daemon``, ``busctl``, ``at-spi2-registryd`` and ``dbus-fast``; ``available()`` says
whether they are all here.

As a module it is the stand-in ``org.a11y.Bus`` process.
"""

# ruff: noqa: F821, UP037  (the quoted "s" and "b" are D-Bus signatures for dbus-fast)

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

# Arch keeps it in /usr/lib, Debian and Ubuntu in /usr/libexec.
REGISTRYD = next(
    (
        p
        for p in ("/usr/lib/at-spi2-registryd", "/usr/libexec/at-spi2-registryd")
        if os.path.exists(p)
    ),
    "/usr/lib/at-spi2-registryd",
)
CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=%s</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def available():
    try:
        import dbus_fast  # noqa: F401
    except ImportError:
        return False
    return bool(
        shutil.which("dbus-daemon") and shutil.which("busctl") and os.path.exists(REGISTRYD)
    )


class SignalLog:
    """What a `busctl monitor` printed. `busctl` buffers its output when piped and writes it when it
    exits, so reading stops the monitor first: call `lines()` or `announcements()` once, at the
    end."""

    def __init__(self, process):
        self._process = process
        self._lines = None

    def lines(self):
        if self._lines is None:
            self._process.terminate()
            try:
                out, _ = self._process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                out, _ = self._process.communicate()
            self._lines = [line.strip() for line in out.splitlines()]
        return list(self._lines)

    def announcements(self):
        """`[(text, politeness), ...]` of the `Announcement` signals so far (1 polite, 2
        assertive)."""
        out = []
        for line in self.lines():
            try:
                data = json.loads(line)["payload"]["data"]
            except ValueError, KeyError, TypeError:
                continue
            if len(data) >= 4 and isinstance(data[3], dict) and data[3].get("type") == "s":
                out.append((data[3]["data"], data[1]))
        return out


class AtspiEnvironment:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="tess-atspi-")
        self.processes = []
        self.session = self._daemon("session")
        self.a11y = self._daemon("a11y")
        mock = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), self.session, self.a11y],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.processes.append(mock)
        assert mock.stdout.readline().strip() == "ready", "the stand-in org.a11y.Bus did not start"
        registry = subprocess.Popen(
            [REGISTRYD],
            env=dict(os.environ, DBUS_SESSION_BUS_ADDRESS=self.session),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes.append(registry)
        self._wait_for_registry()

    def _wait_for_registry(self, timeout=20.0):
        """Until ``org.a11y.atspi.Registry`` owns its name on the a11y bus (no fixed sleep)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            out = subprocess.run(
                ["busctl", "--address=" + self.a11y, "--json=short", "list"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if "org.a11y.atspi.Registry" in out.stdout:
                return
            time.sleep(0.1)
        raise AssertionError("at-spi2-registryd did not start")

    def _daemon(self, name):
        directory = os.path.join(self.dir, name)
        os.mkdir(directory)
        config = os.path.join(self.dir, name + ".conf")
        with open(config, "w") as f:
            f.write(CONFIG % directory)
        process = subprocess.Popen(
            ["dbus-daemon", "--nofork", "--print-address", "--config-file=" + config],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.processes.append(process)
        return process.stdout.readline().strip()

    def env(self):
        """Only what an application needs to publish to this bus: the private session bus's address.
        Never the whole of ``os.environ``: merged over a private compositor's environment it would
        replace its ``XDG_RUNTIME_DIR`` with the real session's."""
        return {"DBUS_SESSION_BUS_ADDRESS": self.session}

    def enable(self, on=True):
        """What turning a screen reader on does: the application starts publishing its tree.
        ``enable(False)`` then ``enable()`` is a screen reader turned off and on again: an
        application that was not yet listening when the first one came hears the second."""
        subprocess.run(
            [
                "busctl",
                "--address=" + self.session,
                "set-property",
                "org.a11y.Bus",
                "/org/a11y/bus",
                "org.a11y.Status",
                "IsEnabled",
                "b",
                "true" if on else "false",
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )

    def call(self, destination, path, interface, method, *args):
        """A method call on the a11y bus, as the parsed JSON `data` list."""
        out = subprocess.run(
            [
                "busctl",
                "--address=" + self.a11y,
                "--json=short",
                "call",
                destination,
                path,
                interface,
                method,
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (
            json.loads(out.stdout)["data"] if out.returncode == 0 and out.stdout.strip() else None
        )

    def children(self, destination, path):
        """`[(bus name, object path), ...]` of an accessible's children."""
        data = self.call(destination, path, "org.a11y.atspi.Accessible", "GetChildren")
        return [tuple(c) for c in data[0]] if data else []

    def role(self, destination, path):
        """The AT-SPI role number (`ATSPI_ROLE_*`): 43 is a push button, 23 a frame."""
        data = self.call(destination, path, "org.a11y.atspi.Accessible", "GetRole")
        return data[0] if data else None

    def name(self, destination, path):
        data = self.call(
            destination,
            path,
            "org.freedesktop.DBus.Properties",
            "Get",
            "ss",
            "org.a11y.atspi.Accessible",
            "Name",
        )
        return data[0]["data"] if data else None

    def states(self, destination, path):
        """The AT-SPI state numbers (`ATSPI_STATE_*`: 12 focused, 23 selected) an accessible has,
        as a set."""
        data = self.call(destination, path, "org.a11y.atspi.Accessible", "GetState")
        if not data:
            return set()
        words = data[0]
        return {32 * i + b for i, w in enumerate(words) for b in range(32) if w >> b & 1}

    def do_action(self, destination, path, index=0):
        data = self.call(destination, path, "org.a11y.atspi.Action", "DoAction", "i", str(index))
        return bool(data and data[0])

    def tree(self, destination, path, depth=0, limit=6):
        """`[(depth, role, name, destination, path), ...]` of a subtree, for finding a node."""
        out = [
            (depth, self.role(destination, path), self.name(destination, path), destination, path)
        ]
        if depth < limit:
            for child_destination, child_path in self.children(destination, path):
                out += self.tree(child_destination, child_path, depth + 1, limit)
        return out

    def monitor(self, member):
        """Starts listening on the a11y bus for the `org.a11y.atspi.Event.Object` signal `member`
        (`Announcement`, say). Returns a `SignalLog`: its `.lines()` are the JSON of each one so
        far."""
        process = subprocess.Popen(
            [
                "busctl",
                "--address=" + self.a11y,
                "--json=short",
                "monitor",
                "--match",
                f"type='signal',interface='org.a11y.atspi.Event.Object',member='{member}'",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.processes.append(process)
        return SignalLog(process)

    def close(self):
        for process in reversed(self.processes):
            process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(self.dir, ignore_errors=True)


def _mock(session_address, a11y_address):  # pragma: no cover - runs in the child process
    import asyncio

    from dbus_fast import BusType  # noqa: F401
    from dbus_fast.aio import MessageBus
    from dbus_fast.constants import PropertyAccess
    from dbus_fast.service import ServiceInterface, dbus_property, method

    class Bus(ServiceInterface):
        def __init__(self):
            super().__init__("org.a11y.Bus")

        @method()
        def GetAddress(self) -> "s":
            return a11y_address

    class Status(ServiceInterface):
        def __init__(self):
            super().__init__("org.a11y.Status")
            self.enabled = False
            self.reader = False

        @dbus_property(access=PropertyAccess.READWRITE)
        def IsEnabled(self) -> "b":
            return self.enabled

        @IsEnabled.setter
        def IsEnabled(self, value: "b"):
            self.enabled = value
            self.emit_properties_changed({"IsEnabled": value})

        @dbus_property(access=PropertyAccess.READWRITE)
        def ScreenReaderEnabled(self) -> "b":
            return self.reader

        @ScreenReaderEnabled.setter
        def ScreenReaderEnabled(self, value: "b"):
            self.reader = value
            self.emit_properties_changed({"ScreenReaderEnabled": value})

    async def main():
        bus = await MessageBus(bus_address=session_address).connect()
        bus.export("/org/a11y/bus", Bus())
        bus.export("/org/a11y/bus", Status())
        await bus.request_name("org.a11y.Bus")
        print("ready", flush=True)
        await asyncio.get_event_loop().create_future()

    asyncio.run(main())


if __name__ == "__main__":
    _mock(sys.argv[1], sys.argv[2])
