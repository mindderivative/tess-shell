"""Hot reload (Hot Reload > The Reload Pipeline).

A change is validated completely on the calling thread (the watcher's, or the signal thread's for
``SIGHUP``): the settings and every shell file are read and checked, exactly as at start. Only a
finished, error-free result crosses to the loop thread with ``call_soon``, which applies the
difference: modules are brought to the new definition, then each Bar is kept (its tree rebuilt by
the keyed diff, its geometry set live) or closed or opened. A file with an error changes nothing
and its errors are reported with ``file:line:column``.
"""

from __future__ import annotations

import dataclasses
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from tess_shell.config.paths import state_dir
from tess_shell.config.registry import Registry
from tess_shell.config.settings import Settings, load_settings
from tess_shell.config.uids import assign_uids
from tess_shell.logging import configure_logging, level_overridden, log_finding
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.modules.host import ModuleHost, ModuleSource, report
from tess_shell.scanner import Scan, build_look, scan, source_line
from tess_shell.schema.findings import Finding, render_findings
from tess_shell.services.shortcuts import Action, ShortcutService
from tess_shell.shortcuts import drop_failed, shortcut_handlers, shortcut_modules
from tess_shell.surfaces.manager import SurfaceManager
from tess_shell.watch import OwnWrites

MAX_FINDINGS = 50


@dataclass(frozen=True, slots=True)
class Outcome:
    """What a reload came to, for the control interface's ``Reload`` and ``Reloaded``: ``ok`` is
    true when it was applied with no error; ``message`` the summary, or the errors in their printed
    form."""

    ok: bool
    message: str


@dataclass(slots=True)
class Prepared:
    """A reload that passed validation, waiting to be applied on the loop thread."""

    result: Scan
    fresh: Settings
    changed: set[Path] | None
    started: float
    names: str


@dataclass(slots=True)
class Rejected:
    """A reload that did not pass validation: nothing changes."""

    findings: list[Finding]
    why: str


