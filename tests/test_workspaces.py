"""The shipped Workspaces module (Workspaces Module): the list as it arrives, then the module on a
fake KWin virtual desktop manager on a private session bus, drawn by the real binder in a headless
Bar, with the click simulated on the button's node."""

from __future__ import annotations

import importlib.util
from types import ModuleType
from typing import Any

import pytest

from tess_shell.module import Event
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.modules_rig import Desk, desk, shell
from tests.widgets_live import SHIPPED, Widgets

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def load() -> ModuleType:
    path = SHIPPED / "Workspaces" / "Workspaces_Module.py"
    spec = importlib.util.spec_from_file_location("shipped_workspaces", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


W = load()


# -- the list as it arrives ---------------------------------------------------------------------


def test_the_list_is_read_as_it_arrives_whatever_the_signature_says() -> None:
    uss = [[0, "a", "Main"], [1, "b", "Code"]]  # a(uss): what ``get-property`` printed
    iss = [(7, "a", "Main"), (-1, "b", "Code")]  # a(iss): what ``introspect`` printed; any integer
    for raw in (uss, iss):
        got = W.records(raw, "b")
        assert [(d["id"], d["number"], d["name"], d["current"]) for d in got] == [
            ("a", 1, "Main", False),
            ("b", 2, "Code", True),
        ]


def test_the_number_is_the_position_plus_one_and_an_empty_name_shows_it() -> None:
    got = W.records([[5, "a", ""], [9, "b", "Code"]], "a")
    assert [(d["number"], d["label"]) for d in got] == [(1, "1"), (2, "Code")]
    assert got[0]["name"] == ""  # the record keeps the real name


@pytest.mark.parametrize(
    "raw",
    [
        [],
        "x",
        None,
        [["a", "id", "Main"]],  # the first field is not an integer
        [[0, 1, "Main"]],
        [[0, "id"]],
        [[0, "id", "Main", "extra"]],
        [[True, "id", "Main"]],
        [[0, "", "Main"]],
        [[0, "a", "x"], [1, "a", "y"]],  # a repeated id
    ],
)
def test_any_other_shape_is_refused(raw: object) -> None:
    with pytest.raises(ValueError):
        W.records(raw, "")


# -- the module on a fake KWin ------------------------------------------------------------------


def buttons(w: Widgets, use: str | None = None) -> list[Any]:
    """The desktop buttons in the order the Bar shows them: the children of a use's ``Root``
    A hidden module (a root that is not visible) shows none. (tre hands out a new proxy for a node
    on each call, but proxies of one node compare equal.)"""
    found: list[Any] = []
    for key, root in w.view.nodes.items():
        if key.endswith("/Root") and (use is None or key.startswith(use)) and root.get("visible"):
            found.extend(c for c in root.children() if c.get("kind") == "box")
    return found


def face(button: Any) -> str:
    (text,) = [c for c in button.children() if c.get("kind") == "text"]
    return str(text.get("text"))


def faces(w: Widgets, use: str | None = None) -> list[str]:
    return [face(b) for b in buttons(w, use)]


def current(w: Widgets, use: str | None = None) -> list[bool]:
    return [bool(b.get("selected")) for b in buttons(w, use)]


def values(w: Widgets) -> dict[str, Any]:
    (use,) = w.uses
    return dict(w.store.values[use])


def info(w: Widgets) -> list[str]:
    return [x for x in w.lines if "| INFO " in x and "Bar Top_Bar" not in x]


@needs_daemon
def test_two_desktops_show_their_names_and_the_first_is_the_current_one() -> None:
    with desk() as d:
        fake, _, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"]), (w.log(), values(w))
            assert current(w) == [True, False]
            first, second = buttons(w)
            assert first.get("role") == "button" and first.get("label") == "Desktop 1, Main"
            assert second.get("label") == "Desktop 2, Code"
            root = [n for k, n in w.view.nodes.items() if k.endswith("/Root")][0]
            assert root.get("role") == "group" and root.get("label") == "Workspaces"
            v = values(w)
            assert v["current"] == ids[0] and v["ready"] is True and v["available"] is True
            assert [x for x in w.warnings()] == []
            # the Default stylesheet gives the current one its look: raised, outlined in primary
            primary = (91, 151, 201, 255)  # $color.primary of the Default theme
            assert first.get("stroke_width") == 2 and first.get("stroke_color") == primary
            assert second.get("stroke_width") != 2


@needs_daemon
def test_the_mark_follows_the_desktops_own_switch_within_one_loop_turn() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin(("A", "B", "C"))
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: current(w) == [True, False, False])
            instance = w.host.loaded["Workspaces"].instance
            obj.set("current", ids[2])
            assert wait_for(lambda: instance.sent["current"] == ids[2])  # sent on the dbus thread
            w.flush()  # one loop turn
            w.advance(16)
            assert current(w) == [False, False, True]


