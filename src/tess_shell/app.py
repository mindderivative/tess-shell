"""``tesserae-shell run``: the start and stop sequences (Shell Start and Stop).

M0 builds steps 1 to 7 and 9 of the start sequence and the stop sequence for what exists. The
resolve and compile step, the model, the surfaces and the modules are logged as not built.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from types import TracebackType
from typing import NoReturn

from loguru import logger
from tess_dl import Document

import tess_shell
from tess_shell.config.discovery import discover, is_shipped
from tess_shell.config.lock import InstanceLock
from tess_shell.config.paths import check_runtime_dir, config_dir, ensure_config_dir, state_dir
from tess_shell.config.registry import Registry, RegistryError
from tess_shell.config.settings import LoggingSettings, Settings, load_settings
from tess_shell.config.uids import assign_uids
from tess_shell.exit_codes import EnvironmentFailure, ExitCode, ShellError
from tess_shell.files.icons import IconSets
from tess_shell.files.loader import (
    ModuleFile,
    display_name,
    load_file,
    load_module_document,
    load_shell_file,
    load_style_file,
    register_module,
)
from tess_shell.logging import (
    configure_logging,
    current_state,
    log_finding,
    shutdown_logging,
)
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.modules.host import ModuleHost, report
from tess_shell.modules.ticks import TimeSource
from tess_shell.options import Options
from tess_shell.schema.findings import Finding, render_findings
from tess_shell.schema.graph import module_cycles
from tess_shell.schema.model import ShellDef, StyleDef
from tess_shell.schema.shell import read_module, read_module_params
from tess_shell.signals import LoopStopper, SignalWatcher
from tess_shell.surfaces.manager import SurfaceManager

MIN_ENGINE = (0, 6, 0)
MIN_PYTHON = (3, 14)


def source_line(config: Path, finding: Finding) -> str | None:
    path = Path(finding.file)
    if not path.is_absolute():
        path = config / path
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError, UnicodeDecodeError:
        return None
    return lines[finding.line - 1] if 0 < finding.line <= len(lines) else None


def print_findings(findings: list[Finding], config: Path) -> None:
    text, _ = render_findings(findings, lambda f: source_line(config, f))
    print(text, file=sys.stderr)


MAX_FINDINGS = 50


def installed_versions() -> dict[str, str]:
    """The versions a file's ``Shell:``, ``TRE:`` and ``TEL:`` pins are compared with."""
    import tess_el

    return {
        "Shell": tess_shell.__version__,
        "TRE": version("tesserae-engine"),
        "TEL": tess_el.__version__,
    }


@dataclass(frozen=True, slots=True)
class Scan:
    count: int
    findings: list[Finding]
    shells: dict[Path, ShellDef]
    modules: dict[str, ModuleFile]

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]


def scan(settings: Settings, config: Path) -> Scan:
    """Discover every shell file and check it: modules first, so a shell file can call them; a
    ``*_Shell.tdl`` through stages 1 to 4, the other types for syntax only. Warnings do not stop
    anything."""
    paths = discover(settings)
    versions = installed_versions()
    findings: list[Finding] = []
    shells: dict[Path, ShellDef] = {}
    modules: dict[str, ModuleFile] = {}
    icons = IconSets(settings.directories.get("Icons", ()))
    # pass 1: every module's name and params, so a layout can call any module in any order
    documents: dict[Path, Document] = {}
    for path in paths:
        if path.name.endswith("_Module.tdl"):
            document, found = load_module_document(path, config, versions)
            findings.extend(found)
            if document is None:
                continue
            documents[path] = document
            stub = read_module_params(document, display_name(path, config))
            if stub is not None:
                findings.extend(
                    register_module(modules, ModuleFile(stub, path, is_shipped(path)), config)
                )
    stubs = {name: mf.definition for name, mf in modules.items()}
    names_by_path = {mf.path.resolve(): name for name, mf in modules.items()}

    def importer(file: Path) -> Callable[[str], str | None]:
        return lambda text: names_by_path.get((file.parent / text).resolve())

    styles: dict[Path, StyleDef | None] = {}

    def style_loader(module_path: Path) -> Callable[[str], StyleDef | None]:
        def load(text: str) -> StyleDef | None:
            path = (module_path.parent / text).resolve()
            if path not in styles:
                styles[path], found = load_style_file(path, config, versions)
                findings.extend(found)
            return styles[path]

        return load

    # pass 2: the layouts, with every module known
    for name, mf in list(modules.items()):
        full, found = read_module(
            documents[mf.path],
            display_name(mf.path, config),
            stubs,
            importer(mf.path),
            style_loader(mf.path),
            icons,
        )
        findings.extend(found)
        modules[name] = ModuleFile(full, mf.path, mf.shipped) if full else mf
        if full is None:
            del modules[name]
    findings.extend(module_cycles({n: mf.definition for n, mf in modules.items()}))
    registry = {name: mf.definition for name, mf in modules.items()}
    for path in paths:
        if path.name.endswith("_Shell.tdl"):
            shell, found = load_shell_file(path, config, versions, registry, importer(path), icons)
            if shell is not None:
                shells[path] = shell
            findings.extend(found)
        elif not path.name.endswith("_Module.tdl"):
            _, found = load_file(path, config)
            findings.extend(found)
    findings.extend(
        Finding("Icons", 1, 1, "warning", "icon-set-invalid", problem, "the set is skipped")
        for problem in icons.problems
    )
    own = sum(1 for path in paths if not is_shipped(path))  # the user's files, not the shipped ones
    return Scan(own, sorted(findings, key=lambda f: f.sort_key), shells, modules)


