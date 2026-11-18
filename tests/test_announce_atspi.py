"""What a screen reader hears from a module's ``ctx.announce``, read from the real AT-SPI
``Announcement`` signals (tre 0.6.9, ``Window.announce``): a real shell on a private headless sway,
publishing its accessibility tree on a private AT-SPI bus (``tests/atspi_env.py``) where ``busctl``
plays the screen reader. Nothing here reaches the user's session, the real accessibility bus or a
real screen reader; Orca itself is the maintainer's check (M7g)."""

from __future__ import annotations

import signal
from pathlib import Path

import pytest

from tests import atspi_env
from tests.shell_samples import BODY, HEADER, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not atspi_env.available(), reason="no private AT-SPI environment"),
]

SETTINGS = (
    "---\nTDL: 0.2\nName: Settings\n---\n"
    "Settings { Logging { Level: DEBUG }  Appearance { Follow_Desktop: false } }\n"
)

VISIBLE = 'Module { FlexBox { Children { Text { Text: "visible" } } } }'
HIDDEN = 'Module { FlexBox { Visible: false, Children { Text { Text: "hidden" } } } }'

SAY_PY = """
import os
from tess_shell import Module


class {name}(Module):
    def start(self):
        self.ticks = 0
        self.ctx.on_tick("second", self.tick)

    def tick(self):
        if not os.path.exists({go!r}):
            return  # the screen reader is not on yet
        self.ticks += 1
        self.ctx.announce("{name} says one")
        self.ctx.announce("{name} says one")  # the same words twice running: each is heard
        self.ctx.announce("{name} urgent", politeness="assertive")
        self.ctx.log.info("{name} tick %d" % self.ticks)
"""


def module(config: Path, name: str, layout: str, go: Path) -> None:
    folder = config / "Modules" / name
    folder.mkdir(parents=True)
    (folder / f"{name}_Module.tdl").write_text(HEADER.replace("Main_Shell", name) + layout)
    (folder / f"{name}_Module.py").write_text(SAY_PY.format(name=name, go=str(go)))


def test_a_module_is_heard_with_its_politeness_repeats_included_and_when_its_block_is_hidden(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    go = tmp_path / "reader-is-on"
    clock = 'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }'
    write_example(tmp_path, BODY.replace(clock, "Seen { }  Unseen { }"))
    (tmp_path / "settings.tdl").write_text(SETTINGS)
    module(tmp_path, "Seen", VISIBLE, go)
    module(tmp_path, "Unseen", HIDDEN, go)
    reader = atspi_env.AtspiEnvironment()
    try:
        heard = reader.monitor("Announcement")
        shell = Shell(tmp_path, {**private_sway.env, **reader.env()})
        try:
            shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")
            reader.enable()  # what turning a screen reader on does
            go.touch()
            shell.wait_for("Seen tick 8", timeout=60)  # the announcements are repeated each second
            shell.wait_for("Unseen tick 8", timeout=60)
            shell.process.send_signal(signal.SIGTERM)
            assert shell.finish() == 0
        finally:
            if shell.process.poll() is None:
                shell.process.kill()
        said = heard.announcements()
    finally:
        reader.close()
    for name in ("Seen", "Unseen"):  # a module whose block is hidden is heard too
        assert said.count((f"{name} says one", 1)) >= 2, said  # polite is 1; repeats each heard
        assert (f"{name} urgent", 2) in said, said  # assertive is 2
        assert not any(t.startswith(name) and p not in (1, 2) for t, p in said)
