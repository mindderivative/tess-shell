"""The error record of the shell and its printed form (Validation and Errors)."""

from __future__ import annotations

import difflib
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Finding:
    file: str
    line: int
    column: int
    severity: Severity
    rule: str
    message: str
    hint: str = ""

    @property
    def sort_key(self) -> tuple[str, int, int]:
        return (self.file, self.line, self.column)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def nearest(name: str, choices: Iterable[str], limit: int = 3) -> list[str]:
    """Up to ``limit`` of ``choices`` closest to ``name``, ignoring case."""
    by_lower = {c.lower(): c for c in choices}
    close = difflib.get_close_matches(name.lower(), list(by_lower), n=limit, cutoff=0.6)
    return [by_lower[c] for c in close]


def format_finding(finding: Finding, source_line: str | None = None) -> str:
    """``FILE:LINE:COL: error: MESSAGE``, the source line with a caret, and the hint."""
    out = [f"{finding.file}:{finding.line}:{finding.column}: {finding.severity}: {finding.message}"]
    if source_line is not None:
        text = source_line.rstrip("\r\n").expandtabs(4)
        number = str(finding.line)
        pad = " " * len(number)
        out.append(f"  {number} |  {text}")
        out.append(f"  {pad} |  {' ' * max(finding.column - 1, 0)}^")
    if finding.hint:
        out.append(f"    hint: {finding.hint}")
    return "\n".join(out)
