"""``registry.json``: read, create and rewrite atomically (Registry).

M0 only opens, creates and saves it. Rebuilding from UIDs, writing UIDs and pruning are not built.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

from tess_shell.schema.findings import Finding

SUPPORTED_VERSION = 1


class RegistryError(Exception):
    def __init__(self, finding: Finding) -> None:
        super().__init__(finding.message)
        self.finding = finding


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():
            os.chmod(tmp, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class Registry:
    def __init__(self, path: Path, data: dict[str, Any]) -> None:
        self.path = path
        self.data = data

    @classmethod
    def open(cls, path: Path) -> Registry:
        if not path.exists():
            data: dict[str, Any] = {"registry": SUPPORTED_VERSION, "entries": {}}
            _atomic_write(path, data)
            return cls(path, data)

        def fail(
            rule: str, message: str, hint: str, line: int = 1, column: int = 1
        ) -> RegistryError:
            return RegistryError(Finding(str(path), line, column, "error", rule, message, hint))

        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise fail(
                "registry-invalid-json",
                f"registry.json is not valid JSON: {exc.msg}",
                "fix the file or move it away; it was not changed",
                exc.lineno,
                exc.colno,
            ) from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise fail("registry-unreadable", f"cannot read the registry: {exc}", "") from exc
        if (
            not isinstance(loaded, dict)
            or not isinstance(loaded.get("registry"), int)
            or isinstance(loaded.get("registry"), bool)
            or not isinstance(loaded.get("entries"), dict)
        ):
            raise fail(
                "registry-bad-shape",
                "registry.json must be an object with an integer 'registry' "
                "and an object 'entries'",
                "fix the file or move it away; it was not changed",
            )
        if loaded["registry"] > SUPPORTED_VERSION:
            raise fail(
                "registry-too-new",
                f"registry.json is version {loaded['registry']}; this shell reads "
                f"version {SUPPORTED_VERSION}",
                "use a newer tesserae-shell",
            )
        return cls(path, loaded)

    def uid_for(self, path: str, kind: str = "use") -> str:
        """The UID of the entry at ``path`` (a dotted use path, or ``module:<Name>``), made on first
        use as a UUIDv7 and kept in the registry (Config Discovery and Registry > Identity)."""
        entries: dict[str, Any] = self.data["entries"]
        entry = entries.get(path)
        if isinstance(entry, dict) and isinstance(entry.get("uid"), str):
            return str(entry["uid"])
        uid = str(uuid.uuid7())
        entries[path] = {"uid": uid, "kind": kind}
        return uid

    def save(self) -> None:
        _atomic_write(self.path, self.data)

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
        """Remember where the user left a Panel and write the registry, off the loop thread: the
        text is made here, so the loop's own changes to the registry cannot race the writer."""
        entries: dict[str, Any] = self.data["entries"]
        entry = entries.get(key)
        if not isinstance(entry, dict):
            entry = entries[key] = {"uid": str(uuid.uuid7()), "kind": "panel"}
        entry["position"] = dict(position)
        text = json.dumps(self.data, indent=2) + "\n"
        with Registry._lock:
            self._pending = text  # a newer text replaces one not written yet
            if self._writing:
                return
            self._writing = True
        threading.Thread(target=self._writer, daemon=True).start()

    _lock = threading.Lock()
    _pending: str | None = None
    _writing = False

    def _writer(self) -> None:
        """Write the latest text, and again if a newer one arrived meanwhile."""
        while True:
            with Registry._lock:
                text, self._pending = self._pending, None
                if text is None:
                    self._writing = False
                    return
            tmp: Path | None = None
            try:
                fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
                tmp = Path(tmp_name)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(text)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, self.path)
            except OSError:
                if tmp is not None:
                    tmp.unlink(missing_ok=True)
