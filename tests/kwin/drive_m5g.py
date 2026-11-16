"""The drivers of the M5g kit (copied into ``/tmp/tess-kwin-m5g`` as ``drive_m5g.py`` by
``prepare_m5g_kwin.py``; not collected by pytest). ``python drive_m5g.py NAME`` runs in the step's
PRIVATE KWin (its own kwinrc, kwinrulesrc and script folder), starts the shell and the throwaway
client ``window_probe.py`` there and prints ``PASS``/``FAIL``/``NOTE`` lines (``kitdrive.Report``).

* ``introspect``: the names the code could confirm only from KWin's files, read from the live
  ``/Scripting`` and ``/KWin``.
* ``script``: mode R: the shell loads its script, the window list follows open, retitle, activate,
  minimise, un-minimise and close, fullscreen hides the shell on its output, the stop unloads it.
* ``off``: ``KWin { Script: OFF }`` loads nothing and hides nothing.
* ``commands``: ``kwin script install|status|remove`` and ``kwin rule show|install|remove``.
* ``layer``: does the window rule apply to a layer-shell surface? Layers read by a one-shot KWin
  script before and after the rule, with a client window as the control.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import kitdrive as d

ENV = dict(os.environ)
KIT = Path(ENV["KIT"])
STEP_DIR = Path(ENV["STEP_DIR"])
SANDBOX = Path(ENV["SANDBOX"])
BIN = ENV["BIN"]
PY = ENV["PY"]
KWIN = "org.kde.KWin"
SCRIPTING = "org.kde.kwin.Scripting"


def shell(config: str) -> d.ShellRun:
    run = d.ShellRun(BIN, KIT / config, ENV, log=STEP_DIR / f"{config}.log")
    run.wait_for(r"\| running")
    return run


def status() -> str:
    return d.cli(BIN, ENV, "kwin", "script", "status").stdout


class Probe:
    """``window_probe.py``: ordinary windows in the private KWin, steered by lines on stdin."""

    def __init__(self, *titles: str) -> None:
        self.process = subprocess.Popen(
            [PY, str(KIT / "window_probe.py"), *titles],
            env=ENV,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert self.process.stdout is not None
        self.process.stdout.readline()  # "windows open: N"

    def send(self, line: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()


def windows(run: d.ShellRun) -> list[dict[str, Any]] | None:
    """The newest ``winlog:`` list the shell logged (the kit's ``WinLog`` module), or ``None``."""
    lines = run.grep(r"winlog: ")
    return json.loads(lines[-1].split("winlog: ", 1)[1]) if lines else None  # type: ignore[no-any-return]


def wait_windows(run: d.ShellRun, ok: Any, timeout: float = 20) -> list[dict[str, Any]] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = windows(run)
        if rows is not None and ok(rows):
            return rows
        time.sleep(0.1)
    return windows(run)


def titles(rows: list[dict[str, Any]] | None) -> list[str]:
    return [r["title"] for r in rows or []]


def activate(run: d.ShellRun, window_id: str) -> None:
    """Make a window the active, shown one (a click on the active window would minimise it)."""

    def done(rows: list[dict[str, Any]]) -> bool:
        return any(w["id"] == window_id and w["active"] and not w["minimized"] for w in rows)

    if not done(windows(run) or []):
        call("Tasks", "activate", window_id)
        wait_windows(run, done)


def call(*args: str) -> subprocess.CompletedProcess[str]:
    return d.cli(BIN, ENV, "call", *args)


def script() -> int:
    report = d.Report()
    run = shell("cfg")
    probe: Probe | None = None
    probe_two: Probe | None = None
    try:
        report.check(
            "1 the log names KWin's version",
            _wait(run, r"kwin: KWin \d+\.\d+\.\d+"),
            run.tail(),
            detail=(run.grep(r"kwin: KWin \d+") or [""])[0][-40:],
        )
        report.check(
            "2 the log says the script is loaded",
            _wait(run, r"kwin: the script tesserae-shell-kwin is loaded \(runtime mode\)"),
            run.tail(),
        )
        report.check(
            "3 kwin script status says loaded in KWin now: yes",
            "loaded in KWin now: yes" in (text := status()),
            text,
        )
        probe = Probe("Kit One")
        probe_two = Probe("Kit Two")
        rows = wait_windows(run, lambda r: len(r) >= 2)
        report.check(
            "4 one entry per open window, the shell's own bar not in it",
            sorted(titles(rows)) == ["Kit One", "Kit Two"],
            f"titles {titles(rows)}",
        )
        report.note(f"the order of the list (KWin's, not the order opened): {titles(rows)}")
        active = [r for r in rows or [] if r["active"]]
        report.check("5 exactly one window is active", len(active) == 1, f"{rows}")
        by_title = {r["title"]: r["id"] for r in rows or []}
        other = next((r for r in rows or [] if not r["active"]), None)
        if other is not None:
            call("Tasks", "activate", other["id"])
            rows = wait_windows(
                run, lambda r: any(w["active"] and w["id"] == other["id"] for w in r)
            )
            report.check(
                "6 activating an inactive window makes it the active one",
                any(w["active"] and w["id"] == other["id"] for w in rows or []),
                f"{rows}",
            )
        target = next((r for r in rows or [] if r["active"]), None)
        if target is not None:
            call("Tasks", "activate", target["id"])  # the active one: minimised
            rows = wait_windows(
                run, lambda r: any(w["id"] == target["id"] and w["minimized"] for w in r)
            )
            report.check(
                "7 a click on the active window minimises it",
                any(w["id"] == target["id"] and w["minimized"] for w in rows or []),
                f"{rows}",
            )
            call("Tasks", "activate", target["id"])
            rows = wait_windows(
                run, lambda r: any(w["id"] == target["id"] and not w["minimized"] for w in r)
            )
            report.check(
                "8 activating it again un-minimises it",
                any(w["id"] == target["id"] and not w["minimized"] for w in rows or []),
                f"{rows}",
            )
        probe.send("title 0 Kit One renamed")
        rows = wait_windows(run, lambda r: "Kit One renamed" in titles(r))
        report.check(
            "9 a retitled window is followed", "Kit One renamed" in titles(rows), f"{titles(rows)}"
        )
        # fullscreen: the shell is hidden on the output of an active fullscreen window
        one, two = by_title["Kit One"], by_title["Kit Two"]
        mark = run.mark()
        activate(run, one)
        probe.send("fullscreen 0")
        report.check(
            "10 a fullscreen active window hides the shell on its output",
            _wait(run, r"fullscreen: the shell is hidden on \S+", mark),
            run.tail(),
        )
        mark = run.mark()
        activate(run, two)
        report.check(
            "11 a fullscreen window that is not active shows the shell again",
            _wait(run, r"fullscreen: the shell is shown everywhere", mark),
            run.tail(),
        )
        mark = run.mark()
        activate(run, one)
        _wait(run, r"fullscreen: the shell is hidden on \S+", mark)
        mark = run.mark()
        probe.send("windowed 0")
        report.check(
            "12 leaving fullscreen shows the shell again",
            _wait(run, r"fullscreen: the shell is shown everywhere", mark),
            run.tail(),
        )
        mark = run.mark()
        probe.send("fullscreen 0")
        _wait(run, r"fullscreen: the shell is hidden on \S+", mark)
        # a close through the window list
        mark = run.mark()
        call("Tasks", "close", two)
        rows = wait_windows(run, lambda r: "Kit Two" not in titles(r))
        report.check(
            "13 a middle click closes the window",
            "Kit Two" not in titles(rows),
            f"{titles(rows)}",
        )
        # stop and start again while a window is fullscreen: the bar starts hidden
        code = run.stop()
        report.check("14 the shell stops with code 0", code == 0, f"exit code {code}")
        report.check(
            "15 after the stop the script is no longer loaded",
            "loaded in KWin now: no" in status(),
            status(),
        )
        run = shell("cfg")
        report.check(
            "16 started while a window is fullscreen, the shell starts hidden",
            _wait(run, r"fullscreen: the shell is hidden on \S+"),
            run.tail(),
        )
        report.check(
            "17 no ERROR in the log of either run",
            not run.grep(r"\| ERROR "),
            "; ".join(run.grep(r"\| ERROR ")),
        )
    finally:
        for each in (probe, probe_two):
            if each is not None:
                each.stop()
        run.stop()
    return int(report.code)


def _wait(run: d.ShellRun, pattern: str, after: int = 0, timeout: float = 20) -> bool:
    try:
        run.wait_for(pattern, timeout=timeout, after=after)
        return True
    except d.Timeout:
        return False


def off() -> int:
    report = d.Report()
    run = shell("cfg-off")
    probe = Probe("Kit Off")
    try:
        report.check(
            "1 the script is off in the log",
            bool(run.grep(r"kwin: the script is off")),
            run.tail(),
        )
        report.check(
            "2 nothing is loaded in KWin",
            "loaded in KWin now: no" in status(),
            status(),
        )
        probe.send("fullscreen 0")
        time.sleep(3)  # a negative: nothing may happen; a few seconds are the whole window
        report.check(
            "3 a fullscreen window hides nothing",
            not run.grep(r"fullscreen: the shell is hidden"),
            run.tail(),
        )
        report.check("4 no ERROR in the log", not run.grep(r"\| ERROR "), run.tail())
    finally:
        probe.stop()
        code = run.stop()
    report.check("5 the shell stops with code 0", code == 0, f"exit code {code}")
    return int(report.code)


def introspect() -> int:
    report = d.Report()
    done = subprocess.run(
        ["gdbus", "introspect", "--session", "--dest", KWIN, "--object-path", "/Scripting"],
        env=ENV,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    text = done.stdout
    report.check("1 /Scripting answers", done.returncode == 0, done.stderr)
    report.check(
        "2 the interface is org.kde.kwin.Scripting (lower case)",
        f"interface {SCRIPTING} {{" in text,
        text[:300],
    )
    for method, signature in (
        ("loadScript", r"loadScript\(in\s+s\s+\w+,\s+in\s+s\s+\w+,\s+out\s+i\s+\w+\)"),
        ("unloadScript", r"unloadScript\(in\s+s\s+\w+,\s+out\s+b\s+\w+\)"),
        ("isScriptLoaded", r"isScriptLoaded\(in\s+s\s+\w+,\s+out\s+b\s+\w+\)"),
        ("start", r"start\(\)"),
    ):
        report.check(
            f"3 {method} has the signature the code uses",
            bool(re.search(signature, text)),
            f"no {signature} in: {text[:400]}",
        )
    info = d.gdbus(ENV, KWIN, "/KWin", "org.kde.KWin.supportInformation")
    report.check(
        "4 /KWin supportInformation answers with KWin's version",
        info.returncode == 0 and "KWin" in info.stdout,
        info.stderr,
        detail=info.stdout[:60].strip(),
    )
    kwin = subprocess.run(
        ["gdbus", "introspect", "--session", "--dest", KWIN, "--object-path", "/KWin"],
        env=ENV,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).stdout
    report.check(
        "5 reconfigure is a method of /KWin and reloadConfig is a signal, not a method",
        bool(re.search(r"\breconfigure\(\)", kwin))
        and not re.search(r"^\s*(?!signal)\S*\s*reloadConfig\(\)", kwin, re.M | re.I)
        or "reloadConfig" in kwin,
        kwin[:300],
    )
    report.note(
        "reloadConfig in /KWin: "
        + ("a signal" if re.search(r"signal\s+org\.kde\.KWin\.reloadConfig", kwin) else "see below")
    )
    report.note("methods of /KWin: " + ", ".join(sorted(set(re.findall(r"(\w+)\(", kwin)))[:40]))
    loaded = d.gdbus(ENV, KWIN, "/Scripting", f"{SCRIPTING}.isScriptLoaded", "tesserae-shell-kwin")
    report.check(
        "6 isScriptLoaded answers (false: nothing is loaded yet)",
        loaded.stdout.strip() == "(false,)",
        loaded.stdout + loaded.stderr,
    )
    return int(report.code)


def ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, delimiters=("=",))
    parser.optionxform = str  # type: ignore[assignment,method-assign]
    if path.exists():
        parser.read(path)
    return parser


def commands() -> int:
    report = d.Report()
    config = Path(ENV["XDG_CONFIG_HOME"])
    rules = config / "kwinrulesrc"
    kwinrc = config / "kwinrc"
    shown = d.cli(BIN, ENV, "kwin", "rule", "show")
    for key in (
        "Description=",
        "layer=4",
        "layerrule=2",
        "wmclass=tesserae-shell.",
        "wmclasscomplete=false",
        "wmclassmatch=2",
    ):
        report.check(f"1 rule show prints {key}", key in shown.stdout, shown.stdout)
    for n in (1, 2):
        done = d.cli(BIN, ENV, "kwin", "rule", "install", "--yes")
        report.check(
            f"2 rule install --yes, time {n}: exit 0 and KWin asked to reload",
            done.returncode == 0 and "KWin was asked to reload" in done.stdout,
            done.stdout + done.stderr,
        )
    parser = ini(rules)
    groups = [s for s in parser.sections() if s != "General"]
    report.check(
        "3 a second install is still ONE group in kwinrulesrc",
        groups == ["tesserae-shell-surfaces"]
        and parser["General"]["count"] == "1"
        and parser["General"]["rules"] == "tesserae-shell-surfaces",
        f"groups {groups}, general {dict(parser['General']) if parser.has_section('General') else None}",
    )
    group = parser["tesserae-shell-surfaces"] if groups else {}
    report.check(
        "4 the group has the keys the spec lists",
        dict(group)
        == {
            "Description": "Tesserae Shell: surfaces above Plasma panels",
            "layer": "4",
            "layerrule": "2",
            "wmclass": "tesserae-shell.",
            "wmclasscomplete": "false",
            "wmclassmatch": "2",
        },
        f"{dict(group)}",
    )
    done = d.cli(BIN, ENV, "kwin", "rule", "remove")
    parser = ini(rules)
    report.check(
        "5 rule remove takes exactly that group out",
        done.returncode == 0
        and [s for s in parser.sections() if s != "General"] == []
        and parser["General"]["count"] == "0",
        done.stdout + done.stderr,
    )
    done = d.cli(BIN, ENV, "kwin", "script", "install")
    report.check("6 script install exits 0", done.returncode == 0, done.stdout + done.stderr)
    text = status()
    report.check(
        "7 status: the package is installed and enabled in kwinrc",
        "package: installed at" in text and "enabled in kwinrc" in text and ": yes" in text,
        text,
    )
    package = Path(ENV["XDG_DATA_HOME"]) / "kwin" / "scripts" / "tesserae-shell-kwin"
    report.check(
        "8 the package is the script KWin reads (metadata.json and contents/code/main.js)",
        (package / "metadata.json").is_file()
        and (package / "contents" / "code" / "main.js").is_file(),
        f"{sorted(p.name for p in package.glob('*'))}",
    )
    report.check(
        "9 kwinrc has the Plugins switch",
        ini(kwinrc).get("Plugins", "tesserae-shell-kwinEnabled", fallback="") == "true",
        kwinrc.read_text() if kwinrc.exists() else "no kwinrc",
    )
    loaded = re.search(r"loaded in KWin now: (\w+)", text)
    report.note(
        "after install and a reconfigure the private KWin says loaded: "
        + (loaded.group(1) if loaded else "?")
        + " (a login loads an enabled script; a reconfigure may not)"
    )
    done = d.cli(BIN, ENV, "kwin", "script", "remove")
    text = status()
    report.check(
        "10 script remove: not installed and the switch is gone",
        done.returncode == 0
        and "package: not installed" in text
        and not ini(kwinrc).has_option("Plugins", "tesserae-shell-kwinEnabled"),
        done.stdout + done.stderr + text,
    )
    return int(report.code)


LAYERS_JS = """\
var out = [];
workspace.windowList().forEach(function (w) {
    out.push([w.caption, w.windowClass, w.layer, w.dock, w.resourceName].join("|"));
});
print("KITLAYERS " + out.join(" ;; "));
"""


def layers(tag: str) -> dict[str, int]:
    """The layer of each window KWin lists, by title (the shell's layer surface has no title:
    ``bar``), read by a one-shot script that prints to KWin's log."""
    path = STEP_DIR / f"layers-{tag}.js"
    path.write_text(LAYERS_JS)
    log = SANDBOX / "kwin.log"
    before = log.stat().st_size
    d.gdbus(ENV, KWIN, "/Scripting", f"{SCRIPTING}.loadScript", str(path), f"kit-layers-{tag}")
    d.gdbus(ENV, KWIN, "/Scripting", f"{SCRIPTING}.start")
    deadline = time.monotonic() + 15
    seen = ""
    while time.monotonic() < deadline and "KITLAYERS" not in seen:
        with open(log, errors="replace") as handle:
            handle.seek(before)
            seen = handle.read()
        time.sleep(0.1)
    d.gdbus(ENV, KWIN, "/Scripting", f"{SCRIPTING}.unloadScript", f"kit-layers-{tag}")
    line = next((ln for ln in seen.splitlines() if "KITLAYERS" in ln), "")
    result: dict[str, int] = {}
    for entry in line.split("KITLAYERS ", 1)[-1].split(" ;; "):
        parts = entry.split("|")
        if len(parts) >= 3 and parts[2].lstrip("-").isdigit():
            result[parts[0] or "bar"] = int(parts[2])
    (STEP_DIR / f"layers-{tag}.txt").write_text(line + "\n")
    return result


def layer() -> int:
    report = d.Report()
    rules = Path(ENV["XDG_CONFIG_HOME"]) / "kwinrulesrc"

    def trial(tag: str) -> dict[str, int]:
        run = shell("cfg")
        probe = Probe("Kit Layer")
        try:
            wait_windows(run, lambda r: "Kit Layer" in titles(r))
            return layers(tag)
        finally:
            probe.stop()
            run.stop()

    base = trial("none")
    report.check(
        "1 without a rule: the shell's layer surface is on the dock layer, a window on the normal one",
        base.get("bar") is not None and base.get("Kit Layer") is not None,
        f"{base}",
        detail=f"{base}",
    )
    done = d.cli(BIN, ENV, "kwin", "rule", "install", "--yes")
    report.check("2 kwin rule install --yes", done.returncode == 0, done.stdout + done.stderr)
    own = trial("shell-rule")
    report.note(f"with the shell's own rule (wmclass tesserae-shell.): {own}")
    report.check(
        "3 the shell's own rule changes no layer: the class it matches is not the surface's",
        own == base,
        f"{own} against {base}",
    )
    # what does KWin call the layer surface's class? the one-shot script printed it
    text = (STEP_DIR / "layers-shell-rule.txt").read_text()
    report.note(f"what KWin lists (caption|class|layer|dock|resourceName): {text.strip()}")
    # a rule that DOES match both the surface and the client window (the process name), as the
    # control: the client window must move to the forced layer, and the surface tells the answer
    name = re.search(r"\|(python[\d.]*)", text)
    if name is None:
        report.fail("4 the process name KWin lists as the resource name", f"not found in {text!r}")
        return int(report.code)
    parser = ini(rules)
    parser["tesserae-shell-control"] = {
        "Description": "kit control: any window of this process",
        "layer": "4",
        "layerrule": "2",
        "wmclass": name.group(1),
        "wmclasscomplete": "false",
        "wmclassmatch": "2",
    }
    parser["General"]["rules"] = "tesserae-shell-surfaces,tesserae-shell-control"
    parser["General"]["count"] = "2"
    with open(rules, "w") as handle:
        parser.write(handle, space_around_delimiters=False)
    d.gdbus(ENV, KWIN, "/KWin", "org.kde.KWin.reconfigure")
    control = trial("control")
    report.note(f"with a rule that matches the process name: {control}")
    changed_window = control.get("Kit Layer") == 4 and base.get("Kit Layer") != 4
    report.check(
        "4 control: a matching rule forces a client window to layer 4 (the rule machinery works)",
        changed_window,
        f"{control} against {base}",
    )
    if changed_window:
        if control.get("bar") == 4 and base.get("bar") != 4:
            report.note(
                "ANSWER: the layer rule DOES apply to a layer-shell surface when its class matches; "
                "the shell's rule (wmclass tesserae-shell.) does not match what KWin lists as the "
                "surface's class (empty), so it changes nothing"
            )
        else:
            report.note(
                "ANSWER: the layer rule does NOT apply to a layer-shell surface: with a rule that "
                f"matches it and its client neighbour, the window went to 4 and the surface stayed "
                f"at {control.get('bar')}"
            )
    return int(report.code)


if __name__ == "__main__":
    which = sys.argv[1]
    raise SystemExit(
        {
            "script": script,
            "off": off,
            "introspect": introspect,
            "commands": commands,
            "layer": layer,
        }[which]()
    )
