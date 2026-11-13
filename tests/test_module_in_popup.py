"""A module call inside a ``For`` in a Popup (Module File > Using a Module in a Structure): the
uses of a Popup's entries exist while the Popup is open, are made when it opens (or when the
entries change while it is open) and end when it closes. The entries here come from
``caller.data`` and from a module's own values."""

from __future__ import annotations

from typing import Any

from tests.widgets_live import Widgets, running

TRAY_TDL = (
    "---\nTDL: 0.1\nName: TrayMenu\n---\n"
    "Module { FlexBox { Name: Root, Flex: VERTICAL, Children { "
    "Menu { Children { "
    "For e In {{ caller.data.items }} Key {{ e.id }} { "
    "MenuItem { Text: {{ e.text }}, On_Click { Action: pick, Id: {{ e.id }} } } } "
    "For x In {{ extra }} Key {{ x.id }} { MenuItem { Text: {{ x.text }} } } "
    "} } } } }\n"
)
TRAY_PY = """
from tess_shell import Module, action

class TrayMenu(Module):
    def __init__(self):
        self.picked = []

    def start(self):
        self.ctx.send("extra", [])

    @action
    def pick(self, event):
        self.picked.append((event.use, dict(event.args)))
"""
ITEM_PY_NOTE = """
"""
POPUPS = (
    "Popup { Name: Tray_Menu, Attach: BOTTOM, "
    "Style { Background: $color.surface_raised, Corner_Radius: 8 }, "
    "Children { TrayMenu { } } }"
)
DRIVER = (
    "Module { FlexBox { Name: Root, Height: 20, Children { "
    "FlexBox { Name: Open, On_Click: open_it, Width: 40, Height: 20 } } } }"
)
DRIVER_PY = """
from tess_shell import Module, action

class Driver(Module):
    def __init__(self):
        self.items = [{"id": "a", "text": "Alpha"}, {"id": "b", "text": "Beta"}]

    @action
    def open_it(self, event):
        self.ctx.popup("Tray_Menu", data={"items": self.items})
"""
# a MenuItem module that logs its lifecycle (the shipped one has no Python of note)


def quiet(w: Any) -> list[str]:
    """Warnings and errors except "took N ms on the loop" (machine load, not the test)."""
    return [x for x in w.warnings() if "ms on the loop" not in x]


def go(**kwargs: Any) -> Any:
    return running(
        "Driver { }",
        driver=DRIVER,
        driver_py=DRIVER_PY,
        extra={"TrayMenu": TRAY_TDL},
        extra_py={"TrayMenu": TRAY_PY},
        popups=POPUPS,
        **kwargs,
    )


def driver(w: Widgets) -> Any:
    return w.host.loaded["Driver"].instance


def open_popup(w: Widgets) -> Any:
    w.window.simulate("click", node=w.of_use("Driver", "Open"))
    op = w.manager.popups.current
    assert op is not None, w.log()[-3000:]
    return op


def labels(op: Any) -> list[str]:
    return [
        str(n.get("label"))
        for k, n in op.view.nodes.items()
        if k.endswith("/Root") and n.get("role") == "menuitem"
    ]


def item_uses(w: Widgets) -> list[str]:
    return sorted(k for k in w.host.loaded["MenuItem"].ctx.uses)


def test_the_entries_of_a_popup_have_uses_only_while_it_is_open() -> None:
    with go() as w:
        assert quiet(w) == [] and w.problems == []
        assert item_uses(w) == []  # nothing open: no entry, but the module is loaded
        op = open_popup(w)
        assert labels(op) == ["Alpha", "Beta"]
        assert len(item_uses(w)) == 2
        assert quiet(w) == [], quiet(w)
        w.manager.popups.close(op, "test")
        assert item_uses(w) == []  # ended with the popup
        assert not [k for k in w.store.values if k.startswith("MenuItem@")]


def test_a_reopened_popup_with_other_data_gets_new_entries() -> None:
    with go() as w:
        op = open_popup(w)
        first = item_uses(w)
        w.manager.popups.close(op, "test")
        driver(w).items = [{"id": "c", "text": "Gamma"}]
        op = open_popup(w)
        assert labels(op) == ["Gamma"]
        assert len(item_uses(w)) == 1 and item_uses(w)[0] not in first or len(first) == 2


def test_a_click_on_an_entry_runs_the_action_with_its_arguments_and_closes() -> None:
    with go() as w:
        op = open_popup(w)
        beta = [n for n in op.view.nodes.values() if n.get("label") == "Beta"][0]
        op.window.simulate("click", node=beta)
        chosen = w.host.loaded["TrayMenu"].instance.picked
        assert [c[1] for c in chosen] == [{"Id": "b"}]
        op.window.advance(50)
        assert w.manager.popups.current is None
        assert item_uses(w) == []


def test_entries_from_a_module_value_change_while_the_popup_is_open() -> None:
    with go() as w:
        op = open_popup(w)
        tray = w.host.loaded["TrayMenu"].instance
        before = dict(op.view.nodes)
        tray.ctx.send("extra", [{"id": "x", "text": "Extra"}])
        w.flush()
        assert labels(op) == ["Alpha", "Beta", "Extra"]
        assert len(item_uses(w)) == 3
        for k, n in before.items():
            assert op.view.nodes[k] == n  # the others kept their nodes
        tray.ctx.send("extra", [])
        w.flush()
        assert labels(op) == ["Alpha", "Beta"] and len(item_uses(w)) == 2


