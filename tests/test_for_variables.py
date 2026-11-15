"""``For i, item In <| enumerate(items) |> Key <| item.id |> { ... }``: several loop variables
unpack each item of the list (TEL binds the names); every reader of a loop variable (a slot, a
``Key``, a handler argument, a Popup's content) sees all of them."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from tess_shell.cli import main
from tests.test_call import running as call_rig
from tests.test_model_structure import Rig, items
from tests.test_module_in_popup import (
    DRIVER,
    DRIVER_PY,
    POPUPS,
    TRAY_PY,
    labels,
    open_popup,
    quiet,
)
from tests.widgets_live import running as widgets_rig

PAIRS = """
Module {
    FlexBox {
        Name: Row
        Children {
            For i, w In <| enumerate(items) |> Key <| w.id |> {
                Text { Text: <| str(i) + ": " + w.title |> }
            }
        }
    }
}
"""


def test_both_names_are_readable_in_a_slot() -> None:
    rig = Rig(PAIRS)
    rig.send_many(items=items((1, "a"), (2, "b"), (3, "c")))
    assert rig.texts() == ["0: a", "1: b", "2: c"]


def test_the_key_may_use_either_name() -> None:
    by_index = PAIRS.replace("Key <| w.id |>", "Key <| i |>")
    rig = Rig(by_index)
    rig.send_many(items=items((1, "a"), (2, "b")))
    first, second = rig.row()
    rig.send_many(items=items((1, "a"), (2, "B"), (3, "c")))
    assert rig.row()[:2] == [first, second]  # the same nodes: the key is the position
    assert rig.texts() == ["0: a", "1: B", "2: c"]


def test_reorder_add_and_remove_keep_the_nodes_by_key() -> None:
    rig = Rig(PAIRS)
    rig.send_many(items=items((1, "a"), (2, "b"), (3, "c")))
    a, b, c = rig.row()
    rig.spy.builds = 0
    rig.send_many(items=items((3, "c"), (1, "a"), (2, "b")))
    assert rig.row() == [c, a, b] and rig.spy.builds == 0
    assert rig.texts() == ["0: c", "1: a", "2: b"]  # the index follows the new place
    rig.send_many(items=items((3, "c"), (2, "b")))
    assert rig.row() == [c, b] and rig.texts() == ["0: c", "1: b"]
    rig.send_many(items=items((3, "c"), (2, "b"), (4, "d")))
    assert rig.row()[:2] == [c, b] and rig.texts()[-1] == "2: d"


def test_a_for_inside_a_for_with_other_names() -> None:
    nested = """
Module {
    FlexBox {
        Name: Row
        Children {
            For i, w In <| enumerate(items) |> Key <| w.id |> {
                For j, tag In <| enumerate(w.tags) |> Key <| str(w.id) + tag |> {
                    Text { Text: <| str(i) + "." + str(j) + " " + tag + " of " + w.title |> }
                }
            }
        }
    }
}
"""
    rig = Rig(nested)
    rig.send_many(
        items=[{"id": 1, "title": "a", "tags": ["x", "y"]}, {"id": 2, "title": "b", "tags": ["z"]}]
    )
    assert rig.texts() == ["0.0 x of a", "0.1 y of a", "1.0 z of b"]


def test_an_item_that_is_not_a_pair_is_reported_at_its_place_and_the_surface_goes_on() -> None:
    lines: list[str] = []
    sink = logger.add(lambda message: lines.append(str(message)), level="WARNING")
    try:
        rig = Rig(PAIRS.replace("enumerate(items)", "items"))
        rig.send_many(items=items((1, "a")))  # a dict is no pair
        assert rig.live.errors >= 1 and rig.texts() == []
        rig.send_many(items=[[0, {"id": 1, "title": "a"}]])  # a pair is
        assert rig.texts() == ["0: a"]
    finally:
        logger.remove(sink)
    reported = [x for x in lines if "each item must be a list or tuple" in x]
    assert reported, lines
    assert re.search(r"Todo_Module\.tdl:10:\d+: ", reported[0]), reported[0]  # the For's own line


def test_a_handler_argument_slot_reads_both_names(tmp_path: Path) -> None:
    layouts = {
        "Btn": "Module { FlexBox { Name: Root, Flex: VERTICAL, Children {\n"
        "For i, item In <| enumerate(items) |> Key <| item.id |> {\n"
        'FlexBox { Width: 40, Height: 10, On_Click { Action: Call, Target: "Btn.picked", '
        "Index: <| i |>, Id: <| item.id |> } }\n} } } }"
    }
    r = call_rig(tmp_path, layouts=layouts)
    r.store.send("Btn", r.uses[0], "items", [{"id": 4}, {"id": 9}])
    r.manager.on_change(r.store.flush())
    entries = sorted(n for n in r.bar.view.nodes if n.startswith("for"))
    assert len(entries) == 2, list(r.bar.view.nodes)
    for node_id in entries:
        r.click(node_id)
    assert [a for _, a in r.action_seen()] == [{"Index": 0, "Id": 4}, {"Index": 1, "Id": 9}]


TRAY_TDL = (
    "---\nTDL: 0.2\nName: TrayMenu\n---\n"
    "Module { FlexBox { Name: Root, Flex: VERTICAL, Children { "
    "Menu { Children { "
    "For i, e In <| enumerate(caller.data.items) |> Key <| e.id |> { "
    'MenuItem { Text: <| str(i + 1) + ". " + e.text |>, '
    "On_Click { Action: pick, Id: <| e.id |>, Index: <| i |> } } } "
    "} } } } }\n"
)


def go() -> Any:
    return widgets_rig(
        "Driver { }",
        driver=DRIVER,
        driver_py=DRIVER_PY,
        extra={"TrayMenu": TRAY_TDL},
        extra_py={"TrayMenu": TRAY_PY},
        popups=POPUPS,
    )


def test_a_popup_for_with_two_names() -> None:
    with go() as w:
        assert quiet(w) == [] and w.problems == []
        op = open_popup(w)
        assert labels(op) == ["1. Alpha", "2. Beta"]
        beta = [n for n in op.view.nodes.values() if n.get("label") == "2. Beta"][0]
        op.window.simulate("click", node=beta)
        chosen = w.host.loaded["TrayMenu"].instance.picked
        assert [c[1] for c in chosen] == [{"Id": "b", "Index": 1}]


def test_a_bad_variable_name_is_refused_by_the_language_through_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "Modules" / "Clock" / "Clock_Module.tdl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nTDL: 0.2\nName: Clock\n---\nModule { Box { Children {\n"
        "For i, _b In <| xs |> Key <| i |> { Text { } } } } }\n"
    )
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    (error,) = json.loads(capsys.readouterr().out)["errors"]
    assert error["message"] == "A For needs a variable name." and error["line"] == 6
    assert error["file"] == "Modules/Clock/Clock_Module.tdl" and error["column"] > 0


def test_a_duplicate_name_is_the_languages_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "Modules" / "Clock" / "Clock_Module.tdl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nTDL: 0.2\nName: Clock\n---\nModule { Box { Children {\n"
        "For i, i In <| xs |> Key <| i |> { Text { } } } } }\n"
    )
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    (error,) = json.loads(capsys.readouterr().out)["errors"]
    assert error["rule"] == "tdl-duplicate-variable" and error["line"] == 6
