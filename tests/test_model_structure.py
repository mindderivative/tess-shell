"""``If``/``Else`` and ``For`` in a module's layout: TEL picks the blocks, the keyed diff keeps the
rest (TEL Integration > If, Else and For; M2 Brief B1)."""

from __future__ import annotations

from typing import Any

import tess_dl
from tess_re import Window

from tess_shell.binder.build import View, build
from tess_shell.model.expand import Expanded, expand
from tess_shell.model.live import LiveTree
from tess_shell.model.store import ValueStore
from tess_shell.schema.shell import read_module, read_shell

HEAD = "---\nTDL: 0.1\nName: {name}\n---\n"

TODO = """
Module {
    FlexBox {
        Name: Row
        Children {
            Text { Name: Clock, Text: {{ time }} }
            If {{ flag }} {
                Text { Name: Yes, Text: yes }
            } Else {
                Text { Name: No, Text: no }
            }
            For w In {{ items }} Key {{ w.id }} {
                Text { Text: {{ w.title }}, Foreground: "#ffffff" }
            }
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
                Children { Todo { } }
            }
        }
    }
}
"""


class Spy:
    def __init__(self, window: Window) -> None:
        self.window = window
        self.applies: list[int] = []
        self.builds = 0

    @property
    def root(self) -> Any:
        return self.window.root

    def apply(self, changes: Any) -> None:
        self.applies.append(len(changes))
        self.window.apply(changes)

    def build(self, spec: Any) -> Any:
        self.builds += 1
        return self.window.build(spec)


class Rig:
    """What the surface manager does, without a compositor."""

    def __init__(self, module_text: str = TODO) -> None:
        mdoc = tess_dl.parse(HEAD.format(name="Todo") + module_text, path="Todo_Module.tdl")
        assert mdoc.document is not None
        module, findings = read_module(mdoc.document, "Todo_Module.tdl")
        assert module is not None, findings
        sdoc = tess_dl.parse(HEAD.format(name="Main_Shell") + SHELL, path="Main_Shell.tdl")
        assert sdoc.document is not None
        shell, findings = read_shell(
            sdoc.document, "Main_Shell.tdl", lambda _: "", {"Todo": module}
        )
        assert shell is not None, findings
        self.expanded: Expanded = expand(
            shell.monitors[0].surfaces[0].children, "P", {"Todo": module}, lambda p: "u", "Main"
        )
        assert self.expanded.errors == []
        self.store = ValueStore()
        for use in self.expanded.uses:
            self.store.add_use(use.module, use.key)
        self.key = self.expanded.uses[0].key
        self.live = LiveTree(self.store, {u.key: u for u in self.expanded.uses})
        self.rebuilds = 0
        self.send_many(time="10:00", flag=True, items=[])
        self.window = Window(400, 40)
        self.view: View = build(self.live.resolve(self.expanded), self.window)
        self.spy = Spy(self.window)
        self.view.window = self.spy  # type: ignore[assignment]

    def send_many(self, **values: object) -> None:
        for k, v in values.items():
            self.store.send("Todo", self.key, k, v)
        self.turn()

    def turn(self) -> None:
        result = self.live.apply_changes(self.store.flush())
        if result.rebuild:
            self.rebuilds += 1
            self.view.rebuild(self.live.resolve(self.expanded))
        elif hasattr(self, "view"):
            self.view.update(result.updates)

    def row(self) -> list[Any]:
        return self.view.nodes[f"{self.key}/Row"].children()

    def texts(self) -> list[str]:
        return [n.get("text") for n in self.row()]


def items(*pairs: tuple[int, str]) -> list[dict[str, Any]]:
    return [{"id": i, "title": t} for i, t in pairs]


def test_the_if_branch_that_holds_is_shown_and_the_other_is_not() -> None:
    rig = Rig()
    assert rig.texts() == ["10:00", "yes"]
    assert f"{rig.key}/Yes" in rig.view.nodes and f"{rig.key}/No" not in rig.view.nodes


def test_flipping_the_condition_swaps_the_branch_and_keeps_the_other_nodes() -> None:
    rig = Rig()
    row, clock = rig.view.nodes[f"{rig.key}/Row"], rig.view.nodes[f"{rig.key}/Clock"]
    rig.send_many(flag=False)
    assert rig.rebuilds == 1 and rig.texts() == ["10:00", "no"]
    assert rig.view.nodes[f"{rig.key}/Row"] == row and rig.view.nodes[f"{rig.key}/Clock"] == clock
    rig.send_many(flag=True)
    assert rig.texts() == ["10:00", "yes"]


