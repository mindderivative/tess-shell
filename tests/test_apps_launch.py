"""Starting an application (Applications Module > Starting an Application): the ``Exec`` value, its
field codes, ``Terminal`` and ``Path``, the environment, the scope, and the runner that starts the
process. Every start here is the recorder of ``tests/launcher_rig.py``: nothing starts a process,
and the real runner is shown to refuse while a test runs."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from typing import Any

import pytest

from tess_shell.services.apps import (
    RECORD_VARIABLE,
    ExecError,
    LaunchError,
    SpawnRefused,
    StartSpec,
    SystemRunner,
    build_command,
    clean_environment,
    parse_exec,
    split_exec,
)
from tess_shell.services.desktop_entries import parse_entry
from tests.launcher_rig import FakeRunner, Loop, write_entry
from tests.test_apps import service, settle

FAKE_PATH = Path("/apps/org.example.Fake.desktop")


def entry(text: str, **keys: str) -> Any:
    """An entry whose ``Exec`` is ``text`` as it stands in the file."""
    lines = ["[Desktop Entry]", "Type=Application", "Name=Fake App", f"Exec={text}"]
    lines += [f"{k}={v}" for k, v in keys.items()]
    return parse_entry("\n".join(lines) + "\n", "org.example.Fake.desktop", FAKE_PATH)


def argv(text: str, **keys: str) -> list[str]:
    return parse_exec(entry(text, **keys))


# -- the Exec key --------------------------------------------------------------------------------


def test_exec_is_split_by_the_specifications_quoting_rules() -> None:
    assert argv("prog a b") == ["prog", "a", "b"]
    assert argv('env "FOO=bar baz" prog') == ["env", "FOO=bar baz", "prog"]
    assert argv('prog   "one  two"\tthree') == ["prog", "one  two", "three"]
    # inside double quotes a backslash makes " ` $ and \ literal; the file's own escape rule
    # (\\ is one backslash) comes first, so a literal backslash in a quoted argument takes four
    assert argv('prog "say \\\\"hi\\\\" \\\\$HOME \\\\\\\\ \\\\`x\\\\`"') == [
        "prog",
        'say "hi" $HOME \\ `x`',
    ]
    assert argv('prog ""') == ["prog", ""]  # an empty quoted argument is an argument
    assert split_exec('a "b c"') == [("a", False), ("b c", True)]
    with pytest.raises(ExecError, match="not closed"):
        argv('prog "unclosed')


def test_the_file_and_url_codes_are_removed_and_nothing_is_passed() -> None:
    assert argv("prog %f") == ["prog"]
    assert argv("prog %F") == ["prog"]
    assert argv("prog %u --flag %U") == ["prog", "--flag"]
    assert argv("prog --open=%f --after") == ["prog", "--open=", "--after"]  # the rest is kept
    assert argv("prog %d %D %n %N %v %m x") == ["prog", "x"]  # the deprecated codes
    assert argv("prog %z x") == ["prog", "x"]  # an unknown code is removed too


def test_the_icon_the_name_the_path_and_the_percent_codes() -> None:
    # %i is two arguments when the entry has an Icon, and nothing when it has none
    assert argv("prog %i x", Icon="fake-icon") == ["prog", "--icon", "fake-icon", "x"]
    assert argv("prog %i x") == ["prog", "x"]
    # %c is the (localised) name, %k the file's path, %% a percent sign
    assert argv("prog --name %c --file %k") == [
        "prog",
        "--name",
        "Fake App",
        "--file",
        str(FAKE_PATH),
    ]
    assert argv("prog 100%% --name=%c") == ["prog", "100%", "--name=Fake App"]
    assert argv('prog "%c and %%"') == ["prog", "Fake App and %"]


def test_a_missing_or_blank_exec_is_an_error_naming_the_entry(tmp_path: Path) -> None:
    for text in ("", "   ", "%f", "%U %F"):
        with pytest.raises(ExecError):
            parse_exec(entry(text))
    runner = FakeRunner()
    with pytest.raises(LaunchError, match="Fake App: the entry has no Exec"):
        build_command(entry(""), runner, {}, "/home/u", None, False)


# -- the command, the environment, the folder ----------------------------------------------------


def test_the_shells_own_variables_are_left_out_and_the_token_is_set_when_there_is_one() -> None:
    env = {
        "HOME": "/home/u",
        "PATH": "/usr/bin",
        "NOTIFY_SOCKET": "/run/systemd/notify",
        "LISTEN_FDS": "3",
        "INVOCATION_ID": "x",
        "JOURNAL_STREAM": "8:1",
        "WATCHDOG_USEC": "1",
        "TESS_SHELL_LAUNCH_RECORD": "/x",
        "XDG_ACTIVATION_TOKEN": "stale",
        "DESKTOP_STARTUP_ID": "stale",
        "WAYLAND_DISPLAY": "wayland-1",
    }
    assert clean_environment(env) == {
        "HOME": "/home/u",
        "PATH": "/usr/bin",
        "WAYLAND_DISPLAY": "wayland-1",
    }
    runner = FakeRunner()
    with_token = build_command(entry("fake-app"), runner, env, "/home/u", "tok-1", False)
    assert with_token.env["XDG_ACTIVATION_TOKEN"] == "tok-1"
    assert "NOTIFY_SOCKET" not in with_token.env
    without = build_command(entry("fake-app"), runner, env, "/home/u", None, False)
    assert "XDG_ACTIVATION_TOKEN" not in without.env  # a stale token never reaches the program


def test_the_working_folder_is_path_when_it_is_a_folder_else_the_users_home(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    work = tmp_path / "work"
    work.mkdir()
    home = str(tmp_path / "home")
    assert build_command(
        entry("fake-app", Path=str(work)), runner, {}, home, None, False
    ).cwd == str(work)
    assert build_command(entry("fake-app"), runner, {}, home, None, False).cwd == home
    missing = str(tmp_path / "missing")
    assert build_command(entry("fake-app", Path=missing), runner, {}, home, None, False).cwd == home


def test_terminal_true_runs_through_xdg_terminal_exec_or_nothing_starts() -> None:
    runner = FakeRunner()
    spec = build_command(entry("fake-app --tui", Terminal="true"), runner, {}, "/h", None, False)
    assert spec.argv == ("xdg-terminal-exec", "fake-app", "--tui")
    runner.programs.discard("xdg-terminal-exec")
    with pytest.raises(LaunchError, match="Fake App needs a terminal: xdg-terminal-exec"):
        build_command(entry("fake-app", Terminal="true"), runner, {}, "/h", None, False)


def test_a_program_that_is_missing_is_an_error_naming_it(tmp_path: Path) -> None:
    runner = FakeRunner()
    with pytest.raises(LaunchError, match="Fake App: no-such-program is not on the path"):
        build_command(entry("no-such-program %U"), runner, {}, "/h", None, False)
    plain = tmp_path / "plain-file"
    plain.write_text("x")
    with pytest.raises(LaunchError, match="is not an executable file"):
        build_command(entry(str(plain)), runner, {}, "/h", None, False)
    plain.chmod(plain.stat().st_mode | stat.S_IXUSR)
    spec = build_command(entry(str(plain)), runner, {}, "/h", None, False)
    assert spec.argv == (str(plain),)  # an absolute path is not looked up on the path


def test_a_scope_puts_systemd_run_in_front_with_a_unit_named_for_the_application() -> None:
    runner = FakeRunner()
    spec = build_command(entry("fake-app %U"), runner, {}, "/h", None, True)
    assert spec.argv[:5] == ("systemd-run", "--user", "--scope", "--quiet", "--collect")
    assert spec.argv[-2:] == ("--", "fake-app")
    assert spec.scope is not None and spec.scope.startswith("app-org.example.Fake-")
    assert spec.scope.endswith(".scope") and f"--unit={spec.scope}" in spec.argv
    assert "--description=Fake App" in spec.argv
    other = build_command(entry("fake-app"), runner, {}, "/h", None, True)
    assert other.scope != spec.scope  # a random part: two starts never share a unit
    plain = build_command(entry("fake-app"), runner, {}, "/h", None, False)
    assert plain.scope is None and plain.argv == ("fake-app",)


# -- the service: which branch ---------------------------------------------------------------------


def make_apps(tmp_path: Path, runner: FakeRunner, **entries: dict[str, str]) -> Any:
    folder = tmp_path / "applications"
    for name, keys in entries.items():
        write_entry(folder, name, **keys)
    return service([folder], runner=runner)


def launched(apps: Any, loop: Loop, app: str, token: str | None = None) -> Any:
    done: list[Any] = []
    apps.launch(app, token, done.append)
    assert settle(loop, lambda: done)
    return done[0]


def test_systemd_run_is_used_when_it_is_there_and_a_plain_start_when_it_is_not(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(scope=True)
    with make_apps(tmp_path, runner, App={"Exec": "fake-app %U"}) as (apps, loop, _r):
        assert launched(apps, loop, "app.desktop", "tok").ok
        scoped = runner.started[-1]
        assert scoped.argv[0] == "systemd-run" and scoped.scope is not None
        assert scoped.env["XDG_ACTIVATION_TOKEN"] == "tok"
        runner.scope = False
        assert launched(apps, loop, "app.desktop").ok
        plain = runner.started[-1]
        assert plain.argv == ("fake-app",) and plain.scope is None
        assert "XDG_ACTIVATION_TOKEN" not in plain.env  # None: it starts without a token


def test_systemd_run_that_fails_falls_back_to_a_plain_start(tmp_path: Path) -> None:
    from loguru import logger

    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(str(m)), level="DEBUG")
    runner = FakeRunner(scope=True, fail_scope=True)
    try:
        with make_apps(tmp_path, runner, App={"Exec": "fake-app"}) as (apps, loop, _r):
            assert launched(apps, loop, "app.desktop").ok
    finally:
        logger.remove(sink)
    assert [s.scope for s in runner.started] == [None]  # only the plain start was made
    assert any("systemd-run failed" in line and "a plain start instead" in line for line in seen)


def test_a_failed_start_is_reported_counts_nothing_and_the_next_start_still_works(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(scope=False, fail_plain=True)
    entries = {
        "Broken": {"Exec": "fake-app"},
        "No Exec": {},
        "Missing Program": {"Exec": "no-such-program"},
        "Terminal App": {"Exec": "fake-app", "Terminal": "true"},
    }
    runner.programs.discard("xdg-terminal-exec")
    with make_apps(tmp_path, runner, **entries) as (apps, loop, _r):
        for app, why in (
            ("broken.desktop", "cannot start"),
            ("no-exec.desktop", "the entry has no Exec"),
            ("missing-program.desktop", "no-such-program is not on the path"),
            ("terminal-app.desktop", "xdg-terminal-exec is not on the path"),
        ):
            result = launched(apps, loop, app)
            assert not result.ok and why in result.error, result
        assert runner.started == [] and apps.count("broken.desktop") == 0
        gone = launched(apps, loop, "nothing.desktop")
        assert not gone.ok and "no application nothing.desktop" in gone.error
        runner.fail_plain = False
        assert launched(apps, loop, "broken.desktop").ok
        assert apps.count("broken.desktop") == 1 and len(runner.started) == 1


def test_a_start_after_the_service_stopped_says_so(tmp_path: Path) -> None:
    runner = FakeRunner()
    with make_apps(tmp_path, runner, App={"Exec": "fake-app"}) as (apps, loop, _r):
        apps.stop()
        result = launched(apps, loop, "app.desktop")
        assert not result.ok and "not running" in result.error and runner.started == []


# -- the real runner -------------------------------------------------------------------------------


def spec(tmp_path: Path) -> StartSpec:
    return StartSpec(
        ("never-started", "--x"), {"XDG_ACTIVATION_TOKEN": "t", "A": "b"}, str(tmp_path)
    )


def test_the_real_runner_refuses_while_a_test_runs_unless_a_recorder_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert os.environ.get("PYTEST_CURRENT_TEST")  # this very test
    monkeypatch.delenv(RECORD_VARIABLE, raising=False)
    runner = SystemRunner({"PATH": "/usr/bin:/bin"})
    with pytest.raises(SpawnRefused, match="never-started"):
        runner.spawn(spec(tmp_path))
    record = tmp_path / "record.jsonl"
    monkeypatch.setenv(RECORD_VARIABLE, str(record))
    runner.spawn(spec(tmp_path))  # recorded, not started
    (line,) = record.read_text().splitlines()
    assert json.loads(line) == {
        "argv": ["never-started", "--x"],
        "cwd": str(tmp_path),
        "scope": None,
        "token": "t",
        "env": {"XDG_ACTIVATION_TOKEN": "t", "A": "b"},
    }


def test_the_real_runner_asks_only_whether_systemd_run_is_there_while_a_test_runs(
    tmp_path: Path,
) -> None:
    """No probe (it would start a process): the presence of the program is the answer."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    runner = SystemRunner({"PATH": str(bin_dir)})
    assert runner.scope_available() is False and runner.which("systemd-run") is None
    tool = bin_dir / "systemd-run"
    tool.write_text("#!/bin/sh\nexit 1\n")
    tool.chmod(0o755)
    started = time.monotonic()
    assert runner.scope_available() is True  # present: not run
    assert time.monotonic() - started < 1
    assert runner.which("systemd-run") == str(tool)
