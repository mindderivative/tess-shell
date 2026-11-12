"""Find, read and check every shell file: the part ``check``, ``run`` and a reload share."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path

import tess_el
from tess_dl import Document

import tess_shell
from tess_shell.appearance import Appearance
from tess_shell.config.discovery import discover, is_shipped, shipped_dir
from tess_shell.config.settings import Settings
from tess_shell.files.icons import IconSets
from tess_shell.files.loader import (
    ModuleFile,
    display_name,
    load_file,
    load_module_document,
    load_shell_file,
    load_style_file,
    load_stylesheet_file,
    load_theme_file,
    register_module,
)
from tess_shell.model.icons import RuntimeIcons
from tess_shell.model.look import Look, check_parts, check_states, check_tokens, make_look
from tess_shell.schema.findings import Finding, nearest, render_findings
from tess_shell.schema.graph import module_cycles
from tess_shell.schema.look import effective_tokens
from tess_shell.schema.model import ShellDef, StyleDef, StylesheetDef, ThemeDef
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
DEFAULT_THEME = "Default"


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
    themes: dict[str, ThemeDef] = field(default_factory=dict)
    stylesheets: dict[str, StylesheetDef] = field(default_factory=dict)
    icons: RuntimeIcons | None = None  # the icon sets, for a name a module sends

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
    # the shipped mdi set is searched last: a set of the same prefix in the user's folders wins
    icons = IconSets([*settings.directories.get("Icons", ()), shipped_dir() / "Icons"])
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

    def file_readers(
        module_path: Path,
    ) -> tuple[Callable[[str], str], Callable[[str], str]]:
        def read_text(relative: str) -> str:
            return (module_path.parent / relative).read_text(encoding="utf-8")

        def resolve_path(relative: str) -> str:
            return os.path.abspath(module_path.parent / os.path.expanduser(relative))

        return read_text, resolve_path

    # pass 2: the layouts, with every module known
    for name, mf in list(modules.items()):
        read_text, resolve_path = file_readers(mf.path)
        full, found = read_module(
            documents[mf.path],
            display_name(mf.path, config),
            stubs,
            importer(mf.path),
            style_loader(mf.path),
            icons,
            read_text,
            resolve_path,
        )
        findings.extend(found)
        modules[name] = ModuleFile(full, mf.path, mf.shipped) if full else mf
        if full is None:
            del modules[name]
    findings.extend(module_cycles({n: mf.definition for n, mf in modules.items()}))
    registry = {name: mf.definition for name, mf in modules.items()}
    themes: dict[str, ThemeDef] = {}
    stylesheets: dict[str, StylesheetDef] = {}
    theme_shipped: dict[str, bool] = {}
    sheet_shipped: dict[str, bool] = {}
    for path in paths:
        if path.name.endswith("_Theme.tdl"):
            theme, found = load_theme_file(path, config, versions)
            findings.extend(found)
            if theme is not None:
                findings.extend(_register(themes, theme_shipped, theme, path, config))
        elif path.name.endswith("_Stylesheet.tdl"):
            sheet, found = load_stylesheet_file(path, config, versions, set(registry))
            findings.extend(found)
            if sheet is not None:
                findings.extend(_register(stylesheets, sheet_shipped, sheet, path, config))
    for path in paths:
        if path.name.endswith("_Shell.tdl"):
            shell, found = load_shell_file(path, config, versions, registry, importer(path), icons)
            if shell is not None:
                shells[path] = shell
            findings.extend(found)
        elif path.name.endswith("_Style.tdl"):
            _, found = load_file(path, config)
            findings.extend(found)
    findings.extend(
        Finding("Icons", 1, 1, "warning", "icon-set-invalid", problem, "the set is skipped")
        for problem in icons.problems
    )
    findings.extend(_check_look(settings, themes, stylesheets, shells, modules))
    own = sum(1 for path in paths if not is_shipped(path))  # the user's files, not the shipped ones
    return Scan(
        own,
        sorted(findings, key=lambda f: f.sort_key),
        shells,
        modules,
        themes,
        stylesheets,
        RuntimeIcons(icons),
    )


def _register[T: (ThemeDef, StylesheetDef)](
    registry: dict[str, T], shipped: dict[str, bool], new: T, path: Path, base: Path
) -> list[Finding]:
    """By the metadata ``Name``: a user file overrides a shipped one, two user files are an
    error. ``shipped`` remembers which registered files ship with the package."""
    is_new_shipped = is_shipped(path)
    have = registry.get(new.name)
    if have is None or (shipped[new.name] and not is_new_shipped):
        registry[new.name] = new
        shipped[new.name] = is_new_shipped
        return []
    if is_new_shipped:
        return []
    return [
        Finding(
            display_name(path, base),
            1,
            1,
            "error",
            "name-duplicate",
            f"the name {new.name} is already used by {have.file}",
            "a name is registered once; a user file may share a shipped file's name",
        )
    ]


def _check_look(
    settings: Settings,
    themes: dict[str, ThemeDef],
    stylesheets: dict[str, StylesheetDef],
    shells: dict[Path, ShellDef],
    modules: dict[str, ModuleFile],
) -> list[Finding]:
    """The chosen theme and stylesheets exist, and every ``$token`` a layout names is in the
    theme and of the kind its key reads."""
    out: list[Finding] = []
    chosen = settings.appearance.theme or DEFAULT_THEME
    theme = themes.get(chosen)
    if theme is None:
        close = nearest(chosen, themes)
        out.append(
            Finding(
                "settings.tdl",
                1,
                1,
                "error",
                "theme-not-found",
                f"Appearance.Theme names '{chosen}', which no theme file has as its Name",
                f"did you mean {', '.join(close)}?" if close else f"themes: {', '.join(themes)}",
            )
        )
    for name in settings.appearance.stylesheets:
        if name not in stylesheets:
            close = nearest(name, stylesheets)
            out.append(
                Finding(
                    "settings.tdl",
                    1,
                    1,
                    "error",
                    "stylesheet-not-found",
                    f"Appearance.Stylesheets names '{name}', which no stylesheet has as its Name",
                    f"did you mean {', '.join(close)}?"
                    if close
                    else f"stylesheets: {', '.join(stylesheets)}",
                )
            )
    if theme is None:
        return out
    tokens = effective_tokens(theme, Appearance(), themes.get(DEFAULT_THEME))
    rules = [
        r
        for name in settings.appearance.stylesheets
        if name in stylesheets
        for r in stylesheets[name].rules
    ]
    stated: list[Finding] = []  # a rule reaches many blocks: the warning is one per rule
    for shell in shells.values():
        for monitor in shell.monitors:
            for bar in monitor.surfaces:
                out.extend(check_tokens(bar.children, tokens, bar.style))
                stated.extend(check_states(bar.children, rules))
            for frame in monitor.frames:
                refs = dict(frame.style)
                for label, border in (
                    ("Inner_Border", frame.inner_border),
                    ("Outer_Border", frame.outer_border),
                ):
                    if border is not None and border.color is not None:
                        refs[f"{label}.Color"] = border.color
                out.extend(check_tokens((), tokens, refs))
                for edge in frame.edges.values():
                    out.extend(check_tokens(edge.children, tokens))
                    stated.extend(check_states(edge.children, rules))
                for panel in frame.melds:
                    out.extend(check_tokens(panel.children, tokens, panel.style))
                    stated.extend(check_states(panel.children, rules))
    for name, mf in modules.items():
        out.extend(check_tokens(mf.definition.children, tokens))
        stated.extend(check_states(mf.definition.children, rules, name))
    out.extend({(f.file, f.line, f.column, f.message): f for f in stated}.values())
    out.extend(check_parts({name: mf.definition for name, mf in modules.items()}, rules))
    return out


def build_look(result: Scan, settings: Settings, appearance: Appearance) -> Look:
    """The look the scan's theme and stylesheets give for ``appearance``. The scan reported an
    error for a name it could not find, so the caller has already stopped on one."""
    theme = result.themes[settings.appearance.theme or DEFAULT_THEME]
    sheets = [result.stylesheets[name] for name in settings.appearance.stylesheets]
    return make_look(theme, sheets, appearance, result.themes.get(DEFAULT_THEME), result.icons)
