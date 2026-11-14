"""Read ``settings.tdl`` (Settings File). Every problem is collected, one finding each."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import tess_dl
from tess_dl import Block, List, Number, Origin, Property, Value

from tess_shell.config.paths import FOLDERS, PathError, expand_path
from tess_shell.schema.findings import Finding, nearest
from tess_shell.schema.keys import Chord, ChordError, parse_chord
from tess_shell.schema.tree import child_blocks, find_property, position, properties, value_text

SETTINGS_FILE = "settings.tdl"
LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
FORMATS = ("TEXT", "JSON")
DEFAULT_MAIN_SHELL = "Main_Shell.tdl"

ROOT_KEYS = (
    "Main_Shell",
    "Registry",
    "Directories",
    "Logging",
    "Validation",
    "Hot_Reload",
    "Reload_Debounce",
    "Appearance",
    "Debug",
    "Control",
    "Shortcuts",
    "Global_Shortcuts",
)
DEBUG_KEYS = ("Panel_Hide", "Frame_Join", "Frame_Blend")
PANEL_HIDE = ("CLOSE", "KEEP")
FRAME_JOIN = ("SMIL", "CONCAVE", "SHADER", "STRUCTURE", "PARAM")
FRAME_BLEND = ("SRGB", "LINEAR")
APPEARANCE_KEYS = ("Theme", "Stylesheets", "Follow_Desktop")
LOGGING_KEYS = (
    "Level",
    "Directory",
    "Retention",
    "Format",
    "Diagnose",
    "Console",
    "Capture_Stderr",
)
_BOOL_KEYS = ("Diagnose", "Console", "Capture_Stderr")
VALIDATION_KEYS = ("Enabled",)
# the five actions of Focus and Keyboard, written in ``Shortcuts { }`` with the keys of the user
FIXED_SHORTCUTS = (
    "Enter_Shortcut_Mode",
    "Exit_Shortcut_Mode",
    "Set_Shortcut_Mode",
    "Next_Focus",
    "Previous_Focus",
)
# ``Toggle_<Name>``, ``Show_<Name>``, ``Hide_<Name>``: the verb is the text before the first
# underscore, the rest is the Name of a surface
SHORTCUT_VERBS = ("Toggle", "Show", "Hide")
_VERB_FORM = re.compile(r"^(Toggle|Show|Hide)_([A-Za-z][A-Za-z0-9_]*)$")
_ENTRY_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


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
class AppearanceSettings:
    theme: str | None = None  # a theme's metadata Name; None: the shell's default theme
    stylesheets: tuple[str, ...] = ()  # stylesheets' metadata Names, lowest priority first
    follow_desktop: bool = True  # read the Settings portal (Portals > Configuration)


@dataclass(frozen=True, slots=True)
class DebugSettings:
    """Switches for finding a fault (D44)."""

    # how a Panel is hidden: KEEP, the default (maintainer, 2026-11-06), leaves the surface mapped
    # and draws nothing, so a hidden Panel keeps its tree and state. CLOSE destroys the window and
    # makes a new one on show.
    panel_hide: str = "KEEP"
    # how the join of a melded Panel animates while it slides (the Frame's join options, all built
    # so they can be compared): PARAM, the default (the maintainer's choice after the KWin
    # comparison), animates the numbers of a path template; SMIL morphs the one contour in an svg;
    # CONCAVE moves boxes with concave corners; SHADER draws the join in a shader; STRUCTURE morphs
    # path data command by command. A restart applies it.
    frame_join: str = "PARAM"
    # how the Frame's ring is blended: LINEAR, the default (maintainer, 2026-11-12), draws the ring
    # in one fill shader that blends in linear light, so a light border reads as wide on a curve as
    # on a straight (TRE-REQ-015, option 2); SRGB draws the bands as paths and tre blends their
    # anti-aliased edges in sRGB (a light line on a dark ground looks thinner on a curve). A
    # Frame the shader cannot draw falls back to paths with one warning. A restart applies it.
    frame_blend: str = "LINEAR"


@dataclass(frozen=True, slots=True)
class ShortcutEntry:
    """One entry of ``Shortcuts { }`` (Global Shortcuts > Action Names and Forms). ``kind`` is
    ``fixed`` (one of ``FIXED_SHORTCUTS``), ``toggle``, ``show`` or ``hide`` (``target`` is the Name
    of a surface) or ``handler`` (a block: ``block`` holds it, ``target`` is empty). ``line`` and
    ``column`` are where the entry's name is written, for the warnings that name it."""

    name: str
    kind: str
    target: str
    chord: Chord
    line: int
    column: int
    block: Block | None = field(default=None, compare=False)


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
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    debug: DebugSettings = field(default_factory=DebugSettings)
    # export the shell's own D-Bus interface (IPC and CLI > Configuration): false runs the shell
    # with no bus name and no control commands; a restart applies it
    control: bool = True
    # register the shell's shortcuts with the desktop's shortcut service (Global Shortcuts >
    # Configuration): false makes no call to it at all; hot reload applies it
    global_shortcuts: bool = True
    shortcuts: tuple[ShortcutEntry, ...] = ()  # the ``Shortcuts { }`` block, in file order


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
    reader.unknown_keys(block, LOGGING_KEYS, "Logging")
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


