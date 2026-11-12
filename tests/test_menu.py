# ruff: noqa: E501
"""Menu and MenuItem (Standard Modules > Menu and MenuItem): a Button opens a Menu Popup with
``Show``, ``Data`` is ``caller.data``, an item runs its action and closes the menu, a submenu is a
Popup parented to its item's Popup (Events and Actions > Call, caller.data and Submenus)."""

from __future__ import annotations

from typing import Any

from tests.widgets_live import Widgets, running

CALL = 'On_Click { Action: Call, Target: "Driver.pressed" }'
POPUPS = f"""
Popup {{
    Name: File_Menu
    Attach: BOTTOM
    Style {{ Background: $color.surface_raised, Corner_Radius: 8 }}
    Children {{
        Menu {{ Children {{
            MenuItem {{ Text: "New", Shortcut_Text: "Ctrl+N", {CALL} }}
            MenuItem {{ Separator: true }}
            MenuItem {{ Text: "Share", Submenu: Share_Menu }}
            MenuItem {{ Text: "Archive", Submenu: Archive_Menu }}
            MenuItem {{ Text: "Off", Enabled: false, {CALL} }}
            MenuItem {{ Text: "Id", {CALL.replace("}", ", Id: {{ caller.data.Id }} }")} }}
        }} }}
    }}
}}
Popup {{
    Name: Share_Menu
    Style {{ Background: $color.surface_raised, Corner_Radius: 8 }}
    Children {{ Menu {{ Children {{ MenuItem {{ Text: "Mail", {CALL} }} MenuItem {{ Text: "More", Submenu: More_Menu }} }} }} }}
}}
Popup {{
    Name: Archive_Menu
    Style {{ Background: $color.surface_raised, Corner_Radius: 8 }}
    Children {{ Menu {{ Children {{ MenuItem {{ Text: "Zip", {CALL} }} }} }} }}
}}
Popup {{
    Name: More_Menu
    Style {{ Background: $color.surface_raised, Corner_Radius: 8 }}
    Children {{ Menu {{ Children {{ MenuItem {{ Text: "Deep", {CALL} }} }} }} }}
}}
"""
BAR = (
    'Button { Name: Opener, Text: "File", On_Click { Action: Show, Target: File_Menu, Data { Id: 7 } } } '
    'Button { Name: Other, Text: "Other", On_Click { Action: Toggle, Target: Archive_Menu } }'
)


def seen(w: Widgets) -> list[Any]:
    return w.host.loaded["Driver"].instance.seen  # type: ignore[no-any-return,attr-defined]


def op_nodes(op: Any) -> dict[str, Any]:
    return dict(op.view.nodes)


def item(op: Any, label: str) -> Any:
    found = [n for n in op.view.nodes.values() if n.get("label") == label]
    assert len(found) == 1, (label, [n.get("label") for n in op.view.nodes.values()])
    return found[0]


def open_menu(w: Widgets) -> Any:
    root = w.of_use("Button", "Root", 0)
    w.window.simulate("click", node=root)
    op = w.manager.popups.current
    assert op is not None, w.log()[-2000:]
    return op


def click(op: Any, node: Any) -> None:
    op.window.simulate("click", node=node)


def hover(w: Widgets, op: Any, node: Any, ms: float) -> None:
    op.window.simulate("pointer_enter", node=node)
    op.window.advance(ms)
    w.window.advance(ms)


def test_a_button_opens_a_menu_with_show_and_its_data_is_caller_data() -> None:
    with running(BAR, popups=POPUPS) as w:
        assert w.warnings() == [], w.warnings()
        op = open_menu(w)
        assert op.popup.name == "File_Menu" and op.caller.data == {"Id": 7}
        assert op.caller.block == ""  # the Button's root has an id; the popup knows its rect
        root = [n for n in op.view.nodes.values() if n.get("role") == "menu"]
        assert len(root) == 1
        assert item(op, "New").get("role") == "menuitem"
        click(op, item(op, "Id"))
        assert seen(w)[-1][2] == {"Id": 7}  # the item reads caller.data
        op.window.advance(50)
        assert w.manager.popups.current is None


