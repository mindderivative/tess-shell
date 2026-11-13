"""``On_Secondary_Click`` and ``On_Scroll`` (Events and Actions): the schema, the loader, the
binder's listeners on a headless tre window and the module host's ``Event`` (``button``,
``delta``)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import tess_dl
from tess_re import Window

from tess_shell.binder.build import View, build
from tess_shell.binder.model import Bool, Handler, Length, Node
from tess_shell.model.args import event_record
from tess_shell.schema import blocks, docs
from tess_shell.schema.findings import Finding
from tess_shell.schema.shell import read_module
from tests.test_events import ACTION_PY, host_module
from tests.test_module_host import Rig

HEAD = "---\nTDL: 0.1\nName: Btn\n---\n"
KEYS = ("On_Click", "On_Secondary_Click", "On_Scroll")


def module_findings(body: str) -> tuple[bool, list[Finding]]:
    result = tess_dl.parse(HEAD + body, path="Modules/Btn_Module.tdl")
    assert result.document is not None
    found, findings = read_module(result.document, "Modules/Btn_Module.tdl")
    return found is not None, [f for f in findings if f.severity == "error"]


def node(name: str, *keys: str, children: tuple[Node, ...] = (), enabled: bool = True) -> Node:
    side = 40 + 40 * bool(children)  # a parent is larger than its child: both can be aimed at
    props: dict[str, object] = {"Width": Length(side), "Height": Length(side)}
    if not enabled:
        props["Enabled"] = Bool(False)
    return Node(
        "FlexBox",
        name=name,
        props=props,  # type: ignore[arg-type]
        handlers={k: Handler(f"{name}:{k}", use="B@1") for k in keys},
        children=children,
    )


def rig(*nodes: Node) -> tuple[Window, View, list[tuple[str, str, object]]]:
    window = Window(width=200, height=100)
    seen: list[tuple[str, str, object]] = []
    view = build(list(nodes), window)
    view.sink = lambda h, key, raw: seen.append((h.action, key, raw))
    return window, view, seen


# -- schema and loader --------------------------------------------------------------------------


def test_the_keys_are_declared_documented_and_raised_wherever_on_click_is() -> None:
    for key in KEYS[1:]:
        assert key in blocks.EVENT_KEYS and docs.EVENT_DOCS[key]
    for kind, events in blocks.BLOCK_EVENTS.items():
        if "On_Click" in events:
            assert all(k in events for k in KEYS), kind
    assert "delta" in docs.EVENT_DOCS["On_Scroll"] and "+1" in docs.EVENT_DOCS["On_Scroll"]
    assert "secondary" in docs.EVENT_DOCS["On_Secondary_Click"]


@pytest.mark.parametrize("key", KEYS[1:])
def test_a_module_layout_accepts_the_keys_on_a_box(key: str) -> None:
    ok, errors = module_findings("Module { Rectangle { Width: 4, Height: 4, " + key + ": go } }")
    assert ok and errors == []
    ok, errors = module_findings(
        "Module { FlexBox { " + key + " { Action: step, delta: {{ event.delta }} } } }"
    )
    assert ok and errors == []


@pytest.mark.parametrize("key", KEYS[1:])
def test_a_text_raises_neither_and_the_error_says_where_to_put_the_handler(key: str) -> None:
    ok, errors = module_findings('Module { Text { Text: "x", ' + key + ": go } }")
    assert not ok
    (f,) = errors
    assert f.rule == "event-not-raised" and "FlexBox or Box around it" in f.hint


def test_the_delta_slot_is_checked_and_read_from_the_event_record() -> None:
    assert event_record("On_Scroll", SimpleNamespace(delta=-1.0))["delta"] == -1.0
    assert event_record("On_Scroll", SimpleNamespace(delta=1.0))["name"] == "scroll"
    assert event_record("On_Secondary_Click", SimpleNamespace(button="secondary")) == {
        "name": "secondary_click",
        "button": "secondary",
    }
    assert "delta" not in event_record("On_Click", SimpleNamespace())


# -- binder: headless tre ------------------------------------------------------------------------


def test_scroll_down_is_plus_one_and_up_is_minus_one() -> None:
    window, view, seen = rig(node("A", "On_Scroll"))
    window.simulate("wheel", node=view.nodes["A"], delta_y=120.0)
    window.simulate("wheel", node=view.nodes["A"], delta_y=-3.0)
    window.simulate("wheel", node=view.nodes["A"], delta_y=0.0, delta_x=5.0)  # sideways: nothing
    assert [(a, k, r.delta) for a, k, r in seen] == [  # type: ignore[attr-defined]
        ("A:On_Scroll", "On_Scroll", 1.0),
        ("A:On_Scroll", "On_Scroll", -1.0),
    ]


def test_a_secondary_click_runs_its_handler_and_not_on_click() -> None:
    window, view, seen = rig(node("A", *KEYS))
    window.simulate("secondary_click", node=view.nodes["A"])
    assert [(a, k) for a, k, _ in seen] == [("A:On_Secondary_Click", "On_Secondary_Click")]
    assert seen[0][2].button == "secondary"  # type: ignore[attr-defined]


def test_a_primary_click_runs_on_click_and_not_the_secondary_handler() -> None:
    window, view, seen = rig(node("A", *KEYS))
    window.simulate("click", node=view.nodes["A"])
    assert [(a, k) for a, k, _ in seen] == [("A:On_Click", "On_Click")]


def test_a_secondary_click_does_not_reach_an_ancestors_on_click() -> None:
    inner = node("Inner", "On_Secondary_Click")
    window, view, seen = rig(node("Outer", "On_Click", children=(inner,)))
    window.simulate("secondary_click", node=view.nodes["Inner"])
    assert [k for _, k, _ in seen] == ["On_Secondary_Click"]


def test_a_disabled_block_raises_neither_and_swallows_them_from_above() -> None:
    inner = node("Inner", *KEYS, enabled=False)
    window, view, seen = rig(node("Outer", *KEYS, children=(inner,)))
    window.simulate("secondary_click", node=view.nodes["Inner"])
    window.simulate("wheel", node=view.nodes["Inner"], delta_y=10.0)
    assert seen == []
    window.simulate("wheel", node=view.nodes["Outer"], delta_y=10.0)
    assert [k for _, k, _ in seen] == ["On_Scroll"]  # the enabled box still takes its own


def test_a_disabled_block_without_handlers_swallows_a_wheel_meant_for_an_ancestor() -> None:
    inner = node("Inner", enabled=False)
    window, view, seen = rig(node("Outer", "On_Scroll", children=(inner,)))
    window.simulate("wheel", node=view.nodes["Inner"], delta_y=10.0)
    assert seen == []


def test_an_ancestor_with_the_handler_hears_a_wheel_over_a_child_without_one() -> None:
    window, view, seen = rig(node("Outer", "On_Scroll", children=(node("Inner"),)))
    window.simulate("wheel", node=view.nodes["Inner"], delta_y=10.0)
    assert [(a, k) for a, k, _ in seen] == [("Outer:On_Scroll", "On_Scroll")]


def test_the_nearest_block_with_the_handler_takes_the_wheel_alone() -> None:
    inner = node("Inner", "On_Scroll")
    window, view, seen = rig(node("Outer", "On_Scroll", children=(inner,)))
    window.simulate("wheel", node=view.nodes["Inner"], delta_y=-10.0)
    assert [a for a, _, _ in seen] == ["Inner:On_Scroll"]


def test_a_reload_swaps_the_handler_and_a_dropped_one_stops_nothing() -> None:
    inner = node("Inner")
    window, view, seen = rig(node("Outer", "On_Scroll", children=(node("Inner", "On_Scroll"),)))
    view.rebuild([node("Outer", "On_Scroll", children=(inner,))])
    window.simulate("wheel", node=view.nodes["Inner"], delta_y=1.0)
    assert [a for a, _, _ in seen] == ["Outer:On_Scroll"]  # Inner's listener let it bubble


# -- module host --------------------------------------------------------------------------------

STEP = """@action
    def step(self, event, delta=0):
        self.seen.append((event, delta))

