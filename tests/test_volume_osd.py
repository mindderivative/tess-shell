"""The shipped Volume_OSD module (M7h): a click-through Panel that shows for a moment when the
default output's volume or mute changes. The module runs on the real sound service over the
in-process fake PulseAudio server (``tests/fake_pulse.py``), in the headless shell of
``tests/widgets_live.py``; time is the window's own clock (``window.advance``), so no test sleeps
for a Panel to go away. No real sound server, session or compositor is involved."""

from __future__ import annotations

import importlib.util
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any

import pytest

from tess_shell.files.icons import IconSets
from tess_shell.services import audio as audio_service
from tess_shell.services.api import AudioState, Output
from tess_shell.services.audio import AudioService
from tess_shell.services.bus import ServiceThread
from tests.fake_pulse import FakePulse
from tests.launcher_rig import Loop
from tests.test_accessibility import listen
from tests.widgets_live import SHIPPED, Widgets, running

NAME = "Razer Leviathan V2 X"
PANEL = (
    "Panel { Name: Volume_Panel, Layer: OVERLAY, Keyboard: NONE, Input_Region: [], "
    "Visible: false, Anchor: [BOTTOM], Inset: [0, 0, 0, 80], Width: 300, Height: 64, "
    "%s Children { Volume_OSD { %s } } }"
)
BAR = "Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, Children { %s } }"


def load() -> ModuleType:
    path = SHIPPED / "Volume_OSD" / "Volume_OSD_Module.py"
    spec = importlib.util.spec_from_file_location("shipped_volume_osd", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V = load()
SETS = IconSets([SHIPPED / "Icons"])


def shell_text(
    panel: str = "", params: str = "", bar: str = "Rectangle { Width: 4, Height: 4 }"
) -> str:
    return (
        "Shell { Monitor { Name: Main, Index: 0, Children { "
        + BAR % bar
        + " "
        + PANEL % (panel, params)
        + " } } }"
    )


# -- the derivations ----------------------------------------------------------------------------


def test_every_icon_the_python_can_send_is_in_the_shipped_mdi_set() -> None:
    missing = sorted(name for name in V.ICONS if SETS.lookup(f"mdi:{name}") is None)
    assert missing == [], f"not in the shipped mdi set: {missing}"
    seen = {V.level_icon(v, m) for v in (0, 1, 33, 34, 66, 67, 100, 130) for m in (False, True)}
    assert seen == set(V.ICONS)  # every name is reachable


@pytest.mark.parametrize(
    ("volume", "muted", "icon"),
    [
        (0, False, "volume-mute"),
        (1, False, "volume-low"),
        (33, False, "volume-low"),
        (34, False, "volume-medium"),
        (66, False, "volume-medium"),
        (67, False, "volume-high"),
        (130, False, "volume-high"),
        (50, True, "volume-off"),
        (0, True, "volume-off"),
    ],
)
def test_the_icon_table(volume: int, muted: bool, icon: str) -> None:
    assert V.level_icon(volume, muted) == icon


def test_the_values_for_a_muted_and_an_amplified_output() -> None:
    output = Output("razer", NAME, "SPEAKER")
    muted = V.values(AudioState(output, 45, True, False, False, (output,)))
    assert (muted["readout"], muted["icon"], muted["bar"]) == ("Muted", "volume-off", 45)
    assert muted["label"] == f"Volume, {NAME}, muted"
    loud = V.values(AudioState(output, 130, False, False, False, (output,)))
    # the server may say more than 100: the text says so, the bar stops at its end
    assert (loud["readout"], loud["bar"], loud["volume"]) == ("130 %", 100, 130)
    assert loud["label"] == f"Volume, {NAME}, 130 %"


# -- the module on the fake server ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio_service, "SHORT_SESSION", 0.0)


def desktop(fake: FakePulse) -> None:
    """Two outputs (the Razer is the default) and a microphone, the server up."""
    fake.add_sink("main", "Mainboard", bus="pci", percent=60)
    fake.add_sink("razer", NAME, bus="usb", percent=45, default=True)
    fake.add_source("mic", "Microphone")
    fake.start()


class Desk:
    def __init__(self, fake: FakePulse, loop: Loop, w: Widgets) -> None:
        self.fake, self.loop, self.w = fake, loop, w
        self.seen: list[AudioState | None] = []  # the states the service handed over, in order

    @property
    def panel(self) -> Any:
        return self.w.surface("Volume_Panel")

    @property
    def window(self) -> Any:
        return self.panel.window

    @property
    def shown(self) -> bool:
        return not self.panel.hidden

    @property
    def shows(self) -> int:
        """How many times the Panel was shown, from the surface's own log line (a Panel that was
        shown and went away again is no longer to be seen by ``shown``)."""
        return sum(1 for x in self.w.lines if "Panel Volume_Panel" in x and " shown (" in x)

    def values(self) -> dict[str, Any]:
        (key,) = [u for u in self.w.uses if u.startswith("Volume_OSD@")]
        return dict(self.w.store.values[key])

    def settle(self, predicate: Callable[[], object], timeout: float = 5.0) -> bool:
        """Be the loop until ``predicate`` holds: drain what the service thread handed over, flush
        the values and draw. It moves the Panel's clock by one millisecond a round, never by a
        fixed wait."""
        deadline = time.monotonic() + timeout
        while True:
            self.loop.drain()
            self.w.flush()
            self.window.advance(1)
            if predicate():
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.004)

    def heard(self, predicate: Callable[[AudioState | None], bool]) -> bool:
        """The module has been told a state that ``predicate`` accepts (the test's own subscriber is
        registered after the module's, so the module has handled it when this is true)."""
        return self.settle(lambda: any(predicate(s) for s in list(self.seen)))

    def run(self, ms: float) -> None:
        """Let ``ms`` of the Panel's own time pass (its ``Hide_After`` timer runs on it)."""
        self.loop.drain()
        self.window.advance(ms)
        self.w.flush()

    def node(self, suffix: str) -> Any:
        return self.w.of_use("Volume_OSD", suffix)

    def bar(self) -> Any:
        """The root block of the ProgressBar the module calls ``Bar``."""
        return self.w.of_use("ProgressBar", "Root")


