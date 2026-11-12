"""The TextField block (Block Reference > TextField) on a headless tre window: how the model
composes it (``model.field``), what reaches tre, how it is as high as its lines, and how it
behaves: typing, ``On_Changed``, Enter, a limit, read-only, a password, scrolling, an ellipsis,
word wrap, a disabled field. ``window.simulate`` is the keyboard; there is no compositor."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import View, build
from tess_shell.model.field import compose, holds_text_field
from tess_shell.model.look import resolve
from tests.field_live import Field, look

LOOK = look()


def text(value: str) -> m.Text:
    return m.Text(value)


def num(value: float) -> m.Number:
    return m.Number(value)


def node(
    props: dict[str, m.Value] | None = None,
    style: dict[str, m.Value] | None = None,
    handlers: dict[str, m.Handler] | None = None,
    states: dict[str, dict[str, m.Value]] | None = None,
) -> m.Node:
    return m.Node(
        m.FIELD,
        name="F",
        props=props or {},
        style=style or {},
        handlers=handlers or {},
        states=states or {},
    )


def named(composed: m.Node) -> m.Node:
    """``composed`` with its three inner nodes named (a slot gives them names in a module): the
    text input ``In``, the size text ``Sz`` and the line ``Ln``."""
    (line,) = composed.children
    assert isinstance(line, m.Node)
    kids = tuple(
        dataclasses.replace(c, name={m.FIELD_INPUT: "In", m.FIELD_SIZE: "Sz"}[c.kind])
        for c in line.children
        if isinstance(c, m.Node)
    )
    return dataclasses.replace(
        composed, children=(dataclasses.replace(line, name="Ln", children=kids),)
    )


class Built:
    """A field built on a headless window, the events its sink saw, and its nodes."""

    def __init__(self, field_node: m.Node, width: int = 400, height: int = 200) -> None:
        self.window = Window(width=width, height=height)
        # a row that does not stretch its children: a field is as high as its lines
        self.holder = self.window.create(
            "box", display="flex", flex_direction="horizontal", align_items="start"
        )
        self.window.root.add_child(self.holder)
        self.seen: list[tuple[str, Any]] = []
        self.view = self.build(field_node)

    def build(self, field_node: m.Node) -> View:
        nodes, errors = resolve([named(compose(field_node))], LOOK)
        assert errors == []
        view = build(nodes, self.window, self.holder)
        view.sink = lambda handler, key, raw: self.seen.append(
            (key, (getattr(raw, "old_value", None), getattr(raw, "new_value", None), raw))
        )
        self.window.advance(16)
        return view

    @property
    def field(self) -> Field:
        return Field(self.view.entries[0])

    @property
    def inp(self) -> Any:
        return self.view.nodes["In"]

    def focus(self) -> None:
        self.window.simulate("pointer_down", node=self.inp)
        self.window.simulate("pointer_up", node=self.inp)
        assert self.inp.get("focused")

    def type(self, text_: str) -> None:
        self.window.simulate("input", text=text_)

    def key(self, key: str, **mods: bool) -> None:
        self.window.simulate("key_down", key=key, **mods)

    def events(self, key: str) -> list[tuple[Any, Any]]:
        return [(old, new) for k, (old, new, _) in self.seen if k == key]


def handlers(*keys: str) -> dict[str, m.Handler]:
    return {k: m.Handler(k.removeprefix("On_").lower()) for k in keys}


ALL = ("On_Changed", "On_Submit", "On_Text_Commit")


# -- the composition ---------------------------------------------------------------------------


def kinds(n: m.Node) -> list[Any]:
    return [n.kind, [kinds(c) for c in n.children if isinstance(c, m.Node)]]


def test_a_single_line_field_is_a_box_a_line_a_size_text_and_a_text_input() -> None:
    out = compose(node())
    assert kinds(out) == [
        "TextField",
        [["TextField.line", [["TextField.size", []], ["TextField.input", []]]]],
    ]
    (line,) = out.children
    assert isinstance(line, m.Node) and line.props["Align_Self"] == m.Enum("CENTER")
    inp = line.children[1]
    assert isinstance(inp, m.Node)
    assert inp.props["Multiline"] == m.Bool(False)
    assert inp.style["Overflow"] == m.Enum("SCROLL")  # always set: a single line stays one line
    assert "Wrap" not in inp.props


def test_a_multi_line_field_fills_its_box_wraps_by_word_and_is_three_lines_high() -> None:
    out = compose(node({"Multiline": m.Bool(True)}))
    (line,) = out.children
    assert isinstance(line, m.Node) and line.props["Align_Self"] == m.Enum("STRETCH")
    size, inp = line.children
    assert isinstance(size, m.Node) and isinstance(inp, m.Node)
    assert size.props["Lines"] == num(3)
    assert inp.props["Wrap"] == m.Enum("WORD") and "Overflow" not in inp.style


def test_a_multi_line_field_with_a_height_has_no_size_text_and_lines_replace_the_default() -> None:
    tall = compose(node({"Multiline": m.Bool(True), "Height": m.Length(90)}))
    (line,) = tall.children
    assert isinstance(line, m.Node) and [
        c.kind for c in line.children if isinstance(c, m.Node)
    ] == [m.FIELD_INPUT]
    five = compose(node({"Multiline": m.Bool(True), "Lines": num(5), "Wrap": m.Enum("NONE")}))
    size, inp = five.children[0].children  # type: ignore[union-attr]
    assert size.props["Lines"] == num(5) and inp.props["Wrap"] == m.Enum("NONE")  # type: ignore[union-attr]


def test_a_single_line_field_keeps_its_size_text_when_it_has_a_height() -> None:
    out = compose(node({"Height": m.Length(40)}))
    (line,) = out.children
    assert isinstance(line, m.Node) and len(line.children) == 2


def test_every_key_goes_to_the_node_that_takes_it() -> None:
    out = compose(
        node(
            {
                "Text": text("a"),
                "Placeholder": text("p"),
                "Selection": m.Seq((num(0), num(1))),
                "Show_Whitespace": m.Bool(True),
                "Read_Only": m.Bool(True),
                "Max_Length": num(3),
                "Password": m.Bool(True),
                "Label": text("Name"),
                "Width": m.Length(100),
                "Enabled": m.Bool(False),
                "Padding": m.Length(2),
                "Font_Size": num(20),
            },
            {"Background": m.Color(1, 2, 3, 255), "Foreground": m.Color(4, 5, 6, 255)},
            handlers("On_Click", *ALL),
        )
    )
    (line,) = out.children
    assert isinstance(line, m.Node)
    size, inp = line.children
    assert isinstance(size, m.Node) and isinstance(inp, m.Node)
    assert {"Width", "Enabled", "Padding"} <= out.props.keys() and "Text" not in out.props
    assert out.style["Background"] == m.Color(1, 2, 3, 255) and "Foreground" not in out.style
    assert set(out.handlers) == {"On_Click"}
    assert {"Text", "Placeholder", "Selection", "Show_Whitespace", "Read_Only", "Max_Length"} <= (
        inp.props.keys()
    )
    assert {"Password", "Label", "Multiline", "Font_Size"} <= inp.props.keys()
    assert inp.style["Foreground"] == m.Color(4, 5, 6, 255)
    assert set(inp.handlers) == set(ALL)
    assert size.props.get("Font_Size") == num(20) and "Foreground" not in size.style


def test_a_key_that_means_nothing_to_the_form_is_left_out() -> None:
    single = compose(node({"Wrap": m.Enum("NONE"), "Lines": num(3)}))
    inp = single.children[0].children[1]  # type: ignore[union-attr]
    assert isinstance(inp, m.Node) and "Wrap" not in inp.props
    size = single.children[0].children[0]  # type: ignore[union-attr]
    assert isinstance(size, m.Node) and "Lines" not in size.props
    multi = compose(
        node(
            {"Multiline": m.Bool(True), "Password": m.Bool(True)},
            {"Overflow": m.Enum("ELLIPSIS")},
            handlers("On_Submit", "On_Changed"),
        )
    )
    inp = multi.children[0].children[1]  # type: ignore[union-attr]
    assert isinstance(inp, m.Node)
    assert "Password" not in inp.props and "Overflow" not in inp.style
    assert set(inp.handlers) == {"On_Changed"}  # Enter is a new line


def test_a_field_with_no_look_gets_one_from_the_theme_and_its_own_keys_win() -> None:
    plain = compose(node())
    assert {"Background", "Border_Width", "Border_Color", "Corner_Radius"} <= plain.style.keys()
    assert isinstance(plain.style["Background"], m.TokenRef)
    assert isinstance(plain.props["Padding"], m.Sides)
    own = compose(node({"Padding": m.Length(1)}, {"Background": m.Color(9, 9, 9, 255)}))
    assert own.style["Background"] == m.Color(9, 9, 9, 255) and own.props["Padding"] == m.Length(1)
    inp = plain.children[0].children[1]  # type: ignore[union-attr]
    assert isinstance(inp, m.Node) and isinstance(inp.style["Foreground"], m.TokenRef)
    assert "hovered" in plain.states and "disabled" in plain.states


def test_a_state_rule_is_split_between_the_box_and_the_text() -> None:
    out = compose(
        node(
            states={
                "hovered": {
                    "Background": m.Color(1, 1, 1, 255),
                    "Foreground": m.Color(2, 2, 2, 255),
                }
            }
        )
    )
    assert set(out.states["hovered"]) == {"Background", "Border_Color"}  # the box's own default too
    inp = out.children[0].children[1]  # type: ignore[union-attr]
    assert isinstance(inp, m.Node) and inp.states == {
        "hovered": {"Foreground": m.Color(2, 2, 2, 255)}
    }


def test_holds_text_field_finds_a_field_in_a_branch() -> None:
    field_node = node()
    assert holds_text_field([m.Node("Box", children=(field_node,))])
    assert holds_text_field([m.IfNode(body=(field_node,))])
    assert holds_text_field([m.ForNode("x", body=(m.Node("Box", children=(field_node,)),))])
    assert not holds_text_field([m.Node("Box", children=(m.Node("Text"),))])


# -- what reaches tre --------------------------------------------------------------------------


def test_the_keys_reach_the_text_input() -> None:
    b = Built(
        node(
            {
                "Text": text("héllo"),
                "Placeholder": text("Name"),
                "Read_Only": m.Bool(True),
                "Max_Length": num(9),
                "Password": m.Bool(True),
                "Show_Whitespace": m.Bool(True),
                "Label": text("Your name"),
            },
            {"Overflow": m.Enum("ELLIPSIS"), "Font_Size": num(18)},
        )
    )
    inp = b.field.inp
    assert inp.get("text") == "héllo" and inp.get("placeholder") == "Name"
    assert inp.get("read_only") is True and inp.get("max_length") == 9
    assert inp.get("obscured") is True and inp.get("show_whitespace") is True
    assert inp.get("overflow") == "ellipsis" and inp.get("multiline") is False
    assert inp.get("font_size") == 18 and inp.get("label") == "Your name"


@pytest.mark.parametrize(
    ("word", "tre"), [("SCROLL", "scroll"), ("ELLIPSIS", "ellipsis"), ("CLIP", "clip")]
)
def test_overflow_words_are_tres(word: str, tre: str) -> None:
    b = Built(node(style={"Overflow": m.Enum(word)}))
    assert b.field.inp.get("overflow") == tre and b.field.inp.get("wrap") is None


@pytest.mark.parametrize(("word", "tre"), [("WORD", "word"), ("NONE", "none")])
def test_wrap_words_are_tres(word: str, tre: str) -> None:
    b = Built(node({"Multiline": m.Bool(True), "Wrap": m.Enum(word)}))
    assert b.field.inp.get("wrap") == tre and b.field.inp.get("multiline") is True
    assert b.field.inp.get("overflow") is None


def test_a_max_length_of_zero_is_no_limit_and_a_selection_selects() -> None:
    b = Built(
        node({"Max_Length": num(0), "Text": text("abcdef"), "Selection": m.Seq((num(1), num(3)))})
    )
    assert b.field.inp.get("max_length") is None and b.field.inp.get("selection") == (1, 3)


def test_the_box_paints_and_the_text_input_draws_the_text() -> None:
    b = Built(
        node(
            style={
                "Background": m.Color(10, 20, 30, 255),
                "Foreground": m.Color(200, 210, 220, 255),
            }
        )
    )
    assert b.field.box.get("fill") == (10, 20, 30, 255)
    assert b.field.inp.get("fill") == (200, 210, 220, 255)
    assert b.field.size.get("fill") == (0, 0, 0, 0)  # the size text paints nothing


def test_the_default_look_is_the_themes() -> None:
    b = Built(node())
    box, inp = b.field.box, b.field.inp
    assert box.get("fill") == (27, 34, 43, 255)  # surface_raised
    assert box.get("stroke_color") == (85, 101, 122, 255) and box.get("stroke_width") == 1
    assert (
        inp.get("fill") == (228, 234, 241, 255) and inp.get("font_size") == 14
    )  # on_surface, body


# -- the height of the lines -------------------------------------------------------------------


def test_a_single_line_field_is_one_line_and_its_padding_high_and_200_wide() -> None:
    b = Built(node({"Padding": m.Sides(10, 6, 10, 6)}))
    line = b.window.measure_text("x", font_size=14, max_lines=1)[1]
    assert b.field.box.get("layout_width") == 200
    assert b.field.box.get("layout_height") == pytest.approx(line + 12, abs=1)
    assert b.field.inp.get("layout_height") == pytest.approx(line, abs=1)


def test_the_field_grows_with_its_font() -> None:
    small = Built(node(style={"Font_Size": num(12)}))
    big = Built(node(style={"Font_Size": num(30)}))
    assert big.field.box.get("layout_height") > small.field.box.get("layout_height") + 15


def test_a_multi_line_field_is_as_high_as_its_lines() -> None:
    b = Built(node({"Multiline": m.Bool(True), "Lines": num(4), "Padding": m.Length(0)}))
    line = b.window.measure_text("x", font_size=14, max_lines=1)[1]
    assert b.field.box.get("layout_height") == pytest.approx(4 * line, abs=2)
    assert b.field.inp.get("layout_height") == pytest.approx(4 * line, abs=2)


def test_a_height_is_the_boxs_and_the_text_input_fills_it() -> None:
    b = Built(node({"Multiline": m.Bool(True), "Height": m.Length(90), "Padding": m.Length(5)}))
    assert b.field.box.get("layout_height") == 90 and b.field.inp.get("layout_height") == 80
    assert b.field.size is None


def test_a_single_line_field_taller_than_a_line_keeps_the_line_in_the_middle() -> None:
    b = Built(node({"Height": m.Length(60), "Padding": m.Length(0)}))
    inp = b.field.inp
    assert b.field.box.get("layout_height") == 60
    assert inp.get("layout_y") - b.field.box.get("layout_y") == pytest.approx(
        (60 - inp.get("layout_height")) / 2, abs=1
    )


# -- typing, On_Changed and the text the module sets -------------------------------------------


def test_typing_raises_on_changed_with_the_old_and_the_new_text_and_on_text_commit() -> None:
    b = Built(node({"Text": text("ab")}, handlers=handlers(*ALL)))
    b.focus()
    b.type("c")
    assert b.events("On_Changed") == [("ab", "abc")]
    assert [raw.text for k, (_, _, raw) in b.seen if k == "On_Text_Commit"] == ["c"]
    b.key("backspace")
    assert b.events("On_Changed") == [("ab", "abc"), ("abc", "ab")]


def test_the_text_a_module_sets_raises_nothing_and_a_clicked_field_takes_typing() -> None:
    b = Built(node({"Text": text("ab")}, handlers=handlers(*ALL)))
    assert b.view.update([("In", "Text", text("module set"))]) == []
    assert b.inp.get("text") == "module set" and b.seen == []
    b.focus()
    b.type("!")
    assert b.inp.get("text") == "module set!" and b.events("On_Changed") == [
        ("module set", "module set!")
    ]


def test_a_module_that_echoes_the_typed_text_does_not_move_the_caret() -> None:
    b = Built(node({"Text": text("abcd")}, handlers=handlers("On_Changed")))
    b.focus()
    b.inp.set(selection=(2, 2))
    b.type("X")  # abXcd, the caret after the X
    caret = b.inp.caret_rect()
    assert b.view.update([("In", "Text", text("abXcd"))]) == []  # what the module read back
    assert b.inp.caret_rect() == caret and b.inp.get("selection") == (3, 3)
    assert b.view.update([("In", "Text", text("other"))]) == []
    assert b.inp.get("text") == "other" and b.inp.get("selection") == (5, 5)  # a new text: the end
    assert len(b.events("On_Changed")) == 1


def test_an_input_method_composes_in_the_block_and_commits_through_both_events() -> None:
    b = Built(node({"Text": text("ab")}, handlers=handlers(*ALL)))
    b.focus()
    b.window.simulate("ime_preedit", text="ni", cursor=(0, 2))
    assert b.inp.get("text") == "ab" and b.seen == []  # a preview is not text yet
    b.window.simulate("input", text="你")
    assert b.inp.get("text") == "ab你"
    assert b.events("On_Changed") == [("ab", "ab你")]
    assert [raw.text for k, (_, _, raw) in b.seen if k == "On_Text_Commit"] == ["你"]


def test_a_click_in_the_padding_gives_the_field_the_focus() -> None:
    b = Built(node({"Padding": m.Length(12)}))
    assert not b.inp.get("focused")
    b.window.simulate("pointer_down", node=b.field.box, x=8, y=8)
    assert b.inp.get("focused")


# -- Enter -------------------------------------------------------------------------------------


def test_enter_submits_a_single_line_field() -> None:
    b = Built(node({"Text": text("ab")}, handlers=handlers(*ALL)))
    b.focus()
    b.key("enter")
    assert [k for k, _ in b.seen] == ["On_Submit"] and b.inp.get("text") == "ab"


def test_enter_adds_a_line_to_a_multi_line_field_and_submits_nothing() -> None:
    b = Built(node({"Multiline": m.Bool(True), "Text": text("ab")}, handlers=handlers(*ALL)))
    b.focus()
    b.key("enter")
    assert b.inp.get("text") == "ab\n"
    assert [k for k, _ in b.seen] == ["On_Changed"]  # there is no On_Submit on this field


# -- a limit, read-only, a password ------------------------------------------------------------


def test_max_length_cuts_an_edit_and_a_rejected_edit_raises_no_change() -> None:
    b = Built(node({"Max_Length": num(5), "Text": text("abc")}, handlers=handlers("On_Changed")))
    b.focus()
    b.type("defgh")
    assert b.inp.get("text") == "abcde" and b.events("On_Changed") == [("abc", "abcde")]
    b.type("z")
    assert b.inp.get("text") == "abcde" and len(b.events("On_Changed")) == 1


def commits(b: Built) -> list[Any]:
    return [raw.text for k, (_, _, raw) in b.seen if k == "On_Text_Commit"]


def test_a_commit_that_max_length_refused_raises_no_on_text_commit() -> None:
    """tre raises ``input`` for a refused edit, with the text as it was (Q20)."""
    b = Built(node({"Max_Length": num(3), "Text": text("abc")}, handlers=handlers(*ALL)))
    b.focus()
    b.type("d")
    assert b.inp.get("text") == "abc" and b.seen == []
    b.key("backspace")
    assert [k for k, _ in b.seen] == ["On_Changed"]
    b.type("c")  # the same text as before the backspace: but this edit took
    assert commits(b) == ["c"] and b.inp.get("text") == "abc"
    b.type("x")  # full again
    assert commits(b) == ["c"]


def test_a_text_the_shell_sets_is_what_a_commit_is_compared_to() -> None:
    b = Built(node({"Max_Length": num(3), "Text": text("abc")}, handlers=handlers(*ALL)))
    b.focus()
    assert b.view.update([("In", "Text", text("ab"))]) == []  # the module sets another text
    b.type("c")  # an accepted edit that gives the text the field had before the module's set
    assert b.inp.get("text") == "abc" and commits(b) == ["c"]
    b.type("x")
    assert commits(b) == ["c"]
    b.view.rebuild(
        resolve(
            [
                named(
                    compose(
                        node({"Max_Length": num(3), "Text": text("xyz")}, handlers=handlers(*ALL))
                    )
                )
            ],
            LOOK,
        )[0]
    )
    b.type("w")  # refused: the text is the one the rebuild set
    assert commits(b) == ["c"]
    b.key("backspace")
    b.type("z")
    assert commits(b) == ["c", "z"]


def test_a_text_longer_than_the_limit_is_kept_and_can_be_deleted() -> None:
    b = Built(node({"Max_Length": num(2), "Text": text("abcdef")}, handlers=handlers("On_Changed")))
    assert b.inp.get("text") == "abcdef"
    b.focus()
    b.key("backspace")
    assert b.inp.get("text") == "abcde"


def test_a_read_only_field_edits_nothing_and_raises_nothing() -> None:
    b = Built(node({"Read_Only": m.Bool(True), "Text": text("abc")}, handlers=handlers(*ALL)))
    b.focus()
    b.type("z")
    b.key("backspace")
    assert b.inp.get("text") == "abc" and b.seen == []
    b.window.simulate("ime_preedit", text="ni", cursor=(0, 2))
    b.window.simulate("input", text="你")
    assert b.inp.get("text") == "abc" and b.seen == []


def test_a_read_only_field_can_be_selected() -> None:
    b = Built(node({"Read_Only": m.Bool(True), "Text": text("abc")}))
    b.focus()
    b.key("a", ctrl=True)
    assert b.inp.get("selection") == (0, 3)


def test_a_password_field_draws_bullets_and_is_obscured() -> None:
    plain = Built(node({"Text": text("secret")}))
    hidden = Built(node({"Text": text("secret"), "Password": m.Bool(True)}))
    assert hidden.inp.get("obscured") is True and plain.inp.get("obscured") is False
    assert hidden.inp.get("text") == "secret"  # the value is the text; only the picture hides it
    assert plain.window.snapshot()[0] != hidden.window.snapshot()[0]


# -- a line longer than the box: Overflow ------------------------------------------------------

LONG = "The quick brown fox jumps over the lazy dog, again and again and again"


def width(b: Built) -> float:
    return float(b.inp.get("layout_width"))


def test_scroll_keeps_the_caret_in_view_while_the_field_is_focused() -> None:
    b = Built(node({"Text": text(LONG)}, {"Overflow": m.Enum("SCROLL")}))
    b.focus()
    b.inp.set(selection=(len(LONG), len(LONG)))
    x, _, w, _ = b.inp.caret_rect()
    assert 0 <= x <= width(b) and w > 0
    (first,) = b.inp.text_rects(0, 1)
    assert first[0] < 0  # the start is scrolled out to the left
    b.inp.set(selection=(0, 0))
    assert b.inp.text_rects(0, 1)[0][0] >= 0  # and back when the caret returns
    assert len(b.inp.text_rects(0, len(LONG))) == 1  # one line, never wrapped


def test_scroll_follows_typing_and_shows_the_start_again_when_the_field_loses_the_focus() -> None:
    b = Built(node({"Text": text(LONG)}, {"Overflow": m.Enum("SCROLL")}))
    b.focus()
    b.key("end")
    b.type("!")
    assert 0 <= b.inp.caret_rect()[0] <= width(b)
    other = b.window.create("box", width=10, height=10, focusable=True)
    b.window.root.add_child(other)
    other.focus()
    assert b.inp.text_rects(0, 1)[0][0] >= 0


def test_ellipsis_cuts_the_unfocused_line_like_a_text_and_scrolls_once_focused() -> None:
    style = {"Overflow": m.Enum("ELLIPSIS"), "Foreground": m.Color(255, 255, 255, 255)}
    b = Built(node({"Text": text(LONG), "Padding": m.Length(0)}, style))
    # a Text node cut with Overflow ELLIPSIS in the same box looks the same (tre: pixel-equal)
    ref = Window(width=400, height=200)
    box = ref.create(
        "box", width=200, height=b.field.box.get("layout_height"), fill=b.field.box.get("fill")
    )
    box.set(**{k: b.field.box.get(k) for k in ("stroke_width", "stroke_color", "corner_radius")})
    cut = ref.create(
        "text",
        text=LONG,
        width=200,
        height=b.field.inp.get("layout_height"),
        font_size=14,
        font_family=b.field.inp.get("font_family"),
        fill=(255, 255, 255, 255),
        wrap="none",
        overflow="ellipsis",
        max_lines=1,
    )
    box.add_child(cut)
    ref.root.add_child(box)
    ref.advance(16)
    assert _crop(b.window.snapshot(), 200, 24) == _crop(ref.snapshot(), 200, 24)
    b.focus()
    b.key("end")
    assert 0 <= b.inp.caret_rect()[0] <= width(b)
    assert b.inp.text_rects(0, 1)[0][0] < 0


def _crop(snap: tuple[bytes, int, int], w: int, h: int) -> bytes:
    data, full_w, _ = snap
    return b"".join(data[(y * full_w) * 4 : (y * full_w + w) * 4] for y in range(h))


def test_clip_never_scrolls_so_the_caret_can_sit_past_the_edge() -> None:
    b = Built(node({"Text": text(LONG)}, {"Overflow": m.Enum("CLIP")}))
    b.focus()
    b.key("end")
    assert b.inp.caret_rect()[0] > width(b)
    assert b.inp.text_rects(0, 1)[0][0] >= 0  # the start is where it was


def test_the_words_of_overflow_stay_one_line_each() -> None:
    for word in ("SCROLL", "ELLIPSIS", "CLIP"):
        b = Built(node({"Text": text(LONG)}, {"Overflow": m.Enum(word)}))
        assert len(b.inp.text_rects(0, len(LONG))) == 1, word


# -- a multi-line field: Wrap ------------------------------------------------------------------

PARAGRAPH = " ".join(["word"] * 40)


def test_word_wrap_breaks_lines_at_the_width() -> None:
    b = Built(node({"Multiline": m.Bool(True), "Text": text(PARAGRAPH), "Wrap": m.Enum("WORD")}))
    rects = b.inp.text_rects(0, len(PARAGRAPH))
    assert len(rects) > 1
    assert all(r[0] + r[2] <= width(b) + 1 for r in rects)  # none past the box


def test_no_wrap_keeps_the_line_whole_and_scrolls_sideways_to_the_caret() -> None:
    b = Built(node({"Multiline": m.Bool(True), "Text": text(PARAGRAPH), "Wrap": m.Enum("NONE")}))
    assert len(b.inp.text_rects(0, len(PARAGRAPH))) == 1
    b.focus()
    b.inp.set(selection=(len(PARAGRAPH), len(PARAGRAPH)))
    assert 0 <= b.inp.caret_rect()[0] <= width(b)
    assert b.inp.text_rects(0, 1)[0][0] < 0


def test_a_new_line_is_a_line_in_either_wrap() -> None:
    for word in ("WORD", "NONE"):
        b = Built(node({"Multiline": m.Bool(True), "Text": text("one\ntwo"), "Wrap": m.Enum(word)}))
        assert len(b.inp.text_rects(0, 7)) == 2, word


# -- Enabled -----------------------------------------------------------------------------------


def test_a_disabled_field_takes_no_text_no_focus_and_raises_nothing() -> None:
    b = Built(node({"Enabled": m.Bool(False), "Text": text("ab")}, handlers=handlers(*ALL)))
    inp = b.inp
    assert inp.get("disabled") is True and inp.get("read_only") is True
    assert inp.get("hit_testable") is False and b.field.box.get("disabled") is True
    b.window.simulate("pointer_down", node=inp)
    b.window.simulate("pointer_up", node=inp)
    b.window.simulate("pointer_down", node=b.field.box, x=8, y=8)
    assert not inp.get("focused")
    inp.focus()  # a keyboard that reached it anyway
    b.type("z")
    b.key("enter")
    assert inp.get("text") == "ab" and b.seen == []


def test_a_field_disabled_while_it_has_the_focus_gives_it_up() -> None:
    b = Built(node({"Text": text("ab")}, handlers=handlers(*ALL)))
    b.focus()
    assert b.view.update([("F", "Enabled", m.Bool(False))]) == []
    assert not b.inp.get("focused") and b.inp.get("disabled") is True
    b.type("z")
    assert b.inp.get("text") == "ab" and b.seen == []


def test_an_enabled_field_has_what_the_file_declared_again() -> None:
    b = Built(
        node(
            {"Enabled": m.Bool(False), "Read_Only": m.Bool(False)}, handlers=handlers("On_Changed")
        )
    )
    assert b.view.update([("F", "Enabled", m.Bool(True))]) == []
    inp = b.inp
    assert inp.get("disabled") is False and inp.get("read_only") is False
    assert inp.get("hit_testable") is True
    b.focus()
    b.type("z")
    assert inp.get("text") == "z" and b.events("On_Changed") == [("", "z")]


def test_a_read_only_field_that_is_enabled_again_stays_read_only() -> None:
    b = Built(node({"Enabled": m.Bool(False), "Read_Only": m.Bool(True)}))
    assert b.view.update([("F", "Enabled", m.Bool(True))]) == []
    assert b.inp.get("read_only") is True


def test_a_disabled_field_shows_its_disabled_look() -> None:
    b = Built(node({"Enabled": m.Bool(False)}))
    assert b.field.box.get("opacity") == 0.5  # the default :disabled look
    assert b.view.update([("F", "Enabled", m.Bool(True))]) == []
    assert b.field.box.get("opacity") == 1.0


# -- states ------------------------------------------------------------------------------------


def test_hovered_and_pressed_show_on_the_box_and_the_text_follows_the_box() -> None:
    hovered = {"Border_Color": m.Color(1, 2, 3, 255), "Foreground": m.Color(4, 5, 6, 255)}
    pressed = {"Background": m.Color(7, 8, 9, 255), "Foreground": m.Color(10, 11, 12, 255)}
    b = Built(node(states={"hovered": hovered, "pressed": pressed}))
    box, inp = b.field.box, b.field.inp
    base_fill, base_text = box.get("fill"), inp.get("fill")
    b.window.simulate("pointer_enter", node=box)
    assert box.get("stroke_color") == (1, 2, 3, 255) and inp.get("fill") == (4, 5, 6, 255)
    b.window.simulate("pointer_down", node=box, x=8, y=8)
    assert box.get("fill") == (7, 8, 9, 255) and inp.get("fill") == (10, 11, 12, 255)
    b.window.simulate("pointer_up", node=box, x=8, y=8)
    b.window.simulate("pointer_leave")
    assert box.get("fill") == base_fill and inp.get("fill") == base_text


def test_the_default_hover_is_the_primary_outline() -> None:
    b = Built(node())
    b.window.simulate("pointer_enter", node=b.field.box)
    assert b.field.box.get("stroke_color") == (91, 151, 201, 255)  # $color.primary


# -- a reload ----------------------------------------------------------------------------------


def test_a_reload_changes_the_keys_in_place_and_keeps_what_the_user_typed() -> None:
    b = Built(
        node({"Text": text("ab"), "Placeholder": text("one")}, {"Overflow": m.Enum("SCROLL")})
    )
    before = [b.field.box, b.field.line, b.field.inp, b.field.size]
    b.focus()
    b.type("c")
    again = node(
        {"Text": text("ab"), "Placeholder": text("two"), "Max_Length": num(9)},
        {"Overflow": m.Enum("ELLIPSIS")},
    )
    nodes, _ = resolve([named(compose(again))], LOOK)
    b.view.rebuild(nodes)
    inp = b.field.inp
    assert [b.field.box, b.field.line, b.field.inp, b.field.size] == before  # the same nodes
    assert inp.get("placeholder") == "two" and inp.get("max_length") == 9
    assert inp.get("overflow") == "ellipsis"
    assert inp.get("text") == "abc"  # the declared text did not change: the typing stays


def test_a_reload_that_changes_the_declared_text_sets_it() -> None:
    b = Built(node({"Text": text("ab")}))
    nodes, _ = resolve([named(compose(node({"Text": text("new")})))], LOOK)
    b.view.rebuild(nodes)
    assert b.field.inp.get("text") == "new"


def test_a_reload_between_one_line_and_many_rebuilds_the_form() -> None:
    b = Built(node({"Text": text("ab")}))
    nodes, _ = resolve(
        [named(compose(node({"Text": text("ab"), "Multiline": m.Bool(True)})))], LOOK
    )
    b.view.rebuild(nodes)
    assert b.field.inp.get("multiline") is True and b.field.inp.get("wrap") == "word"
    assert b.field.inp.get("overflow") is None


def test_a_reload_that_adds_a_height_to_a_multi_line_field_drops_its_size_text() -> None:
    b = Built(node({"Multiline": m.Bool(True)}))
    assert b.field.size is not None
    nodes, _ = resolve(
        [named(compose(node({"Multiline": m.Bool(True), "Height": m.Length(70)})))], LOOK
    )
    b.view.rebuild(nodes)
    assert b.field.size is None and b.field.box.get("layout_height") == 70


def test_a_look_change_repaints_the_field() -> None:
    from tess_shell.appearance import Appearance

    b = Built(node({"Text": text("x")}))
    dark = (b.field.box.get("fill"), b.field.inp.get("fill"))
    light = LOOK.with_appearance(Appearance(scheme="light"))
    nodes, _ = resolve([named(compose(node({"Text": text("x")})))], light)
    b.view.rebuild(nodes)
    assert (b.field.box.get("fill"), b.field.inp.get("fill")) != dark
    assert b.field.box.get("fill") == (255, 255, 255, 255)  # surface_raised of the light mode


# -- handlers that come and go -----------------------------------------------------------------


def test_a_handler_added_by_a_reload_runs_and_one_removed_stops() -> None:
    b = Built(node({"Text": text("ab")}))
    b.focus()
    b.type("c")
    assert b.seen == []
    nodes, _ = resolve(
        [named(compose(node({"Text": text("ab")}, handlers=handlers("On_Changed"))))], LOOK
    )
    b.view.rebuild(nodes)
    b.type("d")
    assert b.events("On_Changed") == [("abc", "abcd")]
    nodes, _ = resolve([named(compose(node({"Text": text("ab")})))], LOOK)
    b.view.rebuild(nodes)
    b.type("e")
    assert len(b.events("On_Changed")) == 1