def test_a_for_shows_one_copy_of_its_body_per_item() -> None:
    rig = Rig()
    rig.send_many(items=items((1, "a"), (2, "b"), (3, "c")))
    assert rig.texts() == ["10:00", "yes", "a", "b", "c"]


def test_an_item_added_at_the_end_leaves_the_other_entries_untouched() -> None:
    rig = Rig()
    rig.send_many(items=items((1, "a"), (2, "b")))
    before = rig.row()
    rig.spy.applies.clear()
    rig.spy.builds = 0
    rig.send_many(items=items((1, "a"), (2, "b"), (3, "c")))
    assert rig.row()[:4] == before  # the same tre nodes, kept
    assert rig.spy.builds == 1 and rig.spy.applies == []
    assert rig.texts()[-1] == "c"


def test_reordering_the_list_moves_entries_without_rebuilding_them() -> None:
    rig = Rig()
    rig.send_many(items=items((1, "a"), (2, "b"), (3, "c")))
    a, b, c = rig.row()[2:]
    rig.spy.builds = 0
    rig.send_many(items=items((3, "c"), (1, "a"), (2, "b")))
    assert rig.row()[2:] == [c, a, b] and rig.spy.builds == 0
    assert rig.texts()[2:] == ["c", "a", "b"]


def test_a_removed_item_removes_only_its_entry() -> None:
    rig = Rig()
    rig.send_many(items=items((1, "a"), (2, "b"), (3, "c")))
    a, b, c = rig.row()[2:]
    rig.send_many(items=items((1, "a"), (3, "c")))
    assert rig.row()[2:] == [a, c]


def test_a_changed_item_changes_only_that_entrys_text_in_one_apply() -> None:
    rig = Rig()
    rig.send_many(items=items((1, "a"), (2, "b")))
    rig.spy.applies.clear()
    rig.send_many(items=items((1, "a"), (2, "B!")))
    assert rig.spy.applies == [1] and rig.texts()[2:] == ["a", "B!"]


def test_a_plain_slot_in_a_use_with_structure_changes_one_property_through_the_diff() -> None:
    rig = Rig()
    rig.send_many(items=items((1, "a")))
    rig.spy.applies.clear()
    rig.send_many(time="10:01")
    assert rig.spy.applies == [1] and rig.texts()[0] == "10:01"


def test_a_key_nothing_reads_causes_no_rebuild_and_no_call() -> None:
    rig = Rig()
    before = rig.rebuilds
    rig.send_many(unrelated=5)
    assert rig.rebuilds == before and rig.spy.applies == [] and rig.spy.builds == 0


def test_entry_names_are_never_reused_when_an_item_comes_back() -> None:
    rig = Rig()
    rig.send_many(items=items((1, "a"), (2, "b")))
    first = rig.row()[3]
    rig.send_many(items=items((1, "a")))
    rig.send_many(items=items((1, "a"), (2, "b again")))
    assert rig.row()[3] != first  # a new node: TEL gave the returning key a new entry name
    assert rig.texts()[3] == "b again"


def test_a_failing_header_shows_no_entries_and_keeps_the_rest() -> None:
    rig = Rig()
    rig.send_many(items=5)  # a number is not a list
    assert rig.texts() == ["10:00", "yes"] and rig.live.errors >= 1
    rig.send_many(items=items((1, "a")))
    assert rig.texts() == ["10:00", "yes", "a"]


def test_an_if_outside_a_module_is_an_error_at_expand() -> None:
    bad = SHELL.replace("Children { Todo { } }", "Children { If {{ true }} { Spacer { } } }")
    sdoc = tess_dl.parse(HEAD.format(name="S") + bad, path="S.tdl")
    assert sdoc.document is not None
    shell, _ = read_shell(sdoc.document, "S.tdl", lambda _: "", {})
    assert shell is not None
    out = expand(shell.monitors[0].surfaces[0].children, "P", {}, lambda p: "u", "Main")
    assert [e.message for e in out.errors] == ["If and For outside a module are not built yet"]
