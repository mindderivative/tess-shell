"""Read ``settings.tdl`` (Settings File). Every problem is collected, one finding each."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import tess_dl
from tess_dl import Block, List, Number, Origin, Property, Value

from tess_shell.config.paths import FOLDERS, PathError, expand_path
from tess_shell.schema.findings import Finding, nearest
from tess_shell.schema.tree import child_blocks, find_property, position, properties, value_text

SETTINGS_FILE = "settings.tdl"
LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
FORMATS = ("TEXT", "JSON")
DEFAULT_MAIN_SHELL = "Main_Shell.tdl"

_ROOT_KEYS = (
    "Main_Shell",
    "Registry",
    "Directories",
    "Logging",
    "Validation",
    "Hot_Reload",
    "Reload_Debounce",
)
_LOGGING_KEYS = (
    "Level",
    "Directory",
    "Retention",
    "Format",
    "Diagnose",
    "Console",
    "Capture_Stderr",
)
_BOOL_KEYS = ("Diagnose", "Console", "Capture_Stderr")
_VALIDATION_KEYS = ("Enabled",)


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    level: str = "INFO"
    directory: Path | None = None  # None: <config>/logs
    retention: int | None = None
    format: str = "TEXT"
    diagnose: bool = False
    console: bool = True
    capture_stderr: bool = True  # accepted and stored; no behaviour in M0


@dataclass(frozen=True, slots=True)
class Settings:
    config_dir: Path
    main_shell: str = DEFAULT_MAIN_SHELL
    main_shell_path: Path | None = None
    registry: Path = Path("registry.json")
    # search list per folder name: configured entries in order, then the config default if it exists
    directories: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    validation_enabled: bool = True
    hot_reload: bool = True
    reload_debounce: float = 0.2  # seconds


class _Reader:
    def __init__(self, file: str) -> None:
        self.file = file
        self.findings: list[Finding] = []

    def error(self, origin: Origin | None, rule: str, message: str, hint: str = "") -> None:
        line, column = position(origin)
        self.findings.append(Finding(self.file, line, column, "error", rule, message, hint))

    def unknown_keys(self, block: Block, allowed: tuple[str, ...], scope: str) -> None:
        for prop in properties(block):
            if prop.key not in allowed:
                self._unknown(prop.key_origin, prop.key, allowed, scope)
        for child in child_blocks(block):
            if child.type not in allowed:
                self._unknown(child.origin, child.type, allowed, scope)
        for entry in block.entries:
            if isinstance(entry, tess_dl.If | tess_dl.For):
                self.error(
                    entry.origin,
                    "unsupported-entry",
                    f"{scope} does not take 'If' or 'For'",
                    "write plain keys",
                )

    def _unknown(
        self, origin: Origin | None, key: str, allowed: tuple[str, ...], scope: str
    ) -> None:
        close = nearest(key, allowed)
        hint = f"did you mean {', '.join(close)}?" if close else f"keys: {', '.join(allowed)}"
        self.error(origin, "unknown-key", f"unknown key '{key}' in {scope}", hint)

    def path(self, prop: Property, value: Value) -> Path | None:
        text = value_text(value)
        if text is None:
            self.error(
                value.origin, "bad-value", f"{prop.key} must be a path", "write a path or quote it"
            )
            return None
        try:
            expanded = expand_path(text)
        except PathError as exc:
            self.error(
                value.origin,
                "unresolved-path",
                f"{prop.key}: cannot resolve '{text}': {exc}",
                "set the variable or write the full path",
            )
            return None
        if not expanded.startswith("/"):
            self.error(
                value.origin,
                "relative-path",
                f"{prop.key}: '{text}' is not an absolute path",
                "start the path with / or ~",
            )
            return None
        return Path(expanded)

    def enum(self, prop: Property, allowed: tuple[str, ...]) -> str | None:
        text = value_text(prop.value)
        if text in allowed:
            return text
        hint = f"allowed: {', '.join(allowed)}"
        if text is not None and text.upper() in allowed:
            hint = f"enum values are upper case, write {text.upper()}"
        self.error(
            prop.value_origin,
            "bad-value",
            f"{prop.key} must be one of {', '.join(allowed)}",
            hint,
        )
        return None

    def boolean(self, prop: Property) -> bool | None:
        text = value_text(prop.value)
        if text in ("true", "false") and not isinstance(prop.value, tess_dl.String):
            return text == "true"
        self.error(prop.value_origin, "bad-value", f"{prop.key} must be true or false", "")
        return None

    def block(self, parent: Block, name: str) -> Block | None:
        for prop in properties(parent):
            if prop.key == name:
                self.error(
                    prop.key_origin, "bad-value", f"{name} must be a block", f"write {name} {{ }}"
                )
        for child in child_blocks(parent):
            if child.type == name:
                return child
        return None


def _logging(reader: _Reader, block: Block) -> LoggingSettings:
    reader.unknown_keys(block, _LOGGING_KEYS, "Logging")
    values: dict[str, Any] = {}
    for prop in properties(block):
        match prop.key:
            case "Level":
                values["level"] = reader.enum(prop, LEVELS)
            case "Format":
                values["format"] = reader.enum(prop, FORMATS)
            case "Directory":
                values["directory"] = reader.path(prop, prop.value)
            case "Retention":
                v = prop.value
                if isinstance(v, Number) and isinstance(v.value, int) and v.value >= 0:
                    values["retention"] = v.value
                else:
                    reader.error(
                        prop.value_origin,
                        "bad-value",
                        "Retention must be a whole number of days, 0 or more",
                        "",
                    )
            case "Diagnose" | "Console" | "Capture_Stderr":
                values[prop.key.lower()] = reader.boolean(prop)
    return replace(LoggingSettings(), **{k: v for k, v in values.items() if v is not None})


def _directories(reader: _Reader, block: Block, config: Path) -> dict[str, tuple[Path, ...]]:
    reader.unknown_keys(block, FOLDERS, "Directories")
    result: dict[str, tuple[Path, ...]] = {}
    for prop in properties(block):
        if prop.key not in FOLDERS:
            continue
        value = prop.value
        items: list[Value] = list(value.items) if isinstance(value, List) else [value]
        found: list[Path] = []
        for item in items:
            path = reader.path(prop, item)
            if path is None:
                continue
            if not path.is_dir():
                reader.error(
                    item.origin,
                    "missing-directory",
                    f"{prop.key}: '{path}' is not a directory",
                    "create it or remove the entry",
                )
                continue
            found.append(path)
        result[prop.key] = tuple(found)
    return result


def load_settings(config: Path) -> tuple[Settings | None, list[Finding]]:
    """Read ``<config>/settings.tdl``. A missing file means defaults.

    Returns ``(settings, findings)``; ``settings`` is ``None`` when any finding is an error.
    """
    path = config / SETTINGS_FILE
    reader = _Reader(SETTINGS_FILE)
    root: Block | None = None
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            return None, [
                Finding(SETTINGS_FILE, 1, 1, "error", "tdl-bad-encoding", f"cannot read: {exc}", "")
            ]
        result = tess_dl.parse(text, path=SETTINGS_FILE)
        if result.errors or result.document is None:
            return None, [
                Finding(
                    SETTINGS_FILE,
                    e.origin.line,
                    e.origin.column,
                    "error",
                    e.code,
                    e.message,
                    e.hint,
                )
                for e in result.errors
            ]
        root = result.document.root
        if root.type != "Settings":
            reader.error(
                root.origin,
                "settings-root",
                f"the root block of settings.tdl is '{root.type}', not 'Settings'",
                "write Settings { }",
            )
            return None, reader.findings

    main_shell, explicit = DEFAULT_MAIN_SHELL, False
    registry = config / "registry.json"
    directories: dict[str, tuple[Path, ...]] = {}
    logging = LoggingSettings()
    validation = True
    hot_reload = True
    debounce = 0.2
    main_origin: Origin | None = None
    if root is not None:
        reader.unknown_keys(root, _ROOT_KEYS, "Settings")
        ms = find_property(root, "Main_Shell")
        if ms is not None:
            text_ = value_text(ms.value)
            if text_ is None:
                reader.error(ms.value_origin, "bad-value", "Main_Shell must be a file name", "")
            else:
                main_shell, explicit, main_origin = text_, True, ms.value_origin
        hr = find_property(root, "Hot_Reload")
        if hr is not None and (flag := reader.boolean(hr)) is not None:
            hot_reload = flag
        rd = find_property(root, "Reload_Debounce")
        if rd is not None:
            v = rd.value
            if isinstance(v, Number) and not isinstance(v.value, bool) and v.value >= 0:
                debounce = v.value / 1000
            else:
                reader.error(
                    rd.value_origin,
                    "bad-value",
                    "Reload_Debounce is a number of milliseconds, 0 or more",
                    "",
                )
        rg = find_property(root, "Registry")
        if rg is not None:
            p = reader.path(rg, rg.value)
            if p is not None:
                registry = p
                if not p.parent.is_dir():
                    reader.error(
                        rg.value_origin,
                        "missing-directory",
                        f"Registry: '{p.parent}' is not a directory",
                        "create it or change Registry",
                    )
        if (blk := reader.block(root, "Directories")) is not None:
            directories = _directories(reader, blk, config)
        if (blk := reader.block(root, "Logging")) is not None:
            logging = _logging(reader, blk)
        if (blk := reader.block(root, "Validation")) is not None:
            reader.unknown_keys(blk, _VALIDATION_KEYS, "Validation")
            en = find_property(blk, "Enabled")
            if en is not None and (b := reader.boolean(en)) is not None:
                validation = b

    search: dict[str, tuple[Path, ...]] = {}
    for folder in FOLDERS:
        entries = list(directories.get(folder, ()))
        default = config / folder
        if default.is_dir() and default not in entries:
            # the config Icons folder comes first and the listed paths follow (Block Reference,
            # Icons); for every other folder the listed paths come first
            if folder == "Icons":
                entries.insert(0, default)
            else:
                entries.append(default)
        search[folder] = tuple(entries)

    main_path: Path | None = None
    for d in search["Shells"]:
        if (d / main_shell).is_file():
            main_path = d / main_shell
            break
    if explicit and main_path is None:
        searched = ", ".join(str(d) for d in search["Shells"]) or "no Shells directory"
        reader.error(
            main_origin,
            "main-shell-not-found",
            f"Main_Shell '{main_shell}' was not found in: {searched}",
            "put the file in a Shells directory",
        )

    if reader.findings:
        return None, reader.findings
    return (
        Settings(
            config_dir=config,
            main_shell=main_shell,
            main_shell_path=main_path,
            registry=registry,
            directories=search,
            logging=logging,
            validation_enabled=validation,
            hot_reload=hot_reload,
            reload_debounce=debounce,
        ),
        [],
    )
