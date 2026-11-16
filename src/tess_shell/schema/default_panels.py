"""The Panels the shell provides (Applications Module > Layout): the shipped ``Launcher``.

A user who binds a key to open the launcher (``Shortcuts { Toggle_Launcher: "Meta+Space" }``) or
writes a handler that shows it (``On_Click { Action: Toggle, Target: Launcher }``) needs a Panel of
that name that holds the ``Applications`` module. This one is provided when the main shell names it
and writes no Panel of the same name: it is added to the shell's first Monitor, which is the
Monitor a Panel written there would be on, hidden until it is shown. A shell that never names
``Launcher`` gets no extra surface at all. The definitions are ordinary shell-file text, typed by
the same reader as the user's file, so they are also what a user copies to change one; a Panel
of the same name in the user's file replaces it entirely.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import tess_dl

from tess_shell.schema.model import ModuleDef, PanelDef, ShellDef
from tess_shell.schema.shell import read_shell

# the Panel's name -> (the module it holds, its text)
PANELS: dict[str, tuple[str, str]] = {
    "Launcher": (
        "Applications",
        "Panel { Name: Launcher, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 480, Height: 400, "
        "Visible: false, Style { Background: $color.surface_raised, Corner_Radius: 12, "
        "Elevation: 20% }, Children { Applications { } } }",
    ),
}
HEADER = "---\nTDL: 0.2\nShell: 0.1\nName: Default_Panels\n---\n"
DOCS: dict[str, str] = {
    "Launcher": "The launcher: the Applications module in a hidden Panel. Open it with "
    "Toggle_Launcher in Shortcuts or a Toggle of Launcher.",
}
WHEN = (
    "added to the main shell's first Monitor when a Shortcuts entry or a handler names it and no "
    "Panel of the same name is written"
)


def shipped_panels(modules: Mapping[str, ModuleDef]) -> tuple[dict[str, PanelDef], list[str]]:
    """The shipped Panels, typed against the module definitions the shell has, and the problems of
    any that did not read (skipped: it is the shell's own text, so that is a bug of the shell)."""
    out: dict[str, PanelDef] = {}
    problems: list[str] = []
    for name, (module, body) in PANELS.items():
        if module not in modules:
            continue
        where = f"<shipped Panel {name}>"
        text = HEADER + f"Shell {{ Monitor {{ Name: Shipped, Index: 0, Children {{ {body} }} }} }}"
        parsed = tess_dl.parse(text, path=where)
        if parsed.document is None:
            problems.append(f"the shipped Panel {name} did not parse")
            continue
        shell, findings = read_shell(parsed.document, where, _no_files, modules)
        if shell is None:
            errors = "; ".join(f.message for f in findings if f.severity == "error")
            problems.append(f"the shipped Panel {name} did not read: {errors}")
            continue
        out[name] = next(s for s in shell.monitors[0].surfaces if isinstance(s, PanelDef))
    return out, problems


def _no_files(path: str) -> str:
    raise OSError(f"{path}: the shipped Panels read no files")


def _handler_targets(nodes: Iterable[Any]) -> Iterable[str]:
    """The ``Target`` of every shell action (``Show``, ``Hide``, ``Toggle``) in a tree of blocks."""
    for node in nodes:
        for handler in getattr(node, "handlers", {}).values():
            if handler.builtin and isinstance(handler.args.get("Target"), str):
                yield handler.args["Target"]
        for field in ("children", "body", "else_body"):
            yield from _handler_targets(getattr(node, field, ()) or ())


def named_surfaces(shell: ShellDef, shortcut_targets: Iterable[str] = ()) -> set[str]:
    """The Names a shell file and the ``Shortcuts`` block ask a surface for: the targets of the
    shell's own ``Show``, ``Hide`` and ``Toggle`` handlers and of the shortcut entries."""
    names = set(shortcut_targets)
    for monitor in shell.monitors:
        for surface in monitor.surfaces:
            names.update(_handler_targets(getattr(surface, "children", ())))
            names.update(_handler_targets([surface]))
        for popup in monitor.popups:
            names.update(_handler_targets(popup.children))
        for frame in monitor.frames:
            for edge in frame.edges.values():
                names.update(_handler_targets(edge.children))
            for meld in frame.melds:
                names.update(_handler_targets(meld.children))
                names.update(_handler_targets([meld]))
    return names


def written_surfaces(shell: ShellDef) -> set[str]:
    """The Names of the Bars, Panels, Frames and melded Panels the shell file writes."""
    names: set[str] = set()
    for monitor in shell.monitors:
        names.update(s.name for s in monitor.surfaces)
        for frame in monitor.frames:
            names.add(frame.name)
            names.update(m.name for m in frame.melds)
    return names


def with_shipped_panels(
    shell: ShellDef,
    modules: Mapping[str, ModuleDef],
    shortcut_targets: Sequence[str] = (),
) -> tuple[ShellDef, list[str]]:
    """``shell`` with each shipped Panel it asks for and does not write, on its first Monitor, and
    the problems of the shipped text."""
    if not shell.monitors:
        return shell, []
    asked = named_surfaces(shell, shortcut_targets) & PANELS.keys()
    asked -= written_surfaces(shell)
    if not asked:
        return shell, []
    panels, problems = shipped_panels(modules)
    added = tuple(panels[name] for name in sorted(asked) if name in panels)
    first = dataclasses.replace(shell.monitors[0], surfaces=(*shell.monitors[0].surfaces, *added))
    return dataclasses.replace(shell, monitors=(first, *shell.monitors[1:])), problems


def describe(modules: Mapping[str, ModuleDef]) -> dict[str, dict[str, Any]]:
    """The shipped Panels as plain data for the schema export (``panels``): by Panel name, the
    module it holds, the keys that matter and a line of documentation."""
    found, _problems = shipped_panels(modules)
    return {
        name: {
            "content": PANELS[name][0],
            "layer": panel.layer,
            "keyboard": panel.keyboard,
            "visible": panel.visible,
            "doc": DOCS.get(name, ""),
        }
        for name, panel in found.items()
    }
