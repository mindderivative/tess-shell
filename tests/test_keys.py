"""The keys of each widget (M6b, T-048; Standard Modules > Keyboard Operation): one test a widget,
each operating the real M4 gallery shell by key events only, and the cases around them.

The gallery shells are the ones the KWin kits are made of (``tests/kwin/prepare_m4a_gallery.py``,
``prepare_m4b_gallery.py`` and ``prepare_m4c_gallery.py``): their shell text and their test modules
are imported, loaded by a real module host and drawn by real surface windows with no compositor, and
every key is ``Window.simulate("key_down", ...)`` on the window that has the keyboard: the Panel, or
the Popup of an open menu. What a module did shows in the line its ``Probe`` or ``Echo`` logs.

Not tested here, on purpose: Ctrl+C, Ctrl+X and Ctrl+V. tre's clipboard is the operating system's
(``Window.read_clipboard`` reaches the real one, even on a headless window), and no test of this
shell touches the real clipboard.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from tests.kwin import prepare_m4a_gallery as m4a
from tests.kwin import prepare_m4b_gallery as m4b
from tests.kwin import prepare_m4c_gallery as m4c
from tests.test_focus_shell import ring_on
from tests.test_popup import _SINKS
from tests.widgets_live import Widgets, running


@pytest.fixture(autouse=True)
def _drain_the_rig_sinks() -> Iterator[None]:
    """As in ``tests/test_focus.py``: the popup rig's log sinks are left for its own module."""
    yield
    from loguru import logger

    while _SINKS:
        logger.remove(_SINKS.pop())


# -- the three galleries, headless ---------------------------------------------------------------


@contextmanager
def gallery_c() -> Iterator[Widgets]:
    """The M4c controls and lists: Panels ``Controls`` and ``Lists``, the ``Probe`` module."""
    with running(
        "",
        body=m4c.BODY,
        home="Controls",
        extra={"Probe": m4c.PROBE_TDL},
        extra_py={"Probe": m4c.PROBE_PY},
    ) as w:
        assert w.warnings() == [], w.warnings()
        yield w


@contextmanager
def gallery_b() -> Iterator[Widgets]:
    """The M4b display widgets: Panel ``Gallery``, the ``Toggler`` module (Button and Expander)."""
    with running(
        "",
        body=m4b.BODY,
        home="Gallery",
        extra={"Toggler": m4b.TOGGLER_TDL},
        extra_py={"Toggler": m4b.TOGGLER_PY},
    ) as w:
        # the one warning of the gallery is the icon that does not exist on purpose, and the bad
        # image file
        assert all("no-such-icon" in x or "bad.png" in x for x in w.warnings()), w.warnings()
        yield w


@contextmanager
def gallery_a() -> Iterator[Widgets]:
    """The M4a text fields: Panel ``Fields``, the ``Echo`` module."""
    modules = {"Meter": (m4a.METER_TDL, m4a.METER_PY), "Pad": (m4a.PAD_TDL, m4a.PAD_PY)}
    modules["Echo"] = (m4a.ECHO_TDL, m4a.ECHO_PY)
    with running(
        "",
        body=m4a.BODY,
        home="Fields",
        extra={k: v[0] for k, v in modules.items()},
        extra_py={k: v[1] for k, v in modules.items()},
        extra_sheet=m4a.STYLESHEET,
    ) as w:
        assert w.warnings() == [], w.warnings()
        yield w


