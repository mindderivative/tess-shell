"""What an ``@action`` method declares (Events and Actions > Call), from a class or a method.

Standard library only: the module host reads it from the class it imported, and a module process
(``tess_shell.modproc.child``) reads it from the class it imported there and tells the shell.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """What an ``@action`` method declares after ``event`` (Events and Actions > Call): the
    arguments a handler may write. ``names`` are its parameters after ``event`` (the ones a call
    can pass by keyword), ``required`` those with no default, ``kwargs`` whether it has
    ``**kwargs``. An action with no parameter after ``event`` and no ``**kwargs`` declares nothing
    and takes any arguments through ``event.args``; one with ``**kwargs`` takes any arguments too,
    and gets them as keywords."""

    first: str
    names: tuple[str, ...] = ()
    required: frozenset[str] = frozenset()
    kwargs: bool = False

    @property
    def checked(self) -> bool:
        """Whether a handler's argument names are checked against ``names`` at load."""
        return bool(self.names) and not self.kwargs

    def keywords(self, args: Mapping[str, object]) -> dict[str, object]:
        """The arguments a call passes as keywords: the declared ones (all that are identifiers,
        for ``**kwargs``). ``event.args`` holds every argument whatever this gives."""
        if self.kwargs:
            return {k: v for k, v in args.items() if k.isidentifier() and k != self.first}
        return {k: args[k] for k in self.names if k in args}


def action_spec(fn: Callable[..., Any]) -> ActionSpec:
    """The :class:`ActionSpec` of a bound method marked ``@action``: its first parameter is the
    event, the others are the arguments."""
    params = list(inspect.signature(fn).parameters.values())
    if not params:
        return ActionSpec("event")
    names: list[str] = []
    required: set[str] = set()
    kwargs = False
    for p in params[1:]:
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            kwargs = True
        elif p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            names.append(p.name)
            if p.default is inspect.Parameter.empty:
                required.add(p.name)
    return ActionSpec(params[0].name, tuple(names), frozenset(required), kwargs)


def actions_of(cls: type) -> list[str]:
    """The names of the methods of ``cls`` marked ``@action``, sorted."""
    return sorted(
        name
        for name, member in inspect.getmembers(cls, callable)
        if getattr(member, "__tess_action__", False)
    )
