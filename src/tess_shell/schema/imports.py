"""A shell file that another one imports (Shell File > Structure, D22).

The schema does no I/O: when a Monitor's ``Children`` write ``Import: Top_Shell.tdl`` the loader
finds, reads and parses that file and hands the schema an :class:`ImportedShell`. A file it cannot
give is one of the exceptions here, or :class:`~tess_shell.config.confine.PathOutsideConfig`.
Standard library and ``tess_dl`` only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tess_dl import Document

from tess_shell.schema.findings import Finding


@dataclass(frozen=True, slots=True)
class ImportedShell:
    """A shell file that was read and parsed, with what the schema needs to read what is in it:
    the paths it writes are relative to ``path``."""

    path: Path  # absolute, ``..`` folded away: what its own relative paths start from
    identity: Path  # the real path, symbolic links followed: two names of one file are one file
    name: str  # as a finding names it (relative to the configuration folder)
    document: Document
    read_text: Callable[[str], str]
    resolve_path: Callable[[str], str]
    import_module: Callable[[str], str | None]


class ImportMissing(Exception):
    """The file an ``Import:`` names does not exist; ``tried`` is the path that was looked at."""

    def __init__(self, tried: str) -> None:
        super().__init__(tried)
        self.tried = tried


class ImportBroken(Exception):
    """The file exists and cannot be used (it does not parse, or fails the header checks);
    ``findings`` say why, each at its position in that file."""

    def __init__(self, findings: list[Finding]) -> None:
        super().__init__(findings[0].message if findings else "")
        self.findings = findings


# (the file that writes the Import, the text it wrote) -> the file it names
ShellImporter = Callable[[Path, str], ImportedShell]
