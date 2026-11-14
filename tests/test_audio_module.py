"""The shipped Audio module (Audio Module): the derivations, then the module on the in-process fake
PulseAudio server (``tests/fake_pulse.py``) through the real sound service, drawn by the real binder
in a headless Bar. No real sound server is involved (the fake's socket is the only one the service
is given)."""

from __future__ import annotations

import importlib.util
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from types import ModuleType
from typing import Any

import pytest

from tess_shell.files.icons import IconSets
from tess_shell.services import audio as audio_service
from tess_shell.services.api import AudioState, Output
from tess_shell.services.audio import AudioService
from tess_shell.services.bus import ServiceThread
from tess_shell.services.pulse_native import NORM
from tests.fake_dbus import wait_for
from tests.fake_pulse import FakePulse
from tests.widgets_live import SHIPPED, Widgets, running

TEXT = (228, 234, 241)  # $color.on_surface of the Default theme
MUTED = (159, 174, 191)  # $color.on_surface_muted
PORTS = [
    ("analog-output-speaker", "Speakers", "Speaker"),
    ("analog-output-headphones", "H", "Headphones"),
]


def load() -> ModuleType:
    path = SHIPPED / "Audio" / "Audio_Module.py"
    spec = importlib.util.spec_from_file_location("shipped_audio", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load()
SETS = IconSets([SHIPPED / "Icons"])


# -- the derivations ----------------------------------------------------------------------------


def test_every_icon_the_python_can_send_is_in_the_shipped_mdi_set() -> None:
    missing = sorted(name for name in A.ICONS if SETS.lookup(f"mdi:{name}") is None)
    assert missing == [], f"not in the shipped mdi set: {missing}"
    seen = {
        A.level_icon(kind, volume, muted)
        for kind in A.KIND_ICONS
        for volume in (0, 1, 33, 34, 66, 67, 100, 130)
        for muted in (False, True)
    } | set(A.KIND_ICONS.values())
    assert seen | {"microphone-off"} == set(A.ICONS)  # every name is reachable


@pytest.mark.parametrize(
    ("kind", "volume", "muted", "icon"),
    [
        ("SPEAKER", 0, False, "volume-mute"),
        ("SPEAKER", 1, False, "volume-low"),
        ("SPEAKER", 33, False, "volume-low"),
        ("SPEAKER", 34, False, "volume-medium"),
        ("SPEAKER", 66, False, "volume-medium"),
        ("SPEAKER", 67, False, "volume-high"),
        ("SPEAKER", 100, False, "volume-high"),
        ("SPEAKER", 130, False, "volume-high"),
        ("HDMI", 50, False, "volume-medium"),
        ("OTHER", 0, False, "volume-mute"),
        ("SPEAKER", 50, True, "volume-off"),
        ("HDMI", 0, True, "volume-off"),
        ("BLUETOOTH", 50, True, "volume-off"),
        ("HEADPHONES", 50, True, "headphones-off"),
        ("HEADPHONES", 0, False, "headphones"),
        ("HEADPHONES", 90, False, "headphones"),
        ("BLUETOOTH", 0, False, "bluetooth-audio"),
        ("BLUETOOTH", 90, False, "bluetooth-audio"),
    ],
)
def test_the_icon_table(kind: str, volume: int, muted: bool, icon: str) -> None:
    assert A.level_icon(kind, volume, muted) == icon


def test_the_tooltip_and_the_menu_entries() -> None:
    assert A.tooltip_text("Razer Leviathan V2 X", 45, False) == "Razer Leviathan V2 X, 45 %"
    assert A.tooltip_text("Razer", 45, True) == "Razer, muted"
    entry = A.output_entry(Output("hdmi-sink", "HDMI output", "HDMI"), True)
    assert entry == {
        "id": "hdmi-sink",
        "name": "HDMI output",
        "kind": "HDMI",
        "icon": "hdmi-port",
        "current": True,
    }
    state = AudioState(None, 0, False, False, False, ())
    values = A.Audio().values(state)
    assert (values["ready"], values["icon"], values["tooltip"], values["outputs"]) == (
        True,
        "volume-off",
        "No output",
        [],
    )
    assert A.Audio().values(None)["ready"] is False


# -- the module on the fake server --------------------------------------------------------------


class Desk:
    def __init__(self, fake: FakePulse, thread: ServiceThread, audio: AudioService) -> None:
        self.fake, self.thread, self.audio = fake, thread, audio

    def settle(
        self, w: Widgets | None, predicate: Callable[[], object], timeout: float = 5.0
    ) -> bool:
        """Be the loop until ``predicate`` holds (or ``timeout``): flush the value store and draw a
        frame."""
        deadline = time.monotonic() + timeout
        while True:
            if w is not None:
                w.flush()
                w.advance(16)
            if predicate():
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.004)


