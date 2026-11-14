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
from typing import Any, NoReturn

from loguru import logger

import tess_shell
from tess_shell.appearance import Appearance
from tess_shell.binder.images import IMAGES
from tess_shell.binder.model import Handler
from tess_shell.commands import ShellCommands
from tess_shell.config.lock import InstanceLock
from tess_shell.config.paths import check_runtime_dir, config_dir, ensure_config_dir, state_dir
from tess_shell.config.registry import Registry, RegistryError
from tess_shell.config.settings import LoggingSettings, Settings, load_settings
from tess_shell.config.uids import assign_uids
from tess_shell.exit_codes import EnvironmentFailure, ExitCode, ShellError
from tess_shell.logging import (
    configure_logging,
    current_state,
    finding_sinks,
    log_finding,
    note_module_error,
    shutdown_logging,
)
from tess_shell.model.store import ValueStore
from tess_shell.model.uses import Use
from tess_shell.modules.host import ModuleHost, report
from tess_shell.modules.ticks import TimeSource
from tess_shell.options import Options
from tess_shell.reloader import Reloader
from tess_shell.scanner import MAX_FINDINGS, build_look, print_findings, scan
from tess_shell.schema.findings import Finding
from tess_shell.services.api import ServiceUnavailable
from tess_shell.services.audio import AudioService
from tess_shell.services.bus import ServiceThread
from tess_shell.services.control import NAME, ControlService, ErrorLog
from tess_shell.services.icons import IconService
from tess_shell.services.layer import Layer
from tess_shell.services.portal import PortalReader
from tess_shell.services.shortcuts import STOP_TIMEOUT, Action, ShortcutService
from tess_shell.services.tray import TrayService
from tess_shell.shortcuts import drop_failed, shortcut_handlers
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
                    "config_dir": str(config),
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


def _start_control(
    service: ServiceThread,
    handle: Any,
    manager: SurfaceManager,
    reloader: Reloader,
    commands: ShellCommands,
    errors: ErrorLog,
) -> ControlService | None:
    """Export the control interface and own its bus name (Shell Start and Stop). ``None`` when
    the session bus cannot be reached: the shell runs without control commands and says so."""
    control = ControlService(service, handle.call_soon, commands, tess_shell.__version__, errors)
    try:
        service.submit(control.start()).result(timeout=START_TIMEOUT)
    except (ServiceUnavailable, TimeoutError, OSError) as exc:
        logger.info(f"control: no commands: the session bus is not reachable ({exc})")
        return None
    except Exception as exc:
        logger.opt(exception=True).warning(f"control: no commands ({exc!r})")
        return None
    if control.owned:
        reloader.on_reloaded = control.reloaded
        manager.on_surface = control.surface_changed
        finding_sinks.append(control.error_reported)
        logger.info(f"control: owning {NAME}")
    return control


def _stop_control(service: ServiceThread, control: ControlService) -> None:
    if control.error_reported in finding_sinks:
        finding_sinks.remove(control.error_reported)
    try:
        service.submit(control.stop()).result(timeout=START_TIMEOUT)
    except Exception as exc:
        logger.debug(f"control: stopping did not go through ({exc!r})")


START_TIMEOUT = 6.0  # seconds the shell waits for the bus when it takes its name


def _start_shortcuts(
    service: ServiceThread,
    handle: Any,
    commands: ShellCommands,
    call_problems: list[Finding],
    declared: tuple[Action, ...],
    settings: Settings,
) -> ShortcutService:
    """Register the shell's global shortcuts with the desktop's shortcut service, after the
    shell's own bus name is owned and before the surfaces are shown (Global Shortcuts >
    Registration). A missing service or a refused call is a warning and no keys: the shell runs and
    the commands work."""
    shortcuts = ShortcutService(service, handle.call_soon, commands.press)
    actions = drop_failed(declared, call_problems)
    try:
        service.submit(shortcuts.start(actions, settings.global_shortcuts)).result(
            timeout=START_TIMEOUT
        )
    except Exception as exc:
        logger.opt(exception=True).warning(f"shortcuts: no global keys ({exc!r})")
    else:
        if settings.global_shortcuts:
            logger.info(
                f"shortcuts: {len(shortcuts.registered)} of {len(actions)} actions registered"
            )
    return shortcuts


