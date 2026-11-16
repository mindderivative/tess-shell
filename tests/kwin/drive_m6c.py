"""The drivers of the M6c kit (copied into ``/tmp/tess-kwin-m6c`` as ``drive_m6c.py`` by
``prepare_m6c_shortcuts.py``; not collected by pytest). ``python drive_m6c.py NAME`` runs in the
step's PRIVATE KWin, which hosts a REAL ``org.kde.kglobalaccel`` of its own (KWin 6.8 has no separate
``kglobalacceld``): the shell registers its shortcuts with it, a key chord is sent through KWin's
fake input exactly like a keyboard would send it, and the service is asked what it holds, over the
private bus, as System Settings would. Nothing reaches the real ``kglobalaccel`` or
``~/.config/kglobalshortcutsrc``.

``register`` (lines 2 to 7 of the old list), ``user-keys`` (8 to 10), ``taken`` (11),
``anycase`` (12) and ``off`` (14). Line 13, restarting the service, cannot be done: see the kit's
checklist.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import kitdrive as d
from tess_shell.schema.keys import qt_text

ENV = dict(os.environ)
KIT = Path(ENV["KIT"])
STEP_DIR = Path(ENV["STEP_DIR"])
BIN = ENV["BIN"]
TRE_PY = ENV["TRE_PY"]

SERVICE = "org.kde.kglobalaccel"
COMPONENT = "tesserae-shell"
CTRL, ALT, SHIFT = 0x04000000, 0x08000000, 0x02000000
F10, F11, F12 = 0x01000039, 0x0100003A, 0x0100003B
KEY_ONE = CTRL | ALT | SHIFT | F11
KEY_TWO = CTRL | ALT | SHIFT | F12
KEY_CHANGED = CTRL | ALT | SHIFT | F10


def action_id(name: str) -> str:
    friendly = name.replace("_", " ")
    return f"['{COMPONENT}', '{name}', 'Tesserae Shell', '{friendly}']"


def ints(text: str) -> list[list[int]]:
    """The non-empty key sequences in gdbus's text for an ``a(ai)``."""
    found = [[int(n) for n in m.split(",") if int(n)] for m in re.findall(r"\[([\d, ]+)\]", text)]
    return [chord for chord in found if chord]  # a QKeySequence is four ints, padded with zeros


def keys_of(name: str) -> list[list[int]]:
    done = d.gdbus(
        ENV, SERVICE, "/kglobalaccel", "org.kde.KGlobalAccel.shortcutKeys", action_id(name)
    )
    return ints(done.stdout)


def set_keys(name: str, *chords: int) -> None:
    value = "[" + ", ".join(f"([{c}],)" for c in chords) + "]" if chords else "@a(ai) []"
    done = d.gdbus(
        ENV,
        SERVICE,
        "/kglobalaccel",
        "org.kde.KGlobalAccel.setForeignShortcutKeys",
        action_id(name),
        value,
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr)


def components() -> str:
    return d.gdbus(ENV, SERVICE, "/kglobalaccel", "org.kde.KGlobalAccel.allComponents").stdout


def reset() -> str:
    """A fresh component, as when the maintainer removes 'Tesserae Shell' in System Settings.
    ``cleanUp`` answers false in about one run in ten while the service still counts an action of
    a shell that stopped a moment ago as present (not investigated: see the report), so the actions
    are unregistered one by one, as the settings' remove button does, and ``cleanUp`` is asked
    last. Says what it found and did."""
    if "tesserae_shell" not in components():
        return "no component to remove"
    names = re.findall(
        r"'([^']+)'",
        d.gdbus(
            ENV,
            SERVICE,
            "/component/tesserae_shell",
            "org.kde.kglobalaccel.Component.shortcutNames",
        ).stdout,
    )
    for name in names:
        d.gdbus(ENV, SERVICE, "/kglobalaccel", "org.kde.KGlobalAccel.unregister", COMPONENT, name)
    deadline = time.monotonic() + 15
    while "tesserae_shell" in components() and time.monotonic() < deadline:
        d.gdbus(ENV, SERVICE, "/component/tesserae_shell", "org.kde.kglobalaccel.Component.cleanUp")
        time.sleep(0.2)
    gone = "tesserae_shell" not in components()
    return f"unregistered {names}; the component is {'gone' if gone else 'STILL there'}"


