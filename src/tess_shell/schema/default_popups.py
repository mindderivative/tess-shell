"""The Popups the shell provides (Tray Module, Audio Module): a module that opens a menu through
``ctx.popup`` needs a Popup of a given name, and a user who writes none gets this one.

A Monitor that shows the module (``Tray``, ``Audio``) and does not write a Popup of that name gets
the shipped one for the same outputs; a Popup of the same name in the user's file overrides it
entirely (the shipped one is not merged with it). The definitions are ordinary shell-file text,
typed by the same reader as the user's file, so they are also what a user copies to change one.
"""

from __future__ import annotations

from collections.abc import Mapping

import tess_dl

from tess_shell.schema.model import ModuleDef, PopupDef
from tess_shell.schema.shell import read_shell

_LOOK = "Style { Background: $color.surface_raised, Corner_Radius: 8 }"
# the module that shows the menu -> the Popups it opens, as shell-file text
POPUPS: dict[str, tuple[tuple[str, str], ...]] = {
    "Tray": tuple(
        (
            name,
            f"Popup {{ Name: {name}, {head}Max_Height: 60%, {_LOOK}, "
            f"Children {{ Tray_Menu {{ Level: {level} }} }} }}",
        )
        for level, name, head in (
            (1, "Tray_Menu", "Attach: BOTTOM, Gap: 4, "),
            (2, "Tray_Menu_2", ""),
            (3, "Tray_Menu_3", ""),
        )
    ),
    "Audio": (
        (
            "Audio_Outputs",
            f"Popup {{ Name: Audio_Outputs, Attach: BOTTOM, Gap: 4, {_LOOK}, "
            "Children { Audio_Outputs { } } }",
        ),
    ),
}
SHIPPED_POPUP_MODULES = frozenset(POPUPS)  # the modules that bring shipped Popups with them
HEADER = "---\nTDL: 0.1\nShell: 0.1\nName: Default_Popups\n---\n"


def default_popups(
    modules: Mapping[str, ModuleDef],
) -> tuple[dict[str, tuple[PopupDef, ...]], list[str]]:
    """The shipped Popups by the module that needs them (``Tray``, ``Audio``), typed against the
    module definitions the shell has, and the problems of any that did not read (skipped: it is
    the shell's own text, so that is a bug of the shell, never of the user's file)."""
    out: dict[str, tuple[PopupDef, ...]] = {}
    problems: list[str] = []
    for module, definitions in POPUPS.items():
        if module not in modules:
            continue
        body = " ".join(text for _, text in definitions)
        text = HEADER + f"Shell {{ Monitor {{ Name: Shipped, Index: 0, Children {{ {body} }} }} }}"
        parsed = tess_dl.parse(text, path=f"<shipped Popups of {module}>")
        shell = None
        if parsed.document is not None:
            shell, findings = read_shell(
                parsed.document, f"<shipped Popups of {module}>", _no_files, modules
            )
            if shell is None:
                errors = "; ".join(f.message for f in findings if f.severity == "error")
                problems.append(f"the shipped Popups of {module} did not read: {errors}")
        else:
            problems.append(f"the shipped Popups of {module} did not parse")
        if shell is not None:
            out[module] = shell.monitors[0].popups
    return out, problems


def _no_files(path: str) -> str:
    raise OSError(f"{path}: the shipped Popups read no files")