class Keys:
    """The keyboard of one surface of a gallery: the Panel's window, or an open Popup's."""

    def __init__(self, w: Widgets, home: str) -> None:
        self.w = w
        self.surface = w.surface(home)
        self.seen = 0  # how many lines the module had said when ``said`` was last asked

    @property
    def window(self) -> Any:
        return self.surface.window

    @property
    def view(self) -> Any:
        return self.surface.view

    def press(self, key: str, window: Any = None, **mods: bool) -> None:
        """A key down and up on ``window`` (the Panel's), then what the modules sent is shown."""
        target = window or self.window
        target.simulate("key_down", key=key, **mods)
        target.simulate("key_up", key=key, **mods)
        self.w.flush()
        target.advance(16)

    def type(self, text: str) -> None:
        """Committed text arrives as tre's ``input`` event (what a real key press that makes a
        character sends after its ``key_down``)."""
        self.window.simulate("input", text=text)
        self.w.flush()
        self.window.advance(16)

    def focused(self, view: Any = None) -> Any:
        found = [n for n in (view or self.view).nodes.values() if n.get("focused")]
        assert len(found) <= 1, found
        return found[0] if found else None

    def name_of(self, view: Any = None) -> str:
        """The label of the focused node, or the id of a text input (which has none)."""
        for key, node in (view or self.view).nodes.items():
            if node.get("focused"):
                return str(node.get("label") or key)
        return ""

    def tab_to(self, label: str, shift: bool = False) -> Any:
        """Tab until the node labelled ``label`` (or an id with it in) has the focus."""
        for _ in range(60):
            self.window.simulate("key_down", key="tab", shift=shift)
            if label in self.name_of():
                self.window.advance(16)
                return self.focused()
        raise AssertionError(f"Tab never reached {label!r}")

    def tab_round(self) -> list[str]:
        """What Tab reaches, once round."""
        seen: list[str] = []
        for _ in range(60):
            self.window.simulate("key_down", key="tab")
            name = self.name_of()
            if seen and name == seen[0]:
                return seen
            seen.append(name)
        raise AssertionError(f"Tab never came round: {seen}")

    def settle(self, ms: float = 600) -> None:
        """Let an animation of the Panel run, and what the modules sent in the meantime show."""
        self.window.advance(ms)
        self.w.flush()
        self.window.advance(16)

    def said(self, tag: str = "Probe") -> list[str]:
        """What the ``Probe`` (or ``Echo``) module logged since the last call."""
        found = [x.split(f"{tag}: ", 1)[1] for x in self.w.lines if f"- {tag}: " in x]
        new = found[self.seen :]
        self.seen = len(found)
        return new


def descendants(node: Any) -> Iterator[Any]:
    """``node`` and every tre node under it (the unnamed blocks are in no view's ``nodes``)."""
    yield node
    for child in node.children():
        yield from descendants(child)


def texts(node: Any) -> list[str]:
    """The text of every ``Text`` under ``node``."""
    found: list[str] = []
    for n in descendants(node):
        try:
            found.append(str(n.get("text")))
        except ValueError:  # a node that has no text
            pass
    return found


def test_every_gallery_starts_with_no_warning_no_focus_and_nothing_said() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        assert k.focused() is None and k.said() == []


# -- Button --------------------------------------------------------------------------------------


def test_button_enter_and_space_press_it_and_the_state_shows_while_the_key_is_held() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        root = k.tab_to("Save")
        assert root.get("role") == "button" and ring_on(k.view, root, w.manager.look)
        k.said()
        k.press("enter")
        assert k.said() == ["Save clicked"]
        k.press("space")
        assert k.said() == ["Save clicked"]
        # held: the accessibility state ``pressed`` and the style state ``:pressed`` show while the
        # key is down, and the handler has run; the key going up ends both
        k.window.simulate("key_down", key="enter")
        assert root.get("pressed") is True  # tre draws the pressed layer while it holds
        assert k.said() == ["Save clicked"]
        k.window.simulate("key_up", key="enter")
        assert root.get("pressed") is None
        # the other keys do nothing, and the other Buttons are their own stops
        for other in ("a", "arrow_down", "arrow_left", "home", "escape"):
            k.press(other)
        assert k.said() == []
        k.tab_to("Open")
        k.press("space")
        assert k.said() == ["Open clicked"]
        k.tab_to("Account")
        k.press("enter")
        assert k.said() == ["Account clicked"]


def test_a_button_whose_focus_goes_while_a_key_is_held_is_not_left_pressed() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        root = k.tab_to("Save")
        k.window.simulate("key_down", key="space")
        assert root.get("pressed") is True
        k.window.simulate("key_down", key="tab")  # the focus moves on, the key-up goes elsewhere
        assert root.get("pressed") is None