def start(config: str) -> d.ShellRun:
    run = d.ShellRun(BIN, KIT / config, ENV, log=STEP_DIR / f"{config}.log")
    run.wait_for(r"\| running")
    return run


def surfaces() -> dict[str, str]:
    out = d.cli(BIN, ENV, "status").stdout
    return {m.group(1): m.group(2) for m in re.finditer(r"^\s+(\w+)\s+panel\s+(\w+)", out, re.M)}


def settle(shown: str, name: str, timeout: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if surfaces().get(name) == shown:
            return True
        time.sleep(0.1)
    return False


def chord(keys: d.Input, qt: int) -> None:
    names = [n for flag, n in ((CTRL, "Ctrl"), (ALT, "Alt"), (SHIFT, "Shift")) if qt & flag]
    names.append({F10: "F10", F11: "F11", F12: "F12"}[qt & 0x01FFFFFF])
    keys.chord(*names)


def register() -> int:
    report = d.Report()
    reset()
    run = start("cfg")
    keys = d.Input(TRE_PY, ENV)
    try:
        report.check(
            "1 the log shows 2 of 2 actions registered",
            _wait(run, r"shortcuts: 2 of 2 actions registered"),
            run.tail(),
        )
        report.check(
            "2 no WARNING about shortcuts", not run.grep(r"\| WARNING .*shortcuts"), run.tail()
        )
        friendly = d.gdbus(
            ENV,
            SERVICE,
            "/component/tesserae_shell",
            "org.freedesktop.DBus.Properties.Get",
            "org.kde.kglobalaccel.Component",
            "friendlyName",
        ).stdout
        report.check(
            "3 the service lists a component named 'Tesserae Shell'",
            "Tesserae Shell" in friendly,
            friendly,
            detail=friendly.strip(),
        )
        report.check(
            "4 it holds Toggle Launcher and Toggle Notes with the two keys",
            keys_of("Toggle_Launcher") == [[KEY_ONE]] and keys_of("Toggle_Notes") == [[KEY_TWO]],
            f"{keys_of('Toggle_Launcher')} {keys_of('Toggle_Notes')}",
            detail=f"{qt_text(KEY_ONE)} and {qt_text(KEY_TWO)}",
        )
        chord(keys, KEY_ONE)
        report.check(
            "5 the key opens the Launcher panel (a key chord through KWin's input)",
            settle("shown", "Launcher"),
            f"{surfaces()}",
        )
        chord(keys, KEY_ONE)
        report.check("6 the key again closes it", settle("hidden", "Launcher"), f"{surfaces()}")
        chord(keys, KEY_TWO)
        report.check("7 the second key opens Notes", settle("shown", "Notes"), f"{surfaces()}")
        chord(keys, KEY_TWO)
        report.check("8 and closes it", settle("hidden", "Notes"), f"{surfaces()}")
        done = d.cli(BIN, ENV, "toggle", "Launcher")
        report.check(
            "9 `tesserae-shell toggle Launcher` toggles the same panel",
            done.returncode == 0 and settle("shown", "Launcher"),
            f"{done.stderr} {surfaces()}",
        )
        d.cli(BIN, ENV, "toggle", "Launcher")
        report.check(
            "10 no ERROR in the log", not run.grep(r"\| ERROR "), "; ".join(run.grep(r"\| ERROR "))
        )
    finally:
        keys.close()
        run.stop()
    return int(report.code)


def user_keys() -> int:
    report = d.Report()
    reset()
    run = start("cfg")
    keys = d.Input(TRE_PY, ENV)
    try:
        _wait(run, r"shortcuts: 2 of 2 actions registered")
        set_keys("Toggle_Launcher", KEY_CHANGED)  # what System Settings does
        report.check(
            "1 the service holds the new key",
            keys_of("Toggle_Launcher") == [[KEY_CHANGED]],
            f"{keys_of('Toggle_Launcher')}",
        )
        report.check(
            "2 the shell hears of it (no restart)",
            _wait(run, r"the key of Toggle_Launcher was changed in the desktop's settings"),
            run.tail(),
        )
        chord(keys, KEY_CHANGED)
        report.check(
            "3 without a restart the new key opens the panel",
            settle("shown", "Launcher"),
            f"{surfaces()}",
        )
        chord(keys, KEY_CHANGED)
        settle("hidden", "Launcher")
        chord(keys, KEY_ONE)
        time.sleep(1.5)  # a negative: the old key must do nothing; a moment is the whole window
        report.check(
            "4 the old key no longer does", surfaces().get("Launcher") == "hidden", f"{surfaces()}"
        )
        run.stop()
        run = start("cfg")
        _wait(run, r"shortcuts: 2 of 2 actions registered")
        report.check(
            "5 started again, the key you chose is still the one (the default did not win back)",
            keys_of("Toggle_Launcher") == [[KEY_CHANGED]],
            f"{keys_of('Toggle_Launcher')}",
        )
        report.check(
            "6 and the log says why the file's key is not used",
            bool(
                run.grep(
                    r"Toggle_Launcher: the file writes Ctrl\+Alt\+Shift\+F11 but the service uses Ctrl\+Alt\+Shift\+F10"
                )
            ),
            run.tail(),
        )
        chord(keys, KEY_CHANGED)
        report.check("7 and it works", settle("shown", "Launcher"), f"{surfaces()}")
        chord(keys, KEY_CHANGED)
        settle("hidden", "Launcher")
        # clearing the key: the user's own choice, not a taken key
        set_keys("Toggle_Launcher")
        run.stop()
        run = start("cfg")
        _wait(run, r"shortcuts: 2 of 2 actions registered")
        report.check(
            "8 cleared, the row stays with no key",
            keys_of("Toggle_Launcher") == [],
            f"{keys_of('Toggle_Launcher')}",
        )
        report.check(
            "9 and the log has no warning about Toggle_Launcher",
            not run.grep(r"\| WARNING .*Toggle_Launcher"),
            "; ".join(run.grep(r"\| WARNING ")),
        )
        # stopping: the keys stay in the service and press nothing
        run.stop()
        chord(keys, KEY_TWO)
        time.sleep(1.0)
        report.check(
            "10 with the shell stopped the rows keep their keys",
            keys_of("Toggle_Notes") == [[KEY_TWO]],
            f"{keys_of('Toggle_Notes')}",
        )
        run = start("cfg")
        _wait(run, r"shortcuts: 2 of 2 actions registered")
        chord(keys, KEY_TWO)
        report.check("11 started again, the keys work", settle("shown", "Notes"), f"{surfaces()}")
    finally:
        keys.close()
        run.stop()
    return int(report.code)


def taken() -> int:
    report = d.Report()
    reset()
    # a key the desktop already owns: the first one KWin's own component holds
    infos = d.gdbus(
        ENV, SERVICE, "/component/kwin", "org.kde.kglobalaccel.Component.allShortcutInfos"
    ).stdout
    owned = None
    # rows: (action, action's name, component, component's name, context, context's name, keys, defaults)
    for row in re.findall(
        r"\('([^']+)', '[^']*', 'kwin', 'KWin', '[^']*', '[^']*', \[(\d+)\], \[", infos
    ):
        owned = (row[0], int(row[1]))
        break
    if owned is None:
        report.fail("1 a key KWin's own component owns", f"none found in {infos[:300]}")
        return int(report.code)
    name, qt = owned
    text = qt_text(qt)
    report.note(f"the key {text} belongs to KWin's '{name}'")
    cfg = KIT / "cfg-taken"
    (cfg / "settings.tdl").write_text(
        (cfg / "settings.tdl.in").read_text().replace("TAKEN_KEY", text)
    )
    report.check(
        "1 the file names that key for Toggle_Launcher",
        text in (cfg / "settings.tdl").read_text(),
        text,
    )
    before = keys_of_other("kwin", name)
    run = start("cfg-taken")
    try:
        _wait(run, r"shortcuts: 2 of 2 actions registered")
        report.check(
            "2 the taken key is never sent: the DEBUG line asks for nothing and the service sets nothing",
            bool(run.grep(r"Toggle_Launcher: asked for \[\], the service set \[\]")),
            run.tail(),
        )
        warnings = run.grep(r"\| WARNING .*Toggle_Launcher")
        report.check(
            "3 exactly one warning names Toggle_Launcher and the key",
            len(warnings) == 1 and text in warnings[0] and "taken by the desktop" in warnings[0],
            f"{warnings}",
        )
        report.check(
            "4 Toggle Launcher has no key",
            keys_of("Toggle_Launcher") == [],
            f"{keys_of('Toggle_Launcher')}",
        )
        report.check(
            "5 the desktop's own shortcut keeps its key",
            keys_of_other("kwin", name) == before and before != [],
            f"{before} -> {keys_of_other('kwin', name)}",
        )
        report.check("6 the shell runs", run.process.poll() is None, run.tail())
    finally:
        code = run.stop()
    report.check("7 the shell stops with code 0", code == 0, f"exit code {code}")
    return int(report.code)


def keys_of_other(component: str, name: str) -> list[list[int]]:
    ident = f"['{component}', '{name}', '', '']"
    done = d.gdbus(ENV, SERVICE, "/kglobalaccel", "org.kde.KGlobalAccel.shortcutKeys", ident)
    return ints(done.stdout)


def anycase() -> int:
    report = d.Report()
    reset()
    run = start("cfg-anycase")
    keys = d.Input(TRE_PY, ENV)
    try:
        _wait(run, r"shortcuts: 2 of 2 actions registered")
        report.check(
            "1 the file says ctrl+ALT+shift+f11 and the service holds Ctrl+Alt+Shift+F11",
            keys_of("Toggle_Launcher") == [[KEY_ONE]],
            f"{keys_of('Toggle_Launcher')}",
        )
        chord(keys, KEY_ONE)
        report.check("2 and it works", settle("shown", "Launcher"), f"{surfaces()}")
    finally:
        keys.close()
        run.stop()
    return int(report.code)


def off() -> int:
    report = d.Report()
    report.note("reset: " + reset())
    run = start("cfg-off")
    keys = d.Input(TRE_PY, ENV)
    try:
        report.check(
            "1 one INFO line says registration is off",
            _wait(run, r"shortcuts: Global_Shortcuts is false: nothing is registered"),
            run.tail(),
        )
        report.check(
            "2 the service gains no component",
            "tesserae_shell" not in components(),
            components(),
        )
        chord(keys, KEY_ONE)
        time.sleep(1.5)  # a negative: no key may work; a moment is the whole window
        report.check("3 no key works", surfaces().get("Launcher") == "hidden", f"{surfaces()}")
    finally:
        keys.close()
        run.stop()
    return int(report.code)


def _wait(run: d.ShellRun, pattern: str, after: int = 0, timeout: float = 20) -> bool:
    try:
        run.wait_for(pattern, timeout=timeout, after=after)
        return True
    except d.Timeout:
        return False


if __name__ == "__main__":
    which = sys.argv[1]
    raise SystemExit(
        {
            "register": register,
            "user-keys": user_keys,
            "taken": taken,
            "anycase": anycase,
            "off": off,
        }[which]()
    )
