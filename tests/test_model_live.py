"""Slots to nodes: a send changes only the node property that reads it (TEL Integration)."""

from __future__ import annotations

from typing import Any

import tess_dl
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import View, build
from tess_shell.model.expand import expand
from tess_shell.model.live import LiveTree
from tess_shell.model.store import ValueStore
from tess_shell.schema.model import ModuleDef
from tess_shell.schema.shell import read_module, read_shell

HEAD = "---\nTDL: 0.1\nName: {name}\n---\n"

CLOCK = """
Module {
    Params {
        suffix { Type: string, Default: "!" }
        size { Type: number, Default: 14 }
    }
    FlexBox {
        Children {
            Text {
                Name: Face
                Text: {{ time }}
                Style { Font_Size: {{ params.size }}, Foreground: "#ffffff" }
            }
            Text {
                Name: Day
                Text: Today is {{ day }}{{ params.suffix }}
            }
            Text { Name: Idle, Text: fixed }
        }
    }
}
"""

SHELL = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top
                Edge: TOP
                Width: EXPAND
                Height: 32
                Children {
                    Clock { Name: A }
                    Clock { Name: B, suffix: "?", size: 20 }
                }
            }
        }
    }
}
"""


class Spy:
    def __init__(self, window: Window) -> None:
        self.window = window
        self.calls: list[list[tuple[Any, dict[str, Any]]]] = []

    def apply(self, changes: Any) -> None:
        self.calls.append(list(changes))
        self.window.apply(changes)


def parse(text: str, name: str, file: str) -> tess_dl.Document:
    result = tess_dl.parse(HEAD.format(name=name) + text, path=file)
    assert not result.errors and result.document is not None
    return result.document


def setup() -> tuple[View, Spy, LiveTree, ValueStore]:
    module, findings = read_module(
        parse(CLOCK, "Clock", "Modules/Clock_Module.tdl"), "Clock_Module.tdl"
    )
    assert module is not None and findings == []
    modules: dict[str, ModuleDef] = {"Clock": module}
    shell, findings = read_shell(
        parse(SHELL, "Main_Shell", "Shells/Main_Shell.tdl"), "Main_Shell.tdl", lambda _: "", modules
    )
    assert shell is not None and findings == []
    bar = shell.monitors[0].surfaces[0]
    expanded = expand(bar.children, "Main_Shell.Main.Top", modules, lambda path: path[-1], "Main")
    assert expanded.errors == []
    store = ValueStore()
    for use in expanded.uses:
        store.add_use(use.module, use.key)
    live = LiveTree(store, {u.key: u for u in expanded.uses})
    for use in expanded.uses:
        store.send("Clock", use.key, "time", "10:00")
        store.send("Clock", use.key, "day", "Mon")
    store.flush()
    nodes = live.resolve(expanded)
    window = Window(400, 40)
    view = build(nodes, window)
    spy = Spy(window)
    view.window = spy  # type: ignore[assignment]
    return view, spy, live, store


def keys(store: ValueStore) -> list[str]:
    return list(store.values)


def test_each_use_has_its_own_key_and_its_own_nodes() -> None:
    view, _, _, store = setup()
    assert keys(store) == ["Clock@A", "Clock@B"]
    assert "Clock@A/Face" in view.nodes and "Clock@B/Face" in view.nodes
    assert view.nodes["Clock@A/Face"].get("text") == "10:00"
    assert view.nodes["Clock@A/Day"].get("text") == "Today is Mon!"
    assert view.nodes["Clock@B/Day"].get("text") == "Today is Mon?"
    assert view.nodes["Clock@A/Face"].get("font_size") == 14
    assert view.nodes["Clock@B/Face"].get("font_size") == 20


def test_a_send_changes_only_the_property_that_reads_it_in_one_apply() -> None:
    view, spy, live, store = setup()
    store.send("Clock", "Clock@A", "time", "10:01")
    update = live.apply_changes(store.flush())
    assert [(n, k) for n, k, _ in update] == [("Clock@A/Face", "Text")]
    assert view.update([(n, k, v) for n, k, v in update]) == []
    assert [len(c) for c in spy.calls] == [1]
    assert view.nodes["Clock@A/Face"].get("text") == "10:01"
    assert view.nodes["Clock@B/Face"].get("text") == "10:00"


def test_a_key_no_slot_reads_causes_no_node_call() -> None:
    view, spy, live, store = setup()
    store.send("Clock", None, "unused", 5)
    assert live.apply_changes(store.flush()) == []
    assert spy.calls == []


def test_a_template_follows_the_key_it_reads_and_keeps_its_literal_parts() -> None:
    view, spy, live, store = setup()
    store.send("Clock", "Clock@B", "day", "Tue")
    update = live.apply_changes(store.flush())
    view.update(update)
    assert view.nodes["Clock@B/Day"].get("text") == "Today is Tue?"
    assert view.nodes["Clock@A/Day"].get("text") == "Today is Mon!"


def test_a_value_that_comes_out_the_same_makes_no_call() -> None:
    _, spy, live, store = setup()
    store.send("Clock", "Clock@A", "time", "10:00")
    assert live.apply_changes(store.flush()) == []
    assert spy.calls == []


def test_two_changes_in_one_turn_are_one_apply() -> None:
    view, spy, live, store = setup()
    store.send("Clock", None, "time", "10:05")
    store.send("Clock", None, "day", "Wed")
    view.update(live.apply_changes(store.flush()))
    assert [len(c) for c in spy.calls] == [4]  # two uses, two nodes each, one call


def test_a_slot_that_errors_keeps_its_last_value_and_logs() -> None:
    view, spy, live, store = setup()
    store.send("Clock", "Clock@A", "time", {"not": "text"})  # a dict where text is needed
    update = live.apply_changes(store.flush())
    assert update == []
    assert view.nodes["Clock@A/Face"].get("text") == "10:00"
    assert live.errors >= 1


def test_a_name_that_is_not_sent_yet_leaves_the_property_unset_then_fills_in() -> None:
    module, _ = read_module(parse(CLOCK, "Clock", "x"), "Clock_Module.tdl")
    assert module is not None
    shell, _ = read_shell(
        parse(SHELL, "Main_Shell", "y"), "Main_Shell.tdl", lambda _: "", {"Clock": module}
    )
    assert shell is not None
    expanded = expand(
        shell.monitors[0].surfaces[0].children, "P", {"Clock": module}, lambda p: p[-1], "Main"
    )
    store = ValueStore()
    for use in expanded.uses:
        store.add_use(use.module, use.key)
    live = LiveTree(store, {u.key: u for u in expanded.uses})
    nodes = live.resolve(expanded)  # nothing sent yet
    window = Window(400, 40)
    view = build(nodes, window)
    assert view.nodes["Clock@A/Face"].get("text") == ""  # unset: the block default
    assert live.errors >= 1
    store.send("Clock", "Clock@A", "time", "09:59")
    view.update(live.apply_changes(store.flush()))
    assert view.nodes["Clock@A/Face"].get("text") == "09:59"


def test_a_misspelled_name_is_reported_at_its_line_and_column_with_the_nearest_name() -> None:
    from loguru import logger

    text = HEAD.format(name="Clock") + CLOCK.replace("{{ time }}", "{{ tme }}")
    module, _ = read_module(
        parse(CLOCK.replace("{{ time }}", "{{ tme }}"), "Clock", "M.tdl"), "M.tdl"
    )
    assert module is not None
    shell, _ = read_shell(parse(SHELL, "S", "S.tdl"), "S.tdl", lambda _: "", {"Clock": module})
    assert shell is not None
    expanded = expand(
        shell.monitors[0].surfaces[0].children, "P", {"Clock": module}, lambda p: p[-1], "Main"
    )
    store = ValueStore()
    for use in expanded.uses:
        store.add_use(use.module, use.key)
        store.send("Clock", use.key, "time", "x")
    store.flush()
    seen: list[str] = []
    sink = logger.add(
        lambda message: seen.append(str(message)), level="WARNING", format="{message}"
    )
    try:
        LiveTree(store, {u.key: u for u in expanded.uses}).resolve(expanded)
    finally:
        logger.remove(sink)
    line = next(i for i, t in enumerate(text.splitlines(), 1) if "{{ tme }}" in t)
    column = text.splitlines()[line - 1].index("tme") + 1
    assert any(f"M.tdl:{line}:{column}:" in s and "time" in s for s in seen), seen
