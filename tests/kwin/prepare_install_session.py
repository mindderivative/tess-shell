"""Regenerate the install-session hand check in /tmp/tess-kwin-install-session (not collected by
pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_install_session.py``. It writes scripts
and a checklist under ``/tmp/tess-kwin-install-session`` and starts nothing, runs nothing and
touches nothing outside that folder. THE SCRIPTS IT WRITES are the only place ``install-session``
touches your REAL ``~/.config/systemd/user`` and ``~/.local/share/applications`` and your REAL
systemd user manager: every test of the suite writes to temporary folders and runs a recording fake
instead of ``systemctl`` (Orchestration Log D-019). The scripts are numbered in the safe order; the
first copies what is there, the last puts it back.

* ``1-backup.sh``: copies the two files (when they exist) and records whether the unit is enabled,
  into ``/tmp/tess-kwin-install-session/backup``. Run it FIRST; it only copies and reads.
* ``2-print.sh``: ``install-session --print`` (text and ``--json``): writes nothing.
* ``3-install.sh``: ``install-session``: writes the two files, enables nothing.
* ``4-verify.sh``: ``systemd-analyze --user verify`` and ``desktop-file-validate`` on COPIES of the
  two files (read-only).
* ``5-stale.sh``: makes the real unit's ``ExecStart`` point at a missing path, shows ``status``
  (the warning) and ``install-session`` (kept without ``--force``), then restores it with
  ``--force``.
* ``6-enable.sh``: ``install-session --enable`` (``systemctl --user enable``; it does not start the
  shell). Log out and in (or ``systemctl --user start tesserae-shell.service``) for the rest.
* ``7-after-login.sh``: read-only: state of the unit, its properties and the journal.
* ``9-undo.sh``: ``install-session --remove``, then puts back any copy that ``1-backup.sh`` made.

``TESS_SHELL_BIN`` names the command the files will start (default: the ``tesserae-shell`` beside the
interpreter that ran this generator). Set it to the installed one (``uv tool install`` puts it in
``~/.local/bin``) when that is the one you want the session to use.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/tmp/tess-kwin-install-session")
# the environment this generator runs in, so that the scripts run this code
BIN = Path(sys.executable).parent / "tesserae-shell"

APP_ID = "io.github.mindderivative.TesseraeShell"
UNIT = "tesserae-shell.service"
HEAD = f"""BIN="${{TESS_SHELL_BIN:-{BIN}}}"
UNITS="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
APPS="${{XDG_DATA_HOME:-$HOME/.local/share}}/applications"
KIT={ROOT}
"""

CHECKLIST = f"""install-session: one list, every line to run.  THIS CHECK WRITES TWO FILES IN YOUR REAL
HOME and talks to your REAL systemd user manager (it enables a unit).  Nothing in the suite does
this: it is the one hand check of the real session.  The scripts start nothing by themselves; step 6
enables the unit so that the NEXT login starts the shell, and step 9 puts everything back.

The files:   ~/.config/systemd/user/{UNIT}
             ~/.local/share/applications/{APP_ID}.desktop
(the XDG variables are honoured).  The command the files start:  {BIN}
(or the one in TESS_SHELL_BIN: export it before step 2 to use another install).  Your shell is fish:
use  set -x TESS_SHELL_BIN ~/.local/bin/tesserae-shell  and $status, not $?.

SAFETY FIRST
 0  Stop any running shell:  tesserae-shell quit
 1  /tmp/tess-kwin-install-session/1-backup.sh : copies the two files when they exist and records
    whether the unit is enabled, into /tmp/tess-kwin-install-session/backup.  To UNDO everything at
    any time:  /tmp/tess-kwin-install-session/9-undo.sh   (disables the unit if enabled, removes both
    files, puts back the copies).  It leaves ~/.config/tesserae-shell alone.

PART 1: read-only and the files
 2  2-print.sh : both files are printed with the paths above and the absolute path of the command;
    afterwards  ls ~/.config/systemd/user/{UNIT}  still says "No such file" (nothing written).
 3  3-install.sh : prints "written <path>" twice and "not enabled: ...".  Exactly those two files are
    new:  ls -l ~/.config/systemd/user/{UNIT} ~/.local/share/applications/{APP_ID}.desktop
    Run it again: "unchanged" twice (idempotent).
 4  4-verify.sh : systemd-analyze and desktop-file-validate print nothing and exit 0 (the unit passes
    `systemd-analyze --user verify`; the desktop file passes `desktop-file-validate`).
 5  5-stale.sh : (a) `tesserae-shell status` prints "warning: the unit ... starts /nonexistent/...,
    which does not exist; run `tesserae-shell install-session --force` ..." (and "no shell is
    running", exit 3, when no shell runs); with --json the object has a "warnings" list.
    (b) `install-session` without --force names the unit, changes nothing, exit 1.
    (c) with --force it is replaced; `status` no longer warns.