@contextmanager
def osd(fake: FakePulse, text: str | None = None, **kwargs: Any) -> Iterator[Desk]:
    thread = ServiceThread()
    thread.start()
    audio = AudioService(thread, fake.socket, env={})  # the fake's socket, and no environment
    loop = Loop()
    try:
        with running(
            "",
            body=text or shell_text(),
            home="Volume_Panel",
            audio=audio,
            call_soon=loop.call_soon,
            **kwargs,
        ) as w:
            d = Desk(fake, loop, w)
            sub = w.host.loaded["Volume_OSD"].ctx.audio.on_changed(d.seen.append)
            try:
                assert d.settle(lambda: d.values()["name"] == NAME), w.log()
                yield d
            finally:
                sub.cancel()
                w.host.stop_all()
    finally:
        thread.stop()


def test_nothing_is_shown_at_start_and_the_first_reading_is_the_baseline(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse) as d:
        assert d.values()["volume_text"] == "45 %"  # it has read the server
        assert d.heard(lambda s: s is not None and s.volume == 45)
        d.run(5000)
        assert d.shown is False and d.shows == 0
        assert d.panel.window.root.get("visible") is False
        assert d.w.warnings() == []


def test_a_volume_change_shows_the_panel_with_the_new_level_and_click_through_no_keyboard(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse) as d:
        fake_pulse.set_volume("razer", 80)
        assert d.settle(lambda: d.shown), d.w.log()
        assert d.window.root.get("visible") is True
        # a click-through surface that never takes the keyboard, over everything
        assert d.window.get("input_region") == []
        assert d.window.get("keyboard") == "none"
        assert d.panel.planned.bar.layer == "OVERLAY"
        assert d.settle(lambda: d.values()["volume"] == 80)
        assert d.node("Value").get("text") == "80 %"
        assert d.node("Output").get("text") == NAME
        assert d.bar().get("value") == 80
        assert d.node("Root").get("label") == f"Volume, {NAME}, 80 %"
        assert d.w.warnings() == []


def test_a_mute_change_shows_the_panel_with_the_mute_state_and_so_does_unmuting(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse) as d:
        fake_pulse.set_mute("razer", True)
        assert d.settle(lambda: d.shown and d.node("Value").get("text") == "Muted"), d.w.log()
        # the state is in the word, in the icon's shape and in the bar's look, not in a colour
        assert d.values()["icon"] == "volume-off"
        assert d.bar().get("opacity") < 1
        assert d.node("Root").get("label") == f"Volume, {NAME}, muted"
        d.run(1500)
        assert d.shown is False
        fake_pulse.set_mute("razer", False)
        assert d.settle(lambda: d.shown and d.node("Value").get("text") == "45 %")
        assert d.bar().get("opacity") == 1


def test_it_hides_after_its_duration_and_a_change_in_that_time_starts_the_time_again(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse) as d:
        fake_pulse.set_volume("razer", 50)
        assert d.settle(lambda: d.shown and d.values()["volume"] == 50)
        d.run(1000)
        fake_pulse.set_volume("razer", 55)
        assert d.settle(lambda: d.values()["volume"] == 55)
        # 1000 ms after the first change is not yet the time of the second
        d.run(1000)
        assert d.shown is True
        d.run(400)
        assert d.shown is True  # 1400 ms after the second change
        d.run(200)
        assert d.shown is False  # past 1500 ms after it
        assert d.window.root.get("visible") is False
        fake_pulse.set_volume("razer", 60)
        assert d.settle(lambda: d.shown)  # and it comes back for the next change


