"""The tables and example listings of the user guide (``guide/``), generated from the code.

The guide's pages are written by hand, except for the parts between a pair of marker comments

    <!-- BEGIN generated: <name> -->
    ...
    <!-- END generated: <name> -->

which this module writes from what the shell itself says: the schema export
(``tess_shell.schema.export.schema_dict()``), the argparse parser of ``tess_shell.cli``, the exit
codes, ``pyproject.toml`` and the example folders under ``guide/examples/``. Nothing a table holds
(a default, a count, a key name) is typed by hand, so a change in the code that the guide does not
follow fails ``tests/test_guide_tables.py`` until the pages are generated again with

    env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.guide_tables

``--check`` writes nothing and exits 1 when a page is out of date. The names a marker may have:

    version-info, release-state, dependencies, kinds, blocks, style-keys, surface:<Root>, events,
    actions,
    module-index, module-common-keys, module:<Name>, shipped-panels, shipped-popups, tokens,
    system-tokens, settings:<Section>, shortcut-forms, key-names, cli-global-options,
    cli-commands, cli-help, cli-command-help, exit-codes, example-set:<page>/<set>
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import sys
import tomllib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

from tess_shell.cli import _build_parser
from tess_shell.exit_codes import ExitCode
from tess_shell.schema.export import schema_dict

REPO = Path(__file__).resolve().parents[1]
GUIDE = REPO / "guide"
EXAMPLES = GUIDE / "examples"

MARKER = re.compile(
    r"<!-- BEGIN generated: (?P<name>[^>]+?) -->\n(?P<body>.*?)<!-- END generated: (?P=name) -->",
    re.S,
)

# What the guide says about each dependency of the wheel. A dependency with no line here is a
# failure of the guide test: say what it is for before the guide goes out.
DEPENDENCY_NOTES: dict[str, str] = {
    "tesserae-engine": "the rendering engine (imported as `tess_re`)",
    "tesserae-el": "the expression language of the `<| |>` slots (imported as `tess_el`)",
    "tesserae-dl": "the reader of TDL files (imported as `tess_dl`)",
    "tesserae-utils": "shared helpers (imported as `tess_utils`)",
    "loguru": "the log",
    "inotify-simple": "notices a saved file, for hot reload",
    "dbus-fast": "the shell's own D-Bus connection",
    "pillow": "decodes the pictures of `Image`",
    "jeepney": "a light D-Bus client that the control commands use",
}

# The meaning of each exit code (``tess_shell.exit_codes.ExitCode``).
EXIT_NOTES: dict[str, str] = {
    "OK": "Done.",
    "CONFIG": (
        "The files have errors (`check`, `run`, `reload`), a control command ran and failed "
        "(an unknown name, an action that raised), or `install-session` kept a file that "
        "differs."
    ),
    "ENVIRONMENT": (
        "The machine cannot run it: no Wayland compositor with layer-shell, no session bus, "
        "`XDG_RUNTIME_DIR` unusable, the config folder missing (`check`), or `systemctl` missing "
        "or refusing (`install-session`)."
    ),
    "NOT_RUNNING": "A control command found no running shell.",
    "ALREADY_RUNNING": "A second `run`: another shell holds the instance lock.",
    "TIMEOUT": "A control command got no answer within `--timeout` seconds.",
    "LOST_COMPOSITOR": (
        "The Wayland connection was lost (the compositor went away). The shell stops what it "
        "runs first, then leaves with this code so that `Restart=on-failure` of the systemd unit "
        "starts it again."
    ),
    "INTERNAL": "An unexpected error inside the shell (it is in the log).",
    "FORCED": "A second signal made the shell leave at once.",
}

KIND_NAMES: dict[str, str] = {
    "string": "text",
    "text_or_number": "text or number",
    "name": "name",
    "name_ref": "name of a surface",
    "bool": "true or false",
    "enabled": "true or false",
    "number": "number",
    "whole": "whole number",
    "percent": "percentage",
    "length": "length",
    "sides": "sides",
    "radius": "radius",
    "color": "colour",
    "enum": "word",
    "list": "list",
    "font": "font",
    "duration": "milliseconds",
    "path": "path",
    "icon": "icon",
    "shadows": "shadows",
    "input_region": "`[]` or `AUTO`",
    "block": "block",
    "tooltip": "tooltip",
    "monitor_index": "number or `default`",
    "key_chord": "key",
    "token_ref": "token",
    "expression": "slot",
}

MODE_NAMES = {
    "light": "light",
    "dark": "dark",
    "high_contrast": "high contrast",
    "reduced_motion": "reduced motion",
}

SETTINGS_SECTIONS = (
    "Settings",
    "Directories",
    "Logging",
    "Validation",
    "Shortcuts",
    "Appearance",
    "KWin",
    "Debug",
)

# the roots that page 4 tabulates, in the order of the page
SURFACE_ROOTS = (
    "Monitor",
    "Bar",
    "Panel",
    "Popup",
    "Tooltip",
    "Frame",
    "Edge",
    "Border",
    "Animation",
    "Peek",
    "Edge_Peek",
)

TEXT_SUFFIXES = (".tdl", ".py", ".json")
LANGUAGE = {".tdl": "tdl", ".py": "python", ".json": "json"}

# What each kind of value is, in a user's words. The schema's own notes speak of its internals, so
# the guide has these; a kind the schema gains has none and fails the guide test until one is added.
KIND_HELP: dict[str, str] = {
    "string": "Text, in double quotes (a single word may be written without).",
    "text_or_number": "A number or text.",
    "name": "Letters, digits and `_`, starting with a letter.",
    "name_ref": "The `Name` of another block or surface of the shell, written exactly.",
    "bool": "`true` or `false`, in lower case.",
    "enabled": (
        "`true` or `false`; `false` disables the block (the key is `Enabled`, not `Disabled`)."
    ),
    "number": "A number.",
    "whole": "A whole number.",
    "percent": "A percentage such as `20%`, within the range the key allows.",
    "length": (
        "Pixels (a whole number), a percentage such as `50%`, or `AUTO` (fit the content); "
        "`EXPAND` (take the free space) only where a table allows it."
    ),
    "sides": (
        "One number for all four sides, a list of four `[left, top, right, bottom]`, or a block "
        "of named sides (`Left`, `Top`, `Right`, `Bottom`; a side not named is 0)."
    ),
    "radius": "One number for all corners, or a list of four corners clockwise from the top left.",
    "color": (
        "A quoted colour in one of these forms: {forms}, or `rgba(r g b a)` with alpha from 0.0 "
        "to 1.0. Where a table lists theme tokens, a token such as `$color.surface` also works "
        "([Styling and themes](06-styling.md#tokens))."
    ),
    "enum": "One upper-case word of the choices the table lists.",
    "list": (
        "A list written `[a, b]`. Where a table says one value is also accepted, a single item "
        "may be written without brackets."
    ),
    "font": "A font family name, or a list of names in the order of fallback.",
    "duration": "A time in milliseconds.",
    "path": (
        "A file or folder path. In a shell file a relative path is relative to that file; "
        "in `settings.tdl` a path starts with `/` or `~`."
    ),
    "icon": "An icon name such as `mdi:account`; the prefix selects an icon set.",
    "shadows": "A block of `Shadow` blocks, the first on top, or `$elevation.max`.",
    "input_region": "`[]` (nothing takes the pointer) or `AUTO` (only the drawn shapes do).",
    "block": "A block of its own.",
    "tooltip": "A Popup's `Name`, a short quoted text, or an inline `Tooltip` block.",
    "monitor_index": "A whole number from 0, or the word `default`.",
    "key_chord": (
        'A key press: modifiers and one key joined by `+`, such as `"Ctrl+Shift+F1"` '
        "([Keyboard and shortcuts](08-keyboard.md#key-names))."
    ),
    "token_ref": "`$group.name`, a theme token ([Styling and themes](06-styling.md#tokens)).",
    "expression": "`<| ... |>`, an expression that a module's layout uses to show a value.",
}


# -- small helpers -------------------------------------------------------------------------------


def prose(text: object) -> str:
    """Text from the schema's docstrings made safe to put in a page: doubled backticks become
    single ones, and a `<` outside a code span (``Toggle_<Name>``) is escaped so that it is not
    taken for the start of an HTML tag."""
    parts = re.split(r"(`[^`]*`)", str(text).replace("``", "`"))
    return "".join(p if p.startswith("`") else p.replace("<", "&lt;") for p in parts)


def cell(text: object) -> str:
    """One table cell: prose, on one line, with a pipe escaped."""
    flat = re.sub(r"\s+", " ", prose(text))
    return flat.replace("|", "\\|").strip()


def code(text: object) -> str:
    return f"`{text}`"


def table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(cell(c) for c in row) + " |" for row in rows)
    return "\n".join(lines)


def names(items: Sequence[object]) -> str:
    return ", ".join(code(i) for i in items)


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.:;])\s", text.strip(), maxsplit=1)[0].rstrip(".")


def default_text(raw: object) -> str:
    return "none" if raw is None else code(raw)


def kind_text(entry: dict[str, Any]) -> str:
    """How a value is written, for the Kind column: the choices of a word, else the kind's name."""
    choices = entry.get("choices")
    if choices:
        shown = " ".join(code(c) for c in choices)
        if entry.get("kind") == "list":
            return f"list of {shown}"
        return shown
    if entry.get("kind") is None:  # a token of the elevation group: a size, or a list of shadows
        return "shadows" if entry.get("block") else "number"
    kind = str(entry["kind"])
    if kind == "list" and entry.get("item_kind"):
        return f"list of {KIND_NAMES.get(str(entry['item_kind']), entry['item_kind'])}"
    return KIND_NAMES.get(kind, kind)


