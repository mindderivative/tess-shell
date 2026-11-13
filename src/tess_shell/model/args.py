"""A handler's ``{{ }}`` arguments, evaluated when the event fires (Events and Actions > Call).

``On_Click { Action: Call, Target: "Clock.cycle_format", Format: {{ params.format }} }``: the
literal arguments are plain values read at load; an argument written as a slot is compiled once
and evaluated each time the event fires, in a scope that holds ``event`` (the event record), the
module's values and params, the variables of the ``For`` entries around the block and, in a
Popup's content, ``caller``. The result is a plain value (text, number, true or false, a list or a
mapping of them); anything else is an error at the slot's position and the action does not run.

Imports ``tess_el``; never ``tess_re``.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import tess_el

from tess_shell.binder import model as m
from tess_shell.model.uses import MapScope

TEL_LANGUAGE = "0.1"


class ArgError(Exception):
    """A slot of a handler could not be evaluated; ``origin`` is the slot's position."""

    def __init__(self, message: str, origin: m.Origin, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.origin = origin
        self.hint = hint


def _pos(origin: m.Origin) -> tess_el.Origin:
    return tess_el.Origin(origin.file, origin.line, origin.column)


@lru_cache(maxsize=512)
def _compiled(parts: tuple[str | m.SlotPart, ...]) -> tuple[str | tess_el.Expression, ...]:
    out: list[str | tess_el.Expression] = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        else:
            out.append(
                tess_el.compile_expression(
                    part.text, language=TEL_LANGUAGE, origin=_pos(part.origin)
                )
            )
    return tuple(out)


def check(handler: m.Handler) -> list[tess_el.TelError]:
    """The syntax errors in the slots of ``handler``'s arguments, one per slot; none if they all
    compile. The surfaces report them when the tree is resolved, so a typo is found at load and
    not on the first click."""
    found: list[tess_el.TelError] = []
    for slot in handler.slots.values():
        try:
            _compiled(slot.parts)
        except tess_el.TelError as exc:
            found.append(exc)
    return found


def event_record(key: str, raw: object) -> dict[str, Any]:
    """The event as a slot reads it (``event.name``, ``event.x``): plain values only; a field the
    event does not have is left out."""
    record: dict[str, Any] = {"name": key.removeprefix("On_").lower()}
    for name, attr in (
        ("x", "window_x"),
        ("y", "window_y"),
        ("button", "button"),
        ("old", "old_value"),
        ("new", "new_value"),
        ("text", "text"),
        ("value", "value"),
        ("delta", "delta"),
    ):
        value = getattr(raw, attr, None)
        if isinstance(value, bool | int | float | str):
            record[name] = value
    return record


def plain(value: object) -> bool:
    """Whether ``value`` is plain data: text, a number, true or false, or a list or mapping of
    them (the rule of every TEL scope, TEL Integration > The Scope)."""
    if isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list | tuple):
        return all(plain(v) for v in value)
    if isinstance(value, Mapping):
        return all(isinstance(k, str) and plain(v) for k, v in value.items())
    return False


def copy_plain(value: object, where: str = "data") -> Any:
    """A deep copy of plain data with tuples turned into lists, so what a Popup reads cannot be
    changed by, or follow, the caller's own objects. Raises ``ValueError`` naming the path of the
    first value that is not plain."""
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [copy_plain(v, f"{where}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{where}: a key is text, found {type(k).__name__}")
            out[k] = copy_plain(v, f"{where}.{k}")
        return out
    raise ValueError(
        f"{where}: {type(value).__name__} is not plain data (text, a number, true or false, a "
        "list or a mapping of them)"
    )


def evaluate(handler: m.Handler, scope: Any) -> dict[str, object]:
    """The handler's arguments: the literal ones and each slot evaluated in ``scope``. Raises
    :class:`ArgError`, naming the slot's position, when one fails or is not plain data."""
    out: dict[str, object] = dict(handler.args)
    for name, slot in handler.slots.items():
        try:
            parts = _compiled(slot.parts)
        except tess_el.TelError as exc:
            raise ArgError(f"{name}: {getattr(exc, 'message', exc)}", slot.origin) from exc
        results: list[Any] = []
        for part in parts:
            if isinstance(part, str):
                results.append(part)
                continue
            try:
                results.append(part.evaluate(scope))
            except tess_el.TelError as exc:
                message = f"{name}: {getattr(exc, 'message', exc)}"
                raise ArgError(message, slot.origin, getattr(exc, "hint", "")) from exc
        value: Any = (
            results[0]
            if slot.single
            else "".join(r if isinstance(r, str) else str(r) for r in results)
        )
        if not plain(value):
            raise ArgError(
                f"{name}: a slot gives an argument as text, a number, true or false, a list or a "
                f"mapping of them, not {type(value).__name__}",
                slot.origin,
            )
        out[name] = value
    return out


def scope_for(
    event: Mapping[str, Any],
    base: Any | None,
    entries: tuple[Any, ...] = (),
    caller: Mapping[str, Any] | None = None,
) -> Any:
    """The scope an argument slot reads: ``event`` and (in a Popup) ``caller`` over the use's own
    scope ``base``, and the loop variables of ``entries`` (outermost first) over that."""
    shell: dict[str, Any] = {"event": event}
    if caller is not None:
        shell["caller"] = caller
    scope: Any = MapScope({}, base) if base is not None else MapScope({})
    for entry in entries:
        scope = entry.scope(scope)
    return MapScope(shell, scope)
