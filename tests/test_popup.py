"""The Popup surface and tooltips: keys in a shell file, placement, size, opening, toggling,
dismissal, ``Close``, hover tooltips and ``ctx.popup`` (Popup; Module Context > Calling a popup).

The windows are real tre windows without a compositor: a ``PopupWindow`` can be made and laid out
headless, and ``Window.simulate`` delivers pointer events; time is moved with ``advance``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import tess_dl
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Auto, Length
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.modules.host import ModuleHost
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.findings import Finding
from tess_shell.schema.look import read_theme
from tess_shell.schema.model import PopupDef, ShellDef
from tess_shell.schema.shell import read_module, read_shell
from tess_shell.surfaces.bar import Rect
from tess_shell.surfaces.manager import SurfaceManager
from tess_shell.surfaces.popup import ANCHORS, choose_attach, placement
from tests.shell_samples import HEADER, SVG
from tests.test_look import THEME
from tests.test_model_live import parse
from tests.test_panel import StubApp

# -- the keys --------------------------------------------------------------------------------

SHELL = (
    "Shell { Monitor { Name: Main, Index: 0, Children {\n"
    "  Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, Children { %s } }\n"
    "  %s\n"
    "} } }\n"
)


def read(body: str, modules: dict[str, Any] | None = None) -> tuple[ShellDef | None, list[Finding]]:
    result = tess_dl.parse(HEADER + body, path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    return read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: SVG, modules)


def popup_of(snippet: str, children: str = "") -> PopupDef:
    shell, findings = read(SHELL % (children, snippet))
    assert shell is not None, findings
    (popup,) = shell.monitors[0].popups
    return popup


def popup_errors(snippet: str, children: str = "") -> list[Finding]:
    shell, findings = read(SHELL % (children, snippet))
    assert shell is None, "the file was accepted"
    return [f for f in findings if f.severity == "error"]


def test_every_popup_key_is_typed() -> None:
    p = popup_of(
        "Popup { Name: P, Attach: TOP, Alignment: END, Gap: 4, Adjust: [FLIP_X, SLIDE_Y], "
        "Width: 120, Height: AUTO, Max_Width: 200, Max_Height: 250, Focus: false, "
        "Open_On_Enter: true, Enter_Delay: 300, Close_On_Exit: true, Exit_Delay: 50, "
        'Style { Fill: "#102030" }, Children { FlexBox { } } }'
    )
    assert (p.name, p.attach, p.alignment, p.gap) == ("P", "TOP", "END", 4)
    assert p.adjust == ("flip_x", "slide_y")
    assert p.width == Length(120) and p.height == Auto()
    assert (p.max_width, p.max_height, p.focus) == (200, 250, False)
    assert (p.open_on_enter, p.enter_delay, p.close_on_exit, p.exit_delay) == (True, 300, True, 50)
    assert "Fill" in p.style and len(p.children) == 1


def test_the_defaults_are_below_the_start_with_flip_y_and_slide_x_focused_and_auto_sized() -> None:
    p = popup_of("Popup { Name: P }")
    assert (p.attach, p.alignment, p.gap, p.adjust) == ("BOTTOM", "START", 0, ("flip_y", "slide_x"))
    assert (p.width, p.height, p.max_width, p.max_height) == (Auto(), Auto(), 300, 400)
    assert (p.focus, p.tooltip, p.open_on_enter, p.close_on_exit) == (True, False, False, False)
    assert (p.enter_delay, p.exit_delay) == (500, 200)


def test_tooltip_true_sets_no_focus_open_on_enter_and_close_on_exit_and_a_key_overrides() -> None:
    p = popup_of("Popup { Name: P, Tooltip: true }")
    assert (p.tooltip, p.focus, p.open_on_enter, p.close_on_exit) == (True, False, True, True)
    q = popup_of("Popup { Name: P, Tooltip: true, Focus: true, Exit_Delay: 900 }")
    assert (q.focus, q.exit_delay, q.open_on_enter) == (True, 900, True)


@pytest.mark.parametrize(
    ("snippet", "rule", "needle"),
    [
        ("Popup { Gap: 4 }", "missing-key", "Name"),
        ("Popup { Name: P, Attach_To: Top_Bar }", "not-built", "Attach_To"),
        ("Popup { Name: P, Attach: MIDDLE }", "bad-value", "BOTTOM"),
        ("Popup { Name: P, Adjust: [FLIP_Z] }", "bad-value", "FLIP_Y"),
        ("Popup { Name: P, Adjust: [FLIP_Y, FLIP_Y] }", "bad-value", "twice"),
        ("Popup { Name: P, Width: 50% }", "not-built", "PERCENT"),
        ("Popup { Name: P, Height: EXPAND }", "not-built", "EXPAND"),
        ("Popup { Name: P, Max_Width: 50% }", "not-built", "Max_Width"),
        ("Popup { Name: P, Animation { Type: FADE } }", "not-built", "Animation"),
        ("Popup { Name: P, Colour: 1 }", "unknown-key", "Popup"),
        ("Popup { Name: P, Enter_Dely: 1 }", "unknown-key", "Enter_Delay"),
    ],
)
def test_a_bad_popup_is_reported_at_its_key(snippet: str, rule: str, needle: str) -> None:
    found = popup_errors(snippet)
    assert any(f.rule == rule and needle in f.message + f.hint for f in found), found
    assert all(f.line > 0 for f in found)


def test_a_popup_name_is_unique_across_the_shell() -> None:
    found = popup_errors("Popup { Name: Top_Bar }")
    assert any(f.rule == "name-duplicate" for f in found)


BTN = 'Module { FlexBox { Name: Root, Width: 60, Height: 20, Style { Background: "#336699" } } }'
BTN_TIP = (
    "Module { FlexBox { Name: Root, Width: 60, Height: 20, Tooltip { Children { Text { "
    "Text: {{ note }}, Width: AUTO, Height: AUTO } } } } }"
)


def module(text: str, name: str = "Btn") -> Any:
    found, findings = read_module(parse(text, name, f"Modules/{name}_Module.tdl"), "x.tdl")
    assert found is not None, findings
    return found


def test_close_closes_the_popup_that_holds_it_and_takes_no_target() -> None:
    p = popup_of(
        "Popup { Name: P, Children { FlexBox { On_Click { Action: Close } } "
        "FlexBox { On_Click: Close } } }"
    )
    handlers = [c.handlers["On_Click"] for c in p.children]  # type: ignore[union-attr]
    assert all(h.action == "Close" and h.builtin and not h.args for h in handlers)
    found = popup_errors(
        "Popup { Name: P, Children { FlexBox { On_Click { Action: Close, Target: P } } } }"
    )
    assert any(f.rule == "bad-key" and "no Target" in f.message for f in found)


def test_close_outside_a_popup_is_an_error_that_says_where_it_belongs() -> None:
    found = popup_errors("", "FlexBox { On_Click: Close }")
    (f,) = found
    assert f.rule == "close-outside-popup" and "Children" in f.hint


def test_a_tooltip_is_a_popup_name_or_an_inline_popup_on_a_block_or_a_module_use() -> None:
    shell, findings = read(
        SHELL
        % (
            "FlexBox { Name: A, Tooltip: Tip } FlexBox { Tooltip { Alignment: CENTER, Gap: 2, "
            "Children { FlexBox { } } } } Btn { Name: B, Tooltip: Tip }",
            "Popup { Name: Tip, Tooltip: true }",
        ),
        {"Btn": module(BTN)},
    )
    assert shell is not None, findings
    a, inline, use = shell.monitors[0].surfaces[0].children  # type: ignore[union-attr]
    assert a.tooltip.name == "Tip" and a.tooltip.popup is None  # type: ignore[union-attr]
    popup = inline.tooltip.popup  # type: ignore[union-attr]
    assert (popup.name, popup.tooltip, popup.focus, popup.alignment, popup.gap) == (
        "",
        True,
        False,
        "CENTER",
        2,
    )
    assert use.tooltip.name == "Tip"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("children", "popup", "rule", "needle"),
    [
        (
            'Text { Text: "x", Tooltip: Tip }',
            "Popup { Name: Tip, Tooltip: true }",
            "event-not-raised",
            "FlexBox or Box",
        ),
        (
            "FlexBox { Tooltip: Nothing }",
            "Popup { Name: Tip, Tooltip: true }",
            "tooltip-unknown",
            "Tip",
        ),
        ("FlexBox { Tooltip: Tip }", "Popup { Name: Tip }", "tooltip-not-hover", "Tooltip: true"),
        ("FlexBox { Tooltip: Tip.tdl }", "", "not-built", "Tip.tdl"),
        ("FlexBox { Tooltip: 5 }", "", "bad-name", "Popup"),
    ],
)
def test_a_bad_tooltip_is_an_error_at_load(
    children: str, popup: str, rule: str, needle: str
) -> None:
    found = popup_errors(popup, children)
    assert any(f.rule == rule and needle in f.message + f.hint for f in found), found


# -- placement -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("attach", "alignment", "anchor", "gravity"),
    [
        ("BOTTOM", "START", "bottom_left", "bottom_right"),
        ("BOTTOM", "CENTER", "bottom", "bottom"),
        ("BOTTOM", "END", "bottom_right", "bottom_left"),
        ("TOP", "START", "top_left", "top_right"),
        ("TOP", "CENTER", "top", "top"),
        ("TOP", "END", "top_right", "top_left"),
        ("RIGHT", "START", "top_right", "bottom_right"),
        ("RIGHT", "CENTER", "right", "right"),
        ("RIGHT", "END", "bottom_right", "top_right"),
        ("LEFT", "START", "top_left", "bottom_left"),
        ("LEFT", "CENTER", "left", "left"),
        ("LEFT", "END", "bottom_left", "top_left"),
    ],
)
def test_attach_and_alignment_map_to_tres_anchor_and_gravity_as_the_spec_table_says(
    attach: str, alignment: str, anchor: str, gravity: str
) -> None:
    assert placement(attach, alignment, 0, (0, 0, 0, 0))[:2] == (anchor, gravity)
    assert ANCHORS[(attach, alignment)] == (anchor, gravity)


@pytest.mark.parametrize(
    ("attach", "alignment", "offset"),
    [
        ("BOTTOM", "START", (-11, 4 - 8)),  # body 4 below the anchor: the top margin is 8
        ("BOTTOM", "END", (13, 4 - 8)),
        ("BOTTOM", "CENTER", (1, 4 - 8)),  # centred: half the difference of the side margins
        ("TOP", "START", (-11, 14 - 4)),  # body 4 above the anchor: the bottom margin is 14
        ("RIGHT", "START", (4 - 11, -8)),
        ("LEFT", "END", (13 - 4, 14)),
    ],
)
def test_the_offset_is_the_gap_less_the_shadow_margin_so_the_body_meets_the_anchor(
    attach: str, alignment: str, offset: tuple[int, int]
) -> None:
    # a margin of 8 above, 13 right, 14 below and 11 left
    assert placement(attach, alignment, 4, (8, 13, 14, 11))[2] == offset


ANCHOR = Rect(100, 700, 60, 20)  # a module at the bottom of a 720 px high output
SIZE = (120, 80)


def test_a_popup_with_no_room_below_opens_above_and_one_with_room_opens_where_asked() -> None:
    out = (1000, 720)
    args = ((), SIZE, 4, (0, 0, 0, 0), out)
    assert choose_attach("BOTTOM", ("flip_y", "slide_x"), ANCHOR, *args[1:]) == "TOP"
    assert choose_attach("BOTTOM", ("flip_y",), Rect(100, 100, 60, 20), *args[1:]) == "BOTTOM"
    assert choose_attach("TOP", ("flip_y",), Rect(100, 10, 60, 20), *args[1:]) == "BOTTOM"
    assert choose_attach("RIGHT", ("flip_x",), Rect(950, 100, 40, 20), *args[1:]) == "LEFT"


def test_without_a_flip_in_adjust_or_with_no_room_either_way_the_side_is_kept() -> None:
    out = (1000, 720)
    assert choose_attach("BOTTOM", ("slide_x",), ANCHOR, SIZE, 4, (0, 0, 0, 0), out) == "BOTTOM"
    tall = (120, 800)  # taller than the output: neither side fits
    assert choose_attach("BOTTOM", ("flip_y",), ANCHOR, tall, 4, (0, 0, 0, 0), out) == "BOTTOM"


def test_the_shadow_margin_counts_in_whether_it_fits() -> None:
    out = (1000, 720)
    near = Rect(100, 600, 60, 20)  # 100 px to the bottom: an 80 px body fits, with 24 of margin not
    assert choose_attach("BOTTOM", ("flip_y",), near, SIZE, 0, (0, 0, 0, 0), out) == "BOTTOM"
    assert choose_attach("BOTTOM", ("flip_y",), near, (120, 104), 0, (0, 0, 24, 0), out) == "TOP"


# -- a running manager (real windows, no compositor) -------------------------------------------


@dataclass
class Rig:
    """A manager with a Bar holding module uses, the Popups of a Monitor and a list of log lines."""

    manager: SurfaceManager
    uses: list[str]
    lines: list[str]
    store: ValueStore

    @property
    def bar(self) -> Any:
        return next(s for s in self.manager.surfaces if s.name == "Top_Bar")

    @property
    def popups(self) -> Any:
        return self.manager.popups

    @property
    def use(self) -> str:
        return self.uses[0]

    def root_of(self, use: str | None = None) -> Any:
        key = use or self.use
        return self.bar.view.nodes[self.bar.expanded.roots.get(key) or f"{key}/Root"]

    def call(self, name: str = "Menu", data: Any = None, use: str | None = None) -> Any:
        self.popups.call("Btn", use or self.use, name, data)
        return self.popups.current

    def advance(self, ms: float) -> None:
        self.bar.window.advance(ms)

    def log(self) -> str:
        return "\n".join(self.lines)


def card(name: str = "Card") -> str:
    return (
        f"FlexBox {{ Name: {name}, Padding: 6, Children {{ "
        'Text { Text: "Hello world", Width: AUTO, Height: AUTO, Font_Size: 14 } } }'
    )


CARD = card()


def rig(
    popups: str,
    children: str = "Btn { Name: Btn_One }",
    btn: str = BTN,
    edge: str = "TOP",
) -> Iterator[Rig]:
    shell, findings = read(
        (SHELL % (children, popups)).replace("Edge: TOP", f"Edge: {edge}"),
        {"Btn": module(btn)},
    )
    assert shell is not None, findings
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    look = make_look(theme, [], Appearance())
    store = ValueStore()
    manager = SurfaceManager(StubApp(), {"Btn": module(btn)}, lambda k: k, store, look)  # type: ignore[arg-type]
    lines: list[str] = []
    _SINKS.append(logger.add(lambda message: lines.append(str(message).rstrip()), level="DEBUG"))
    uses = manager.plan(shell)
    manager.build()
    store.flush()
    r = Rig(manager, [u.key for u in uses], lines, store)
    r.bar.window.advance(16)
    yield r


_SINKS: list[int] = []


@pytest.fixture(autouse=True)
def _remove_log_sinks() -> Iterator[None]:
    yield
    while _SINKS:
        logger.remove(_SINKS.pop())


@pytest.fixture
def menu() -> Iterator[Rig]:
    yield from rig(f"Popup {{ Name: Menu, Gap: 4, Alignment: END, Children {{ {CARD} }} }}")


def rect_of(node: Any) -> tuple[int, int, int, int]:
    return tuple(  # type: ignore[return-value]
        round(float(node.get(k))) for k in ("layout_x", "layout_y", "layout_width", "layout_height")
    )


def test_a_call_opens_the_popup_beside_the_calling_use_as_its_keys_ask(menu: Rig) -> None:
    op = menu.call()
    assert op is not None
    w = op.window
    assert w.get("anchor_rect") == rect_of(menu.root_of())  # the use's first root block
    assert (w.get("anchor"), w.get("gravity")) == ("bottom_right", "bottom_left")  # BOTTOM, END
    assert w.get("offset") == (0, 4)  # the gap, no shadow margin
    assert w.get("grab") is True and tuple(w.get("constraint_adjustment")) == ("slide_x", "flip_y")
    assert "Popup Menu on HDMI-A-1 opened beside Btn" in menu.log()


def test_the_size_is_the_content_within_one_pixel_and_the_shadow_margin_is_added(
    menu: Rig,
) -> None:
    op = menu.call()
    op.window.advance(16)
    card = rect_of(op.view.nodes["Card"])
    assert tuple(op.window.get("size")) == (card[2], card[3])  # AUTO: what the content is
    assert card[2] > 12 and card[3] > 12  # padding and a line of text

    shadowed = list(
        rig(
            f"Popup {{ Name: Menu, Style {{ Elevation: 20% }}, Children {{ {CARD} }} }}",
        )
    )[0]
    big = shadowed.call()
    big.window.advance(16)
    inner = rect_of(big.view.nodes["Card"])
    top, right, bottom, left = (  # 20 % elevation: the transparent margin around the body
        int(big.body.get(f"margin_{side}")) for side in ("top", "right", "bottom", "left")
    )
    assert top > 0 and right > 0 and bottom > 0 and left > 0
    assert (inner[0], inner[1]) == (left, top)  # the content starts after the margin
    assert tuple(big.window.get("size")) == (inner[2] + left + right, inner[3] + top + bottom)
    assert abs(inner[2] - card[2]) <= 1 and abs(inner[3] - card[3]) <= 1  # the same body


def test_a_fixed_width_and_height_skip_the_measure_and_content_beyond_max_height_scrolls() -> None:
    tall = (
        "FlexBox { Name: Column, Flex: VERTICAL, Children { "
        + 'Rectangle { Width: 80, Height: 50, Fill: "#ff0000" } ' * 5
        + "} }"
    )
    (r,) = list(rig(f"Popup {{ Name: Menu, Max_Height: 120, Children {{ {tall} }} }}"))
    op = r.call()
    assert tuple(op.window.get("size"))[1] == 120  # clamped to Max_Height
    kinds = [c.get("kind") for c in op.body.children()]
    assert kinds == ["scroll_view"]  # and it scrolls

    (f,) = list(rig(f"Popup {{ Name: Menu, Width: 90, Height: 40, Children {{ {tall} }} }}"))
    fixed = f.call()
    assert tuple(fixed.window.get("size")) == (90, 40)
    assert [c.get("kind") for c in fixed.body.children()] != ["scroll_view"]


def test_calling_the_open_popup_again_closes_it(menu: Rig) -> None:
    first = menu.call()
    assert menu.call() is None  # the toggle
    assert first.closing and menu.popups.current is None
    assert "Popup Menu on HDMI-A-1 closing (toggled)" in menu.log()
    assert menu.call() is not None  # and once more it opens


def test_opening_another_popup_closes_the_open_one() -> None:
    two = (
        f"Popup {{ Name: Menu, Children {{ {CARD} }} }} "
        f"Popup {{ Name: Other, Children {{ {card('Second')} }} }}"
    )
    (r,) = list(rig(two))
    first = r.call("Menu")
    second = r.call("Other")
    assert first.closing and r.popups.current is second
    assert "Popup Menu on HDMI-A-1 closing (replaced)" in r.log()


def test_an_unknown_popup_is_an_error_naming_the_module_and_the_name_and_nothing_crashes(
    menu: Rig,
) -> None:
    assert menu.call("Mnu") is None
    errors = [x for x in menu.lines if "ERROR" in x]
    assert len(errors) == 1
    assert "Btn: ctx.popup('Mnu'): no Popup named Mnu" in errors[0]
    assert "did you mean Menu" in errors[0]


def test_a_use_on_no_open_surface_has_no_parent_and_the_call_says_so(menu: Rig) -> None:
    menu.popups.call("Btn", "Btn@nowhere", "Menu", None)
    assert menu.popups.current is None
    assert "ctx.popup('Menu'): the use Btn@nowhere is on no open surface" in menu.log()


def test_data_is_accepted_but_warned_about_because_nothing_reads_it_yet(menu: Rig) -> None:
    assert menu.call(data={"items": [1]}) is not None
    assert "data is accepted but not read yet" in menu.log()


def test_a_close_action_in_the_popup_closes_it_when_its_block_is_clicked() -> None:
    item = "FlexBox { Name: Item, Width: 50, Height: 20, On_Click: Close }"
    (r,) = list(rig(f"Popup {{ Name: Menu, Children {{ {item} }} }}"))
    op = r.call()
    op.window.simulate("click", op.view.nodes["Item"])
    assert r.popups.current is None and op.closing
    assert "closing (closed by its content)" in r.log()


def test_the_compositor_closing_a_popup_clears_it_and_a_denied_grab_is_reported(
    menu: Rig,
) -> None:
    op = menu.call()
    op.window.simulate("closed")
    assert menu.popups.current is None
    assert "Popup Menu on HDMI-A-1 closed" in menu.log()
    again = menu.call()
    assert again is not None and again is not op
    menu.popups._closed(again, "dismissed")  # tre's reason, a moment after it opened
    assert "dismissed" in menu.log() and "may have denied its grab" in menu.log()


def test_a_parent_that_was_not_open_is_logged_with_the_popup_and_the_caller(menu: Rig) -> None:
    op = menu.call()
    menu.popups._closed(op, "failed")
    assert "Popup Menu on HDMI-A-1: tre closed it with reason failed" in menu.log()
    assert "called by Btn Btn@" in menu.log()


def test_a_click_on_a_shell_surface_closes_a_focused_popup_and_is_not_a_call_to_reopen_it(
    menu: Rig,
) -> None:
    op = menu.call()
    root = menu.root_of()
    menu.bar.window.simulate("pointer_down", root)  # tre gives this click to the Bar, not the grab
    assert op.closing and menu.popups.current is None
    menu.bar.window.simulate("pointer_up", root)
    assert menu.call() is None  # the click that followed: it was the one that closed it
    assert menu.call() is not None  # the next call is a call


def test_a_click_on_a_surface_leaves_an_unfocused_popup_open() -> None:
    (r,) = list(rig(f"Popup {{ Name: Menu, Focus: false, Children {{ {CARD} }} }}"))
    op = r.call()
    r.bar.window.simulate("pointer_down", r.root_of())
    assert r.popups.current is op and not op.closing and op.window.get("grab") is False


def test_closing_the_parent_surface_closes_the_popup(menu: Rig) -> None:
    op = menu.call()
    menu.manager._close(menu.bar)
    assert op.closing and menu.popups.current is None
    assert "closing (its parent closed)" in menu.log()


# -- tooltips --------------------------------------------------------------------------------

TIP = (
    "Popup { Name: Tip, Tooltip: true, Enter_Delay: 100, Exit_Delay: 50, Children { "
    + CARD
    + " } }"
)
HOT = "FlexBox { Name: Hot, Width: 40, Height: 20, Tooltip: Tip }"


def hover(r: Rig, entering: bool = True, name: str = "Hot") -> None:
    if entering:
        r.bar.window.simulate("pointer_enter", r.bar.view.nodes[name])
    else:
        r.bar.window.simulate("pointer_leave")


def test_a_tooltip_opens_after_enter_delay_unfocused_and_closes_after_exit_delay() -> None:
    (r,) = list(rig(TIP, HOT))
    hover(r)
    r.advance(99)
    assert r.popups.current is None  # not yet: the pointer must stay for Enter_Delay
    r.advance(2)
    op = r.popups.current
    assert op is not None and op.window.get("grab") is False  # no focus, no keyboard
    assert op.window.get("anchor_rect") == rect_of(r.bar.view.nodes["Hot"])
    hover(r, False)
    r.advance(49)
    assert r.popups.current is op  # it waits Exit_Delay so the pointer can cross the gap
    r.advance(2)
    assert r.popups.current is None and op.closing
    assert "closing (the pointer left)" in r.log()


def test_leaving_before_enter_delay_cancels_the_tooltip() -> None:
    (r,) = list(rig(TIP, HOT))
    hover(r)
    r.advance(60)
    hover(r, False)
    r.advance(500)
    assert r.popups.current is None


def test_the_pointer_crossing_into_the_tooltip_keeps_it_open_and_leaving_it_closes_it() -> None:
    (r,) = list(rig(TIP, HOT))
    hover(r)
    r.advance(101)
    op = r.popups.current
    hover(r, False)
    op.window.simulate("pointer_enter", op.body)  # into the popup within Exit_Delay
    r.advance(500)
    assert r.popups.current is op
    op.window.simulate("pointer_leave")
    r.advance(51)
    assert r.popups.current is None


def test_a_tooltip_never_opens_while_a_focused_popup_is_open() -> None:
    both = f"Popup {{ Name: Menu, Children {{ {card('Second')} }} }} {TIP}"
    (r,) = list(rig(both, f"Btn {{ Name: Btn_One }} {HOT}"))
    menu = r.call("Menu")
    hover(r)
    r.advance(500)
    assert r.popups.current is menu and not menu.closing


def test_a_focused_popup_replaces_an_open_tooltip() -> None:
    both = f"Popup {{ Name: Menu, Children {{ {card('Second')} }} }} {TIP}"
    (r,) = list(rig(both, f"Btn {{ Name: Btn_One }} {HOT}"))
    hover(r)
    r.advance(101)
    tip = r.popups.current
    menu = r.call("Menu")
    assert tip.closing and r.popups.current is menu


def test_an_inline_tooltip_on_a_module_use_shows_that_uses_values_beside_its_root_block() -> None:
    (r,) = list(rig("", btn=BTN_TIP))
    r.store.send("Btn", r.use, "note", "Friday")
    r.store.flush()
    r.bar.window.simulate("pointer_enter", r.root_of())
    r.advance(499)
    assert r.popups.current is None  # the default Enter_Delay is 500 ms
    r.advance(2)
    op = r.popups.current
    assert op is not None and op.window.get("grab") is False
    (text,) = [n for i, n in op.view.nodes.items() if n.get("kind") == "text"] or [None]
    assert text is not None and text.get("text") == "Friday"
    assert op.window.get("anchor_rect") == rect_of(r.root_of())
    # a later value reaches the open tooltip, which keeps its size
    r.store.send("Btn", r.use, "note", "Saturday")
    r.manager.on_change(r.store.flush())  # the store's callback, as the app wires it
    assert op is r.popups.current and text.get("text") == "Saturday"


def test_a_tooltip_on_a_module_use_in_the_shell_file_names_a_popup_or_writes_one() -> None:
    (r,) = list(rig(TIP, "Btn { Name: Btn_One, Tooltip: Tip }"))
    r.bar.window.simulate("pointer_enter", r.root_of())
    r.advance(101)
    assert r.popups.current is not None
    assert r.popups.current.plan.popup.name == "Tip"


# -- ctx.popup: the module's way to open one -----------------------------------------------------


class Port:
    """What the shell offers a module for Popups, recording the calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, str, Any]] = []
        self.closed: list[str | None] = []

    def call(self, module: str, use: str | None, name: str, data: Any) -> None:
        self.calls.append((module, use, name, data))

    def close_named(self, name: str | None = None) -> None:
        self.closed.append(name)


