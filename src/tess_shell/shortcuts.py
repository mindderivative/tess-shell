"""The actions the shell declares as global shortcuts, and the warnings found while they are
collected (Global Shortcuts > Action Names and Forms, Failure Modes).

The sources are the ``Shortcuts { }`` block of ``settings.tdl`` and the keys the surfaces declare
(a Panel's ``Shortcut``, a Bar's ``Reveal_Key``). They are put together when the shell files are
known (``scanner.scan``), so a name that matches no surface and two actions that share a key are
found at load, before anything is registered, and ``tesserae-shell check`` reports them:

* ``Toggle_<Name>``, ``Show_<Name>``, ``Hide_<Name>`` name a Panel, Bar or Frame; a name that
  matches none is a warning naming the nearest, and the action is not declared.
* A surface's own key and a ``Shortcuts`` entry for the same action: the entry wins, with one
  warning.
* Two actions with the same key (after normalisation: any case, order or alias): one warning naming
  both with ``file:line:column``; the shell starts, and neither gets the key (it stays declared
  with no key, so the user can pick one in System Settings).

The id of an action is the entry's own name; a key declared on a surface has the id of the equal
entry (``Toggle_Launcher``, ``Show_Top_Bar``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tess_shell.binder import model as m
from tess_shell.config.settings import SETTINGS_FILE, ShortcutEntry
from tess_shell.schema.findings import Finding, nearest
from tess_shell.schema.keys import Chord, parse_chord
from tess_shell.schema.model import BarDef, ModuleDef, PanelDef, ShellDef
from tess_shell.schema.shell import read_shortcut_handler
from tess_shell.services.shortcuts import Action, friendly_text

VERBS = {"toggle": "Toggle", "show": "Show", "hide": "Hide"}


@dataclass(frozen=True, slots=True)
class _Declared:
    action: Action
    chord: Chord
    file: str
    line: int
    column: int
    surface_key: bool  # declared on a surface, not in ``Shortcuts``

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


def _surfaces(shell: ShellDef | None) -> tuple[dict[str, str], set[str], list[BarDef | PanelDef]]:
    """The Names a ``Toggle_<Name>`` may use (Bars, Panels, Frames, melded Panels) with their kind,
    the Popup names (no key opens a Popup), and the Bars and Panels (for their own keys)."""
    kinds: dict[str, str] = {}
    popups: set[str] = set()
    keyed: list[BarDef | PanelDef] = []
    for monitor in shell.monitors if shell is not None else ():
        for surface in monitor.surfaces:
            kinds[surface.name] = "bar" if isinstance(surface, BarDef) else "panel"
            keyed.append(surface)
        for frame in monitor.frames:
            kinds[frame.name] = "frame"
            for meld in frame.melds:
                kinds[meld.name] = "panel"
                keyed.append(meld)
        popups.update(p.name for p in monitor.popups if p.name)
    return kinds, popups, keyed


def _warning(file: str, line: int, column: int, rule: str, message: str, hint: str = "") -> Finding:
    return Finding(file, line, column, "warning", rule, message, hint)


def build_plan(
    entries: Sequence[ShortcutEntry],
    shell: ShellDef | None,
    modules: Mapping[str, ModuleDef],
) -> tuple[tuple[Action, ...], list[Finding]]:
    """The actions to declare and the findings: the errors of a handler entry, and the warnings
    above."""
    findings: list[Finding] = []
    kinds, popups, keyed = _surfaces(shell)
    declared: dict[str, _Declared] = {}

    def own(surface: BarDef | PanelDef) -> None:
        key = surface.reveal_key if isinstance(surface, BarDef) else surface.shortcut
        if key is None:
            return
        verb = "show" if isinstance(surface, BarDef) else "toggle"
        id_ = f"{VERBS[verb]}_{surface.name}"
        o = key.origin
        where = f"{o.file}:{o.line}:{o.column}"
        action = Action(id_, friendly_text(id_), verb, surface.name, (), where=where)
        declared[id_] = _Declared(action, parse_chord(key.value), o.file, o.line, o.column, True)

    for surface in keyed:
        own(surface)

    for entry in entries:
        file, line, column = SETTINGS_FILE, entry.line, entry.column
        where = f"{file}:{line}:{column}"
        handler: m.Handler | None = None
        if entry.kind == "handler":
            assert entry.block is not None
            handler, found = read_shortcut_handler(entry.block, SETTINGS_FILE, modules)
            findings.extend(found)
            if handler is None:
                continue
        elif entry.kind in VERBS:
            target = entry.target
            if target in popups:
                findings.append(
                    _warning(
                        file,
                        line,
                        column,
                        "shortcut-popup",
                        f"{entry.name}: {target} is a Popup, and no key opens a Popup",
                        "a key opens a Panel; a Popup needs the press or click that opens it",
                    )
                )
                continue
            if target not in kinds:
                close = nearest(target, kinds)
                findings.append(
                    _warning(
                        file,
                        line,
                        column,
                        "shortcut-unknown-surface",
                        f"{entry.name}: no Panel, Bar or Frame is named {target}; the shortcut is "
                        "not registered",
                        f"did you mean {VERBS[entry.kind]}_{close[0]}?"
                        if close
                        else f"the surfaces: {', '.join(sorted(kinds)) or 'none'}",
                    )
                )
                continue
            if kinds[target] == "bar" and entry.kind != "show":
                findings.append(
                    _warning(
                        file,
                        line,
                        column,
                        "shortcut-bar",
                        f"{entry.name}: {target} is a Bar, which is always shown and cannot be "
                        "hidden; the shortcut is not registered",
                        f"write Show_{target}",
                    )
                )
                continue
        action = Action(
            entry.name,
            friendly_text(entry.name),
            entry.kind,
            entry.target if entry.kind != "handler" else "",
            (),
            handler,
            where,
        )
        before = declared.get(entry.name)
        if before is not None and before.surface_key:
            findings.append(
                _warning(
                    before.file,
                    before.line,
                    before.column,
                    "shortcut-override",
                    f"the key of {entry.name} here is replaced by the entry at {where}, which wins",
                    f"remove the key here or the entry {entry.name} in {SETTINGS_FILE}",
                )
            )
        declared[entry.name] = _Declared(action, entry.chord, file, line, column, False)

    # a key shared by two actions of the shell (one level): neither gets it
    by_chord: dict[Chord, list[_Declared]] = {}
    for item in declared.values():
        by_chord.setdefault(item.chord, []).append(item)
    withheld: set[str] = set()
    for chord, items in by_chord.items():
        if len(items) < 2:
            continue
        withheld.update(i.action.id for i in items)
        first = min(items, key=lambda i: (i.file, i.line, i.column))
        named = " and ".join(f"{i.action.id} ({i.where})" for i in items)
        findings.append(
            _warning(
                first.file,
                first.line,
                first.column,
                "shortcut-conflict",
                f"{named} share the key {chord.text}: neither gets it",
                "give one of them another key",
            )
        )
    actions: list[Action] = []
    for id_, item in declared.items():
        keys: tuple[Chord, ...] = () if id_ in withheld else (item.chord,)
        a = item.action
        actions.append(Action(a.id, a.friendly, a.kind, a.target, keys, a.handler, a.where))
    return tuple(actions), findings


def shortcut_handlers(actions: Sequence[Action]) -> list[m.Handler]:
    """The handlers of the ``handler`` entries: what ``ModuleHost.check_calls`` checks along with
    the handlers of the surfaces (the module is loaded, the action exists, the arguments fit)."""
    return [a.handler for a in actions if a.handler is not None]


def drop_failed(actions: Sequence[Action], findings: Sequence[Finding]) -> tuple[Action, ...]:
    """Without the actions whose handler a check reported as an error (the same findings are
    reported once, as for any other ``Call``): such an action would fail at every press."""
    bad = {(f.file, f.line, f.column) for f in findings if f.severity == "error"}
    kept: list[Action] = []
    for a in actions:
        h = a.handler
        if h is not None and (h.origin.file, h.origin.line, h.origin.column) in bad:
            continue
        kept.append(a)
    return tuple(kept)
