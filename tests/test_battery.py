"""The shipped Battery module (Battery Module): the derivations, then the module on a fake UPower on
a private system bus, drawn by the real binder in a headless Bar."""

from __future__ import annotations

import importlib.util
from types import ModuleType
from typing import Any

import pytest

from tess_shell.files.icons import IconSets
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.modules_rig import desk, shell
from tests.widgets_live import SHIPPED, Widgets

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

ERROR = (242, 149, 140, 255)  # $color.error of the Default theme
WARNING = (230, 187, 106, 255)  # $color.warning


def load() -> ModuleType:
    path = SHIPPED / "Battery" / "Battery_Module.py"
    spec = importlib.util.spec_from_file_location("shipped_battery", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B = load()
SETS = IconSets([SHIPPED / "Icons"])
LAYOUT = (SHIPPED / "Battery" / "Battery_Module.tdl").read_text()


# -- the derivations ----------------------------------------------------------------------------


def test_every_icon_the_python_can_send_is_in_the_shipped_mdi_set() -> None:
    missing = sorted(name for name in B.ICONS if SETS.lookup(f"mdi:{name}") is None)
    assert missing == [], f"not in the mdi set: {missing}"
    assert len(B.ICONS) == 24


def test_icon_names_the_table_gives_never_leave_the_set() -> None:
    for state in ("CHARGING", "DISCHARGING", "FULL", "EMPTY", "UNKNOWN"):
        for percent in range(0, 101):
            for reading in (True, False):
                assert B.icon_name(state, percent, reading) in B.ICONS, (state, percent)


@pytest.mark.parametrize(
    ("state", "percent", "icon"),
    [
        ("DISCHARGING", 82, "battery-80"),
        ("DISCHARGING", 90, "battery-90"),
        ("DISCHARGING", 91, "battery"),
        ("DISCHARGING", 100, "battery"),
        ("DISCHARGING", 19, "battery-10"),
        ("DISCHARGING", 10, "battery-10"),
        ("DISCHARGING", 9, "battery-alert"),
        ("DISCHARGING", 0, "battery-alert"),
        ("UNKNOWN", 55, "battery-50"),
        ("CHARGING", 82, "battery-charging-80"),
        ("CHARGING", 99, "battery-charging-90"),
        ("CHARGING", 100, "battery-charging-100"),
        ("CHARGING", 4, "battery-charging-outline"),
        ("FULL", 100, "battery"),
        ("EMPTY", 0, "battery-alert-variant-outline"),
    ],
)
def test_the_icon_follows_the_state_and_the_level(state: str, percent: int, icon: str) -> None:
    assert B.icon_name(state, percent, True) == icon


def test_no_reading_is_the_unknown_icon() -> None:
    assert B.icon_name("UNKNOWN", 0, False) == "battery-unknown"
    assert B.derive({})["icon"] == "battery-unknown"


@pytest.mark.parametrize(
    ("code", "percent", "name"),
    [
        (0, 50, "UNKNOWN"),
        (1, 50, "CHARGING"),
        (2, 50, "DISCHARGING"),
        (3, 0, "EMPTY"),
        (4, 100, "FULL"),
        (5, 100, "FULL"),  # pending charge at 100 %: full
        (5, 60, "UNKNOWN"),
        (6, 100, "FULL"),
        (6, 60, "UNKNOWN"),
        (9, 60, "UNKNOWN"),
    ],
)
def test_the_state_codes(code: int, percent: int, name: str) -> None:
    assert B.state_name(code, percent) == name


def test_the_level_is_rounded_and_kept_between_0_and_100() -> None:
    assert B.derive({"Percentage": 81.5})["percent"] == 82
    assert B.derive({"Percentage": 81.4})["percent"] == 81
    assert B.derive({"Percentage": 140.0})["percent"] == 100
    assert B.derive({"Percentage": -3.0})["percent"] == 0
    assert B.derive({"Percentage": "x"})["percent"] == 0  # a wrong type keeps the default


def test_the_warning_level_sets_low_and_critical() -> None:
    flags = {
        w: (B.derive({"WarningLevel": w})["low"], B.derive({"WarningLevel": w})["critical"])
        for w in range(0, 7)
    }
    assert flags == {
        0: (False, False),
        1: (False, False),
        2: (False, False),
        3: (True, False),
        4: (False, True),
        5: (False, True),
        6: (False, False),
    }


def test_the_tooltip_says_the_state_and_the_time_left_and_leaves_an_unknown_time_out() -> None:
    props = {"Percentage": 82.0, "State": 2, "TimeToEmpty": 8040}
    assert B.derive(props)["tooltip"] == "82 %, discharging, 2 h 14 min left"
    assert B.derive({**props, "TimeToEmpty": 0})["tooltip"] == "82 %, discharging"
    assert B.derive({**props, "State": 1, "TimeToFull": 1800})["tooltip"] == (
        "82 %, charging, 30 min until full"
    )
    assert B.derive({**props, "State": 1, "TimeToFull": 0})["tooltip"] == "82 %, charging"
    assert B.derive({"Percentage": 100.0, "State": 4})["tooltip"] == "100 %, fully charged"
    assert B.derive({"Percentage": 50.0})["tooltip"] == "50 %"
    assert B.derive(props)["label"] == "Battery 82 percent, discharging"


def test_the_tooltip_text_changes_at_most_once_a_minute_of_time_left() -> None:
    props = {"Percentage": 50.0, "State": 2}
    seconds = range(7200, 7200 + 600)  # ten minutes of ticks, one a second
    texts = [B.derive({**props, "TimeToEmpty": s})["tooltip"] for s in seconds]
    changes = sum(1 for a, b in zip(texts, texts[1:], strict=False) if a != b)
    assert changes == 9  # a new text at each whole minute: 120 min to 129 min
    assert B.duration(59) == "1 min" and B.duration(3600) == "1 h 0 min"


# -- the module on a fake UPower ----------------------------------------------------------------


def shown(w: Widgets) -> bool:
    """Is the module's root visible (it takes space in the Bar)?"""
    (root,) = [n for k, n in w.view.nodes.items() if k.endswith("/Root")]
    return bool(root.get("visible"))


def level(w: Widgets) -> Any:
    """The box of the level that shows (normal, low or critical), or ``None`` when hidden."""
    if not shown(w):
        return None
    found = [n for k, n in w.view.nodes.items() if "/Level" in k]
    assert len(found) == 1
    return found[0]


def glyph(w: Widgets) -> Any:
    found = [n for k, n in w.view.nodes.items() if "/Glyph" in k]
    assert len(found) == 1, f"{len(found)} icon nodes"
    return found[0]


def icon_of(w: Widgets) -> str | None:
    """The name of the icon the Bar shows (the one ``mdi`` SVG of the module), or ``None``."""
    if not shown(w):
        return None
    doc = glyph(w).get("svg")
    (name,) = [n for n in B.ICONS if SETS.lookup(f"mdi:{n}") == doc] or [None]
    return name  # type: ignore[no-any-return]


def texts(w: Widgets) -> list[str]:
    return [n.get("text") for k, n in w.view.nodes.items() if w.view.kinds[k] == "Text"]


def values(w: Widgets) -> dict[str, Any]:
    (use,) = w.uses
    return dict(w.store.values[use])


def quiet(w: Widgets) -> list[str]:
    """Every INFO, WARNING and ERROR line: what a module that has nothing to say logs."""
    return [x for x in w.lines if "| INFO " in x or "| WARNING " in x or "| ERROR " in x]


@needs_daemon
def test_a_fake_battery_shows_the_icon_the_number_and_the_tooltip() -> None:
    with desk() as d:
        fake, _ = d.battery(percentage=82.0, state=2)
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80"), (w.log(), values(w))
            assert texts(w) == ["82 %"]
            v = values(w)
            assert v["tooltip"] == "82 %, discharging, 2 h 14 min left"
            assert v["label"] == "Battery 82 percent, discharging"
            assert (v["available"], v["present"], v["low"], v["critical"]) == (
                True,
                True,
                False,
                False,
            )
            root = [n for k, n in w.view.nodes.items() if k.endswith("/Root")][0]
            assert root.get("role") == "group"
            assert root.get("label") == "Battery 82 percent, discharging"
            assert [x for x in w.warnings()] == []


@needs_daemon
def test_charging_changes_the_icon_in_one_loop_turn_after_the_signal() -> None:
    with desk() as d:
        fake, obj = d.battery()
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            instance = w.host.loaded["Battery"].instance
            obj.set("State", 1)
            # the callback on the dbus thread has sent; no wait for anything else
            assert wait_for(lambda: instance.sent["icon"] == "battery-charging-80")
            w.flush()  # one loop turn: the store applies what was sent
            w.advance(16)
            assert icon_of(w) == "battery-charging-80"
            assert values(w)["state"] == "CHARGING"


@needs_daemon
def test_the_warning_level_sets_low_and_critical_and_the_look_follows() -> None:
    with desk() as d:
        fake, obj = d.battery(percentage=15.0)
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-10")

            def percent_node() -> Any:
                found = [n for k, n in w.view.nodes.items() if "/Percent" in k]
                assert len(found) == 1
                return found[0]

            def dot() -> Any:
                return [n for k, n in w.view.nodes.items() if "/Alarm" in k]

            assert dot() == [] and percent_node().get("fill") not in (WARNING, ERROR)
            obj.set("WarningLevel", 3)
            assert d.settle(w, lambda: values(w)["low"] is True and len(dot()) == 1)
            assert values(w)["critical"] is False
            assert percent_node().get("fill") == WARNING and dot()[0].get("fill") == WARNING
            assert glyph(w).get("svg_color") == WARNING  # the icon takes the level's colour
            obj.set("WarningLevel", 4)
            assert d.settle(w, lambda: values(w)["critical"] is True)
            assert d.settle(w, lambda: percent_node().get("fill") == ERROR)
            assert values(w)["low"] is False and dot()[0].get("fill") == ERROR
            assert glyph(w).get("svg_color") == ERROR
            obj.set("WarningLevel", 1)
            assert d.settle(w, lambda: dot() == [])


@needs_daemon
def test_a_time_to_empty_of_zero_leaves_the_time_out_of_the_tooltip() -> None:
    with desk() as d:
        fake, obj = d.battery()
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: "left" in values(w).get("tooltip", ""))
            obj.set("TimeToEmpty", 0)
            assert d.settle(w, lambda: values(w)["tooltip"] == "82 %, discharging")


