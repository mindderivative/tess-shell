"""The module host: load, start, stop, and the failures the Module Contract names."""

from __future__ import annotations

from pathlib import Path

import tess_dl

from tess_shell.binder.model import NO_ORIGIN
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.modules.host import LoadedModule, ModuleHost
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef
from tess_shell.schema.shell import read_module

LAYOUT = "---\nTDL: 0.1\nName: {name}\n---\nModule {{\n    Text {{ Text: {{{{ time }}}} }}\n}}\n"


def definition(name: str) -> ModuleDef:
    result = tess_dl.parse(LAYOUT.format(name=name), path=f"Modules/{name}_Module.tdl")
    assert result.document is not None
    found, findings = read_module(result.document, f"Modules/{name}_Module.tdl")
    assert found is not None, findings
    return found


def use(name: str, n: int = 1) -> Use:
    return Use(f"{name}@u{n}", name, f"S.M.B.{name}_{n}", {}, "Main", NO_ORIGIN)


class Rig:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.store = ValueStore()
        self.ticks = TimeSource()
        self.host = ModuleHost(self.store, self.ticks, tmp_path)

    def load(
        self, name: str, code: str | None, uses: int = 1
    ) -> tuple[LoadedModule | None, list[Finding]]:
        py = self.tmp / f"{name}_Module.py"
        if code is not None:
            py.write_text(code)
        us = [use(name, i + 1) for i in range(uses)]
        for u in us:
            self.store.add_use(name, u.key)
        return self.host.load(definition(name), py, f"uid-{name}", us)


GOOD = """
from tess_shell import Module

class Good(Module):
    def start(self):
        self.started = True
        self.ctx.send("time", "12:00")
    def stop(self):
        self.stopped = True
"""


