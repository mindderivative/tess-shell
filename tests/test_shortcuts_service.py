"""The shell's global shortcuts against a fake ``org.kde.kglobalaccel`` on a private bus (Global
Shortcuts > Acceptance Criteria). Nothing here reaches the real session bus or the real service."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

import pytest
from loguru import logger

from tess_shell.schema.keys import parse_chord
from tess_shell.services.bus import ServiceThread
from tess_shell.services.shortcuts import (
    COMPONENT,
    COMPONENT_FRIENDLY,
    Action,
    ShortcutService,
    friendly_text,
)
from tests.fake_dbus import HAVE_DAEMON, FakeBus, fake_bus, wait_for
from tests.fake_kglobalaccel import FakeKGlobalAccel
from tests.test_control import FakeLoop

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

SPACE = parse_chord("Meta+Space").qt


def act(id_: str, keys: str = "", kind: str = "toggle", target: str = "") -> Action:
    """An action of the shell: ``keys`` is a key string, or empty for no key."""
    chords = (parse_chord(keys),) if keys else ()
    return Action(id_, friendly_text(id_), kind, target or id_.split("_", 1)[-1], chords)


@dataclass
class Rig:
    bus: FakeBus
    fake: FakeKGlobalAccel
    service: ServiceThread
    loop: FakeLoop
    shortcuts: ShortcutService
    pressed: list[Action]
    threads: list[str]
    lines: list[tuple[str, str]] = field(default_factory=list)  # (level, message)

    def start(self, actions: Sequence[Action], enabled: bool = True) -> None:
        self.service.submit(self.shortcuts.start(actions, enabled)).result(10)

    def stop(self) -> None:
        self.service.submit(self.shortcuts.stop()).result(10)

    def said(self, level: str, needle: str) -> list[str]:
        return [m for lv, m in list(self.lines) if lv == level and needle in m]


@contextmanager
def rig(*, up: bool = True) -> Iterator[Rig]:
    with fake_bus() as bus:
        fake = FakeKGlobalAccel(bus)
        if up:
            fake.start()
        service = ServiceThread(bus.address)
        service.start()
        loop = FakeLoop()
        pressed: list[Action] = []
        threads: list[str] = []

        def press(action: Action) -> None:
            threads.append(threading.current_thread().name)
            pressed.append(action)

        shortcuts = ShortcutService(service, loop.call_soon, press)
        r = Rig(bus, fake, service, loop, shortcuts, pressed, threads)
        sink = logger.add(
            lambda m: r.lines.append((m.record["level"].name, m.record["message"])),
            level="DEBUG",
        )
        try:
            yield r
        finally:
            logger.remove(sink)
            service.stop()
            loop.close()


def registered(r: Rig, ids: Sequence[str]) -> bool:
    return wait_for(lambda: sorted(r.shortcuts.registered) == sorted(ids))


LAUNCHER = act("Toggle_Launcher", "Meta+Space")
BAR = act("Show_Top_Bar", "Ctrl+Alt+B", kind="show")
PLAIN = act("Toggle_Settings")  # declared with no key


# -- registration -------------------------------------------------------------------------------


def test_the_component_exists_after_start_and_lists_every_declared_action() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR, PLAIN])
        assert r.fake.names() == ["Toggle_Launcher", "Show_Top_Bar", "Toggle_Settings"]
        component = r.fake.components[COMPONENT]
        assert (component.unique, component.friendly) == ("tesserae-shell", "Tesserae Shell")
        assert COMPONENT_FRIENDLY == "Tesserae Shell"
        assert r.fake.action(COMPONENT, "Toggle_Launcher").friendly == "Toggle Launcher"  # type: ignore[union-attr]
        assert sorted(r.fake.present()) == sorted(r.fake.names())  # every action is present
        registers = [c.args[0] for c in r.fake.of("doRegister")]
        assert registers[0] == [
            "tesserae-shell",
            "Toggle_Launcher",
            "Tesserae Shell",
            "Toggle Launcher",
        ]
        assert all(len(ids) == 4 for ids in registers)
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == [SPACE]
        assert r.fake.keys_of(COMPONENT, "Toggle_Settings") == []  # no key declared


def test_the_keys_are_set_in_two_calls_with_flags_2_then_8_and_never_4() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR])
        calls = [c for c in r.fake.calls if c.member in ("doRegister", "setShortcutKeys")]
        by_action: dict[str, list[tuple[str, int | None]]] = {}
        for c in calls:
            ids = c.args[0]
            by_action.setdefault(ids[1], []).append((c.member, c.flags))
        for steps in by_action.values():
            assert steps == [("doRegister", None), ("setShortcutKeys", 2), ("setShortcutKeys", 8)]
        assert all(c.flags in (2, 8) for c in r.fake.of("setShortcutKeys"))
        first = r.fake.of("setShortcutKeys")[0]
        assert first.args[1] == [[[SPACE]]]  # one key sequence: a struct holding one int32
        # then the component is asked for (never derived), and its signal is subscribed
        members = [c.member for c in r.fake.calls]
        assert members.index("getComponent") > max(
            i for i, m in enumerate(members) if m == "setShortcutKeys"
        )
        assert r.fake.of("getComponent")[0].args == ("tesserae-shell",)


def test_an_action_with_no_key_is_registered_present_with_an_empty_list() -> None:
    with rig() as r:
        r.start([PLAIN])
        assert [c.args[1] for c in r.fake.of("setShortcutKeys")] == [[], []]
        assert r.fake.present() == ["Toggle_Settings"]


def test_registering_ten_actions_is_fast_on_the_fake(capsys: pytest.CaptureFixture[str]) -> None:
    actions = [act(f"Toggle_Panel_{n}", f"Ctrl+Alt+{n}") for n in range(10)]
    with rig() as r:
        started = time.perf_counter()
        r.start(actions)
        elapsed = (time.perf_counter() - started) * 1000
        assert len(r.fake.names()) == 10
    with capsys.disabled():
        print(f"\nshortcuts: 10 actions registered in {elapsed:.1f} ms on the fake")
    assert elapsed < 500  # the spec's target is 50 ms of the service's own work; the fake is loose


# -- a key press ----------------------------------------------------------------------------------


def test_a_press_runs_the_action_on_the_loop_thread_not_the_bus_thread() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR])
        r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: r.pressed == [LAUNCHER])
        assert r.threads == ["fake-loop"]  # call_soon: never the dbus thread
        r.fake.press("Show_Top_Bar")
        assert wait_for(lambda: r.pressed == [LAUNCHER, BAR])


def test_a_press_by_key_reaches_the_action_that_holds_it() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR])
        assert r.fake.press_key(SPACE)
        assert wait_for(lambda: r.pressed == [LAUNCHER])


def test_release_and_repeat_are_ignored() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        obj = r.fake._objects["/component/tesserae_shell"]
        obj.emit("globalShortcutRepeated", COMPONENT, "Toggle_Launcher", 5)
        obj.emit("globalShortcutReleased", COMPONENT, "Toggle_Launcher", 6)
        r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: len(r.pressed) == 1)
        time.sleep(0.2)
        assert len(r.pressed) == 1  # a held key toggles once


def test_a_press_for_an_action_the_shell_does_not_declare_is_dropped_and_logged_once() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        r.fake.press("Ghost")
        r.fake.press("Ghost")
        r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: r.pressed == [LAUNCHER])
        assert len(r.said("DEBUG", "Ghost")) == 1


def test_a_press_for_another_component_is_not_ours() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        r.fake.preregister("plasma", "Toggle_Launcher", keys=(1,))
        obj = r.fake._objects["/component/tesserae_shell"]
        obj.emit("globalShortcutPressed", "plasma", "Toggle_Launcher", 1)
        r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: r.pressed == [LAUNCHER])


def test_a_press_while_stopping_is_dropped_with_a_debug_line() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        r.shortcuts.begin_stop()
        r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: r.said("DEBUG", "starting or stopping"))
        assert r.pressed == []


def test_a_press_before_the_start_has_finished_is_dropped() -> None:
    with rig() as r:
        assert not r.shortcuts._accepting  # nothing is taken until start() has returned
        r.start([LAUNCHER])
        assert r.shortcuts._accepting


# -- the user's keys -----------------------------------------------------------------------------


def test_a_key_the_user_changes_is_used_at_the_next_press_with_nothing_sent_again() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        before = len(r.fake.calls)
        new = parse_chord("Ctrl+Alt+L").qt
        r.fake.user_changes(COMPONENT, "Toggle_Launcher", (new,))
        assert wait_for(lambda: r.shortcuts.keys_now.get("Toggle_Launcher") == (new,))
        assert r.fake.press_key(new)  # the service grabs the user's key
        assert wait_for(lambda: r.pressed == [LAUNCHER])
        assert not r.fake.press_key(SPACE)  # and the old key is no longer ours
        assert len(r.fake.calls) == before  # the shell sends nothing: it only listens


def test_a_key_the_user_changed_survives_a_restart_of_the_shell() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        new = parse_chord("Ctrl+Alt+L").qt
        r.fake.user_changes(COMPONENT, "Toggle_Launcher", (new,))
        r.stop()
        assert r.fake.present() == []  # inactive, the component and the keys stay
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == [new]
        second = ShortcutService(r.service, r.loop.call_soon, r.pressed.append)
        r.service.submit(second.start([LAUNCHER], True)).result(10)
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == [new]  # the default did not win
        assert r.fake.of("setShortcutKeys")[-2].flags == 2


def test_a_taken_key_leaves_the_action_registered_with_no_key_and_one_warning() -> None:
    with rig() as r:
        r.fake.own(SPACE, "kwin")
        r.start([LAUNCHER, BAR])
        assert "Toggle_Launcher" in r.fake.names()  # registered
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == []  # with no key
        assert r.fake.keys_of(COMPONENT, "Show_Top_Bar") != []  # the other one is fine
        warnings = r.said("WARNING", "taken")
        assert len(warnings) == 1
        assert "Toggle_Launcher" in warnings[0] and "Meta+Space" in warnings[0]
        assert not r.fake.press_key(SPACE)  # the desktop keeps the key


def test_a_key_another_component_holds_is_never_taken() -> None:
    with rig() as r:
        r.fake.preregister("plasma", "Launcher", keys=(SPACE,))
        r.fake.action("plasma", "Launcher").present = True  # type: ignore[union-attr]
        r.start([LAUNCHER])
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == []
        assert r.fake.keys_of("plasma", "Launcher") == [SPACE]
        assert len(r.said("WARNING", "taken")) == 1


def test_two_actions_the_plan_withheld_the_key_from_register_with_no_key_and_no_warning() -> None:
    # the plan (tests/test_shortcut_plan.py) gives both actions an empty key list; the service
    # registers both, and the desktop is not asked for a key
    both = [act("Toggle_A"), act("Toggle_B")]
    with rig() as r:
        r.start(both)
        assert r.fake.names() == ["Toggle_A", "Toggle_B"]
        assert r.fake.keys_of(COMPONENT, "Toggle_A") == r.fake.keys_of(COMPONENT, "Toggle_B") == []
        assert r.said("WARNING", "") == []


# -- the service goes and comes ---------------------------------------------------------------


def test_a_restart_of_the_service_registers_everything_again_and_the_keys_work() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR])
        first = len(r.fake.of("doRegister"))
        r.fake.restart()
        assert wait_for(lambda: len(r.fake.of("doRegister")) == 2 * first)
        assert wait_for(lambda: sorted(r.fake.present()) == ["Show_Top_Bar", "Toggle_Launcher"])
        assert r.fake.press_key(SPACE)
        assert wait_for(lambda: r.pressed == [LAUNCHER])
        assert r.shortcuts.registered == {"Toggle_Launcher", "Show_Top_Bar"}


def test_a_service_that_leaves_and_comes_back_is_followed() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        r.fake.stop()
        assert wait_for(lambda: not r.shortcuts.attached)
        assert wait_for(lambda: r.said("INFO", "left the session bus"))
        r.fake.start()
        assert wait_for(lambda: r.fake.present() == ["Toggle_Launcher"])
        assert r.fake.press_key(SPACE)
        assert wait_for(lambda: r.pressed == [LAUNCHER])


def test_with_no_service_the_shell_starts_with_one_warning_and_registers_when_it_comes() -> None:
    with rig(up=False) as r:
        r.start([LAUNCHER])  # returns: the shell does not wait for a service
        assert r.shortcuts.registered == frozenset()
        assert len(r.said("WARNING", "org.kde.kglobalaccel")) == 1
        r.fake.start()
        assert wait_for(lambda: r.fake.present() == ["Toggle_Launcher"])
        assert len(r.said("WARNING", "org.kde.kglobalaccel")) == 1


def test_an_action_the_service_refuses_is_skipped_and_the_rest_register() -> None:
    with rig() as r:
        r.fake.refuse_actions.add("Show_Top_Bar")
        r.start([LAUNCHER, BAR, PLAIN])
        assert sorted(r.shortcuts.registered) == ["Toggle_Launcher", "Toggle_Settings"]
        assert len(r.said("WARNING", "Show_Top_Bar")) == 1
        r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: r.pressed == [LAUNCHER])


def test_a_refused_set_of_keys_skips_that_action_only() -> None:
    with rig() as r:
        r.fake.refuse.add("setShortcutKeys")
        r.start([LAUNCHER])
        assert r.shortcuts.registered == frozenset()
        assert len(r.said("WARNING", "Toggle_Launcher")) == 1


# -- cleaning up ---------------------------------------------------------------------------------


def test_a_deleted_surfaces_action_is_removed_at_the_next_start_and_other_components_stay() -> None:
    with rig() as r:
        r.fake.preregister(COMPONENT, "Toggle_Gone", "Toggle Gone")
        r.fake.preregister("plasma", "Toggle_Gone", keys=(7,))  # same name, not ours
        r.fake.preregister("other", "Stay")
        r.start([LAUNCHER])
        assert r.fake.names() == ["Toggle_Launcher"]
        assert r.fake.action("plasma", "Toggle_Gone") is not None
        assert r.fake.action("other", "Stay") is not None
        assert [c.args for c in r.fake.of("unregister")] == [("tesserae-shell", "Toggle_Gone")]
        assert r.fake.of("unRegister") == []
        assert any(m for lv, m in r.lines if "removed Toggle_Gone" in m)


def test_a_stop_makes_every_action_inactive_and_keeps_the_component_and_the_keys() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR])
        r.stop()
        assert r.fake.present() == []
        assert sorted(r.fake.names()) == ["Show_Top_Bar", "Toggle_Launcher"]
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == [SPACE]
        inactive = [c.args[0] for c in r.fake.of("setInactive")]
        assert [ids[:2] for ids in inactive] == [
            ["tesserae-shell", "Toggle_Launcher"],
            ["tesserae-shell", "Show_Top_Bar"],
        ]
        assert r.fake.of("unregister") == [] and r.fake.of("unRegister") == []


# -- changes at reload --------------------------------------------------------------------------


def calls_for(r: Rig, action: str) -> list[tuple[str, int | None]]:
    out: list[tuple[str, int | None]] = []
    for c in r.fake.calls:
        if c.member == "unregister" and c.args[1] == action:
            out.append((c.member, None))
        elif (
            c.member in ("doRegister", "setShortcutKeys", "setInactive") and c.args[0][1] == action
        ):
            out.append((c.member, c.flags))
    return out


def test_an_update_registers_new_replaces_changed_removes_gone_and_leaves_the_rest() -> None:
    keep = act("Toggle_Keep", "Ctrl+Alt+K")
    gone = act("Toggle_Gone", "Ctrl+Alt+G")
    changes = act("Toggle_Changes", "Ctrl+Alt+C")
    with rig() as r:
        r.start([keep, gone, changes])
        r.fake.clear_calls()
        moved = act("Toggle_Changes", "Ctrl+Alt+X")
        new = act("Toggle_New", "Ctrl+Alt+N")
        r.shortcuts.update([keep, moved, new], True)
        assert wait_for(
            lambda: (
                sorted(r.shortcuts.registered) == ["Toggle_Changes", "Toggle_Keep", "Toggle_New"]
            )
        )
        assert wait_for(lambda: r.fake.names() == ["Toggle_Keep", "Toggle_Changes", "Toggle_New"])
        assert calls_for(r, "Toggle_Gone") == [("unregister", None)]  # unregistered, not inactive
        assert calls_for(r, "Toggle_Changes") == [
            ("unregister", None),
            ("doRegister", None),
            ("setShortcutKeys", 2),
            ("setShortcutKeys", 8),
        ]
        assert r.fake.keys_of(COMPONENT, "Toggle_Changes") == [parse_chord("Ctrl+Alt+X").qt]
        assert calls_for(r, "Toggle_New")[0] == ("doRegister", None)
        assert calls_for(r, "Toggle_Keep") == []  # untouched: no churn
        assert r.fake.of("getComponent") == []  # the component is known: not asked again


def test_a_new_handler_with_the_same_key_sends_nothing_and_a_press_runs_the_new_one() -> None:
    first = Action(
        "Volume_Up", "Volume Up", "handler", "", (parse_chord("Ctrl+Alt+U"),), handler="a"
    )
    second = Action(
        "Volume_Up", "Volume Up", "handler", "", (parse_chord("Ctrl+Alt+U"),), handler="b"
    )
    with rig() as r:
        r.start([first])
        r.fake.clear_calls()
        r.shortcuts.update([second], True)
        assert wait_for(lambda: r.shortcuts._desired["Volume_Up"].handler == "b")
        time.sleep(0.1)
        assert r.fake.calls == []
        r.fake.press("Volume_Up")
        assert wait_for(lambda: len(r.pressed) == 1)
        assert r.pressed[0].handler == "b"


def test_an_update_after_a_key_the_user_changed_keeps_their_key_for_an_unchanged_action() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR])
        new = parse_chord("Ctrl+Alt+L").qt
        r.fake.user_changes(COMPONENT, "Toggle_Launcher", (new,))
        r.shortcuts.update([LAUNCHER, act("Show_Top_Bar", "Ctrl+Alt+Z", kind="show")], True)
        assert wait_for(
            lambda: r.fake.keys_of(COMPONENT, "Show_Top_Bar") == [parse_chord("Ctrl+Alt+Z").qt]
        )
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == [new]


# -- Global_Shortcuts: false -----------------------------------------------------------------------


def test_with_global_shortcuts_false_nothing_is_sent_and_one_info_line_says_so() -> None:
    with rig() as r:
        r.start([LAUNCHER], enabled=False)
        assert r.fake.calls == []
        assert r.shortcuts.registered == frozenset() and not r.shortcuts.attached
        assert len(r.said("INFO", "Global_Shortcuts is false")) == 1
        r.shortcuts.update([LAUNCHER, BAR], False)  # still off: still silent
        time.sleep(0.2)
        assert r.fake.calls == [] and len(r.said("INFO", "Global_Shortcuts is false")) == 1


def test_turning_global_shortcuts_off_makes_every_action_inactive_and_keeps_the_keys() -> None:
    with rig() as r:
        r.start([LAUNCHER, BAR])
        r.shortcuts.update([LAUNCHER, BAR], False)
        assert wait_for(lambda: r.fake.present() == [])
        assert sorted(r.fake.names()) == ["Show_Top_Bar", "Toggle_Launcher"]
        assert r.fake.keys_of(COMPONENT, "Toggle_Launcher") == [SPACE]  # the user's keys stay
        assert r.fake.of("unregister") == []
        assert r.shortcuts.registered == frozenset()
        r.fake.press("Toggle_Launcher")  # no subscription: nothing is heard
        time.sleep(0.2)
        assert r.pressed == []
        before = len(r.fake.calls)
        time.sleep(0.2)
        assert len(r.fake.calls) == before


def test_turning_global_shortcuts_on_registers_as_at_start() -> None:
    with rig() as r:
        r.start([LAUNCHER], enabled=False)
        r.shortcuts.update([LAUNCHER, BAR], True)
        assert wait_for(lambda: sorted(r.fake.present()) == ["Show_Top_Bar", "Toggle_Launcher"])
        assert r.fake.press_key(SPACE)
        assert wait_for(lambda: r.pressed == [LAUNCHER])


def test_off_then_on_again_restores_the_subscriptions() -> None:
    with rig() as r:
        r.start([LAUNCHER])
        r.shortcuts.update([LAUNCHER], False)
        assert wait_for(lambda: r.fake.present() == [])
        r.shortcuts.update([LAUNCHER], True)
        assert wait_for(lambda: r.fake.present() == ["Toggle_Launcher"])
        r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: r.pressed == [LAUNCHER])


def test_the_press_time_on_the_bus_thread_is_recorded_and_tiny(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with rig() as r:
        r.start([LAUNCHER])
        for _ in range(200):
            r.fake.press("Toggle_Launcher")
        assert wait_for(lambda: len(r.pressed) == 200, 10)
        samples = sorted(r.shortcuts.callback_ns)
        p50, p99 = samples[len(samples) // 2], samples[int(len(samples) * 0.99) - 1]
    with capsys.disabled():
        print(
            f"\nshortcuts: press callback on the dbus thread p50 {p50 / 1000:.1f} us, "
            f"p99 {p99 / 1000:.1f} us"
        )
    assert p99 < 5_000_000  # 5 ms: a lookup and a call_soon
