"""The syntax-tree reader of a module's Python (``tess_shell.modproc.static``): what the shell knows
of a user module without running it. Parity with a real import is the point: a finding or an action
the reader gets wrong is a ``Call`` that is refused or accepted wrongly."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType

import pytest

import tess_shell
from tess_shell.modproc.static import ClassInfo, inspect_module_file, inspect_source
from tess_shell.module import Module
from tess_shell.modules.actions import ActionSpec, action_spec, actions_of

SHIPPED = Path(tess_shell.__file__).resolve().parent / "shipped"
SHIPPED_FILES = sorted(SHIPPED.glob("*/*_Module.py"))


def spec_of(sig: inspect.Signature) -> ActionSpec:
    """``action_spec`` of a signature, the way the host reads a stub's method."""

    def method(self: object) -> None: ...

    method.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            *sig.parameters.values(),
        ]
    )

    class Holder:
        pass

    Holder.method = method  # type: ignore[attr-defined]
    return action_spec(Holder().method)  # type: ignore[attr-defined]


def real_import(path: Path) -> ModuleType:
    name = f"static_parity_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def real_classes(module: ModuleType) -> list[type]:
    return [
        c
        for _, c in inspect.getmembers(module, inspect.isclass)
        if issubclass(c, Module) and c is not Module and c.__module__ == module.__name__
    ]


def find(source: str) -> tuple[ClassInfo, ...]:
    info = inspect_source(source, "M_Module.py")
    assert not info.problems, info.problems
    return info.classes


# -- parity with a real import ----------------------------------------------------------------


@pytest.mark.parametrize("path", SHIPPED_FILES, ids=lambda p: p.stem)
def test_every_shipped_module_reads_as_a_real_import_does(path: Path) -> None:
    """The class, the actions and each action's declared arguments are what ``getmembers`` and
    ``action_spec`` give for the imported class, for the 22 files the shell ships."""
    info = inspect_module_file(path)
    assert not info.problems, info.problems
    real = real_classes(real_import(path))
    assert [c.name for c in info.classes] == [c.__name__ for c in real]
    for static, cls in zip(info.classes, real, strict=True):
        assert sorted(static.actions) == actions_of(cls)
        instance = cls.__new__(cls)
        for name, sig in static.actions.items():
            assert spec_of(sig) == action_spec(getattr(instance, name)), name


def test_the_shipped_modules_include_ones_with_actions() -> None:
    """The parity above means something: some files do have actions to compare."""
    counts = [len(c.actions) for p in SHIPPED_FILES for c in inspect_module_file(p).classes]
    assert len(SHIPPED_FILES) >= 20 and sum(counts) >= 10


# -- what it finds ------------------------------------------------------------------------------


def test_a_syntax_error_is_module_import_with_its_line() -> None:
    info = inspect_source(
        "from tess_shell import Module\n\nclass A(Module):\n    def f(self:\n", "A.py"
    )
    (problem,) = info.problems
    assert problem.rule == "module-import" and "SyntaxError" in problem.message
    assert problem.line == 4


def test_an_error_only_compiling_finds_is_found_too() -> None:
    """``return`` outside a function parses and does not compile: the real import fails on it."""
    info = inspect_source(
        "from tess_shell import Module\nclass A(Module): pass\nreturn 1\n", "A.py"
    )
    assert [p.rule for p in info.problems] == ["module-import"]


def test_a_missing_file_is_module_no_python(tmp_path: Path) -> None:
    info = inspect_module_file(tmp_path / "Nothing_Module.py")
    assert [p.rule for p in info.problems] == ["module-no-python"]


def test_a_file_that_is_not_utf8_is_module_import(tmp_path: Path) -> None:
    path = tmp_path / "Bad_Module.py"
    path.write_bytes(b"\xff\xfe = 1\n")
    assert [p.rule for p in inspect_module_file(path).problems] == ["module-import"]


