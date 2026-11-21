"""Step 0003: ``Tab_Index`` above 0 is gone (Focus and Keyboard > Tab Order).

A block's order is the order of the file, so a positive ``Tab_Index`` on a block is removed. A
surface's place among the surfaces is the ``Focus_Order`` list of the ``Shell`` block: the surfaces
that wrote a ``Tab_Index`` are listed in the order it gave (ascending, equal ones in file order)
and their ``Tab_Index`` is removed. Only the keys' own bytes change, plus one new line before the
first ``Monitor``. A file of surfaces made to be imported (a ``Shell`` with no ``Monitor``) has no
place for the list: its ``Tab_Index`` stays and the loader says so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tess_dl

from tess_shell.migrate.slots import Change
from tess_shell.schema.deprecations import walk

_SURFACES = ("Bar", "Panel", "Frame")
_SIDES = ("Top", "Right", "Bottom", "Left")
_KEY = re.compile(r"Tab_Index[ \t]*:[ \t]*\d+")


@dataclass(slots=True)
class _Edit:
    start: int
    end: int
    text: str
    line: int
    column: int
    kind: str
    before: str
    after: str


def _remove_span(text: str, at: int) -> tuple[int, int] | None:
    """The span of the ``Tab_Index: n`` that starts at ``at``, with the comma that separated it
    from its neighbour, or the whole line when it was alone on it."""
    found = _KEY.match(text, at)
    if found is None:
        return None
    start, end = at, found.end()
    trailing = re.compile(r"[ \t]*,[ \t]*").match(text, end)
    if trailing is not None:
        end = trailing.end()
    else:
        leading = re.search(r",[ \t]*$", text[:start])
        if leading is not None:
            start = leading.start()
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end
    if not text[line_start:start].strip() and not text[end:line_end].strip():
        return line_start, min(line_end + 1, len(text))
    return start, end


def _name(block: tess_dl.Block) -> str | None:
    for entry in block.entries:
        if isinstance(entry, tess_dl.Property) and entry.key == "Name":
            return getattr(entry.value, "text", None)
    return None


def _tab_index(block: tess_dl.Block) -> tess_dl.Property | None:
    for entry in block.entries:
        if (
            isinstance(entry, tess_dl.Property)
            and entry.key == "Tab_Index"
            and isinstance(entry.value, tess_dl.Number)
            and isinstance(entry.value.value, int)
        ):
            return entry
    return None


def move_tab_index(text: str, *, path: str) -> tuple[str, list[Change]]:
    """``text`` of a TDL 0.2 shell or module file without a ``Tab_Index`` above 0; a Shell with
    Monitors gets the ``Focus_Order`` the surfaces' ones gave. A file that does not parse is
    returned unchanged."""
    result = tess_dl.parse(text.removeprefix("\ufeff"), path=path)
    if result.errors or result.document is None:
        return text, []
    root = result.document.root
    shift = 1 if text.startswith("\ufeff") else 0
    has_monitor = root.type == "Shell" and any(
        isinstance(e, tess_dl.Block) and e.type == "Monitor" for e in root.entries
    )
    ranked: list[tuple[int, int, str]] = []  # Tab_Index, position in the file, surface name
    edits: list[_Edit] = []
    for position, block in enumerate(walk(root)):
        entry = _tab_index(block)
        if entry is None:
            continue
        assert isinstance(entry.value, tess_dl.Number) and entry.key_origin is not None
        value = int(entry.value.value)
        name: str | None = None
        if has_monitor and block.type in _SURFACES:
            name = _name(block)
        elif has_monitor and block.type in _SIDES:
            frame = next((b for b in walk(root) if b.type == "Frame" and block in _all(b)), None)
            fname = _name(frame) if frame is not None else None
            if fname is not None and any(
                isinstance(e, tess_dl.Block) and e.type == "Children" for e in block.entries
            ):
                name = f"{fname}.{block.type.lower()}"
        if name is not None:
            ranked.append((value, position, name))
        elif root.type == "Shell" and (block.type in _SURFACES or block.type in _SIDES):
            continue  # a file of surfaces to import: no place for a list here, the loader says so
        elif value <= 0:
            continue  # a 0 on a block is allowed and changes nothing
        span = _remove_span(text, entry.key_origin.offset + shift)
        if span is None:
            continue
        o = entry.key_origin
        edits.append(
            _Edit(
                span[0],
                span[1],
                "",
                o.line,
                o.column,
                "tab-index",
                text[span[0] : span[1]].strip(),
                "",
            )
        )
    if has_monitor and ranked:
        ranked.sort()
        names = ", ".join(n for _, _, n in ranked)
        monitor = next(
            e for e in root.entries if isinstance(e, tess_dl.Block) and e.type == "Monitor"
        )
        assert monitor.origin is not None
        at = monitor.origin.offset + shift
        line_start = text.rfind("\n", 0, at) + 1
        indent = text[line_start:at]
        added = f"{indent}Focus_Order: [{names}]\n"
        o = monitor.origin
        edits.append(
            _Edit(line_start, line_start, added, o.line, 1, "focus-order", "", added.strip())
        )
    body, changes = text, []
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        body = body[: edit.start] + edit.text + body[edit.end :]
    for edit in sorted(edits, key=lambda e: (e.line, e.column)):
        changes.append(Change(path, edit.line, edit.column, edit.kind, edit.before, edit.after))
    return body, changes


def _all(block: tess_dl.Block) -> list[tess_dl.Block]:
    return list(walk(block))
