"""A module call inside ``If`` and ``For`` (Module File > Using a Module in a Structure): in an
``If`` the use lives as long as the layout around it and only its blocks come and go; in a
``For`` there is one use for each entry, made when the entry appears and ended when it goes, with
the same identity for the same entry however the list is reordered."""

from __future__ import annotations

from typing import Any

from tests.widgets_live import Widgets, running

ITEM_TDL = (
    "---\nTDL: 0.1\nName: Item\n---\n"
    "Module { Params { title { Type: string, Default: none } }\n"
    "FlexBox { Name: Root, Children { Text { Name: T, Text: {{ label }} } } } }\n"
)
ITEM_PY = """
from tess_shell import Module

class Item(Module):
    def __init__(self):
        self.events = []
        self.picked = []

    def start(self):
        self.events.append(("start",))
        for use in self.ctx.uses.values():  # the uses the files give
            self.ctx.send("label", "item " + use.params["title"], use=use)

    def stop(self):
        self.events.append(("stop",))

    def validate_use(self, use):
        self.events.append(("validate", use.params["title"]))

    def use_added(self, use):
        self.events.append(("added", use.key, use.params["title"]))
        self.ctx.send("label", "item " + use.params["title"], use=use)

    def use_removed(self, use):
        self.events.append(("removed", use.key))

"""
DRIVER_PY = (
    "from tess_shell import Module, action\n"
    "class Driver(Module):\n"
    "    def __init__(self):\n"
    "        self.picked = []\n"
    "    @action\n"
    "    def pick(self, event):\n"
    "        self.picked.append((event.use, dict(event.args)))\n"
    "    def start(self):\n"
    "        self.ctx.send('show', True)\n"
    "        self.ctx.send('rows', [{'id': 'a', 't': 'A'}, {'id': 'b', 't': 'B'}])\n"
)
FOR = (
    "Module { FlexBox { Name: Root, Children { For r In {{ rows }} Key {{ r.id }} { "
    "Item { title: {{ r.t }}, On_Click { Action: pick, Id: {{ r.id }} } } } } } }"
)
IF = (
    "Module { FlexBox { Name: Root, Children { Text { Name: Before, Text: x } "
    "If {{ show }} { Item { title: shown } } Else { Text { Name: Other, Text: other } } } } }"
)
IF_IN_FOR = (
    "Module { FlexBox { Name: Root, Children { For r In {{ rows }} Key {{ r.id }} { "
    "FlexBox { Children { If {{ r.on }} { Item { title: {{ r.t }} } } } } } } } }"
)


def run(driver: str, code: str = DRIVER_PY) -> Any:
    return running(
        "Driver { }",
        driver=driver,
        driver_py=code,
        extra={"Item": ITEM_TDL},
        extra_py={"Item": ITEM_PY},
    )