def test_no_class_and_two_classes_are_module_classes_with_the_hosts_words() -> None:
    none = inspect_source("x = 1\n", "N.py")
    assert none.problems[0].rule == "module-classes"
    assert none.problems[0].message == "N.py has no class extending Module"
    two = inspect_source(
        "from tess_shell import Module\nclass B(Module): pass\nclass A(Module): pass\n", "T.py"
    )
    assert two.problems[0].message == "T.py has 2 classes extending Module (A, B); it needs one"


def test_a_class_that_does_not_extend_module_is_not_counted() -> None:
    assert (
        find("from tess_shell import Module\nclass Helper: pass\nclass M(Module): pass\n")[0].name
        == "M"
    )


@pytest.mark.parametrize(
    "header",
    [
        "from tess_shell import Module",
        "from tess_shell import Module as Mod",
        "import tess_shell\nMod = tess_shell.Module",
        "import tess_shell as ts",
    ],
)
def test_the_ways_to_name_module_and_action_are_read(header: str) -> None:
    base = {
        "from tess_shell import Module": "Module",
        "from tess_shell import Module as Mod": "Mod",
        "import tess_shell\nMod = tess_shell.Module": "tess_shell.Module",
        "import tess_shell as ts": "ts.Module",
    }[header]
    dec = "ts.action" if "as ts" in header else "action"
    imports = header + ("\nfrom tess_shell import action" if dec == "action" else "")
    source = f"{imports}\n\nclass M({base}):\n    @{dec}\n    def go(self, event): ...\n"
    (cls,) = find(source)
    assert list(cls.actions) == ["go"]


def test_an_alias_of_action_is_read() -> None:
    (cls,) = find(
        "from tess_shell import Module, action as act\nclass M(Module):\n"
        "    @act\n    def go(self, event): ...\n"
    )
    assert list(cls.actions) == ["go"]


def test_only_decorated_methods_are_actions() -> None:
    (cls,) = find(
        "from tess_shell import Module, action\nclass M(Module):\n"
        "    def start(self): ...\n    def helper(self, x): ...\n"
        "    @action\n    def go(self, event, a, b=1, *, c, d=2, **kw): ...\n"
    )
    assert list(cls.actions) == ["go"]
    spec = spec_of(cls.actions["go"])
    assert spec.first == "event" and spec.names == ("a", "b", "c", "d")
    assert spec.required == frozenset({"a", "c"}) and spec.kwargs


def test_an_action_with_no_parameter_declares_nothing() -> None:
    (cls,) = find(
        "from tess_shell import Module, action\nclass M(Module):\n"
        "    @action\n    def go(self): ...\n"
    )
    assert spec_of(cls.actions["go"]) == ActionSpec("event")


def test_actions_of_a_class_of_the_same_file_it_inherits_from_are_read() -> None:
    """A mixin that is no ``Module`` and carries an action, and a ``Module`` that overrides one of
    its actions with a plain method (which is then no action, as at runtime)."""
    (cls,) = find(
        "from tess_shell import Module, action\n"
        "class Mixin:\n    @action\n    def one(self, event): ...\n    @action\n"
        "    def two(self, event): ...\n"
        "class M(Mixin, Module):\n    def two(self, event): ...\n"
    )
    assert list(cls.actions) == ["one"]


def test_a_subclass_of_a_module_class_of_the_file_counts_as_a_second_class() -> None:
    """The host counts every class that extends ``Module``, a subclass of one too."""
    info = inspect_source(
        "from tess_shell import Module\nclass A(Module): pass\nclass B(A): pass\n", "X.py"
    )
    assert info.problems[0].rule == "module-classes" and "(A, B)" in info.problems[0].message


def test_a_class_inside_an_if_or_try_is_found() -> None:
    (cls,) = find(
        "from tess_shell import Module\ntry:\n    import fast\nexcept ImportError:\n"
        "    class M(Module): pass\n"
    )
    assert cls.name == "M"
