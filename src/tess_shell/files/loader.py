"""Read and parse shell files. Syntax only: no suffix, root, name or schema checks yet."""

from __future__ import annotations

from pathlib import Path

import tess_dl
from tess_dl import Document

from tess_shell.schema.findings import Finding


def display_name(path: Path, base: Path) -> str:
    """The path relative to ``base`` when it is inside it, else absolute."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def load_file(path: Path, base: Path) -> tuple[Document | None, list[Finding]]:
    name = display_name(path, base)
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return None, [
            Finding(
                name,
                1,
                1,
                "error",
                "tdl-bad-encoding",
                f"The bytes are not valid UTF-8 (at byte {exc.start}).",
                "Save the file as UTF-8",
            )
        ]
    except OSError as exc:
        return None, [
            Finding(name, 1, 1, "error", "unreadable", f"cannot read: {exc.strerror}", "")
        ]
    result = tess_dl.parse(text, path=name)
    findings = [
        Finding(name, e.origin.line, e.origin.column, "error", e.code, e.message, e.hint)
        for e in result.errors
    ]
    return (None if findings else result.document), findings


def load_all(paths: list[Path], base: Path) -> tuple[list[Document], list[Finding]]:
    documents: list[Document] = []
    findings: list[Finding] = []
    for path in paths:
        document, errors = load_file(path, base)
        findings.extend(errors)
        if document is not None:
            documents.append(document)
    return documents, findings