def test_a_click_on_an_item_runs_its_action_and_closes_the_menu() -> None:
    with running(BAR, popups=POPUPS) as w:
        op = open_menu(w)
        click(op, item(op, "New"))
        w.advance(50)
        op.window.advance(50)
        assert len(seen(w)) == 1 and seen(w)[0][0] == "pressed"
        assert w.manager.popups.current is None


def test_a_disabled_item_and_a_separator_take_no_click_and_the_menu_stays() -> None:
    with running(BAR, popups=POPUPS) as w:
        op = open_menu(w)
        off = item(op, "Off")
        assert off.get("disabled") is True and off.get("opacity") == 0.5
        click(op, off)
        sep = [n for n in op.view.nodes.values() if n.get("role") == "separator"]
        assert len(sep) == 1
        click(op, sep[0])
        op.window.advance(50)
        assert seen(w) == [] and w.manager.popups.current is op


def test_show_again_from_the_same_button_does_not_stack_and_toggle_closes() -> None:
    with running(BAR, popups=POPUPS) as w:
        op = open_menu(w)
        w.window.simulate("click", node=w.of_use("Button", "Root", 1))  # Toggle another popup
        assert (
            w.manager.popups.current is not op
            and w.manager.popups.current.popup.name == "Archive_Menu"
        )
        assert op.closing  # one popup is open at a time
        w.window.simulate("click", node=w.of_use("Button", "Root", 1))
        assert w.manager.popups.current is None


def test_a_submenu_opens_beside_its_item_after_a_rest_and_closes_with_its_parent() -> None:
    with running(BAR, popups=POPUPS) as w:
        op = open_menu(w)
        share = item(op, "Share")
        assert share.get("expanded") is False
        hover(w, op, share, 100)
        assert op.sub is None  # not yet: 250 ms
        hover(w, op, share, 200)
        sub = op.sub
        assert sub is not None and sub.popup.name == "Share_Menu" and sub.parent_op is op
        assert share.get("expanded") is True
        assert sub.caller.use.startswith("MenuItem@")
        assert sub.caller.data == {"Id": 7}  # the data of the Menu that opened it (Q22)
        assert w.manager.popups.current is op  # the root stays the open popup
        assert [p.popup.name for p in w.manager.popups.chain()] == ["File_Menu", "Share_Menu"]
        w.manager.popups.close(op, "test")
        assert sub.closing and w.manager.popups.current is None


def test_a_click_opens_a_submenu_at_once_and_one_submenu_is_open_at_a_time() -> None:
    with running(BAR, popups=POPUPS) as w:
        op = open_menu(w)
        click(op, item(op, "Share"))
        first = op.sub
        assert (
            first is not None
            and first.popup.name == "Share_Menu"
            and w.manager.popups.current is op
        )
        click(op, item(op, "Archive"))
        assert first.closing and op.sub is not None and op.sub.popup.name == "Archive_Menu"
        assert (
            item(op, "Share").get("expanded") is False
            and item(op, "Archive").get("expanded") is True
        )


def test_the_pointer_resting_on_another_item_closes_the_open_submenu_after_300_ms() -> None:
    with running(BAR, popups=POPUPS) as w:
        op = open_menu(w)
        click(op, item(op, "Share"))
        assert op.sub is not None
        hover(w, op, item(op, "New"), 200)
        assert op.sub is not None  # not yet
        hover(w, op, item(op, "New"), 200)
        assert op.sub is None or op.sub.closing


def test_three_levels_and_a_click_deep_runs_the_action_and_closes_every_level() -> None:
    with running(BAR, popups=POPUPS) as w:
        op = open_menu(w)
        click(op, item(op, "Share"))
        mid = op.sub
        assert mid is not None
        click(mid, item(mid, "More"))
        deep = mid.sub
        assert deep is not None and deep.parent_op is mid
        assert len(w.manager.popups.chain()) == 3
        click(deep, item(deep, "Deep"))
        w.advance(50)
        deep.window.advance(50)
        assert len(seen(w)) == 1
        assert w.manager.popups.current is None and deep.closing and mid.closing and op.closing


