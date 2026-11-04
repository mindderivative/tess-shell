"""Write ``UID:`` into a file's metadata the first time the shell registers it (Config Discovery
and Registry > Identity and UIDs; M2 decision G8).

Only the one line is added; ``tess_dl`` guarantees no other byte changes. The file is copied
first to the state directory, outside the config folder (risk R-06), and replaced atomically.
The shipped files are never edited.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path

import tess_dl

from tess_shell.schema.findings import Finding


def _backup(path: Path, config: Path, backups: Path, now: datetime) -> Path:
    try:
        relative = path.relative_to(config)
    except ValueError:
        relative = Path(path.name)
    target = backups / f"{relative}.{now:%Y%m%dT%H%M%S}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target


def _replace(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def assign_uids(
    paths: Iterable[Path],
    config: Path,
    uid_for: Callable[[str], str],
    backups: Path,
    now: datetime | None = None,
    on_write: Callable[[Path, bytes], None] | None = None,
) -> tuple[dict[Path, str], list[Finding]]:
    """Give each file a UID. ``uid_for(key)`` returns the registry's UID for ``file:<path>``.

    A file that already has a ``UID`` keeps it. Returns the UID of every file and the problems
    met (an unwritable file keeps its registry UID and is reported; nothing is lost).
    """
    now = now or datetime.now()
    uids: dict[Path, str] = {}
    findings: list[Finding] = []
    for path in paths:
        try:
            text = path.read_bytes().decode("utf-8-sig")
        except OSError, UnicodeDecodeError:
            continue  # the loader already reported it
        result = tess_dl.parse(text, path=str(path))
        document = result.document
        if result.errors or document is None:
            continue
        existing = document.metadata.get("UID")
        known = getattr(existing, "text", None) or getattr(existing, "value", None)
        try:
            key = f"file:{path.relative_to(config)}"
        except ValueError:
            key = f"file:{path}"
        if isinstance(known, str) and known:
            uids[path] = known
            continue
        uid = uid_for(key)
        uids[path] = uid
        try:
            edited = document.with_metadata("UID", uid)
            _backup(path, config, backups, now)
            _replace(path, edited.text)
            if on_write is not None:
                on_write(path, edited.text.encode("utf-8"))
        except (OSError, ValueError, tess_dl.TDLError) as exc:
            findings.append(
                Finding(
                    str(path),
                    1,
                    1,
                    "warning",
                    "uid-write",
                    f"could not write the UID: {exc}",
                    "the UID is kept in the registry; the file is unchanged",
                )
            )
    return uids, findings