def test_a_disabled_widget_takes_no_focus_and_no_key() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        # a key that reaches the window with nothing focused is no one's
        for key in ("enter", "space", "arrow_right", "home"):
            k.press(key)
        assert k.said() == []
        # the faint Button, Toggles, Checkboxes and Sliders of the gallery are no Tab stops
        names = k.tab_round()
        for faint in ("Off", "disabled", "disabled on", "Disabled", "Disabled on", "Upright off"):
            assert faint not in names, faint
        assert {"Save", "Open", "Next", "Account", "off", "on", "Remember", "Checked"} <= set(names)
        # and a disabled block that is given the focus all the same (a Toggle of the gallery, by a
        # call to ``focus()``) takes no key
        faint_toggle = w.of_use("Toggle", "Root", 2)
        assert faint_toggle.get("disabled") is True
        before = faint_toggle.get("checked")
        faint_toggle.focus()
        k.press("space")
        k.press("enter")
        assert faint_toggle.get("checked") == before and k.said() == []


# -- Toggle and Checkbox -------------------------------------------------------------------------


def test_toggle_space_flips_it_and_raises_on_changed_and_enter_does_nothing() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        root = k.tab_to("off")
        assert root.get("role") == "switch" and root.get("checked") is False
        k.said()
        k.press("space")
        assert root.get("checked") is True
        assert k.said() == ["Toggle off: False -> True"]
        k.press("enter")  # tre clicks the focused block for Enter too: not a flip here
        assert root.get("checked") is True and k.said() == []
        k.press("space")
        assert root.get("checked") is False and k.said() == ["Toggle off: True -> False"]
        # a held Space repeats: the repeat is not a second flip
        k.window.simulate("key_down", key="space")
        k.window.simulate("key_down", key="space", repeat=True)
        k.window.simulate("key_up", key="space")
        assert k.said() == ["Toggle off: False -> True"] and root.get("checked") is True
        k.tab_to("on")
        k.press("space")
        assert k.said() == ["Toggle on: True -> False"]
        for other in ("a", "arrow_up", "arrow_right", "escape"):
            k.press(other)
        assert k.said() == []


def test_checkbox_space_flips_it_and_raises_on_changed_and_enter_does_nothing() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        root = k.tab_to("Remember")
        assert root.get("role") == "checkbox" and root.get("checked") is False
        k.said()
        k.press("space")
        assert root.get("checked") is True and k.said() == ["Checkbox: False -> True"]
        k.press("enter")
        assert root.get("checked") is True and k.said() == []
        k.press("space")
        assert root.get("checked") is False and k.said() == ["Checkbox: True -> False"]
        second = k.tab_to("Checked")
        assert second.get("checked") is True
        k.press("space")
        assert second.get("checked") is False and k.said() == ["Checkbox 2: True -> False"]


# -- Slider --------------------------------------------------------------------------------------


def test_slider_arrows_pages_home_and_end_step_it_and_each_step_raises_changed_then_released() -> (
    None
):
    with gallery_c() as w:
        k = Keys(w, "Controls")
        root = k.tab_to("Volume")
        assert root.get("role") == "slider"
        assert (root.get("value"), root.get("value_min"), root.get("value_max")) == (30, 0, 100)
        assert root.get("value_step") == 1
        k.said()

        def step(key: str, new: int, old: int) -> None:
            k.press(key)
            assert root.get("value") == new, (key, root.get("value"))
            assert k.said() == [
                f"Volume: {old} -> {new}",  # On_Changed, then at once On_Released
                f"Volume released at {new} (pressed at {old})",
            ]

        step("arrow_right", 31, 30)
        step("arrow_up", 32, 31)
        step("arrow_left", 31, 32)
        step("arrow_down", 30, 31)
        step("page_up", 40, 30)
        step("page_down", 30, 40)
        step("home", 0, 30)
        k.press("arrow_left")  # at Min: no step, so neither event
        k.press("arrow_down")
        k.press("page_down")
        k.press("home")
        assert root.get("value") == 0 and k.said() == []
        step("end", 100, 0)
        k.press("arrow_right")
        k.press("page_up")
        k.press("end")
        assert root.get("value") == 100 and k.said() == []
        # the handle and the fill followed
        handle = w.nodes("Handle")[0]
        assert handle.get("translate_x") > 0
        for other in ("a", "enter", "escape"):
            k.press(other)
        assert root.get("value") == 100 and k.said() == []


