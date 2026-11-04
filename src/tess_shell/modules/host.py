"""Load a module's Python, create its one instance, call ``start`` and ``stop``, and isolate every
failure (Module Contract > Lifecycle, Failure Modes and Recovery).

Nothing here touches tre. A failure becomes a :class:`Finding` naming the files and, for code that
raised, the line in the module's own file; the other modules keep running.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from loguru import logger

from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.module import Module
from tess_shell.modules.context import ModuleContext, UseRecord
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef

PACKAGE = "tess_shell_user_modules"


@dataclass(slots=True)
class LoadedModule:
    definition: ModuleDef
    py_path: Path
    instance: Module
    ctx: ModuleContext
    state: str = "created"  # created, running, failed, stopped
    uses: list[Use] = field(default_factory=list)


def _where(exc: BaseException, py_path: Path) -> tuple[int, str]:
    """The line in ``py_path`` where ``exc`` was raised, else the last frame."""
    frames = traceback.extract_tb(exc.__traceback__)
    own = [f for f in frames if Path(f.filename) == py_path]
    frame = (own or frames)[-1] if frames else None
    return (frame.lineno or 1, frame.filename) if frame else (1, str(py_path))


class ModuleHost:
    def __init__(self, store: ValueStore, ticks: TimeSource, config_root: Path) -> None:
        self.store = store
        self.ticks = ticks
        self.config_root = config_root
        self.loaded: dict[str, LoadedModule] = {}

    def _finding(
        self, definition: ModuleDef, rule: str, message: str, hint: str = "", line: int = 0
    ) -> Finding:
        o = definition.origin
        return Finding(
            definition.file, line or o.line, 1 if line else o.column, "error", rule, message, hint
        )

    def _import(
        self, definition: ModuleDef, py_path: Path
    ) -> tuple[ModuleType | None, Finding | None]:
        name = f"{PACKAGE}.{definition.name}"
        spec = importlib.util.spec_from_file_location(name, py_path)
        if spec is None or spec.loader is None:
            return None, self._finding(definition, "module-import", f"cannot import {py_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(name, None)
            line, _ = _where(exc, py_path)
            return None, Finding(
                str(py_path),
                line,
                1,
                "error",
                "module-import",
                f"{definition.name}: importing the Python failed: {type(exc).__name__}: {exc}",
                f"the layout file is {definition.file}",
            )
        return module, None

    def load(
        self, definition: ModuleDef, py_path: Path, uid: str, uses: list[Use]
    ) -> tuple[LoadedModule | None, list[Finding]]:
        """Import ``py_path`` and make the instance. Returns the findings of a bad module."""
        if not py_path.is_file():
            return None, [
                self._finding(
                    definition,
                    "module-no-python",
                    f"the module {definition.name} has no Python file: {py_path} is missing",
                    f"a module is {definition.file} plus {py_path.name} next to it",
                )
            ]
        module, finding = self._import(definition, py_path)
        if module is None:
            return None, [finding] if finding else []
        classes = [
            c
            for _, c in inspect.getmembers(module, inspect.isclass)
            if issubclass(c, Module) and c is not Module and c.__module__ == module.__name__
        ]
        if len(classes) != 1:
            found = ", ".join(c.__name__ for c in classes)
            message = (
                f"{py_path} has no class extending Module"
                if not classes
                else f"{py_path} has {len(classes)} classes extending Module ({found}); "
                "it needs one"
            )
            return None, [
                self._finding(
                    definition, "module-classes", message, f"the layout file is {definition.file}"
                )
            ]
        records = {
            u.key: UseRecord(u.key, u.name, u.key.split("@", 1)[1], u.monitor, dict(u.params))
            for u in uses
        }
        ctx = ModuleContext(
            definition.name,
            uid,
            {"name": definition.name},
            records,
            lambda use, key, value: self.store.send(definition.name, use, key, value),
            self.ticks,
        )
        instance = classes[0].__new__(classes[0])
        instance.ctx = ctx
        try:
            instance.__init__()  # type: ignore[misc]
        except Exception as exc:
            line, _ = _where(exc, py_path)
            return None, [
                Finding(
                    str(py_path), line, 1, "error", "module-init", f"{type(exc).__name__}: {exc}"
                )
            ]
        loaded = LoadedModule(definition, py_path, instance, ctx, uses=uses)
        self.loaded[definition.name] = loaded
        return loaded, []

    # -- lifecycle ------------------------------------------------------------------------------

    def _call(self, loaded: LoadedModule, what: str, fn: Callable[[], Any]) -> Finding | None:
        try:
            fn()
        except Exception as exc:
            line, _ = _where(exc, loaded.py_path)
            loaded.state = "failed"
            loaded.ctx.close()
            return Finding(
                str(loaded.py_path),
                line,
                1,
                "error",
                f"module-{what}",
                f"{loaded.definition.name}: {what}() raised {type(exc).__name__}: {exc}",
                "the module is marked failed; its surfaces keep their last values",
            )
        return None

    def start(self, loaded: LoadedModule) -> list[Finding]:
        """Validate each use, then ``start()``. A failure marks only this module failed."""
        findings: list[Finding] = []
        for use in loaded.uses:
            record = loaded.ctx.uses[use.key]
            try:
                loaded.instance.validate_use(record)
            except ValueError as exc:
                findings.append(
                    self._finding(
                        loaded.definition,
                        "module-use",
                        f"{use.name}: {exc}",
                        f"in the use at {use.origin}",
                    )
                )
        found = self._call(loaded, "start", loaded.instance.start)
        if found is not None:
            findings.append(found)
        else:
            loaded.state = "running"
        return findings

    def start_all(self) -> list[Finding]:
        out: list[Finding] = []
        for loaded in list(self.loaded.values()):
            out.extend(self.start(loaded))
        return out

    def stop_all(self) -> None:
        for loaded in self.loaded.values():
            if loaded.state == "running":
                found = self._call(loaded, "stop", loaded.instance.stop)
                if found is not None:
                    logger.error(f"{found.file}:{found.line}: {found.message}")
            loaded.ctx.close()
            loaded.state = "stopped"


def report(findings: list[Finding], source: Mapping[str, str] | None = None) -> None:
    """Log each finding as ``file:line: message``."""
    for f in findings:
        logger.error(
            f"{f.file}:{f.line}:{f.column}: {f.message}" + (f" ({f.hint})" if f.hint else "")
        )
