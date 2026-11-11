"""A module call may write a param as a ``{{ }}`` slot (Module File > Using a Module): the slot is
evaluated in the scope of the place that wrote the call, and the called module follows it, so a
standard module can show a value its caller's Python sends. A shell file's own block has no
scope."""

from __future__ import annotations

from tests.widgets_live import running

DRIVER = """Module {
    Params { Count { Type: number, Default: 3 } }
    FlexBox {
        Name: Root
        Children {
            ProgressBar { Name: Bar, Value: {{ level }}, Max: {{ params.Count * 10 }} }
            Label { Name: Name, Text: {{ title }} }
            Badge { Name: Chip, Count: {{ level }}, Show_Zero: {{ zero }} }
        }
    }
}"""
CODE = """from tess_shell import Module

class Driver(Module):
    def start(self):
        self.ctx.send("level", 5)
        self.ctx.send("title", "first")
        self.ctx.send("zero", False)
"""


def test_a_param_slot_follows_what_the_caller_sends() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        assert w.problems == [] and w.warnings() == []
        fill = w.of_use("ProgressBar", "Fill")
        assert fill.get("width") == "17%"  # 5 of 0..30
        assert w.of_use("Label", "#0").get("text") == "first"
        w.send("level", 15)
        w.advance(1000)
        assert w.of_use("ProgressBar", "Fill").get("width") == "50%"
        w.send("title", "second")
        assert w.of_use("Label", "#0").get("text") == "second"


def test_the_slot_feeds_the_numbers_of_a_nested_module_too() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        digits = w.of_use("Badge", "Digits")
        assert digits.get("text") == "5"
        w.send("level", 12)
        assert w.of_use("Badge", "Digits").get("text") == "12"
        assert w.of_use("Badge", "Root").get("visible") is True


def test_a_declared_default_is_what_a_slot_that_cannot_be_read_leaves() -> None:
    bad = DRIVER.replace("Max: {{ params.Count * 10 }}", "Max: {{ nothing_here }}")
    with running("Driver { }", driver=bad, driver_py=CODE) as w:
        assert any("nothing_here" in line for line in w.warnings())
        # the default Max (100) stands: 5 of 100
        assert w.of_use("ProgressBar", "Fill").get("width") == "5%"


def test_a_slot_of_the_wrong_type_is_a_warning_and_leaves_the_default() -> None:
    wrong = DRIVER.replace("Value: {{ level }}", 'Value: {{ "text" }}')
    with running("Driver { }", driver=wrong, driver_py=CODE) as w:
        assert any("number" in line for line in w.warnings())
        assert w.of_use("ProgressBar", "Fill").get("width") == "0%"


def test_a_slot_in_a_shell_files_own_call_is_refused_for_want_of_a_scope() -> None:
    """A shell file has no values of its own: the model says so and the Bar opens empty."""
    with running("ProgressBar { Value: {{ level }} }") as w:
        assert any("a slot outside a module is not built yet" in x for x in w.lines)
        assert w.view is None


def test_a_param_slot_changes_the_use_of_each_driver_separately() -> None:
    both = "Driver { Name: A } Driver { Name: B }"
    with running(both, driver=DRIVER, driver_py=CODE) as w:
        keys = sorted(k for k in w.uses if k.startswith("Driver@"))
        assert len(keys) == 2
        w.send("level", 20, use=keys[0])
        w.advance(1000)
        widths = sorted(
            n.get("width")
            for k, n in w.view.nodes.items()
            if k.endswith("/Fill") and k.startswith("ProgressBar@")
        )
        assert widths == ["17%", "67%"]
