"""``registry.json``: read, create and rewrite atomically (Registry; Crash Recovery and Watchdog >
What Survives a Restart).

Every change is written within a fraction of a second, off the loop thread, to a temporary file in
the same folder that is then renamed over the registry, so a kill at any moment leaves the old file
or the new one whole. A registry that is not valid JSON or not the right shape is moved aside (it
is never overwritten or lost) and rebuilt from the UIDs the files carry; saved positions are lost.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from tess_shell.schema.findings import Finding

SUPPORTED_VERSION = 1
DEBOUNCE = 0.2  # seconds from the first unsaved change to the write; later changes ride along


class RegistryError(Exception):
    def __init__(self, finding: Finding) -> None:
        super().__init__(finding.message)
        self.finding = finding


def _atomic_write_text(path: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():
            os.chmod(tmp, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2) + "\n"


def _remove_leftovers(path: Path) -> None:
    """A temporary file a killed write left beside the registry."""
    for stray in path.parent.glob(f".{path.name}.*"):
        stray.unlink(missing_ok=True)


class Registry:
    def __init__(self, path: Path, data: dict[str, Any], recovered: str | None = None) -> None:
        self.path = path
        self.data = data
        # why this registry was rebuilt from an unreadable file (the shell warns), or ``None``
        self.recovered = recovered
        self.created = False  # the file was missing and was made now (the usual first start)
        self._lock = threading.Lock()  # the data and the flag: the loop writes, a timer reads
        self._write_lock = threading.Lock()  # one write to the file at a time
        self._dirty = False
        self._timer: threading.Timer | None = None

    @classmethod
    def open(cls, path: Path) -> Registry:
        if not path.exists():
            data: dict[str, Any] = {"registry": SUPPORTED_VERSION, "entries": {}}
            _atomic_write_text(path, _text(data))
            registry = cls(path, data)
            registry.created = True
            return registry
        _remove_leftovers(path)

        def fail(
            rule: str, message: str, hint: str, line: int = 1, column: int = 1
        ) -> RegistryError:
            return RegistryError(Finding(str(path), line, column, "error", rule, message, hint))

        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return cls._rebuilt(path, f"it is not valid JSON ({exc.msg}, line {exc.lineno})")
        except UnicodeDecodeError as exc:
            return cls._rebuilt(path, f"it is not valid text ({exc.reason})")
        except OSError as exc:
            raise fail("registry-unreadable", f"cannot read the registry: {exc}", "") from exc
        if (
            not isinstance(loaded, dict)
            or not isinstance(loaded.get("registry"), int)
            or isinstance(loaded.get("registry"), bool)
            or not isinstance(loaded.get("entries"), dict)
        ):
            return cls._rebuilt(
                path,
                "it is not an object with an integer 'registry' and an object 'entries'",
            )
        if loaded["registry"] > SUPPORTED_VERSION:
            raise fail(
                "registry-too-new",
                f"registry.json is version {loaded['registry']}; this shell reads "
                f"version {SUPPORTED_VERSION}",
                "use a newer tesserae-shell",
            )
        return cls(path, loaded)

    @classmethod
    def _rebuilt(cls, path: Path, why: str) -> Registry:
        """Move the unreadable file aside, whole, and start a new registry: the shell then issues
        UIDs from the ones the files carry and the saved positions are lost."""
        aside = path.with_name(f"{path.name}.corrupt-{datetime.now():%Y%m%dT%H%M%S}")
        try:
            os.replace(path, aside)
        except OSError as exc:
            raise RegistryError(
                Finding(
                    str(path),
                    1,
                    1,
                    "error",
                    "registry-invalid",
                    f"registry.json cannot be used ({why}) and cannot be moved aside: {exc}",
                    "fix the file or move it away",
                )
            ) from exc
        data: dict[str, Any] = {"registry": SUPPORTED_VERSION, "entries": {}}
        _atomic_write_text(path, _text(data))
        return cls(path, data, f"{why}; the old file is kept as {aside.name}")

    def uid_for(self, path: str, kind: str = "use") -> str:
        """The UID of the entry at ``path`` (a dotted use path, or ``module:<Name>``), made on first
        use as a UUIDv7 and kept in the registry (Config Discovery and Registry > Identity)."""
        with self._lock:
            entries: dict[str, Any] = self.data["entries"]
            entry = entries.get(path)
            if isinstance(entry, dict) and isinstance(entry.get("uid"), str):
                return str(entry["uid"])
            uid = str(uuid.uuid7())
            entries[path] = {"uid": uid, "kind": kind}
            self._changed()
            return uid

    def save(self) -> None:
        """Write the registry now (the stop sequence), after any write that is pending."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._dirty = False
            text = _text(self.data)
        with self._write_lock:
            _atomic_write_text(self.path, text)

    # -- a Panel's saved position (Panel > Position and Attachment) -------------------------------

    def position(self, key: str) -> dict[str, float] | None:
        """The saved position of the Panel at ``key``: the ``Inset`` of each side it is anchored
        to (``left``, ``top``, ``right``, ``bottom``), or ``None`` when it was never moved."""
        entry = self.data["entries"].get(key)
        saved = entry.get("position") if isinstance(entry, dict) else None
        if not isinstance(saved, dict):
            return None
        return {
            side: float(v)
            for side, v in saved.items()
            if side in ("left", "top", "right", "bottom") and isinstance(v, int | float)
        }

    def set_position(self, key: str, position: dict[str, float]) -> None:
        """Remember where the user left a Panel; the file follows within ``DEBOUNCE`` seconds."""
        with self._lock:
            entries: dict[str, Any] = self.data["entries"]
            entry = entries.get(key)
            if not isinstance(entry, dict):
                entry = entries[key] = {"uid": str(uuid.uuid7()), "kind": "panel"}
            entry["position"] = dict(position)
            self._changed()

    # -- the write, off the loop thread -----------------------------------------------------------

    def _changed(self) -> None:
        """A change was made (``_lock`` is held): one write is due ``DEBOUNCE`` seconds from the
        first change that is not written yet; the text is made when it runs, so changes in the
        meantime ride along."""
        self._dirty = True
        if self._timer is None:
            self._timer = threading.Timer(DEBOUNCE, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            self._timer = None
            if not self._dirty:
                return
            self._dirty = False
            text = _text(self.data)
        try:
            with self._write_lock:
                _atomic_write_text(self.path, text)
        except OSError as exc:
            with self._lock:
                self._dirty = True  # the next change (or the stop) tries again
            logger.warning(f"registry: could not write {self.path} ({exc}); it is tried again")
