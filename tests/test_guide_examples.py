"""Every example of the user guide is a configuration folder that passes ``tesserae-shell check``.

An example is a folder two levels under ``guide/examples/`` (``<page>/<set>/``): a configuration
folder with a ``settings.tdl``, ``Shells/``, ``Modules/`` and so on, exactly what a person would
copy. Each is checked, in process, on a temporary copy, so nothing real is read or written. A
warning fails the test too, unless the page says the example has one (``ALLOWED`` below says which).
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import re
import shutil
from pathlib import Path

import pytest

from tess_shell import Module
from tess_shell.cli import main
from tess_shell.schema.export import schema_dict
from tests import guide_tables as g

SETS = g.example_sets()
IDS = [s.relative_to(g.EXAMPLES).as_posix() for s in SETS]
SCHEMA = schema_dict()

# the examples that have a warning, by set, with the rules the page explains: none
ALLOWED: dict[str, set[str]] = {}

SUFFIXES = ("_Shell.tdl", "_Module.tdl", "_Style.tdl", "_Theme.tdl", "_Stylesheet.tdl")


def check(folder: Path, tmp_path: Path) -> tuple[int, dict[str, object]]:
    """``tesserae-shell check --json`` on a copy of ``folder``."""
    config = tmp_path / "config"
    shutil.copytree(folder, config)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["check", "--json", "--config-dir", str(config)])
    return code, json.loads(out.getvalue())


def test_there_are_examples() -> None:
    assert len(SETS) >= 40


@pytest.mark.parametrize("folder", SETS, ids=IDS)
def test_the_example_passes_check(folder: Path, tmp_path: Path) -> None:
    code, report = check(folder, tmp_path)
    name = folder.relative_to(g.EXAMPLES).as_posix()
    findings = report["errors"]
    assert isinstance(findings, list)
    errors = [f for f in findings if f["severity"] == "error"]
    assert code == 0 and report["ok"] is True and not errors, errors
    unexpected = [f for f in findings if f["rule"] not in ALLOWED.get(name, set())]
    assert not unexpected, f"{name} has findings the page does not explain: {unexpected}"


@pytest.mark.parametrize("folder", SETS, ids=IDS)
def test_check_read_every_file_of_the_example(folder: Path, tmp_path: Path) -> None:
    """A file the shell ignores (a misnamed one) would make an example that checks nothing."""
    _, report = check(folder, tmp_path)
    written = [p for p in folder.rglob("*.tdl") if p.name.endswith(SUFFIXES)]
    assert report["files"] == len(written)
    stray = [
        p.relative_to(folder).as_posix()
        for p in folder.rglob("*.tdl")
        if p.name != "settings.tdl" and not p.name.endswith(SUFFIXES)
    ]
    assert not stray, f"files that are not read: {stray}"


@pytest.mark.parametrize("folder", SETS, ids=IDS)
def test_the_python_of_an_example_is_a_module(folder: Path) -> None:
    """A module's Python file parses, and holds the class named like the module."""
    for path in folder.rglob("*_Module.py"):
        ast.parse(path.read_text(encoding="utf-8"))
        name = path.name.removesuffix("_Module.py")
        spec = importlib.util.spec_from_file_location(f"guide_example_{name}", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert issubclass(getattr(module, name), Module), path


CALL = re.compile(r"Action:\s*Call,\s*Target:\s*\"(\w+)\.(\w+)\"([^}]*)\}")


@pytest.mark.parametrize("folder", SETS, ids=IDS)
def test_the_calls_of_an_example_name_real_actions(folder: Path) -> None:
    """``check`` does not look inside a module's Python, so a ``Call`` to an action that does not
    exist would pass it: look the shipped modules' actions up in the schema."""
    own = {p.name.removesuffix("_Module.tdl") for p in folder.rglob("*_Module.tdl")}
    for path in folder.rglob("*.tdl"):
        for module, action, rest in CALL.findall(path.read_text(encoding="utf-8")):
            if module in own:
                continue
            actions = {a["name"]: a for a in SCHEMA["modules"][module]["actions"]}
            assert action in actions, f"{path.name}: {module} has no action {action}"
            given = set(re.findall(r"(\w+)\s*:", rest))
            wanted = {a["name"] for a in actions[action]["args"] if a["required"]}
            assert wanted <= given, f"{path.name}: {module}.{action} needs {wanted - given}"