@needs_daemon
def test_no_battery_hides_the_module_and_logs_nothing() -> None:
    with desk() as d:
        fake, _ = d.battery(present=False, percentage=0.0, state=0)
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: values(w).get("available") is True)
            d.settle(w, lambda: False, 0.3)  # let the first read arrive and settle
            assert values(w)["present"] is False
            assert level(w) is None and not shown(w)
            instance = w.host.loaded["Battery"].instance
            assert instance.sent["present"] is False
            assert [x for x in quiet(w) if "Bar Top_Bar" not in x] == []


@needs_daemon
def test_a_battery_that_is_plugged_in_shows_itself() -> None:
    with desk() as d:
        fake, obj = d.battery(present=False, percentage=0.0, state=0)
        fake.up()
        with shell(d, "Battery { }") as w:
            d.settle(w, lambda: False, 0.3)
            assert level(w) is None
            obj.set("IsPresent", True)
            obj.set("Percentage", 64.0)
            obj.set("State", 2)
            assert d.settle(w, lambda: icon_of(w) == "battery-60" and texts(w) == ["64 %"])


@needs_daemon
def test_upower_leaving_hides_the_module_with_one_warning_and_returning_shows_it() -> None:
    with desk() as d:
        fake, obj = d.battery()
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            fake.down()
            assert d.settle(w, lambda: level(w) is None)
            assert values(w)["available"] is False
            warned = [x for x in w.lines if "| WARNING " in x]
            assert len(warned) == 1 and "org.freedesktop.UPower left the system bus" in warned[0]
            obj.silent_set("Percentage", 40.0)  # it changed while UPower was away
            fake.up()
            assert d.settle(w, lambda: icon_of(w) == "battery-40" and texts(w) == ["40 %"])
            assert values(w)["available"] is True
            assert [x for x in w.lines if "| ERROR " in x] == []


