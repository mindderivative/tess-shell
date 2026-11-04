"""A use of a module: where it is, what it was given, and the scope its slots read."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
    """What a module's slots can read: ``params`` and the values its Python sent (TEL Integration >
    The Scope). Implements ``tess_el.Scope``; every value is plain data."""

    __slots__ = ("_params", "_values")

    def __init__(self, params: Mapping[str, Any], values: Mapping[str, Any]) -> None:
        self._params = dict(params)
        self._values = values

    def lookup(self, name: str) -> Any:
        if name == "params":
            return self._params
        if name in self._values:
            return self._values[name]
        raise KeyError(name)

    def names(self) -> list[str]:
        return ["params", *self._values]