def test_slider_with_a_step_moves_by_it_and_an_upright_one_goes_up_with_up() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        root = k.tab_to("Stepped")
        assert (root.get("value"), root.get("value_step")) == (50, 10)
        k.said()
        k.press("arrow_right")
        assert root.get("value") == 60 and k.said()[0] == "Step 10: 50 -> 60"
        k.press("page_up")  # ten steps: past Max, so Max
        assert root.get("value") == 100 and k.said()[0] == "Step 10: 60 -> 100"
        upright = k.tab_to("Upright")
        assert upright.get("value") == 40
        k.said()
        k.press("arrow_up")
        assert upright.get("value") == 41 and k.said() == ["Upright: 40 -> 41"]  # no On_Released
        k.press("arrow_down")
        k.press("arrow_down")
        assert upright.get("value") == 39
        k.press("end")
        assert upright.get("value") == 100


def test_a_key_that_holds_ctrl_or_alt_is_not_the_sliders() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        root = k.tab_to("Volume")
        for mods in ({"ctrl": True}, {"alt": True}, {"meta": True}):
            k.press("arrow_right", **mods)
        assert root.get("value") == 30


# -- List ----------------------------------------------------------------------------------------


def test_list_arrows_home_end_and_pages_move_the_chosen_entry_and_it_scrolls_into_view() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        root = k.tab_to("Entries")
        assert root.get("role") == "listbox"
        k.said()
        k.press("arrow_down")
        assert k.said() == ["List: 'k2' -> 'k3'"]
        k.press("arrow_up")
        k.press("arrow_up")
        assert k.said() == ["List: 'k3' -> 'k2'", "List: 'k2' -> 'k1'"]
        k.press("arrow_up")  # the first entry: nowhere to go
        assert k.said() == []
        k.press("end")
        assert k.said() == ["List: 'k1' -> 'k10'"]
        assert root.get("scroll_offset") > 0  # the last entry is in view
        k.press("home")
        assert k.said() == ["List: 'k10' -> 'k1'"] and root.get("scroll_offset") == 0
        k.press("page_down")  # 150 px of 28 px entries: five at a time
        assert k.said() == ["List: 'k1' -> 'k6'"]
        k.press("page_up")
        assert k.said() == ["List: 'k6' -> 'k1'"]
        # Enter and Space choose: the entry that is chosen already stays, and nothing is raised
        k.press("enter")
        k.press("space")
        assert k.said() == []


def test_list_marks_the_chosen_entry_selected_for_assistive_technology_and_the_style() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        root = k.tab_to("Entries")
        k.press("arrow_down")

        def chosen() -> list[Any]:
            return [n for n in descendants(root) if n.get("selected") is True]

        (entry,) = chosen()
        assert entry.get("role") == "option"
        assert "Entry number 3" in " ".join(texts(entry))
        assert entry.get("stroke_width") == 2  # the ``.list_item:selected`` rule of the stylesheet
        k.press("arrow_down")
        (entry,) = chosen()
        assert "Entry number 4" in " ".join(texts(entry))


def test_a_list_that_chooses_nothing_takes_no_choice_by_key() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        k.tab_to("Plain")
        k.said()
        for key in ("arrow_down", "arrow_up", "end", "enter", "space", "a"):
            k.press(key)
        assert k.said() == []
        assert not [n for n in descendants(k.tab_to("Plain")) if n.get("selected")]


FRUIT = (
    "Module { FlexBox { Children { List { Name: L, Width: 200, Height: 100, Label: Fruit, "
    "On_Changed: changed, Children { "
    'Label { Key: ape, Text: "Apple" } Label { Key: apr, Text: "Apricot" } '
    'Label { Key: ban, Text: "Banana" } Label { Key: ber, Text: "Blueberry" } '
    'Label { Key: new, Text: "New York" } Label { Key: nev, Text: "Newark", Enabled: false } '
    "} } } } }"
)


