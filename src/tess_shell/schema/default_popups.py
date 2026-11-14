"""The Popups the shell provides (Tray Module, Audio Module): a module that opens a menu through
``ctx.popup`` needs a Popup of a given name, and a user who writes none gets this one.

A Monitor that shows the module (``Tray``, ``Audio``) and does not write a Popup of that name gets
the shipped one for the same outputs; a Popup of the same name in the user's file overrides it
entirely (the shipped one is not merged with it). The definitions are ordinary shell-file text,
typed by the same reader as the user's file, so they are also what a user copies to change one.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import tess_dl

from tess_shell.binder import model as m
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


def describe(modules: Mapping[str, ModuleDef]) -> dict[str, dict[str, Any]]:
    """The shipped Popups as plain data for the schema export (``popups``): by Popup name, the
    module whose use on a Monitor brings it (``shown_by``), the module that is its content
    (``content``), its placement keys and its ``Max_Height`` as written. Derived from the text
    above, so the export and the shell cannot disagree."""
    found, _problems = default_popups(modules)
    out: dict[str, dict[str, Any]] = {}
    for shown_by, popups in found.items():
        for popup in popups:
            content = [c.module for c in popup.children if isinstance(c, m.UseNode)]
            height: dict[str, Any] = (
                {"value": popup.max_height_percent, "unit": "%"}
                if popup.max_height_percent is not None
                else {"value": popup.max_height, "unit": "px"}
            )
            out[popup.name] = {
                "shown_by": shown_by,
                "content": content[0] if content else "",
                "attach": popup.attach,
                "alignment": popup.alignment,
                "gap": popup.gap,
                "max_height": height,
                "doc": DOCS.get(popup.name, ""),
            }
    return out


# one line for each shipped Popup (the schema export's ``doc``)
DOCS: dict[str, str] = {
    "Tray_Menu": "The menu of a tray item: its entries, below the clicked icon.",
    "Tray_Menu_2": "The submenu of a row of Tray_Menu.",
    "Tray_Menu_3": "The submenu of a row of Tray_Menu_2.",
    "Audio_Outputs": "The list of sound outputs the Audio module's secondary click opens.",
}
MONITORS = (
    "every Monitor with a Bar, Panel or Frame that shows the module in shown_by, on each output "
    "it opens on, unless that Monitor writes a Popup of the same name (which replaces it whole)"
)
