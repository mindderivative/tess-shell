"""Regenerate the install-session kit in /tmp/tess-kwin-install-session (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_install_session.py``. It writes the kit
folder and starts nothing. Then ``/tmp/tess-kwin-install-session/run-all.sh`` runs every step that
needs no person (``tests/kitlib.py``): ``install-session`` writes the two files and runs
``systemctl --user`` in a PRIVATE systemd user manager inside a private ``dbus-run-session`` with
temporary XDG folders, next to a private KWin, so nothing touches the real home, the real systemd
user manager or the real session (Orchestration Log D-019, D-025, D-026). ``results.txt`` has one
PASS/FAIL/SKIP line per step; ``results/<id>.txt`` the command, the output and the verdict.

``checklist.txt`` holds ONLY what no session can do: logging out and in (step 9) and the real
xdg-desktop-portal's answer to the application id (the one step that needs the real session).

The unit it starts runs ``BIN run``: the ``tesserae-shell`` beside the interpreter that ran this
generator.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests import kitlib  # noqa: E402
from tests.kitlib import Step  # noqa: E402

ROOT = Path("/tmp/tess-kwin-install-session")
# the environment this generator runs in, so that the scripts run this code
BIN = Path(sys.executable).parent / "tesserae-shell"

APP_ID = "io.github.mindderivative.TesseraeShell"
UNIT = "tesserae-shell.service"
DESKTOP = f"{APP_ID}.desktop"

HEAD = f"""UNIT="$XDG_CONFIG_HOME/systemd/user/{UNIT}"
DESK="$XDG_DATA_HOME/applications/{DESKTOP}"
CTL="systemctl --user"
SHELL_OUT="$SANDBOX/shell.out"
"""

TITLE = "install-session kit: the files, the unit and its start in a private systemd manager"

INTRO = f"""The files:   $XDG_CONFIG_HOME/systemd/user/{UNIT}
             $XDG_DATA_HOME/applications/{DESKTOP}
the unattended steps write them to a private folder, never to your home. The checks of the
earlier list (steps 0 to 8 and 10) are results.txt lines. Left for you: step 9 and 7d."""


# the scripts of the earlier kit: they wrote to the real home, and are gone
OBSOLETE = (
    "1-backup.sh",
    "2-print.sh",
    "3-install.sh",
    "4-verify.sh",
    "5-stale.sh",
    "6-enable.sh",
    "7-after-login.sh",
    "9-undo.sh",
    "stale-original.service",
)


def sh(body: str) -> str:
    """A step script: the shared variables, then ``body``."""
    return HEAD + body


# -- the checks that are richer than a regex -------------------------------------------------

JSON_WARNINGS = """
def check(result):
    import json
    lines = [ln for ln in result.stdout.splitlines() if ln.strip().startswith("{")]
    if not lines:
        return "no JSON object on standard output"
    data = json.loads(lines[-1])
    warnings = data.get("warnings")
    if not isinstance(warnings, list) or not warnings:
        return f"no 'warnings' list in {data}"
    if not any("/nonexistent/venv/bin/tesserae-shell" in w and "does not exist" in w
               for w in warnings):
        return f"the warnings do not name the missing command: {warnings}"
    return None
"""

PRINT_JSON = """
def check(result):
    import json
    lines = [ln for ln in result.stdout.splitlines() if ln.startswith("{")]
    if not lines:
        return "no JSON object on standard output"
    data = json.loads(lines[-1])
    kinds = sorted(f["kind"] for f in data.get("files", []))
    if kinds != ["desktop", "unit"]:
        return f"--json lists {kinds}, expected the desktop file and the unit"
    return None
