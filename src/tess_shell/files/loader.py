"""Read and parse shell files. Syntax only: no suffix, root, name or schema checks yet."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import tess_dl
from tess_dl import Document

from tess_shell.config.confine import Confinement
from tess_shell.files.header import check_header
from tess_shell.schema.deprecations import deprecation_findings
from tess_shell.schema.findings import Finding
from tess_shell.schema.imports import ImportBroken, ImportedShell, ImportMissing, ShellImporter
from tess_shell.schema.look import read_stylesheet, read_theme
from tess_shell.schema.model import (
    IconSource,
    ModuleDef,
    ShellDef,
    StyleDef,
    StylesheetDef,
    ThemeDef,
)
from tess_shell.schema.shell import read_shell, read_style
from tess_shell.schema.tree import old_language_finding


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
    if result.errors:
        old = old_language_finding(text, name)
        if old is not None:  # a 0.1 file does not parse as 0.2: say why, not where it breaks
            return None, [old]
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
    name = display_name(path, base)
    header = check_header(document, name, installed)
    return (None, header) if header else (document, deprecation_findings(document, name))


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
    style, found = read_style(document, name)
    return style, [*found, *deprecation_findings(document, name)]


def load_theme_file(
    path: Path, base: Path, installed: Mapping[str, str]
) -> tuple[ThemeDef | None, list[Finding]]:
    """Stages 1 to 4 for a ``*_Theme.tdl``."""
    document, findings = load_file(path, base)
    if document is None:
        return None, findings
    name = display_name(path, base)
    header = check_header(document, name, installed)
    if header:
        return None, header
    theme, found = read_theme(document, name)
    return theme, [*found, *deprecation_findings(document, name)]


def load_stylesheet_file(
    path: Path, base: Path, installed: Mapping[str, str], module_names: set[str]
) -> tuple[StylesheetDef | None, list[Finding]]:
    """Stages 1 to 4 for a ``*_Stylesheet.tdl``."""
    document, findings = load_file(path, base)
    if document is None:
        return None, findings
    name = display_name(path, base)
    header = check_header(document, name, installed)
    if header:
        return None, header
    sheet, found = read_stylesheet(document, name, module_names)
    return sheet, [*found, *deprecation_findings(document, name)]


def shell_importer(
    base: Path,
    installed: Mapping[str, str],
    confine: Confinement,
    module_importer: Callable[[Path], Callable[[str], str | None]],
    on_target: Callable[[Path], None],
) -> ShellImporter:
    """The reader of the shell file an ``Import:`` names (stages 1 to 3: read, parse, header; the
    schema reads what is in it). The path is relative to the file that writes it and must end
    inside ``confine``. ``module_importer(file)`` is the module finder for the paths ``file``
    writes; ``on_target`` hears of every file named, found or not, so a reload can watch it."""

    def load(importer: Path, text: str) -> ImportedShell:
        target = confine.target(importer, text)
        on_target(target)
        if not target.is_file():
            raise ImportMissing(str(target))
        document, findings = load_file(target, base)
        name = display_name(target, base)
        if document is not None:
            findings = check_header(document, name, installed)
        if document is None or findings:
            raise ImportBroken(findings)
        return ImportedShell(
            target,
            Path(os.path.realpath(target)),
            name,
            document,
            confine.read_text(target),
            confine.resolve_path(target),
            module_importer(target),
        )

    return load


def load_shell_file(
    path: Path,
    base: Path,
    installed: Mapping[str, str],
    confine: Confinement,
    modules: Mapping[str, ModuleDef] | None = None,
    import_module: Callable[[str], str | None] | None = None,
    icons: IconSource | None = None,
    import_shell: ShellImporter | None = None,
) -> tuple[ShellDef | None, list[Finding]]:
    """Stages 1 to 4 for a ``*_Shell.tdl``: read, parse, header, schema. A file that fails an
    earlier stage is not checked further. A path the file writes must end inside ``confine``;
    ``import_shell`` reads the shell files its Monitors import."""
    document, findings = load_file(path, base)
    if document is None:
        return None, findings
    name = display_name(path, base)
    header = check_header(document, name, installed)
    if header:
        return None, header

    shell, findings = read_shell(
        document,
        name,
        confine.read_text(path),
        modules,
        import_module,
        icons,
        confine.resolve_path(path),
        import_shell,
        path,
    )
    return shell, [*findings, *deprecation_findings(document, name)]


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