CALLER_PY = """
from tess_shell import Module, action


class Menu_Button(Module):
    @action
    def open_menu(self, event):
        self.ctx.popup("Menu", {"n": 1})

    @action
    def open_for(self, event):
        self.ctx.popup("Other", use=self.ctx.uses[event.args["which"]])

    @action
    def shut(self, event):
        self.ctx.close_popup("Menu")

    def stray(self):
        self.ctx.popup("Menu")  # not from an action: no use to open beside
"""


def test_ctx_popup_opens_beside_the_use_whose_action_runs_and_close_popup_closes(
    tmp_path: Path,
) -> None:
    from tess_shell.binder.model import NO_ORIGIN, Handler

    layout = (
        "---\nTDL: 0.1\nName: Menu_Button\n---\n"
        "Module { FlexBox { Width: 10, Height: 10, On_Click: open_menu } }\n"
    )
    result = tess_dl.parse(layout, path="Modules/Menu_Button_Module.tdl")
    assert result.document is not None
    definition, findings = read_module(result.document, "Modules/Menu_Button_Module.tdl")
    assert definition is not None, findings
    py = tmp_path / "Menu_Button_Module.py"
    py.write_text(CALLER_PY)
    store = ValueStore()
    host = ModuleHost(store, TimeSource(), tmp_path)
    uses = [
        Use(f"Menu_Button@u{i}", "Menu_Button", f"S.M.B.Btn_{i}", {}, "Main", NO_ORIGIN)
        for i in (1, 2)
    ]
    loaded, problems = host.load(definition, py, "uid", uses)
    assert loaded is not None, problems
    host.start(loaded)
    port = Port()
    host.popups = port  # the surfaces, once they exist

    host.dispatch(Handler("open_menu", use="Menu_Button@u2"), "On_Click", object())
    assert port.calls == [("Menu_Button", "Menu_Button@u2", "Menu", {"n": 1})]  # the caller's use
    assert loaded.ctx.caller is None  # only while the action runs

    host.dispatch(Handler("shut", use="Menu_Button@u1"), "On_Click", object())
    assert port.closed == ["Menu"]

    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="ERROR")
    try:
        loaded.instance.stray()  # type: ignore[attr-defined]
    finally:
        logger.remove(sink)
    assert len(port.calls) == 1  # nothing was opened
    assert "ctx.popup('Menu') needs the use that calls it" in "".join(lines)