def required_marks(root: dict[str, Any]) -> dict[str, str]:
    """``Name`` -> ``yes`` for a key that must be written, ``one of`` for a key that is one of
    several alternatives of which one must be."""
    marks: dict[str, str] = {}
    for group in root.get("required", []):
        for key in group:
            marks[key] = "yes" if len(group) == 1 else "one of"
    return marks


def keys_table(keys: dict[str, Any], marks: dict[str, str] | None = None) -> str:
    marks = marks or {}
    rows = [
        (code(k), kind_text(v), default_text(v["default"]), marks.get(k, ""), v["doc"])
        for k, v in keys.items()
        if v.get("built", True)
    ]
    return table(["Key", "Value", "Default", "Required", "What it does"], rows)


def not_built(keys: dict[str, Any]) -> list[str]:
    return [k for k, v in keys.items() if not v.get("built", True)]


# -- the blocks of the schema ----------------------------------------------------------------------


def block_version_info(s: dict[str, Any]) -> str:
    return (
        f"This guide describes tesserae-shell {s['shell_version']} "
        f"(schema version {s['schema_version']}, the one `tesserae-shell schema --json` prints)."
    )


def has_unreleased_entries() -> bool:
    """Whether the CHANGELOG lists anything under ``Unreleased`` (not how many: every change
    adds an entry, and the guide must not go stale with each one)."""
    inside = False
    for line in (REPO / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip().lower() == "## unreleased"
        elif inside and line.startswith("- "):
            return True
    return False


def block_release_state(s: dict[str, Any]) -> str:
    version = s["shell_version"]
    if not has_unreleased_entries():
        return f"The code this guide describes is the released version, {version}."
    return (
        f"The code this guide describes is a little **ahead of the {version} release** on PyPI: "
        "the CHANGELOG lists the difference under *Unreleased*. The pages mark what was added "
        f"after {version}; a package installed from PyPI at {version} does not have it until the "
        "next release."
    )


def block_dependencies(_: dict[str, Any]) -> str:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    rows = []
    for spec in project["dependencies"]:
        match = re.match(r"^([A-Za-z0-9_.-]+)(\[[^\]]*\])?(.*)$", spec)
        assert match is not None, spec
        name, extras, version = match.group(1), match.group(2) or "", match.group(3)
        rows.append((code(name + extras), code(version.strip() or "any"), DEPENDENCY_NOTES[name]))
    return f"Python {code(project['requires-python'])} is required.\n\n" + table(
        ["Package", "Version", "What it is for"], rows
    )


def block_kinds(s: dict[str, Any]) -> str:
    forms = s["roots"]["Bar"]["style"]["Background"]["forms"]
    rows = []
    for kind in s["kinds"]:
        if kind == "block":
            continue
        help_text = KIND_HELP[kind].replace("{forms}", ", ".join(code(f) for f in forms))
        rows.append((KIND_NAMES.get(kind, kind), help_text))
    return table(["Value", "How it is written"], rows)


def block_blocks(s: dict[str, Any]) -> str:
    rows = [
        (code(name), v["doc"], names(list(v["style"])) if v["style"] else "none")
        for name, v in s["blocks"].items()
    ]
    return table(["Block", "What it is", "Style keys"], rows)


def block_style_keys(s: dict[str, Any]) -> str:
    union: dict[str, tuple[dict[str, Any], list[str]]] = {}
    for block, v in s["blocks"].items():
        for key, entry in v["style"].items():
            union.setdefault(key, (entry, []))[1].append(block)
    rows = []
    for key, (entry, blocks) in union.items():
        used = ", ".join(blocks) if len(blocks) < 6 else f"{len(blocks)} block types"
        tokens = ", ".join(entry.get("preferred_tokens") or entry.get("tokens") or [])
        rows.append((code(key), kind_text(entry), used, tokens, entry["doc"]))
    return table(["Style key", "Value", "Used by", "Theme tokens", "What it does"], rows)


def block_surface(s: dict[str, Any], root_name: str) -> str:
    root = s["roots"][root_name]
    out = [prose(root["doc"]), "", keys_table(root["keys"], required_marks(root))]
    missing = not_built(root["keys"])
    if missing:
        out += ["", f"Not built yet (the loader says so if you write them): {names(missing)}."]
    if root["style"]:
        out += ["", f"A `Style {{ }}` block of a {root_name} takes: {names(list(root['style']))}."]
    if root["events"]:
        out += ["", f"Events it raises: {names(root['events'])}."]
    kids = root["allowed_children"]
    if kids:
        shown = names(kids) if len(kids) <= 6 else "any block (see the table of blocks on page 3)"
        out += ["", f"Inside it: {shown}."]
    return "\n".join(out)


def block_events(s: dict[str, Any]) -> str:
    rows = []
    for name, event in s["events"].items():
        raised = event["raised_by"]
        if not raised:
            where = "nothing yet"
        elif len(raised) <= 4:
            where = ", ".join(raised)
        else:
            where = f"{len(raised)} block types"
        rows.append((code(name), where, event["doc"]))
    return table(["Event", "Raised by", "What it is"], rows)


def block_actions(s: dict[str, Any]) -> str:
    rows = []
    for action in s["actions"]:
        args = ", ".join(
            code(a["name"]) + (" (required)" if a["required"] else "") for a in action["args"]
        )
        rows.append((code(action["name"]), args or "none", action["doc"]))
    return table(["Action", "Arguments", "What it does"], rows)


def block_module_index(s: dict[str, Any]) -> str:
    rows = [
        (f"[{name}](#{name.lower()})", first_sentence(m["doc"])) for name, m in s["modules"].items()
    ]
    return table(["Module", "What it is"], rows)


def block_module_common_keys(s: dict[str, Any]) -> str:
    keys = {tuple(m["common_keys"]) for m in s["modules"].values()}
    assert len(keys) == 1, "the modules no longer share one list of common keys"
    return names(list(keys.pop()))


def block_module(s: dict[str, Any], name: str) -> str:
    module = s["modules"][name]
    out = [prose(module["doc"]), ""]
    params = module["params"]
    if params:
        rows = [
            (code(p), v["type"], default_text(v["default"]), v["doc"]) for p, v in params.items()
        ]
        out.append(table(["Param", "Type", "Default", "What it does"], rows))
    else:
        out.append("This module has no params of its own.")
    out += ["", f"Events a use may handle: {names(module['events'])}."]
    if module["actions"]:
        action_rows = []
        for action in module["actions"]:
            args = ", ".join(a["name"] + ("" if a["required"] else "?") for a in action["args"])
            action_rows.append((code(f"{name}.{action['name']}({args})"), action["doc"]))
        out += ["", "Actions a `Call` may run:", "", table(["Action", "What it does"], action_rows)]
    return "\n".join(out)


def block_shipped_panels(s: dict[str, Any]) -> str:
    rows = [
        (
            code(n),
            p["content"],
            p["layer"],
            p["keyboard"],
            "yes" if p["visible"] else "no",
            p["doc"],
        )
        for n, p in s["panels"]["panels"].items()
    ]
    return (
        f"The shell adds them to the main shell's first Monitor when {s['panels']['when']}.\n\n"
        + table(["Panel", "Holds", "Layer", "Keyboard", "Shown at start", "What it is"], rows)
    )


def block_shipped_popups(s: dict[str, Any]) -> str:
    rows = []
    for n, p in s["popups"]["popups"].items():
        height = p["max_height"]
        rows.append(
            (
                code(n),
                p["shown_by"],
                p["content"],
                f"{height['value']:g} {height['unit']}",
                p["doc"],
            )
        )
    return f"Added to {s['popups']['monitors']}.\n\n" + table(
        ["Popup", "Used by", "Holds", "Max height", "What it is"], rows
    )


def block_tokens(s: dict[str, Any]) -> str:
    out: list[str] = []
    headers = ["Token", "Value", "Default", "The built-in modes change it in", "What it is"]
    for group, tokens in s["tokens"].items():
        rows = []
        for token in tokens.values():
            changed = ", ".join(MODE_NAMES.get(str(m), str(m)) for m in token["modes"]) or "never"
            rows.append(
                (
                    code(token["ref"]),
                    kind_text(token),
                    default_text(token["default"]),
                    changed,
                    token["doc"],
                )
            )
        out += [f"### {group.capitalize()}", "", table(headers, rows), ""]
    return "\n".join(out).rstrip()


def block_system_tokens(s: dict[str, Any]) -> str:
    rows = [
        (code(t["ref"]), kind_text(t), default_text(t["default"]), t["doc"])
        for t in s["system_tokens"]
    ]
    return table(["Token", "Value", "Default", "What it is"], rows)


def block_settings(s: dict[str, Any], section: str) -> str:
    rows = [
        (code(k), kind_text(v), default_text(v["default"]), v["doc"])
        for k, v in s["settings"][section].items()
        if v.get("built", True)
    ]
    return table(["Key", "Value", "Default", "What it does"], rows)


def block_shortcut_forms(s: dict[str, Any]) -> str:
    shortcuts = s["shortcuts"]
    rows = [(code(f["form"]), f["doc"]) for f in shortcuts["forms"]]
    out = [table(["Entry in `Shortcuts { }`", "What it does"], rows), ""]
    out.append(f"The five fixed actions are {names(shortcuts['fixed'])}.")
    out.append("")
    surface_rows = [
        (code(surface), code(v["key"]), f"the same as {code(v['same_as'])}")
        for surface, v in shortcuts["surface_keys"].items()
    ]
    out.append(table(["Surface", "Key", "Meaning"], surface_rows))
    out += ["", prose(shortcuts["doc"])]
    return "\n".join(out)


def block_key_names(s: dict[str, Any]) -> str:
    chord = s["kinds"]["key_chord"]
    rows = [(group.capitalize(), names(keys)) for group, keys in chord["groups"].items()]
    out = [
        f"A key is the modifiers {names(chord['modifiers'])} and one key, joined by "
        f"{code(chord['separator'])}, for example {code('Ctrl+Shift+F1')}. "
        "Case and order do not matter. These are the key names:",
        "",
        table(["Group", "Names"], rows),
        "",
    ]
    aliases: dict[str, str] = chord["aliases"]
    hardware = chord["groups"]["hardware"]
    x_names = {a: k for a, k in aliases.items() if a.startswith("XF86")}
    plain = {a: k for a, k in aliases.items() if not a.startswith("XF86")}
    out.append("Other spellings that are read:")
    out.append("")
    out.append(table(["Written", "Read as"], [(code(a), code(k)) for a, k in plain.items()]))
    out.append("")
    if set(x_names.values()) == set(hardware) and all(a == "XF86" + k for a, k in x_names.items()):
        out.append(
            "Every key of the hardware group may also be written with the `XF86` prefix of its X "
            "name."
        )
    else:
        out.append(table(["Written", "Read as"], [(code(a), code(k)) for a, k in x_names.items()]))
    return "\n".join(out)


# -- the command line ----------------------------------------------------------------------------

GLOBAL_DESTS = {"config_dir", "json", "quiet", "timeout"}


@contextlib.contextmanager
def fixed_width() -> Iterator[None]:
    """argparse wraps its help at the width of the terminal: make it 80 so the text is the same
    wherever it is generated."""
    old = os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = "80"
    try:
        yield
    finally:
        if old is None:
            del os.environ["COLUMNS"]
        else:
            os.environ["COLUMNS"] = old


def sub_parsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def option_text(action: argparse.Action) -> str:
    flags = "/".join(action.option_strings)
    if action.nargs == 0:
        return code(flags)
    metavar = action.metavar or action.dest.upper()
    return code(f"{flags} {metavar}")


def own_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [
        a
        for a in parser._actions
        if not isinstance(a, argparse._HelpAction | argparse._SubParsersAction)
        and a.dest not in GLOBAL_DESTS
    ]


def walk_commands(
    parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], argparse.ArgumentParser, str]]:
    """Every command, nested ones too, as ``(words, parser, help line)``."""
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        helps = {c.dest: (c.help or "") for c in action._choices_actions}
        for name, child in action.choices.items():
            words = (*prefix, name)
            yield words, child, helps.get(name, "")
            yield from walk_commands(child, words)