def test_a_send_to_an_ended_use_is_dropped_with_one_debug_line() -> None:
    with go() as w:
        op = open_popup(w)
        use = next(iter(w.host.loaded["MenuItem"].ctx.uses.values()))
        w.manager.popups.close(op, "test")
        w.host.loaded["MenuItem"].ctx.send("label", "late", use=use)
        w.flush()
        late = [x for x in w.lines if use.key in x and "has ended" in x]
        assert len(late) == 1 and "| DEBUG " in late[0]
        assert not [x for x in w.lines if "unknown use" in x]


def test_an_entry_use_can_open_a_popup_beside_itself() -> None:
    # the use's root block is known to the Popup machinery (a ctx.popup from an entry)
    with go() as w:
        op = open_popup(w)
        uses = list(w.host.loaded["MenuItem"].ctx.uses)
        roots = op.plan.expanded.roots
        assert all(u in roots and roots[u] in op.view.nodes for u in uses), (uses, roots)
        w.manager.popups.close(op, "test")
        assert not any(u in roots for u in uses)  # taken back with the popup


def test_two_popups_with_the_same_module_do_not_collide() -> None:
    popups = POPUPS + POPUPS.replace("Tray_Menu", "Tray_Menu_Two")
    code = DRIVER_PY.replace(
        '        self.ctx.popup("Tray_Menu", data={"items": self.items})',
        '        self.ctx.popup("Tray_Menu", data={"items": self.items})\n'
        '        self.ctx.popup("Tray_Menu_Two", data={"items": self.items[:1]},\n'
        "                       use=self.ctx.caller.key)",
    )
    with running(
        "Driver { }",
        driver=DRIVER,
        driver_py=code,
        extra={"TrayMenu": TRAY_TDL},
        extra_py={"TrayMenu": TRAY_PY},
        popups=popups,
    ) as w:
        w.window.simulate("click", node=w.of_use("Driver", "Open"))
        # the second call replaces the first (one popup at a time at the top level): its entries
        # are the only ones alive, and the first one's ended
        op = w.manager.popups.current
        assert op is not None and op.popup.name == "Tray_Menu_Two"
        assert len(item_uses(w)) == 1
        assert not [x for x in w.lines if "| ERROR " in x], [x for x in w.lines if "| ERROR " in x]


def test_a_submenu_from_an_entry_hangs_off_the_entry_and_closes_with_its_parent() -> None:
    tray = TRAY_TDL.replace(
        "MenuItem { Text: {{ e.text }}, On_Click",
        "MenuItem { Text: {{ e.text }}, Submenu: Sub_Menu, On_Click",
    )
    sub = (
        "Popup { Name: Sub_Menu, Style { Background: $color.surface_raised }, "
        'Children { Menu { Children { MenuItem { Text: "Deep" } } } } }'
    )
    with running(
        "Driver { }",
        driver=DRIVER,
        driver_py=DRIVER_PY,
        extra={"TrayMenu": tray},
        extra_py={"TrayMenu": TRAY_PY},
        popups=POPUPS + sub,
    ) as w:
        op = open_popup(w)
        alpha = [n for n in op.view.nodes.values() if n.get("label") == "Alpha"][0]
        op.window.simulate("click", node=alpha)  # an item with a submenu opens it at once
        assert op.sub is not None and op.sub.popup.name == "Sub_Menu"
        assert op.sub.parent_op is op
        assert len(item_uses(w)) == 3  # two entries of the parent and the static "Deep"
        w.manager.popups.close(op, "test")
        assert w.manager.popups.current is None
        # only the submenu's static item is left: it is a use the files give, not an entry's
        assert item_uses(w) == ["MenuItem@Main_Shell.Main.Sub_Menu.MenuItem_1"]
        assert quiet(w) == [], quiet(w)


def test_a_submenu_from_an_entry_reads_that_entry_as_caller_use_not_the_for_prefix() -> None:
    """The row's block id starts with the ``For`` prefix (``for3.7/...``): the submenu's ``caller``
    is the row's own use, so ``caller.use.params`` are its params (the Tray menu reads ``Id``)."""
    tray = TRAY_TDL.replace(
        "MenuItem { Text: {{ e.text }}, On_Click",
        "MenuItem { Text: {{ e.text }}, Id: {{ e.id }}, Submenu: Sub_Menu, On_Click",
    )
    sub = (
        "Popup { Name: Sub_Menu, Style { Background: $color.surface_raised }, "
        "Children { Menu { Children { MenuItem { Text: {{ caller.use.params.Id }} } } } } }"
    )
    with running(
        "Driver { }",
        driver=DRIVER,
        driver_py=DRIVER_PY,
        extra={"TrayMenu": tray},
        extra_py={"TrayMenu": TRAY_PY},
        popups=POPUPS + sub,
    ) as w:
        op = open_popup(w)
        for text, ident in (("Alpha", "a"), ("Beta", "b")):
            row = [n for n in op.view.nodes.values() if n.get("label") == text][0]
            op.window.simulate("click", node=row)
            assert op.sub is not None
            assert op.sub.caller.use.startswith("MenuItem@") and "for" in op.sub.caller.use
            assert op.sub.record["use"]["params"]["Id"] == ident  # type: ignore[index]
            labels = [n.get("label") for n in op.sub.view.nodes.values() if n.get("label")]
            assert ident in labels


def test_a_reload_that_replaces_the_plans_closes_the_popup_and_ends_its_entries() -> None:
    with go() as w:
        open_popup(w)
        assert len(item_uses(w)) == 2
        w.manager.popups.set_plans(list(w.manager.popups.plans.values()))  # what a reload does
        assert w.manager.popups.current is None
        assert item_uses(w) == []
        open_popup(w)  # and it opens again afterwards, with entries again
        assert len(item_uses(w)) == 2
