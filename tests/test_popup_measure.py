"""The cheap measure of a menu (``surfaces.popup_measure``): for the Tray menu and the Audio outputs
menu it gives EXACTLY the numbers of the full pass (the same width and height, no tolerance: tre
lays out whole pixels, and the cheap measure takes its text widths and fixed parts from tre), and
any content that is not a uniform column of rows takes the full pass. Headless: a real binder,
module host and Popups; the content of each case is measured both ways on the same meter window."""

from __future__ import annotations

from typing import Any

import pytest

from tess_shell.surfaces import popup as P
from tess_shell.surfaces.popup import Measured
from tests.tray_rig import POPUPS
from tests.widgets_live import Widgets, running

DRIVER = (
    "Module { FlexBox { Name: Root, Width: 40, Height: 20, On_Click: open_it, "
    "On_Secondary_Click: open_audio } }"
)
DRIVER_PY = """
from tess_shell import Module, action

class Driver(Module):
    data = {}

    @action
    def open_it(self, event):
        self.ctx.popup('Tray_Menu', data=Driver.data)

    @action
    def open_audio(self, event):
        self.ctx.popup('Audio_Outputs', data=Driver.data)
"""
AUDIO_POPUP = (
    "Popup { Name: Audio_Outputs, Attach: BOTTOM, "
    "Style { Background: $color.surface_raised, Corner_Radius: 8 }, "
    "Children { Audio_Outputs { } } }"
)
CHECK = "mdi:check"


def entry(ident: int, text: str = "", **more: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": str(ident),
        "text": text or f"Entry {ident}",
        "enabled": True,
        "icon": "",
        "shortcut": "",
        "separator": False,
        "submenu": "",
        "label": text or f"Entry {ident}",
    }
    base.update(more)
    return base


def tray(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"service": "s", "path": "/p", "title": "Item", "menus": {"0": entries}}


def outputs(count: int, **more: Any) -> dict[str, Any]:
    return {
        "outputs": [
            {
                "id": f"o{i}",
                "name": f"Output number {i}",
                "icon": "speaker",
                "current": i == 1,
                **more,
            }
            for i in range(count)
        ]
    }