def test_a_good_module_loads_starts_sends_and_stops(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    loaded, findings = rig.load("Good", GOOD, uses=2)
    assert loaded is not None and findings == []
    assert rig.host.start(loaded) == [] and loaded.state == "running"
    assert loaded.instance.started is True  # type: ignore[attr-defined]
    assert {c.use for c in rig.store.flush()} == {"Good@u1", "Good@u2"}  # no use: every use
    assert rig.store.values["Good@u1"]["time"] == "12:00"
    rig.host.stop_all()
    assert loaded.instance.stopped is True and loaded.state == "stopped"  # type: ignore[attr-defined]


def test_ctx_is_set_before_start_and_names_the_module_and_its_uses(tmp_path: Path) -> None:
    code = GOOD.replace(
        "self.started = True", "self.seen = (self.ctx.name, self.ctx.uid, sorted(self.ctx.uses))"
    )
    rig = Rig(tmp_path)
    loaded, _ = rig.load("Good", code, uses=2)
    assert loaded is not None
    rig.host.start(loaded)
    assert loaded.instance.seen == ("Good", "uid-Good", ["Good@u1", "Good@u2"])  # type: ignore[attr-defined]
    record = loaded.ctx.uses["Good@u2"]
    assert (record.name, record.monitor, record.uid) == ("S.M.B.Good_2", "Main", "u2")


def test_a_missing_python_file_names_both_files(tmp_path: Path) -> None:
    loaded, findings = Rig(tmp_path).load("Gone", None)
    assert loaded is None
    (f,) = findings
    assert f.rule == "module-no-python"
    assert (
        "Gone_Module.py" in f.message and "Modules/Gone_Module.tdl" in f.message + f.hint + f.file
    )


def test_no_class_and_two_classes_each_name_the_file(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    loaded, findings = rig.load("None_", "x = 1\n")
    assert loaded is None and findings[0].rule == "module-classes"
    assert "None__Module.py" in findings[0].message and "no class" in findings[0].message
    two = GOOD + "\nclass Other(Module):\n    pass\n"
    loaded, findings = rig.load("Two", two)
    assert loaded is None and findings[0].rule == "module-classes"
    assert "2 classes" in findings[0].message and "Good" in findings[0].message


def test_an_import_error_is_a_finding_at_the_line_in_the_module_file(tmp_path: Path) -> None:
    code = "from tess_shell import Module\n\nraise RuntimeError('boom')\n"
    loaded, findings = Rig(tmp_path).load("Boom", code)
    assert loaded is None
    (f,) = findings
    assert f.rule == "module-import" and f.line == 3 and f.file.endswith("Boom_Module.py")
    assert "boom" in f.message


def test_a_start_that_raises_fails_only_that_module(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    bad = GOOD.replace("self.started = True", "raise ValueError('no clock')")
    broken, _ = rig.load("Bad", bad)
    fine, _ = rig.load("Good", GOOD)
    assert broken is not None and fine is not None
    findings = rig.host.start_all()
    assert [f.rule for f in findings] == ["module-start"]
    raised = next(i for i, t in enumerate(bad.splitlines(), 1) if "raise ValueError" in t)
    assert "no clock" in findings[0].message and findings[0].line == raised
    assert broken.state == "failed" and fine.state == "running"
    rig.store.flush()
    assert rig.store.values["Good@u1"]["time"] == "12:00"  # the other module still ran
    rig.host.stop_all()  # a failed module is not stopped again


def test_a_rejected_use_is_reported_naming_the_use_and_the_param(tmp_path: Path) -> None:
    code = GOOD + (
        "\n    def validate_use(self, use):\n        raise ValueError('format: bad pattern')\n"
    )
    loaded, _ = Rig(tmp_path).load("Good", code)
    assert loaded is not None
    rig = Rig(tmp_path)
    rig.host.loaded["Good"] = loaded
    findings = rig.host.start(loaded)
    assert findings[0].rule == "module-use"
    assert "S.M.B.Good_1" in findings[0].message and "format" in findings[0].message
    assert loaded.state == "running"  # the module itself keeps running


def test_a_tick_callback_that_raises_is_logged_and_the_next_one_still_runs(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    loaded, _ = rig.load("Good", GOOD)
    assert loaded is not None
    calls: list[int] = []

    def bad() -> None:
        calls.append(1)
        raise RuntimeError("x")

    sub = loaded.ctx.on_tick("second", bad)
    loaded.ctx.on_tick("second", lambda: calls.append(2))
    for s in rig.ticks._subs:  # run the callbacks as the loop would
        s.fn()
    assert calls == [1, 2]
    sub.cancel()
    loaded.ctx.close()
    assert rig.ticks._subs == []


def test_the_shipped_clock_loads_with_the_real_module_file(tmp_path: Path) -> None:
    from tess_shell.config.discovery import shipped_dir

    path = shipped_dir() / "Clock" / "Clock_Module.tdl"
    result = tess_dl.parse(path.read_text(), path=str(path))
    assert result.document is not None
    from tess_shell.schema.shell import read_style

    def style(text: str) -> object:
        document = tess_dl.parse((path.parent / text).read_text(), path=text).document
        assert document is not None
        found, problems = read_style(document, text)
        assert problems == []
        return found

    mod, findings = read_module(
        result.document,
        "Clock_Module.tdl",
        None,
        None,
        style,  # type: ignore[arg-type]
    )
    assert mod is not None and findings == []
    assert set(mod.params) == {"format", "hour_cycle", "timezone"}
    rig = Rig(tmp_path)
    rig.store.add_use("Clock", "Clock@u1")
    params = {"format": "%H:%M", "hour_cycle": "desktop", "timezone": "Europe/Berlin"}
    u = Use("Clock@u1", "Clock", "S.M.B.Clock_1", params, "Main", NO_ORIGIN)
    loaded, problems = rig.host.load(mod, path.with_suffix(".py"), "uid", [u])
    assert loaded is not None and problems == []
    assert rig.host.start(loaded) == []
    rig.store.flush()
    assert len(rig.store.values["Clock@u1"]["time"]) == 5
    rig.host.stop_all()


def test_a_syntax_error_is_located_in_the_module_file_not_in_the_host(tmp_path: Path) -> None:
    code = "from tess_shell import Module\nclass Bad(Module:\n    pass\n"
    loaded, findings = Rig(tmp_path).load("Syn", code)
    assert loaded is None
    (f,) = findings
    assert f.rule == "module-import" and f.file.endswith("Syn_Module.py") and f.line == 2
    assert "SyntaxError" in f.message
