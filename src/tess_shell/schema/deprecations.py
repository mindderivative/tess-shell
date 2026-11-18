"""Deprecated names: the table, the warnings, the schema marks and the rename ``migrate`` makes.

Version Policy and Migration, "Deprecation": a renamed or replaced key, block or command keeps
working under its old name for one minor before 1.0 (two after) with the warning ``deprecated-key``
(``deprecated-command`` on the command line) that names the replacement and the release that removes
it; the schema export marks it (``deprecated: {since, removed_in, use}``); ``migrate`` rewrites the
old name to the new one. Nothing is deprecated in 0.2.0, so ``DEPRECATIONS`` is empty; a minor that
renames something adds a row here and every part below follows (the warning, the export mark, the
rewrite) with no other change.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tess_shell.schema.findings import Finding

if TYPE_CHECKING:  # the parser is imported inside the functions: the thin client never loads it
    from tess_dl import Block, Document, Entry, Property


@dataclass(frozen=True, slots=True)
class Deprecation:
    """One old name and what replaces it. ``block`` limits a ``key`` to that block type (``None``:
    in any block); a ``block`` names a block head; a ``command`` a command-line command."""

    kind: Literal["key", "block", "command"]
    name: str
    use: str
    since: str  # the release that began the deprecation
    removed_in: str  # the release that removes the old name
    block: str | None = None

    def mark(self) -> dict[str, str]:
        """The ``deprecated`` object of the schema export."""
        return {"since": self.since, "removed_in": self.removed_in, "use": self.use}

    def message(self) -> str:
        return (
            f"{self.name} is deprecated since {self.since} and is removed in {self.removed_in}; "
            f"use {self.use}"
        )


DEPRECATIONS: tuple[Deprecation, ...] = ()


def _blocks(entries: Iterable[Entry]) -> Iterator[Block]:
    from tess_dl import Block, For, If

    for entry in entries:
        if isinstance(entry, Block):
            yield entry
        elif isinstance(entry, If):
            yield from _blocks([*entry.body, *(entry.else_body or ())])
        elif isinstance(entry, For):
            yield from _blocks(entry.body)


def walk(root: Block) -> Iterator[Block]:
    """``root`` and every block below it, also those inside ``If`` and ``For`` bodies."""
    yield root
    for child in _blocks(root.entries):
        yield from walk(child)


def _entries_of(block: Block) -> Iterator[Property]:
    """The properties of ``block`` itself, also those inside its ``If`` and ``For`` bodies."""
    from tess_dl import For, If, Property

    stack: list[Entry] = list(block.entries)
    while stack:
        entry = stack.pop(0)
        if isinstance(entry, Property):
            yield entry
        elif isinstance(entry, If):
            stack = [*entry.body, *(entry.else_body or ()), *stack]
        elif isinstance(entry, For):
            stack = [*entry.body, *stack]


def deprecation_findings(document: Document, file: str) -> list[Finding]:
    """A ``deprecated-key`` warning for each old key or block head the file uses."""
    table = [d for d in DEPRECATIONS if d.kind in ("key", "block")]
    if not table:
        return []
    from tess_shell.schema.tree import position

    out: list[Finding] = []
    for block in walk(document.root):
        for dep in table:
            if dep.kind == "block" and block.type == dep.name:
                line, column = position(block.origin)
                out.append(_finding(dep, file, line, column))
            elif dep.kind == "key" and dep.block in (None, block.type):
                for prop in _entries_of(block):
                    if prop.key == dep.name:
                        line, column = position(prop.key_origin)
                        out.append(_finding(dep, file, line, column))
    out.sort(key=lambda f: (f.line, f.column))
    return out


def _finding(dep: Deprecation, file: str, line: int, column: int) -> Finding:
    return Finding(
        file,
        line,
        column,
        "warning",
        "deprecated-key",
        dep.message(),
        f"write {dep.use}; `tesserae-shell migrate` rewrites it",
    )


def command_warning(command: str) -> str | None:
    """The ``deprecated-command`` line for a deprecated command, else ``None``."""
    for dep in DEPRECATIONS:
        if dep.kind == "command" and dep.name == command:
            return f"tesserae-shell: warning: deprecated-command: {dep.message()}"
    return None


def mark_schema(blocks: dict[str, dict[str, object]]) -> None:
    """Add ``deprecated`` to the exported spec of each deprecated key and block (in place)."""
    for dep in DEPRECATIONS:
        if dep.kind == "block" and dep.name in blocks:
            blocks[dep.name]["deprecated"] = dep.mark()
        elif dep.kind == "key":
            for name, spec in blocks.items():
                keys = spec.get("keys")
                if dep.block in (None, name) and isinstance(keys, dict) and dep.name in keys:
                    keys[dep.name]["deprecated"] = dep.mark()
