"""``tesserae-shell migrate``: bring a configuration folder's files to the current format.

Version Policy and Migration, "The ``migrate`` Command". The files are read, every step is applied
in memory in order, and only then does anything touch the disk: the originals are copied to
``<config>/.migrate-backup/<timestamp>/`` and each changed file is replaced through a temporary file
in its own folder and a rename, so a file is either as it was or fully migrated, never half. A file
a step cannot rewrite is left as it was and reported. A step is idempotent, so a second run changes
nothing.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from tess_shell.config.lock import is_held
from tess_shell.config.paths import config_dir
from tess_shell.exit_codes import ExitCode
from tess_shell.migrate.slots import Change, MigrationError
from tess_shell.migrate.steps import STEPS, Step
from tess_shell.options import Options

BACKUP_DIR = ".migrate-backup"


@dataclass(slots=True)
class FileResult:
    path: str
    state: str  # "changed" | "would-change"
    changes: list[Change] = field(default_factory=list)


@dataclass(slots=True)
class Skipped:
    path: str
    step: str
    message: str
    line: int = 0
    column: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "step": self.step,
            "line": self.line,
            "column": self.column,
            "message": self.message,
        }


@dataclass(slots=True)
class Report:
    config_dir: Path
    check: bool
    steps: dict[str, list[FileResult]] = field(default_factory=dict)
    skipped: list[Skipped] = field(default_factory=list)
    backup: Path | None = None
    verdict: dict[str, Any] | None = None  # ``check --json`` after the rewrite

    @property
    def changed(self) -> int:
        return len({f.path for files in self.steps.values() for f in files})


def _roots(config: Path) -> list[Path]:
    """The configuration folder, then the other folders ``settings.tdl`` names (when it can be
    read; a 0.1 ``settings.tdl`` cannot, and then the config folder alone is searched)."""
    roots = [config]
    try:
        from tess_shell.config.settings import load_settings

        settings, _ = load_settings(config)
    except Exception:
        return roots
    if settings is None:
        return roots
    for folders in settings.directories.values():
        for folder in folders:
            resolved = folder.resolve()
            if resolved.is_dir() and not any(resolved.is_relative_to(r.resolve()) for r in roots):
                roots.append(resolved)
    return roots


def discover(config: Path) -> list[tuple[Path, str]]:
    """Every ``.tdl`` file under the configuration folders as ``(path, name shown)``: the name is
    relative to the config folder, else absolute. The backup folder is skipped and so is a link
    that leads out of the folder it is found in (a write must stay inside)."""
    found: dict[Path, str] = {}
    for root in _roots(config):
        real_root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d != BACKUP_DIR)
            for name in sorted(filenames):
                if not name.endswith(".tdl"):
                    continue
                path = Path(dirpath, name)
                if not path.resolve().is_relative_to(real_root) or not path.is_file():
                    continue
                try:
                    shown = str(path.relative_to(config))
                except ValueError:
                    shown = str(path)
                found.setdefault(path, shown)
    return sorted(found.items(), key=lambda item: item[1])


def _apply(
    text: str, name: str, steps: tuple[Step, ...]
) -> tuple[str, dict[str, list[Change]], Skipped | None]:
    done: dict[str, list[Change]] = {}
    for step in steps:
        try:
            text, changes = step.apply(text, path=name)
        except MigrationError as exc:
            return text, {}, Skipped(name, step.id, str(exc), exc.line, exc.column)
        if changes:
            done[step.id] = changes
    return text, done, None


def _write_atomic(path: Path, data: bytes) -> None:
    """Replace ``path`` with ``data`` through a temporary file next to it and a rename."""
    handle, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".migrate-tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        shutil.copymode(path, temp)
        os.replace(temp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise


def _backup_folder(config: Path, now: datetime) -> Path:
    base = config / BACKUP_DIR
    stamp = now.strftime("%Y%m%dT%H%M%S")
    candidate = base / stamp
    n = 1
    while candidate.exists():
        n += 1
        candidate = base / f"{stamp}-{n}"
    return candidate


def migrate(
    config: Path,
    *,
    check: bool,
    steps: tuple[Step, ...] = STEPS,
    now: Callable[[], datetime] = datetime.now,
) -> Report:
    """Migrate (or, with ``check``, only list) the files of ``config``. Raises ``OSError`` when
    the backup cannot be made: nothing is written then."""
    report = Report(config, check)
    pending: list[tuple[Path, str, bytes, bytes]] = []  # path, shown, original, migrated
    for path, name in discover(config):
        try:
            original = path.read_bytes()
            text = original.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            reason = exc.strerror if isinstance(exc, OSError) else "the file is not valid UTF-8"
            report.skipped.append(Skipped(name, "", f"cannot read: {reason}"))
            continue
        new, done, skipped = _apply(text, name, steps)
        if skipped is not None:
            report.skipped.append(skipped)
            continue
        if not done:
            continue
        state = "would-change" if check else "changed"
        for step_id, changes in done.items():
            report.steps.setdefault(step_id, []).append(FileResult(name, state, changes))
        pending.append((path, name, original, new.encode("utf-8")))
    if check or not pending:
        return report
    backup = _backup_folder(config, now())
    for path, name, original, _ in pending:
        target = backup / (name if not Path(name).is_absolute() else Path(*Path(name).parts[1:]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original)
        shutil.copystat(path, target)
    report.backup = backup
    failed: set[str] = set()
    for path, name, _, data in pending:
        try:
            _write_atomic(path, data)
        except OSError as exc:
            failed.add(name)
            report.skipped.append(Skipped(name, "", f"cannot write: {exc.strerror}"))
    if failed:
        for step_id in list(report.steps):
            report.steps[step_id] = [f for f in report.steps[step_id] if f.path not in failed]
            if not report.steps[step_id]:
                del report.steps[step_id]
    return report


def exit_code(report: Report) -> ExitCode:
    if report.skipped:
        return ExitCode.ENVIRONMENT  # exit 2: a file could not be migrated
    if report.check and report.changed:
        return ExitCode.CONFIG  # exit 1: --check found work
    return ExitCode.OK


def to_dict(report: Report, steps: tuple[Step, ...] = STEPS) -> dict[str, Any]:
    texts = {s.id: s for s in steps}
    return {
        "ok": not report.skipped,
        "config_dir": str(report.config_dir),
        "check": report.check,
        "steps": [
            {
                "step": step_id,
                "from": texts[step_id].source,
                "to": texts[step_id].target,
                "files": [{"path": f.path, "state": f.state} for f in files],
            }
            for step_id, files in report.steps.items()
        ],
        "skipped": [s.to_dict() for s in report.skipped],
        "backup": str(report.backup) if report.backup else None,
        "result": report.verdict,
    }


def _print_text(report: Report, steps: tuple[Step, ...], quiet: bool) -> None:
    texts = {s.id: s for s in steps}
    for step_id, files in report.steps.items():
        step = texts[step_id]
        if not quiet:
            print(f"step {step_id}: {step.source} to {step.target}: {step.summary}")
        for f in files:
            verb = "would change" if f.state == "would-change" else "changed"
            print(f"  {verb}: {f.path} ({len(f.changes)} edit{'s' if len(f.changes) != 1 else ''})")
    for s in report.skipped:
        where = f":{s.line}:{s.column}" if s.line else ""
        which = f" (step {s.step})" if s.step else ""
        print(f"not migrated: {s.path}{where}: {s.message}{which}", file=sys.stderr)
    if report.backup is not None:
        print(f"backup: {report.backup}")
    verb = "to change" if report.check else "changed"
    print(f"{report.changed} file(s) {verb}, {len(report.skipped)} not migrated")


def _verdict(options: Options) -> tuple[int, str]:
    """``check`` on the migrated folder: its exit code and what it printed."""
    from tess_shell import app

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = app.check(options)
    return code, out.getvalue() + err.getvalue()


def run(
    options: Options,
    *,
    check: bool,
    force: bool,
    environ: Mapping[str, str] | None = None,
) -> int:
    config = config_dir(options.config_dir)
    if not config.is_dir():
        message = f"config directory does not exist: {config}"
        if options.json:
            print(json.dumps({"ok": False, "error": message, "exit": int(ExitCode.ENVIRONMENT)}))
        else:
            print(f"tesserae-shell: {message}", file=sys.stderr)
        return int(ExitCode.ENVIRONMENT)
    if not check and not force:
        env = os.environ if environ is None else environ
        runtime = env.get("XDG_RUNTIME_DIR", "")
        if runtime and os.path.isabs(runtime) and is_held(Path(runtime)):
            message = (
                "a tesserae-shell is running: a reload would read half-migrated files; "
                "stop it, or add --force"
            )
            if options.json:
                payload = {"ok": False, "error": message, "exit": int(ExitCode.ALREADY_RUNNING)}
                print(json.dumps(payload))
            else:
                print(f"tesserae-shell: {message}", file=sys.stderr)
            return int(ExitCode.ALREADY_RUNNING)
    try:
        report = migrate(config, check=check)
    except OSError as exc:
        message = f"cannot write the backup, nothing was changed: {exc.strerror}"
        if options.json:
            print(json.dumps({"ok": False, "error": message, "exit": int(ExitCode.ENVIRONMENT)}))
        else:
            print(f"tesserae-shell: {message}", file=sys.stderr)
        return int(ExitCode.ENVIRONMENT)
    code = exit_code(report)
    if not check and report.steps:
        # the verdict on the result: ``check`` over the folder, in the same process
        quiet = Options(config_dir=config, json=True, quiet=True)
        _, printed = _verdict(quiet)
        try:
            report.verdict = json.loads(printed)
        except ValueError:
            report.verdict = {"ok": False, "output": printed.strip()}
    if options.json:
        print(json.dumps(to_dict(report)))
    else:
        _print_text(report, STEPS, options.quiet)
        if report.verdict is not None:
            if report.verdict.get("ok"):
                print(f"check: ok, {report.verdict.get('files', 0)} files checked")
            else:
                print("check: the migrated folder still has errors; run tesserae-shell check")
    return int(code)