def check(options: Options) -> int:
    """``tesserae-shell check``: settings, then every shell file, and nothing is created."""
    config = config_dir(options.config_dir)
    if not config.is_dir():
        print(f"tesserae-shell: config directory does not exist: {config}", file=sys.stderr)
        return int(ExitCode.ENVIRONMENT)
    settings, findings = load_settings(config)
    count = 0
    if settings is not None:
        result = scan(settings, config)
        count, findings = result.count, result.findings
    failed = any(f.severity == "error" for f in findings)
    if options.json:
        shown = findings[:MAX_FINDINGS]
        print(
            json.dumps(
                {
                    "ok": not failed,
                    "files": count,
                    "errors": [f.to_dict() for f in shown],
                    "omitted": len(findings) - len(shown),
                }
            )
        )
    else:
        if findings:
            print_findings(findings, config)
        if not failed and not options.quiet:
            print(f"ok: {count} files checked")
    return int(ExitCode.CONFIG if failed else ExitCode.OK)


def _preflight() -> tuple[Path, bool]:
    if sys.version_info < MIN_PYTHON:
        raise EnvironmentFailure("tesserae-shell needs Python 3.14 or newer")
    engine = tuple(int(p) for p in version("tesserae-engine").split(".")[:3] if p.isdigit())
    if engine < MIN_ENGINE:
        raise EnvironmentFailure(
            f"tesserae-engine {version('tesserae-engine')} is too old; 0.6.0 or newer is needed"
        )
    runtime = check_runtime_dir()
    import tess_re

    try:
        has_layer_shell = tess_re.supports("layer_shell")
    except Exception:
        has_layer_shell = False
    if not has_layer_shell:
        raise EnvironmentFailure(
            "no Wayland compositor with layer-shell "
            f"(WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')})"
        )
    return runtime


def _install_excepthooks() -> None:
    def hook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        logger.opt(exception=(exc_type, exc, tb)).critical("unhandled exception")

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is not SystemExit and args.exc_value is not None:
            logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).critical(
                f"unhandled exception in thread {args.thread.name if args.thread else '?'}"
            )

    sys.excepthook = hook
    threading.excepthook = thread_hook


def _fail(message: str) -> None:
    """Report a one-line failure: on stderr, and in the log once logging runs."""
    state = current_state()
    if state is None:
        print(f"tesserae-shell: {message}", file=sys.stderr)
        return
    logger.error(message)
    if state.console_sink is None:
        print(f"tesserae-shell: {message}", file=sys.stderr)


def run(options: Options) -> int:
    lock = InstanceLock()
    try:
        _install_excepthooks()
        return int(_run(options, lock))
    except ShellError as exc:
        _fail(str(exc))
        return int(exc.exit_code)
    except KeyboardInterrupt:
        return int(ExitCode.FORCED)
    except Exception as exc:
        if current_state() is None:
            print(f"tesserae-shell: unexpected error: {exc!r}", file=sys.stderr)
        else:
            logger.opt(exception=True).critical("unexpected error")
        return int(ExitCode.INTERNAL)
    finally:
        shutdown_logging()
        lock.release()


