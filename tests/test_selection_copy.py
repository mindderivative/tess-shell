"""Ctrl+C on a selectable Text (Text Selection, AC-SEL-1, AC-SEL-4)."""

from __future__ import annotations

from types import SimpleNamespace

import tess_re

from tess_shell.surfaces.selection_copy import copy_selection, selected_text


def build() -> tuple[tess_re.Window, list[tess_re.Node]]:
    window = tess_re.Window(300, 200)
    texts = [
        window.create("text", text=s, selectable=True)
        for s in ("hello world", "second line", "héllo")
    ]
    for t in texts:
        window.root.add_child(t)
    window.snapshot()
    return window, texts


class Surface:
    """The window with a clipboard that remembers what was written (a headless one has none)."""

    def __init__(self, window: tess_re.Window, sent: list[str]) -> None:
        self.root = window.root
        self._sent = sent

    def write_clipboard(self, text: str) -> bool:
        self._sent.append(text)
        return True


def key(char: str = "c", **mods: bool) -> SimpleNamespace:
    return SimpleNamespace(key=char, ctrl=mods.pop("ctrl", True), **mods)


def test_the_selection_is_in_bytes_and_one_text_holds_it() -> None:
    window, (a, b, c) = build()
    c.set(selection=(0, 3))  # "hé" is three bytes
    assert selected_text(window.root) == "hé"
    a.set(selection=(2, 8))  # selecting in another text moves it there
    assert selected_text(window.root) == "llo wo"
    assert b.get("selection") is None and c.get("selection") is None


def test_nothing_is_copied_without_a_selection_or_with_another_key() -> None:
    window, (a, _b, _c) = build()
    sent: list[str] = []
    window = Surface(window, sent)
    assert copy_selection(window, key()) is False  # nothing selected
    a.set(selection=(0, 5))
    assert copy_selection(window, key("x")) is False
    assert copy_selection(window, key(ctrl=False)) is False
    assert copy_selection(window, key(shift=True)) is False  # Ctrl+Shift+C is not copy
    assert sent == []


def test_ctrl_c_puts_exactly_the_selected_substring_on_the_clipboard() -> None:
    window, (a, _b, _c) = build()
    sent: list[str] = []
    window = Surface(window, sent)
    a.set(selection=(2, 8))
    assert copy_selection(window, key()) is True
    assert sent == ["llo wo"]


def test_a_focused_text_input_keeps_its_own_copy() -> None:
    window, (a, _b, _c) = build()
    box = window.create("text_input", text="abc")
    window.root.add_child(box)
    window.snapshot()
    box.focus()
    a.set(selection=(0, 5))
    sent: list[str] = []
    window = Surface(window, sent)
    assert copy_selection(window, key()) is False and sent == []
