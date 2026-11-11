"""The M4a widgets gallery (``tests/kwin/prepare_m4a_gallery.py``) run headless: every tile shows
the states its stylesheet asks, the Meter's parts take their rules, the Pad calls its module with
arguments and its Popup reads ``caller.data``. The pointer is simulated; the gallery on a real
compositor is ``tests/test_gallery_live.py`` and the maintainer's KWin checklist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.kwin import prepare_m4a_gallery as g
from tests.test_call import Live, running
from tests.test_call import _remove_log_sinks as _remove_call_sinks  # noqa: F401

SHIPPED = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped"
THEME = (SHIPPED / "Themes" / "Default_Theme.tdl").read_text()

SURFACE = (18, 23, 29, 255)  # #12171D
RAISED = (27, 34, 43, 255)  # #1B222B
PRIMARY = (91, 151, 201, 255)  # #5B97C9
ACCENT = (70, 130, 180, 255)  # #4682B4
WARNING = (230, 187, 106, 255)  # #E6BB6A
MUTED = (159, 174, 191, 255)  # #9FAEBF
LIGHT = (228, 234, 241, 255)  # #E4EAF1


def body(tdl: str) -> str:
    """A module file without its metadata block (``running`` adds one)."""
    return tdl.split("---\n", 2)[2]


@pytest.fixture
def gallery(tmp_path: Path) -> Live:
    r = running(
        tmp_path,
        children=g.COLUMN,
        popups=g.POPUP,
        layouts={"Meter": body(g.METER_TDL), "Pad": body(g.PAD_TDL)},
        code={"Meter": g.METER_PY, "Pad": g.PAD_PY},
        look=(THEME, g.STYLESHEET),
    )
    assert r.problems == []
    return r


def node(r: Live, suffix: str) -> Any:
    (found,) = [n for k, n in r.bar.view.nodes.items() if k.split("/")[-1] == suffix]
    return found


def meter(r: Live, which: str, part: str) -> Any:
    (found,) = [
        n for k, n in r.bar.view.nodes.items() if f"Meter_{which}/" in k and k.endswith(f"/{part}")
    ]
    return found


def enter(r: Live, n: Any) -> None:
    r.bar.window.simulate("pointer_enter", node=n)


def test_the_gallery_loads_with_no_error_or_warning(gallery: Live) -> None:
    bad = [x for x in gallery.lines if "| ERROR " in x or "| WARNING " in x]
    assert bad == []


@pytest.mark.parametrize("kind", ["Box", "FlexBox", "Rectangle"])
def test_a_tile_shows_normal_hovered_pressed_and_disabled(gallery: Live, kind: str) -> None:
    w = gallery.bar.window
    tile = node(gallery, f"{kind}_Hover")
    assert tile.get("fill") == RAISED and tile.get("stroke_width") == 1
    enter(gallery, tile)
    assert tile.get("fill") == ACCENT and tile.get("stroke_color") == LIGHT  # :hovered
    w.simulate("pointer_down", node=tile)
    assert tile.get("fill") == ACCENT and tile.get("stroke_width") == 3  # :pressed over :hovered
    assert tile.get("stroke_color") == WARNING
    w.simulate("pointer_up", node=tile)
    w.simulate("pointer_leave")
    assert tile.get("fill") == RAISED and tile.get("stroke_width") == 1  # exactly as before
    off = node(gallery, f"{kind}_Disabled")
    assert off.get("disabled") is True and off.get("fill") == SURFACE and off.get("opacity") == 0.55
    enter(gallery, off)
    w.simulate("pointer_down", node=off)
    assert off.get("fill") == SURFACE  # no hover, no press while disabled
    assert node(gallery, f"{kind}_Normal").get("disabled") is False


def test_the_svg_icon_takes_its_colour_from_the_states(gallery: Live) -> None:
    icon, off = node(gallery, "SVG_Hover"), node(gallery, "SVG_Disabled")
    base = icon.get("svg_color")
    enter(gallery, icon)
    assert icon.get("svg_color") == PRIMARY != base
    assert off.get("disabled") is True and off.get("svg_color") == MUTED
    assert off.get("opacity") == 0.55


def test_a_disabled_text_is_faint_and_a_normal_one_is_not(gallery: Live) -> None:
    on, off = node(gallery, "Text_Normal"), node(gallery, "Text_Disabled")
    assert off.get("disabled") is True and off.get("fill") == MUTED and off.get("opacity") == 0.55
    assert on.get("disabled") is False and on.get("opacity") == 1.0


def test_the_meters_parts_take_their_rules_and_a_disabled_meter_looks_disabled(
    gallery: Live,
) -> None:
    fill, track = meter(gallery, "On", "Fill"), meter(gallery, "On", "Track")
    assert fill.get("fill") == (140, 203, 154, 255) and track.get("fill") == (85, 101, 122, 255)
    assert fill.get("corner_radius") == (5, 5, 5, 5) or fill.get("corner_radius") == 5
    enter(gallery, fill)
    assert fill.get("fill") == PRIMARY and track.get("fill") == (85, 101, 122, 255)  # ::fill only
    gallery.bar.window.simulate("pointer_down", node=fill)
    assert fill.get("fill") == WARNING and fill.get("stroke_width") == 2
    gallery.bar.window.simulate("pointer_up", node=fill)
    gallery.bar.window.simulate("pointer_leave")
    off_fill, off_track = meter(gallery, "Off", "Fill"), meter(gallery, "Off", "Track")
    assert off_fill.get("fill") == MUTED and off_fill.get("opacity") == 0.4
    assert off_track.get("opacity") == 0.4
    enter(gallery, off_fill)
    assert off_fill.get("fill") == MUTED  # the module is disabled: no hover on its parts
    assert fill.get("opacity") == 1.0  # the other Meter is untouched


def last_text(r: Live) -> str:
    r.manager.on_change(r.store.flush())
    return str(node(r, "Last").get("text"))


def test_the_call_button_runs_the_pad_action_with_its_arguments(gallery: Live) -> None:
    assert last_text(gallery) == "no call yet"
    gallery.bar.window.simulate("click", node=node(gallery, "Call_Button"))
    expected = "received: Amount=5, Kind=click, Label=from the Pad"
    assert last_text(gallery) == expected
    assert any(
        "Pad.log_press received: Amount=5, Kind=click, Label=from the Pad" in x
        for x in gallery.lines
    )


def test_the_popup_reads_caller_data_and_its_button_calls_with_it(gallery: Live) -> None:
    gallery.bar.window.simulate("click", node=node(gallery, "Menu_Button"))
    popups = gallery.manager.popups
    op = popups.current
    assert op is not None and op.record["data"] == {"Title": "Hello from the Pad", "Count": 3}
    assert op.view.nodes["Menu_Title"].get("text") == "Hello from the Pad"
    assert op.view.nodes["Menu_Source"].get("text").startswith("called by Pad at ")
    assert op.view.nodes["Menu_Source"].get("text").endswith("Pad_One")
    op.window.simulate("click", node=op.view.nodes["Menu_Call"])
    assert last_text(gallery) == "received: From=popup, Id=3"
    assert popups.current is op  # the popup stays open
    op.window.simulate("click", node=op.view.nodes["Menu_Close"])
    assert popups.current is None
    assert [x for x in gallery.lines if "| ERROR " in x] == []