@contextmanager
def desk(fake: FakePulse) -> Iterator[Desk]:
    thread = ServiceThread()
    thread.start()
    audio = AudioService(thread, fake.socket, env={})  # the fake's socket, and no environment
    try:
        yield Desk(fake, thread, audio)
    finally:
        thread.stop()


@contextmanager
def shell(d: Desk, children: str, **kwargs: Any) -> Iterator[Widgets]:
    with running(children, audio=d.audio, **kwargs) as w:
        try:
            yield w
        finally:
            w.host.stop_all()


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio_service, "SHORT_SESSION", 0.0)


def maintainers_desktop(fake: FakePulse) -> None:
    """His three outputs (Audio Module > What It Reads) and a microphone."""
    fake.add_sink(
        "main", "Mainboard", bus="pci", percent=60, ports=PORTS, active="analog-output-speaker",
    )  # fmt: skip
    fake.add_sink(
        "razer", "Razer Leviathan V2 X", bus="usb", percent=45, default=True,
        ports=[("analog-output", "Analog Output", "Analog")],
    )  # fmt: skip
    fake.add_sink("gpu", "HDMI", bus="pci", ports=[("hdmi-output-0", "HDMI", "HDMI")])
    fake.add_source("mic", "Microphone")
    fake.start()


def audio_uses(w: Widgets) -> list[str]:
    """The keys of the Audio uses (a slider inside one is a use of the Slider module)."""
    return [u for u in w.uses if u.startswith("Audio@")]


def values(w: Widgets, index: int = 0) -> dict[str, Any]:
    return dict(w.store.values[audio_uses(w)[index]])


def root(w: Widgets) -> Any:
    return w.of_use("Audio", "Root")


def shown(w: Widgets) -> bool:
    return bool(root(w).get("visible"))


def icon_of(w: Widgets) -> str | None:
    """The name of the icon the Bar shows: the visible one of the two glyphs."""
    for suffix in ("Glyph", "Glyph_Muted"):
        node = w.of_use("Audio", suffix)
        if node.get("visible"):
            doc = node.get("svg")
            (name,) = [n for n in A.ICONS if SETS.lookup(f"mdi:{n}") == doc] or [None]
            return name  # type: ignore[no-any-return]
    return None


def instance(w: Widgets) -> Any:
    return w.host.loaded["Audio"].instance


def quiet(w: Widgets) -> list[str]:
    """Every INFO (but the Bar's own, the Popup's and the client's lines), WARNING and ERROR."""
    return [
        x
        for x in w.lines
        if ("| INFO " in x or "| WARNING " in x or "| ERROR " in x)
        and "Bar Top_Bar" not in x
        and "tess_shell.services.audio" not in x
        and "tess_shell.surfaces.popup" not in x
        and "tess_shell.surfaces.popup" not in x
    ]


def test_the_maintainers_desktop_shows_a_speaker_icon_and_the_tooltip(
    fake_pulse: FakePulse,
) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: values(w).get("ready") is True), w.log()
        assert d.settle(w, lambda: shown(w) and icon_of(w) == "volume-medium")
        v = values(w)
        assert (v["volume"], v["muted"], v["kind"], v["name"]) == (
            45,
            False,
            "SPEAKER",
            "Razer Leviathan V2 X",
        )
        assert v["tooltip"] == "Razer Leviathan V2 X, 45 %"
        assert v["label"] == "Audio, Razer Leviathan V2 X, 45 %"
        assert [(o["id"], o["kind"], o["current"]) for o in v["outputs"]] == [
            ("main", "SPEAKER", False),
            ("razer", "SPEAKER", True),
            ("gpu", "HDMI", False),
        ]
        assert root(w).get("role") == "group" and root(w).get("label") == v["label"]
        assert w.of_use("Audio", "Toggle").get("label") == "Mute"
        assert not w.of_use("Audio", "Mic").get("visible")  # the microphone is not muted
        assert quiet(w) == [] and w.warnings() == []


