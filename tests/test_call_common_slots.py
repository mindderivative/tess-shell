"""A key written on a module call and placed on its root block (``Button { Enabled: {{ ok }} }``,
``Marquee_Text { Width: {{ params.w }} }``) is a slot of the module that holds the call: it reads
that module's values and params, and follows them (found with the Media module, whose layout calls
Buttons with ``Enabled: {{ can_next }}``; the slot used to be read in the callee's own scope and
failed with "not defined")."""

from __future__ import annotations

from tests.widgets_live import running

DRIVER = (
    "Module { Params { w { Type: number, Default: 50 } } FlexBox { Name: Root, Children { "
    'Button { Name: B, Icon: "mdi:home", Label: "B", Enabled: {{ ok }}, Width: {{ params.w }} } '
    'If {{ 1 == 1 }} { Button { Name: C, Icon: "mdi:home", Label: "C", Enabled: {{ ok }} } } '
    "} } }"
)
CODE = (
    "from tess_shell import Module\n"
    "class Driver(Module):\n"
    "    def start(self):\n"
    "        self.ctx.send('ok', False)\n"
)


def test_a_slot_on_a_module_call_reads_the_scope_of_the_module_that_holds_the_call() -> None:
    with running("Driver { w: 70 }", driver=DRIVER, driver_py=CODE) as w:
        assert w.warnings() == [], w.warnings()
        b, c = w.of_use("Button", "Root", 0), w.of_use("Button", "Root", 1)
        assert b.get("disabled") is True and c.get("disabled") is True  # ok is false
        assert b.get("width") == 70  # a param of the Driver, not of the Button
        w.send("ok", True)  # and it follows the module's values
        w.advance(16)
        assert b.get("disabled") is False and c.get("disabled") is False
        w.send("ok", False)
        w.advance(16)
        assert b.get("disabled") is True