@needs_daemon
def test_a_value_is_sent_only_when_it_changed() -> None:
    with desk() as d:
        fake, obj = d.battery()
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            instance = w.host.loaded["Battery"].instance
            calls: list[str] = []
            real = instance.ctx.send
            instance.ctx.send = lambda key, value, use=None: (  # type: ignore[method-assign, assignment]
                calls.append(key),
                real(key, value),
            )
            obj.set("Percentage", 82.0)  # the same
            obj.set("TimeToEmpty", 8041)  # the same minute
            obj.set("IconName", "battery-full-symbolic")  # a property nothing reads
            d.settle(w, lambda: False, 0.3)
            assert calls == []
            obj.set("Percentage", 81.0)
            assert wait_for(lambda: calls)
            assert "percent" in calls and "state" not in calls and "present" not in calls


@needs_daemon
def test_show_percent_false_leaves_the_number_out() -> None:
    with desk() as d:
        fake, _ = d.battery()
        fake.up()
        with shell(d, "Battery { show_percent: false }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            assert texts(w) == []


@needs_daemon
def test_the_power_profile_is_a_read_only_value_and_may_be_absent() -> None:
    with desk() as d:
        fake, _ = d.battery()
        fake.up()
        profiles, pobj = d.profiles("balanced")
        profiles.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: values(w).get("profile") == "balanced")
            pobj.set("ActiveProfile", "power-saver")
            assert d.settle(w, lambda: values(w).get("profile") == "power-saver")
            assert pobj.sets == []  # the module never writes it
            profiles.down()  # the profile service leaves: the Battery stays
            d.settle(w, lambda: False, 0.3)
            assert values(w)["available"] is True and icon_of(w) == "battery-80"
            assert values(w)["profile"] == "power-saver"  # the last value stays
            assert [x for x in w.lines if "| WARNING " in x] == []
    with desk() as d:
        fake, _ = d.battery()
        fake.up()  # no power-profiles service at all
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            assert "profile" not in values(w)
            assert quiet(w) == [x for x in quiet(w) if "Bar Top_Bar" in x]


