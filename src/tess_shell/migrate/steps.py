"""The ordered migration steps. A step rewrites text only and is idempotent: a file already at the
step's ``to`` comes back unchanged. A new minor that changes a user's files adds a step at the end
of ``STEPS`` with the next number; a number is never reused or reordered."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tess_shell.migrate.rename import rename_deprecated
from tess_shell.migrate.slots import Change, rewrite_slots

Apply = Callable[..., tuple[str, list[Change]]]  # (text, *, path) -> (new text, edits)


@dataclass(frozen=True, slots=True)
class Step:
    id: str
    source: str  # ``from``: a language or shell version
    target: str  # ``to``
    summary: str
    apply: Apply


STEPS: tuple[Step, ...] = (
    Step(
        "0001",
        "TDL 0.1",
        "TDL 0.2",
        "a slot is written <| expression |>, not {{ expression }}; TDL: 0.1 becomes TDL: 0.2",
        rewrite_slots,
    ),
    Step(
        "0002",
        "deprecated names",
        "current names",
        "a deprecated key or block is written under its new name",
        rename_deprecated,
    ),
)
