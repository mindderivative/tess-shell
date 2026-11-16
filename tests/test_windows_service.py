"""``ctx.windows`` (Tasks Module > Needs from the Shell): the window service over a KWin service
whose script is a fake. What a module gets, when its callback runs, the subscriber count that turns
the script's list on and off, and what a stopped module leaves behind. Private buses only."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tess_shell.modules.context import ModuleContext
from tess_shell.modules.ticks import TimeSource
from tess_shell.services.windows import WindowService
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.fake_kwin import uuid, window
from tests.tasks_rig import TasksDesk, tasks_desk

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def pump(t: TasksDesk, predicate: Callable[[], object], timeout: float = 5.0) -> bool:
    return t.d.pump.wait(predicate, timeout)


def test_a_module_gets_the_window_helper_and_nothing_of_the_services_internals(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t:
        helper = t.windows.for_module("Tasks")
        public = {n for n in dir(helper) if not n.startswith("_")}
        assert public == {
            "available",
            "ready",
            "list",
            "on_changed",
            "activate",
            "minimize",
            "close_window",
            "close",
        }


def test_the_first_subscriber_turns_the_list_on_the_last_one_leaving_turns_it_off(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t:
        one, two = t.windows.for_module("A"), t.windows.for_module("B")
        assert not t.kwin.windows_wanted
        first = one.on_changed(lambda: None)
        assert t.kwin.windows_wanted and t.windows.subscribers == 1
        second = two.on_changed(lambda: None)
        assert t.kwin.windows_wanted and t.windows.subscribers == 2
        first.cancel()
        assert t.kwin.windows_wanted  # one module still wants it
        second.cancel()
        assert not t.kwin.windows_wanted and t.windows.subscribers == 0
        second.cancel()  # a second cancel is harmless
        one.on_changed(lambda: None)
        two.on_changed(lambda: None)
        one.close()  # a module that stops cancels its subscriptions
        two.close()
        assert not t.kwin.windows_wanted


def test_the_callback_runs_on_the_loop_for_each_new_list_and_each_change_of_availability(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t:
        helper = t.windows.for_module("Tasks")
        seen: list[tuple[bool, bool, int]] = []
        helper.on_changed(lambda: seen.append((helper.available, helper.ready, len(helper.list()))))
        t.fake.script.windows = [window(uuid(1), "One"), window(uuid(2), "Two")]
        t.start_kwin()  # the script loads: availability changes
        assert pump(t, lambda: any(s[0] for s in seen))
        assert pump(t, lambda: seen[-1] == (True, True, 2))
        assert [w.title for w in helper.list()] == ["One", "Two"]
        t.fake.set_windows([window(uuid(2), "Two")])
        assert pump(t, lambda: seen[-1] == (True, True, 1))


def test_a_list_from_before_is_never_shown_after_the_list_was_turned_off_and_on(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t:
        helper = t.windows.for_module("Tasks")
        sub = helper.on_changed(lambda: None)
        t.fake.script.windows = [window(uuid(1), "Old")]
        t.start_kwin()
        assert pump(t, lambda: helper.ready and len(helper.list()) == 1)
        sub.cancel()
        assert helper.list() == () and not helper.ready  # off: nothing is kept
        t.fake.script.windows = [window(uuid(2), "New")]
        helper.on_changed(lambda: None)
        assert helper.list() == () and not helper.ready  # on again: nothing until the new list
        assert pump(t, lambda: helper.ready)
        assert [w.title for w in helper.list()] == ["New"]


def test_a_callback_that_raises_is_logged_and_noted_and_the_others_still_run(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t:
        noted: list[tuple[str, str]] = []
        t.windows.on_module_error = lambda module, what, exc: noted.append((module, what))
        good: list[int] = []
        helper = t.windows.for_module("Bad")
        helper.on_changed(lambda: 1 / 0)
        t.windows.for_module("Good").on_changed(lambda: good.append(1))
        t.fake.script.windows = [window(uuid(1))]
        t.start_kwin()
        assert pump(t, lambda: good and noted)
        assert noted[0] == ("Bad", "a windows callback")


def test_the_actions_go_to_the_kwin_service_as_one_shot_scripts(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t:
        helper = t.windows.for_module("Tasks")
        t.start_kwin()
        assert helper.activate(uuid(1)).result(5) is True
        assert helper.minimize(uuid(2)).result(5) is True
        assert helper.close_window(uuid(3)).result(5) is True
        kinds = [shot.name.rsplit("-", 2)[1] for shot in t.fake.one_shots()]
        assert kinds == ["activate", "minimize", "close"]
        assert helper.activate("not a uuid").result(5) is False


def test_the_context_has_ctx_windows_only_when_the_shell_has_a_window_service() -> None:
    def make(port: Any) -> ModuleContext:
        return ModuleContext("M", "u", {}, {}, lambda *a: None, TimeSource(), windows=lambda: port)

    with pytest.raises(RuntimeError, match="no window service"):
        make(None).windows  # noqa: B018

    class Stub:
        closed = 0

        def for_module(self, module: str) -> Any:
            stub = self
            return type("H", (), {"close": lambda self: setattr(stub, "closed", stub.closed + 1)})()

    stub = Stub()
    ctx = make(stub)
    assert ctx.windows is ctx.windows  # one helper for the module
    ctx.close()  # the shell closes it when the module stops
    assert stub.closed == 1


def test_the_service_hands_over_nothing_when_nobody_listens(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t:
        t.start_kwin()
        t.d.pump.drain()
        t.fake.raw("WindowsState", json.dumps([window(uuid(1))]))  # nobody asked
        assert wait_for(lambda: True)
        t.d.pump.drain()
        assert t.windows.list() == () and t.windows.ready is False
        assert isinstance(t.windows, WindowService)
