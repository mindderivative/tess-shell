"""``Call`` and a handler's ``{{ }}`` arguments (Events and Actions > Call, caller.data and
Submenus): the schema, the module host's check, and the click that runs a module's action with its
arguments, through a manager with real tre windows and no compositor."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import tess_dl
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.files.icons import IconSets
from tess_shell.model.args import ArgError, copy_plain, evaluate, scope_for
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.modules.host import ModuleHost
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.look import read_stylesheet, read_theme
from tess_shell.schema.model import ModuleDef
from tess_shell.schema.shell import read_module, read_shell
from tess_shell.surfaces.manager import SurfaceManager
from tests.shell_samples import HEADER
from tests.test_look import THEME
from tests.test_model_live import parse
from tests.test_panel import StubApp
from tests.test_popup import SHELL, read

# -- the schema -------------------------------------------------------------------------------

HEAD = "---\nTDL: 0.1\nName: Btn\n---\n"


def layout(body: str, modules: dict[str, ModuleDef] | None = None) -> tuple[Any, list[Any]]:
    result = tess_dl.parse(HEAD + body, path="Modules/Btn_Module.tdl")
    assert result.document is not None
    return read_module(result.document, "Modules/Btn_Module.tdl", modules)


def known(*names: str) -> dict[str, ModuleDef]:
    return {n: ModuleDef(n, f"{n}.tdl", m.NO_ORIGIN, {}, ()) for n in names}


def test_call_names_a_module_action_and_keeps_the_other_keys_as_its_arguments() -> None:
    found, findings = layout(
        'Module { FlexBox { On_Click { Action: Call, Target: "Clock.cycle_format", '
        'Format: "24h", N: 3, Loud: true } } }',
        known("Clock", "Btn"),
    )
    assert found is not None and findings == [], findings
    (box,) = found.children
    h = box.handlers["On_Click"]
    assert (h.action, h.module, h.builtin) == ("cycle_format", "Clock", False)
    assert dict(h.args) == {"Format": "24h", "N": 3, "Loud": True} and not h.slots
    assert h.origin.line > 0


def test_an_argument_may_be_a_slot_that_is_kept_for_the_moment_the_event_fires() -> None:
    found, findings = layout(
        "Module { Params { p { Type: string, Default: x } }\nFlexBox { On_Click { "
        'Action: Call, Target: "Btn.go", Id: {{ item.id }}, Tag: a{{ params.p }}b, Fixed: 1 } } }',
        known("Btn"),
    )
    assert found is not None and findings == [], findings
    h = found.children[0].handlers["On_Click"]
    assert dict(h.args) == {"Fixed": 1} and set(h.slots) == {"Id", "Tag"}
    assert h.slots["Id"].single and not h.slots["Tag"].single


def test_a_module_own_action_may_take_slot_arguments_too() -> None:
    found, _ = layout(
        "Module { FlexBox { On_Click { Action: go, Who: {{ event.name }} } } }", known("Btn")
    )
    h = found.children[0].handlers["On_Click"]
    assert h.action == "go" and h.module == "" and set(h.slots) == {"Who"}


def test_call_is_allowed_in_a_shell_file_and_names_a_module_of_the_shell() -> None:
    shell, findings = read(
        SHELL % ('FlexBox { On_Click { Action: Call, Target: "Btn.go", A: 1 } }', ""),
        {"Btn": ModuleDef("Btn", "x", m.NO_ORIGIN, {}, ())},
    )
    assert shell is not None, findings
    box = shell.monitors[0].surfaces[0].children[0]
    assert box.handlers["On_Click"].module == "Btn"  # type: ignore[union-attr]


def test_a_misspelt_module_is_an_error_naming_the_nearest() -> None:
    found, findings = layout(
        'Module { FlexBox { On_Click { Action: Call, Target: "Clck.cycle" } } }',
        known("Clock", "Btn"),
    )
    assert found is None
    (f,) = [x for x in findings if x.severity == "error"]
    assert f.rule == "unknown-module" and "Clck" in f.message and "Clock" in f.hint
    assert f.line == 5


# -- the arguments ----------------------------------------------------------------------------


class Scope:
    def __init__(self, **values: Any) -> None:
        self.values = values

    def lookup(self, name: str) -> Any:
        return self.values[name]

    def names(self) -> list[str]:
        return list(self.values)


def slot(text: str, *literal: str) -> m.SlotValue:
    parts: list[str | m.SlotPart] = [m.SlotPart(text)]
    parts[:0] = list(literal)
    return m.SlotValue(tuple(parts))


def test_a_slot_argument_keeps_the_type_of_a_single_slot_and_joins_a_mixed_one() -> None:
    h = m.Handler("go", {"Fixed": 1}, slots={"N": slot("n + 1"), "Tag": slot("name", "id-")})
    out = evaluate(h, scope_for({"name": "click"}, Scope(n=4, name="x")))
    assert out == {"Fixed": 1, "N": 5, "Tag": "id-x"}
    assert isinstance(out["N"], int)


def test_a_slot_reads_event_the_use_s_names_and_the_for_entries_over_them() -> None:
    h = m.Handler("go", slots={"Who": slot("event.name"), "P": slot("params.p")})
    scope = scope_for({"name": "click"}, Scope(params={"p": 7}))
    assert evaluate(h, scope) == {"Who": "click", "P": 7}


def test_an_unknown_name_is_an_error_at_the_slot_that_does_not_run_the_action() -> None:
    origin = m.Origin("M.tdl", 7, 9)
    h = m.Handler(
        "go", slots={"A": m.SlotValue((m.SlotPart("nothing", origin=origin),), origin=origin)}
    )
    with pytest.raises(ArgError) as raised:
        evaluate(h, scope_for({"name": "click"}, Scope()))
    assert raised.value.origin == origin and raised.value.message.startswith("A:")


def test_a_slot_that_gives_no_plain_value_is_refused() -> None:
    h = m.Handler("go", slots={"A": slot("x")})
    with pytest.raises(ArgError) as raised:
        evaluate(h, scope_for({}, Scope(x=object())))
    assert "plain" in raised.value.message or "not" in raised.value.message


def test_copy_plain_copies_deep_turns_tuples_into_lists_and_refuses_the_rest() -> None:
    src = {"a": [1, (2, 3)], "b": {"c": True}}
    out = copy_plain(src)
    assert out == {"a": [1, [2, 3]], "b": {"c": True}}
    assert out["b"] is not src["b"]
    with pytest.raises(ValueError, match=r"data\.a\[1\].*not plain"):
        copy_plain({"a": [1, object()]})
    with pytest.raises(ValueError, match="a key is text"):
        copy_plain({1: 2})


# -- a running manager --------------------------------------------------------------------------

BTN = (
    "Module { Params { label { Type: string, Default: L } }\n"
    'FlexBox { Name: Root, Width: 60, Height: 20, On_Click { Action: Call, Target: "Btn.picked", '
    'Who: "me", N: 3, Label: {{ params.label }}, Kind: {{ event.name }} } } }'
)

PY = """
from tess_shell import Module, action