"""


def steps(bin_path: Path = BIN) -> list[Step]:
    stale_bin = r"/nonexistent/venv/bin/tesserae-shell"
    exec_start = re.escape(f"ExecStart={bin_path} run")
    return [
        Step(
            "2-print",
            "install-session --print (text, then --json) writes nothing",
            command=sh(
                '"$BIN" install-session --print || exit 1\n'
                '"$BIN" install-session --print --json || exit 1\n'
                '[ ! -e "$UNIT" ] && [ ! -e "$DESK" ] && echo "nothing written"\n'
            ),
            sandbox="bus",
            expect=(
                re.escape(UNIT),
                re.escape(DESKTOP),
                exec_start,
                "nothing written",
            ),
            check=PRINT_JSON,
        ),
        Step(
            "3a-install",
            "install-session writes exactly the two files, enables nothing",
            command=sh(
                '"$BIN" install-session || exit 1\n'
                'ls -1 "$UNIT" "$DESK"\n'
                'find "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" -type f | sort\n'
            ),
            sandbox="bus",
            expect=(
                rf"written .*{re.escape(UNIT)}",
                rf"written .*{re.escape(DESKTOP)}",
                "not enabled",
            ),
            forbid=("replaced", "unchanged"),
            check="""
def check(result):
    files = [ln for ln in result.stdout.splitlines() if ln.startswith("/") and "/tmp/tk-" in ln]
    names = sorted({ln.rsplit("/", 1)[-1] for ln in files})
    if names != sorted(["tesserae-shell.service", "io.github.mindderivative.TesseraeShell.desktop"]):
        return f"files written: {names}"
    return None
