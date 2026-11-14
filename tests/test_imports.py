"""The import rules of Shell Package Layout, checked on the source with ``ast``."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "tess_shell"
STDLIB = sys.stdlib_module_names
ANY = None  # no restriction

# Allowed non-standard-library imports per module, by dotted path relative to ``tess_shell``.
# A dotted entry allows that package and everything under it.
RULES: dict[str, set[str] | None] = {
    "schema": {
        "tess_dl",
        "tess_shell.appearance",
        "tess_shell.schema",
        "tess_shell.binder.model",
        "tess_shell.binder.convert",
    },
    # the export of the schema to JSON reads the loader's own tables, the settings reader's and the
    # shipped theme; only the command line calls it
    "schema.export": {
        "tess_dl",
        "tess_shell.__version__",
        "tess_shell.binder.defaults",
        "tess_shell.binder.marquee",
        "tess_shell.binder.model",
        "tess_shell.binder.motion",
        "tess_shell.config.paths",
        "tess_shell.config.settings",
        "tess_shell.schema",
    },
    "files": {"tess_dl", "tess_shell.schema", "tess_shell.config", "tess_shell.files"},
    "config": {
        "tess_dl",
        "tess_shell.schema",
        "tess_shell.config",
        "tess_shell.exit_codes",
    },
    "model": {
        "tess_el",
        "loguru",
        "tess_shell.appearance",
        "tess_shell.binder.model",
        "tess_shell.binder.focus",
        "tess_shell.binder.shadow",
        "tess_shell.schema",
        "tess_shell.model",
    },
    "module": set(),
    "modules": {
        "loguru",
        "tess_shell.logging",  # ModuleHost.report tells the control interface of a finding
        "tess_shell.binder.model",
        "tess_shell.module",
        "tess_shell.model",
        "tess_shell.modules",
        "tess_shell.schema",
        "tess_shell.services.api",
    },
    # the shipped modules are module code: only the public names a module author may use
    "shipped": {"tess_shell.Module", "tess_shell.action"},
    "watch": {"inotify_simple", "loguru"},
    # note_module_error makes a Finding (the record: standard library only)
    "logging": {"loguru", "tess_shell.schema.findings"},
    "exit_codes": set(),
    "options": set(),
    "signals": set(),
    "binder": {"tess_re", "loguru", "tess_shell._vendor.tess_utils", "tess_shell.binder"},
    "_vendor": set(),
    "appearance": set(),
    "services": {
        "dbus_fast",
        "inotify_simple",
        "loguru",
        "tess_shell._vendor.tess_utils",  # services.icons decodes a png the way the Image path does
        "tess_shell.services",
        "tess_shell.appearance",
    },
    "surfaces": set(),
    "surfaces.bar": {"tess_shell.binder.model"},
    "surfaces.panel": {"tess_shell.binder.model", "tess_shell.surfaces.bar"},
    # the order of the shell's surfaces for keyboard focus: pure, over the shell definition
    "surfaces.focus": {"tess_shell.binder.focus", "tess_shell.schema.model"},
    "surfaces.manager": {
        "tess_re",
        "loguru",
        "tess_shell.binder",
        "tess_shell.model",
        "tess_shell.schema.default_popups",
        "tess_shell.schema.findings",  # nearest names for the control commands
        "tess_shell.schema.model",
        "tess_shell.surfaces",
    },
    "surfaces.hotplug": {
        "loguru",
        "tess_shell.schema.model",
        "tess_shell.surfaces",
    },
    "surfaces.outline": set(),
    # the joins of a melded Panel (Frame > Comparing the Join Options): nodes come from the painter
    # they are given; only the shader join builds an engine object of its own
    "surfaces.join": {"tess_shell.surfaces"},
    "surfaces.join_concave": {"tess_shell.surfaces"},
    "surfaces.join_param": {"tess_shell.surfaces"},
    "surfaces.join_shader": {"tess_re", "tess_shell.surfaces"},
    "surfaces.join_structure": {"tess_shell.surfaces"},
    "surfaces.ring": {"tess_shell.surfaces.outline"},
    # the Frame's ring as one shader that blends in linear light (Debug { Frame_Blend: LINEAR })
    "surfaces.frame_shader": {"tess_re", "tess_shell.surfaces"},
    "surfaces.frame": {
        "tess_re",
        "loguru",
        "tess_shell.binder",
        "tess_shell.model",
        "tess_shell.schema.model",
        "tess_shell.surfaces",
    },
    "surfaces.popup": {
        "tess_re",
        "loguru",
        "tess_shell.binder",
        "tess_shell.model",
        "tess_shell.schema.default_popups",  # the Popups the shell provides
        "tess_shell.schema.model",
        "tess_shell.surfaces",
    },
    # the control commands' client: the standard library and jeepney, nothing that costs time to
    # import (tests/test_client.py lists what a run imports)
    "client": {"jeepney", "tess_shell.__version__", "tess_shell.exit_codes", "tess_shell.options"},
    "commands": ANY,  # the shell's side of the control interface: it holds the model
    "scanner": ANY,
    "reloader": ANY,
    "app": ANY,
    "cli": ANY,
    "__main__": ANY,
    "__init__": ANY,
}


def external_imports(path: Path) -> set[str]:
    """Imported module names, ignoring ``if TYPE_CHECKING:`` blocks."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skipped: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test):
            skipped.update(id(n) for child in node.body for n in ast.walk(child))
    names: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path}: relative imports are not used here"
            assert node.module is not None
            # `from a.b import c` may import the module a.b.c: judge it as a.b.c
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def rule_for(path: Path) -> tuple[str, set[str] | None]:
    relative = path.relative_to(SRC)
    dotted = ".".join(relative.with_suffix("").parts)
    key = dotted if dotted in RULES else relative.parts[0].removesuffix(".py")
    assert key in RULES, f"{relative}: no import rule; add one to tests/test_imports.py"
    return key, RULES[key]


def allowed(name: str, rule: set[str]) -> bool:
    top = name.split(".")[0]
    if top in STDLIB:
        return True
    return any(name == a or name.startswith(a + ".") for a in rule)


SOURCES = sorted(p for p in SRC.rglob("*.py"))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(SRC)))
def test_module_imports_follow_the_layout(path: Path) -> None:
    key, rule = rule_for(path)
    if rule is None:
        return
    bad = sorted(n for n in external_imports(path) if not allowed(n, rule))
    assert not bad, f"{path.relative_to(SRC)} ({key}) may not import {bad}"


def test_only_app_and_cli_import_the_engine() -> None:
    importers = {
        p.relative_to(SRC).parts[0].removesuffix(".py")
        for p in SOURCES
        if any(n.split(".")[0] == "tess_re" for n in external_imports(p))
    }
    assert importers <= {"app", "binder", "surfaces"}, importers


def test_shell_modules_never_import_the_engine() -> None:
    for path in (SRC / "modules").rglob("*.py") if (SRC / "modules").is_dir() else []:
        assert not any(n.split(".")[0] == "tess_re" for n in external_imports(path)), path


def test_only_tess_utils_imports_pillow() -> None:
    for path in SOURCES:
        if "tess_utils" in path.parts:
            continue
        assert not any(n.split(".")[0] == "PIL" for n in external_imports(path)), path