"""


def test_the_action_receives_delta_and_button(tmp_path: Path) -> None:
    code = ACTION_PY.replace("clicks = []", "clicks = []\n    seen = []").replace(
        "def helper", STEP + "    def helper"
    )
    r = Rig(tmp_path)
    (loaded, findings), _, u = host_module(
        r, "On_Scroll { Action: step, delta: {{ event.delta }} }", code
    )
    assert loaded is not None and findings == []
    r.host.start(loaded)
    window = Window(width=100, height=40)
    box = Node(
        "Rectangle",
        name="T",
        props={"Width": Length(10), "Height": Length(10)},
        handlers={
            "On_Scroll": Handler("step", {"delta": 7}, use=u.key),
            "On_Secondary_Click": Handler("step", use=u.key),
        },
    )
    view = build([box], window)
    view.sink = r.host.dispatch
    window.simulate("wheel", node=view.nodes["T"], delta_y=40.0)
    window.simulate("wheel", node=view.nodes["T"], delta_y=-40.0)
    window.simulate("secondary_click", node=view.nodes["T"])
    events = [e for e, _ in getattr(loaded.instance, "seen")]  # noqa: B009
    scroll_down, scroll_up, secondary = events
    assert (scroll_down.name, scroll_down.delta, scroll_down.button) == ("scroll", 1.0, None)
    assert (scroll_up.delta, scroll_up.name) == (-1.0, "scroll")
    assert (secondary.name, secondary.button, secondary.delta) == (
        "secondary_click",
        "secondary",
        None,
    )