def block_cli_global_options(_: dict[str, Any]) -> str:
    parser = _build_parser()
    rows = [
        (option_text(a), a.help or "")
        for a in parser._actions
        if a.dest in GLOBAL_DESTS and a.option_strings
    ]
    return table(["Option", "What it does"], rows)


def block_cli_commands(_: dict[str, Any]) -> str:
    parser = _build_parser()
    rows = []
    for words, child, help_line in walk_commands(parser):
        subs = sub_parsers(child)
        if subs:  # a group of commands: its own rows follow
            rows.append((code("tesserae-shell " + " ".join(words)), "a group", help_line))
            continue
        args: list[str] = []
        for action in own_actions(child):
            if action.option_strings:
                args.append(option_text(action))
            else:
                metavar = action.metavar or action.dest
                args.append(code(f"[{metavar} ...]" if action.nargs == "*" else str(metavar)))
        rows.append(
            (code("tesserae-shell " + " ".join(words)), " ".join(args) or "none", help_line)
        )
    return table(["Command", "Its own arguments and options", "What it does"], rows)


def block_cli_help(_: dict[str, Any]) -> str:
    with fixed_width():
        parser = _build_parser()
        parser.color = False
        text: str = parser.format_help()
    return "```text\n" + text.rstrip("\n") + "\n```"


