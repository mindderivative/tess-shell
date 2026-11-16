"""``On_Key_Down`` of a text field (Standard Modules > Keyboard Operation; Applications Module >
Needs from the Shell): a module hears each key that goes down in its TextInput, with the key's name
and the modifiers held, and its ``event.stop()`` keeps the key from the surface above (a Panel's
Escape, the keys of shortcut mode). The field does what it does with the key whatever the module
does: the key arrives before the field acts and cannot be vetoed. ``simulate`` is the keyboard; no
compositor."""

from __future__ import annotations

from typing import Any

from tess_shell.module import Event
from tests.field_live import Fields, running

PAD_TDL = (
    "---\nTDL: 0.2\nName: Pad\n---\n"
    "Module { FlexBox { Children { "
    'TextInput { Name: field, Text: "abc", On_Key_Down: pressed } } } }'
)
PAD_PY = """
from tess_shell import Module, action

class Pad(Module):
    def __init__(self):
        self.seen = []
        self.stop_keys = set()

    @action
    def pressed(self, event):
        self.seen.append((event.key, event.ctrl, event.shift, event.alt, event.meta, event.repeat))
        if event.key in self.stop_keys:
            event.stop()
"""
BAR = "Pad { Name: P }"


def pad(r: Fields) -> Any:
    return r.host.loaded["Pad"].instance


def run() -> Any:
    return running(BAR, extra={"Pad": PAD_TDL}, extra_code={"Pad": PAD_PY})


def field(r: Fields) -> Any:
    found = [f for f in r.fields()]
    assert len(found) == 1
    return found[0]


def click(r: Fields, node: Any) -> None:
    r.window.simulate("pointer_down", node=node)
    r.window.simulate("pointer_up", node=node)


def test_the_module_hears_the_key_before_the_field_acts_on_it() -> None:
    probe = PAD_PY.replace(
        "self.seen.append((event.key,", "self.seen.append((self.inp.get('text'), event.key,"
    ).replace("self.stop_keys = set()", "self.stop_keys = set()\n        self.inp = None")
    with running(BAR, extra={"Pad": PAD_TDL}, extra_code={"Pad": probe}) as r:
        inp = field(r).inp
        pad(r).inp = inp
        click(r, inp)
        inp.set(selection=(3, 3))
        r.window.simulate("key_down", key="backspace")
        assert pad(r).seen[0][:2] == ("abc", "backspace")  # the text as it was
        assert inp.get("text") == "ab"  # and then the field acted


def test_a_module_hears_every_key_with_its_name_and_the_modifiers_held() -> None:
    with run() as r:
        assert r.problems == [], r.problems
        click(r, field(r).inp)
        for key, mods in (
            ("arrow_down", {}),
            ("a", {}),
            ("escape", {}),
            ("page_up", {"shift": True}),
            ("arrow_up", {"ctrl": True, "alt": True}),
            ("f", {"meta": True}),
        ):
            r.window.simulate("key_down", key=key, **mods)
        assert pad(r).seen == [
            ("arrow_down", False, False, False, False, False),
            ("a", False, False, False, False, False),
            ("escape", False, False, False, False, False),
            ("page_up", False, True, False, False, False),
            ("arrow_up", True, False, True, False, False),
            ("f", False, False, False, True, False),
        ]


def test_the_field_acts_on_a_key_whatever_the_module_does_with_it() -> None:
    with run() as r:
        click(r, field(r).inp)
        pad(r).stop_keys = {"backspace", "home"}  # the module uses them: the field still acts
        inp = field(r).inp
        inp.set(selection=(3, 3))
        r.window.simulate("key_down", key="backspace")
        assert inp.get("text") == "ab"  # not vetoed
        r.window.simulate("key_down", key="home")
        assert inp.get("selection") == (0, 0)
        assert [k[0] for k in pad(r).seen] == ["backspace", "home"]


def test_stop_keeps_a_key_from_the_surface_above_and_a_key_not_stopped_goes_on() -> None:
    with run() as r:
        reached: list[str] = []
        # the Bar's window root: where a surface hears the keys that bubble up from its blocks
        # (the manager's own listener there is the mode's; ours replaces nothing it needs)
        click(r, field(r).inp)
        pad(r).stop_keys = {"escape"}
        root = r.window.root
        root.on("key_down", lambda e: reached.append(e.key))
        r.window.simulate("key_down", key="escape")
        r.window.simulate("key_down", key="arrow_down")
        assert reached == ["arrow_down"]  # Escape was stopped by the module, the arrow went on
        assert [k[0] for k in pad(r).seen] == ["escape", "arrow_down"]


def test_an_event_that_has_no_tre_event_behind_it_stops_nothing_and_raises_nothing() -> None:
    event = Event("key_down", "Pad@x", key="a")
    event.stop()  # a call from a test or a control command carries no event to stop
    assert event.key == "a" and not (event.ctrl or event.shift or event.alt or event.meta)