@needs_daemon
def test_a_click_sets_current_on_kwin_and_the_mark_follows() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            first, second = buttons(w)
            w.window.simulate("click", node=second)  # on the loop thread, returns at once
            assert d.settle(w, lambda: current(w) == [False, True])
            assert obj.sets == [("current", ids[1])]
            w.window.simulate("click", node=first)
            assert d.settle(w, lambda: current(w) == [True, False])
            assert obj.sets == [("current", ids[1]), ("current", ids[0])]


@needs_daemon
def test_a_click_never_blocks_the_loop() -> None:
    import time

    with desk() as d:
        fake, obj, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            second = buttons(w)[1]
            started = time.perf_counter()
            w.window.simulate("click", node=second)
            assert time.perf_counter() - started < 0.05
            assert d.settle(w, lambda: current(w) == [False, True])


@needs_daemon
def test_creating_renaming_and_removing_keep_the_other_buttons_nodes() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin(("Main", "Code"))
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            main, code = buttons(w)

            def desktops(*names: str) -> Any:
                return [[i, ids[i] if i < len(ids) else f"new-{i}", n] for i, n in enumerate(names)]

            obj.set("desktops", desktops("Main", "Code", "Web"))  # created
            assert d.settle(w, lambda: faces(w) == ["Main", "Code", "Web"])
            kept = buttons(w)
            assert kept[0] == main and kept[1] == code
            web = kept[2]
            obj.set("desktops", desktops("Main", "Editor", "Web"))  # renamed
            assert d.settle(w, lambda: faces(w) == ["Main", "Editor", "Web"])
            assert buttons(w) == [main, code, web]  # the same nodes, one text changed
            assert code.get("label") == "Desktop 2, Editor"
            obj.set("desktops", [desktops("Main", "Editor", "Web")[i] for i in (0, 2)])  # removed
            assert d.settle(w, lambda: faces(w) == ["Main", "Web"])
            assert buttons(w)[0] == main and buttons(w)[1] == web
            assert [x for x in w.warnings()] == []


@needs_daemon
def test_a_rename_changes_only_that_buttons_text() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin(("Main", "Code", "Web"))
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code", "Web"])
            before = [(b, b.get("selected"), b.get("label")) for b in buttons(w)]
            obj.set("desktops", [[0, ids[0], "Main"], [1, ids[1], "Code!"], [2, ids[2], "Web"]])
            assert d.settle(w, lambda: faces(w) == ["Main", "Code!", "Web"])
            after = [(b, b.get("selected"), b.get("label")) for b in buttons(w)]
            assert [a[0] for a in after] == [b[0] for b in before]
            assert [a[1] for a in after] == [b[1] for b in before]
            assert [a[2] for a in after] == [
                "Desktop 1, Main",
                "Desktop 2, Code!",
                "Desktop 3, Web",
            ]


@needs_daemon
def test_label_number_shows_numbers_and_an_empty_name_shows_its_number() -> None:
    with desk() as d:
        fake, _, _ = d.kwin(("Main", "", "Web"))
        fake.up()
        with shell(d, "Workspaces { }\nWorkspaces { label: number }") as w:
            first, second = (use for use in w.uses)
            assert d.settle(w, lambda: faces(w, first) == ["Main", "2", "Web"]), faces(w, first)
            assert faces(w, second) == ["1", "2", "3"]
            assert buttons(w, first)[1].get("label") == "Desktop 2, 2"


@needs_daemon
def test_the_a_iss_shape_works_the_same() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin(signature="a(iss)")
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            assert current(w) == [True, False]


@needs_daemon
def test_with_no_kwin_the_module_is_hidden_with_one_info_line_and_recovers() -> None:
    with desk() as d:  # sway: nobody owns org.kde.KWin
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: values(w).get("available") is False)
            d.settle(w, lambda: False, 0.4)
            assert buttons(w) == [] and values(w)["available"] is False
            said = [x for x in info(w) if "org.kde.KWin" in x or "KWin" in x]
            assert len(said) == 1 and "| WARNING " not in said[0], said
            assert [x for x in w.lines if "| WARNING " in x or "| ERROR " in x] == []
            fake, _, _ = d.kwin()
            fake.up()  # a KWin starts
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])


@needs_daemon
def test_kwin_restarting_hides_the_module_and_shows_it_again() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            fake.drop()  # the compositor dies
            assert d.settle(w, lambda: buttons(w) == [])
            assert values(w)["available"] is False
            obj.silent_set("desktops", [[0, ids[0], "Main"], [1, ids[1], "Code"], [2, "z", "New"]])
            obj.silent_set("current", ids[1])
            fake.up()  # and comes back with another list
            assert d.settle(w, lambda: faces(w) == ["Main", "Code", "New"])
            assert current(w) == [False, True, False]
            assert [x for x in w.lines if "| ERROR " in x] == []