def block_cli_command_help(_: dict[str, Any]) -> str:
    out: list[str] = []
    with fixed_width():
        parser = _build_parser()
        for words, child, _help in walk_commands(parser):
            child.color = False
            out += [
                f"#### tesserae-shell {' '.join(words)} --help",
                "",
                "```text",
                child.format_help().rstrip("\n"),
                "```",
                "",
            ]
    return "\n".join(out).rstrip()


def block_exit_codes(_: dict[str, Any]) -> str:
    rows = [(str(int(c)), code(c.name), EXIT_NOTES[c.name]) for c in ExitCode]
    return table(["Code", "Name", "Meaning"], rows)


# -- the examples ---------------------------------------------------------------------------------


def example_sets() -> list[Path]:
    """Every example set: a folder two levels under ``guide/examples/`` that is a configuration
    folder."""
    return sorted(
        p for page in EXAMPLES.iterdir() if page.is_dir() for p in page.iterdir() if p.is_dir()
    )


def set_files(folder: Path) -> list[Path]:
    """The text files of a set, in the order a person makes them: settings first, then the
    folders in the order of the configuration folder."""
    order = ["settings.tdl", "Shells", "Modules", "Themes", "Stylesheets", "Styles", "Icons"]

    def rank(path: Path) -> tuple[int, str]:
        relative = path.relative_to(folder).as_posix()
        first = relative.split("/", 1)[0]
        return (order.index(first) if first in order else len(order), relative)

    files = [
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix in TEXT_SUFFIXES and "__pycache__" not in p.parts
    ]
    return sorted(files, key=rank)