def test_the_duration_param_is_the_time_and_replaces_the_panels_hide_after(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    text = shell_text(panel="Hide_After: 200,", params="duration: 3000")
    with osd(fake_pulse, text) as d:
        fake_pulse.set_volume("razer", 50)
        assert d.settle(lambda: d.shown and d.values()["volume"] == 50)
        d.run(2900)
        assert d.shown is True  # the Panel's own 200 ms did not hide it
        d.run(200)
        assert d.shown is False


@pytest.mark.parametrize("duration", ["0", "-5", "61000"])
def test_a_bad_duration_is_reported_at_load(fake_pulse: FakePulse, duration: str) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse, shell_text(params=f"duration: {duration}")) as d:
        assert [f.message for f in d.w.problems if "duration" in f.message], d.w.problems


def test_no_other_change_of_the_server_shows_it(fake_pulse: FakePulse) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse) as d:
        fake_pulse.set_source_mute("mic", True)  # the microphone
        assert d.heard(lambda s: s is not None and s.mic_muted)
        fake_pulse.set_volume("main", 10)  # an output that is not the default
        fake_pulse.set_default_sink("main")  # another default output: its volume is a new baseline
        assert d.heard(lambda s: s is not None and s.output is not None and s.output.name == "main")
        assert d.settle(lambda: d.values()["name"] == "Mainboard")
        d.run(100)
        assert d.shown is False and d.shows == 0
        # the new output is the baseline: its own changes show
        fake_pulse.set_volume("main", 25)
        assert d.settle(lambda: d.shown and d.values()["volume"] == 25)
        assert d.node("Output").get("text") == "Mainboard"


def test_when_the_server_goes_and_comes_back_the_first_reading_shows_nothing(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse) as d:
        fake_pulse.stop()
        assert d.heard(lambda s: s is None)
        fake_pulse.set_volume("razer", 70)  # while the server was away
        fake_pulse.start()
        assert d.settle(lambda: d.values()["volume"] == 70), d.w.log()
        d.run(100)
        assert d.shown is False and d.shows == 0


def test_it_announces_nothing_so_the_audio_modules_announce_is_said_once(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    text = shell_text(bar="Audio { announce: true }")
    with osd(fake_pulse, text) as d:
        said = listen(d.w)
        fake_pulse.set_mute("razer", True)
        assert d.settle(lambda: d.shown and "Muted" in said.texts)
        d.run(100)
        assert said.texts == ["Muted"]  # once, and by the Audio use
        assert all(key.startswith("Audio@") for keys, _, _ in said.calls for key in keys)


def test_the_accessibility_tree_is_a_named_group_with_one_named_progress_bar(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse) as d:
        fake_pulse.set_volume("razer", 30)
        assert d.settle(lambda: d.shown and d.values()["volume"] == 30)
        root, bar = d.node("Root"), d.bar()
        assert (root.get("role"), root.get("label")) == ("group", f"Volume, {NAME}, 30 %")
        assert (bar.get("role"), bar.get("label"), bar.get("value")) == (
            "progressbar",
            "Volume",
            30,
        )
        # said by the group's name: the icon and the two texts are not read again
        assert d.node("Glyph").get("a11y_hidden") is True
        assert d.node("Output").get("a11y_hidden") is True
        assert d.node("Value").get("a11y_hidden") is True
        # no live region: a screen reader is told only by the Audio module's `announce`
        assert not any(n.get("live") for n in d.w.view.nodes.values())
        assert d.window.get("keyboard") == "none"
        assert not any(n.get("focusable") for n in d.w.view.nodes.values())


def test_a_use_on_a_bar_says_it_once_and_leaves_the_bar_alone(fake_pulse: FakePulse) -> None:
    desktop(fake_pulse)
    text = (
        "Shell { Monitor { Name: Main, Index: 0, Children { "
        "Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, Children { Volume_OSD { } } } "
        "Panel { Name: Volume_Panel, Anchor: [BOTTOM], Width: 10, Height: 10 } } } }"
    )
    with osd(fake_pulse, text) as d:
        fake_pulse.set_volume("razer", 50)
        assert d.settle(lambda: d.values()["volume"] == 50)
        fake_pulse.set_volume("razer", 55)
        assert d.settle(lambda: d.values()["volume"] == 55)
        d.run(50)
        said = [x for x in d.w.lines if "is not on a Panel: put Volume_OSD" in x]
        assert len(said) == 1, d.w.log()


# -- ctx.surface.show, which the module is built on ---------------------------------------------


def test_surface_show_uses_the_panels_hide_after_unless_told_otherwise_and_names_a_miss(
    fake_pulse: FakePulse,
) -> None:
    desktop(fake_pulse)
    with osd(fake_pulse, shell_text(panel="Hide_After: 300,")) as d:
        ctx = d.w.host.loaded["Volume_OSD"].ctx
        (use,) = ctx.uses.values()
        assert ctx.surface.show(use) is True
        assert d.shown is True
        d.run(299)
        assert d.shown is True
        d.run(2)
        assert d.shown is False  # the Panel's own time
        assert ctx.surface.show(use, hide_after=700) is True
        d.run(600)
        assert d.shown is True
        d.run(200)
        assert d.shown is False  # the caller's time for that show
        # a miss is a False, not an exception: outside an action there is no use to default to
        assert ctx.surface.show() is False
        assert d.w.manager.show_use("Nothing@nowhere") is False
        assert d.shown is False