def test_list_typing_jumps_to_the_next_entry_that_starts_with_the_letters() -> None:
    with running("Driver { }", driver=FRUIT) as w:
        k = Keys(w, "Top_Bar")
        k.tab_to("Fruit")
        chosen = w.host.loaded["Driver"].instance.seen

        def picked() -> list[str]:
            out = [x[3] for x in chosen]
            chosen.clear()
            return out

        def word(letters: str) -> None:
            for letter in letters:
                k.press("space" if letter == " " else letter)

        def later() -> None:  # a second on: the search that was going is over
            k.window.advance(1500)

        k.press("b")  # none is chosen: the first entry that starts with b
        assert picked() == ["ban"]
        k.press("b")  # the same letter again goes on round the entries that start with it
        assert picked() == ["ber"]
        k.press("b")
        assert picked() == ["ban"]
        later()
        word("a")  # a new search starts after the chosen entry, round the end
        assert picked() == ["ape"]
        word("p")  # "ap": Apple, the chosen one, starts with it
        assert picked() == []
        word("r")  # "apr"
        assert picked() == ["apr"]
        later()
        word("new")
        assert picked() == ["new"]
        # a space in a search in progress is a letter of it, so Space does not choose here
        word(" y")
        assert picked() == []
        word("a")  # "new ya": nothing starts with it, the chosen entry stays
        assert picked() == []
        later()
        word("newa")  # Newark starts with it, but it is disabled: passed over
        assert picked() == []
        later()
        word("z")
        assert picked() == []
        # with no search going, Space is Space: it chooses nothing new
        later()
        k.press("space")
        assert picked() == []


# -- Menu and MenuItem ---------------------------------------------------------------------------


def lit(op: Any) -> list[str]:
    """The text of the rows of an open menu the arrow keys are on."""
    return [_text(r.tre) for r in op.view.menu_rows() if r.wire is not None and r.wire.active]


def _text(node: Any) -> str:
    for child in node.children():
        for part in [child, *child.children()]:
            try:
                text = part.get("text")
            except ValueError:
                continue
            if text:
                return str(text)
    return ""


def test_menu_arrows_run_rows_open_submenus_and_escape_gives_the_focus_back() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        popups = w.manager.popups
        opener = k.tab_to("File")
        k.said()
        k.press("enter")  # the Button's click: the menu opens, from the keyboard
        op = popups.current
        assert op is not None and op.popup.name == "File_Menu"
        menu = next(n for n in op.view.nodes.values() if n.get("role") == "menu")
        assert menu.get("focused")  # a Menu opened from the keyboard takes the focus
        assert lit(op) == []
        # Up and Down move the lit row, over the faint "Menu for File" and "Print"
        order = [
            "New",
            "Open",
            "Share",
            "Quit",
            "New",  # round the end
        ]
        for text in order:
            k.press("arrow_down", op.window)
            assert lit(op) == [text]
        k.press("arrow_up", op.window)
        assert lit(op) == ["Quit"]
        k.press("home", op.window)
        assert lit(op) == ["New"]
        k.press("end", op.window)
        assert lit(op) == ["Quit"]
        # Enter runs the row; the menu closes and the focus goes back to the Button
        k.press("home", op.window)
        k.press("arrow_down", op.window)
        k.press("enter", op.window)
        assert k.said() == ["Open clicked"]
        assert popups.current is None
        assert k.focused() is opener and ring_on(k.view, opener, w.manager.look)
        # Space runs a row too
        k.press("enter")
        op = popups.current
        assert op is not None
        k.press("arrow_down", op.window)
        k.press("space", op.window)
        assert k.said() == ["New clicked"]
        assert popups.current is None


def test_menu_right_opens_a_submenu_left_and_escape_close_the_innermost_level() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        popups = w.manager.popups
        opener = k.tab_to("File")
        k.press("enter")
        root = popups.current
        assert root is not None
        for _ in range(3):  # New, Open, Share
            k.press("arrow_down", root.window)
        assert lit(root) == ["Share"]
        share_row = root.view.marked_row()
        assert share_row is not None and share_row.tre.get("expanded") is False
        k.press("arrow_right", root.window)
        sub = popups.current.sub
        assert sub is not None and sub.popup.name == "Share_Menu"
        assert share_row.tre.get("expanded") is True  # ``expanded`` on an item with a submenu
        assert lit(sub) == ["Mail"]  # the submenu takes the keys and lights its first row
        menu = next(n for n in sub.view.nodes.values() if n.get("role") == "menu")
        assert menu.get("focused")
        k.press("arrow_down", sub.window)
        k.press("arrow_down", sub.window)
        assert lit(sub) == ["More"]
        k.press("arrow_right", sub.window)  # a third level
        deep = sub.sub
        assert deep is not None and deep.popup.name == "More_Menu" and lit(deep) == ["Deep one"]
        k.press("arrow_left", deep.window)  # Left closes the innermost level only
        assert sub.sub is None and not sub.closing and not root.closing
        k.press("arrow_right", sub.window)
        assert sub.sub is not None
        k.press("escape", sub.sub.window)  # Escape closes the innermost level too
        assert sub.sub is None and popups.current is root and root.sub is sub
        k.press("arrow_left", sub.window)
        assert root.sub is None and popups.current is root
        assert share_row.tre.get("expanded") is False
        k.press("arrow_left", root.window)  # Left on the root does nothing
        assert popups.current is root
        # Enter on a row with a submenu opens it as Right does
        k.press("enter", root.window)
        assert root.sub is not None and lit(root.sub) == ["Mail"]
        # a row of the submenu runs and every level closes
        k.press("arrow_down", root.sub.window)
        k.press("enter", root.sub.window)
        assert k.said()[-1] == "Chat clicked"
        assert popups.current is None
        assert k.focused() is opener