def assets(folder: Path) -> list[Path]:
    """The files of an example folder that the page does not print (not its bytecode: running the
    examples makes ``__pycache__``, and a page must not depend on whether that happened first)."""
    return sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix not in TEXT_SUFFIXES and "__pycache__" not in p.parts
    )


def block_example_set(_: dict[str, Any], name: str) -> str:
    folder = EXAMPLES / name
    if not folder.is_dir():
        raise KeyError(f"no example set {name} under guide/examples")
    out: list[str] = []
    for path in set_files(folder):
        relative = path.relative_to(folder).as_posix()
        text = path.read_text(encoding="utf-8")
        language = LANGUAGE[path.suffix]
        out += [f"File {code(relative)}:", "", f"```{language}", text.rstrip("\n"), "```", ""]
    extra = assets(folder)
    if extra:
        listed = names([p.relative_to(folder).as_posix() for p in extra])
        out.append(f"The folder also holds {listed}, which are not shown.")
        out.append("")
    return "\n".join(out).rstrip()


# -- the dispatch ---------------------------------------------------------------------------------

Renderer = Callable[[dict[str, Any]], str]

FIXED: dict[str, Renderer] = {
    "version-info": block_version_info,
    "release-state": block_release_state,
    "dependencies": block_dependencies,
    "kinds": block_kinds,
    "blocks": block_blocks,
    "style-keys": block_style_keys,
    "events": block_events,
    "actions": block_actions,
    "module-index": block_module_index,
    "module-common-keys": block_module_common_keys,
    "shipped-panels": block_shipped_panels,
    "shipped-popups": block_shipped_popups,
    "tokens": block_tokens,
    "system-tokens": block_system_tokens,
    "shortcut-forms": block_shortcut_forms,
    "key-names": block_key_names,
    "cli-global-options": block_cli_global_options,
    "cli-commands": block_cli_commands,
    "cli-help": block_cli_help,
    "cli-command-help": block_cli_command_help,
    "exit-codes": block_exit_codes,
}