@needs_daemon
def test_no_upower_at_all_is_hidden_without_a_crash() -> None:
    with desk() as d:  # no fake UPower on the system bus
        with shell(d, "Battery { }") as w:
            d.settle(w, lambda: False, 0.5)
            assert values(w)["available"] is False and level(w) is None
            assert [x for x in w.lines if "| ERROR " in x] == []
            fake, _ = d.battery()
            fake.up()  # it appears later (a daemon started, or activated)
            assert d.settle(w, lambda: icon_of(w) == "battery-80")


@needs_daemon
def test_the_module_starts_no_thread_and_calls_nothing_on_the_loop_thread() -> None:
    import threading

    with desk() as d:
        fake, _ = d.battery()
        fake.up()
        before = {t.name for t in threading.enumerate()}
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            assert {t.name for t in threading.enumerate()} - before == set()
    source = (SHIPPED / "Battery" / "Battery_Module.py").read_text()
    assert "threading" not in source and "Thread(" not in source and "run_blocking" not in source


@needs_daemon
def test_per_signal_module_work_is_far_under_a_millisecond(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with desk() as d:
        fake, obj = d.battery()
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            start = len(d.layer.callback_times.get("Battery", ()))
            for i in range(150):
                obj.set("Percentage", float(i % 100))
                obj.set("TimeToEmpty", 600 + i * 60)
            assert d.settle(w, lambda: len(d.layer.callback_times["Battery"]) - start >= 300, 10)
            count, p50, p99, worst = d.layer.callback_summary("Battery")
            with capsys.disabled():
                print(
                    f"\nBattery callback: n={count} p50={p50 * 1e6:.1f} us "
                    f"p99={p99 * 1e6:.1f} us max={worst * 1e6:.1f} us"
                )
            assert p99 < 0.001


def test_the_module_has_no_timer() -> None:
    source = (SHIPPED / "Battery" / "Battery_Module.py").read_text()
    assert "every(" not in source and "on_tick" not in source and "sleep" not in source


@needs_daemon
def test_the_slot_renders_each_of_the_24_names_and_swaps_the_icon_in_place() -> None:
    with desk() as d:
        fake, obj = d.battery()
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "battery-80")
            node = glyph(w)
            seen: set[str] = set()
            for state, percent in [
                (s, p) for s in (1, 2, 3, 4, 0) for p in (0, 5, 15, 35, 55, 75, 95, 100)
            ]:
                obj.set("State", state)
                obj.set("Percentage", float(percent))
                want = B.icon_name(B.state_name(state, percent), percent, True)
                assert d.settle(w, lambda want=want: icon_of(w) == want), (state, percent, want)
                assert glyph(w) == node  # the same SVG node: the document was swapped in place
                seen.add(want)
            # every name in the table that the Python can reach by a reading is rendered here;
            # the rest are rendered by sending the key directly
            for name in sorted(B.ICONS - seen):
                w.host.loaded["Battery"].instance.ctx.send("icon", name)
                w.flush()
                w.advance(16)
                assert icon_of(w) == name
                seen.add(name)
            assert seen == set(B.ICONS)
            assert w.warnings() == []
