"""The preview model (``tess_shell.preview``): what the shell would show for a configuration, as
plain data, from the shell's own pipeline, with no window and with files held in memory."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tess_shell.config import overlay
from tess_shell.preview import PREVIEW_VERSION, VirtualOutput, describe, preview
from tests.preview_golden import CONFIG, GOLDEN, RICH, example, model, rich
from tests.shell_samples import BODY, HEADER, write_example

SHELL = CONFIG / "Shells" / "Main_Shell.tdl"


def surfaces(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["name"]: s for s in data["surfaces"]}


def test_the_model_of_the_example_and_of_a_rich_configuration_is_the_golden_data() -> None:
    """A change of the model's shape is deliberate: ``python -m tests.preview_golden`` and a
    ``PREVIEW_VERSION`` bump when a key is changed or removed."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert golden["example"]["preview_version"] == PREVIEW_VERSION
    assert model(example()) == golden["example"]
    assert model(rich()) == golden["rich"]


def test_the_model_is_plain_data_and_the_same_every_time() -> None:
    first = model(rich())
    assert json.loads(json.dumps(first)) == first
    assert model(rich()) == first == model(rich())


def test_surfaces_are_placed_by_the_shells_own_rules_and_the_desktop_is_what_is_left() -> None:
    data = model(rich())
    by_name = surfaces(data)
    bar, dock, ring = by_name["Top_Bar"], by_name["Dock"], by_name["Ring"]
    assert bar["rect"] == {"x": 0, "y": 0, "width": 1920, "height": 32}
    assert bar["anchor"] == ["left", "right", "top"] and bar["exclusive_zone"] == 32
    assert dock["rect"] == {"x": 760, "y": 1012, "width": 400, "height": 56}  # 12 px above the edge
    assert dock["exclusive_zone"] in (-1, 0)  # a Panel reserves nothing
    assert ring["thickness"] == {"left": 4, "top": 0, "right": 4, "bottom": 4}
    # 1920x1080 minus the Bar's 32 at the top and the Frame's 4, 0, 4, 4
    assert data["desktop"] == [
        {"output": "Preview-1", "x": 4, "y": 32, "width": 1912, "height": 1044}
    ]
    assert [p["name"] for p in data["popups"]] == ["Tip"]


def test_module_slots_are_placeholders_with_their_params_and_no_live_data() -> None:
    bar = surfaces(model(rich()))["Top_Bar"]
    (row,) = bar["blocks"]
    (clock,) = row["children"]
    assert clock["type"] == "module" and clock["module"] == "Clock" and clock["label"] == "Clock"
    assert clock["params"]["tooltip_format"] == "%A, %d %B %Y"  # the module's own default


def test_the_theme_tokens_and_the_appearance_are_in_the_model() -> None:
    data = model(rich())
    assert data["tokens"]["color.surface"] == "#12171D" and data["tokens"]["shape.small"] == 4
    assert data["appearance"]["density"] == "compact" and data["appearance"]["stylesheets"] == [
        "Default"
    ]


def test_an_output_size_changes_the_placement_and_a_monitor_that_matches_none_is_skipped() -> None:
    body = RICH.replace("Index: 0", "Index: default")
    files = {SHELL: HEADER + body}
    two = preview(
        CONFIG, files, [VirtualOutput("A", 1000, 600), VirtualOutput("B", 2000, 900)]
    ).to_dict()
    assert {
        (s["output"], s["name"]): s["rect"]["width"]
        for s in two["surfaces"]
        if s["kind"] != "frame"
    } == {
        ("A", "Top_Bar"): 1000,
        ("A", "Dock"): 400,
        ("B", "Top_Bar"): 2000,
        ("B", "Dock"): 400,
    }
    assert [d["output"] for d in two["desktop"]] == ["A", "B"]
    none = preview(CONFIG, {SHELL: HEADER + RICH.replace("Index: 0", "Connector: DP-9")}).to_dict()
    assert none["monitors"][0]["status"] == "skipped: matches no output"
    assert none["surfaces"] == [] and none["desktop"][0]["height"] == 1080


