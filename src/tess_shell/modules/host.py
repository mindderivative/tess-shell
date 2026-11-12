"""Load a module's Python, create its one instance, call ``start`` and ``stop``, and isolate every
failure (Module Contract > Lifecycle, Failure Modes and Recovery).

Nothing here touches tre. A failure becomes a :class:`Finding` naming the files and, for code that
raised, the line in the module's own file; the other modules keep running.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any

from loguru import logger

from tess_shell.binder import model as m
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.module import Event, Module
from tess_shell.modules.context import ModuleContext, PopupPort, UseRecord
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.blocks import BUILTIN_ACTIONS
from tess_shell.schema.findings import Finding, nearest
from tess_shell.schema.model import ModuleDef
from tess_shell.services.api import DBusPort

PACKAGE = "tess_shell_user_modules"


@dataclass(frozen=True, slots=True)
class ModuleSource:
    """Where a module comes from now: its definition, its Python, its UID, and every TDL file it
    is made of (its own and its style file), so a change to one of them is known."""

    definition: ModuleDef
    py_path: Path
    uid: str
    tdl_paths: frozenset[Path]


@dataclass(slots=True)
class LoadedModule:
    definition: ModuleDef
    py_path: Path
    instance: Module
    ctx: ModuleContext
    state: str = "created"  # created, running, failed, stopped
    uses: list[Use] = field(default_factory=list)


SLOW_ACTION = 0.05  # seconds; a handler runs on the loop thread, so a slow one is logged


def handlers_of(children: tuple[object, ...]) -> list[m.Handler]:
    """Every handler in a layout, inside blocks, ``If`` and ``For`` too."""
    found: list[m.Handler] = []
    for node in children:
        if isinstance(node, m.Node):
            found.extend(node.handlers.values())
            found.extend(handlers_of(node.children))
        elif isinstance(node, m.UseNode):
            found.extend(node.handlers.values())
        elif isinstance(node, m.IfNode):
            found.extend(handlers_of(node.body))
            found.extend(handlers_of(node.else_body or ()))
        elif isinstance(node, m.ForNode):
            found.extend(handlers_of(node.body))
    return found


def actions_of(cls: type) -> list[str]:
    """The names of the methods of ``cls`` marked ``@action``, sorted."""
    return sorted(
        name
        for name, member in inspect.getmembers(cls, callable)
        if getattr(member, "__tess_action__", False)
    )


def _where(exc: BaseException, py_path: Path) -> tuple[int, str]:
    """The line in ``py_path`` where ``exc`` was raised, else the last frame."""
    if isinstance(exc, SyntaxError) and exc.lineno:  # raised while compiling: no frame of its own
        return exc.lineno, str(exc.filename or py_path)
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
        self.popups: PopupPort | None = None  # set by the app once the surfaces exist
        self.dbus: DBusPort | None = None  # set by the app: the D-Bus service layer
        # the uses made for the entries of a For: they come and go while the shell runs, so a
        # reload (which brings the modules to the uses the files give) must not drop them
        self._dynamic: dict[str, Use] = {}

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
        if spec is None:
            return None, self._finding(definition, "module-import", f"cannot import {py_path}")
        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(name)
        sys.modules[name] = module
        try:
            # compiled from the source every time, never from a bytecode cache: a file saved twice
            # in one second at the same size would otherwise load the old code
            code = compile(py_path.read_text(encoding="utf-8"), str(py_path), "exec")
            exec(code, module.__dict__)  # noqa: S102 - this is what loading a module is
        except (Exception, SyntaxError) as exc:
            if previous is not None:
                sys.modules[name] = previous
            else:
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
        actions = actions_of(classes[0])
        clash = [a for a in actions if a in BUILTIN_ACTIONS]
        if clash:
            return None, [
                self._finding(
                    definition,
                    "action-clash",
                    f"the module {definition.name} has an action named like a built-in action "
                    f"({', '.join(clash)})",
                    f"the built-in actions are {', '.join(BUILTIN_ACTIONS)}: rename the method",
                )
            ]
        # a handler of this layout names an action of this module, unless it is a ``Call`` of
        # another one (checked by ``check_calls`` once every module is loaded)
        missing = [
            h
            for h in handlers_of(definition.children)
            if not h.builtin and h.action not in actions and h.module in ("", definition.name)
        ]
        if missing:
            return None, [
                Finding(
                    h.origin.file,
                    h.origin.line,
                    h.origin.column,
                    "error",
                    "unknown-action",
                    f"the module {definition.name} has no action {h.action}",
                    f"its actions: {', '.join(actions)}"
                    if actions
                    else f"mark a method with @action in {py_path.name}",
                )
                for h in missing
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
            lambda: self.popups,
            lambda: self.dbus,
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
        ctx.set_service_hooks(instance.on_service_lost, instance.on_service_found)
        loaded = LoadedModule(definition, py_path, instance, ctx, uses=uses)
        self.loaded[definition.name] = loaded
        return loaded, []

    def check_calls(self, handlers: Sequence[m.Handler]) -> list[Finding]:
        """The ``Call`` handlers among ``handlers`` (the shell's, once the modules are loaded):
        each names a module that is loaded and an ``@action`` it has. A finding for each that does
        not, at the handler, with the nearest names (Events and Actions > Call)."""
        out: list[Finding] = []
        for h in handlers:
            if not h.module or h.builtin:
                continue
            o = h.origin
            loaded = self.loaded.get(h.module)
            if loaded is None:
                out.append(
                    Finding(
                        o.file,
                        o.line,
                        o.column,
                        "error",
                        "call-module-not-loaded",
                        f"Call: the module {h.module} is not loaded, so {h.action} cannot run",
                        "a module loads when a Bar, Panel, Popup or Frame uses it; or its Python "
                        "failed to load (see the errors above)",
                    )
                )
                continue
            actions = actions_of(type(loaded.instance))
            if h.action not in actions:
                close = nearest(h.action, actions)
                out.append(
                    Finding(
                        o.file,
                        o.line,
                        o.column,
                        "error",
                        "unknown-action",
                        f"Call: the module {h.module} has no action {h.action}",
                        f"did you mean {', '.join(close)}?"
                        if close
                        else (
                            f"its actions: {', '.join(actions)}"
                            if actions
                            else f"mark a method with @action in {loaded.py_path.name}"
                        ),
                    )
                )
        return out

    # -- events ---------------------------------------------------------------------------------

    def dispatch(self, handler: m.Handler, key: str, raw: object) -> None:
        """Loop thread: a node raised ``key``; call the module's action with an :class:`Event`.
        A handler that raises is logged with the module, the event and the block's position, and
        is not repeated; the shell keeps running. A ``Call`` names its module; any other action
        is one of the module that holds the block."""
        module = handler.module or handler.use.split("@", 1)[0]
        loaded = self.loaded.get(module)
        if loaded is None or loaded.state != "running":
            logger.debug(f"{key} for {module}, which is not running: ignored")
            return
        fn = getattr(loaded.instance, handler.action, None)
        if not callable(fn) or not getattr(fn, "__tess_action__", False):
            logger.error(f"{handler.origin}: {module} has no action {handler.action}")
            return
        event = Event(
            key.removeprefix("On_").lower(),
            handler.use,
            handler.args,
            x=getattr(raw, "window_x", None),
            y=getattr(raw, "window_y", None),
            button=getattr(raw, "button", None),
            old=getattr(raw, "old_value", None),
            new=getattr(raw, "new_value", None),
            text=getattr(raw, "text", None),
            value=getattr(raw, "value", None),
        )
        started = time.monotonic()
        loaded.ctx.caller = loaded.ctx.uses.get(handler.use)  # what ctx.popup() calls from
        try:
            fn(event)
        except Exception:
            logger.opt(exception=True).error(
                f"{handler.origin}: {module}.{handler.action} raised on {key}"
            )
        finally:
            loaded.ctx.caller = None
        took = time.monotonic() - started
        if took > SLOW_ACTION:
            logger.warning(
                f"{handler.origin}: {module}.{handler.action} took {took * 1000:.0f} ms on the loop"
            )

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

    # -- reload ---------------------------------------------------------------------------------

    def _records(self, uses: list[Use]) -> dict[str, UseRecord]:
        return {
            u.key: UseRecord(u.key, u.name, u.key.split("@", 1)[1], u.monitor, dict(u.params))
            for u in uses
        }

    def _sync_uses(self, loaded: LoadedModule, uses: list[Use]) -> list[Finding]:
        """Bring ``ctx.uses`` to ``uses`` and tell the module: ``use_removed``, ``use_added`` and
        ``validate_use`` for a use whose params changed."""
        findings: list[Finding] = []
        new = self._records(uses)
        current = loaded.ctx.uses
        assert isinstance(current, dict)
        for key in [k for k in current if k not in new]:
            record = current.pop(key)
            found = self._call(loaded, "use_removed", partial(loaded.instance.use_removed, record))
            if found is not None:
                findings.append(found)
        for key, record in new.items():
            had = current.get(key)
            current[key] = record
            if had is not None and had.params == record.params:
                continue
            try:
                loaded.instance.validate_use(record)
            except ValueError as exc:
                findings.append(
                    self._finding(loaded.definition, "module-use", f"{record.name}: {exc}")
                )
            if had is None and loaded.state == "running":
                loaded.ctx.send_available(record)  # the layer sent it to the uses that existed
                found = self._call(loaded, "use_added", partial(loaded.instance.use_added, record))
                if found is not None:
                    findings.append(found)
        loaded.uses = uses
        return findings

    def _replace(self, old: LoadedModule, src: ModuleSource, uses: list[Use]) -> list[Finding]:
        """The module's Python changed: import the new code first; only if that works stop the old
        instance (Module Contract > Lifecycle, code reload)."""
        new, problems = self.load(src.definition, src.py_path, src.uid, uses)
        if new is None:
            self.loaded[src.definition.name] = old  # the old instance keeps running
            return problems
        if old.state == "running":
            found = self._call(old, "stop", old.instance.stop)
            if found is not None:
                logger.error(f"{found.file}:{found.line}: {found.message}")
        old.ctx.close()
        old.state = "stopped"
        logger.info(f"module {src.definition.name}: the code was replaced")
        return [*problems, *self.start(new)]

    def sync(
        self,
        sources: Mapping[str, ModuleSource],
        uses_by_module: Mapping[str, list[Use]],
        changed: set[Path],
    ) -> list[Finding]:
        """Bring the running modules to a new shell definition (Hot Reload > What is Applied
        Live): a module no longer used is stopped; a new one is loaded and started; a changed
        ``.py`` replaces the instance; a changed TDL file calls ``reload()`` and keeps it."""
        findings: list[Finding] = []
        resolved = {p.resolve() for p in changed}
        for name in [n for n in self.loaded if n not in uses_by_module]:
            gone = self.loaded.pop(name)
            if gone.state == "running":
                self._call(gone, "stop", gone.instance.stop)
            gone.ctx.close()
            gone.state = "stopped"
            logger.info(f"module {name}: no longer used, stopped")
        for name, given in uses_by_module.items():
            uses = self._with_dynamic(name, given)
            src = sources[name]
            old = self.loaded.get(name)
            if old is None:
                loaded, problems = self.load(src.definition, src.py_path, src.uid, uses)
                findings.extend(problems)
                if loaded is not None:
                    findings.extend(self.start(loaded))
                continue
            if src.py_path.resolve() in resolved or old.state == "failed":
                findings.extend(self._replace(old, src, uses))
                continue
            old.definition = src.definition
            findings.extend(self._sync_uses(old, uses))
            if {p.resolve() for p in src.tdl_paths} & resolved and old.state == "running":
                found = self._call(old, "reload", old.instance.reload)
                if found is not None:
                    findings.append(found)
        return findings

    def dynamic(self, added: Sequence[Use], removed: Sequence[str]) -> list[Finding]:
        """Uses made for the entries of a ``For`` came or went: tell their modules the way a use
        that appears or goes away in a reload is told (``use_added``, ``use_removed``)."""
        before = set(self._dynamic)
        for use in added:
            logger.debug(f"module {use.module}: a use of an entry came: {use.key}")
        for key in removed:
            logger.debug(f"module {key.split('@', 1)[0]}: the use of an entry ended: {key}")
        touched: set[str] = set()
        for key in removed:
            gone = self._dynamic.pop(key, None)
            if gone is not None:
                touched.add(gone.module)
        for use in added:
            self._dynamic[use.key] = use
            touched.add(use.module)
        findings: list[Finding] = []
        for name in touched:
            loaded = self.loaded.get(name)
            if loaded is None:
                logger.warning(f"module {name} is called in a For but is not loaded")
                continue
            keep = [u for u in loaded.uses if u.key not in before]  # the uses the files give
            keep += [u for u in self._dynamic.values() if u.module == name]
            findings.extend(self._sync_uses(loaded, keep))
        return findings

    def _with_dynamic(self, name: str, uses: list[Use]) -> list[Use]:
        return [*uses, *(u for u in self._dynamic.values() if u.module == name)]

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