def test_menu_escape_on_the_root_closes_it_and_returns_the_focus_to_the_opener() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        popups = w.manager.popups
        opener = k.tab_to("File")
        k.press("enter")
        op = popups.current
        assert op is not None
        k.press("arrow_down", op.window)
        k.press("escape", op.window)
        assert popups.current is None and k.said() == []
        assert k.focused() is opener and ring_on(k.view, opener, w.manager.look)
        # the Edit menu is a Toggle from its Button: the same keys
        k.tab_to("Edit")
        k.press("space")
        edit = popups.current
        assert edit is not None and edit.popup.name == "Edit_Menu"
        for text in ("Cut", "Copy", "Paste", "Cut"):
            k.press("arrow_down", edit.window)
            assert lit(edit) == [text]
        k.press("enter", edit.window)
        assert k.said() == ["Cut clicked"]


def test_the_pointer_on_a_row_takes_the_light_from_the_keys_and_a_disabled_row_is_passed_over() -> (
    None
):
    with gallery_c() as w:
        k = Keys(w, "Lists")
        k.tab_to("File")
        k.press("enter")
        op = w.manager.popups.current
        assert op is not None
        k.press("arrow_down", op.window)
        assert lit(op) == ["New"]
        rows = op.view.menu_rows()
        assert [_text(r.tre) for r in rows] == ["New", "Open", "Share", "Quit"]  # no "Print"
        open_row = rows[1]
        op.window.simulate("pointer_enter", node=open_row.tre)
        assert lit(op) == []  # the keys' row gave way to the pointer's
        k.press("arrow_down", op.window)  # and the keys go on from where the pointer is
        assert lit(op) == ["Share"]


def test_a_popup_with_no_menu_in_it_ignores_menu_keys() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        k.tab_to("File")
        k.press("enter")
        op = w.manager.popups.current
        assert op is not None
        # a key with Ctrl is not the menu's; Space on no lit row runs nothing
        k.press("arrow_down", op.window, ctrl=True)
        assert lit(op) == []
        k.press("space", op.window)
        k.press("enter", op.window)
        assert k.said() == [] and w.manager.popups.current is op


# -- TextInput and TextEditor --------------------------------------------------------------------


def field_node(k: Keys, name: str) -> Any:
    """The text input of the field the call ``name`` made (the one with a caret that takes the
    focus: a multi-line field has a line-number input beside it)."""
    found = [
        n for key, n in k.view.nodes.items() if name in key and _is_input(n) and n.get("focusable")
    ]
    assert len(found) == 1, found
    return found[0]


def _is_input(node: Any) -> bool:
    try:
        node.get("selection")
    except ValueError:  # tre: only a text input has a selection
        return False
    return True


