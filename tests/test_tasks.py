"""The Tasks module and ``ctx.windows`` (Tasks Module > Acceptance Criteria): the shipped module on
a shell whose KWin is a fake (``tests/fake_kwin.py``) with a fake script that calls the shell's real
control interface; the shell's real KWin service, window service and icon service on private
buses. Nothing here touches the real session bus, the real KWin or a real data folder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tess_shell.modules.context import UseRecord
from tess_shell.services.api import WindowInfo
from tess_shell.services.icons import FALLBACK
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.fake_kwin import uuid, window
from tests.icon_theme import svg
from tests.tasks_rig import BLUE, RED, TasksDesk, tasks_desk, tasks_shell
from tests.widgets_live import Widgets

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

SECRET = "SECRET-TITLE"
OUT = "HDMI-A-1"  # the output of the headless Bar of tests/widgets_live.py


# -- helpers ------------------------------------------------------------------------------------


def uses(w: Widgets) -> list[str]:
    return [u for u in w.uses if u.startswith("Tasks@")]


def values(w: Widgets, index: int = 0) -> dict[str, Any]:
    return dict(w.store.values[uses(w)[index]])


def ids(w: Widgets, index: int = 0) -> list[str]:
    return [row["id"] for row in values(w, index).get("windows", [])]


def root(w: Widgets, index: int = 0) -> Any:
    keys = sorted(k for k in w.view.nodes if k.startswith("Tasks@") and k.endswith("/Root"))
    return w.view.nodes[keys[index]]


def buttons(w: Widgets, index: int = 0) -> list[Any]:
    """The Task_Item roots of the ``index``-th Tasks use, in the order of the row."""
    mine = uses(w)[index].split("@")[1] + ".for"
    return [n for k, n in w.view.nodes.items() if f"/Task_Item@{mine}" in k and k.endswith("/Root")]


def labels(w: Widgets, index: int = 0) -> list[str]:
    return [str(b.get("label")) for b in buttons(w, index)]


def shown(w: Widgets, index: int = 0) -> bool:
    return bool(root(w, index).get("visible"))


def start(t: TasksDesk, w: Widgets) -> None:
    """The shell loads the script, as at the end of the start sequence."""
    t.start_kwin()
    assert t.settle(w, lambda: t.kwin.fullscreen_reports >= 1)


def lists(t: TasksDesk, w: Widgets, *records: dict[str, Any], index: int = 0) -> None:
    """The script reports the window list and the row shows it."""
    t.fake.set_windows(list(records))
    assert t.settle(w, lambda: ids(w, index) == [r["id"] for r in records] or not records)


def a(n: int = 1, **kw: Any) -> dict[str, Any]:
    kw.setdefault("title", f"Window {n}")
    kw.setdefault("output", OUT)
    kw.setdefault("app", "fake-app")
    return window(uuid(n), **kw)


# -- the window list is on only while a Tasks module is in use ---------------------------------


def test_with_no_tasks_module_the_shell_answers_no_window_list_and_ignores_one_that_comes(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Label { Text: x }") as w:
        start(t, w)
        assert t.kwin.windows_wanted is False and t.windows.subscribers == 0
        # the reply reaches the fake after the shell has answered: wait for it (a slow runner
        # failed this on an empty list)
        assert t.settle(w, lambda: t.fake.script.replies[-1:] == ['{"windows": false}'], 20)
        assert not t.fake.script.sends_windows
        answer = t.fake.raw("WindowsState", json.dumps([a(1, title=SECRET)]))
        assert json.loads(answer or "") == {"windows": False}
        t.settle(w, lambda: False, 0.3)
        assert t.windows.list() == () and not any(SECRET in x for x in w.lines)


def test_a_tasks_use_turns_the_list_on_and_the_last_one_removed_turns_it_off(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t:
        with tasks_shell(t) as w:
            start(t, w)
            assert t.kwin.windows_wanted and t.windows.subscribers == 1
            assert t.settle(w, lambda: t.fake.script.sends_windows)
        # the module stopped with the shell: the list is off again, the script is told so
        assert not t.kwin.windows_wanted and t.windows.subscribers == 0
        assert t.settle(None, lambda: not t.fake.script.sends_windows)


# -- the row -----------------------------------------------------------------------------------


def test_the_scripts_list_is_a_row_of_buttons_in_the_scripts_order_with_the_active_one_marked(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [
            a(1, title="Alpha", minimized=True),
            a(2, title="Beta", active=True),
            a(3, title="Gamma", attention=True),
        ]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 3)
        assert ids(w) == [uuid(1), uuid(2), uuid(3)]  # the script's order
        first, second, third = buttons(w)
        assert [b.get("selected") for b in (first, second, third)] == [False, True, False]
        assert first.get("role") == "button" and root(w).get("role") == "group"
        assert first.get("label") == "Alpha, fake-app, minimised"
        assert second.get("label") == "Beta, fake-app, active"
        assert third.get("label") == "Gamma, fake-app, wants attention"
        # a minimised window is drawn dimmed; the others are not
        assert float(first.get("opacity")) == pytest.approx(0.5)
        assert float(second.get("opacity")) == pytest.approx(1.0)
        # dimming is not the only cue: a minimised item has a bar under it, an item that wants
        # attention has a dot (AC-MOD-TIT-7)

        def cue(b: Any, name: str) -> bool:
            key = next(k for k, n in w.view.nodes.items() if n is b)
            return bool(w.view.nodes[key.removesuffix("/Root") + "/" + name].get("visible"))

        assert [cue(b, "Minimized") for b in (first, second, third)] == [True, False, False]
        assert [cue(b, "Attention") for b in (first, second, third)] == [False, False, True]
        assert shown(w) and values(w)["has_windows"] is True and values(w)["ready"] is True


def test_the_module_is_hidden_and_takes_no_space_until_there_is_a_window_unless_show_empty(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Tasks { }  Tasks { show_empty: true }") as w:
        start(t, w)
        assert t.settle(w, lambda: values(w).get("ready") is True)
        assert not shown(w, 0) and float(root(w, 0).get("layout_width") or 0) == 0
        assert shown(w, 1)  # show_empty keeps the module's space
        lists(t, w, a(1))
        assert t.settle(w, lambda: shown(w, 0))


def test_a_script_that_is_not_loaded_or_kwin_missing_hides_the_module(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        # the script was never loaded: nothing is ready, nothing is shown
        t.settle(w, lambda: False, 0.3)
        assert values(w)["ready"] is False and not shown(w)
        assert t.windows.available is False


def test_monitor_this_shows_the_windows_on_the_modules_output_and_all_shows_every_one(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Tasks { }  Tasks { monitor: ALL }") as w:
        t.fake.script.windows = [a(1, output=OUT), a(2, output="DP-1"), a(3, output=OUT)]
        start(t, w)
        assert t.settle(w, lambda: ids(w, 1) == [uuid(1), uuid(2), uuid(3)])
        assert ids(w, 0) == [uuid(1), uuid(3)]  # monitor: THIS, the default


def test_two_uses_on_two_monitors_show_different_rows(tmp_path: Path) -> None:
    """The row is chosen by the use's monitor (the name of the output it is on): asked of the
    module with two uses made for two outputs, as the shell makes them for two monitors."""
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        tasks = w.host.loaded["Tasks"].instance
        windows = (
            WindowInfo("1", "One", "x", False, False, (), "HDMI-A-1", False),
            WindowInfo("2", "Two", "x", False, False, (), "DP-1", False),
            WindowInfo("3", "Three", "x", False, False, (), "HDMI-A-1", False),
        )
        params = {"monitor": "THIS", "desktop": "ALL", "icon_size": 18}
        left = UseRecord("Tasks@l", "l", "l", "HDMI-A-1", params)
        right = UseRecord("Tasks@r", "r", "r", "DP-1", params)
        assert [r["id"] for r in tasks.rows(left, windows)] == ["1", "3"]
        assert [r["id"] for r in tasks.rows(right, windows)] == ["2"]


def test_desktop_current_shows_the_windows_on_the_current_desktop_and_on_all_of_them(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Tasks { }  Tasks { desktop: ALL }") as w:
        d0, d1 = t.desktops
        t.fake.script.windows = [
            a(1, desktops=[d0]),
            a(2, desktops=[d1]),
            a(3),  # on all desktops
            a(4, desktops=[d0, d1]),
        ]
        start(t, w)
        assert t.settle(w, lambda: len(ids(w, 1)) == 4)
        assert t.settle(w, lambda: ids(w, 0) == [uuid(1), uuid(3), uuid(4)])
        t.vdm.set("current", d1)  # the user switches the desktop
        assert t.settle(w, lambda: ids(w, 0) == [uuid(2), uuid(3), uuid(4)])
        assert len(ids(w, 1)) == 4


def test_a_new_list_with_one_title_changed_updates_one_button_and_creates_no_node(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1, title="One"), a(2, title="Two"), a(3, title="Three")]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 3)
        nodes = dict(w.view.nodes)
        before = [b for b in buttons(w)]
        t.fake.set_windows([a(1, title="One"), a(2, title="Two, renamed"), a(3, title="Three")])
        assert t.settle(w, lambda: "renamed" in labels(w)[1])
        assert set(w.view.nodes) == set(nodes)  # no node was made or dropped
        assert all(x is y for x, y in zip(buttons(w), before, strict=True))  # the same nodes
        assert labels(w)[0] == "One, fake-app" and labels(w)[2] == "Three, fake-app"


def test_a_window_that_closes_and_one_that_opens_change_the_row(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1), a(2)]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 2)
        t.fake.set_windows([a(2), a(3)])
        assert t.settle(w, lambda: ids(w) == [uuid(2), uuid(3)] and len(buttons(w)) == 2)


def test_the_shells_own_surfaces_never_appear_in_the_row(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [
            a(1, app="tesserae-shell.panel.launcher"),
            a(2, app="org.example.app"),
        ]
        start(t, w)
        assert t.settle(w, lambda: ids(w) == [uuid(2)])


def test_a_malformed_list_leaves_the_row_and_is_one_warning_without_its_content(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1, title="Kept")]
        start(t, w)
        assert t.settle(w, lambda: ids(w) == [uuid(1)])
        for raw in (f'[{{"id": "{SECRET}", "title": 5}}]', f"{SECRET} is not json"):
            t.fake.raw("WindowsState", raw)
        t.settle(w, lambda: False, 0.3)
        assert ids(w) == [uuid(1)] and labels(w) == ["Kept, fake-app"]
        warned = [x for x in w.warnings() if "WindowsState" in x]
        assert len(warned) == 1 and SECRET not in warned[0]
        assert not any(SECRET in x for x in w.lines)


# -- the clicks --------------------------------------------------------------------------------


def one_shots(t: TasksDesk) -> list[tuple[str, str]]:
    """(kind, window id) of each one-shot script KWin was asked to load, read from its text."""
    out = []
    for shot in t.fake.one_shots():
        kind = next(k for k in ("activate", "minimize", "close") if f"-{k}-" in shot.name)
        wid = next(x for x in (uuid(n) for n in range(1, 9)) if f'"{x}"' in shot.text)
        out.append((kind, wid))
    return out


def test_a_click_on_an_inactive_window_activates_it_and_on_the_active_one_minimises_it(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1), a(2, active=True)]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 2)
        first, second = buttons(w)
        w.window.simulate("click", node=first)
        assert wait_for(lambda: one_shots(t) == [("activate", uuid(1))])
        w.window.simulate("click", node=second)
        assert wait_for(lambda: one_shots(t) == [("activate", uuid(1)), ("minimize", uuid(2))])
        assert w.warnings() == [], w.warnings()
        # the module does not predict: the row stays as it was until the script reports
        assert [b.get("selected") for b in buttons(w)] == [False, True]


def test_a_middle_click_closes_the_window_and_the_script_that_does_it_is_unloaded_again(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1), a(2)]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 2)
        node = buttons(w)[1]
        w.window.simulate("pointer_down", node=node, button="middle")
        w.window.simulate("pointer_up", node=node, button="middle")
        assert wait_for(lambda: one_shots(t) == [("close", uuid(2))])
        (shot,) = t.fake.one_shots()
        assert "closeWindow" in shot.text
        assert wait_for(lambda: not t.fake.loaded(shot.name))  # unloaded
        assert t.fake.loaded()  # the shell's own script stays


def test_delete_on_a_focused_task_closes_its_window_and_other_keys_do_not(tmp_path: Path) -> None:
    """TSH-012: the keyboard twin of the middle click."""
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1), a(2)]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 2)
        node = buttons(w)[1]
        node.focus()
        w.window.simulate("key_down", key="x")
        w.window.simulate("key_down", key="delete", ctrl=True)  # a shortcut of the user's
        t.settle(w, lambda: False, 0.2)
        assert one_shots(t) == []
        w.window.simulate("key_down", key="delete")
        assert wait_for(lambda: one_shots(t) == [("close", uuid(2))])


def test_the_wheel_activates_the_next_or_the_previous_window_of_the_row_and_wraps(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1), a(2, active=True), a(3)]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 3)
        second = buttons(w)[1]
        w.window.simulate("wheel", node=second, delta_y=40.0)  # a step down: the next
        assert wait_for(lambda: one_shots(t) == [("activate", uuid(3))])
        w.window.simulate("wheel", node=second, delta_y=-40.0)  # a step up: the previous
        assert wait_for(lambda: one_shots(t)[-1] == ("activate", uuid(1)))
        # from the first window a step up wraps to the last
        t.fake.set_windows([a(1, active=True), a(2), a(3)])
        assert t.settle(w, lambda: buttons(w)[0].get("selected") is True)
        w.window.simulate("wheel", node=buttons(w)[0], delta_y=-40.0)
        assert wait_for(lambda: one_shots(t)[-1] == ("activate", uuid(3)))


def test_a_click_on_a_window_that_has_gone_does_nothing(tmp_path: Path) -> None:
    """The window closed between the list and the click: the click's id is no longer in the list."""
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [a(1)]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 1)
        t.fake.set_windows([])
        assert t.settle(w, lambda: ids(w) == [])
        for name in ("activate", "close"):
            w.host.call_named("Tasks", name, {"id": uuid(1)})
        t.settle(w, lambda: False, 0.2)
        assert t.fake.one_shots() == [] and w.warnings() == []


