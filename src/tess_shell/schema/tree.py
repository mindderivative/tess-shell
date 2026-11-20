"""Small helpers over the public ``tess_dl`` tree, which has no accessors of its own in 0.1."""

from __future__ import annotations

import re

from tess_dl import LANGUAGE_VERSION, Block, Document, Origin, Property, String, Value, Word

from tess_shell.schema.findings import Finding


def properties(block: Block) -> list[Property]:
    return [e for e in block.entries if isinstance(e, Property)]


def child_blocks(block: Block) -> list[Block]:
    return [e for e in block.entries if isinstance(e, Block)]


def find_property(block: Block, key: str) -> Property | None:
    for prop in properties(block):
        if prop.key == key:
            return prop
    return None


def value_text(value: Value) -> str | None:
    """The text of a word or string value, ``None`` for any other kind of value."""
    if isinstance(value, Word):
        return value.text
    if isinstance(value, String):
        return value.value
    return None


def position(origin: Origin | None) -> tuple[int, int]:
    """``(line, column)`` of an origin, ``(1, 1)`` for a node built in code."""
    if origin is None:
        return (1, 1)
    return (origin.line, origin.column)


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


def language_finding(document: Document, file: str) -> Finding | None:
    """The ``TDL:`` key of the metadata against the language the installed ``tess_dl`` reads.

    ``tess_dl`` accepts any version of its own major number, so a file written for TDL 0.1 would
    load without a word; the shell reads TDL 0.2 only and says so.
    """
    entry = next(
        (e for e in document.metadata.entries if isinstance(e, Property) and e.key == "TDL"), None
    )
    if entry is None:
        return None
    text = value_text(entry.value)
    if text is None:
        return None
    declared, current = parse_version(text), parse_version(LANGUAGE_VERSION)
    if declared == current:
        return None
    line, column = position(entry.key_origin)
    if declared > current:
        return Finding(
            file,
            line,
            column,
            "error",
            "version-pin",
            f"this file needs TDL {text} or newer; {LANGUAGE_VERSION} is installed",
            "upgrade tesserae-dl, or lower the TDL version in the metadata block",
        )
    return _old_language(file, line, column, text)


def _old_language(file: str, line: int, column: int, text: str) -> Finding:
    return Finding(
        file,
        line,
        column,
        "error",
        "tdl-old-version",
        f"this file is written for TDL {text}; the shell reads TDL {LANGUAGE_VERSION}",
        "run `tesserae-shell migrate` to rewrite the file (a slot is written "
        f"<| expression |>, not {{{{ expression }}}}) and write TDL: {LANGUAGE_VERSION}",
    )


_METADATA_TDL = re.compile(r"^TDL[ \t]*:[ \t]*[\"']?(\d+(?:\.\d+)*)", re.MULTILINE)


def old_language_finding(text: str, file: str) -> Finding | None:
    """``tdl-old-version`` for a file whose metadata says an older TDL, read from the text. A TDL
    0.1 file that holds a ``{{ }}`` slot does not parse as 0.2, and the parse error would hide
    the real cause: this names it first, with the hint to run ``migrate``."""
    lines = text.removeprefix("\ufeff").split("\n")
    if not lines or lines[0].rstrip(" \t\r") != "---":
        return None
    for number, line in enumerate(lines[1:], start=2):
        if line.rstrip(" \t\r") == "---":
            return None
        found = _METADATA_TDL.match(line)
        if found:
            if parse_version(found.group(1)) >= parse_version(LANGUAGE_VERSION):
                return None
            return _old_language(file, number, 1, found.group(1))
    return None
