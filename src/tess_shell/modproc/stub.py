"""The class the module host loads in place of a user module's own.

``ModuleHost.load`` finds the one class that extends ``Module``, reads its ``@action`` methods and
their parameters (``action_spec``), checks the ``Call`` handlers of the shell files against them,
builds the context and instantiates the class. Nothing of the module's file may run in the shell,
so this stub is built from the file's syntax tree (:mod:`tess_shell.modproc.static`): the same class
name, an ``@action`` method for each action with the signature the file declares, and the lifecycle
methods. Its ``__init__`` starts the module's process; every method is a message to it.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from dataclasses import fields
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from tess_shell.modproc.static import ClassInfo, Problem
from tess_shell.module import Module
from tess_shell.modules.actions import ActionSpec
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef

if TYPE_CHECKING:
    from tess_shell.modproc.supervisor import ModuleProcesses, ProcessHandle

PACKAGE = "tess_shell_user_modules"


def finding_for(definition: ModuleDef, py_path: Path, problem: Problem) -> Finding:
    """The finding ``ModuleHost.load`` makes for the same fault found by importing the file."""
    o = definition.origin
    name = definition.name
    layout = f"the layout file is {definition.file}"
    if problem.rule == "module-no-python":
        return Finding(
            definition.file,
            o.line,
            o.column,
            "error",
            "module-no-python",
            f"the module {name} has no Python file: {py_path} is missing",
            f"a module is {definition.file} plus {py_path.name} next to it",
        )
    if problem.rule == "module-import":
        return Finding(
            str(py_path),
            problem.line or 1,
            1,
            "error",
            "module-import",
            f"{name}: {problem.message}",
            layout,
        )
    return Finding(
        definition.file,
        problem.line or o.line,
        1 if problem.line else o.column,
        "error",
        problem.rule,
        problem.message,
        layout,
    )


def event_fields(event: Any) -> dict[str, Any]:
    """An ``Event`` as plain data: all but the engine's own object (``stop`` cannot cross)."""
    return {f.name: getattr(event, f.name) for f in fields(event) if f.name != "_raw"}


def use_dict(record: Any) -> dict[str, Any]:
    return {
        "key": record.key,
        "name": record.name,
        "uid": record.uid,
        "monitor": record.monitor,
        "params": dict(record.params),
    }


def signature_of(spec: Mapping[str, Any]) -> inspect.Signature:
    """The signature (after ``self``) a child reported for an action: ``first`` is the event."""
    params = [inspect.Parameter(spec["first"], inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    required = set(spec["required"])
    for name in spec["names"]:
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=inspect.Parameter.empty if name in required else None,
            )
        )
    if spec["kwargs"]:
        params.append(inspect.Parameter("kwargs", inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(params)


def spec_dict(spec: ActionSpec) -> dict[str, Any]:
    return {
        "first": spec.first,
        "names": list(spec.names),
        "required": sorted(spec.required),
        "kwargs": spec.kwargs,
    }


class StubModule(Module):
    """What ``load`` instantiates for a module that runs in a process."""

    _supervisor: ModuleProcesses
    _module_name: str
    _py: Path
    _static_actions: dict[str, inspect.Signature]
    _process: ProcessHandle

    def __init__(self) -> None:
        self._process = self._supervisor.spawn(
            self._module_name, self._py, self.ctx, self._static_actions
        )

    def start(self) -> None:
        self._process.start()

    def stop(self) -> None:
        self._process.stop()

    def reload(self) -> None:
        self._process.send({"t": "reload"})

    def validate_use(self, use: Any) -> None:
        return None  # the process validates every use before start (a ValueError is a finding)

    def use_added(self, use: Any) -> None:
        self._process.send({"t": "use_added", "key": use.key})

    def use_removed(self, use: Any) -> None:
        self._process.send({"t": "use_removed", "rec": use_dict(use)})

    def on_service_lost(self, name: str) -> None:
        self._process.send({"t": "lost", "name": name})

    def on_service_found(self, name: str) -> None:
        self._process.send({"t": "found", "name": name})


def action_method(name: str, signature: inspect.Signature) -> Callable[..., Any]:
    """The stub of one ``@action``. Called for a handler of a shell file it returns at once (the
    process runs it); called for a control call or a shortcut (``Event("call")``) it returns the
    ``Future`` of the answer."""

    def stub(self: StubModule, event: Any, **kw: Any) -> Future[Any] | None:
        caller = self.ctx.caller
        return self._process.call(
            name,
            event_fields(event),
            kw,
            caller.key if caller is not None else None,
            wants_result=getattr(event, "name", "") == "call",
        )

    stub.__name__ = name
    stub.__qualname__ = name
    stub.__tess_action__ = True  # type: ignore[attr-defined]
    stub.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            *signature.parameters.values(),
        ]
    )
    return stub


def build_module(
    supervisor: ModuleProcesses,
    definition: ModuleDef,
    py_path: Path,
    classes: tuple[ClassInfo, ...],
) -> ModuleType:
    """The module object ``ModuleHost.load`` looks into: a stub class for each class of the file
    that extends ``Module`` (the host needs exactly one)."""
    name = f"{PACKAGE}.{definition.name}"
    module = ModuleType(name)
    module.__file__ = str(py_path)
    for cls in classes:
        namespace: dict[str, Any] = {
            "__module__": name,
            "_supervisor": supervisor,
            "_module_name": definition.name,
            "_py": py_path,
            "_static_actions": dict(cls.actions),
        }
        for action, signature in cls.actions.items():
            namespace[action] = action_method(action, signature)
        module.__dict__[cls.name] = type(cls.name, (StubModule,), namespace)
    sys.modules[name] = module
    return module
