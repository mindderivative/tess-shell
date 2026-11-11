"""A running shell, a module on ``ctx.dbus`` and a fake service on a private bus (M5a, A4 and A5 as
the shell runs them: the layer is wired in ``app.py``, the hooks reach the module on the loop).

The module logs what it sees; the test reads the shell's log. Private sway for the surface, a
private ``dbus-daemon`` for the bus; the real session bus is never touched.
"""

from __future__ import annotations

import signal
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON, fake_bus
from tests.shell_samples import BODY, HEADER, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [pytest.mark.tre, pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")]

SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\n"
    "Settings { Logging { Level: DEBUG }  Appearance { Follow_Desktop: false } }\n"
)

SVC_TDL = """
Module {
    FlexBox {
        Children {
            Text { Name: Always, Text: "svc" }
            If {{ available }} { Text { Name: Shown, Text: {{ percent }} } }
        }
    }
}
"""

SVC_PY = """
import threading
from tess_shell import Module


class Svc(Module):
    def start(self):
        proxy = self.ctx.dbus.session().proxy(
            "org.test.Battery", "/org/test/Battery", "org.test.Battery"
        )
        proxy.on_property_changed(self.changed)
        self.ctx.log.info("svc started")

    def changed(self, values):
        self.ctx.send("percent", f"{values['Percentage']:.0f}%")
        self.ctx.log.info(f"svc percent {values['Percentage']:.0f}")

    def on_service_lost(self, name):
        self.ctx.log.info(f"svc lost {name} on {threading.current_thread().name}")

    def on_service_found(self, name):
        self.ctx.log.info(f"svc found {name} on {threading.current_thread().name}")
"""


def test_a_module_follows_its_service_leaving_and_returning(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    with fake_bus() as bus:
        fake = bus.service("org.test.Battery")
        obj = fake.add(
            "/org/test/Battery", "org.test.Battery", properties={"Percentage": ("d", 50.0)}
        )
        fake.up()
        clock = 'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }'
        body = BODY.replace(clock, "Svc { }")
        write_example(tmp_path, body)
        (tmp_path / "settings.tdl").write_text(SETTINGS)
        folder = tmp_path / "Modules" / "Svc"
        folder.mkdir(parents=True)
        (folder / "Svc_Module.tdl").write_text(HEADER.replace("Main_Shell", "Svc") + SVC_TDL)
        (folder / "Svc_Module.py").write_text(SVC_PY)
        shell = Shell(tmp_path, {**private_sway.env, "DBUS_SESSION_BUS_ADDRESS": bus.address})
        try:
            shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")
            shell.wait_for("svc percent 50")
            fake.down()
            shell.wait_for("svc lost org.test.Battery on MainThread")  # the loop thread
            obj.silent_set("Percentage", 77.0)
            fake.up()
            shell.wait_for("svc found org.test.Battery on MainThread")
            shell.wait_for("svc percent 77")
            shell.process.send_signal(signal.SIGTERM)
            assert shell.finish() == 0
        finally:
            if shell.process.poll() is None:
                shell.process.kill()
    assert not any("| ERROR " in x for x in shell.seen), "".join(shell.seen)