class {name}(Module):
    def __init__(self):
        self.seen = []

    @action
    def picked(self, event):
        self.seen.append((event.use, dict(event.args)))

    @action
    def open_it(self, event):
        self.ctx.popup("Menu", data={"Id": 7, "Title": "Seven"})
"""


def py_code(name: str) -> str:
    return PY.replace("{name}", name)


@dataclass
class Live:
    manager: SurfaceManager
    host: ModuleHost
    store: ValueStore
    uses: list[str]
    lines: list[str] = field(default_factory=list)
    problems: list[Any] = field(default_factory=list)

    @property
    def bar(self) -> Any:
        return next(s for s in self.manager.surfaces if s.name == "Top_Bar")

    def action_seen(self, module: str = "Btn") -> list[Any]:
        return self.host.loaded[module].instance.seen  # type: ignore[no-any-return]

    def click(self, node_id: str) -> None:
        self.bar.window.simulate("click", node=self.bar.view.nodes[node_id])

    def root(self, use: str | None = None) -> str:
        key = use or self.uses[0]
        return self.bar.expanded.roots.get(key) or f"{key}/Root"

    def log(self) -> str:
        return "\n".join(self.lines)


_SINKS: list[int] = []


@pytest.fixture(autouse=True)
def _remove_log_sinks() -> Iterator[None]:
    yield
    while _SINKS:
        logger.remove(_SINKS.pop())


def running(
    tmp_path: Path,
    children: str = "Btn { Name: Btn_One }",
    popups: str = "",
    layouts: dict[str, str] | None = None,
    code: dict[str, str] | None = None,
    look: tuple[str, str] | None = None,
) -> Live:
    """The shell of ``tests.test_popup`` with the modules ``Btn`` (and any other in ``layouts``)
    loaded by a real module host, and the manager's events routed to it as the app does."""
    texts = {"Btn": BTN, **(layouts or {})}
    defs = {}
    names = known(*texts)
    for name, text in texts.items():
        found, findings = read_module(
            parse(text, name, f"Modules/{name}_Module.tdl"), "x.tdl", names
        )
        assert found is not None, findings
        defs[name] = found
    result = tess_dl.parse(HEADER + SHELL % (children, popups), path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    shipped = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped" / "Icons"
    shell, findings = read_shell(
        result.document, "Shells/Main_Shell.tdl", lambda p: "", defs, None, IconSets([shipped])
    )
    assert shell is not None, findings
    # ``look`` is (a theme file's text, a stylesheet file's text); the default is the tests' theme
    doc = tess_dl.parse(look[0] if look else THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    assert theme is not None
    sheets = []
    if look:
        sheet_doc = tess_dl.parse(look[1], path="G_Stylesheet.tdl").document
        assert sheet_doc is not None
        sheet, findings = read_stylesheet(sheet_doc, "G_Stylesheet.tdl", set(defs))
        assert sheet is not None, findings
        sheets.append(sheet)
    the_look = make_look(theme, sheets, Appearance())
    store = ValueStore()
    manager = SurfaceManager(StubApp(), defs, lambda k: k, store, the_look)  # type: ignore[arg-type]
    host = ModuleHost(store, TimeSource(), tmp_path)

    def route(handler: m.Handler, key: str, raw: object) -> None:
        if handler.builtin:
            manager.run_builtin(handler)
        else:
            host.dispatch(handler, key, raw)

    manager.sink = route
    host.popups = manager.popups
    live = Live(manager, host, store, [])
    _SINKS.append(
        logger.add(lambda message: live.lines.append(str(message).rstrip()), level="DEBUG")
    )
    uses = manager.plan(shell)
    live.uses = [u.key for u in uses]
    by_module: dict[str, list[Any]] = {}
    for use in uses:
        by_module.setdefault(use.module, []).append(use)
    for name, module_uses in by_module.items():
        py = tmp_path / f"{name}_Module.py"
        py.write_text((code or {}).get(name) or py_code(name))
        loaded, problems = host.load(defs[name], py, f"uid-{name}", module_uses)
        assert loaded is not None, problems
    live.problems = host.check_calls(manager.planned_handlers())
    host.start_all()
    store.flush()
    manager.build()
    live.bar.window.advance(16)
    return live


def test_a_click_runs_the_modules_action_with_its_arguments(tmp_path: Path) -> None:
    r = running(tmp_path)
    assert r.problems == []
    r.click(r.root())
    ((use, args),) = r.action_seen()
    assert use == r.uses[0]
    # the literals as written; the slots read the use's params and the event when it fired
    assert args == {"Who": "me", "N": 3, "Label": "L", "Kind": "click"}


def test_a_slot_reads_the_values_as_they_are_when_the_event_fires(tmp_path: Path) -> None:
    layouts = {
        "Btn": "Module { FlexBox { Name: Root, Width: 60, Height: 20, On_Click { Action: Call, "
        'Target: "Btn.picked", Count: {{ count }} } } }'
    }
    r = running(tmp_path, layouts=layouts)
    r.store.send("Btn", r.uses[0], "count", 1)
    r.store.flush()
    r.click(r.root())
    r.store.send("Btn", r.uses[0], "count", 2)
    r.store.flush()
    r.click(r.root())
    assert [a["Count"] for _, a in r.action_seen()] == [1, 2]  # not the value at the build


def test_a_for_variable_is_in_scope_of_an_argument_slot(tmp_path: Path) -> None:
    layouts = {
        "Btn": "Module { FlexBox { Name: Root, Flex: VERTICAL, Children {\n"
        "For item In {{ items }} Key {{ item.id }} {\n"
        'FlexBox { Width: 40, Height: 10, On_Click { Action: Call, Target: "Btn.picked", '
        "Id: {{ item.id }}, Title: {{ item.title }} } }\n} } } }"
    }
    r = running(tmp_path, layouts=layouts)
    r.store.send(
        "Btn", r.uses[0], "items", [{"id": 4, "title": "four"}, {"id": 9, "title": "nine"}]
    )
    r.manager.on_change(r.store.flush())
    entries = sorted(n for n in r.bar.view.nodes if n.startswith("for"))
    assert len(entries) == 2, list(r.bar.view.nodes)
    for node_id in entries:
        r.click(node_id)
    assert [a for _, a in r.action_seen()] == [
        {"Id": 4, "Title": "four"},
        {"Id": 9, "Title": "nine"},
    ]


def test_a_slot_that_fails_is_logged_at_its_position_and_the_action_does_not_run(
    tmp_path: Path,
) -> None:
    layouts = {
        "Btn": "Module { FlexBox { Name: Root, Width: 60, Height: 20, On_Click { Action: Call, "
        'Target: "Btn.picked", Id: {{ nothing_here }} } } }'
    }
    r = running(tmp_path, layouts=layouts)
    r.click(r.root())
    assert r.action_seen() == []
    errors = [x for x in r.lines if "ERROR" in x]
    assert len(errors) == 1 and "Id:" in errors[0] and "picked did not run on On_Click" in errors[0]
    assert "x.tdl:5:" in errors[0]  # the slot's own line and column


# -- a call into another module -----------------------------------------------------------------


def test_a_call_runs_the_action_of_another_module_with_the_callers_use(tmp_path: Path) -> None:
    layouts = {
        "Btn": "Module { FlexBox { Name: Root, Width: 60, Height: 20, On_Click { Action: Call, "
        'Target: "Other.picked", From: "btn" } } }',
        "Other": "Module { FlexBox { Name: Root, Width: 10, Height: 10 } }",
    }
    r = running(
        tmp_path, children="Btn { Name: Btn_One } Other { Name: Other_One }", layouts=layouts
    )
    assert r.problems == []
    r.click(r.root(r.uses[0]))
    ((use, args),) = r.action_seen("Other")
    assert use.startswith("Btn@") and args == {"From": "btn"}  # the block that raised it
    assert r.action_seen("Btn") == []


def test_a_call_from_a_shell_file_block_runs_the_action_with_no_use(tmp_path: Path) -> None:
    children = (
        "Btn { Name: Btn_One } "
        "FlexBox { Name: Shell_Box, Width: 30, Height: 10, On_Click { Action: Call, "
        'Target: "Btn.picked", Where: "shell", Kind: {{ event.name }} } }'
    )
    r = running(tmp_path, children=children)
    r.click("Shell_Box")
    ((use, args),) = r.action_seen()
    assert use == "" and args == {"Where": "shell", "Kind": "click"}


# -- what the host checks -----------------------------------------------------------------------

OTHER = "Module { FlexBox { Name: Root, Width: 10, Height: 10 } }"


def calls(tmp_path: Path, target: str, other: bool = True) -> list[Any]:
    layouts = {
        "Btn": "Module { FlexBox { Name: Root, Width: 60, Height: 20, On_Click { Action: Call, "
        'Target: "' + target + '" } } }',
        "Other": OTHER,
    }
    children = "Btn { Name: Btn_One }" + (" Other { Name: Other_One }" if other else "")
    return running(tmp_path, children=children, layouts=layouts).problems


def test_a_call_to_an_action_the_module_lacks_is_a_finding_with_the_nearest_names(
    tmp_path: Path,
) -> None:
    (f,) = calls(tmp_path, "Other.pickd")
    assert f.severity == "error" and f.rule == "unknown-action"
    assert "Other has no action pickd" in f.message and "picked" in f.hint
    assert f.line > 0


def test_a_call_to_a_module_with_no_use_is_a_finding_that_says_why(tmp_path: Path) -> None:
    (f,) = calls(tmp_path, "Other.picked", other=False)
    assert f.rule == "call-module-not-loaded" and "Other is not loaded" in f.message
    assert "uses it" in f.hint


def test_a_valid_call_has_no_finding(tmp_path: Path) -> None:
    assert calls(tmp_path, "Other.picked") == []


def load_btn(tmp_path: Path, layout: str, code: str) -> tuple[Any, list[Any]]:
    found, findings = read_module(
        parse(layout, "Btn", "Modules/Btn_Module.tdl"), "x", known("Btn", "Other")
    )
    assert found is not None, findings
    py = tmp_path / "Btn_Module.py"
    py.write_text(code)
    use = Use("Btn@u1", "Btn", "S.M.B.Btn", {}, "Main", m.NO_ORIGIN)
    return ModuleHost(ValueStore(), TimeSource(), tmp_path).load(found, py, "uid", [use])


def test_a_call_to_the_own_module_needs_the_action_but_a_call_to_another_does_not(
    tmp_path: Path,
) -> None:
    own = 'Module { FlexBox { On_Click { Action: Call, Target: "Btn.%s" } } }'
    loaded, findings = load_btn(tmp_path, own % "nothing_like_it", py_code("Btn"))
    assert loaded is None
    assert (
        findings[0].rule == "unknown-action" and "no action nothing_like_it" in findings[0].message
    )
    loaded, findings = load_btn(tmp_path, own % "picked", py_code("Btn"))
    assert loaded is not None and findings == []
    other = 'Module { FlexBox { On_Click { Action: Call, Target: "Other.whatever" } } }'
    loaded, findings = load_btn(tmp_path, other, py_code("Btn"))
    assert loaded is not None and findings == []  # check_calls looks at it, once all are loaded


def test_a_module_action_named_like_a_built_in_action_fails_the_load(tmp_path: Path) -> None:
    code = py_code("Btn") + "\n    @action\n    def Show(self, event):\n        pass\n"
    loaded, findings = load_btn(tmp_path, "Module { FlexBox { } }", code)
    assert loaded is None
    (f,) = findings
    assert f.rule == "action-clash" and "Show" in f.message and "Call" in f.hint
