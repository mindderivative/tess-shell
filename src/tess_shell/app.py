"""``tesserae-shell run``: the start and stop sequences (Shell Start and Stop).

M0 builds steps 1 to 7 and 9 of the start sequence and the stop sequence for what exists. The
resolve and compile step, the model, the surfaces and the modules are logged as not built.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from types import TracebackType
from typing import NoReturn

from loguru import logger

import tess_shell
from tess_shell.config.discovery import discover
from tess_shell.config.lock import InstanceLock
from tess_shell.config.paths import check_runtime_dir, config_dir, ensure_config_dir
from tess_shell.config.registry import Registry, RegistryError
from tess_shell.config.settings import LoggingSettings, Settings, load_settings
from tess_shell.exit_codes import EnvironmentFailure, ExitCode, ShellError
from tess_shell.files.loader import load_file, load_shell_file
from tess_shell.logging import (
    configure_logging,
    current_state,
    log_finding,
    shutdown_logging,
)
from tess_shell.options import Options
from tess_shell.schema.findings import Finding, render_findings
from tess_shell.schema.model import ShellDef
from tess_shell.signals import LoopStopper, SignalWatcher

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

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]


def scan(settings: Settings, config: Path) -> Scan:
    """Discover every shell file and check it: a ``*_Shell.tdl`` through stages 1 to 4, the other
    types for syntax only. Warnings do not stop anything."""
    paths = discover(settings)
    versions = installed_versions()
    findings: list[Finding] = []
    shells: dict[Path, ShellDef] = {}
    for path in paths:
        if path.name.endswith("_Shell.tdl"):
            shell, found = load_shell_file(path, config, versions)
            if shell is not None:
                shells[path] = shell
        else:
            _, found = load_file(path, config)
        findings.extend(found)
    return Scan(len(paths), sorted(findings, key=lambda f: f.sort_key), shells)


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
        for step, what in ((10, "model"), (11, "surfaces"), (12, "modules")):
            logger.info(f"step {step} ({what}): not built in M0")
        logger.info("running")
        try:
            app.run(keep_alive=True)
        finally:
            stopper.loop_finished()
        if not stopper.requested.is_set():
            _fail("event loop ended without a stop request")
            return ExitCode.ENVIRONMENT
        # stop sequence: no modules and no D-Bus yet
        logger.info("stopping")
        try:
            registry.save()
        except OSError as exc:
            _fail(f"cannot save the registry: {exc}")
            return ExitCode.CONFIG
        logger.info("stopped")
        return ExitCode.OK
    finally:
        watcher.close()