PARAMETRIC: dict[str, Callable[[dict[str, Any], str], str]] = {
    "surface": block_surface,
    "module": block_module,
    "settings": block_settings,
    "example-set": block_example_set,
}


def render(name: str, schema: dict[str, Any]) -> str:
    """The text between the markers called ``name``."""
    if name in FIXED:
        body = FIXED[name](schema)
    else:
        head, _, argument = name.partition(":")
        if head not in PARAMETRIC or not argument:
            raise KeyError(f"no generated block called {name}")
        body = PARAMETRIC[head](schema, argument)
    return f"\n{body}\n\n"


def regenerate(text: str, schema: dict[str, Any] | None = None) -> str:
    """``text`` of a page with every generated part written again."""
    data = schema_dict() if schema is None else schema

    def fill(match: re.Match[str]) -> str:
        name = match.group("name")
        return f"<!-- BEGIN generated: {name} -->{render(name, data)}<!-- END generated: {name} -->"

    return MARKER.sub(fill, text)


def markers(text: str) -> list[str]:
    """The names of the marker pairs of a page, in order."""
    return [m.group("name") for m in MARKER.finditer(text)]


def stray_markers(text: str) -> list[str]:
    """A BEGIN or END comment that is not part of a well-formed pair."""
    stripped = MARKER.sub("", text)
    return re.findall(r"<!-- (?:BEGIN|END) generated: [^>]+ -->", stripped)


