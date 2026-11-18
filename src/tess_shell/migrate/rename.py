"""Step 0002: a deprecated key or block head is written under its new name (the table is
``tess_shell.schema.deprecations``; it is empty in 0.2.0, so the step changes nothing yet)."""

from __future__ import annotations

from tess_shell.migrate.slots import Change
from tess_shell.schema import deprecations
from tess_shell.schema.deprecations import _entries_of, walk


def rename_deprecated(text: str, *, path: str) -> tuple[str, list[Change]]:
    """``text`` of a TDL 0.2 file with every deprecated key and block head written under its new
    name; only the name's own bytes change. A file that does not parse is returned unchanged."""
    import tess_dl

    table = [d for d in deprecations.DEPRECATIONS if d.kind in ("key", "block")]
    if not table:
        return text, []
    result = tess_dl.parse(text.removeprefix("\ufeff"), path=path)
    if result.errors or result.document is None:
        return text, []
    shift = 1 if text.startswith("\ufeff") else 0
    edits: list[tuple[int, str, str, int, int]] = []  # offset, old, new, line, column
    for block in walk(result.document.root):
        for dep in table:
            if dep.kind == "block" and block.type == dep.name and block.origin is not None:
                o = block.origin
                edits.append((o.offset, dep.name, dep.use, o.line, o.column))
            elif dep.kind == "key" and dep.block in (None, block.type):
                for prop in _entries_of(block):
                    if prop.key == dep.name and prop.key_origin is not None:
                        o = prop.key_origin
                        edits.append((o.offset, dep.name, dep.use, o.line, o.column))
    changes: list[Change] = []
    body = text
    for offset, old, new, line, column in sorted(edits, reverse=True):
        at = offset + shift
        if body[at : at + len(old)] != old:
            continue
        body = body[:at] + new + body[at + len(old) :]
        changes.append(Change(path, line, column, "rename", old, new))
    changes.sort(key=lambda c: (c.line, c.column))
    return body, changes