def _appearance(reader: _Reader, block: Block) -> AppearanceSettings:
    reader.unknown_keys(block, APPEARANCE_KEYS, "Appearance")
    values: dict[str, Any] = {}
    for prop in properties(block):
        match prop.key:
            case "Theme":
                text_ = value_text(prop.value)
                if text_ is None:
                    reader.error(prop.value_origin, "bad-value", "Theme must be a theme's Name", "")
                else:
                    values["theme"] = text_
            case "Stylesheets":
                v = prop.value
                names = [value_text(i) for i in (v.items if isinstance(v, List) else [v])]
                if any(n is None for n in names):
                    reader.error(
                        prop.value_origin,
                        "bad-value",
                        "Stylesheets is a stylesheet Name or a list of them",
                        "",
                    )
                else:
                    values["stylesheets"] = tuple(n for n in names if n is not None)
            case "Follow_Desktop":
                values["follow_desktop"] = reader.boolean(prop)
    return replace(AppearanceSettings(), **{k: v for k, v in values.items() if v is not None})


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


def _chord(reader: _Reader, origin: Origin | None, text: str | None) -> Chord | None:
    if text is None:
        reader.error(origin, "bad-value", 'keys are a string such as "Ctrl+Space"', "")
        return None
    try:
        return parse_chord(text)
    except ChordError as exc:
        reader.error(origin, "bad-value", exc.message, exc.hint)
        return None


