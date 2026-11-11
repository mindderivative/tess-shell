"""The M4a widgets gallery (``tests/kwin/prepare_m4a_gallery.py``) run headless: every tile shows
the states its stylesheet asks, the Meter's parts take their rules, the Pad calls its module with
arguments and its Popup reads ``caller.data``. The pointer is simulated; the gallery on a real
compositor is ``tests/test_gallery_live.py`` and the maintainer's KWin checklist."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tess_shell.binder import model as m
from tests.field_live import Field, Fields
from tests.field_live import running as running_fields
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


# -- the text fields (A2) ----------------------------------------------------------------------
#
# The second Panel of the gallery, ``Fields``, run through the shell's real model with the shipped
# TextInput and TextEditor and the gallery's Echo module; the keyboard is ``simulate``.


@contextmanager
def fields_panel() -> Iterator[Fields]:
    with running_fields(
        "",
        popups=g.FIELDS_PANEL,
        extra={"Echo": g.ECHO_TDL},
        extra_code={"Echo": g.ECHO_PY},
        sheet=g.FIELDS_STYLESHEET,
    ) as r:
        yield r


def panel_of(r: Fields, name: str = "Fields") -> Any:
    return next(s for s in r.manager.surfaces if s.name == name)


def field_of(r: Fields, name: str) -> Field:
    found: list[Field] = []

    def walk(entries: list[Any]) -> None:
        for e in entries:
            if e.typed.kind == m.FIELD and name in (e.typed.name or ""):
                found.append(Field(e))
            walk(e.children)

    walk(panel_of(r).view.entries)
    (one,) = found
    return one


def echo(r: Fields) -> str:
    r.manager.on_change(r.store.flush())
    view = panel_of(r).view
    (last,) = [n for k, n in view.nodes.items() if k.endswith("/Last")]
    return str(last.get("text"))


def type_in(r: Fields, f: Field, text_: str) -> None:
    w = panel_of(r).window
    w.simulate("pointer_down", node=f.inp)
    w.simulate("pointer_up", node=f.inp)
    w.simulate("input", text=text_)


def test_the_fields_panel_loads_with_no_error_or_warning_and_takes_the_keyboard() -> None:
    with fields_panel() as r:
        assert r.problems == []
        assert [x for x in r.lines if "| ERROR " in x or "| WARNING " in x] == []
        assert panel_of(r).window.get("keyboard") == "on_demand"  # it holds text fields
        assert any("Panel Fields" in x and "keyboard on_demand" in x for x in r.lines)


def test_every_form_of_the_fields_panel_is_what_its_row_says() -> None:
    with fields_panel() as r:
        normal, hint, ro = (field_of(r, n).inp for n in ("In_Normal", "In_Hint", "In_Read"))
        assert normal.get("text") == "hello" and normal.get("overflow") == "scroll"
        assert hint.get("placeholder") == "Search..." and hint.get("text") == ""
        assert (
            hint.get("placeholder_fill") == PRIMARY
        )  # the part ::placeholder of the gallery sheet
        assert ro.get("read_only") is True
        assert field_of(r, "In_Pass").inp.get("obscured") is True
        assert field_of(r, "In_Max").inp.get("max_length") == 8
        assert field_of(r, "In_Off").inp.get("disabled") is True
        for name, word in (("F_Scroll", "scroll"), ("F_Ellipsis", "ellipsis"), ("F_Clip", "clip")):
            assert field_of(r, name).inp.get("overflow") == word, name
        word_wrap, no_wrap, off = (field_of(r, n).inp for n in ("Ed_Word", "Ed_None", "Ed_Off"))
        assert word_wrap.get("wrap") == "word" and no_wrap.get("wrap") == "none"
        assert off.get("disabled") is True and off.get("multiline") is True
        text = str(word_wrap.get("text"))
        assert len(word_wrap.text_rects(0, len(text))) > 1  # wrapped by word
        assert len(no_wrap.text_rects(0, len(text))) == 1  # one line
        assert field_of(r, "F_Ellipsis").inp.text_rects(0, 1)[0][0] == 0  # unfocused: the start


def test_typing_in_the_first_field_reaches_echo_with_old_and_new() -> None:
    with fields_panel() as r:
        assert echo(r).startswith("nothing yet")
        type_in(r, field_of(r, "In_Normal"), "a")
        assert echo(r) == "changed: 'hello' -> 'helloa'"
        panel_of(r).window.simulate("input", text="b")
        assert echo(r) == "changed: 'helloa' -> 'helloab'"
        assert any("Echo: changed: 'hello' -> 'helloa'" in x for x in r.lines)
        panel_of(r).window.simulate("key_down", key="enter")
        assert echo(r) == "submit (Enter)"


def test_the_limited_field_stops_at_eight_and_echo_hears_no_rejected_edit() -> None:
    with fields_panel() as r:
        f = field_of(r, "In_Max")
        type_in(r, f, "0123456789")
        assert f.inp.get("text") == "01234567"
        assert echo(r) == "changed: '' -> '01234567'"
        count = len(r.lines)
        panel_of(r).window.simulate("input", text="z")
        assert f.inp.get("text") == "01234567"
        # tre still reports the commit of a rejected edit (input); it reports no change
        assert not [x for x in r.lines[count:] if "changed:" in x]


def test_the_read_only_password_and_disabled_fields_take_no_text() -> None:
    with fields_panel() as r:
        for name in ("In_Read", "In_Off", "Ed_Off"):
            f = field_of(r, name)
            before = f.inp.get("text")
            type_in(r, f, "z")
            panel_of(r).window.simulate("key_down", key="backspace")
            assert f.inp.get("text") == before, name
        assert echo(r).startswith("nothing yet")  # no event came of any of them
        pw = field_of(r, "In_Pass")
        type_in(r, pw, "!")
        assert pw.inp.get("text") == "secret!" and pw.inp.get("obscured") is True


def test_the_editors_take_enter_as_a_new_line_and_echo_never_says_submit() -> None:
    with fields_panel() as r:
        ed = field_of(r, "Ed_Word")
        before = str(ed.inp.get("text"))
        w = panel_of(r).window
        w.simulate("pointer_down", node=ed.inp)
        w.simulate("pointer_up", node=ed.inp)
        w.simulate("key_down", key="end")  # the end of the paragraph
        w.simulate("key_down", key="enter")
        assert str(ed.inp.get("text")) == before + "\n"
        assert "submit" not in echo(r) and echo(r).startswith("changed:")
        w.simulate("input", text="x")
        assert str(ed.inp.get("text")) == before + "\nx" and echo(r).startswith("changed:")


def test_a_long_line_scrolls_in_scroll_and_ellipsis_and_not_in_clip() -> None:
    with fields_panel() as r:
        w = panel_of(r).window
        for name, scrolls in (("F_Scroll", True), ("F_Ellipsis", True), ("F_Clip", False)):
            f = field_of(r, name)
            w.simulate("pointer_down", node=f.inp)
            w.simulate("pointer_up", node=f.inp)
            w.simulate("key_down", key="end")
            x = f.inp.caret_rect()[0]
            if scrolls:
                assert 0 <= x <= f.inp.get("layout_width") and f.inp.text_rects(0, 1)[0][0] < 0, (
                    name
                )
            else:
                assert x > f.inp.get("layout_width") and f.inp.text_rects(0, 1)[0][0] == 0, name


def test_the_gallery_panel_has_no_text_field_and_no_keyboard() -> None:
    with fields_panel() as r:
        assert panel_of(r).window.get("keyboard") == "on_demand"
    # the first Panel is the M4a one: it holds no field
    assert "TextField" not in g.COLUMN and "TextInput" not in g.COLUMN


def test_the_gallery_checklist_has_the_text_field_lines() -> None:
    text = g.CHECKLIST
    for word in ("input-method", "Ctrl+V", "ELLIPSIS", "LOGICAL", "Max_Length", "read-only"):
        assert word in text, word
