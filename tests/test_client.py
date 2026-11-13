"""The control commands as a client of the interface (IPC and CLI > The Command Line, Exit Codes of
the Client): output, exit codes, and the cost of a command (imports, end-to-end time)."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tess_shell import client
from tess_shell.exit_codes import ExitCode
from tess_shell.options import Options
from tests.fake_dbus import HAVE_DAEMON, fake_bus
from tests.test_control import rig

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

# what a command from a keyboard shortcut must never pull in
HEAVY = ("tess_re", "loguru", "tess_dl", "tess_el", "dbus_fast", "jsonschema")


def env_for(address: str | None, tmp: Path) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp), "XDG_RUNTIME_DIR": str(tmp)}
    if address is not None:
        env["DBUS_SESSION_BUS_ADDRESS"] = address
    return env


def tesserae(
    address: str | None, tmp: Path, *argv: str, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tess_shell", *argv],
        env=env_for(address, tmp),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_every_command_reaches_the_shell_and_prints_its_answer(tmp_path: Path) -> None:
    with rig() as r:
        a = r.bus.address
        assert tesserae(a, tmp_path, "reload").stdout.strip() == "reloaded ticket"
        out = tesserae(a, tmp_path, "toggle", "Launcher")
        assert (out.returncode, out.stdout.strip()) == (0, "Launcher Toggle")
        assert tesserae(a, tmp_path, "show", "Launcher").stdout.strip() == "Launcher Show"
        assert tesserae(a, tmp_path, "hide", "Launcher").stdout.strip() == "Launcher Hide"
        assert tesserae(a, tmp_path, "log-level", "debug").returncode == 0
        quiet = tesserae(a, tmp_path, "quit")
        assert (quiet.returncode, quiet.stdout.strip()) == (0, "stopping")
        assert r.commands.stopped == 1


def test_a_refused_command_exits_1_with_the_reason_on_standard_error(tmp_path: Path) -> None:
    with rig() as r:
        out = tesserae(r.bus.address, tmp_path, "show", "Nope")
        assert out.returncode == 1
        assert out.stderr.strip() == "no surface named Nope" and out.stdout == ""
        as_json = tesserae(r.bus.address, tmp_path, "--json", "show", "Nope")
        assert as_json.returncode == 1
        assert json.loads(as_json.stdout) == {"ok": False, "message": "no surface named Nope"}


def test_call_arguments_are_json_values_or_plain_text(tmp_path: Path) -> None:
    with rig() as r:
        out = tesserae(
            r.bus.address, tmp_path, "call", "Mod", "act", "5", '{"a": [1]}', "plain", "true"
        )
        assert out.returncode == 0
        assert json.loads(out.stdout) == {
            "module": "Mod",
            "action": "act",
            "values": [5, {"a": [1]}, "plain", True],
        }
        as_json = tesserae(r.bus.address, tmp_path, "--json", "call", "Mod", "act")
        assert json.loads(as_json.stdout)["result"]["values"] == []
        failed = tesserae(r.bus.address, tmp_path, "call", "Boom", "go")
        assert (
            failed.returncode == 1 and failed.stderr.strip() == "tesserae-shell: Boom.go: it failed"
        )


def test_status_prints_a_summary_and_with_json_the_shells_own_text(tmp_path: Path) -> None:
    with rig() as r:
        text = tesserae(r.bus.address, tmp_path, "status")
        assert text.returncode == 0 and text.stdout.startswith("state: running\n")
        data = tesserae(r.bus.address, tmp_path, "status", "--json")
        assert json.loads(data.stdout)["state"] == "running"


def test_no_shell_is_exit_3_with_one_line_and_a_json_object(tmp_path: Path) -> None:
    with fake_bus() as bus:  # a bus with nobody on the name
        out = tesserae(bus.address, tmp_path, "status")
        assert out.returncode == 3
        assert out.stdout == ""
        assert (
            out.stderr.strip() == "tesserae-shell: no shell is running (nobody owns the bus name)"
        )
        as_json = tesserae(bus.address, tmp_path, "--json", "status")
        assert as_json.returncode == 3
        data = json.loads(as_json.stdout)
        assert data["ok"] is False and data["exit"] == 3 and "no shell is running" in data["error"]
        for command in ("reload", "quit", "toggle X", "call M A", "log-level info"):
            assert tesserae(bus.address, tmp_path, *command.split()).returncode == 3, command


def test_no_session_bus_is_exit_2_and_names_the_variable(tmp_path: Path) -> None:
    out = tesserae(None, tmp_path, "status")
    assert out.returncode == 2
    assert "DBUS_SESSION_BUS_ADDRESS" in out.stderr
    unreachable = tesserae(f"unix:path={tmp_path}/none", tmp_path, "status")
    assert unreachable.returncode == 2 and "session bus" in unreachable.stderr


def test_a_loop_that_does_not_answer_is_exit_5(tmp_path: Path) -> None:
    with rig(loop_timeout=30) as r:
        r.loop.stuck.set()  # the shell's loop never runs the command
        started = time.monotonic()
        out = tesserae(r.bus.address, tmp_path, "--timeout", "0.5", "status")
        assert out.returncode == 5
        assert 0.4 < time.monotonic() - started < 10
        assert "did not answer within 0.5 s" in out.stderr


def test_a_shell_without_the_method_is_named_older(monkeypatch: pytest.MonkeyPatch) -> None:
    with rig() as r:
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", r.bus.address)
        shell = client.Shell(5.0)
        try:
            with pytest.raises(client.Failure) as info:
                shell.call("FullscreenState")  # the shell does not have it
        finally:
            shell.close()
    assert info.value.code == ExitCode.CONFIG
    assert (
        "version 9.9.9" in info.value.message
        and "does not know 'FullscreenState'" in info.value.message
    )


def test_the_exit_codes_are_the_documented_ones() -> None:
    assert [int(c) for c in (ExitCode.OK, ExitCode.CONFIG, ExitCode.ENVIRONMENT)] == [0, 1, 2]
    assert (ExitCode.NOT_RUNNING, ExitCode.ALREADY_RUNNING, ExitCode.TIMEOUT) == (3, 4, 5)


def test_an_argument_is_json_when_it_parses_else_text() -> None:
    assert client.parse_argument("5") == 5
    assert client.parse_argument('"x"') == "x"
    assert client.parse_argument("[1,2]") == [1, 2]
    assert client.parse_argument("null") is None
    assert client.parse_argument("hello world") == "hello world"
    assert client.parse_argument("{broken") == "{broken"


def test_the_timeout_option_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float] = []

    def fake(command: str, args: object, options: Options) -> int:
        seen.append(options.timeout)
        return 0

    monkeypatch.setattr(client, "run", fake)
    from tess_shell.cli import main

    assert main(["toggle", "X"]) == 0
    assert main(["--timeout", "1.5", "toggle", "X"]) == 0
    assert main(["toggle", "X", "--timeout", "2.5"]) == 0
    assert seen == [5.0, 1.5, 2.5]


IMPORTS = """
import json, sys
from tess_shell.cli import main
code = main(sys.argv[1:])
print(json.dumps({"code": code, "modules": sorted(sys.modules)}), file=sys.stderr)
"""


def test_the_reload_path_imports_neither_the_engine_nor_the_parsers(tmp_path: Path) -> None:
    with rig() as r:
        out = subprocess.run(
            [sys.executable, "-c", IMPORTS, "reload"],
            env=env_for(r.bus.address, tmp_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
    assert out.returncode == 0, out.stderr
    report = json.loads(out.stderr.strip().splitlines()[-1])
    assert report["code"] == 0
    modules = report["modules"]
    top = {m.split(".")[0] for m in modules}
    assert not [h for h in HEAVY if h in top], [h for h in HEAVY if h in top]
    ours = sorted(m for m in modules if m.startswith("tess_shell"))
    print("\nimported by `tesserae-shell reload`:", ", ".join(ours))
    print("third party:", ", ".join(sorted(m for m in top if m == "jeepney")))
    assert "jeepney" in top


def test_a_toggle_takes_well_under_a_hundred_milliseconds_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """From the process start to its exit, against a shell that answers at once (the part that is
    the client's: Python's start, the imports, one bus call). The target is under 100 ms."""
    with rig() as r:
        env = env_for(r.bus.address, tmp_path)
        argv = [sys.executable, "-m", "tess_shell", "toggle", "Launcher"]
        subprocess.run(argv, env=env, capture_output=True, check=True)  # warm the page cache
        times: list[float] = []
        for _ in range(15):
            started = time.perf_counter()
            done = subprocess.run(argv, env=env, capture_output=True)
            times.append(time.perf_counter() - started)
            assert done.returncode == 0
        bare = []
        for _ in range(5):
            started = time.perf_counter()
            subprocess.run([sys.executable, "-c", "pass"], env=env, capture_output=True)
            bare.append(time.perf_counter() - started)
    times.sort()
    median, worst = statistics.median(times), times[-1]
    with capsys.disabled():
        print(
            f"\ntoggle end to end: median {median * 1e3:.0f} ms, min {times[0] * 1e3:.0f} ms, "
            f"max {worst * 1e3:.0f} ms over {len(times)} runs "
            f"(a bare `python -c pass`: median {statistics.median(bare) * 1e3:.0f} ms)"
        )
    assert median < 0.1