def test_an_item_with_a_submenu_that_does_not_exist_is_reported() -> None:
    popups = POPUPS.replace("Submenu: Archive_Menu", "Submenu: Nowhere")
    with running(BAR, popups=popups) as w:
        op = open_menu(w)
        click(op, item(op, "Archive"))
        assert any("no Popup named Nowhere" in x for x in w.lines)
        assert op.sub is None


def test_data_belongs_on_show_and_toggle_only() -> None:
    import pytest

    for action in ('Call, Target: "Driver.pressed"', "Close"):
        bad = f"Button {{ Text: x, On_Click {{ Action: {action}, Data {{ Id: 1 }} }} }}"
        with pytest.raises(AssertionError, match="Data is the data a Popup gets"), running(bad):
            pass
    # a slot is allowed in Data and nowhere else on Show
    ok = (
        "Button { Text: x, On_Click { Action: Show, Target: File_Menu, Data { Id: {{ 1 + 1 }} } } }"
    )
    with running(ok, popups=POPUPS):
        pass
    bad = "Button { Text: x, On_Click { Action: Show, Target: File_Menu, Id: {{ 1 }} } }"
    with (
        pytest.raises(AssertionError, match="takes literal arguments"),
        running(bad, popups=POPUPS),
    ):
        pass


def test_show_of_a_name_that_is_neither_a_panel_nor_a_popup_is_reported_with_the_nearest_names() -> (
    None
):
    bar = "Button { Text: x, On_Click { Action: Show, Target: File_Mnu } }"
    with running(bar, popups=POPUPS) as w:
        assert any("Show: no Panel named File_Mnu" in x and "File_Menu" in x for x in w.lines)


def test_a_module_inside_a_popup_opens_a_submenu_with_ctx_popup() -> None:
    code = (
        "from tess_shell import Module, action\n"
        "class Driver(Module):\n"
        "    def __init__(self):\n        self.seen = []\n"
        "    @action\n    def opensub(self, event):\n"
        "        self.ctx.popup('Share_Menu', use=next(iter(self.ctx.uses)))\n"
    )
    popups = POPUPS.replace(
        'MenuItem {{ Text: "Share", Submenu: Share_Menu }}'.replace("{{", "{").replace("}}", "}"),
        'Driver { } MenuItem { Text: "Share", Submenu: Share_Menu }',
    )
    with running(
        BAR,
        popups=popups,
        driver_py=code,
        driver="Module { FlexBox { Name: Root, Height: 20, Children { FlexBox { Name: Row, On_Click: opensub, Width: 40, Height: 20 } } } }",
    ) as w:
        op = open_menu(w)
        row = [n for k, n in op.view.nodes.items() if k.endswith("/Row")][0]
        click(op, row)
        assert op.sub is not None and op.sub.popup.name == "Share_Menu" and op.sub.parent_op is op


def test_a_submenu_reads_the_data_of_the_menu_that_opened_it_and_cannot_change_it() -> None:
    popups = POPUPS.replace(
        'MenuItem { Text: "Mail", On_Click { Action: Call, Target: "Driver.pressed" } }',
        'MenuItem { Text: "Mail", On_Click { Action: Call, Target: "Driver.pressed", Id: {{ caller.data.Id }} } }',
    )
    assert popups != POPUPS
    with running(BAR, popups=popups) as w:
        assert w.warnings() == [], w.warnings()
        op = open_menu(w)
        click(op, item(op, "Share"))
        sub = op.sub
        assert sub is not None and sub.caller.data == {"Id": 7}
        click(sub, item(sub, "More"))  # a second level inherits it too
        assert sub.sub is not None and sub.sub.caller.data == {"Id": 7}
        click(sub, item(sub, "Mail"))
        assert seen(w)[-1][2] == {"Id": 7}  # a submenu item acts on the parent menu's item
        assert sub.record is not None
        sub.record["data"]["Id"] = 99  # what a slot reads is a copy: the parent's data is whole
        assert op.caller.data == {"Id": 7} and sub.caller.data == {"Id": 7}