# -- icons (the desktop-entry index, ctx.icons.app_icon) ---------------------------------------


def icons_of(w: Widgets) -> dict[str, str]:
    return {r["id"]: r["icon"] for r in values(w)["windows"]}


def test_an_applications_icon_is_found_from_its_desktop_file_name(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.entry("org.example.app", "fake-icon", "Example")
        t.fake.script.windows = [
            a(1, app="org.example.app"),  # an entry whose Icon= is in the theme
            a(2, app="not-installed"),  # no entry, no icon of that name: the shipped one
        ]
        start(t, w)
        assert t.settle(w, lambda: icons_of(w).get(uuid(1)) == svg(RED))
        assert icons_of(w)[uuid(2)] == FALLBACK
        assert w.warnings() == []


def test_the_icons_follow_a_theme_change_of_the_portal(tmp_path: Path) -> None:
    """H1: a fake portal changing ``icon-theme`` re-resolves the icons of Tasks."""
    with tasks_desk(tmp_path, theme=None) as t:
        t.icons.set_portal_theme("Fake")
        with tasks_shell(t) as w:
            t.entry("app", "fake-icon")
            t.fake.script.windows = [a(1, app="app")]
            start(t, w)
            assert t.settle(w, lambda: icons_of(w).get(uuid(1)) == svg(RED))
            t.icons.set_portal_theme("Other")  # the portal's SettingChanged
            assert t.settle(w, lambda: icons_of(w).get(uuid(1)) == svg(BLUE))
            t.icons.set_portal_theme("Fake")
            assert t.settle(w, lambda: icons_of(w).get(uuid(1)) == svg(RED))


def test_an_icon_is_read_on_a_worker_never_on_the_loop_thread(tmp_path: Path) -> None:
    import threading

    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        threads: list[str] = []
        real = t.icons.app_icon

        def spy(app: str, size: int) -> str:
            threads.append(threading.current_thread().name)
            return real(app, size)

        t.icons.app_icon = spy  # type: ignore[method-assign]
        t.entry("app", "fake-icon")
        t.fake.script.windows = [a(1, app="app")]
        start(t, w)
        assert t.settle(w, lambda: icons_of(w).get(uuid(1)) == svg(RED))
        assert threads and all(x.startswith("tasks-icons") for x in threads), threads


# -- validation --------------------------------------------------------------------------------


def test_a_param_that_is_not_one_of_the_words_is_refused_with_the_words(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Tasks { monitor: SOME }") as w:
        assert any("monitor must be one of THIS, ALL" in p.message for p in w.problems), [
            p.message for p in w.problems
        ]


def test_a_scrolling_title_does_not_take_clicks_outside_its_own_item(tmp_path: Path) -> None:
    """The owner's check on KWin: a click on the workspace to the left of a task item hit the task
    item. A title wider than its box scrolls to the left inside the item; what has scrolled past
    the item's edge is clipped, so it must not take the pointer either."""
    long = "A very long window title that is much wider than its button " * 3
    row = (
        "FlexBox { Flex: HORIZONTAL, Align_Items: CENTER, Spacing: 12, Children { "
        "Workspaces { } Tasks { show_title: true, max_width: 180 } Spacer { } } }"
    )
    with tasks_desk(tmp_path) as t, tasks_shell(t, row) as w:
        t.fake.script.windows = [a(1, title="Alpha"), a(2, title=long)]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 2)
        first, second = buttons(w)
        w.window.advance(6000)  # the second title has scrolled as far as it goes
        title = next(
            n
            for k, n in w.view.nodes.items()
            if "/Task_Item_0002/Marquee_Text@" in k and k.endswith("/Root")
        )
        (text,) = title.children()
        assert float(text.get("translate_x")) < -50  # it really is scrolled left
        box = second.get("layout_x")
        x_first = first.get("layout_x") + 20  # inside the first item, left of the second one
        assert x_first < box
        w.window.simulate("click", x=x_first, y=first.get("layout_y") + 10)
        assert wait_for(lambda: bool(one_shots(t)))
        assert one_shots(t) == [("activate", uuid(1))]
