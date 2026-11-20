"""The service modules in the Tab order (M6a, T-041): Workspaces, Media, Audio and Tray on the fakes
of their own tests, drawn by the real binder in a headless Bar; Tab is simulated on the Bar's
window. What a module's controls are made of (a Button, a Slider, a block with ``Role: BUTTON``) is
what makes each one a stop, once, and the module's own hiding and disabling take stops away."""

from __future__ import annotations

from pathlib import Path

import pytest

from tess_shell.services import audio as audio_service
from tests.fake_dbus import HAVE_DAEMON
from tests.fake_pulse import FakePulse
from tests.modules_rig import desk, shell
from tests.test_audio_module import desk as audio_desk
from tests.test_audio_module import maintainers_desktop
from tests.test_audio_module import shell as audio_shell
from tests.test_focus_shell import rotated
from tests.test_tray_module import settle, up
from tests.tray_rig import tray_desk, tray_shell
from tests.widgets_live import Widgets

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio_service, "SHORT_SESSION", 0.0)  # as tests/test_audio_module.py


def walk(w: Widgets) -> list[str]:
    """The labels of the nodes Tab visits, once round (the focus starts nowhere)."""
    seen: list[str] = []
    for _ in range(30):
        w.window.simulate("key_down", key="tab")
        now = [n for n in w.view.nodes.values() if n.get("focused")]
        assert len(now) == 1, now
        label = str(now[0].get("label"))
        if seen and label == seen[0]:
            return seen
        seen.append(label)
    raise AssertionError(f"Tab never came round: {seen}")


def ring_shown(w: Widgets) -> bool:
    (node,) = [n for n in w.view.nodes.values() if n.get("focused")]
    return bool(list(node.get("shadows")))


@needs_daemon
def test_every_desktop_button_of_workspaces_is_one_stop() -> None:
    with desk() as d:
        fake, _, _ = d.kwin(("Main", "Code", "Mail"))
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: len(w.view.tab_stops()) == 3), w.log()
            assert walk(w) == ["Desktop 1, Main", "Desktop 2, Code", "Desktop 3, Mail"]
            assert ring_shown(w)


@needs_daemon
def test_media_controls_and_the_seek_slider_are_stops_unless_the_player_cannot_do_it() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", can_next=False)
        p.up()
        with shell(d, "Media { show_position: true }") as w:
            assert d.settle(w, lambda: len(w.view.tab_stops()) == 3), w.log()
            # Next is disabled: out of the order
            assert walk(w) == ["Previous", "Pause", "Position"]
            p.player.set("CanGoNext", True)
            assert d.settle(w, lambda: len(w.view.tab_stops()) == 4)
            assert rotated(walk(w), ["Previous", "Pause", "Next", "Position"])


@needs_daemon
def test_a_media_module_with_no_player_is_hidden_and_has_no_stop() -> None:
    with desk() as d, shell(d, "Media { show_position: true }") as w:
        d.settle(w, lambda: False, 0.3)
        assert w.view.tab_stops() == []


def test_audio_has_its_mute_button_and_volume_slider_as_two_stops(fake_pulse: FakePulse) -> None:
    maintainers_desktop(fake_pulse)
    with audio_desk(fake_pulse) as d, audio_shell(d, "Audio { show_slider: true }") as w:
        assert d.settle(w, lambda: len(w.view.tab_stops()) == 2), w.log()
        assert walk(w) == ["Mute", "Volume"]


def test_audio_with_no_sound_server_is_hidden_and_has_no_stop(fake_pulse: FakePulse) -> None:
    with audio_desk(fake_pulse) as d, audio_shell(d, "Audio { show_slider: true }") as w:
        d.settle(w, lambda: False, 0.3)
        assert w.view.tab_stops() == []


@needs_daemon
def test_each_tray_item_is_one_stop_and_a_hidden_tray_has_none(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        a = t.item("1-1", title="Chat")
        b = t.item("2-1", title="Sync")
        with tray_shell(t) as w:
            settle(t, w, lambda: False, 0.3)
            assert w.view.tab_stops() == []  # nothing registered: the module is hidden
            up(t, a, b)
            assert settle(t, w, lambda: len(w.view.tab_stops()) == 2), w.log()
            labels = walk(w)
            assert sorted(labels) == ["Chat", "Sync"]
            assert ring_shown(w)
            t.watcher.unregister(a)
            assert settle(t, w, lambda: len(w.view.tab_stops()) == 1)
            assert walk(w) == ["Sync"]