""",
        ),
        Step(
            "3b-install-again",
            "install-session again: unchanged twice (idempotent)",
            command=sh('"$BIN" install-session\n'),
            sandbox="bus",
            expect=(rf"unchanged .*{re.escape(UNIT)}", rf"unchanged .*{re.escape(DESKTOP)}"),
            forbid=("written", "replaced"),
        ),
        Step(
            "4a-verify-unit",
            "the unit passes systemd-analyze --user verify (no output, exit 0)",
            command=sh(
                'copy="$(mktemp -d)"\ncp "$UNIT" "$copy/"\nsystemd-analyze --user verify "$copy/'
                + UNIT
                + '"\n'
            ),
            sandbox="bus",
            tools=("systemd-analyze",),
            forbid=(r"\S",),
        ),
        Step(
            "4b-verify-desktop",
            "the desktop file passes desktop-file-validate (no output, exit 0)",
            command=sh('desktop-file-validate "$DESK"\n'),
            sandbox="bus",
            tools=("desktop-file-validate",),
            forbid=(r"\S",),
        ),
        Step(
            "5a-stale-status",
            "a unit that starts a missing command: status warns, exit 3",
            command=sh(
                'sed -i "s|^ExecStart=.*|ExecStart=' + stale_bin + ' run|" "$UNIT" || exit 1\n'
                'grep ^ExecStart= "$UNIT"\n'
                '"$BIN" status\n'
            ),
            sandbox="bus",
            exit_code=3,
            expect=(
                r"warning: the unit .*"
                + re.escape(UNIT)
                + r" starts "
                + re.escape(stale_bin)
                + r", which does not exist; run `tesserae-shell install-session --force`",
                "no shell is running",
            ),
        ),
        Step(
            "5b-stale-json",
            "the same with --json: a warnings list, exit 3",
            command=sh('"$BIN" --json status\n'),
            sandbox="bus",
            exit_code=3,
            check=JSON_WARNINGS,
        ),
        Step(
            "5c-stale-kept",
            "install-session without --force: exit 1, 'exists and differs ... nothing was changed'",
            command=sh('"$BIN" install-session; code=$?\ngrep ^ExecStart= "$UNIT"\nexit $code\n'),
            sandbox="bus",
            exit_code=1,
            expect=(
                re.escape(UNIT) + r" exists and differs from what install-session writes; "
                r"nothing was changed",
                "^ExecStart=" + re.escape(stale_bin) + " run$",
            ),
        ),
        Step(
            "5d-stale-force",
            "install-session --force replaces it",
            command=sh('"$BIN" install-session --force || exit 1\ngrep ^ExecStart= "$UNIT"\n'),
            sandbox="bus",
            expect=(rf"replaced .*{re.escape(UNIT)}", "^" + exec_start + "$"),
            forbid=(re.escape(stale_bin),),
        ),
        Step(
            "5e-stale-gone",
            "after --force status no longer warns (exit 3: no shell is running)",
            command=sh('"$BIN" status\n'),
            sandbox="bus",
            exit_code=3,
            expect=("no shell is running",),
            forbid=("warning",),
        ),
        Step(
            "6-enable",
            "install-session --enable enables the unit and starts nothing",
            command=sh(
                # the kit sends the shell's output to a file instead of the (real) journal
                'dropin="$XDG_RUNTIME_DIR/systemd/user/' + UNIT + '.d"\n'
                'mkdir -p "$dropin"\n'
                'printf "[Service]\\nStandardOutput=append:%s\\nStandardError=append:%s\\n"'
                ' "$SHELL_OUT" "$SHELL_OUT" > "$dropin/kit-log.conf"\n'
                '"$BIN" install-session --enable || exit 1\n'
                "$CTL is-enabled " + UNIT + "; code=$?\n"
                "$CTL is-active " + UNIT + "\n"
                "exit $code\n"
            ),
            sandbox="systemd+kwin",
            expect=("enabled " + re.escape(UNIT), r"^enabled$", r"^inactive$"),
        ),
        Step(
            "7a-start",
            "systemctl start returns once the shell is ready (Type=notify): active, NRestarts=0",
            command=sh(
                "$CTL start " + UNIT + "; code=$?\n"
                "$CTL show " + UNIT + " -p ActiveState -p SubState -p Type -p NotifyAccess"
                " -p Result -p NRestarts -p MainPID\n"
                'for i in $(seq 1 100); do grep -q running "$SHELL_OUT" 2>/dev/null && break;'
                " sleep 0.1; done\n"
                'echo "--- the shell\'s output"; tail -n 20 "$SHELL_OUT"\n'
                "exit $code\n"
            ),
            sandbox="systemd+kwin",
            timeout=150,
            expect=(
                "^ActiveState=active$",
                "^SubState=running$",
                "^Type=notify$",
                "^NotifyAccess=main$",
                "^Result=success$",
                "^NRestarts=0$",
                "^MainPID=[1-9][0-9]*$",
                r"--- the shell's output.*running",
            ),
        ),
        Step(
            "7b-status",
            "tesserae-shell status talks to the running shell (exit 0)",
            command=sh('"$BIN" status\n'),
            sandbox="systemd+kwin",
            forbid=("warning", "no shell is running"),
        ),
        Step(
            "8a-kill-restarts",
            "kill -KILL: systemd restarts the shell (NRestarts=1, active again)",
            command=sh(
                "old=$($CTL show " + UNIT + " -p MainPID --value)\n"
                'kill -KILL "$old" || exit 1\n'
                "for i in $(seq 1 200); do\n"
                "  n=$($CTL show " + UNIT + " -p NRestarts --value)\n"
                "  s=$($CTL show " + UNIT + " -p ActiveState --value)\n"
                '  [ "$n" = 1 ] && [ "$s" = active ] && break\n'
                "  sleep 0.2\n"
                "done\n"
                "new=$($CTL show " + UNIT + " -p MainPID --value)\n"
                'echo "old pid $old, new pid $new"\n'
                "$CTL show " + UNIT + " -p ActiveState -p NRestarts\n"
                '[ "$old" != "$new" ]\n'
            ),
            sandbox="systemd+kwin",
            timeout=90,
            expect=("^ActiveState=active$", "^NRestarts=1$"),
        ),
        Step(
            "8b-stop",
            "systemctl stop: the shell stops with code 0, status says no shell is running",
            command=sh(
                "$CTL stop " + UNIT + "; code=$?\n"
                "$CTL show " + UNIT + " -p ActiveState -p Result -p ExecMainStatus\n"
                '"$BIN" status; echo "status exit: $?"\n'
                "exit $code\n"
            ),
            sandbox="systemd+kwin",
            expect=(
                "^status exit: 3$",
                "^ActiveState=inactive$",
                "^Result=success$",
                "^ExecMainStatus=0$",
                "no shell is running",
            ),
        ),
        Step(
            "8c-quit-no-restart",
            "tesserae-shell quit (exit 0) does not restart it",
            command=sh(
                "$CTL start " + UNIT + " || exit 1\n"
                '"$BIN" quit || exit 1\n'
                "for i in $(seq 1 100); do\n"
                "  s=$($CTL show " + UNIT + " -p ActiveState --value)\n"
                '  [ "$s" = inactive ] && break\n'
                "  sleep 0.1\n"
                "done\n"
                "$CTL show " + UNIT + " -p ActiveState -p SubState -p Result -p NRestarts\n"
            ),
            sandbox="systemd+kwin",
            timeout=150,
            expect=(
                "^ActiveState=inactive$",
                "^SubState=dead$",
                "^Result=success$",
                "^NRestarts=0$",
            ),
        ),
        Step(
            "8d-disable",
            "systemctl disable, then install-session --enable once more",
            command=sh(
                "$CTL disable " + UNIT + " || exit 1\n"
                "$CTL is-enabled " + UNIT + "\n"
                '"$BIN" install-session --enable || exit 1\n'
                "$CTL is-enabled " + UNIT + "\n"
            ),
            sandbox="systemd+kwin",
            expect=("^disabled$", "^enabled$"),
        ),
        Step(
            "10-remove",
            "install-session --remove: removed twice, nothing is left",
            command=sh(
                '"$BIN" install-session --remove || exit 1\n'
                'rm -r "$XDG_RUNTIME_DIR/systemd/user/' + UNIT + '.d"\n'
                "$CTL daemon-reload\n"
                'echo "is-enabled: $($CTL is-enabled ' + UNIT + ' 2>&1)"\n'
                '[ ! -e "$UNIT" ] && [ ! -e "$DESK" ] && echo "files gone"\n'
                'find "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" -name "*tesserae*" -o -name "*Tesserae*"'
                ' | grep -v "/tesserae-shell/" ; echo "left over: none"\n'
            ),
            sandbox="systemd+kwin",
            expect=(
                rf"removed .*{re.escape(UNIT)}",
                rf"removed .*{re.escape(DESKTOP)}",
                "is-enabled: (not-found|disabled)",
                "files gone",
                "left over: none",
            ),
        ),
        Step(
            "9-login",
            "log out and in: the enabled unit starts the shell with graphical-session.target",
            kind="manual",
            reason=(
                "needs a real login: the real graphical-session.target and KWin's session start "
                "exist only in a real logind session; no sandbox can log out and in. After the "
                "login the shell is running (tesserae-shell status), and logging out again stops "
                "it. If it does not start: journalctl --user -u tesserae-shell.service -b."
            ),
            expect=("tesserae-shell status exits 0 after the login",),
        ),
        Step(
            "7d-portal",
            "the REAL xdg-desktop-portal accepts the application id once the desktop file is "
            "installed in the real home",
            kind="real-session",
            reason=(
                "an xdg-desktop-portal does start on the private bus (its own service file), but "
                "its answer to Register is not a usable stand-in for yours: with no desktop file "
                "it says 'App info not found for io.github.mindderivative.TesseraeShell', with "
                "the file installed it says 'Connection already associated with an application "
                "ID' to a shell started from a terminal and gives no reply in 5 s to the shell "
                "started by the unit (the cause is not established; [INFERENCE] the sandbox's "
                "processes share the cgroup and identity of the session that ran the kit). "
                "Only your real portal can say whether "
                "it ACCEPTS the id. It is probably already shown: your run of the shell with the "
                "file installed printed no 'portal: Register failed' warning."
            ),
            action=(
                f"run `{BIN} install-session` (writes {DESKTOP} and {UNIT} in your real ~/.local/"
                f"share/applications and ~/.config/systemd/user), start the shell, and read its "
                "log: there must be no 'portal: Register failed' line (undo with "
                f"`{BIN} install-session --remove`)"
            ),
        ),
    ]


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root`` (nothing outside it)."""
    kitlib.write_kit(
        root,
        steps(),
        title=TITLE,
        intro=INTRO,
        variables={"BIN": str(BIN)},
        obsolete=OBSOLETE,
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
