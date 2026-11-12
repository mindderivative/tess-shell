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
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from tess_shell.config.paths import state_dir
from tess_shell.config.registry import Registry
from tess_shell.config.settings import Settings, load_settings
from tess_shell.config.uids import assign_uids
from tess_shell.logging import configure_logging, log_finding
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.modules.host import ModuleHost, ModuleSource, report
from tess_shell.scanner import Scan, build_look, print_findings, scan
from tess_shell.surfaces.manager import SurfaceManager
from tess_shell.watch import OwnWrites

MAX_FINDINGS = 50


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
    _lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    # -- the calling thread: read, parse, validate ---------------------------------------------

    def trigger(self, changed: set[Path] | None) -> None:
        """Validate the new files and, if they are good, queue the apply. Never raises. ``None``
        means everything changed (``SIGHUP``)."""
        try:
            with self._lock:  # a reload while another is validating waits for it
                self._validate(changed)
        except Exception:
            logger.opt(exception=True).error("reload failed; the shell keeps its state")

    def _validate(self, changed: set[Path] | None) -> None:
        started = time.monotonic()
        fresh, findings = load_settings(self.cfg)
        if fresh is None:
            self._reject(findings, "settings.tdl")
            return
        running = dataclasses.replace(
            self.settings, main_shell_path=fresh.main_shell_path, appearance=fresh.appearance
        )
        result = scan(running, self.cfg)
        if result.errors:
            self._reject(result.findings, f"{len(result.errors)} errors")
            return
        for f in result.findings[:MAX_FINDINGS]:
            log_finding(f)
        names = ", ".join(sorted(p.name for p in changed)) if changed else "everything"
        self.call_soon(lambda: self._apply(result, fresh, changed, started, names))

    def _reject(self, findings: list, why: str) -> None:  # type: ignore[type-arg]
        for f in findings[:MAX_FINDINGS]:
            log_finding(f)
        print_findings(findings, self.cfg)
        logger.error(f"reload refused ({why}); the shell keeps what it shows")

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
        if fresh.logging != old.logging:
            configure_logging(fresh.logging, quiet=self.quiet, default_directory=self.cfg / "logs")
            logger.info("settings.tdl: the logging settings were applied")

    def _apply(
        self,
        result: Scan,
        fresh: Settings,
        changed: set[Path] | None,
        started: float,
        names: str,
    ) -> None:
        try:
            self._apply_now(result, fresh, changed, started, names)
        except Exception:
            logger.opt(exception=True).error("applying the reload failed; check the Bars")

    def _apply_now(
        self,
        result: Scan,
        fresh: Settings,
        changed: set[Path] | None,
        started: float,
        names: str,
    ) -> None:
        self._settings_changes(fresh)
        shell = result.shells.get(fresh.main_shell_path) if fresh.main_shell_path else None
        if shell is None:
            logger.info("reload: there is no main shell file; nothing to show")
            return
        module_defs = {name: mf.definition for name, mf in result.modules.items()}
        look = build_look(result, fresh, self.manager.look.appearance)
        checked = self.manager.check(shell, module_defs, look)
        if checked is None:
            logger.error("reload refused: a Bar's contents have errors; the shell keeps its state")
            return
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
        self.scan, self.file_uids = result, file_uids
        sources = {name: self._source(name) for name in by_module}
        everything = {p for s in sources.values() for p in (s.py_path, *s.tdl_paths)}
        sync_problems = self.host.sync(
            sources, by_module, everything if changed is None else changed
        )
        report(sync_problems)
        report(self.host.check_calls(self.manager.planned_handlers(planned)))
        self.store.flush()  # what modules sent while changing; the Bars below are resolved from it
        self.manager.apply(planned, module_defs, uses, look)
        self.settings = dataclasses.replace(
            self.settings,
            logging=fresh.logging,
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
