"""Find, read and check every shell file: the part ``check``, ``run`` and a reload share."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import tess_el
from tess_dl import Document

import tess_shell
from tess_shell.config.discovery import discover, is_shipped
from tess_shell.config.settings import Settings
from tess_shell.files.icons import IconSets
from tess_shell.files.loader import (
    ModuleFile,
    display_name,
    load_file,
    load_module_document,
    load_shell_file,
    load_style_file,
    register_module,
)
from tess_shell.schema.findings import Finding, render_findings
from tess_shell.schema.graph import module_cycles
from tess_shell.schema.model import ShellDef, StyleDef
from tess_shell.schema.shell import read_module, read_module_params


def source_line(config: Path, finding: Finding) -> str | None:
    path = Path(finding.file)
    if not path.is_absolute():
        path = config / path
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError, UnicodeDecodeError:
        return None
    return lines[finding.line - 1] if 0 < finding.line <= len(lines) else None


def print_findings(findings: list[Finding], config: Path) -> None:
    text, _ = render_findings(findings, lambda f: source_line(config, f))
    print(text, file=sys.stderr)


MAX_FINDINGS = 50


def installed_versions() -> dict[str, str]:
    """The versions a file's ``Shell:``, ``TRE:`` and ``TEL:`` pins are compared with."""
    return {
        "Shell": tess_shell.__version__,
        "TRE": version("tesserae-engine"),
        "TEL": tess_el.__version__,
    }


@dataclass(frozen=True, slots=True)
class Scan:
    count: int
    findings: list[Finding]
    shells: dict[Path, ShellDef]
    modules: dict[str, ModuleFile]

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]


def scan(settings: Settings, config: Path) -> Scan:
    """Discover every shell file and check it: modules first, so a shell file can call them; a
    ``*_Shell.tdl`` through stages 1 to 4, the other types for syntax only. Warnings do not stop
    anything."""
    paths = discover(settings)
    versions = installed_versions()
    findings: list[Finding] = []
    shells: dict[Path, ShellDef] = {}
    modules: dict[str, ModuleFile] = {}
    icons = IconSets(settings.directories.get("Icons", ()))
    # pass 1: every module's name and params, so a layout can call any module in any order
    documents: dict[Path, Document] = {}
    for path in paths:
        if path.name.endswith("_Module.tdl"):
            document, found = load_module_document(path, config, versions)
            findings.extend(found)
            if document is None:
                continue
            documents[path] = document
            stub = read_module_params(document, display_name(path, config))
            if stub is not None:
                findings.extend(
                    register_module(modules, ModuleFile(stub, path, is_shipped(path)), config)
                )
    stubs = {name: mf.definition for name, mf in modules.items()}
    names_by_path = {mf.path.resolve(): name for name, mf in modules.items()}

    def importer(file: Path) -> Callable[[str], str | None]:
        return lambda text: names_by_path.get((file.parent / text).resolve())

    styles: dict[Path, StyleDef | None] = {}

    def style_loader(module_path: Path) -> Callable[[str], StyleDef | None]:
        def load(text: str) -> StyleDef | None:
            path = (module_path.parent / text).resolve()
            if path not in styles:
                styles[path], found = load_style_file(path, config, versions)
                findings.extend(found)
            return styles[path]

        return load

    # pass 2: the layouts, with every module known
    for name, mf in list(modules.items()):
        full, found = read_module(
            documents[mf.path],
            display_name(mf.path, config),
            stubs,
            importer(mf.path),
            style_loader(mf.path),
            icons,
        )
        findings.extend(found)
        modules[name] = ModuleFile(full, mf.path, mf.shipped) if full else mf
        if full is None:
            del modules[name]
    findings.extend(module_cycles({n: mf.definition for n, mf in modules.items()}))
    registry = {name: mf.definition for name, mf in modules.items()}
    for path in paths:
        if path.name.endswith("_Shell.tdl"):
            shell, found = load_shell_file(path, config, versions, registry, importer(path), icons)
            if shell is not None:
                shells[path] = shell
            findings.extend(found)
        elif not path.name.endswith("_Module.tdl"):
            _, found = load_file(path, config)
            findings.extend(found)
    findings.extend(
        Finding("Icons", 1, 1, "warning", "icon-set-invalid", problem, "the set is skipped")
        for problem in icons.problems
    )
    own = sum(1 for path in paths if not is_shipped(path))  # the user's files, not the shipped ones
    return Scan(own, sorted(findings, key=lambda f: f.sort_key), shells, modules)
