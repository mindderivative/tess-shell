"""Regenerate the crash-recovery kit in /tmp/tess-kwin-m7b-watchdog (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m7b_watchdog.py``. It writes the kit
folder and starts nothing. Then ``/tmp/tess-kwin-m7b-watchdog/run-all.sh`` runs every step
(``tests/kitlib.py``) in a PRIVATE systemd user manager inside a private ``dbus-run-session`` with
temporary XDG folders, next to a private headless sway, so nothing touches the real home, the real
systemd user manager or the real session. ``results.txt`` has one PASS/FAIL/SKIP line per step;
``results/<id>.txt`` the command, the output and the verdict. Where the private manager cannot be
started (a CI runner is not a login session) the steps are skipped with that reason.

What it proves, with the REAL timings (nothing is scaled: the shell's own 2 s and 10 s, the unit's
``WatchdogSec=15``):

* a healthy shell is pinged and is never killed by the manager, also past ``WatchdogSec``;
* a module whose action sleeps 20 s is named in the log (module and entry point) with the
  tracebacks, the shell asks for the restart at 10 s, the manager ends it with ``SIGABRT``
  (``Result=watchdog``), restarts it after 2 s, ``crash.log.1`` holds the traceback and the shell
  is back with its surfaces, counting one unclean start;
* the manager's own rule, with no shell involved: a ``Type=notify`` service with ``WatchdogSec=15``
  that never pings is ended with ``SIGABRT`` after 15 s and restarted after 2 s;
* ``SIGKILL`` is restarted and counted; a killed private compositor makes the shell stop what it
  runs and exit with code 69, which the manager restarts (not counted as a crash);
* a clean ``systemctl stop`` leaves no marker and resets the count.

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
from tests.shell_samples import BODY, HEADER, SVG  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m7b-watchdog")
# the environment this generator runs in, so that the scripts run this code
BIN = Path(sys.executable).parent / "tesserae-shell"
PYTHON = sys.executable

UNIT = "tesserae-shell.service"
SILENT = "kit-silent.service"
TEXT_LINE = 'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }'

HEAD = f"""UNIT="$XDG_CONFIG_HOME/systemd/user/{UNIT}"
CTL="systemctl --user"
SHELL_OUT="$SANDBOX/shell.out"
STATE="$XDG_STATE_HOME/tesserae-shell"
SYSD_LOG="$SANDBOX/systemd.log"
now() {{ date +%s.%N; }}
since() {{ awk "BEGIN{{printf \\"%.1f\\", $(now) - $1}}"; }}
# wait up to $2 s for the command in $1 to succeed
wait_for() {{ for i in $(seq 1 $(( $2 * 10 ))); do eval "$1" && return 0; sleep 0.1; done; return 1; }}
running() {{ [ "$($CTL show {UNIT} -p ActiveState --value)" = active ]; }}
answers() {{ "$BIN" status >/dev/null 2>&1; }}
"""

TITLE = "M7b kit: the watchdog, the crash record and a lost compositor in a private systemd manager"

INTRO = f"""The unit: $XDG_CONFIG_HOME/systemd/user/{UNIT}, written by install-session into a private
folder; the shell's output goes to $SANDBOX/shell.out and the manager's own log to
$SANDBOX/systemd.log (both are copied to results/sandbox/). Everything runs unattended: nothing is
left for you except reading results.txt."""

# -- the files the steps copy into the sandbox --------------------------------------------------

HANG_TDL = HEADER.replace("Main_Shell", "Hang") + 'Module { Text { Text: "hang" } }\n'
HANG_PY = '''"""An action that keeps the loop for 20 seconds (a module that does not return)."""
import time
from tess_shell import Module, action


class Hang(Module):
    @action
    def sleep(self, event):
        time.sleep(20)
'''
SETTINGS = "---\nTDL: 0.2\nName: Settings\n---\nSettings { Logging { Level: INFO } }\n"
SILENT_PY = '''"""A Type=notify service that says READY=1 and then never pings the watchdog."""
import os
import signal
import socket
import time

OUT = os.environ["SILENT_OUT"]


def log(text):
    with open(OUT, "a") as handle:
        handle.write(f"{time.time():.2f} {text}\\n")


def on_abort(signum, frame):
    log("SIGABRT received")
    signal.signal(signal.SIGABRT, signal.SIG_DFL)
    os.kill(os.getpid(), signal.SIGABRT)


signal.signal(signal.SIGABRT, on_abort)
address = os.environ["NOTIFY_SOCKET"]
if address.startswith("@"):
    address = "\\0" + address[1:]
with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
    sock.sendto(b"READY=1", address)
log(f"started pid {os.getpid()} WATCHDOG_USEC={os.environ.get('WATCHDOG_USEC')}")
time.sleep(1000)
'''
FILES = {
    "config/settings.tdl": SETTINGS,
    "config/Shells/Main_Shell.tdl": HEADER + BODY.replace(TEXT_LINE, "Hang { }"),
    "config/Shells/dot.svg": SVG,
    "config/Modules/Hang/Hang_Module.tdl": HANG_TDL,
    "config/Modules/Hang/Hang_Module.py": HANG_PY,
    "silent.py": SILENT_PY,
}


def sh(body: str) -> str:
    """A step script: the shared helpers, then ``body``."""
    return HEAD + body


# -- the checks that are richer than a regex -------------------------------------------------------

RESTART_TIME = """
def check(result):
    import re
    found = re.search(r"restarted after (\\d+\\.\\d) s", result.stdout)
    if not found:
        return "no 'restarted after N s' line"
    seconds = float(found.group(1))
    # the shell decides at 10 s and systemd ends it at once; the unit waits RestartSec=2
    if not 9.0 <= seconds <= 30.0:
        return f"restarted after {seconds} s, expected about 12 s (the 10 s decision plus 2 s)"
    return None