class Spy:
    """What ``Popups.open`` handed to ``measure`` for one opening."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.sizes: list[Measured] = []


def both(w: Widgets, click: str, data: dict[str, Any]) -> tuple[Measured, Measured]:
    """Open the Popup with ``data`` and measure what it measured, both ways."""
    w.host.loaded["Driver"].instance.__class__.data = data
    seen: list[tuple[Any, ...]] = []
    real = P.measure

    def spy(meter: Any, nodes: Any, popup: Any, *rest: Any, **kw: Any) -> Measured:
        seen.append((meter, nodes, popup, rest))
        return real(meter, nodes, popup, *rest, **kw)

    P.measure = spy
    try:
        w.window.simulate(click, node=w.of_use("Driver", "Root"))
    finally:
        P.measure = real
    (meter, nodes, popup, rest), *_ = seen
    cheap = real(meter, nodes, popup, *rest, estimate=True)
    full = real(meter, nodes, popup, *rest, estimate=False)
    w.manager.popups.close_current("test")
    return cheap, full


def run(click: str, data: dict[str, Any], popups: str = POPUPS) -> tuple[Measured, Measured]:
    with running("Driver { }", driver=DRIVER, driver_py=DRIVER_PY, popups=popups) as w:
        return both(w, click, data)


def same(cheap: Measured, full: Measured, *, estimated: bool = True) -> None:
    assert (cheap.width, cheap.height, cheap.scrolls) == (full.width, full.height, full.scrolls)
    assert cheap.estimated is estimated and full.estimated is False


SHAPES: dict[str, list[dict[str, Any]]] = {
    "one": [entry(1)],
    "five": [entry(i) for i in range(1, 6)],
    "a hundred": [entry(i) for i in range(1, 101)],
    "separators": [entry(1), entry(2, separator=True, text=""), entry(3), entry(4, separator=True)],
    "a long label": [entry(1, "W" * 18), entry(2, "short")],
    "arrows": [entry(1, "More", submenu="Tray_Menu_2"), entry(2, "Less")],
    "icons": [
        entry(1, "Check", icon=CHECK),
        entry(2, "Plain"),
        entry(3, "Dot", icon="mdi:radiobox-marked"),
    ],
    "disabled": [entry(1, "Off", enabled=False), entry(2, "On")],
    "shortcuts": [
        entry(1, "Quit", shortcut="Ctrl+Q"),
        entry(2, "Open", shortcut="Ctrl+Shift+Alt+O"),
    ],
    "everything": [
        entry(1, "Open Window", icon=CHECK, shortcut="Ctrl+O"),
        entry(2, separator=True, text=""),
        entry(3, "Disabled one", enabled=False),
        entry(4, "More things here", submenu="Tray_Menu_2", icon="mdi:radiobox-blank"),
        entry(5, "i"),
        entry(6, "Ünïcödé — wide: 日本語"),
        entry(7, "Quit", shortcut="Ctrl+Q"),
    ],
    "empty words": [entry(1, ""), entry(2, " ")],
}


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_the_tray_menu_measures_the_same_cheaply_and_in_full(shape: str) -> None:
    cheap, full = run("click", tray(SHAPES[shape]))
    same(cheap, full)


def test_a_menu_shorter_than_its_min_width_and_one_wider_are_both_exact() -> None:
    short, full = run("click", tray([entry(1, "a")]))
    assert short.width == full.width == 160.0  # the Menu's Min_Width
    wide, full_wide = run("click", tray([entry(1, "W" * 10, shortcut="Ctrl+Shift+Alt+O")]))
    assert wide.width == full_wide.width > 160.0
    same(wide, full_wide)


def test_the_height_is_the_rows_and_the_padding_and_a_separator_is_its_own_height() -> None:
    cheap, full = run("click", tray([entry(1), entry(2, separator=True, text=""), entry(3)]))
    assert cheap.height == full.height == 8 + 28 + 9 + 28  # padding 4 + 4, two items, a rule


def test_a_menu_taller_than_the_popup_is_clamped_and_scrolls_the_same() -> None:
    popups = POPUPS.replace("Max_Height: 600", "Max_Height: 40%")
    cheap, full = run("click", tray(SHAPES["a hundred"]), popups)
    same(cheap, full)
    assert cheap.scrolls and cheap.height < 100 * 28
    px = POPUPS.replace("Max_Height: 600", "Max_Height: 200")
    cheap, full = run("click", tray(SHAPES["a hundred"]), px)
    same(cheap, full)
    assert cheap.height == 200


def test_a_label_wider_than_the_popup_takes_the_full_pass() -> None:
    cheap, full = run("click", tray([entry(1, "W" * 120)]))
    same(cheap, full, estimated=False)  # it wraps: the cheap measure does not guess


@pytest.mark.parametrize("count", [1, 3, 40])
def test_the_audio_outputs_menu_measures_the_same_cheaply_and_in_full(count: int) -> None:
    cheap, full = run("secondary_click", outputs(count), AUDIO_POPUP)
    same(cheap, full)


def test_the_audio_outputs_menu_with_the_current_dot_is_exact() -> None:
    data = {
        "outputs": [
            {"id": "a", "name": "Speakers", "icon": "speaker", "current": True},
            {
                "id": "b",
                "name": "Headphones with a long name indeed",
                "icon": "headphones",
                "current": False,
            },
            {"id": "c", "name": "HDMI", "icon": "hdmi-port", "current": False},
        ]
    }
    cheap, full = run("secondary_click", data, AUDIO_POPUP)
    same(cheap, full)


# -- what is not a menu --------------------------------------------------------------------------

HAND = (
    "Popup { Name: Tray_Menu, Style { Background: $color.surface_raised }, "
    'Children { FlexBox { Flex: VERTICAL, Padding: 6, Children { Label { Text: "Hello there" } '
    'Label { Text: "Second line of the Popup" } } } } }'
)
MENU_OF_OTHERS = (
    "Popup { Name: Tray_Menu, Style { Background: $color.surface_raised }, "
    "Children { Menu { Children { Label { Text: A } MenuItem { Text: B } } } } }"
)
SPACED = (
    "Popup { Name: Tray_Menu, Style { Background: $color.surface_raised }, "
    "Children { FlexBox { Flex: VERTICAL, Spacing: 5, Children { Menu { Children { "
    "MenuItem { Text: A } MenuItem { Text: B } } } } } } }"
)
BORDERED = POPUPS.replace(
    "Style { Background: $color.surface_raised, Corner_Radius: 8 }",
    "Style { Background: $color.surface_raised, Border_Width: 2, Border_Color: $color.primary }",
)
FIXED = POPUPS.replace("Max_Height: 600", "Width: 200, Max_Height: 600")


@pytest.mark.parametrize(
    "popups", [HAND, MENU_OF_OTHERS, SPACED, BORDERED, FIXED], ids=lambda p: p[:0] or "case"
)
def test_content_that_is_not_a_plain_menu_takes_the_full_pass_and_gets_the_same_numbers(
    popups: str,
) -> None:
    cheap, full = run("click", tray([entry(1), entry(2, "Second")]), popups)
    same(cheap, full, estimated=False)


def test_the_hand_written_popup_is_not_measured_by_the_cheap_path_at_all() -> None:
    from tess_shell.surfaces import popup_measure

    with running("Driver { }", driver=DRIVER, driver_py=DRIVER_PY, popups=HAND) as w:
        calls: list[Any] = []
        real = popup_measure.measure_menu

        def count(*a: Any, **k: Any) -> Any:
            result = real(*a, **k)
            calls.append(result)
            return result

        P.measure_menu = count
        try:
            w.window.simulate("click", node=w.of_use("Driver", "Root"))
        finally:
            P.measure_menu = real
        assert calls == [None]  # asked, and refused: no row was built for it
        assert w.manager.popups.current is not None


def test_a_hundred_rows_of_one_kind_build_one_row_not_a_hundred() -> None:
    """The point of the cheap measure: the rows are sorted into kinds and one of each is built."""
    from tess_shell.surfaces import popup_measure

    built: list[str] = []
    real = popup_measure._build_kind

    def count(meter: Any, row: Any) -> Any:
        built.append(row.name)
        return real(meter, row)

    popup_measure._build_kind = count
    try:
        cheap, full = run("click", tray(SHAPES["a hundred"]))
    finally:
        popup_measure._build_kind = real
    same(cheap, full)
    assert len(built) == 2  # two runs of the measure here: the Popup's own, and the test's
    kinds = [entry(i, shortcut="Ctrl+X" if i % 2 else "") for i in range(1, 41)]
    built.clear()
    popup_measure._build_kind = count
    try:
        run("click", tray(kinds))
    finally:
        popup_measure._build_kind = real
    assert len(built) == 4  # two kinds (with and without a shortcut), measured twice