def test_ctx_popup_with_an_explicit_use_works_outside_an_action(tmp_path: Path) -> None:
    from tess_shell.modules.context import ModuleContext, UseRecord

    port = Port()
    record = UseRecord("M@u1", "S.M.B.M_1", "u1", "Main", {})
    ctx = ModuleContext(
        "M", "uid", {}, {record.key: record}, lambda *_: None, TimeSource(), lambda: port
    )
    ctx.popup("Menu", use=record)
    ctx.popup("Menu", use="M@u1")
    assert port.calls == [("M", "M@u1", "Menu", None)] * 2


def test_moving_from_one_block_with_a_tooltip_to_another_opens_the_second_after_its_delay() -> None:
    two = f"{HOT} FlexBox {{ Name: Cold, Width: 40, Height: 20, Tooltip: Tip }}"
    r = next(rig(TIP, two))
    hover(r)
    r.advance(101)
    first = r.popups.current
    hover(r, False)
    hover(r, name="Cold")  # before Exit_Delay ends
    assert first.closing and r.popups.current is None  # the first goes at once
    r.advance(101)
    second = r.popups.current
    assert second is not None and second.block == "Cold"
    assert second.window.get("anchor_rect") == rect_of(r.bar.view.nodes["Cold"])


def test_a_reload_closes_the_open_popup_and_the_new_definition_is_the_one_that_opens() -> None:
    r = next(rig(f"Popup {{ Name: Menu, Gap: 4, Children {{ {CARD} }} }}"))
    assert r.call() is not None
    shell, _ = read(
        SHELL
        % (
            "Btn { Name: Btn_One }",
            f"Popup {{ Name: Menu, Gap: 9, Children {{ {CARD} }} }}",
        ),
        {"Btn": module(BTN)},
    )
    assert shell is not None
    checked = r.manager.check(shell, {"Btn": module(BTN)})
    assert checked is not None
    planned, uses = checked
    r.manager.apply(planned, {"Btn": module(BTN)}, uses)
    assert r.popups.current is None
    assert "closing (reloaded)" in r.log()
    op = r.call()
    assert op is not None and op.window.get("offset") == (0, 9)  # the Gap that was written
