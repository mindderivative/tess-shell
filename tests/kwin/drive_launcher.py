"""The drivers of the launcher kit (copied into ``/tmp/tess-kwin-launcher`` as ``drive_launcher.py`` by
``prepare_launcher.py``; not collected by pytest). ``python drive_launcher.py panel|key`` runs in the
step's PRIVATE KWin: the shell's Launcher Panel is opened, searched and used by KEY EVENTS sent
through KWin's own fake input (the same pipeline a keyboard feeds), and the applications it starts
are the kit's made-up ones (a marker script that writes a line and sleeps, and a tre window).

* ``panel``: ``tesserae-shell toggle Launcher`` opens it; the field has the keyboard at once with no
  click (the spec's question 2, answered by what the module hears); search, selection, Escape,
  Enter on a script, on an application that opens a window (which KWin makes the active one), on a
  missing program (the Panel stays and says so), a click outside (it does not hide the Panel), and
  the started marker outliving the shell.
* ``key``: the same from a global key registered with the private ``kglobalaccel`` of KWin.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import kitdrive as d

ENV = dict(os.environ)
KIT = Path(ENV["KIT"])
STEP_DIR = Path(ENV["STEP_DIR"])
SANDBOX = Path(ENV["SANDBOX"])
BIN = ENV["BIN"]
TRE_PY = ENV["TRE_PY"]
KWIN = "org.kde.KWin"
SCRIPTING = "org.kde.kwin.Scripting"
CTRL, ALT, SHIFT, F9 = 0x04000000, 0x08000000, 0x02000000, 0x01000038


def share_without_applications() -> Path:
    """Links to everything the real ``XDG_DATA_DIRS`` hold except their ``applications`` folders: the
    graphics stack finds its drivers there, but the launcher must read no real desktop entry."""
    share = STEP_DIR / "share"
    share.mkdir(exist_ok=True)
    real = ENV.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    for directory in (Path(p) for p in real.split(":") if p):
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            link = share / entry.name
            if entry.name != "applications" and not link.exists() and not link.is_symlink():
                link.symlink_to(entry)
    return share


def start(config: str) -> d.ShellRun:
    env = {
        "XDG_DATA_DIRS": f"{KIT / 'data'}:{share_without_applications()}",
        "XDG_STATE_HOME": str(SANDBOX / "state"),
    }
    run = d.ShellRun(BIN, KIT / config, ENV, log=STEP_DIR / f"{config}.log", extra_env=env)
    run.wait_for(r"\| running")
    run.wait_for(r"Panel Launcher on \S+ configured|Launcher .*hidden", timeout=30)
    return run


def wait(run: d.ShellRun, pattern: str, after: int = 0, timeout: float = 20) -> bool:
    try:
        run.wait_for(pattern, timeout=timeout, after=after)
        return True
    except d.Timeout:
        return False


def count(run: d.ShellRun, pattern: str) -> int:
    return len(run.grep(pattern))


def open_panel(run: d.ShellRun, keys: d.Input | None = None, key_chord: bool = False) -> bool:
    mark = run.mark()
    if key_chord and keys is not None:
        keys.chord("Ctrl", "Alt", "Shift", "F9")
    else:
        d.cli(BIN, ENV, "toggle", "Launcher")
    return wait(run, r"Panel Launcher on \S+ shown", mark)


def type_and_see(run: d.ShellRun, keys: d.Input, text: str, results: int | None = None) -> bool:
    """Type ``text``; the module says what it searched. ``results``: how many it found."""
    mark = run.mark()
    keys.type(text)
    pattern = rf"search {re.escape(repr(text))}: " + (
        rf"{results} results" if results is not None else r"\d+ results"
    )
    return wait(run, pattern, mark)


def press_until_heard(run: d.ShellRun, keys: d.Input, tries: int = 30) -> bool:
    """The compositor hands an exclusive layer surface the keyboard some milliseconds after it shows:
    send Down until the module has heard one (the observable, not a sleep)."""
    for _ in range(tries):
        before = count(run, r"\| key arrow_down")
        keys.key("Down")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if count(run, r"\| key arrow_down") > before:
                return True
            time.sleep(0.05)
    return False


def active_window() -> str:
    """The caption of KWin's active window, read by a one-shot script that prints to KWin's log."""
    path = STEP_DIR / "active.js"
    path.write_text(
        "var w = workspace.activeWindow;\n"
        'print("KITACTIVE " + (w ? w.caption : "-") + "|" + (w ? w.resourceName : "-"));\n'
    )
    log = SANDBOX / "kwin.log"
    before = log.stat().st_size
    d.gdbus(ENV, KWIN, "/Scripting", f"{SCRIPTING}.loadScript", str(path), "kit-active")
    d.gdbus(ENV, KWIN, "/Scripting", f"{SCRIPTING}.start")
    deadline = time.monotonic() + 15
    text = ""
    while time.monotonic() < deadline and "KITACTIVE" not in text:
        with open(log, errors="replace") as handle:
            handle.seek(before)
            text = handle.read()
        time.sleep(0.1)
    d.gdbus(ENV, KWIN, "/Scripting", f"{SCRIPTING}.unloadScript", "kit-active")
    found = re.search(r"KITACTIVE (.*)", text)
    return found.group(1).split("|")[0] if found else "?"


def marker_lines() -> list[str]:
    path = KIT / "marker.txt"
    return path.read_text().splitlines() if path.exists() else []


def panel() -> int:
    report = d.Report()
    (KIT / "marker.txt").unlink(missing_ok=True)
    run = start("cfg")
    keys = d.Input(TRE_PY, ENV)
    try:
        report.check(
            "1 `tesserae-shell toggle Launcher` opens the Panel", open_panel(run), run.tail()
        )
        report.check(
            "2 the keys reach the Panel with no click first (KWin hands it the keyboard)",
            press_until_heard(run, keys),
            run.tail(),
        )
        report.note("spec question 2: on KWin the Panel got the keyboard with no click")
        report.check(
            "3 typing 'mark' finds the two listed marker entries (the NoDisplay one is not there)",
            type_and_see(run, keys, "mark", 2),
            run.tail(),
        )
        report.check(
            "4 Down and Up move the marking",
            _moves(run, keys),
            run.tail(),
        )
        mark = run.mark()
        keys.key("Escape")
        report.check(
            "5 Escape with text clears the field and keeps the Panel",
            wait(run, r"escape: the field is cleared", mark)
            and not run.grep(r"Panel Launcher on \S+ hidden", mark),
            run.tail(),
        )
        mark = run.mark()
        keys.key("Escape")
        report.check(
            "6 Escape again hides it",
            wait(run, r"escape: the panel hides", mark)
            and wait(run, r"Panel Launcher on \S+ hidden", mark),
            run.tail(),
        )
        open_panel(run)
        press_until_heard(run, keys)
        report.check("7 'zzz' finds nothing", type_and_see(run, keys, "zzz", 0), run.tail())
        keys.key("Escape")
        keys.key("Escape")
        # Enter on the marker script
        open_panel(run)
        press_until_heard(run, keys)
        type_and_see(run, keys, "tesserae marker", None)
        mark = run.mark()
        keys.key("Enter")
        report.check(
            "8 Enter starts the marker and the Panel hides at once",
            wait(run, r"Panel Launcher on \S+ hidden", mark),
            run.tail(),
        )
        deadline = time.monotonic() + 15
        while not marker_lines() and time.monotonic() < deadline:
            time.sleep(0.1)
        line = marker_lines()[0] if marker_lines() else ""
        report.check(
            "9 marker.txt has its line: the entry's working folder",
            f"cwd={KIT}/work" in line,
            line or "no marker.txt",
            detail=line,
        )
        report.check(
            "10 the activation token reached the started program",
            "token=set" in line,
            f"{line}; the log: {run.grep('activation token')}",
            detail=(run.grep("activation token") or ["no log line"])[-1][-60:],
        )
        pid_match = re.search(r"pid=(\d+) ppid=(\d+)", line)
        # a missing program: the Panel stays and says so
        open_panel(run)
        press_until_heard(run, keys)
        type_and_see(run, keys, "missing", None)
        mark = run.mark()
        keys.key("Enter")
        warned = wait(run, r"\| WARNING .*could not start Tesserae Missing Program", mark)
        time.sleep(0.5)  # the Panel must NOT hide: nothing to wait for
        report.check(
            "11 a missing program: one warning naming the entry, and the Panel stays open",
            warned
            and len(run.grep(r"\| WARNING .*could not start", mark)) == 1
            and not run.grep(r"Panel Launcher on \S+ hidden", mark),
            run.tail(),
        )
        # a click outside the Panel does not hide it (exclusive keyboard)
        mark = run.mark()
        keys.click(40, 650)
        time.sleep(1.0)  # a negative again
        report.check(
            "12 a click outside the Panel does not hide it",
            not run.grep(r"Panel Launcher on \S+ hidden", mark),
            run.tail(),
        )
        report.note("design gap 1: a click outside does not hide the Panel (as the spec expects)")
        keys.key("Escape")
        keys.key("Escape")
        # terminal entries: never started here if a terminal launcher exists
        if shutil.which("xdg-terminal-exec", path=ENV.get("PATH")):
            report.note("xdg-terminal-exec is installed here: the terminal entry is not started")
        else:
            open_panel(run)
            press_until_heard(run, keys)
            type_and_see(run, keys, "terminal", None)
            mark = run.mark()
            keys.key("Enter")
            report.check(
                "13 a terminal entry with no xdg-terminal-exec: a warning naming it",
                wait(run, r"\| WARNING .*xdg-terminal-exec", mark),
                run.tail(),
            )
            keys.key("Escape")
            keys.key("Escape")
        # an application with a window: KWin makes the started window the active one
        open_panel(run)
        press_until_heard(run, keys)
        type_and_see(run, keys, "launched", None)
        mark = run.mark()
        keys.key("Enter")
        wait(run, r"Panel Launcher on \S+ hidden", mark)
        deadline = time.monotonic() + 20
        caption = "?"
        while time.monotonic() < deadline:
            caption = active_window()
            if caption == "Launched Window":
                break
            time.sleep(0.3)
        report.check(
            "14 the started application's window opens and is the active one",
            caption == "Launched Window",
            f"the active window is {caption!r}",
        )
        report.note(
            "spec question 1 on KWin (virtual): the started window "
            + ("took the focus" if caption == "Launched Window" else "did not take the focus")
        )
        report.check(
            "15 the log says whether the Panel gave a token",
            bool(run.grep(r"activation token: (received|none)")),
            run.tail(),
        )
        counts = SANDBOX / "state" / "tesserae-shell" / "launcher-counts.json"
        deadline = time.monotonic() + 10
        while not counts.exists() and time.monotonic() < deadline:
            time.sleep(0.1)  # the counts are written by a worker thread
        data = json.loads(counts.read_text()) if counts.exists() else {}
        report.check(
            "16 the start counts are in the kit's own state folder",
            any("tess-marker" in key for key in data),
            f"{counts}: {data}",
            detail=f"{data}",
        )
        report.check(
            "17 no ERROR in the log", not run.grep(r"\| ERROR "), "; ".join(run.grep(r"\| ERROR "))
        )
        shell_pid = run.process.pid
    finally:
        keys.close()
        code = run.stop()
    report.check("18 the shell stops with code 0", code == 0, f"exit code {code}")
    # the marker sleeps 20 s: it outlives the shell and is not its child
    alive = False
    if pid_match:
        pid, ppid = int(pid_match.group(1)), int(pid_match.group(2))
        alive = Path(f"/proc/{pid}").exists()
        report.check(
            "19 the started marker outlives the shell",
            alive,
            f"pid {pid} is gone",
        )
        report.check(
            "20 and it was not the shell's child (the start is detached)",
            ppid != shell_pid,
            f"its parent was {ppid}, the shell {shell_pid}",
        )
    # what the kit started is the kit's to remove: the marker (sleeping 20 s) and the window
    d.kill_started(str(KIT / "bin" / "marker"), str(KIT / "window_probe.py"))
    return int(report.code)


def _moves(run: d.ShellRun, keys: d.Input) -> bool:
    mark = run.mark()
    keys.key("Down")
    if not wait(run, r"selected ", mark):
        return False
    first = run.grep(r"selected ", mark)[-1]
    mark = run.mark()
    keys.key("Up")
    return wait(run, r"selected ", mark) and run.grep(r"selected ", mark)[-1] != first


def key() -> int:
    report = d.Report()
    run = start("cfg-key")
    keys = d.Input(TRE_PY, ENV)
    try:
        report.check(
            "1 the log shows 1 of 1 actions registered with the private kglobalaccel",
            wait(run, r"shortcuts: 1 of 1 actions registered"),
            run.tail(),
        )
        report.check(
            "2 the key opens the Panel with no shell surface focused",
            open_panel(run, keys, key_chord=True),
            run.tail(),
        )
        report.check(
            "3 and the field has the keyboard at once, from a key",
            press_until_heard(run, keys),
            run.tail(),
        )
        report.check("4 typing searches", type_and_see(run, keys, "mark", 2), run.tail())
        mark = run.mark()
        keys.chord("Ctrl", "Alt", "Shift", "F9")
        report.check(
            "5 the key again closes it",
            wait(run, r"Panel Launcher on \S+ hidden", mark),
            run.tail(),
        )
        open_panel(run, keys, key_chord=True)
        press_until_heard(run, keys)
        mark = run.mark()
        keys.key("Escape")
        keys.key("Escape")
        report.check(
            "6 opened from the key, Escape twice closes it",
            wait(run, r"Panel Launcher on \S+ hidden", mark),
            run.tail(),
        )
        report.check(
            "7 no ERROR in the log", not run.grep(r"\| ERROR "), "; ".join(run.grep(r"\| ERROR "))
        )
    finally:
        keys.close()
        code = run.stop()
    report.check("8 the shell stops with code 0", code == 0, f"exit code {code}")
    return int(report.code)


if __name__ == "__main__":
    which = sys.argv[1]
    raise SystemExit({"panel": panel, "key": key}[which]())