@dataclass(slots=True)
class Reloader:
    cfg: Path
    settings: Settings  # what is running; its directories do not change without a restart
    quiet: bool
    registry: Registry
    manager: SurfaceManager
    host: ModuleHost
    store: ValueStore
    own: OwnWrites
    call_soon: Callable[[Callable[[], None]], None]
    scan: Scan | None = None  # the files that are running: what a hot-plug needs to start a module
    file_uids: Mapping[Path, str] = dataclasses.field(default_factory=dict)
    reloads: int = 0
    # told after every reload (the control interface's ``Reloaded`` signal); any thread
    on_reloaded: Callable[[bool, str], None] | None = None
    # the global shortcuts (``services.shortcuts``): told the actions after every reload, or
    # ``None`` when none are made (a test)
    shortcuts: ShortcutService | None = None
    _lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    # -- the calling thread: read, parse, validate ---------------------------------------------

    def trigger(self, changed: set[Path] | None) -> None:
        """Validate the new files and, if they are good, queue the apply. Never raises. ``None``
        means everything changed (``SIGHUP``)."""
        try:
            prepared = self.prepare(changed)
            if isinstance(prepared, Rejected):
                self._reject(prepared)
                return

            def apply() -> None:
                self._apply(prepared)

            self.call_soon(apply)
        except Exception:
            logger.opt(exception=True).error("reload failed; the shell keeps its state")

    def prepare(self, changed: set[Path] | None) -> Prepared | Rejected:
        """Read and check the settings and every shell file, exactly as at start (the calling
        thread blocks; a reload while another is validating waits for it). Applies nothing."""
        with self._lock:
            return self._validate(changed)

    def _validate(self, changed: set[Path] | None) -> Prepared | Rejected:
        started = time.monotonic()
        fresh, findings = load_settings(self.cfg)
        if fresh is None:
            return Rejected(findings, "settings.tdl")
        running = dataclasses.replace(
            self.settings,
            main_shell_path=fresh.main_shell_path,
            appearance=fresh.appearance,
            shortcuts=fresh.shortcuts,
            global_shortcuts=fresh.global_shortcuts,
        )
        result = scan(running, self.cfg)
        if result.errors:
            return Rejected(result.findings, f"{len(result.errors)} errors")
        for f in result.findings[:MAX_FINDINGS]:
            log_finding(f)
        names = ", ".join(sorted(p.name for p in changed)) if changed else "everything"
        return Prepared(result, fresh, changed, started, names)

    def _reject(self, rejected: Rejected) -> Outcome:
        for f in rejected.findings[:MAX_FINDINGS]:
            log_finding(f)
        text, _ = render_findings(rejected.findings, lambda f: source_line(self.cfg, f))
        print(text, file=sys.stderr)
        logger.error(f"reload refused ({rejected.why}); the shell keeps what it shows")
        outcome = Outcome(
            False, f"reload refused ({rejected.why}); the shell keeps what it shows\n{text}"
        )
        self._told(outcome)
        return outcome

    def _told(self, outcome: Outcome) -> None:
        if self.on_reloaded is not None:
            try:
                self.on_reloaded(outcome.ok, outcome.message.split("\n", 1)[0])
            except Exception:
                logger.opt(exception=True).debug("a reload listener raised")

    # -- for the control interface: the same two steps, with the answer ---------------------------

    def validate_for_control(self) -> Prepared | Outcome:
        """``Reload`` (any thread but the loop's: it blocks on the files): the checked reload, or
        the refusal with the errors in their printed form."""
        try:
            prepared = self.prepare(None)
        except Exception as exc:
            logger.opt(exception=True).error("reload failed; the shell keeps its state")
            outcome = Outcome(False, f"reload failed ({exc!r}); the shell keeps its state")
            self._told(outcome)
            return outcome
        if isinstance(prepared, Rejected):
            return self._reject(prepared)
        return prepared

    def apply_for_control(self, prepared: Prepared) -> Outcome:
        """Loop thread: apply what :meth:`validate_for_control` checked and say how it went."""
        return self._apply(prepared)

    # -- the loop thread: apply ---------------------------------------------------------------

    def _source(self, name: str) -> ModuleSource:
        assert self.scan is not None
        mf = self.scan.modules[name]
        tdl = {mf.path}
        if mf.definition.style_file:
            tdl.add(mf.path.parent / mf.definition.style_file)
        uid = self.file_uids.get(mf.path) or self.registry.uid_for(f"module:{name}", "module")
        return ModuleSource(mf.definition, mf.python, uid, frozenset(tdl))

    def sync_uses(self, uses: list[Use]) -> None:
        """A monitor came or went (the manager re-planned): bring the modules to the new uses the
        way a reload does, from the files that are running. No file changed, so no module is
        replaced or told to ``reload``; a module with no use left is stopped, one with its first
        use is started, and each use that came or went is told."""
        if self.scan is None:
            return
        by_module: dict[str, list[Use]] = {}
        for use in uses:
            by_module.setdefault(use.module, []).append(use)
        for name in self.manager.dynamic_module_names():
            by_module.setdefault(name, [])
        for name in shortcut_modules(self.scan.shortcuts):
            by_module.setdefault(name, [])
        sources = {name: self._source(name) for name in by_module if name in self.scan.modules}
        report(self.host.sync(sources, {n: u for n, u in by_module.items() if n in sources}, set()))
        self.store.flush()

    def _settings_changes(self, fresh: Settings) -> None:
        old = self.settings
        if fresh.directories != old.directories or fresh.registry != old.registry:
            logger.warning("settings.tdl: Directories and Registry apply after a restart")
        if fresh.main_shell != old.main_shell:
            logger.warning("settings.tdl: Main_Shell applies after a restart")
        if fresh.debug != old.debug:
            logger.warning("settings.tdl: Debug applies after a restart")
        if fresh.appearance.follow_desktop != old.appearance.follow_desktop:
            logger.warning("settings.tdl: Appearance.Follow_Desktop applies after a restart")
        if fresh.logging != old.logging or level_overridden():  # SetLogLevel lasts to here
            configure_logging(fresh.logging, quiet=self.quiet, default_directory=self.cfg / "logs")
            logger.info("settings.tdl: the logging settings were applied")

    def _apply_shortcuts(
        self, actions: Sequence[Action], fresh: Settings, checked: Sequence[Finding]
    ) -> None:
        """The global shortcuts of the new files: a new action is registered, a changed key
        replaced, a removed action unregistered, an unchanged one left alone (``Global_Shortcuts``
        false makes them all inactive). An action whose ``Call`` the module check refused is not
        registered."""
        if self.shortcuts is not None:
            self.shortcuts.update(drop_failed(actions, checked), fresh.global_shortcuts)

    def _apply(self, prepared: Prepared) -> Outcome:
        try:
            outcome = self._apply_now(prepared)
        except Exception as exc:
            logger.opt(exception=True).error("applying the reload failed; check the Bars")
            outcome = Outcome(False, f"applying the reload failed ({exc!r}); check the Bars")
        self._told(outcome)
        return outcome

    def _apply_now(self, prepared: Prepared) -> Outcome:
        result, fresh, changed = prepared.result, prepared.fresh, prepared.changed
        started, names = prepared.started, prepared.names
        self._settings_changes(fresh)
        shell = result.shells.get(fresh.main_shell_path) if fresh.main_shell_path else None
        if shell is None:
            logger.info("reload: there is no main shell file; nothing to show")
            self._apply_shortcuts(result.shortcuts, fresh, [])
            return Outcome(True, "reloaded: there is no main shell file; nothing to show")
        module_defs = {name: mf.definition for name, mf in result.modules.items()}
        look = build_look(result, fresh, self.manager.look.appearance)
        checked = self.manager.check(shell, module_defs, look)
        if checked is None:
            logger.error("reload refused: a Bar's contents have errors; the shell keeps its state")
            errors = "\n".join(f"{e.origin}: {e.message}" for e in self.manager.check_errors)
            return Outcome(
                False,
                f"reload refused: a Bar's contents have errors; the shell keeps its state\n"
                f"{errors}",
            )
        planned, uses = checked
        own_files = [mf.path for mf in result.modules.values() if not mf.shipped]
        file_uids, problems = assign_uids(
            [*own_files, *result.shells],
            self.cfg,
            lambda key: self.registry.uid_for(key, "file"),
            state_dir() / "backups",
            on_write=self.own.wrote,
        )
        report(problems)
        by_module: dict[str, list[Use]] = {}
        for use in uses:
            by_module.setdefault(use.module, []).append(use)
            self.store.add_use(use.module, use.key)
        for name in self.manager.dynamic_module_names(planned):
            by_module.setdefault(name, [])  # called in a For: loaded, with no use until an entry
        for name in shortcut_modules(result.shortcuts):
            by_module.setdefault(name, [])  # named by a Call shortcut: loaded, with no use
        self.scan, self.file_uids = result, file_uids
        sources = {name: self._source(name) for name in by_module}
        everything = {p for s in sources.values() for p in (s.py_path, *s.tdl_paths)}
        sync_problems = self.host.sync(
            sources, by_module, everything if changed is None else changed
        )
        report(sync_problems)
        handlers = [*self.manager.planned_handlers(planned), *shortcut_handlers(result.shortcuts)]
        checked_calls = self.host.check_calls(handlers)
        report(checked_calls)
        self._apply_shortcuts(result.shortcuts, fresh, checked_calls)
        self.store.flush()  # what modules sent while changing; the Bars below are resolved from it
        self.manager.apply(planned, module_defs, uses, look)
        self.settings = dataclasses.replace(
            self.settings,
            logging=fresh.logging,
            global_shortcuts=fresh.global_shortcuts,
            shortcuts=fresh.shortcuts,
            main_shell_path=fresh.main_shell_path,
            appearance=dataclasses.replace(
                fresh.appearance, follow_desktop=self.settings.appearance.follow_desktop
            ),
        )
        self.reloads += 1
        ms = (time.monotonic() - started) * 1000
        failed = any(f.severity == "error" for f in (*problems, *sync_problems))
        note = " with errors" if failed else ""
        logger.info(f"reloaded{note} ({names}) in {ms:.0f} ms")
        summary = f"reloaded{note} ({names}) in {ms:.0f} ms"
        if not failed:
            return Outcome(True, summary)
        text = "\n".join(
            f"{f.file}:{f.line}:{f.column}: {f.message}"
            for f in (*problems, *sync_problems)
            if f.severity == "error"
        )
        return Outcome(False, f"{summary}\n{text}")