def pages() -> list[Path]:
    return sorted(GUIDE.glob("*.md"))


def required_markers(schema: dict[str, Any]) -> dict[str, list[str]]:
    """The markers each page must hold, by page file name: the guide keeps a table for everything
    the schema lists, so a module or a settings section added to the code must be added to the
    guide too."""
    return {
        "README.md": ["version-info", "release-state"],
        "01-install.md": ["version-info", "release-state", "dependencies"],
        "03-first-bar.md": ["blocks"],
        "04-surfaces.md": [
            "kinds",
            *(f"surface:{r}" for r in SURFACE_ROOTS),
            "actions",
            "events",
            "shipped-panels",
            "shipped-popups",
        ],
        "05-modules.md": [
            "module-index",
            "module-common-keys",
            *(f"module:{m}" for m in schema["modules"]),
        ],
        "06-styling.md": ["tokens", "system-tokens", "style-keys"],
        "07-settings.md": [f"settings:{s}" for s in SETTINGS_SECTIONS],
        "08-keyboard.md": ["shortcut-forms", "key-names"],
        "09-command-line.md": [
            "cli-global-options",
            "cli-commands",
            "cli-help",
            "cli-command-help",
            "exit-codes",
        ],
    }


def write_pages(check: bool = False) -> list[Path]:
    """Write every page; with ``check`` write nothing. The pages that were or are out of date."""
    schema = schema_dict()
    changed: list[Path] = []
    for page in pages():
        old = page.read_text(encoding="utf-8")
        new = regenerate(old, schema)
        if new != old:
            changed.append(page)
            if not check:
                page.write_text(new, encoding="utf-8")
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the generated parts of the user guide.")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if out of date")
    args = parser.parse_args(argv)
    changed = write_pages(check=args.check)
    for page in changed:
        print(("out of date: " if args.check else "written: ") + str(page.relative_to(REPO)))
    if not changed:
        print("the guide is up to date")
    return 1 if (changed and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