@needs_daemon
def test_a_burst_of_signals_is_one_refresh_and_the_module_reads_what_kwin_now_says() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            instance = w.host.loaded["Workspaces"].instance
            runs: list[int] = []
            real = instance.refresh

            async def counting() -> None:
                runs.append(1)
                await real()

            instance.refresh = counting
            # KWin changed the list and says so only by signals (no PropertiesChanged)
            obj.silent_set("desktops", [[0, ids[0], "Main"], [1, ids[1], "Code"], [2, "n", "New"]])

            async def burst() -> None:  # KWin emits a burst together, in one write
                assert obj._iface is not None
                for _ in range(6):
                    obj._iface.desktopCreated("n", 2, "New")  # type: ignore[attr-defined]

            obj.service.thread.run(burst())
            assert d.settle(w, lambda: faces(w) == ["Main", "Code", "New"])
            assert 1 <= len(runs) <= 3, runs  # a burst, not one read per signal (six)


@needs_daemon
def test_a_click_on_an_id_that_is_not_in_the_list_is_refused_and_logged_once() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            instance = w.host.loaded["Workspaces"].instance
            for _ in range(3):
                instance.switch(Event("click", w.uses[0], {"Id": "gone"}))
            instance.switch(Event("click", w.uses[0], {}))
            d.settle(w, lambda: False, 0.2)
            assert obj.sets == []
            refused = [
                x for x in w.lines if "| WARNING " in x and "is not one of the desktops" in x
            ]
            assert len(refused) == 2  # 'gone' once, a missing id once


@needs_daemon
def test_a_failing_set_is_logged_once_and_the_buttons_keep_the_real_desktop() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin()
        obj.writable = frozenset()  # KWin refuses the write
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            second = buttons(w)[1]
            for _ in range(3):
                w.window.simulate("click", node=second)
            assert d.settle(w, lambda: any("switching the desktop failed" in x for x in w.lines))
            d.settle(w, lambda: False, 0.2)
            failed = [x for x in w.lines if "switching the desktop failed" in x]
            assert len(failed) == 1
            assert current(w) == [True, False]  # it did not change


@needs_daemon
def test_an_unreadable_list_keeps_the_last_one_with_one_warning() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            for _ in range(2):
                obj.set("desktops", [])
                obj.set("current", ids[1])
            assert d.settle(w, lambda: current(w) == [False, True])
            assert faces(w) == ["Main", "Code"]
            warned = [x for x in w.lines if "| WARNING " in x and "desktops is not understood" in x]
            assert len(warned) == 1


@needs_daemon
def test_a_list_that_was_never_readable_leaves_the_module_hidden() -> None:
    with desk() as d:
        fake, obj, ids = d.kwin()
        obj.values["desktops"] = []
        fake.up()
        with shell(d, "Workspaces { }") as w:
            d.settle(w, lambda: False, 0.4)
            assert values(w)["ready"] is False and buttons(w) == []
            obj.set("desktops", [[0, "a", "One"]])
            assert d.settle(w, lambda: faces(w) == ["One"])


@needs_daemon
def test_the_module_starts_no_thread_and_never_waits_on_the_loop() -> None:
    import threading

    with desk() as d:
        fake, _, _ = d.kwin()
        fake.up()
        before = {t.name for t in threading.enumerate()}
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: faces(w) == ["Main", "Code"])
            assert {t.name for t in threading.enumerate()} - before == set()
    source = (SHIPPED / "Workspaces" / "Workspaces_Module.py").read_text()
    assert "Thread(" not in source and "run_blocking" not in source and "sleep" not in source
    assert "every(" not in source and "on_tick" not in source


@needs_daemon
def test_per_signal_module_work_is_far_under_a_millisecond(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with desk() as d:
        fake, obj, ids = d.kwin(("A", "B", "C", "D"))
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: len(faces(w)) == 4)
            start = len(d.layer.callback_times.get("Workspaces", ()))
            for i in range(150):
                obj.set("current", ids[i % 4])
            assert d.settle(w, lambda: len(d.layer.callback_times["Workspaces"]) - start >= 100, 10)
            count, p50, p99, worst = d.layer.callback_summary("Workspaces")
            with capsys.disabled():
                print(
                    f"\nWorkspaces callback: n={count} p50={p50 * 1e6:.1f} us "
                    f"p99={p99 * 1e6:.1f} us max={worst * 1e6:.1f} us"
                )
            assert p99 < 0.001


def test_desk_type_is_exported() -> None:
    assert Desk is not None


@needs_daemon
def test_the_mark_follows_a_kwin_that_only_emits_current_changed() -> None:
    """On the maintainer's KWin the mark did not move with Ctrl+F2 and a click back did nothing:
    ``current`` changed with the ``currentChanged`` signal and no ``PropertiesChanged``."""
    with desk() as d:
        fake, obj, ids = d.kwin()
        fake.up()
        with shell(d, "Workspaces { }") as w:
            assert d.settle(w, lambda: current(w) == [True, False])
            obj.silent_set("current", ids[1])
            obj.emit("currentChanged", ids[1])
            assert d.settle(w, lambda: current(w) == [False, True])
            first, _ = buttons(w)
            w.window.simulate("click", node=first)  # back to the first: must reach KWin
            assert d.settle(w, lambda: obj.sets == [("current", ids[0])])