PART 2: the session
 6  6-enable.sh : prints "enabled tesserae-shell.service"; `systemctl --user is-enabled
    {UNIT}` says "enabled".  Nothing started.
 7  Start it without logging out:  systemctl --user start {UNIT}
    The command RETURNS only after the shell is ready (Type=notify waits for READY=1: this is the
    check that the shell sends it; if the start hangs for 90 s and fails, READY=1 never arrived:
    keep `journalctl --user -u tesserae-shell` for the code session).  Then  7-after-login.sh :
    "Active: active (running)",
    Type=notify, NotifyAccess=main, MainPID the shell's pid.  `tesserae-shell status` works.
    The shell's log has no "Register failed" warning (the portal accepts the registration now that
    the desktop file with the id {APP_ID} is installed; the portal's own journal line, if any, is
    `journalctl --user -u xdg-desktop-portal`).
 8  Stop it:  systemctl --user stop {UNIT}  : the shell stops with code 0 (journal: "Deactivated
    successfully"), and `status` says "no shell is running".  Crash restart: start it again, then
    kill -KILL $(pgrep -f 'tesserae-shell run')  : systemd restarts it after 2 s (journal:
    "Scheduled restart job"); a `tesserae-shell quit` (exit 0) does NOT restart it.
 9  LOG OUT AND IN (the enabled unit starts the shell with graphical-session.target): the shell is
    running after KWin is up (check 7-after-login.sh), and log out again: it stops with the session.
    If the shell does not start, `journalctl --user -u {UNIT} -b` says why (three tries in a row
    that fail stop after 5 starts in 60 seconds).

CLEAN UP
10  9-undo.sh : "removed" twice, `systemctl --user is-enabled {UNIT}` says "not-found" or "disabled"
    (nothing is left), and the files are gone (or are your earlier copies, step 1).  A running shell
    is NOT stopped by it:  tesserae-shell quit.
"""


def script(root: Path, name: str, text: str) -> None:
    path = root / name
    path.write_text("#!/bin/sh\n" + HEAD + text)
    path.chmod(0o755)


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root`` (nothing outside it)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "checklist.txt").write_text(CHECKLIST)
    script(
        root,
        "1-backup.sh",
        'mkdir -p "$KIT/backup"\n'
        ': > "$KIT/backup/state.txt"\n'
        f'for f in "$UNITS/{UNIT}" "$APPS/{APP_ID}.desktop"; do\n'
        '  if [ -e "$f" ]; then cp -p "$f" "$KIT/backup/"; echo "had $f" >> "$KIT/backup/state.txt";'
        ' echo "copied $f"; else echo "none $f" >> "$KIT/backup/state.txt"; echo "no file $f"; fi\n'
        "done\n"
        f'echo "enabled: $(systemctl --user is-enabled {UNIT} 2>&1)" | tee -a "$KIT/backup/state.txt"\n'
        'echo "state written to $KIT/backup/state.txt"\n',
    )
    script(
        root,
        "2-print.sh",
        '"$BIN" install-session --print\n"$BIN" install-session --print --json\n',
    )
    script(root, "3-install.sh", '"$BIN" install-session\n')
    script(
        root,
        "4-verify.sh",
        'copy="$(mktemp -d)"\n'
        f'cp "$UNITS/{UNIT}" "$APPS/{APP_ID}.desktop" "$copy/"\n'
        f'systemd-analyze --user verify "$copy/{UNIT}" && echo "unit: ok"\n'
        f'desktop-file-validate "$copy/{APP_ID}.desktop" && echo "desktop file: ok"\n'
        'rm -r "$copy"\n',
    )
    script(
        root,
        "5-stale.sh",
        f'unit="$UNITS/{UNIT}"\n'
        'cp -p "$unit" "$KIT/stale-original.service" || exit 1\n'
        'sed -i "s|^ExecStart=.*|ExecStart=/nonexistent/venv/bin/tesserae-shell run|" "$unit"\n'
        'echo "--- status (a warning; exit 3 when no shell is running)"\n'
        '"$BIN" status; echo "exit $?"\n'
        '"$BIN" --json status; echo "exit $?"\n'
        'echo "--- install-session without --force (exit 1, unit unchanged)"\n'
        '"$BIN" install-session; echo "exit $?"\n'
        'grep ^ExecStart= "$unit"\n'
        'echo "--- install-session --force (replaced), status again"\n'
        '"$BIN" install-session --force; echo "exit $?"\n'
        '"$BIN" status; echo "exit $?"\n',
    )
    script(
        root,
        "6-enable.sh",
        'echo "THIS ENABLES THE UNIT in your REAL systemd user manager (starts nothing)." >&2\n'
        'echo "Did you run 1-backup.sh? Ctrl+C within 5 s to stop." >&2\n'
        "sleep 5\n"
        '"$BIN" install-session --enable\n'
        f"systemctl --user is-enabled {UNIT}\n",
    )
    script(
        root,
        "7-after-login.sh",
        f"systemctl --user status {UNIT} --no-pager\n"
        f"systemctl --user show {UNIT} -p Type -p NotifyAccess -p MainPID -p ActiveState"
        " -p NRestarts -p ExecStart --no-pager\n"
        f'journalctl --user -u {UNIT} -b --no-pager | tail -n 40\n"$BIN" status; echo "exit $?"\n',
    )
    script(
        root,
        "9-undo.sh",
        '"$BIN" install-session --remove\n'
        "restored=0\n"
        f"for f in {UNIT} {APP_ID}.desktop; do\n"
        '  if grep -q "^had .*/$f$" "$KIT/backup/state.txt" 2>/dev/null; then\n'
        f'    case "$f" in {UNIT}) dest="$UNITS";; *) dest="$APPS";; esac\n'
        '    mkdir -p "$dest"; cp -p "$KIT/backup/$f" "$dest/$f"; echo "restored $dest/$f"; restored=1\n'
        "  fi\n"
        "done\n"
        '[ "$restored" = 1 ] && systemctl --user daemon-reload\n'
        'if grep -q "^enabled: enabled" "$KIT/backup/state.txt" 2>/dev/null; then\n'
        f'  echo "it was enabled before: enable it again with  {BIN} install-session --enable"\n'
        "fi\n"
        f"systemctl --user is-enabled {UNIT}\n"
        'echo "a running shell is not stopped: tesserae-shell quit"\n',
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
