"""The content written on a module call (``Expander { Children { ... } }``): a module's layout marks
where it goes with ``Content { }``; the blocks stay the caller's (their slots and handlers read the
scope of the place that wrote them) and the stylesheet styles them like any others."""

from __future__ import annotations

from typing import Any

import tess_dl

from tess_shell.schema.shell import read_module
from tests.widgets_live import running

SHEET_HEAD = "---\nTDL: 0.1\nName: Extra\n---\n"
DRIVER = """Module {
    FlexBox {
        Name: Root
        Children {
            Expander {
                Name: Fold
                Expanded: true
                Children {
                    Label { Name: Said, Text: {{ title }} }
                    FlexBox { Name: Hit, Width: 20, Height: 10, On_Click: pressed }
                }
            }
        }
    }
}"""
CODE = """from tess_shell import Module, action

class Driver(Module):
    def __init__(self):
        self.seen = []

    def start(self):
        self.ctx.send("title", "from the caller")

    @action
    def pressed(self, event):
        self.seen.append((event.use, event.name))
"""


def test_the_content_is_placed_where_the_layout_has_its_content_marker() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        assert w.problems == [] and w.warnings() == []
        body = w.of_use("Expander", "Body")
        said = w.of_use("Label", "#0")
        assert said.parent() == body  # the Label is the content of the Expander's Body
        assert said.get("text") == "from the caller"  # the Driver's scope, not the Expander's


def test_a_handler_in_the_content_belongs_to_the_caller() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        hit = w.of_use("Driver", "Hit")
        w.window.simulate("click", node=hit)
        seen = w.host.loaded["Driver"].instance.seen  # type: ignore[attr-defined]
        assert len(seen) == 1 and seen[0][1] == "click"
        assert seen[0][0].startswith("Driver@")  # the Driver's use, not the Expander's


def test_a_value_the_caller_sends_reaches_the_content_after_the_build() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        w.send("title", "changed")
        assert w.of_use("Label", "#0").get("text") == "changed"


def test_content_in_a_shell_file_is_styled_by_the_stylesheet() -> None:
    sheet = SHEET_HEAD + 'Stylesheet { Rule { Selector: "Text", Foreground: "#ff0000" } }'
    body = "Expander { Expanded: true, Children { Label { Text: hi } } }"
    with running(body, extra_sheet=sheet) as w:
        assert w.warnings() == []
        assert w.of_use("Label", "#0").get("fill") == (255, 0, 0, 255)


def test_children_on_a_call_whose_module_has_no_content_marker_is_an_error() -> None:
    with running("Label { Text: x, Children { Label { Text: y } } }") as w:
        assert any("has no place for Children" in x for x in w.lines)
        assert w.view is None


def _read(text: str) -> tuple[Any, list[Any]]:
    doc = tess_dl.parse("---\nTDL: 0.1\nName: Box_M\n---\n" + text, path="Modules/Box_M.tdl")
    assert doc.document is not None
    return read_module(doc.document, "Box_M.tdl")


def test_a_content_marker_is_a_module_layout_block_only() -> None:
    from tess_shell.schema.shell import read_shell
    from tests.shell_samples import HEADER

    shell = HEADER + "Shell { Monitor { Name: M, Index: 0, Children { Bar { Name: B, Edge: TOP, "
    shell += "Width: EXPAND, Height: 20, Children { Content { } } } } } }"
    parsed = tess_dl.parse(shell, path="Shells/S_Shell.tdl")
    assert parsed.document is not None
    result, findings = read_shell(parsed.document, "Shells/S_Shell.tdl", lambda p: "")
    assert result is None and findings[0].rule == "content-outside-module"
    module, found = _read("Module { FlexBox { Children { Content { } } } }")
    assert module is not None and found == []