def test_a_surface_that_gets_no_geometry_says_why_and_the_others_are_still_drawn() -> None:
    extra = (
        "Panel { Name: Sized, Anchor: [TOP], Width: AUTO, Height: AUTO, "
        "Children { FlexBox { } } }\n"
        "            Panel { Name: Lost, Attach_To: Sized, Attach: BOTTOM, Width: 10, "
        "Height: 10 }\n"
    )
    body = RICH.replace(
        "            Panel {\n                Name: Dock",
        extra + "            Panel {\n                Name: Dock",
    )
    data = model({SHELL: HEADER + body})
    by_name = surfaces(data)
    assert data["findings"] == [], data["findings"]
    assert by_name["Lost"]["status"] == "skipped: its target Sized is sized by its content (AUTO)"
    assert by_name["Top_Bar"]["status"] == "ok" and by_name["Dock"]["status"] == "ok"


def test_a_configuration_with_an_error_gives_the_findings_and_what_still_resolves() -> None:
    broken = {
        SHELL: HEADER + RICH,
        CONFIG / "Shells" / "Other_Shell.tdl": HEADER + "Shell { Monitor { Wat: 1 } }",
        CONFIG / "Themes" / "Odd_Theme.tdl": "this is not tdl {{{",
    }
    data = model(broken)
    rules = {(f["file"], f["rule"]) for f in data["findings"] if f["severity"] == "error"}
    assert ("Shells/Other_Shell.tdl", "unknown-key") in rules
    assert any(f["file"] == "Themes/Odd_Theme.tdl" for f in data["findings"])
    assert surfaces(data)["Top_Bar"]["status"] == "ok"  # the good shell is still drawn
    assert all(
        {"file", "line", "column", "severity", "rule", "message", "hint"} <= f.keys()
        for f in data["findings"]
    )


def test_a_main_shell_with_a_syntax_error_has_findings_and_no_surfaces() -> None:
    data = model({SHELL: HEADER + "Shell { Monitor { "})
    assert data["shell"] is None and data["surfaces"] == []
    assert any(f["severity"] == "error" for f in data["findings"])
    assert data["desktop"] == [
        {"output": "Preview-1", "x": 0, "y": 0, "width": 1920, "height": 1080}
    ]


def test_overrides_win_over_the_disk_and_leave_it_alone(tmp_path: Path) -> None:
    write_example(tmp_path)
    on_disk = preview(tmp_path).to_dict()
    assert surfaces(on_disk)["Top_Bar"]["rect"]["height"] == 32
    held = {
        tmp_path / "Shells" / "Main_Shell.tdl": HEADER + BODY.replace("Height: 32", "Height: 48")
    }
    over = preview(tmp_path, held).to_dict()
    assert surfaces(over)["Top_Bar"]["rect"]["height"] == 48
    assert over["desktop"][0]["y"] == 48
    assert (tmp_path / "Shells" / "Main_Shell.tdl").read_text().count("Height: 32") == 1
    assert preview(tmp_path).to_dict() == on_disk  # nothing stayed behind
    assert overlay.read_bytes(tmp_path / "Shells" / "Main_Shell.tdl")  # the plain file system


def test_a_file_that_does_not_exist_yet_is_read_from_the_overrides(tmp_path: Path) -> None:
    write_example(tmp_path)
    extra = tmp_path / "Shells" / "Extra_Shell.tdl"
    data = preview(tmp_path, {extra: HEADER + "Shell { Monitor { Wat: 1 } }"}).to_dict()
    assert any(f["file"] == "Shells/Extra_Shell.tdl" for f in data["findings"])


def test_the_preview_is_fast_enough_for_every_keystroke() -> None:
    """A loose bound, not a timing contract: the example takes a few tens of milliseconds; a
    second means something is re-reading far more than it should."""
    model(rich())  # the shipped files are read once
    start = time.perf_counter()
    for _ in range(5):
        model(rich())
    assert (time.perf_counter() - start) / 5 < 1.0


def test_the_shape_is_described_for_the_schema_export() -> None:
    shape = describe()
    assert shape["version"] == PREVIEW_VERSION
    assert set(shape["keys"]) == set(model(rich()))