def _shortcuts(reader: _Reader, block: Block) -> tuple[ShortcutEntry, ...]:
    """``Shortcuts { Toggle_Launcher: "Meta+Space", Volume_Up { Keys: "...", Action: ... } }``
    (Global Shortcuts > Action Names and Forms). The keys are read here (a string that is no key
    string is an error at its place); whether a surface named in a ``Toggle_<Name>`` exists, and the
    handler of a block entry, are judged when the shell files are known (``tess_shell.shortcuts``).
    """
    entries: list[ShortcutEntry] = []
    seen: dict[str, tuple[int, int]] = {}

    def once(name: str, origin: Origin | None) -> bool:
        line, column = position(origin)
        if name in seen:
            first = seen[name]
            reader.error(
                origin,
                "shortcut-duplicate",
                f"the shortcut {name} is written twice, first at {first[0]}:{first[1]}",
                "an action has one entry",
            )
            return False
        seen[name] = (line, column)
        return True

    for prop in properties(block):
        verb = _VERB_FORM.match(prop.key)
        if prop.key not in FIXED_SHORTCUTS and verb is None:
            close = nearest(prop.key, FIXED_SHORTCUTS)
            hint = (
                f"did you mean {', '.join(close)}?"
                if close
                else f"the actions: {', '.join(FIXED_SHORTCUTS)}, Toggle_<Name>, Show_<Name>, "
                "Hide_<Name>; or a block with Keys and Action"
            )
            reader.error(prop.key_origin, "unknown-key", f"unknown shortcut {prop.key}", hint)
            continue
        chord = _chord(reader, prop.value_origin, value_text(prop.value))
        if chord is None or not once(prop.key, prop.key_origin):
            continue
        line, column = position(prop.key_origin)
        if verb is None:
            entries.append(ShortcutEntry(prop.key, "fixed", prop.key, chord, line, column))
        else:
            entries.append(ShortcutEntry(prop.key, verb[1].lower(), verb[2], chord, line, column))
    for child in child_blocks(block):
        name = child.type
        if name in FIXED_SHORTCUTS or _VERB_FORM.match(name):
            reader.error(
                child.origin,
                "bad-name",
                f"{name} is written as a block, which is a handler of your own: its name may "
                "not be one of the fixed actions or start with Toggle_, Show_ or Hide_",
                f'write {name}: "keys" for the shell\'s own action, or rename the handler',
            )
            continue
        keys = find_property(child, "Keys")
        if keys is None:
            reader.error(
                child.origin,
                "missing-key",
                f"the shortcut {name} needs Keys",
                f'write {name} {{ Keys: "Ctrl+Alt+T", Action: ... }}',
            )
            continue
        chord = _chord(reader, keys.value_origin, value_text(keys.value))
        if chord is None or not once(name, child.origin):
            continue
        line, column = position(child.origin)
        entries.append(ShortcutEntry(name, "handler", "", chord, line, column, child))
    for entry in block.entries:
        if isinstance(entry, tess_dl.If | tess_dl.For):
            reader.error(
                entry.origin,
                "unsupported-entry",
                "Shortcuts does not take 'If' or 'For'",
                "write plain entries",
            )
    return tuple(sorted(entries, key=lambda e: (e.line, e.column)))


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
    appearance = AppearanceSettings()
    debug = DebugSettings()
    control = True
    global_shortcuts = True
    shortcuts: tuple[ShortcutEntry, ...] = ()
    main_origin: Origin | None = None
    if root is not None:
        reader.unknown_keys(root, ROOT_KEYS, "Settings")
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
        ct = find_property(root, "Control")
        if ct is not None and (flag := reader.boolean(ct)) is not None:
            control = flag
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
        if (blk := reader.block(root, "Appearance")) is not None:
            appearance = _appearance(reader, blk)
        if (blk := reader.block(root, "Debug")) is not None:
            reader.unknown_keys(blk, DEBUG_KEYS, "Debug")
            hide, join = find_property(blk, "Panel_Hide"), find_property(blk, "Frame_Join")
            blend = find_property(blk, "Frame_Blend")
            hide_word = None if hide is None else reader.enum(hide, PANEL_HIDE)
            join_word = None if join is None else reader.enum(join, FRAME_JOIN)
            blend_word = None if blend is None else reader.enum(blend, FRAME_BLEND)
            debug = DebugSettings(
                panel_hide=hide_word or debug.panel_hide,
                frame_join=join_word or debug.frame_join,
                frame_blend=blend_word or debug.frame_blend,
            )
        if (blk := reader.block(root, "Validation")) is not None:
            reader.unknown_keys(blk, VALIDATION_KEYS, "Validation")
            en = find_property(blk, "Enabled")
            if en is not None and (b := reader.boolean(en)) is not None:
                validation = b
        gs = find_property(root, "Global_Shortcuts")
        if gs is not None and (flag := reader.boolean(gs)) is not None:
            global_shortcuts = flag
        if (blk := reader.block(root, "Shortcuts")) is not None:
            shortcuts = _shortcuts(reader, blk)

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
            appearance=appearance,
            debug=debug,
            control=control,
            global_shortcuts=global_shortcuts,
            shortcuts=shortcuts,
        ),
        [],
    )
