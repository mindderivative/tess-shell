"""Step 0001's text rewrite: the TDL 0.1 slot ``{{ expression }}`` becomes ``<| expression |>``.

``tess_dl`` 0.2 reads only the new form and ships no rewrite (a request in the vault, TDL-REQ-001),
so the shell carries its own scanner of the 0.1 slot rules behind ONE function, ``rewrite_slots``;
a library function can replace it without touching a caller. The 0.1 rules it follows (the
``tess-dl`` 0.1.1 language reference):

* a ``#`` that is the first thing on a line or follows whitespace starts a comment to the line end;
* a quote starts a string where a value is expected (after ``:``, ``,``, ``[``, ``(``, ``{``, at a
  line start, or after whitespace inside a call), not in the middle of an unquoted word; a string
  closes on its own line and ``\\`` escapes the next character;
* outside a string and a comment, ``{{`` opens a slot, on one line, that ends at the first ``}}``
  not inside a quoted string of its own (``'...'`` or ``"..."`` with ``\\`` escapes);
* in the metadata block (between the two ``---`` lines) nothing is a slot.

Only a file that says ``TDL: 0.1`` is touched, so a 0.2 file whose strings or words hold ``{{`` is
returned as it is. Nothing but the two delimiters of each slot and the version word changes: every
other byte (comments, layout, line endings, a byte-order mark, quoted text that looks like a slot)
stays.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

OLD_OPEN, OLD_CLOSE = "{{", "}}"
NEW_OPEN, NEW_CLOSE = "<|", "|>"
_QUOTES = "'\""
_TDL_LINE = re.compile(r"^(?P<head>TDL[ \t]*:[ \t]*)(?P<q>[\"']?)0\.1(?P=q)[ \t]*(?:#.*)?$")


@dataclass(frozen=True, slots=True)
class Change:
    """One edit a step makes (or would make): where, what kind, the text before and after."""

    path: str
    line: int
    column: int
    kind: str  # "slot" | "version" | "rename"
    before: str
    after: str

    def to_dict(self) -> dict[str, object]:
        return {
            "line": self.line,
            "column": self.column,
            "kind": self.kind,
            "before": self.before,
            "after": self.after,
        }


class MigrationError(ValueError):
    """A file a step cannot rewrite safely; it is left unchanged. ``line`` and ``column`` are
    1-based (0 when the error is about the whole file)."""

    def __init__(self, message: str, line: int = 0, column: int = 0) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


def holds_new_close(text: str) -> bool:
    """Whether ``|>`` stands in ``text`` outside a quoted string (the scan the 0.2 reader makes
    to find where a slot ends): such a slot cannot be written in the new form."""
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in _QUOTES:
            quote = ch
        elif text.startswith(NEW_CLOSE, i):
            return True
        i += 1
    return False


class _Lines:
    """Offset to 1-based ``(line, column)``."""

    def __init__(self, text: str) -> None:
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def at(self, offset: int) -> tuple[int, int]:
        line = bisect_right(self.starts, offset)
        return line, offset - self.starts[line - 1] + 1


def _metadata(text: str) -> tuple[int, int] | None:
    """The offsets ``(start, end)`` of the metadata lines (between the two ``---`` lines), or
    ``None`` when the file does not open with one. A byte-order mark is skipped."""
    pos = 1 if text.startswith("\ufeff") else 0
    lines = text[pos:].split("\n")
    if not lines or lines[0].rstrip(" \t\r") != "---":
        return None
    start = pos + len(lines[0]) + 1
    offset = start
    for line in lines[1:]:
        if line.rstrip(" \t\r") == "---":
            return start, offset
        offset += len(line) + 1
    return None


def _skip_string(text: str, i: int) -> int:
    """The offset after the string that opens at ``i`` (a string ends at its line)."""
    quote = text[i]
    j = i + 1
    n = len(text)
    while j < n and text[j] != "\n":
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == quote:
            return j + 1
        j += 1
    return j


def _find_slot_end(text: str, i: int) -> int | None:
    """The offset of the ``}}`` ending the slot opened at ``i``; ``None`` if the line has none."""
    quote = ""
    k = i + 2
    n = len(text)
    while k < n and text[k] != "\n":
        ch = text[k]
        if quote:
            if ch == "\\":
                k += 1
            elif ch == quote:
                quote = ""
        elif ch in _QUOTES:
            quote = ch
        elif text.startswith(OLD_CLOSE, k):
            return k
        k += 1
    return None


def rewrite_slots(text: str, *, path: str) -> tuple[str, list[Change]]:
    """``text`` of a TDL 0.1 file as TDL 0.2, with the edits made. A file that does not say
    ``TDL: 0.1`` comes back unchanged with no edits. ``path`` names the file in the edits.

    Raises ``MigrationError`` (nothing is returned, so the file stays as it was) for a slot with
    no ``}}`` on its line and for a slot whose text holds ``|>`` outside a quote."""
    meta = _metadata(text)
    if meta is None:
        return text, []
    version_at = -1
    offset = meta[0]
    for meta_line in text[meta[0] : meta[1]].split("\n"):
        found = _TDL_LINE.match(meta_line.rstrip("\r"))
        if found:
            version_at = offset + found.end("head") + len(found.group("q"))
            break
        offset += len(meta_line) + 1
    if version_at < 0:
        return text, []

    lines = _Lines(text)
    edits: list[tuple[int, int, str]] = []
    changes: list[Change] = []
    n = len(text)
    i = meta[1]
    value_start = True  # a value (so a string) may begin here
    at_entry = True  # an entry (a key or a block head) may begin here
    run_start = i  # where the current non-space run began
    run_value = False  # that run began where a value may
    run_entry = False  # that run began where an entry may
    depth = 0  # open ``(`` of calls
    while i < n:
        ch = text[i]
        if ch == "\n":
            value_start = at_entry = True
            run_start = i + 1
            i += 1
        elif ch in " \t\r":
            run_start = i + 1
            i += 1
        elif ch == "#" and (i == 0 or text[i - 1] in " \t\r\n"):
            while i < n and text[i] != "\n":
                i += 1
        elif ch in _QUOTES and (value_start or (depth > 0 and text[i - 1] in " \t\r\n")):
            i = _skip_string(text, i)
            value_start = at_entry = False
        elif text.startswith(OLD_OPEN, i):
            end = _find_slot_end(text, i)
            line, column = lines.at(i)
            if end is None:
                raise MigrationError(
                    f"the slot opened by {OLD_OPEN} has no {OLD_CLOSE} on its line", line, column
                )
            if holds_new_close(text[i + 2 : end]):
                raise MigrationError(
                    f"the slot text holds {NEW_CLOSE} outside a quote, so it cannot be "
                    f"written as {NEW_OPEN} ... {NEW_CLOSE}",
                    line,
                    column,
                )
            edits.append((i, i + 2, NEW_OPEN))
            edits.append((end, end + 2, NEW_CLOSE))
            new_slot = NEW_OPEN + text[i + 2 : end] + NEW_CLOSE
            changes.append(Change(path, line, column, "slot", text[i : end + 2], new_slot))
            i = end + 2
            value_start = at_entry = False
        else:
            if i == run_start:
                run_value, run_entry = value_start, at_entry
            if ch in ",{":
                value_start = at_entry = True
                run_start = i + 1
            elif ch == "[":
                value_start, at_entry = True, False
                run_start = i + 1
            elif ch == ":" and run_entry and text[run_start:i].isidentifier():
                value_start, at_entry = True, False
            elif ch == "(":
                if run_value and text[run_start:i].isidentifier():
                    depth += 1
                value_start, at_entry = True, False
                run_start = i + 1
            else:
                if ch == ")":
                    depth = max(depth - 1, 0)
                value_start = at_entry = False
            i += 1
    line, column = lines.at(version_at)
    edits.append((version_at, version_at + 3, "0.2"))
    changes.append(Change(path, line, column, "version", "0.1", "0.2"))
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    changes.sort(key=lambda c: (c.line, c.column))
    return text, changes
