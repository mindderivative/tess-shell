"""``On_Click`` and ``@action`` (Events and Actions): the schema, the module host, the click."""

from __future__ import annotations

from pathlib import Path

import pytest
import tess_dl
from tess_re import Window

from tess_shell.binder.build import build
from tess_shell.binder.model import Handler, Length, Node
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef
from tess_shell.schema.shell import read_module, read_shell
from tests.shell_samples import BODY, HEADER, SVG
from tests.test_module_host import Rig, definition, use

BOX = {"Width": Length(10), "Height": Length(10)}  # a zero-size box takes no click
MODULE_HEAD = "---\nTDL: 0.1\nName: Btn\n---\n"


def module(body: str) -> tuple[ModuleDef | None, list[Finding]]:
    result = tess_dl.parse(MODULE_HEAD + body, path="Modules/Btn_Module.tdl")
    assert result.document is not None
    return read_module(result.document, "Modules/Btn_Module.tdl")


def module_errors(body: str) -> list[Finding]:
    found, findings = module(body)
    assert found is None
    return [f for f in findings if f.severity == "error"]


def test_a_bare_name_and_a_block_form_are_typed() -> None:
    found, findings = module(
        "Module { FlexBox { On_Click: open_it\n Children { Rectangle { Width: 4, Height: 4, "
        'On_Click { Action: pick, Which: "second", Count: 3, Loud: true } } } } }'
    )
    assert found is not None and findings == []
    (box,) = found.children
    assert isinstance(box, Node) and box.handlers["On_Click"] == Handler("open_it")
    (rect,) = box.children
    assert isinstance(rect, Node)
    assert rect.handlers["On_Click"].args == {"Which": "second", "Count": 3, "Loud": True}
    assert rect.handlers["On_Click"].action == "pick"
    assert rect.handlers["On_Click"].origin.line > 0


@pytest.mark.parametrize(
    ("line", "rule", "needle"),
    [
        ("On_Clik: go", "unknown-key", "On_Click"),
        ("On_Focus: go", "event-not-raised", "On_Click"),
        ("On_Open: go", "event-not-raised", "does not raise"),
        ("On_Click: Close", "not-built", "Close"),
        ("On_Click: Show", "missing-key", "Target"),
        ("On_Click: 5", "bad-name", "action"),
        ("On_Click { Which: 1 }", "missing-key", "Action"),
        ("On_Click { Action: go, Who: [1, 2] }", "bad-value", "argument"),
    ],
)
def test_a_bad_handler_is_reported_at_its_key(line: str, rule: str, needle: str) -> None:
    found = module_errors("Module { Rectangle { Width: 4, Height: 4, " + line + " } }")
    assert any(f.rule == rule and needle in f.message + f.hint for f in found), found
    assert all(f.line > 0 for f in found)


def test_a_text_raises_nothing_and_the_error_says_where_to_put_the_handler() -> None:
    found = module_errors('Module { Text { Text: "x", On_Click: go } }')
    (f,) = found
    assert f.rule == "event-not-raised" and "FlexBox or Box around it" in f.hint


def test_a_shell_file_cannot_name_a_module_action() -> None:
    body = BODY.replace("Spacer { }", "Spacer { On_Click: go }")
    result = tess_dl.parse(HEADER + body, path="Shells/Main_Shell.tdl")
    assert result.document is not None
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: SVG)
    assert shell is None
    assert any(f.rule == "unknown-action" and "Show" in f.hint for f in findings), findings


ACTION_PY = """
from tess_shell import Module, action

class Btn(Module):
    clicks = []

    @action
    def go(self, event):
        self.clicks.append(event)

    @action
    def boom(self, event):
        raise RuntimeError("no")

    def helper(self):
        pass
"""


def host_module(rig: Rig, handlers: str, code: str = ACTION_PY):  # type: ignore[no-untyped-def]
    layout = MODULE_HEAD + "Module { Rectangle { Width: 4, Height: 4, " + handlers + " } }\n"
    result = tess_dl.parse(layout, path="Modules/Btn_Module.tdl")
    assert result.document is not None
    defn, findings = read_module(result.document, "Modules/Btn_Module.tdl")
    assert defn is not None, findings
    py = rig.tmp / "Btn_Module.py"
    py.write_text(code)
    u = use("Btn")
    rig.store.add_use("Btn", u.key)
    return rig.host.load(defn, py, "uid", [u]), defn, u


def test_a_handler_naming_a_method_that_is_not_an_action_fails_the_load(tmp_path: Path) -> None:
    (loaded, findings), _, _ = host_module(Rig(tmp_path), "On_Click: helper")
    assert loaded is None
    (f,) = findings
    assert f.rule == "unknown-action" and "no action helper" in f.message
    assert "boom, go" in f.hint and f.file == "Modules/Btn_Module.tdl" and f.line > 0


def test_a_click_calls_the_action_on_the_loop_with_the_event_record(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    (loaded, findings), defn, u = host_module(rig, 'On_Click { Action: go, Who: "me" }')
    assert loaded is not None and findings == []
    rig.host.start(loaded)
    window = Window(width=100, height=40)
    handler = Handler("go", {"Who": "me"}, use=u.key)
    node = Node("Rectangle", name="T", props=BOX, handlers={"On_Click": handler})
    view = build([node], window)
    view.sink = rig.host.dispatch
    window.simulate("click", node=view.nodes["T"])
    (event,) = loaded.instance.clicks
    assert (event.name, event.use, dict(event.args)) == ("click", u.key, {"Who": "me"})
    assert event.time > 0


def test_a_raising_action_is_logged_once_and_the_shell_goes_on(tmp_path: Path) -> None:
    from loguru import logger

    rig = Rig(tmp_path)
    (loaded, _), _, u = host_module(rig, "On_Click: boom")
    assert loaded is not None
    rig.host.start(loaded)
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="ERROR")
    try:
        window = Window(width=100, height=40)
        node = Node(
            "Rectangle", name="T", props=BOX, handlers={"On_Click": Handler("boom", use=u.key)}
        )
        view = build([node], window)
        view.sink = rig.host.dispatch
        window.simulate("click", node=view.nodes["T"])
        window.simulate("click", node=view.nodes["T"])
    finally:
        logger.remove(sink)
    assert len(lines) == 2 and all(
        "Btn.boom raised on On_Click" in x for x in lines
    )  # one per click


def test_a_reload_replaces_the_handler_without_a_second_listener() -> None:
    window = Window(width=100, height=40)
    seen: list[str] = []

    def node(action: str) -> Node:
        return Node(
            "Rectangle", name="T", props=BOX, handlers={"On_Click": Handler(action, use="Btn@1")}
        )

    view = build([node("first")], window)
    view.sink = lambda h, key, raw: seen.append(h.action)
    view.rebuild([node("second")])
    window.simulate("click", node=view.nodes["T"])
    assert seen == ["second"]  # the new handler, called once
    view.rebuild([Node("Rectangle", name="T", props=BOX)])  # handler removed
    window.simulate("click", node=view.nodes["T"])
    assert seen == ["second"]


def test_definition_helper_still_loads_modules_without_handlers() -> None:
    assert definition("Plain").children  # the M2 module layout is unchanged
