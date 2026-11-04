"""Read and parse shell files. Syntax only: no suffix, root, name or schema checks yet."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import tess_dl
from tess_dl import Document

from tess_shell.files.header import check_header
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import IconSource, ModuleDef, ShellDef, StyleDef
from tess_shell.schema.shell import read_shell, read_style


def display_name(path: Path, base: Path) -> str:
    """The path relative to ``base`` when it is inside it, else absolute."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def load_file(path: Path, base: Path) -> tuple[Document | None, list[Finding]]:
    name = display_name(path, base)
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return None, [
            Finding(
                name,
                1,
                1,
                "error",
                "tdl-bad-encoding",
                f"The bytes are not valid UTF-8 (at byte {exc.start}).",
                "Save the file as UTF-8",
            )
        ]
    except OSError as exc:
        return None, [
            Finding(name, 1, 1, "error", "unreadable", f"cannot read: {exc.strerror}", "")
        ]
    result = tess_dl.parse(text, path=name)
    findings = [
        Finding(name, e.origin.line, e.origin.column, "error", e.code, e.message, e.hint)
        for e in result.errors
    ]
    return (None if findings else result.document), findings


def load_all(paths: list[Path], base: Path) -> tuple[list[Document], list[Finding]]:
    documents: list[Document] = []
    findings: list[Finding] = []
    for path in paths:
        document, errors = load_file(path, base)
        findings.extend(errors)
        if document is not None:
            documents.append(document)
    return documents, findings


def load_module_document(
    path: Path, base: Path, installed: Mapping[str, str]
) -> tuple[Document | None, list[Finding]]:
    """Stages 1 to 3 for a ``*_Module.tdl``: read, parse, header."""
    document, findings = load_file(path, base)
    if document is None:
        return None, findings
    header = check_header(document, display_name(path, base), installed)
    return (None, header) if header else (document, [])


def load_style_file(
    path: Path, base: Path, installed: Mapping[str, str]
) -> tuple[StyleDef | None, list[Finding]]:
    """Stages 1 to 4 for a ``*_Style.tdl``. A file that cannot be read is ``style-not-found``."""
    if not path.is_file():
        return None, [
            Finding(
                display_name(path, base),
                1,
                1,
                "error",
                "style-not-found",
                f"the style file {display_name(path, base)} does not exist",
                "a path is relative to the module file that names it",
            )
        ]
    document, findings = load_file(path, base)
    if document is None:
        return None, findings
    name = display_name(path, base)
    header = check_header(document, name, installed)
    if header:
        return None, header
    return read_style(document, name)


def load_shell_file(
    path: Path,
    base: Path,
    installed: Mapping[str, str],
    modules: Mapping[str, ModuleDef] | None = None,
    import_module: Callable[[str], str | None] | None = None,
    icons: IconSource | None = None,
) -> tuple[ShellDef | None, list[Finding]]:
    """Stages 1 to 4 for a ``*_Shell.tdl``: read, parse, header, schema. A file that fails an
    earlier stage is not checked further."""
    document, findings = load_file(path, base)
    if document is None:
        return None, findings
    name = display_name(path, base)
    header = check_header(document, name, installed)
    if header:
        return None, header

    def read_text(relative: str) -> str:
        return (path.parent / relative).read_text(encoding="utf-8")

    shell, findings = read_shell(document, name, read_text, modules, import_module, icons)
    return shell, findings


@dataclass(frozen=True, slots=True)
class ModuleFile:
    """A module file that was read: its definition, where it is, and whether it ships with the
    shell. Its Python is next to it, with the same name and the suffix ``.py``."""

    definition: ModuleDef
    path: Path
    shipped: bool

    @property
    def python(self) -> Path:
        return self.path.with_suffix(".py")


def register_module(registry: dict[str, ModuleFile], new: ModuleFile, base: Path) -> list[Finding]:
    """Add ``new`` to ``registry`` by its call name. A user module overrides a shipped one; two of
    the same kind are an error naming both (TDL Language > Names and the Registry)."""
    name = new.definition.name
    have = registry.get(name)
    if have is None or (have.shipped and not new.shipped):
        registry[name] = new
        return []
    if new.shipped and not have.shipped:
        return []
    first = display_name(have.path, base)
    origin = new.definition.origin
    return [
        Finding(
            display_name(new.path, base),
            origin.line,
            origin.column,
            "error",
            "name-duplicate",
            f"the module name {name} is already used by {first}",
            "a name is registered once; a user module may share a shipped module's name",
        )
    ]