def test_with_no_server_the_module_is_hidden_and_takes_no_space_and_shows_when_it_starts(
    fake_pulse: FakePulse,
) -> None:
    fake_pulse.add_sink("razer", "Razer", percent=45, default=True)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: values(w).get("ready") is False and not shown(w))
        d.settle(w, lambda: False, 0.2)
        assert not shown(w)
        assert float(root(w).get("layout_width") or 0) == 0  # no space on the Bar
        fake_pulse.start()  # no shell restart
        assert d.settle(w, lambda: shown(w) and icon_of(w) == "volume-medium")
        assert float(root(w).get("layout_width") or 0) > 0
        assert quiet(w) == []


def test_the_server_restarting_hides_the_module_for_the_gap_and_it_comes_back(
    fake_pulse: FakePulse,
) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: shown(w))
        fake_pulse.stop()
        assert d.settle(w, lambda: not shown(w))
        fake_pulse.start()
        assert d.settle(w, lambda: shown(w) and values(w)["volume"] == 45)
        fake_pulse.set_volume("razer", 20)
        assert d.settle(w, lambda: icon_of(w) == "volume-low")


def test_a_change_by_another_client_changes_the_values_and_the_icon_and_replaces_no_node(
    fake_pulse: FakePulse,
) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { show_percent: true }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        nodes = dict(w.view.nodes)
        fake_pulse.set_volume("razer", 80)
        assert d.settle(w, lambda: icon_of(w) == "volume-high" and values(w)["volume"] == 80)
        assert w.of_use("Audio", "Percent").get("text") == "80 %"
        fake_pulse.set_mute("razer", True)
        assert d.settle(w, lambda: icon_of(w) == "volume-off")
        assert w.of_use("Audio", "Toggle").get("label") == "Unmute"
        assert w.of_use("Audio", "Glyph_Muted").get("visible")
        assert not w.of_use("Audio", "Glyph").get("visible")
        assert values(w)["tooltip"] == "Razer Leviathan V2 X, muted"
        fake_pulse.set_mute("razer", False)
        fake_pulse.set_volume("razer", 0)
        assert d.settle(w, lambda: icon_of(w) == "volume-mute")
        fake_pulse.set_source_mute("mic", True)
        assert d.settle(w, lambda: bool(w.of_use("Audio", "Mic").get("visible")))
        assert {k: n for k, n in w.view.nodes.items() if k in nodes} == nodes  # none replaced
        assert quiet(w) == [], quiet(w)


def test_the_default_output_changing_changes_the_name_the_kind_and_the_current_mark(
    fake_pulse: FakePulse,
) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: values(w).get("name") == "Razer Leviathan V2 X")
        fake_pulse.set_default_sink("gpu")
        assert d.settle(w, lambda: values(w).get("kind") == "HDMI" and values(w)["name"] == "HDMI")
        assert [o["current"] for o in values(w)["outputs"]] == [False, False, True]
        fake_pulse.set_active_port("main", "analog-output-headphones")
        fake_pulse.set_default_sink("main")
        assert d.settle(w, lambda: icon_of(w) == "headphones")
        fake_pulse.add_sink("bt", "Headset", bus="bluetooth", form_factor="headset")
        assert d.settle(w, lambda: len(values(w)["outputs"]) == 4)
        fake_pulse.set_default_sink("bt")
        assert d.settle(
            w, lambda: icon_of(w) == "bluetooth-audio" and values(w)["kind"] == "BLUETOOTH"
        )
        fake_pulse.remove_sink("bt")  # the server names a new default and the module follows it
        assert d.settle(
            w, lambda: len(values(w)["outputs"]) == 3 and values(w)["kind"] != "BLUETOOTH"
        )


def test_no_output_at_all_is_ready_with_an_empty_list_and_the_off_icon(
    fake_pulse: FakePulse,
) -> None:
    fake_pulse.start()
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: values(w).get("ready") is True)
        v = values(w)
        assert (v["outputs"], v["icon"], v["tooltip"]) == ([], "volume-off", "No output")
        assert shown(w)


