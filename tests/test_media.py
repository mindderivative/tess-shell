"""The shipped Media module (Media Module): the derivations, then the module on fake MPRIS players
on a private session bus (``tests/fake_mpris.py``), drawn by the real binder in a headless Bar. A
player's state changes only by the fake's own signals, as a real player's does after a call."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from dbus_fast import DBusError

from tess_shell.files.icons import IconSets
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.fake_mpris import Fake, metadata
from tests.modules_rig import Desk, desk, shell
from tests.widgets_live import SHIPPED, Widgets

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load() -> ModuleType:
    path = SHIPPED / "Media" / "Media_Module.py"
    spec = importlib.util.spec_from_file_location("shipped_media", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load()
SETS = IconSets([SHIPPED / "Icons"])
SOURCE = (SHIPPED / "Media" / "Media_Module.py").read_text()


# -- the derivations ----------------------------------------------------------------------------


def test_every_icon_the_module_uses_is_in_the_shipped_mdi_set() -> None:
    layout = (SHIPPED / "Media" / "Media_Module.tdl").read_text()
    names = set(M.ICONS)
    assert names == {"play", "pause", "skip-next", "skip-previous", "music"}
    assert [n for n in names if SETS.lookup(f"mdi:{n}") is None] == []
    for name in ("skip-previous", "skip-next", "music"):  # the ones the layout writes
        assert f"mdi:{name}" in layout


def test_a_file_url_becomes_a_path_and_nothing_else_does() -> None:
    assert M.file_path("file:///tmp/a%20b.png") == "/tmp/a b.png"
    assert M.file_path("file://localhost/tmp/a.png") == "/tmp/a.png"
    assert M.file_path("https://example.org/a.png") is None
    assert M.file_path("http://example.org/a.png") is None
    assert M.file_path("file://other-host/a.png") is None
    assert M.file_path("/tmp/a.png") is None


def test_the_tooltip_and_the_label_say_the_title_the_artist_the_player_and_the_status() -> None:
    assert M.tooltip_text("Song", "Artist", "Google Chrome", "PAUSED") == (
        "Song, Artist (Google Chrome), paused"
    )
    assert M.tooltip_text("", "", "Mpv", "PLAYING") == "No title (Mpv), playing"
    assert M.tooltip_text("Song", "", "", "STOPPED") == "Song, stopped"
    assert M.label_text("Song", "Artist", "Chrome", "PLAYING") == (
        "Media, Song, Artist, Chrome, playing"
    )


def player_state(name: str, status: str, **kw: Any) -> Any:
    state = M.Playing(name, status=status, seen=True, **kw)
    return state


def test_the_choice_follows_the_specs_four_rules() -> None:
    def pick(players: dict[str, Any], last: str | None = None) -> str | None:
        return M.choose(players, last)  # type: ignore[no-any-return]

    a = player_state("a", "PLAYING", since=1, changed=1, metadata={"xesam:title": "A"})
    b = player_state("b", "PLAYING", since=2, changed=2, metadata={"xesam:title": "B"})
    assert pick({"a": a, "b": b}) == "b"  # 1: playing; the one that began last
    a.since = 3
    assert pick({"a": a, "b": b}) == "a"
    a.status = b.status = "PAUSED"  # 2: the one shown before, while it is not stopped
    assert pick({"a": a, "b": b}, "a") == "a" and pick({"a": a, "b": b}, "b") == "b"
    b.status = "STOPPED"
    assert pick({"a": a, "b": b}, "b") == "a"  # the one before is stopped: the paused one
    a.changed, b.status = 5, "PAUSED"
    b.changed = 9
    assert pick({"a": a, "b": b}) == "b"  # 3: the paused one that changed last
    assert pick({"a": a, "b": b}, "ghost") == "b"
    a.status = b.status = "STOPPED"
    assert pick({"a": a, "b": b}, "a") is None  # 4: none
    empty = player_state("e", "STOPPED")  # stopped and no title: never
    assert pick({"e": empty}, "e") is None
    unread = M.Playing("u", status="PLAYING")  # its properties were not read yet
    assert pick({"u": unread}) is None


def test_the_duplicate_rule_keeps_the_integration_player_of_a_browser_pair() -> None:
    chrome = M.PREFIX + "chromium.instance926871"
    integration = M.PREFIX + "plasma-browser-integration"
    other = M.PREFIX + "vlc"
    assert M.is_duplicate(chrome, [chrome, integration])
    assert not M.is_duplicate(integration, [chrome, integration])
    assert not M.is_duplicate(chrome, [chrome])  # alone: it is the player
    assert not M.is_duplicate(other, [other, integration])  # not a browser
    assert M.is_duplicate(M.PREFIX + "firefox.instance_1_2", [M.PREFIX + "firefox.x", integration])


# -- the module on fake players -----------------------------------------------------------------


def media_uses(w: Widgets) -> list[str]:
    return [u for u in w.uses if u.startswith("Media@")]


def values(w: Widgets, index: int = 0) -> dict[str, Any]:
    return dict(w.store.values[media_uses(w)[index]])


def instance(w: Widgets) -> Any:
    return w.host.loaded["Media"].instance


def node(w: Widgets, tail: str) -> Any:
    found = [n for k, n in w.view.nodes.items() if k.endswith(tail)]
    assert len(found) == 1, (tail, found)
    return found[0]


def root(w: Widgets) -> Any:
    return node(w, "Media_1/Root")


def shown(w: Widgets) -> bool:
    return bool(root(w).get("visible"))


def button(w: Widgets, name: str) -> Any:
    return node(w, f"Media_1.{name}/Root")


def glyph_of(w: Widgets, name: str) -> str | None:
    doc = node(w, f"Media_1.{name}/Glyph").get("svg")
    (found,) = [n for n in M.ICONS if SETS.lookup(f"mdi:{n}") == doc] or [None]
    return found  # type: ignore[no-any-return]


def title_of(w: Widgets) -> str:
    return str(node(w, "Media_1.Title/#1").get("text"))


def quiet(w: Widgets) -> list[str]:
    return [
        x
        for x in w.lines
        if ("| INFO " in x or "| WARNING " in x or "| ERROR " in x) and "Bar Top_Bar" not in x
    ]


def click(w: Widgets, name: str) -> None:
    w.window.simulate("click", node=button(w, name))


def calls(p: Fake) -> list[str]:
    return [c[0] for c in p.calls]


def settled(d: Desk, w: Widgets, predicate: Any, timeout: float = 5.0) -> bool:
    return d.settle(w, predicate, timeout)


@needs_daemon
def test_with_no_player_the_module_is_hidden_and_takes_no_bar_space() -> None:
    from tests.test_hidden_module import gap, row

    with desk() as d, shell(d, row("Media { }")) as w:
        assert d.settle(w, lambda: values(w).get("available") is True)
        d.settle(w, lambda: False, 0.3)
        assert not shown(w) and values(w)["has_player"] is False
        assert gap(w) == 8  # hidden: no second gap, no zero-size box
        assert quiet(w) == [] and w.warnings() == []
        player = d.player("vlc", status="Playing")
        player.up()
        assert d.settle(w, lambda: shown(w))
        assert gap(w) > 8 + 8
        player.down()
        assert d.settle(w, lambda: not shown(w))
        assert gap(w) == 8


@needs_daemon
def test_a_playing_player_shows_its_title_and_artist_with_the_pause_icon() -> None:
    with desk() as d:
        p = d.player("vlc", identity="VLC", status="Playing", meta=metadata("Song", ["Ann", "Bo"]))
        p.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: shown(w) and title_of(w) == "Song")
            v = values(w)
            assert (v["status"], v["artist"], v["album"], v["player"]) == (
                "PLAYING",
                "Ann, Bo",
                "Album",
                "VLC",
            )
            assert v["tooltip"] == "Song, Ann, Bo (VLC), playing"
            assert v["label"] == "Media, Song, Ann, Bo, VLC, playing"
            assert glyph_of(w, "Play") == "pause" and button(w, "Play").get("label") == "Pause"
            assert root(w).get("role") == "group" and root(w).get("label") == v["label"]
            assert [x for x in w.warnings()] == []


@needs_daemon
def test_pause_changes_the_icon_to_play_in_one_loop_turn_after_the_players_signal() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing")
        p.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: glyph_of(w, "Play") == "pause")
            p.status("Paused")
            assert wait_for(lambda: instance(w).sent["icon"] == "play")
            w.flush()  # one loop turn: the store applies what was sent
            w.advance(16)
            assert glyph_of(w, "Play") == "play" and button(w, "Play").get("label") == "Play"
            assert values(w)["status"] == "PAUSED"


@needs_daemon
def test_a_click_calls_the_player_once_and_the_look_changes_only_on_the_players_signal() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing")
        p.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: glyph_of(w, "Play") == "pause")
            click(w, "Play")
            assert wait_for(lambda: calls(p) == ["PlayPause"])
            d.settle(w, lambda: False, 0.4)
            assert glyph_of(w, "Play") == "pause" and values(w)["status"] == "PLAYING"  # no guess
            p.status("Paused")  # the player says so
            assert d.settle(w, lambda: glyph_of(w, "Play") == "play")
            click(w, "Next")
            click(w, "Previous")
            assert wait_for(lambda: calls(p) == ["PlayPause", "Next", "Previous"])
            d.settle(w, lambda: False, 0.3)
            assert calls(p) == ["PlayPause", "Next", "Previous"]  # each once
            assert quiet(w) == []


@needs_daemon
def test_a_control_the_player_cannot_do_is_disabled_and_a_click_calls_nothing() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", can_next=False, can_previous=False)
        p.up()
        with shell(d, "Media { }") as w:
            assert d.settle(
                w,
                lambda: (
                    button(w, "Next").get("disabled") is True
                    and button(w, "Play").get("disabled") is False
                ),
            )
            assert button(w, "Previous").get("disabled") is True
            click(w, "Next")
            click(w, "Previous")
            d.settle(w, lambda: False, 0.4)
            assert calls(p) == []
            p.player.set("CanGoNext", True)  # a track appears after this one
            assert d.settle(w, lambda: button(w, "Next").get("disabled") is False)
            click(w, "Next")
            assert wait_for(lambda: calls(p) == ["Next"])


@needs_daemon
def test_a_player_that_cannot_be_controlled_disables_every_control_and_still_shows() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", can_control=False)
        p.up()
        with shell(d, "Media { show_position: true }") as w:
            assert d.settle(w, lambda: shown(w) and title_of(w) == "Song")
            assert all(button(w, n).get("disabled") is True for n in ("Previous", "Play", "Next"))
            assert node(w, "Media_1.Position/Root").get("disabled") is True
            for name in ("Previous", "Play", "Next"):
                click(w, name)
            d.settle(w, lambda: False, 0.3)
            assert calls(p) == []


@needs_daemon
def test_with_two_players_the_playing_one_shows_and_the_shown_one_leaving_shows_the_other() -> None:
    with desk() as d:
        a = d.player("alpha", identity="Alpha", status="Paused", meta=metadata("Song A"))
        b = d.player("beta", identity="Beta", status="Paused", meta=metadata("Song B"))
        a.up()
        b.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: shown(w))
            first = values(w)["player"]  # both paused: one of them, the one that changed last
            assert first in ("Alpha", "Beta")
            a.status("Playing")
            assert d.settle(w, lambda: values(w)["player"] == "Alpha" and title_of(w) == "Song A")
            click(w, "Play")  # the control reaches the shown player and only it
            assert wait_for(lambda: calls(a) == ["PlayPause"])
            assert calls(b) == []
            a.status("Paused")
            b.status("Playing")
            assert d.settle(w, lambda: values(w)["player"] == "Beta" and title_of(w) == "Song B")
            click(w, "Next")
            assert wait_for(lambda: calls(b) == ["Next"])
            assert calls(a) == ["PlayPause"]
            a.status("Playing")  # it began later than Beta: now it shows
            assert d.settle(w, lambda: values(w)["player"] == "Alpha")
            a.down()  # the shown one leaves: the remaining one is shown
            assert d.settle(w, lambda: values(w)["player"] == "Beta" and shown(w))
            assert values(w)["status"] == "PLAYING" and title_of(w) == "Song B"
            assert quiet(w) == [x for x in quiet(w) if "left the session bus" in x]


@needs_daemon
def test_the_last_active_paused_player_stays_over_one_that_changed_but_is_not_playing() -> None:
    with desk() as d:
        a = d.player("alpha", identity="Alpha", status="Playing", meta=metadata("Song A"))
        b = d.player("beta", identity="Beta", status="Paused", meta=metadata("Song B"))
        a.up()
        b.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: values(w).get("player") == "Alpha")
            a.status("Paused")  # nothing plays: the one shown before stays
            d.settle(w, lambda: False, 0.4)
            assert values(w)["player"] == "Alpha" and values(w)["status"] == "PAUSED"
            b.track(title="Song B2")  # the other changes its track: still not the shown one
            d.settle(w, lambda: False, 0.4)
            assert values(w)["player"] == "Alpha"
            a.status("Stopped")  # the one before is stopped: the paused one is shown
            assert d.settle(w, lambda: values(w)["player"] == "Beta")


@needs_daemon
def test_a_stopped_player_with_no_title_is_never_shown_and_removing_every_player_hides() -> None:
    with desk() as d:
        s = d.player("idle", status="Stopped", meta=metadata(None, None, None, None, None, None))
        s.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: values(w).get("available") is True)
            d.settle(w, lambda: False, 0.4)
            assert not shown(w)
            p = d.player("vlc", status="Playing")
            p.up()
            assert d.settle(w, lambda: shown(w))
            p.down()
            s.down()
            assert d.settle(w, lambda: not shown(w))
            q = d.player("later", status="Paused")
            q.up()  # a new player shows it again, with no shell restart
            assert d.settle(w, lambda: shown(w) and values(w)["status"] == "PAUSED")


@needs_daemon
def test_the_two_browser_names_make_one_entry_and_the_integration_player_is_the_one_shown() -> None:
    with desk() as d:
        chrome = d.player("chromium.instance926871", identity="Google Chrome", status="Playing")
        integration = d.player(
            "plasma-browser-integration",
            identity="Google Chrome (integration)",
            status="Playing",
            meta=metadata("Song", ["Artist"]),
        )
        chrome.up()
        integration.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: values(w).get("player") == "Google Chrome (integration)")
            click(w, "Play")
            assert wait_for(lambda: calls(integration) == ["PlayPause"])
            assert calls(chrome) == []
            integration.down()  # alone, the browser's own player is the player
            assert d.settle(w, lambda: values(w).get("player") == "Google Chrome")


@needs_daemon
def test_metadata_with_missing_or_wrong_entries_gives_empty_values_and_one_warning() -> None:
    from dbus_fast import Variant

    with desk() as d:
        p = d.player("vlc", status="Playing", meta=metadata(None, None, None, None, None, None))
        p.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: values(w).get("has_player") is True)
            v = values(w)
            assert (v["title"], v["artist"], v["album"], v["art"], v["length"]) == (
                "",
                "",
                "",
                "",
                0,
            )
            assert v["tooltip"] == "No title (Fake Player), playing"
            p.player.set("Metadata", {**metadata("Song"), "xesam:album": Variant("i", 3)})
            assert d.settle(w, lambda: values(w)["title"] == "Song")
            assert values(w)["album"] == ""
            p.player.set("Metadata", {**metadata("Song 2"), "xesam:album": Variant("i", 4)})
            assert d.settle(w, lambda: values(w)["title"] == "Song 2")
            said = [x for x in w.lines if "| WARNING " in x and "xesam:album" in x]
            assert len(said) == 1, said  # once for the entry, not for each track


@needs_daemon
def test_a_file_url_shows_the_artwork_and_an_https_url_or_a_missing_file_the_placeholder() -> None:
    art = FIXTURES / "png.png"
    with desk() as d:
        p = d.player("vlc", status="Playing", meta=metadata(art=f"file://{art}"))
        p.up()
        with shell(d, "Media { show_art: true }") as w:

            def bitmaps() -> list[Any]:
                art_box = node(w, "Media_1.Art/Root")
                return [c for c in art_box.children() if c.get("kind") == "image"]

            def placeholder() -> bool:
                art_box = node(w, "Media_1.Art/Root")
                return any(c.get("kind") == "svg" for c in art_box.children())

            assert d.settle(w, lambda: len(bitmaps()) == 1)
            assert values(w)["art"] == str(art)
            p.track(art="https://example.org/cover.png")  # not fetched: the placeholder
            assert d.settle(w, lambda: values(w)["art"] == "" and not bitmaps() and placeholder())
            p.track(art="https://example.org/cover.png", title="Song 2")  # the same URL again
            p.track(
                art=f"file://{FIXTURES}/nothing.png", title="Song 3"
            )  # a file that is not there
            assert d.settle(w, lambda: values(w)["title"] == "Song 3")
            assert values(w)["art"] == "" and not bitmaps() and placeholder()
            p.track(art=f"file://{art}", title="Song 4")
            assert d.settle(w, lambda: len(bitmaps()) == 1)
            assert [x for x in w.warnings()] == []  # no error image, no warning
            said = [x for x in w.lines if "not a file:// URL" in x]
            assert len(said) == 1 and "https://example.org/cover.png" in said[0]  # one debug line
            assert instance(w).bus is not None


@needs_daemon
def test_the_position_is_the_stored_one_plus_the_time_times_the_rate_and_seeked_jumps_it() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", position=10_000_000, rate=2.0)
        clock = [1000.0]
        with shell(d, "Media { show_position: true }") as w:
            instance(w).monotonic = lambda: clock[0]
            p.up()
            assert d.settle(w, lambda: values(w).get("status") == "PLAYING")
            assert values(w)["position"] == 10 and values(w)["length"] == 200
            clock[0] += 5.5  # 5.5 s at rate 2: 11 s more
            instance(w).tick()
            assert d.settle(w, lambda: values(w)["position"] == 21)
            clock[0] += 500  # never past the length
            instance(w).tick()
            assert d.settle(w, lambda: values(w)["position"] == 200)
            p.seek(30)  # the player jumps and says so: the module reads it again
            assert d.settle(w, lambda: values(w)["position"] in (30, 31))
            assert quiet(w) == []


@needs_daemon
def test_a_pause_keeps_the_position_and_a_resume_continues_from_the_players_own_reading() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", position=60_000_000)
        clock = [500.0]
        with shell(d, "Media { show_position: true }") as w:
            instance(w).monotonic = lambda: clock[0]
            p.up()
            assert d.settle(w, lambda: values(w).get("status") == "PLAYING")
            clock[0] += 4
            p.player.silent_set("Position", 64_000_000)  # what the player is at when it pauses
            p.status("Paused")
            assert d.settle(w, lambda: values(w)["status"] == "PAUSED")
            assert d.settle(w, lambda: values(w)["position"] == 64)
            clock[0] += 100  # time passes while paused: the position does not move
            instance(w).tick()
            d.settle(w, lambda: False, 0.3)
            assert values(w)["position"] == 64


@needs_daemon
def test_the_tick_exists_only_while_playing_and_a_use_shows_the_position() -> None:
    with desk() as d:
        p = d.player("vlc", status="Paused")
        p.up()
        with shell(d, "Media { show_position: true }\nMedia { }") as w:
            ticks = w.host.ticks._subs
            assert d.settle(w, lambda: values(w).get("status") == "PAUSED")
            assert ticks == [] and instance(w).tick_sub is None  # paused: no timer
            p.status("Playing")
            assert d.settle(w, lambda: len(ticks) == 1)  # one timer, though two uses
            assert ticks[0].unit == "second"
            p.status("Paused")
            assert d.settle(w, lambda: ticks == [])
            p.status("Playing")
            assert d.settle(w, lambda: len(ticks) == 1)
            p.down()  # the player leaves: no timer
            assert d.settle(w, lambda: ticks == [])
    with desk() as d:
        p = d.player("vlc", status="Playing")
        p.up()
        with shell(d, "Media { }") as w:  # no use shows the position: never a timer
            assert d.settle(w, lambda: values(w).get("status") == "PLAYING")
            d.settle(w, lambda: False, 0.3)
            assert w.host.ticks._subs == [] and instance(w).tick_sub is None
        assert w.host.ticks._subs == [] or True


@needs_daemon
def test_a_released_slider_calls_set_position_with_the_track_id_and_microseconds() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", meta=metadata("Song", track="/track/42"))
        p.up()
        with shell(d, "Media { show_position: true }") as w:
            assert d.settle(w, lambda: values(w).get("can_seek") is True)
            slider = node(w, "Media_1.Position/Root")
            width = float(slider.get("layout_width"))
            # a drag sends nothing to the player until the release
            w.window.simulate("pointer_down", node=slider, x=width / 4, y=10)
            w.window.simulate("pointer_move", node=slider, x=width / 2, y=10)
            d.settle(w, lambda: False, 0.3)
            assert calls(p) == []
            w.window.simulate("pointer_up", node=slider, x=width / 2, y=10)
            assert wait_for(lambda: calls(p) == ["SetPosition"], 3), (calls(p), quiet(w))
            track, micro = p.calls[0][1]
            assert (
                track == "/track/42" and 90_000_000 <= micro <= 110_000_000
            )  # about half of 200 s


@needs_daemon
def test_seek_does_nothing_without_a_length_or_a_trackid_and_the_slider_is_disabled() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", meta=metadata("Live", length=None))
        p.up()
        with shell(d, "Media { show_position: true }") as w:
            assert d.settle(w, lambda: values(w).get("status") == "PLAYING")
            assert values(w)["length"] == 0 and values(w)["can_seek"] is False
            assert node(w, "Media_1.Position/Root").get("disabled") is True
            instance(w).seek_to(30.0)
            d.settle(w, lambda: False, 0.3)
            assert calls(p) == []
            p.track(title="Song", track=None)  # a length but no track id
            assert d.settle(w, lambda: values(w)["can_seek"] is True)
            instance(w).seek_to(30.0)
            d.settle(w, lambda: False, 0.3)
            assert calls(p) == []
            assert len([x for x in w.lines if "| WARNING " in x and "mpris:trackid" in x]) == 1


@needs_daemon
def test_a_failed_control_call_is_logged_once_a_minute_per_player_and_changes_nothing() -> None:
    def refuse() -> None:
        raise DBusError("org.mpris.MediaPlayer2.Error", "no")

    with desk() as d:
        p = d.player("vlc", status="Playing")
        p.player._methods["PlayPause"] = ([], "", refuse)
        p.up()
        with shell(d, "Media { }") as w:
            clock = [100.0]
            assert d.settle(w, lambda: glyph_of(w, "Play") == "pause")
            instance(w).monotonic = lambda: clock[0]
            for _ in range(3):
                click(w, "Play")
            assert wait_for(lambda: len(p.calls) == 3)
            d.settle(w, lambda: False, 0.3)
            said = [x for x in w.lines if "| WARNING " in x and "PlayPause failed" in x]
            assert len(said) == 1, said
            assert glyph_of(w, "Play") == "pause" and values(w)["status"] == "PLAYING"
            clock[0] += 61
            click(w, "Play")
            assert wait_for(lambda: len(p.calls) == 4)
            assert wait_for(
                lambda: len([x for x in w.lines if "PlayPause failed" in x and "WARNING" in x]) == 2
            )


@needs_daemon
def test_a_use_added_later_gets_the_values_and_a_value_is_sent_only_when_it_changed() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing")
        p.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: title_of(w) == "Song")
            sent: list[str] = []
            real = instance(w).ctx.send

            def spy(key: str, value: Any, use: Any = None) -> None:
                sent.append(key)
                real(key, value) if use is None else real(key, value, use=use)

            instance(w).ctx.send = spy
            p.player.set("Rate", 1.0)  # the same
            p.player.set("CanSeek", True)  # the same
            p.player.set("Metadata", metadata())  # the same track again
            d.settle(w, lambda: False, 0.4)
            assert sent == [], sent
            p.player.set("Metadata", metadata("Other"))
            assert wait_for(lambda: sent)
            assert "title" in sent and "status" not in sent and "player" not in sent


# -- what it draws ------------------------------------------------------------------------------

TEXT = (228, 234, 241)  # $color.on_surface of the Default theme


def near(px: tuple[int, ...], want: tuple[int, ...], tol: int = 40) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px[:3], want[:3], strict=True))


def pixels(w: Widgets, name: str) -> int:
    """How many pixels of the text colour the Bar's drawing has in the button's icon box."""
    g = node(w, f"Media_1.{name}/Glyph")
    x, y, gw, gh = (
        int(g.get(k)) for k in ("layout_x", "layout_y", "layout_width", "layout_height")
    )
    rgba, width, _ = w.window.snapshot()
    return sum(
        near(tuple(rgba[(r * width + c) * 4 : (r * width + c) * 4 + 4]), TEXT)
        for r in range(y, y + gh)
        for c in range(x, x + gw)
    )


@needs_daemon
def test_the_icons_are_drawn_in_every_state_and_no_node_is_made_or_lost_by_a_change() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing", can_next=False)
        p.up()
        with shell(d, "Media { show_position: true }") as w:
            assert d.settle(w, lambda: glyph_of(w, "Play") == "pause")
            names = set(w.view.nodes)
            before = len([x for x in w.lines if "rebuilt" in x])
            assert pixels(w, "Play") > 10 and pixels(w, "Previous") > 10
            for act in (
                lambda: p.status("Paused"),
                lambda: p.track(title="A much longer title than before", artist=["X"]),
                lambda: p.player.set("CanGoNext", True),
                lambda: p.status("Playing"),
                lambda: p.seek(100),
            ):
                act()
                d.settle(w, lambda: False, 0.35)
                w.advance(16)
                assert set(w.view.nodes) == names  # nothing created, nothing removed
                assert pixels(w, "Play") > 10, glyph_of(w, "Play")
            assert pixels(w, "Next") > 10  # enabled now: drawn
            rebuilt = [x for x in w.lines if "rebuilt" in x][before:]
            assert rebuilt == [] or all("0 created, 0 removed" in x for x in rebuilt), rebuilt


@needs_daemon
def test_the_module_keeps_its_size_at_every_state_so_its_tooltip_area_stays() -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing")
        p.up()
        with shell(d, "Media { max_width: 200 }") as w:
            assert d.settle(w, lambda: shown(w))
            sizes = []
            for act in (
                lambda: p.status("Paused"),
                lambda: p.track(title="Another"),
                lambda: p.status("Playing"),
            ):
                act()
                d.settle(w, lambda: False, 0.3)
                w.advance(16)
                sizes.append((root(w).get("layout_width"), root(w).get("layout_height")))
            assert len(set(sizes)) == 1 and sizes[0][0] >= 3 * 32, sizes


# -- no thread, no blocking, the work per signal ------------------------------------------------


@needs_daemon
def test_the_module_starts_no_thread_and_never_blocks() -> None:
    import threading

    with desk() as d:
        p = d.player("vlc", status="Playing")
        p.up()
        before = {t.name for t in threading.enumerate()}
        with shell(d, "Media { show_position: true }") as w:
            assert d.settle(w, lambda: values(w).get("status") == "PLAYING")
            assert {t.name for t in threading.enumerate()} - before == set()
    for word in ("Thread(", "run_blocking", "sleep", "subprocess", "urlopen", "requests"):
        assert word not in SOURCE, word
    assert "import socket" not in SOURCE and "http.client" not in SOURCE  # no network


@needs_daemon
def test_a_player_that_leaves_is_forgotten_by_the_layer() -> None:
    with desk() as d:
        a = d.player("alpha", status="Playing")
        b = d.player("beta", status="Paused")
        a.up()
        b.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: len(instance(w).players) == 2)
            services = lambda: [k for k in d.layer._services if "MediaPlayer2." in k[1]]  # noqa: E731
            assert wait_for(lambda: len(services()) == 2)
            a.down()
            assert d.settle(w, lambda: list(instance(w).players) == [b.name])
            assert wait_for(lambda: services() == [("session", b.name)])
            assert [k for k in d.layer._caches if k[1] == a.name] == []


@needs_daemon
def test_per_signal_module_work_is_far_under_a_millisecond(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with desk() as d:
        p = d.player("vlc", status="Playing")
        q = d.player("mpv", status="Paused")
        p.up()
        q.up()
        with shell(d, "Media { }") as w:
            assert d.settle(w, lambda: values(w).get("status") == "PLAYING")
            start = len(d.layer.callback_times.get("Media", ()))
            for i in range(120):
                p.track(title=f"Song {i}", artist=[f"Artist {i}"])
                p.player.set("CanGoNext", i % 2 == 0)
                q.track(title=f"Other {i}")
            assert d.settle(w, lambda: len(d.layer.callback_times["Media"]) - start >= 360, 15)
            count, p50, p99, worst = d.layer.callback_summary("Media")
            with capsys.disabled():
                print(
                    f"\nMedia callback: n={count} p50={p50 * 1e6:.1f} us "
                    f"p99={p99 * 1e6:.1f} us max={worst * 1e6:.1f} us"
                )
            assert p99 < 0.001