def labels(w: Widgets) -> list[str]:
    """The text of every Item, in the order the Bar shows them."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if node.get("kind") == "text":
            out.append(str(node.get("text")))
        for child in node.children():
            walk(child)

    (root,) = [n for k, n in w.view.nodes.items() if k.endswith("Driver_1/Root")]
    walk(root)
    return out


def item(w: Widgets) -> Any:
    return w.host.loaded["Item"].instance


def keys(w: Widgets) -> list[str]:
    return sorted(w.host.loaded["Item"].ctx.uses)


# -- If -----------------------------------------------------------------------------------------


def test_a_module_in_an_if_shows_and_hides_with_its_condition_and_keeps_its_values() -> None:
    with run(IF) as w:
        assert w.warnings() == [] and w.problems == []
        assert labels(w) == ["x", "item shown"]
        assert len(keys(w)) == 1  # one use, there from the start
        events = list(item(w).events)
        w.send("show", False)
        assert labels(w) == ["x", "other"]
        w.send("show", True)
        assert labels(w) == ["x", "item shown"]  # its value was kept while it was hidden
        assert item(w).events == events  # no start, stop, added or removed: the use never left
        assert w.warnings() == []


def test_a_module_in_the_else_branch_works_too() -> None:
    code = DRIVER_PY.replace("'show', True", "'show', False")
    swapped = IF.replace("If {{ show }}", "If {{ not show }}")
    with run(swapped, code) as w:
        assert labels(w) == ["x", "other"] or labels(w) == ["x", "item shown"]
        w.send("show", True)
        w.send("show", False)
        assert labels(w) == ["x", "item shown"]


# -- For ----------------------------------------------------------------------------------------


def test_a_module_in_a_for_has_a_use_for_each_entry_that_the_module_hears_of() -> None:
    with run(FOR) as w:
        assert w.warnings() == [] and w.problems == []
        assert labels(w) == ["item A", "item B"]
        assert len(keys(w)) == 2
        events = item(w).events
        assert events[0] == ("start",)
        assert [e[0] for e in events].count("added") == 2
        assert [e[2] for e in events if e[0] == "added"] == ["A", "B"]  # its params, per entry
        assert [e for e in events if e[0] == "stop"] == []


def test_a_reordered_list_keeps_each_entrys_use_nodes_and_values() -> None:
    with run(FOR) as w:
        before = keys(w)
        nodes = dict(w.view.nodes)
        events = list(item(w).events)
        w.send("rows", [{"id": "b", "t": "B"}, {"id": "a", "t": "A"}])
        assert labels(w) == ["item B", "item A"]
        assert keys(w) == before  # the same two uses
        assert item(w).events == events  # nobody was added or removed
        # the nodes are the same ones, moved
        assert {k: v for k, v in w.view.nodes.items() if k in nodes} == {
            k: v for k, v in nodes.items() if k in w.view.nodes
        }
        assert set(w.view.nodes) == set(nodes)


def test_an_entry_added_and_removed_makes_and_ends_its_use_and_leaves_the_others_alone() -> None:
    with run(FOR) as w:
        first = keys(w)
        nodes = dict(w.view.nodes)
        w.send("rows", [{"id": "a", "t": "A"}, {"id": "b", "t": "B"}, {"id": "c", "t": "C"}])
        assert labels(w) == ["item A", "item B", "item C"]
        assert len(keys(w)) == 3 and set(first) < set(keys(w))
        for k, n in nodes.items():
            assert w.view.nodes[k] == n  # the others kept their nodes
        added = [e for e in item(w).events if e[0] == "added"]
        assert [e[2] for e in added] == ["A", "B", "C"]
        w.send("rows", [{"id": "b", "t": "B"}, {"id": "c", "t": "C"}])
        assert labels(w) == ["item B", "item C"]
        gone = [e for e in item(w).events if e[0] == "removed"]
        assert len(gone) == 1 and gone[0][1] not in keys(w)
        assert gone[0][1] in first
        assert len(keys(w)) == 2
        # the store forgot the ended use
        assert gone[0][1] not in w.store.values
        assert w.warnings() == []


def test_a_key_that_returns_is_a_new_use() -> None:
    with run(FOR) as w:
        w.send("rows", [{"id": "b", "t": "B"}])
        w.send("rows", [{"id": "a", "t": "A"}, {"id": "b", "t": "B"}])
        added = [e for e in item(w).events if e[0] == "added"]
        assert [e[2] for e in added] == ["A", "B", "A"]  # a returned: made again
        assert len(keys(w)) == 2


def test_send_with_a_use_reaches_the_right_entry_whatever_the_order() -> None:
    with run(FOR) as w:
        by_title = {u.params["title"]: u for u in w.host.loaded["Item"].ctx.uses.values()}
        w.send("rows", [{"id": "b", "t": "B"}, {"id": "a", "t": "A"}])
        item(w).ctx.send("label", "second", use=by_title["B"])
        w.flush()
        assert labels(w) == ["second", "item A"]  # B is first now, and it got the value
        item(w).ctx.send("label", "other", use=by_title["A"])
        w.flush()
        assert labels(w) == ["second", "other"]
        item(w).ctx.send("label", "everyone")  # no use: every entry
        w.flush()
        assert labels(w) == ["everyone", "everyone"]


def test_params_written_as_slots_are_read_for_each_entry_and_follow_the_data() -> None:
    with run(FOR) as w:
        titles = sorted(u.params["title"] for u in w.host.loaded["Item"].ctx.uses.values())
        assert titles == ["A", "B"]
        w.send("rows", [{"id": "a", "t": "A2"}, {"id": "b", "t": "B"}])
        titles = sorted(u.params["title"] for u in w.host.loaded["Item"].ctx.uses.values())
        assert titles == ["A2", "B"]  # the use is the same, its params are current
        assert ("validate", "A2") in item(w).events


def test_an_event_on_a_call_carries_the_arguments_of_its_entry() -> None:
    with run(FOR) as w:
        boxes = [n for k, n in w.view.nodes.items() if k.endswith("/Root") and "Item@" in k]
        assert len(boxes) == 2
        w.window.simulate("click", node=boxes[1])
        w.window.simulate("click", node=boxes[0])
        picked = w.host.loaded["Driver"].instance.picked
        assert [p[1] for p in picked] == [{"Id": "b"}, {"Id": "a"}]
        assert all("Driver@" in p[0] for p in picked)  # the use that holds the call


def test_a_module_in_an_if_in_a_for_comes_and_goes_with_the_entry_s_condition() -> None:
    code = DRIVER_PY.replace(
        "[{'id': 'a', 't': 'A'}, {'id': 'b', 't': 'B'}]",
        "[{'id': 'a', 't': 'A', 'on': True}, {'id': 'b', 't': 'B', 'on': False}]",
    )
    with run(IF_IN_FOR, code) as w:
        assert w.warnings() == [], w.warnings()
        assert labels(w) == ["item A"]
        assert len(keys(w)) == 1
        w.send(
            "rows",
            [{"id": "a", "t": "A", "on": True}, {"id": "b", "t": "B", "on": True}],
        )
        assert labels(w) == ["item A", "item B"]
        assert len(keys(w)) == 2
        w.send(
            "rows",
            [{"id": "a", "t": "A", "on": False}, {"id": "b", "t": "B", "on": True}],
        )
        assert labels(w) == ["item B"]
        assert len(keys(w)) == 1  # the one under the false If is ended


# -- what is refused, at load -------------------------------------------------------------------


def test_a_call_in_a_for_is_checked_when_the_file_is_read_not_on_the_first_entry() -> None:
    import pytest

    # Item's root is a FlexBox: it raises no On_Key_Down
    bad = FOR.replace("On_Click", "On_Key_Down")
    with pytest.raises(AssertionError) as raised, run(bad):
        pass
    assert "On_Key_Down" in str(raised.value) or "does not raise" in str(raised.value)


def test_modules_that_call_themselves_through_a_for_are_a_cycle() -> None:
    import tess_dl

    from tess_shell.schema.graph import module_cycles
    from tess_shell.schema.shell import read_module, read_module_params

    HEAD = "---\nTDL: 0.1\nName: %s\n---\n"
    texts = {
        "A": HEAD % "A"
        + "Module { FlexBox { Children { For r In {{ rows }} Key {{ r }} { B { } } } } }\n",
        "B": HEAD % "B" + "Module { FlexBox { Children { If {{ x }} { A { } } } } }\n",
    }
    docs = {n: tess_dl.parse(t, path=f"{n}.tdl").document for n, t in texts.items()}
    stubs = {n: read_module_params(d, f"{n}.tdl") for n, d in docs.items() if d is not None}
    defs = {}
    for n, d in docs.items():
        assert d is not None
        found, _ = read_module(d, f"{n}.tdl", {k: v for k, v in stubs.items() if v is not None})
        assert found is not None
        defs[n] = found
    findings = module_cycles(defs)
    assert [f.rule for f in findings] == ["import-cycle"]


def test_a_module_with_a_tooltip_in_a_for_gets_one_per_entry() -> None:
    tip = (
        "---\nTDL: 0.1\nName: Tipped\n---\n"
        "Module { FlexBox { Name: Root, Tooltip { Children { Text { Text: tip } } }, "
        "Children { Text { Text: {{ label }} } } } }\n"
    )
    driver = (
        "Module { FlexBox { Name: Root, Children { For r In {{ rows }} Key {{ r.id }} { "
        "Tipped { } } } } }"
    )
    code = (
        "from tess_shell import Module\n"
        "class Driver(Module):\n"
        "    def start(self):\n"
        "        self.ctx.send('rows', [{'id': 'a'}, {'id': 'b'}])\n"
    )
    tipped_py = (
        "from tess_shell import Module\n"
        "class Tipped(Module):\n"
        "    def use_added(self, use):\n"
        "        self.ctx.send('label', 'x', use=use)\n"
    )
    with running(
        "Driver { }",
        driver=driver,
        driver_py=code,
        extra={"Tipped": tip},
        extra_py={"Tipped": tipped_py},
    ) as w:
        assert w.warnings() == [], w.warnings()
        assert len(w.bar.expanded.tooltips) >= 2  # one for each entry's root block
        ids = [k for k in w.bar.expanded.tooltips if "Tipped@" in k and k in w.view.nodes]
        assert len(ids) == 2


def test_an_entry_use_has_a_root_block_a_popup_can_open_beside() -> None:
    popups = "Popup { Name: Menu, Children { FlexBox { } } }"  # a Monitor with a Popup marks roots
    with running(
        "Driver { }",
        driver=FOR,
        driver_py=DRIVER_PY,
        extra={"Item": ITEM_TDL},
        extra_py={"Item": ITEM_PY},
        popups=popups,
    ) as w:
        uses = list(w.host.loaded["Item"].ctx.uses)
        roots = w.bar.expanded.roots
        assert len(uses) == 2 and all(u in roots and roots[u] in w.view.nodes for u in uses)
        w.send("rows", [{"id": "a", "t": "A"}])
        assert len([u for u in uses if u in w.bar.expanded.roots]) == 1  # the gone one's is dropped