def test_a_refresh_that_changes_nothing_sends_nothing(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        calls: list[str] = []
        real = instance(w).ctx.send

        def spy(key: str, value: Any, use: Any = None) -> None:
            calls.append(key)
            real(key, value) if use is None else real(key, value, use=use)

        instance(w).ctx.send = spy
        fake_pulse.set_volume("razer", 46)  # 45 -> 46: the icon stays; the number changes
        assert d.settle(w, lambda: values(w)["volume"] == 46)
        assert sorted(calls) == ["label", "tooltip", "volume", "volume_text"]
        calls.clear()
        fake_pulse.set_volume("main", 10)  # not the default output: the list's order is unchanged
        d.settle(w, lambda: False, 0.3)
        assert calls == []  # the entry list holds no volume: nothing that is shown changed


# -- the actions --------------------------------------------------------------------------------


def server_volume(fake: FakePulse, name: str = "razer") -> float:
    levels = fake.sink(name).volume
    return round(sum(levels) / len(levels) * 100 / NORM)


def test_a_click_toggles_the_mute_and_the_server_event_shows_it(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        w.window.simulate("click", node=w.of_use("Audio", "Toggle"))
        assert d.settle(w, lambda: icon_of(w) == "volume-off")  # the event, not a guess
        assert fake_pulse.sink("razer").mute
        w.window.simulate("click", node=w.of_use("Audio", "Toggle"))
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        assert not fake_pulse.sink("razer").mute


def test_scroll_steps_the_volume_up_for_up_and_down_for_down_by_the_step_param(
    fake_pulse: FakePulse,
) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }\nAudio { step: 10 }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        first, second = w.of_use("Audio", "Root", 0), w.of_use("Audio", "Root", 1)
        w.window.simulate("wheel", node=first, delta_y=-120)  # a step up
        assert wait_for(lambda: server_volume(fake_pulse) == 50)
        w.window.simulate("wheel", node=first, delta_y=120)  # a step down
        assert wait_for(lambda: server_volume(fake_pulse) == 45)
        w.window.simulate("wheel", node=second, delta_y=-120)  # step 10
        assert wait_for(lambda: server_volume(fake_pulse) == 55)
        for _ in range(3):  # three quick steps before the event comes back add up
            w.window.simulate("wheel", node=first, delta_y=-1)
        assert wait_for(lambda: server_volume(fake_pulse) == 70)
        for _ in range(9):
            w.window.simulate("wheel", node=second, delta_y=-1)
        assert wait_for(lambda: server_volume(fake_pulse) == 100)  # clamped
        d.settle(w, lambda: False, 0.2)
        assert quiet(w) == [], quiet(w)


def test_the_slider_writes_at_most_every_50_ms_while_dragging_and_the_final_value_on_release(
    fake_pulse: FakePulse,
) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { show_slider: true }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        slider = w.of_use("Slider", "Root")
        width = float(slider.get("layout_width"))
        clock = [100.0]
        instance(w).monotonic = lambda: clock[0]
        fake_pulse.commands.clear()
        w.window.simulate("pointer_down", node=slider, x=width * 0.10, y=10)
        for i in range(20):  # 20 moves, 10 ms apart: a write at most every 50 ms
            clock[0] += 0.010
            w.window.simulate("pointer_move", node=slider, x=width * (0.10 + 0.03 * (i + 1)), y=10)
        assert instance(w).dragging  # the handle is the user's
        time.sleep(0.2)  # the calls run on the service thread: let the last one reach the server
        before = server_volume(fake_pulse)
        writes_during = len([c for c in fake_pulse.commands if c[0] == "set_sink_volume"])
        assert 1 <= writes_during <= 5, writes_during  # 200 ms: at most 4 or 5 writes
        # the held-back echo does not move the handle: no volume is sent for the use
        assert values(w)["volume"] == 45
        w.window.simulate("pointer_up", node=slider, x=width * 0.70, y=10)
        assert wait_for(lambda: 66 <= server_volume(fake_pulse) <= 74), (
            before,
            server_volume(fake_pulse),
        )
        assert not instance(w).dragging
        assert d.settle(w, lambda: 66 <= values(w)["volume"] <= 74)  # the handle follows again
        assert wait_for(  # the release is one more write
            lambda: (
                len([c for c in fake_pulse.commands if c[0] == "set_sink_volume"])
                == writes_during + 1
            )
        )
        assert quiet(w) == [], quiet(w)


def test_set_volume_is_clamped_to_100_and_a_negative_to_0(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        from tess_shell.module import Event

        inst = instance(w)
        inst.set_volume(Event("click", audio_uses(w)[0]), 150)
        assert wait_for(lambda: server_volume(fake_pulse) == 100)
        inst.set_volume(Event("click", audio_uses(w)[0]), -3)
        assert wait_for(lambda: server_volume(fake_pulse) == 0)
        inst.toggle_mic(Event("click", audio_uses(w)[0]))
        assert wait_for(lambda: fake_pulse.source("mic").mute)
        inst.set_output(Event("click", audio_uses(w)[0]), "gpu")
        assert wait_for(lambda: fake_pulse.default_sink == "gpu")


def test_a_failed_call_is_logged_once_a_minute_and_changes_nothing(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        from tess_shell.module import Event

        for _ in range(3):
            instance(w).set_output(Event("click", audio_uses(w)[0]), "no-such-output")
        assert wait_for(lambda: len([x for x in w.warnings() if "set_output failed" in x]) >= 1)
        time.sleep(0.2)
        assert len([x for x in w.warnings() if "set_output failed" in x]) == 1
        assert values(w)["volume"] == 45


def test_a_bad_step_param_is_reported_at_load(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { step: 0 }") as w:
        assert [f.message for f in w.problems if "step" in f.message], w.problems


# -- the outputs menu ---------------------------------------------------------------------------

POPUPS = (
    "Popup { Name: Audio_Outputs, Attach: BOTTOM, "
    "Style { Background: $color.surface_raised, Corner_Radius: 8 }, "
    "Children { Audio_Outputs { } } }"
)


def labels(op: Any) -> list[str]:
    return [
        str(n.get("label"))
        for k, n in op.view.nodes.items()
        if k.endswith("/Root") and n.get("role") == "menuitem"
    ]


def test_a_secondary_click_opens_the_outputs_menu_and_a_click_on_an_entry_sets_the_default(
    fake_pulse: FakePulse,
) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }", popups=POPUPS) as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        assert w.manager.popups.current is None
        w.window.simulate("secondary_click", node=root(w))
        op = w.manager.popups.current
        assert op is not None, w.log()[-2500:]
        assert labels(op) == ["Mainboard", "Razer Leviathan V2 X, current", "HDMI"]
        hdmi = [n for n in op.view.nodes.values() if n.get("label") == "HDMI"][0]
        op.window.simulate("click", node=hdmi)
        assert wait_for(lambda: fake_pulse.default_sink == "gpu")
        op.window.advance(50)
        assert w.manager.popups.current is None  # a click on an entry closes the menu
        assert d.settle(w, lambda: icon_of(w) == "volume-high" and values(w)["name"] == "HDMI")
        assert quiet(w) == [], quiet(w)


def test_a_secondary_click_with_no_popup_written_opens_the_shipped_one(
    fake_pulse: FakePulse,
) -> None:
    """The shell provides ``Audio_Outputs`` (T-039): a shell file that writes none still has the
    menu."""
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        assert w.manager.popups.current is None
        w.window.simulate("secondary_click", node=root(w))
        op = w.manager.popups.current
        assert op is not None and op.plan.popup.name == "Audio_Outputs"
        assert labels(op) == ["Mainboard", "Razer Leviathan V2 X, current", "HDMI"]
        assert not [x for x in w.warnings() if "Audio_Outputs" in x]
        assert fake_pulse.default_sink == "razer"


# -- idle and the callback's cost ---------------------------------------------------------------


def test_the_callback_costs_well_under_a_millisecond(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        for i in range(40):
            fake_pulse.set_volume("razer", 10 + i)
            want = 10 + i
            assert d.settle(w, partial(lambda v: values(w)["volume"] == v, want))
        count, p50, p99, worst = d.audio.callback_summary("Audio")
        assert count >= 40
        assert p50 < 0.001 and p99 < 0.005, (p50, p99, worst)


def test_no_timer_runs_for_the_module(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with desk(fake_pulse) as d, shell(d, "Audio { show_slider: true, show_percent: true }") as w:
        assert d.settle(w, lambda: icon_of(w) == "volume-medium")
        d.settle(w, lambda: False, 0.3)
        assert w.host.ticks._subs == []
        assert threading.active_count() >= 1
