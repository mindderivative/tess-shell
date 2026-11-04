"""Stage 3 of the pipeline: the checks a file must pass before its schema is read."""

from __future__ import annotations

import re
from collections.abc import Mapping

from tess_dl import Document

from tess_shell.schema.findings import Finding

_ROOT_SUFFIX = {
    "Shell": "_Shell.tdl",
    "Module": "_Module.tdl",
    "Style": "_Style.tdl",
    "Theme": "_Theme.tdl",
    "Stylesheet": "_Stylesheet.tdl",
}


def parse_version(text: str) -> tuple[int, ...]:
    """``0.1.0.dev0`` is ``(0, 1, 0)``: the leading numeric parts."""
    parts: list[int] = []
    for piece in text.split("."):
        m = re.match(r"\d+", piece)
        if not m:
            break
        parts.append(int(m.group()))
        if m.end() != len(piece):
            break
    return tuple(parts)


def check_header(document: Document, file: str, installed: Mapping[str, str]) -> list[Finding]:
    """The minimum-version pins (``TEL``, ``TRE``, ``Shell``) and the root block against the
    file's suffix. ``installed`` maps ``TEL``, ``TRE`` and ``Shell`` to the running versions."""
    out: list[Finding] = []
    for key, have in installed.items():
        entry = document.metadata.get(key)
        if entry is None:
            continue
        text = getattr(entry, "text", None) or getattr(entry, "value", "")
        need = parse_version(str(text))
        if need > parse_version(have):
            out.append(
                Finding(
                    file,
                    1,
                    1,
                    "error",
                    "version-pin",
                    f"this file needs {key} {text} or newer; {have} is installed",
                    f"upgrade {key}, or lower the pin in the metadata block",
                )
            )
    suffix = next((s for s in _ROOT_SUFFIX.values() if file.endswith(s)), None)
    expected_root = next((r for r, s in _ROOT_SUFFIX.items() if s == suffix), None)
    root = document.root
    if expected_root is not None and root.type != expected_root:
        origin = root.origin
        out.append(
            Finding(
                file,
                origin.line if origin else 1,
                origin.column if origin else 1,
                "error",
                "shell-root-suffix",
                f"the root block is {root.type} but the file name ends in {suffix} "
                f"(a {expected_root} file)",
                f"write {expected_root} {{ }}, or rename the file; the root block decides",
            )
        )
    return out