def _stop_shortcuts(service: ServiceThread, shortcuts: ShortcutService) -> None:
    try:
        service.submit(shortcuts.stop()).result(timeout=STOP_TIMEOUT + 0.5)
    except Exception as exc:
        logger.debug(f"shortcuts: stopping did not go through ({exc!r})")


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
        # the D-Bus service thread: one thread, started now, that connects to nothing until a
        # module or the portal reader uses a bus
        service = ServiceThread()
        service.start()
        layer = Layer(service, handle.call_soon)
        layer.on_module_error = note_module_error
        portal: PortalReader | None = None
        appearance = Appearance()
        manager_box: list[SurfaceManager] = []

        def appearance_changed(new: Appearance) -> None:  # on the service thread
            def apply() -> None:
                manager_box[0].set_look(manager_box[0].look.with_appearance(new))

            handle.call_soon(apply)

        if settings.appearance.follow_desktop:
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
            blend_mode=settings.debug.frame_blend,
        )
        manager_box.append(manager)
        host = ModuleHost(store, ticks, cfg)

        def route(handler: Handler, key: str, raw: object) -> None:
            # a shell action (Show, Hide, Toggle) is the manager's; any other name is an @action
            if handler.builtin:
                manager.run_builtin(handler, raw)
            else:
                host.dispatch(handler, key, raw)

        manager.sink = route
        host.popups = manager.popups  # ctx.popup() opens a Popup of the surfaces
        host.dbus = layer  # ctx.dbus: the D-Bus service layer
        host.audio = AudioService(service)  # ctx.audio: the sound server, on the same thread
        host.icons = IconService(IMAGES.register)  # ctx.icons: the theme lookup, files read here
        host.tray = TrayService(service)  # ctx.tray: the shell as a StatusNotifier host
        host.call_soon = handle.call_soon  # ctx.call_soon: back to the loop thread
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
        for name in manager.dynamic_module_names():
            by_module.setdefault(name, [])  # called in a For: loaded, with no use until an entry
        for name, module_uses in by_module.items():
            mf = result.modules[name]
            uid = file_uids.get(mf.path) or registry.uid_for(f"module:{name}", "module")
            _, problems = host.load(mf.definition, mf.python, uid, module_uses)
            report(problems)
        # every Call names a loaded action, the shortcuts' too
        call_problems = host.check_calls(
            [*manager.planned_handlers(), *shortcut_handlers(result.shortcuts)]
        )
        report(call_problems)
        report(host.start_all())
        store.flush()  # what the modules sent while starting, before the first build
        logger.info(f"step 10 (model): {len(uses)} module uses, {len(host.loaded)} modules")
        # 11. surfaces
        # the entries of a For make uses while the surfaces are built: the modules hear of them
        manager.dynamic_sink = lambda added, removed: report(host.dynamic(added, removed))
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
        control: ControlService | None = None
        shortcuts: ShortcutService | None = None
        errors = ErrorLog()
        commands = ShellCommands(manager, host, reloader, stopper.request, errors.last)
        taken = False
        if settings.control:
            control = _start_control(service, handle, manager, reloader, commands, errors)
            taken = control is not None and not control.owned
        if taken:
            _fail(
                f"the bus name {NAME} is owned: another tesserae-shell is running on this "
                "session bus"
            )
            stopper.loop_finished()
            if file_watcher is not None:
                file_watcher.stop()
        else:
            shortcuts = _start_shortcuts(
                service, handle, commands, call_problems, result.shortcuts, settings
            )
            reloader.shortcuts = shortcuts
            logger.info("running")
            if control is not None:
                control.set_state("running")
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
        if shortcuts is not None:
            shortcuts.begin_stop()  # a press from here on is dropped
        if control is not None:
            control.set_state("stopping")
            _stop_control(service, control)
        if shortcuts is not None:
            _stop_shortcuts(service, shortcuts)
        host.stop_all()
        ticks.close()
        if portal is not None:
            portal.stop()
        service.stop()
        try:
            registry.save()
        except OSError as exc:
            _fail(f"cannot save the registry: {exc}")
            return ExitCode.CONFIG
        logger.info("stopped")
        return ExitCode.ALREADY_RUNNING if taken else ExitCode.OK
    finally:
        watcher.close()