def _run(options: Options, lock: InstanceLock) -> ExitCode:
    # 1. pre-flight
    runtime_dir, loose = _preflight()
    # 2. the config directory
    cfg = config_dir(options.config_dir)
    ensure_config_dir(cfg)
    # 3. settings
    settings, findings = load_settings(cfg)
    if settings is None:
        configure_logging(LoggingSettings(console=False), default_directory=cfg / "logs")
        for f in findings:
            log_finding(f)
        print_findings(findings, cfg)
        return ExitCode.CONFIG
    # 4. logging
    configure_logging(settings.logging, quiet=options.quiet, default_directory=cfg / "logs")
    logger.info(f"starting tesserae-shell {tess_shell.__version__} (config {cfg})")
    if loose:
        logger.warning(f"{runtime_dir} is not mode 0700")
    # 5. the instance lock
    lock.acquire(runtime_dir)
    if lock.sticky_refused:
        logger.warning("the lock file could not be given the sticky bit")
    # 6. the registry
    try:
        registry = Registry.open(settings.registry)
    except RegistryError as exc:
        log_finding(exc.finding)
        print_findings([exc.finding], cfg)
        return ExitCode.CONFIG
    # 7. check and load every shell file
    result = scan(settings, cfg)
    for f in result.findings[:MAX_FINDINGS]:
        log_finding(f)
    if result.findings:
        print_findings(result.findings, cfg)
    if result.errors:
        return ExitCode.CONFIG
    logger.info(f"loaded {result.count} shell files")
    if settings.main_shell_path is None:
        logger.info(f"no {settings.main_shell} found; nothing to show")
    # 8. resolve and compile
    logger.info("step 8 (resolve and compile): not built in M0")
    # 9. the engine and its loop
    import tess_re

    app = tess_re.App()
    handle = app.thread_handle()
    stopper = LoopStopper(handle.stop)

    def force() -> NoReturn:
        shutdown_logging()
        os._exit(int(ExitCode.FORCED))

    watcher = SignalWatcher(stopper.request, force)
    watcher.start()
    try:
        store = ValueStore()
        ticks = TimeSource()
        shell = result.shells.get(settings.main_shell_path) if settings.main_shell_path else None
        module_defs = {name: mf.definition for name, mf in result.modules.items()}
        manager = SurfaceManager(app, module_defs, registry.uid_for, store)
        host = ModuleHost(store, ticks, cfg)
        # a file the shell registers for the first time gets a UID in its metadata (G8)
        own_files = [mf.path for mf in result.modules.values() if not mf.shipped]
        file_uids, uid_problems = assign_uids(
            [*own_files, *result.shells],
            cfg,
            lambda key: registry.uid_for(key, "file"),
            state_dir() / "backups",
        )
        report(uid_problems)
        # 10. model: expand the module calls, load and start each module that is used
        uses = manager.plan(shell) if shell is not None else []
        by_module: dict[str, list[Use]] = {}
        for use in uses:
            by_module.setdefault(use.module, []).append(use)
        for name, module_uses in by_module.items():
            mf = result.modules[name]
            uid = file_uids.get(mf.path) or registry.uid_for(f"module:{name}", "module")
            _, problems = host.load(mf.definition, mf.python, uid, module_uses)
            report(problems)
        report(host.start_all())
        store.flush()  # what the modules sent while starting, before the first build
        logger.info(f"step 10 (model): {len(uses)} module uses, {len(host.loaded)} modules")
        # 11. surfaces
        manager.build()
        logger.info(f"step 11 (surfaces): {len(manager.surfaces)} opened")
        store.on_change = manager.on_change
        store.attach_loop(handle.call_soon)
        ticks.start(handle.call_soon)
        logger.info("step 12 (modules): started")
        logger.info("running")
        try:
            app.run(keep_alive=True)
        finally:
            stopper.loop_finished()
        if not stopper.requested.is_set():
            _fail("event loop ended without a stop request")
            return ExitCode.ENVIRONMENT
        # stop sequence: modules, then the time source (no D-Bus yet)
        logger.info("stopping")
        host.stop_all()
        ticks.close()
        try:
            registry.save()
        except OSError as exc:
            _fail(f"cannot save the registry: {exc}")
            return ExitCode.CONFIG
        logger.info("stopped")
        return ExitCode.OK
    finally:
        watcher.close()
