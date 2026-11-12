"""A use of a module: where it is, what it was given, and the scope its slots read."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from tess_shell.binder import model as m


@dataclass(frozen=True, slots=True)
class Use:
    key: str  # <Module>@<uid>, the key Python gets and passes back
    module: str
    name: str  # the dotted path name, for messages
    params: Mapping[str, Any]  # plain Python values, defaults merged
    monitor: str
    origin: m.Origin
    # params written as ``{{ }}`` slots on the call, each with the kind it is read as: the model
    # evaluates them in the scope of the use that holds the call (``outer``, empty in a Popup's
    # own blocks) and ``params`` above keeps the default until it has
    slots: Mapping[str, tuple[m.SlotValue, str]] = field(default_factory=dict, compare=False)
    outer: str = ""


# the kind a slot of a param of each type is read as
PARAM_SLOT_KINDS = {
    "string": "text",
    "number": "number",
    "boolean": "bool",
    "path": "text",
    "icon": "icon",
}
# what a param that has no default and is given a slot holds until the slot has a value
PARAM_BLANKS: Mapping[str, Any] = {
    "string": "",
    "number": 0,
    "boolean": False,
    "path": "",
    "icon": "",
}


def plain_param(value: m.Value) -> Any:
    """The Python value of a literal param."""
    if isinstance(value, m.Text):
        return value.value
    if isinstance(value, m.Number):
        return value.value
    if isinstance(value, m.Bool):
        return value.value
    raise TypeError(f"not a literal param: {value!r}")


class UseScope:
    """What a module's slots can read: ``params``, what the shell supplies (``caller`` in a
    Popup's content) and the values its Python sent (TEL Integration > The Scope). Implements
    ``tess_el.Scope``; every value is plain data."""

    __slots__ = ("_params", "_shell", "_values")

    def __init__(
        self,
        params: Mapping[str, Any],
        values: Mapping[str, Any],
        shell: Mapping[str, Any] | None = None,
    ) -> None:
        self._params = dict(params)
        self._values = values
        self._shell = shell or {}

    def lookup(self, name: str) -> Any:
        if name == "params":
            return self._params
        if name in self._shell:
            return self._shell[name]
        if name in self._values:
            return self._values[name]
        raise KeyError(name)

    def names(self) -> list[str]:
        return ["params", *self._shell, *self._values]


class MapScope:
    """A scope of named plain values: what a block of a Popup's shell file (no module, so no
    ``params``) reads, and what a handler's argument slot reads on top of a use's scope."""

    __slots__ = ("_base", "_values")

    def __init__(self, values: Mapping[str, Any], base: Any | None = None) -> None:
        self._values = values
        self._base = base

    def lookup(self, name: str) -> Any:
        if name in self._values:
            return self._values[name]
        if self._base is not None:
            return self._base.lookup(name)
        raise KeyError(name)

    def names(self) -> list[str]:
        return [*self._values, *(self._base.names() if self._base is not None else [])]
