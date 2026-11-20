"""A module's Python read from its syntax tree, and never run.

The shell does not import a user module (it runs in a child process), so what the module host and
``tesserae-shell check`` need to know of a file (does it parse, how many classes extend ``Module``,
which methods are ``@action`` and what arguments each takes) comes from here: ``ast.parse`` and a
``compile`` of the tree find every ``SyntaxError`` the real import would, and nothing executes.

What it cannot see is what the file only does when it runs: an action added by assignment, by
``setattr`` or by a metaclass. The child reports the actions it really found (``imported``) and the
shell warns when they differ (``module-actions``).

Standard library only.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Problem:
    """Something wrong with the file. ``rule`` is the finding's rule; ``line`` is 0 when the finding
    belongs to the whole file (the caller then uses the layout file's position)."""

    rule: str
    message: str
    line: int = 0


@dataclass(frozen=True, slots=True)
class ClassInfo:
    name: str
    line: int
    actions: dict[str, inspect.Signature] = field(default_factory=dict)  # without ``self``


@dataclass(frozen=True, slots=True)
class FileInfo:
    """``classes`` are the classes that extend ``Module`` (directly, or through a class of the same
    file): the host needs exactly one. ``problems`` are the findings of the file itself."""

    classes: tuple[ClassInfo, ...] = ()
    problems: tuple[Problem, ...] = ()


def no_class(path: Path | str) -> str:
    return f"{path} has no class extending Module"


def many_classes(path: Path | str, names: list[str]) -> str:
    return f"{path} has {len(names)} classes extending Module ({', '.join(names)}); it needs one"


# -- reading names -----------------------------------------------------------------------------


class _Names:
    """What ``Module`` and ``action`` are called in this file (``from tess_shell import Module as
    M``, ``import tess_shell as ts`` then ``ts.Module``)."""

    def __init__(self, tree: ast.Module) -> None:
        self.module_names = {"Module"}
        self.action_names = {"action"}
        self.packages: set[str] = {"tess_shell"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in (
                "tess_shell",
                "tess_shell.module",
            ):
                for alias in node.names:
                    if alias.name == "Module":
                        self.module_names.add(alias.asname or alias.name)
                    elif alias.name == "action":
                        self.action_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("tess_shell", "tess_shell.module"):
                        self.packages.add(alias.asname or alias.name.split(".")[0])

    def is_module(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.module_names
        return isinstance(node, ast.Attribute) and node.attr == "Module"

    def is_action(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.action_names
        return isinstance(node, ast.Attribute) and node.attr == "action"


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> inspect.Signature:
    """What ``inspect.signature`` gives for the bound method (``self`` dropped); a default is only
    a marker, its value is not needed."""
    a = fn.args
    params: list[inspect.Parameter] = []
    positional = [*a.posonlyargs, *a.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults)) + list(
        a.defaults
    )
    for n, (arg, default) in enumerate(zip(positional, defaults, strict=True)):
        if n == 0:
            continue  # self
        kind = (
            inspect.Parameter.POSITIONAL_ONLY
            if n < len(a.posonlyargs)
            else inspect.Parameter.POSITIONAL_OR_KEYWORD
        )
        params.append(
            inspect.Parameter(
                arg.arg, kind, default=inspect.Parameter.empty if default is None else None
            )
        )
    if a.vararg:
        params.append(inspect.Parameter(a.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    for arg, kw_default in zip(a.kwonlyargs, a.kw_defaults, strict=True):
        params.append(
            inspect.Parameter(
                arg.arg,
                inspect.Parameter.KEYWORD_ONLY,
                default=inspect.Parameter.empty if kw_default is None else None,
            )
        )
    if a.kwarg:
        params.append(inspect.Parameter(a.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(params)


def _class_defs(body: list[ast.stmt]) -> list[ast.ClassDef]:
    """The classes bound at the top level of a module, also inside ``if``, ``try`` and ``with``."""
    found: list[ast.ClassDef] = []
    for node in body:
        if isinstance(node, ast.ClassDef):
            found.append(node)
        elif isinstance(node, ast.If):
            found.extend(_class_defs(node.body))
            found.extend(_class_defs(node.orelse))
        elif isinstance(node, ast.Try):
            for part in (node.body, node.orelse, node.finalbody):
                found.extend(_class_defs(part))
            for handler in node.handlers:
                found.extend(_class_defs(handler.body))
        elif isinstance(node, ast.With):
            found.extend(_class_defs(node.body))
    return found


def _base_names(cls: ast.ClassDef) -> list[str]:
    return [b.id for b in cls.bases if isinstance(b, ast.Name)]


def read_tree(tree: ast.Module) -> tuple[ClassInfo, ...]:
    """The classes of ``tree`` that extend ``Module`` and their ``@action`` methods."""
    names = _Names(tree)
    by_name = {c.name: c for c in _class_defs(tree.body)}

    def extends(cls: ast.ClassDef, seen: frozenset[str]) -> bool:
        if any(names.is_module(b) for b in cls.bases):
            return True
        for base in _base_names(cls):
            parent = by_name.get(base)
            if parent is not None and base not in seen and extends(parent, seen | {base}):
                return True
        return False

    def members(cls: ast.ClassDef, seen: frozenset[str]) -> dict[str, inspect.Signature | None]:
        """Method name to its signature when it is an action, else ``None``; the class's own
        definitions win over its bases'."""
        out: dict[str, inspect.Signature | None] = {}
        for item in cls.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                is_action = any(names.is_action(d) for d in item.decorator_list)
                out[item.name] = _signature(item) if is_action else None
        for base in _base_names(cls):
            parent = by_name.get(base)
            if parent is not None and base not in seen:
                for name, sig in members(parent, seen | {base}).items():
                    out.setdefault(name, sig)
        return out

    found: list[ClassInfo] = []
    for cls in by_name.values():
        if extends(cls, frozenset({cls.name})):
            actions = {
                n: s for n, s in members(cls, frozenset({cls.name})).items() if s is not None
            }
            found.append(ClassInfo(cls.name, cls.lineno, dict(sorted(actions.items()))))
    return tuple(sorted(found, key=lambda c: c.line))


def inspect_source(source: str, path: Path | str) -> FileInfo:
    """:func:`inspect_module_file` for text already read."""
    try:
        tree = ast.parse(source, str(path))
        compile(tree, str(path), "exec", dont_inherit=True)  # the errors only compiling finds
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        line = exc.lineno if isinstance(exc, SyntaxError) and exc.lineno else 1
        return FileInfo(
            problems=(
                Problem(
                    "module-import",
                    f"importing the Python failed: {type(exc).__name__}: {exc}",
                    line,
                ),
            )
        )
    classes = read_tree(tree)
    if len(classes) == 1:
        return FileInfo(classes)
    names = sorted(c.name for c in classes)
    message = no_class(path) if not classes else many_classes(path, names)
    return FileInfo(classes, (Problem("module-classes", message),))


def inspect_module_file(path: Path) -> FileInfo:
    """Read ``path`` without running it. ``problems`` holds ``module-no-python`` (no such file),
    ``module-import`` (it does not parse or compile: a ``SyntaxError``, with its line) and
    ``module-classes`` (none or more than one class extends ``Module``); ``classes`` the classes
    with their actions."""
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return FileInfo(problems=(Problem("module-no-python", f"{path} is missing"),))
    except (OSError, UnicodeDecodeError) as exc:
        return FileInfo(
            problems=(
                Problem(
                    "module-import", f"importing the Python failed: {type(exc).__name__}: {exc}", 1
                ),
            )
        )
    return inspect_source(source, path)
