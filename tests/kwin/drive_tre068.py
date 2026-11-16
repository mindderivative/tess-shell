"""The drivers of the tre 0.6.8 kit (copied into ``/tmp/tess-kwin-tre068`` as ``drive_tre068.py`` by
``prepare_tre068.py``; not collected by pytest). ``python drive_tre068.py tab|popup|token`` runs in
the step's private KWin, starts the shell (or the token probe) there, drives it with KWin's own fake
input, reads what it logs and prints ``PASS``/``FAIL`` lines (``kitdrive.Report``).

* ``tab``: a click gives the Panel the keyboard, then Tab and Shift+Tab move the focus over the
  TextEditor, the TextInput and the Button, as the shell's own focus log says
  (TRE-REQ-018: Tab leaves a multi-line TextEditor).
* ``popup``: a Popup opened and closed in the same turn (``tesserae-shell call``), once and 20
  times, leaves no ``xdg_popup`` behind: every one the protocol trace shows created is destroyed
  (TRE-REQ-019). A control opens one and leaves it, to show the trace sees a popup that stays.
* ``token``: ``token_probe.py`` asks for an activation token on a click and starts a FAKE program
  that writes its environment to a file; the file has ``XDG_ACTIVATION_TOKEN`` exactly when the
  probe said it had a token.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import kitdrive as d  # noqa: I001

ENV = dict(os.environ)
KIT = Path(ENV["KIT"])
STEP_DIR = Path(ENV["STEP_DIR"])
BIN = ENV["BIN"]
TRE_PY = ENV["TRE_PY"]
PY = ENV["PY"]

FOCUS = re.compile(r"focus: (\w+)@\S+ '([^']*)' (\(ring\)|\(no ring\)|lost)")


def focus_events(lines: list[str]) -> list[tuple[str, str]]:
    """``(block word, state)`` of each focus line: ``ring``, ``no ring`` or ``lost``."""
    out = []
    for line in lines:
        found = FOCUS.search(line)
        if found:
            out.append((found.group(1), found.group(3).strip("()")))
    return out


def start_shell(config: str, extra_env: dict[str, str] | None = None) -> d.ShellRun:
    shell = d.ShellRun(BIN, KIT / config, ENV, log=STEP_DIR / f"{config}.log", extra_env=extra_env)
    shell.wait_for(r"\| running")
    return shell


def tab() -> int:
    report = d.Report()
    shell = start_shell("cfg-tab")
    keys = d.Input(TRE_PY, ENV)
    try:
        shell.wait_for(r"Panel Form on \S+ configured")
        # the Panel is laid out a moment after it is configured: click until the editor answers
        mark = shell.mark()
        for _ in range(20):
            keys.click(640, 130)
            try:
                shell.wait_for(r"focus: TextEditor@\S+ .*\(no ring\)", timeout=1.5, after=mark)
                break
            except d.Timeout:
                continue
        report.check(
            "1 a click puts the focus in the TextEditor",
            bool(shell.grep(r"focus: TextEditor@\S+ .*\(no ring\)", mark)),
            "no focus line for the TextEditor",
        )
        keys.type("ab")
        keys.key("Enter")
        keys.type("cd")

        def press(*names: str) -> list[tuple[str, str]]:
            at = shell.mark()
            if len(names) > 1:
                keys.chord(*names)
            else:
                keys.key(names[0])
            try:
                shell.wait_for(r"focus: \w+@\S+ .*\(ring\)", timeout=5, after=at)
            except d.Timeout:
                return []
            return focus_events(shell.since(at))

        moved = press("Tab")
        report.check(
            "2 Tab leaves the TextEditor for the TextInput, with a focus ring",
            moved == [("TextEditor", "lost"), ("TextInput", "ring")],
            f"focus events {moved}",
        )
        moved = press("Shift", "Tab")
        report.check(
            "3 Shift+Tab returns to the TextEditor",
            moved == [("TextInput", "lost"), ("TextEditor", "ring")],
            f"focus events {moved}",
        )
        press("Tab")
        moved = press("Tab")
        report.check(
            "4 Tab in the single-line TextInput moves on to the Button",
            moved == [("TextInput", "lost"), ("Button", "ring")],
            f"focus events {moved}",
        )
        moved = press("Tab")
        report.check(
            "5 Tab from the last control wraps to the first (the TextEditor)",
            moved == [("Button", "lost"), ("TextEditor", "ring")],
            f"focus events {moved}",
        )
        report.check(
            "6 no ERROR in the shell's log",
            not shell.grep(r"\| ERROR ", 0),
            "; ".join(shell.grep(r"\| ERROR ", 0)),
        )
    finally:
        keys.close()
        code = shell.stop()
    report.check("7 the shell stops with code 0", code == 0, f"exit code {code}")
    return int(report.code)


POPUP_NEW = re.compile(r"-> xdg_surface[@#]\d+\.get_popup\(new id xdg_popup[@#](\d+)")
POPUP_GONE = re.compile(r"-> xdg_popup[@#](\d+)\.destroy\(\)")


def popup_balance(lines: list[str]) -> tuple[set[str], set[str]]:
    created, destroyed = set(), set()
    for line in lines:
        if found := POPUP_NEW.search(line):
            created.add(found.group(1))
        elif found := POPUP_GONE.search(line):
            destroyed.add(found.group(1))
    return created, destroyed


def settle(shell: d.ShellRun, mark: int, timeout: float = 12) -> tuple[set[str], set[str]]:
    """The popups created and destroyed since ``mark``, once they are equal (or after
    ``timeout``): a popup closed before the compositor placed it goes away a moment later."""
    deadline = time.monotonic() + timeout
    while True:
        created, destroyed = popup_balance(shell.since(mark))
        if created <= destroyed or time.monotonic() > deadline:
            return created, destroyed
        time.sleep(0.1)


def popup() -> int:
    report = d.Report()
    shell = start_shell("cfg-popup", extra_env={"WAYLAND_DEBUG": "1"})
    try:
        shell.wait_for(r"Bar Top_Bar on \S+ configured")
        shell.wait_for(r"Probe ready")
        # control: one popup opened and left must show up in the trace as created, not destroyed
        mark = shell.mark()
        done = d.cli(BIN, ENV, "call", "Probe", "open_hold")
        report.check("1 the control call works", done.returncode == 0, done.stderr.strip())
        shell.wait_for(r"Probe: Menu opened and left open", after=mark)
        deadline = time.monotonic() + 10
        created: set[str] = set()
        destroyed: set[str] = set()
        while not created and time.monotonic() < deadline:
            created, destroyed = popup_balance(shell.since(mark))
            time.sleep(0.1)
        report.check(
            "2 control: a popup left open is created and not destroyed",
            len(created) == 1 and not (created & destroyed),
            f"created {created}, destroyed {destroyed}",
        )
        done = d.cli(BIN, ENV, "call", "Probe", "open_hold")  # a toggle: closes it again
        created, destroyed = settle(shell, mark)
        report.check(
            "3 control: closing it destroys it",
            len(created) == 1 and created <= destroyed,
            f"created {created}, destroyed {destroyed}",
        )
        for action, text in (
            ("open_close", "in one turn"),
            ("open_close_20", "20 times in one turn"),
        ):
            mark = shell.mark()
            done = d.cli(BIN, ENV, "call", "Probe", action)
            report.check(f"4 call {action}", done.returncode == 0, done.stderr.strip())
            shell.wait_for(rf"Probe: Menu opened and closed {text}", after=mark)
            created, destroyed = settle(shell, mark)
            report.check(
                f"5 {action}: every popup the trace shows created is destroyed",
                created <= destroyed,
                f"created {sorted(created)}, destroyed {sorted(destroyed)}: "
                f"{len(created - destroyed)} left",
                detail=f"{len(created)} created, {len(destroyed)} destroyed",
            )
        report.check(
            "6 no ERROR and no 'popup' warning in the shell's log",
            not shell.grep(r"\| (ERROR|WARNING) .*[Pp]opup", 0) and not shell.grep(r"\| ERROR ", 0),
            "; ".join(shell.grep(r"\| (ERROR|WARNING) ", 0))[:300],
        )
    finally:
        code = shell.stop()
    report.check("7 the shell stops with code 0", code == 0, f"exit code {code}")
    return int(report.code)


def token() -> int:
    report = d.Report()
    out = STEP_DIR / "token-env.txt"
    said = STEP_DIR / "token-probe.out"
    env = {**ENV, "TOKEN_PROGRAM": str(KIT / "fake-app"), "TOKEN_ENV_OUT": str(out)}
    with open(said, "w") as sink:
        probe = subprocess.Popen(
            [PY, str(KIT / "token_probe.py")],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=sink,
            stderr=subprocess.STDOUT,
            text=True,
        )
    keys = d.Input(TRE_PY, ENV)

    def text() -> str:
        return said.read_text(errors="replace")

    def wait_text(needle: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if needle in text():
                return True
            time.sleep(0.1)
        return False

    try:
        report.check("1 the probe is up", wait_text("click the button", 40), text())
        answered = ""
        for _ in range(15):  # the click is repeated until the probe has answered it
            keys.click(100, 24)
            if wait_text("token", 1.5) and re.search(r"started |no token", text()):
                break
        found = re.search(r"^.*(started .*|no token.*)$", text(), re.M)
        answered = found.group(1) if found else ""
        report.check("2 the click is answered with a token or None", bool(answered), text())
        started = answered.startswith("started ")
        report.note(
            "the compositor gave a token" if started else "the compositor gave NO token (None)"
        )
        if started:
            report.check(
                "3 the fake program started and wrote its environment",
                d.wait_file(out, 10),
                "no environment file",
            )
            got = d.environ_file(out).get("XDG_ACTIVATION_TOKEN", "") if out.exists() else ""
            length = re.search(r"length (\d+)", answered)
            report.check(
                "4 the started program received XDG_ACTIVATION_TOKEN",
                bool(got) and length is not None and len(got) == int(length.group(1)),
                f"token in its environment: {got!r}; the probe said {answered!r}",
                detail=f"a token of length {len(got)}",
            )
        else:
            report.check(
                "3 with no token nothing was started",
                answered.startswith("no token") and not out.exists(),
                answered,
            )
    finally:
        keys.close()
        probe.terminate()
        try:
            probe.wait(timeout=10)
        except subprocess.TimeoutExpired:
            probe.kill()
    return int(report.code)


if __name__ == "__main__":
    which = sys.argv[1]
    raise SystemExit({"tab": tab, "popup": popup, "token": token}[which]())
