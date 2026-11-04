"""``registry.json``: read, create and rewrite atomically (Registry).

M0 only opens, creates and saves it. Rebuilding from UIDs, writing UIDs and pruning are not built.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
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

    def save(self) -> None:
        _atomic_write(self.path, self.data)
