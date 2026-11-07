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
from importlib.metadata import version
from pathlib import Path
from types import TracebackType
from typing import NoReturn

from loguru import logger

import tess_shell
from tess_shell.appearance import Appearance
from tess_shell.binder.model import Handler
from tess_shell.config.lock import InstanceLock
from tess_shell.config.paths import check_runtime_dir, config_dir, ensure_config_dir, state_dir
from tess_shell.config.registry import Registry, RegistryError
from tess_shell.config.settings import LoggingSettings, load_settings
from tess_shell.config.uids import assign_uids
from tess_shell.exit_codes import EnvironmentFailure, ExitCode, ShellError
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
from tess_shell.reloader import Reloader
from tess_shell.scanner import MAX_FINDINGS, build_look, print_findings, scan
from tess_shell.services.bus import ServiceThread
from tess_shell.services.portal import PortalReader
from tess_shell.signals import LoopStopper, SignalWatcher
from tess_shell.surfaces.manager import SurfaceManager
from tess_shell.watch import OwnWrites, Watcher

MIN_ENGINE = (0, 6, 0)
MIN_PYTHON = (3, 14)


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

    reload_signal: list[Callable[[], None]] = []
    watcher = SignalWatcher(
        stopper.request, force, lambda: reload_signal[-1]() if reload_signal else None
    )
    watcher.start()
    try:
        store = ValueStore()
        ticks = TimeSource()
        shell = result.shells.get(settings.main_shell_path) if settings.main_shell_path else None
        module_defs = {name: mf.definition for name, mf in result.modules.items()}
        # the desktop's look: one read of the Settings portal, on the D-Bus thread; a slow or
        # missing portal gives the defaults and never delays the surfaces
        service: ServiceThread | None = None
        portal: PortalReader | None = None
        appearance = Appearance()
        manager_box: list[SurfaceManager] = []

        def appearance_changed(new: Appearance) -> None:  # on the service thread
            def apply() -> None:
                manager_box[0].set_look(manager_box[0].look.with_appearance(new))

            handle.call_soon(apply)

        if settings.appearance.follow_desktop:
            service = ServiceThread()
            service.start()
            portal = PortalReader(service, appearance_changed)
            portal.start()
            appearance = portal.first()
        else:
            logger.debug("Appearance.Follow_Desktop is false: the portal is not read")
        look = build_look(result, settings, appearance)
        manager = SurfaceManager(
            app,
            module_defs,
            registry.uid_for,
            store,
            look,
            hide_mode=settings.debug.panel_hide,
            positions=registry,
            join_mode=settings.debug.frame_join,
        )
        manager_box.append(manager)
        host = ModuleHost(store, ticks, cfg)

        def route(handler: Handler, key: str, raw: object) -> None:
            # a shell action (Show, Hide, Toggle) is the manager's; any other name is an @action
            if handler.builtin:
                manager.run_builtin(handler)
            else:
                host.dispatch(handler, key, raw)

        manager.sink = route
        host.popups = manager.popups  # ctx.popup() opens a Popup of the surfaces
        # a file the shell registers for the first time gets a UID in its metadata (G8)
        own_files = [mf.path for mf in result.modules.values() if not mf.shipped]
        own_writes = OwnWrites()
        file_uids, uid_problems = assign_uids(
            [*own_files, *result.shells],
            cfg,
            lambda key: registry.uid_for(key, "file"),
            state_dir() / "backups",
            on_write=own_writes.wrote,
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
        reloader = Reloader(
            cfg,
            settings,
            options.quiet,
            registry,
            manager,
            host,
            store,
            own_writes,
            handle.call_soon,
            result,
            file_uids,
        )
        reload_signal.append(lambda: reloader.trigger(None))
        manager.sync_uses = reloader.sync_uses  # a monitor that comes or goes changes the uses
        manager.hotplug.start()  # output_added, output_removed, output_updated
        files = None
        file_watcher: Watcher | None = None
        if settings.hot_reload:
            trees = {d for folder, dirs in settings.directories.items() for d in dirs if d.is_dir()}
            files = {cfg: frozenset({"settings.tdl"})}
            file_watcher = Watcher(
                trees,
                reloader.trigger,
                files=files,
                debounce=settings.reload_debounce,
                is_own=own_writes.is_own,
            )
            own_writes.clear()  # the writes of the start made no event: nothing to drop yet
            file_watcher.start()
            if not file_watcher.ok:
                logger.warning("some folders are not watched; SIGHUP still reloads everything")
        logger.info("running")
        try:
            app.run(keep_alive=True)
        finally:
            stopper.loop_finished()
            if file_watcher is not None:
                file_watcher.stop()
        if not stopper.requested.is_set():
            _fail("event loop ended without a stop request")
            return ExitCode.ENVIRONMENT
        # stop sequence: modules, then the time source (no D-Bus yet)
        logger.info("stopping")
        host.stop_all()
        ticks.close()
        if portal is not None:
            portal.stop()
        if service is not None:
            service.stop()
        try:
            registry.save()
        except OSError as exc:
            _fail(f"cannot save the registry: {exc}")
            return ExitCode.CONFIG
        logger.info("stopped")
        return ExitCode.OK
    finally:
        watcher.close()