def test_textinput_typing_arrows_selection_enter_and_tab_reach_the_module() -> None:
    with gallery_a() as w:
        k = Keys(w, "Fields")
        k.tab_to("In_Normal")
        field = field_node(k, "In_Normal")
        assert field.get("focused") and field.get("text") == "hello"
        k.said("Echo")
        k.press("end")
        k.type("!")  # tre raises the commit first and then the change: the module hears both
        assert field.get("text") == "hello!"
        assert k.said("Echo") == ["commit: '!'", "changed: 'hello' -> 'hello!'"]
        k.press("arrow_left")
        k.press("backspace")  # one character before the caret
        assert field.get("text") == "hell!"
        assert k.said("Echo") == ["changed: 'hello!' -> 'hell!'"]
        k.press("home")
        assert field.get("selection") == (0, 0)
        k.press("arrow_right", shift=True)
        k.press("arrow_right", shift=True)
        assert field.get("selection") == (0, 2)  # Shift selects
        k.press("end", shift=True)
        assert field.get("selection") == (0, 5)
        k.press("arrow_left")  # an arrow ends the selection
        assert field.get("selection")[0] == field.get("selection")[1]
        k.press("a", ctrl=True)  # Ctrl+A selects it all; typing replaces it
        assert field.get("selection") == (0, 5)
        k.type("x")
        assert field.get("text") == "x"
        assert k.said("Echo") == ["commit: 'x'", "changed: 'hell!' -> 'x'"]
        k.press("delete")  # at the end: nothing to delete, nothing said
        assert k.said("Echo") == []
        # Enter submits: the module hears it, and the text is not touched
        k.press("enter")
        assert k.said("Echo") == ["submit (Enter)"] and field.get("text") == "x"
        # Tab leaves the field: the next stop (the field with a hint) has the focus, no tab typed
        k.press("tab")
        assert not field.get("focused") and "Search..." in k.name_of()  # named by its placeholder
        assert field.get("text") == "x"
        k.press("tab", shift=True)
        assert field.get("focused")


def test_a_read_only_or_disabled_textinput_takes_no_edit_and_no_focus() -> None:
    with gallery_a() as w:
        k = Keys(w, "Fields")
        stops = k.view.tab_stops()
        ids = [key for key, n in k.view.nodes.items() if n in stops]
        assert any("In_Read" in i for i in ids) and not any("In_Off" in i for i in ids)  # no stop
        k.tab_to("In_Read")
        field = field_node(k, "In_Read")
        k.said("Echo")
        k.type("x")
        k.press("backspace")
        assert field.get("text") == "read only text" and k.said("Echo") == []
        k.press("a", ctrl=True)  # it can be selected
        assert field.get("selection") == (0, len("read only text"))
        k.press("enter")  # and Enter submits nothing: this field has no On_Submit
        assert k.said("Echo") == []


def test_texteditor_enter_inserts_a_newline_and_raises_on_changed_and_no_submit() -> None:
    with gallery_a() as w:
        k = Keys(w, "Fields")
        k.tab_to("Ed_Word")
        field = field_node(k, "Ed_Word")
        assert field.get("focused")
        text = str(field.get("text"))
        k.said("Echo")
        k.press("end", ctrl=True)  # to the end of the whole text
        k.press("enter")
        assert field.get("text") == text + "\n"
        (line,) = k.said("Echo")
        assert line.startswith("changed: ")  # the Echo module cuts the text it shows
        k.type("ok")
        assert str(field.get("text")).endswith("\nok")
        # the arrow keys move inside it and Home goes to the start of the row
        k.press("arrow_left")
        k.press("arrow_left")
        k.press("a", ctrl=True)
        assert field.get("selection") == (0, len(str(field.get("text"))))


def test_texteditor_tab_leaves_the_field() -> None:
    with gallery_a() as w:
        k = Keys(w, "Fields")
        k.tab_to("Ed_Word")
        field = field_node(k, "Ed_Word")
        text = str(field.get("text"))
        k.press("tab")
        assert not field.get("focused")
        assert field.get("text") == text  # and no tab character was typed


# -- Expander ------------------------------------------------------------------------------------


def test_expander_enter_and_space_on_its_button_toggle_it_and_the_button_says_expanded() -> None:
    with gallery_b() as w:
        k = Keys(w, "Gallery")
        button = k.tab_to("Open / close")
        assert button.get("role") == "button" and button.get("expanded") is False
        fold = w.of_use("Expander", "Root")
        said = w.of_use("Toggler", "Said")
        assert fold.get("layout_height") == 0 and "nothing yet" in said.get("text")
        k.press("enter")
        k.settle()
        assert button.get("expanded") is True and fold.get("layout_height") > 0
        assert said.get("text") == "On_Changed: finished opening"
        k.press("space")
        k.settle()
        assert button.get("expanded") is False and fold.get("layout_height") == 0
        assert said.get("text") == "On_Changed: finished closing"
        # no other key toggles it
        for other in ("a", "arrow_down", "escape"):
            k.press(other)
        k.settle()
        assert button.get("expanded") is False and fold.get("layout_height") == 0
        k.press("enter")
        k.settle()
        assert button.get("expanded") is True and said.get("text") == "On_Changed: finished opening"