"""

SILENT_TIME = """
def check(result):
    import re
    nums = [float(m) for m in re.findall(r"^(\\d+\\.\\d+) started", result.stdout, re.M)]
    aborts = [float(m) for m in re.findall(r"^(\\d+\\.\\d+) SIGABRT received", result.stdout, re.M)]
    if len(nums) < 2 or not aborts:
        return f"starts {nums}, SIGABRT at {aborts}"
    ended = aborts[0] - nums[0]
    again = nums[1] - aborts[0]
    if not 14.0 <= ended <= 20.0:
        return f"SIGABRT came {ended:.1f} s after READY=1 and the last start, expected about 15 s"
    if not 1.5 <= again <= 6.0:
        return f"restarted {again:.1f} s after the SIGABRT, expected about 2 s"
    return None
"""


def steps() -> list[Step]:
    return [
        Step(
            "1-unit",
            "install-session writes the unit with WatchdogSec=15; the manager reads it",
            command=sh(
                'mkdir -p "$XDG_CONFIG_HOME" && cp -r "$KIT/config" "$XDG_CONFIG_HOME/tesserae-shell"'
                " || exit 1\n"
                'dropin="$XDG_RUNTIME_DIR/systemd/user/' + UNIT + '.d"\n'
                'mkdir -p "$dropin"\n'
                'printf "[Service]\\nStandardOutput=append:%s\\nStandardError=append:%s\\n"'
                ' "$SHELL_OUT" "$SHELL_OUT" > "$dropin/kit-log.conf"\n'
                '"$BIN" install-session --enable || exit 1\n'
                'grep -E "^(WatchdogSec|StartLimit|Restart|Type|NotifyAccess)" "$UNIT"\n'
                "$CTL daemon-reload\n"
                "$CTL show " + UNIT + " -p Type -p Restart -p RestartUSec\n"
            ),
            sandbox="systemd+sway",
            expect=(
                "^WatchdogSec=15$",
                "^Type=notify$",
                "^Restart=on-failure$",
                "^RestartUSec=2s$",
            ),
        ),
        Step(
            "2-start",
            "systemctl start: ready (Type=notify), the watchdog is armed, NRestarts=0",
            command=sh(
                "$CTL start " + UNIT + " || exit 1\n"
                "wait_for answers 30 || { echo 'the shell never answered'; exit 1; }\n"
                "$CTL show " + UNIT + " -p ActiveState -p SubState -p NRestarts -p MainPID"
                " -p WatchdogUSec\n"
                '"$BIN" status\n'
            ),
            sandbox="systemd+sway",
            timeout=120,
            expect=(
                "^ActiveState=active$",
                "^NRestarts=0$",
                "^MainPID=[1-9][0-9]*$",
                "^WatchdogUSec=15s$",
                "^surfaces:$",
                "Top_Bar  bar  shown",
                "^unclean starts since the last clean stop: 0$",
                "^last crash: none$",
            ),
        ),
        Step(
            "3-pings",
            "a healthy shell is pinged: 20 s (more than WatchdogSec) and the manager leaves it alone",
            command=sh(
                "pid=$($CTL show " + UNIT + " -p MainPID --value)\n"
                "sleep 20\n"
                "now_pid=$($CTL show " + UNIT + " -p MainPID --value)\n"
                'echo "pid before $pid, after $now_pid"\n'
                "$CTL show " + UNIT + " -p ActiveState -p NRestarts\n"
                '[ "$pid" = "$now_pid" ]\n'
            ),
            sandbox="systemd+sway",
            timeout=60,
            expect=("^ActiveState=active$", "^NRestarts=0$"),
        ),
        Step(
            "4-hang",
            "a module that sleeps 20 s: named in the log, systemd ends it with SIGABRT and restarts it",
            command=sh(
                "old=$($CTL show " + UNIT + " -p MainPID --value)\n"
                "t0=$(now)\n"
                '"$BIN" --timeout 2 call Hang sleep >/dev/null 2>&1; echo "call exit: $?"\n'
                'result=""\n'
                "for i in $(seq 1 600); do\n"
                "  new=$($CTL show " + UNIT + " -p MainPID --value)\n"
                "  r=$($CTL show " + UNIT + " -p Result --value)\n"
                '  [ "$r" = watchdog ] && result=watchdog\n'
                '  [ "$new" != "$old" ] && [ "$new" != 0 ] && running && break\n'
                "  sleep 0.1\n"
                "done\n"
                'echo "restarted after $(since $t0) s: old pid $old, new pid $new"\n'
                'echo "result seen while it was down: ${result:-none}"\n'
                "wait_for answers 30 || { echo 'the shell is not back'; exit 1; }\n"
                "$CTL show " + UNIT + " -p ActiveState -p NRestarts\n"
                'echo "--- the shell\'s log"\n'
                'grep -E "loop stalled|traceback of every thread|asking systemd|previous run" '
                '"$SHELL_OUT"\n'
                'echo "--- the manager\'s log"\n'
                'grep -iE "watchdog|ABRT|Main process exited|Failed with result" "$SYSD_LOG" '
                "| tail -n 8\n"
                'echo "--- crash.log.1"\n'
                'grep -E "Fatal Python error|in sleep|File .*Hang_Module.py" "$STATE/crash.log.1"\n'
                'echo "--- status"; "$BIN" status\n'
            ),
            sandbox="systemd+sway",
            timeout=180,
            check=RESTART_TIME,
            expect=(
                "result seen while it was down: watchdog",
                "^ActiveState=active$",
                "^NRestarts=1$",
                r"WARNING .*loop stalled for 2 s: module Hang, entry point sleep, running for",
                "the traceback of every thread",
                "asking systemd to restart the shell",
                "previous run ended uncleanly",
                "Fatal Python error: Aborted",
                r"in sleep",
                "Top_Bar  bar  shown",
                "^unclean starts since the last clean stop: 1$",
            ),
        ),
        Step(
            "5-silent-service",
            "the manager's own rule: a Type=notify service that never pings is SIGABRTed after 15 s",
            command=sh(
                'mkdir -p "$XDG_CONFIG_HOME/systemd/user"\n'
                'out="$SANDBOX/silent.out"; rm -f "$out"\n'
                'cat > "$XDG_CONFIG_HOME/systemd/user/' + SILENT + '" <<EOF\n'
                "[Unit]\n"
                "Description=Kit: a notify service that never pings\n"
                "StartLimitIntervalSec=0\n"
                "[Service]\n"
                "Type=notify\n"
                "NotifyAccess=main\n"
                "WatchdogSec=15\n"
                "Restart=on-failure\n"
                "RestartSec=2\n"
                "Environment=SILENT_OUT=$out\n"
                f"ExecStart={PYTHON} $KIT/silent.py\n"
                "EOF\n"
                "$CTL daemon-reload\n"
                "$CTL start " + SILENT + " || exit 1\n"
                "wait_for \"[ \\$(grep -c started '$out') -ge 2 ]\" 60 || echo 'no second start'\n"
                "$CTL show " + SILENT + " -p NRestarts -p WatchdogUSec\n"
                "$CTL stop " + SILENT + "\n"
                'cat "$out"\n'
            ),
            sandbox="systemd+sway",
            timeout=120,
            check=SILENT_TIME,
            expect=(
                "^WatchdogUSec=15s$",
                "^NRestarts=[1-9]$",
                "WATCHDOG_USEC=15000000",
                "SIGABRT received",
            ),
        ),
        Step(
            "6-sigkill",
            "kill -KILL: restarted, the next start logs and counts the unclean end",
            command=sh(
                "wait_for answers 30 || exit 1\n"
                "old=$($CTL show " + UNIT + " -p MainPID --value)\n"
                "n0=$($CTL show " + UNIT + " -p NRestarts --value)\n"
                'kill -KILL "$old" || exit 1\n'
                'wait_for "[ \\"\\$($CTL show '
                + UNIT
                + ' -p NRestarts --value)\\" -gt $n0 ] && running"'
                " 30 || exit 1\n"
                "wait_for answers 30 || exit 1\n"
                'echo "old pid $old, new pid $($CTL show ' + UNIT + ' -p MainPID --value)"\n'
                "$CTL show " + UNIT + " -p NRestarts\n"
                '"$BIN" status\n'
                'grep -c "previous run ended uncleanly" "$SHELL_OUT"\n'
            ),
            sandbox="systemd+sway",
            timeout=120,
            expect=(
                "^NRestarts=2$",
                "^unclean starts since the last clean stop: 2$",
                "^last crash: 20",
                "^2$",
            ),
        ),
        Step(
            "7-lost-compositor",
            "a killed compositor: the shell stops what it runs, exits 69 and is restarted",
            command=sh(
                'main_display="$WAYLAND_DISPLAY"\n'
                'cfg="$SANDBOX/sway2-config"; disp="$SANDBOX/sway2-display"; pidf="$SANDBOX/sway2-pid"\n'
                'rm -f "$disp" "$pidf"\n'
                'printf "exec sh -c \'echo \\$WAYLAND_DISPLAY > $disp\'\\n" > "$cfg"\n'
                "trap 'kill -KILL $(cat \"$pidf\") 2>/dev/null' EXIT\n"
                "WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman "
                "env -u WAYLAND_DISPLAY -u SWAYSOCK setsid sh -c "
                "'echo $$ > \"'$pidf'\"; exec sway -c \"'$cfg'\"' >\"$SANDBOX/sway2.log\" 2>&1 &\n"
                'wait_for "[ -s \\"$disp\\" ]" 30 || { echo "the second sway did not start"; exit 1; }\n'
                'second="$(cat "$disp")"\n'
                'echo "second compositor: $second (the sandbox one: $main_display)"\n'
                "# the shell restarts on the second compositor (a clean stop: nothing counted)\n"
                '$CTL set-environment WAYLAND_DISPLAY="$second"\n'
                "$CTL restart " + UNIT + " || exit 1\n"
                "wait_for answers 30 || { echo 'the shell did not start on the second one'; exit 1; }\n"
                "# the unit's next start must find a compositor: point it back at the first\n"
                '$CTL set-environment WAYLAND_DISPLAY="$main_display"\n'
                "old=$($CTL show " + UNIT + " -p MainPID --value)\n"
                "n0=$($CTL show " + UNIT + " -p NRestarts --value)\n"
                'kill -KILL "$(cat "$pidf")"; t0=$(now)\n'
                'wait_for "[ \\"\\$($CTL show '
                + UNIT
                + ' -p NRestarts --value)\\" -gt $n0 ] && running"'
                " 30 || { echo 'not restarted'; exit 1; }\n"
                "wait_for answers 30 || exit 1\n"
                'echo "restarted after $(since $t0) s: old pid $old, new pid $($CTL show '
                + UNIT
                + ' -p MainPID --value)"\n'
                "$CTL show " + UNIT + " -p NRestarts\n"
                'echo "--- the shell\'s log"\n'
                'grep -E "Wayland connection was lost|^.*\\| stopped" "$SHELL_OUT" | tail -n 3\n'
                'echo "--- the manager\'s log"\n'
                'grep -E "status=69|code=exited" "$SYSD_LOG" | tail -n 3\n'
                '"$BIN" status\n'
            ),
            sandbox="systemd+sway",
            timeout=180,
            expect=(
                r"the Wayland connection was lost .*stopping with exit code 69",
                r"\| stopped",
                "^NRestarts=1$",  # the manual restart before it reset the counter
                # the manual restart was a clean stop (count 0) and a lost compositor is not a crash
                "^unclean starts since the last clean stop: 0$",
                "^last crash: 20",
                "Top_Bar  bar  shown",
            ),
        ),
        Step(
            "8-stop",
            "systemctl stop: exit 0, no marker, the count starts again",
            command=sh(
                "$CTL stop " + UNIT + "; code=$?\n"
                "$CTL show " + UNIT + " -p ActiveState -p Result -p ExecMainStatus\n"
                '[ ! -e "$STATE/running" ] && echo "no marker"\n'
                'ls "$STATE"\n'
                '"$BIN" status; echo "status exit: $?"\n'
                "exit $code\n"
            ),
            sandbox="systemd+sway",
            expect=(
                "^ActiveState=inactive$",
                "^Result=success$",
                "^ExecMainStatus=0$",
                "^no marker$",
                "^status exit: 3$",
                "no shell is running",
            ),
            # the count starts again; the time of the last crash stays as information
            forbid=("unclean starts since the last clean stop: [1-9]",),
        ),
        Step(
            "9-remove",
            "install-session --remove leaves nothing",
            command=sh(
                '"$BIN" install-session --remove || exit 1\n'
                'rm -f "$XDG_CONFIG_HOME/systemd/user/' + SILENT + '"\n'
                'rm -rf "$XDG_RUNTIME_DIR/systemd/user/' + UNIT + '.d"\n'
                "$CTL daemon-reload\n"
                'echo "is-enabled: $($CTL is-enabled ' + UNIT + ' 2>&1)"\n'
                '[ ! -e "$UNIT" ] && echo "unit gone"\n'
            ),
            sandbox="systemd+sway",
            expect=(
                rf"removed .*{re.escape(UNIT)}",
                "is-enabled: (not-found|disabled)",
                "unit gone",
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
        files=FILES,
        variables={"BIN": str(BIN)},
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