def test_a_button_that_does_not_control_an_expander_says_nothing_about_expanded() -> None:
    with gallery_c() as w:
        k = Keys(w, "Controls")
        assert k.tab_to("Save").get("expanded") is None


# -- what a rebuild and a value from the module do to the keys ----------------------------------

ROSTER = (
    "Module { FlexBox { Children { List { Label: Roster, On_Changed: changed, Children { "
    "For it In <| items |> Key <| it |> { Label { Text: <| it |> } } } } } } }"
)
ROSTER_PY = (
    "from tess_shell import Module, action\n"
    "class Driver(Module):\n"
    "    def __init__(self):\n"
    "        self.seen = []\n"
    "    def start(self):\n"
    "        self.ctx.send('items', ['a', 'b', 'c'])\n"
    "    @action\n"
    "    def changed(self, event):\n"
    "        self.seen.append(('changed', event.use, event.old, event.new, event.value))\n"
)


def test_a_list_keeps_its_keys_when_its_entries_change_and_goes_on_from_the_chosen_one() -> None:
    with running("Driver { }", driver=ROSTER, driver_py=ROSTER_PY) as w:
        k = Keys(w, "Top_Bar")
        seen = w.host.loaded["Driver"].instance.seen

        def picked() -> list[str]:
            out = [x[3] for x in seen]
            seen.clear()
            return out

        k.tab_to("Roster")
        k.press("arrow_down")
        assert picked() == ["a"]
        w.send("items", ["x", "a", "b", "c"])  # a new entry in front: the chosen one is still a
        k.press("arrow_down")
        assert picked() == ["b"]
        w.send("items", ["c", "b", "a"])  # reordered: b is chosen and a follows it
        k.press("arrow_down")
        assert picked() == ["a"]
        k.press("arrow_down")  # the last one
        k.press("arrow_up")
        assert picked() == ["b"]
        w.send("items", ["c", "a"])  # the chosen entry is gone: Down starts at the first again
        k.press("arrow_down")
        assert picked() == ["c"]


SLIDING = (
    "Module { FlexBox { Children { Slider { Label: S, Value: <| v |>, On_Changed: changed } } } }"
)
SLIDING_PY = ROSTER_PY.replace("'items', ['a', 'b', 'c']", "'v', 10")


def test_a_sliders_keys_start_from_the_value_the_module_sent_and_the_users_step_stays() -> None:
    with running("Driver { }", driver=SLIDING, driver_py=SLIDING_PY) as w:
        k = Keys(w, "Top_Bar")
        root = k.tab_to("S")
        seen = w.host.loaded["Driver"].instance.seen
        k.press("arrow_right")
        assert root.get("value") == 11 and [x[2:4] for x in seen] == [(10, 11)]
        w.send("v", 10)  # the module sends the value it sent before: the user's step stays
        assert root.get("value") == 11
        w.send("v", 40)  # a different one moves it, and raises nothing
        assert root.get("value") == 40 and len(seen) == 1
        k.press("arrow_right")
        assert root.get("value") == 41 and [x[2:4] for x in seen][-1] == (40, 41)


def test_a_menu_opened_by_a_click_takes_the_keys_too_and_escape_leaves_the_focus_alone() -> None:
    with gallery_c() as w:
        k = Keys(w, "Lists")
        popups = w.manager.popups
        opener = next(
            n
            for key, n in k.view.nodes.items()
            if key.endswith("/Root") and n.get("label") == "File"
        )
        k.window.simulate("click", node=opener)  # the pointer opens it: no ring, no focus in it
        op = popups.current
        assert op is not None
        assert not any(n.get("focused") for n in op.view.nodes.values())
        k.press("arrow_down", op.window)
        k.press("arrow_down", op.window)
        assert lit(op) == ["Open"]
        k.press("enter", op.window)
        assert k.said() == ["Open clicked"] and popups.current is None
        k.window.simulate("click", node=opener)
        op = popups.current
        assert op is not None
        k.press("escape", op.window)
        assert popups.current is None and k.said() == []
