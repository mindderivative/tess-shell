"""``tesserae-shell install-session`` (Packaging and Session Start): the desktop file and the
systemd user unit, written to TEMPORARY folders only.

The acceptance criteria of the note map to these tests:

1. ``--print`` shows both files with the absolute command: ``test_print_*``.
2. two files in the two XDG folders and nothing elsewhere, ``--remove`` removes exactly those:
   ``test_the_command_writes_exactly_two_files_and_remove_takes_exactly_those_away``.
3. a differing file is kept without ``--force``: ``test_a_differing_file_is_kept_*``.
4. the unit passes ``systemd-analyze --user verify`` (a read-only check, on a copy):
   ``test_the_unit_passes_systemd_analyze_verify*``.
5. the desktop file passes ``desktop-file-validate``: ``test_the_desktop_file_passes_*``.
6. no test calls ``systemctl`` or writes outside its temporary folder: every action here takes
   ``Targets`` in a temporary folder and a recording runner; the guards that make that so are tested
   by ``test_the_guard_*`` and ``test_the_real_runner_*``.

Nothing here runs the real ``systemctl``: the runner is a recording fake, and the real one refuses
while a test runs.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from tess_shell import cli, notify, session
from tess_shell.session import (
    DESKTOP_NAME,
    UNIT_NAME,
    Ran,
    Refused,
    Targets,
    desktop_quote,
    systemd_quote,
    systemd_split,
)
from tests.fake_dbus import HAVE_DAEMON
from tests.test_client import env_for
from tests.test_client import tesserae as client_tesserae
from tests.test_control import rig as control_rig

REPO = Path(__file__).resolve().parent.parent


# -- rigs -------------------------------------------------------------------------------------


def make_command(folder: Path) -> str:
    """An executable ``tesserae-shell`` script in ``folder`` (the command the files start)."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "tesserae-shell"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    return str(script)


def targets_in(root: Path) -> Targets:
    return Targets(root / "data" / "applications", root / "config" / "systemd" / "user")


class Systemctl:
    """A runner that records what would run and acts the way ``systemctl --user`` does for the
    symlink of ``WantedBy=``; a verb in ``fail`` returns a failure."""

    def __init__(self, targets: Targets, fail: Sequence[str] = ()) -> None:
        self.targets = targets
        self.fail = set(fail)
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> Ran:
        self.calls.append(list(argv))
        verb = argv[2]
        if verb in self.fail:
            return Ran(1, "Failed to connect to bus: No medium found")
        link = self.targets.wants_link
        if verb == "enable":
            link.parent.mkdir(parents=True, exist_ok=True)
            if not link.is_symlink():
                link.symlink_to(self.targets.unit_file)
        elif verb == "disable":
            link.unlink(missing_ok=True)
        return Ran(0, "")


def files_under(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if not p.is_dir())


def run(capsys: pytest.CaptureFixture[str], *flags: str, **kwargs: object) -> tuple[int, str, str]:
    code = cli.main(["install-session", *flags], **kwargs)  # type: ignore[arg-type]
    out = capsys.readouterr()
    return code, out.out, out.err


class Rig:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.targets = targets_in(root)
        self.command = make_command(root / "bin")
        self.runner = Systemctl(self.targets)

    def call(self, **kwargs: object) -> int:
        """``install-session`` through the library entry (the CLI reads the real XDG folders, so
        its tests go through a subprocess with a temporary environment)."""
        base: dict[str, object] = {
            "targets": self.targets,
            "runner": self.runner,
            "command": [self.command],
        }
        return session.run_command(**{**base, **kwargs})  # type: ignore[arg-type]


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def temporary_env(root: Path) -> dict[str, str]:
    """An environment that sends every home and XDG folder of a child process into ``root``."""
    home = root / "home"
    runtime = root / "run"
    runtime.mkdir(mode=0o700, exist_ok=True)
    home.mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_CACHE_HOME": str(root / "cache"),
    }


def tesserae(
    env: dict[str, str], *argv: str, extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tess_shell", *argv],
        env={**env, **(extra or {})},
        capture_output=True,
        text=True,
        timeout=60,
    )


# -- the command: print, install, differing files, remove -------------------------------------


def test_print_shows_both_files_with_the_absolute_command_and_writes_nothing(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.call(print_only=True) == 0
    out = capsys.readouterr().out
    assert str(rig.targets.desktop_file) in out and str(rig.targets.unit_file) in out
    assert f"Exec={rig.command} run\n" in out
    assert f"ExecStart={rig.command} run\n" in out
    assert "Type=notify" in out and "[Desktop Entry]" in out
    assert not rig.root.joinpath("data").exists() and not rig.root.joinpath("config").exists()
    assert rig.runner.calls == []


def test_print_through_the_command_line_names_the_command_that_ran_it(tmp_path: Path) -> None:
    env = temporary_env(tmp_path)
    done = tesserae(env, "install-session", "--print", "--json")
    assert done.returncode == 0, done.stderr
    data = json.loads(done.stdout)
    start = data["exec_start"]
    assert os.path.isabs(start[0]) and os.access(start[0], os.X_OK) and start[-1] == "run"
    unit = next(f for f in data["files"] if f["kind"] == "unit")
    desktop = next(f for f in data["files"] if f["kind"] == "desktop")
    assert unit["path"] == str(tmp_path / "config" / "systemd" / "user" / UNIT_NAME)
    assert desktop["path"] == str(tmp_path / "data" / "applications" / DESKTOP_NAME)
    assert f"ExecStart={start[0]} run\n" in unit["content"]
    assert files_under(tmp_path) == []  # nothing written, not even a folder's file


def test_the_command_writes_exactly_two_files_and_remove_takes_exactly_those_away(
    tmp_path: Path,
) -> None:
    env = temporary_env(tmp_path)
    before = files_under(tmp_path)
    done = tesserae(env, "install-session")
    assert done.returncode == 0, done.stderr
    assert files_under(tmp_path) == sorted(
        [f"config/systemd/user/{UNIT_NAME}", f"data/applications/{DESKTOP_NAME}"]
    )
    assert before == [] and "not enabled" in done.stdout
    # an unrelated file of the same folders is left alone by --remove
    keep = tmp_path / "config" / "tesserae-shell" / "settings.tdl"
    keep.parent.mkdir(parents=True)
    keep.write_text("mine")
    gone = tesserae(env, "install-session", "--remove")  # not enabled: no systemctl at all
    assert gone.returncode == 0, gone.stderr
    assert files_under(tmp_path) == ["config/tesserae-shell/settings.tdl"]
    assert keep.read_text() == "mine"


def test_the_files_are_written_through_a_temporary_name_that_does_not_stay(rig: Rig) -> None:
    assert rig.call() == 0
    names = files_under(rig.root)
    assert not [n for n in names if n.endswith(".tmp") or "/." in n]
    # readable by the user manager and by the desktop
    assert rig.targets.unit_file.stat().st_mode & 0o777 == 0o644
    assert rig.targets.desktop_file.stat().st_mode & 0o777 == 0o644


def test_a_differing_file_is_kept_without_force_and_nothing_else_changes(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.targets.unit_file.parent.mkdir(parents=True)
    rig.targets.unit_file.write_text("[Service]\nExecStart=/mine\n")
    assert rig.call() == 1
    err = capsys.readouterr().err
    assert str(rig.targets.unit_file) in err and "--force" in err
    assert rig.targets.unit_file.read_text() == "[Service]\nExecStart=/mine\n"
    assert not rig.targets.desktop_file.exists()  # nothing was written, the desktop file neither


def test_force_replaces_a_differing_file(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    rig.targets.desktop_file.parent.mkdir(parents=True)
    rig.targets.desktop_file.write_text("old")
    assert rig.call(force=True) == 0
    out = capsys.readouterr().out
    assert f"replaced {rig.targets.desktop_file}" in out
    assert f"written {rig.targets.unit_file}" in out
    assert "Exec=" in rig.targets.desktop_file.read_text()


def test_install_twice_changes_nothing_the_second_time(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.call() == 0
    first = {p: p.stat().st_mtime_ns for p in (rig.targets.unit_file, rig.targets.desktop_file)}
    capsys.readouterr()
    assert rig.call() == 0  # the same content: no --force needed
    out = capsys.readouterr().out
    assert out.count("unchanged ") == 2
    assert first == {p: p.stat().st_mtime_ns for p in first}


def test_enable_runs_systemctl_enable_and_twice_is_the_same(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.call(enable=True) == 0
    assert rig.runner.calls == [["systemctl", "--user", "enable", UNIT_NAME]]
    assert "enabled " in capsys.readouterr().out
    assert rig.call(enable=True) == 0
    assert rig.runner.calls[-1] == ["systemctl", "--user", "enable", UNIT_NAME]
    assert len(rig.runner.calls) == 2  # nothing else: no start, no daemon-reload
    assert rig.targets.enabled


def test_a_plain_install_never_touches_systemd(rig: Rig) -> None:
    assert rig.call() == 0
    assert rig.runner.calls == []
    assert not rig.targets.enabled


def test_enable_without_a_working_user_session_still_writes_both_files(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.runner.fail.add("enable")
    assert rig.call(enable=True) == 2
    out = capsys.readouterr()
    assert rig.targets.unit_file.exists() and rig.targets.desktop_file.exists()
    assert str(rig.targets.unit_file) in out.out  # the paths written are still printed
    assert "cannot be enabled" in out.err and "Failed to connect to bus" in out.err


def test_remove_disables_an_enabled_unit_then_removes_both_files(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.call(enable=True) == 0
    rig.runner.calls.clear()
    capsys.readouterr()
    assert rig.call(remove_files=True) == 0
    assert rig.runner.calls == [
        ["systemctl", "--user", "disable", UNIT_NAME],
        ["systemctl", "--user", "daemon-reload"],
    ]
    assert not rig.targets.unit_file.exists() and not rig.targets.desktop_file.exists()
    assert not rig.targets.enabled
    out = capsys.readouterr().out
    assert (
        f"removed {rig.targets.unit_file}" in out and f"removed {rig.targets.desktop_file}" in out
    )


def test_remove_when_nothing_is_installed_is_not_an_error_and_runs_nothing(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.call(remove_files=True) == 0
    assert rig.call(remove_files=True) == 0
    assert capsys.readouterr().out.count("absent ") == 4
    assert rig.runner.calls == []


def test_a_failed_disable_removes_nothing(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    assert rig.call(enable=True) == 0
    capsys.readouterr()
    rig.runner.fail.add("disable")
    assert rig.call(remove_files=True) == 2
    assert "nothing was removed" in capsys.readouterr().err
    assert rig.targets.unit_file.exists() and rig.targets.desktop_file.exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write into a read-only folder")
def test_a_folder_that_cannot_be_written_names_the_path_and_leaves_nothing_half_written(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.targets.units.mkdir(parents=True)
    rig.targets.units.chmod(0o500)
    try:
        assert rig.call() == 1
    finally:
        rig.targets.units.chmod(0o700)
    err = capsys.readouterr().err
    assert str(rig.targets.unit_file) in err
    # not the desktop file, not a temporary file (only the fake command of the rig is there)
    assert files_under(rig.root) == ["bin/tesserae-shell"]


def test_the_exclusive_flags_are_refused_together(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        cli.main(["install-session", "--enable", "--remove"])
    assert exit_.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_a_config_dir_is_carried_into_the_command_the_files_start(
    rig: Rig, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    cfg = tmp_path / "my config"
    assert rig.call(print_only=True, config_dir=cfg) == 0
    out = capsys.readouterr().out
    assert f'ExecStart={rig.command} run --config-dir "{cfg}"\n' in out


# -- the output shape ---------------------------------------------------------------------------


def test_json_shapes(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    assert rig.call(print_only=True, json_out=True) == 0
    shown = json.loads(capsys.readouterr().out)
    assert set(shown) == {"ok", "action", "files", "enabled", "exec_start", "notes"}
    assert (shown["ok"], shown["action"], shown["enabled"]) == (True, "print", False)
    assert [set(f) for f in shown["files"]] == [{"kind", "path", "state", "content"}] * 2
    assert [f["state"] for f in shown["files"]] == ["absent", "absent"]

    assert rig.call(json_out=True) == 0
    written = json.loads(capsys.readouterr().out)
    assert written["action"] == "install"
    assert [(f["kind"], f["result"]) for f in written["files"]] == [
        ("desktop", "written"),
        ("unit", "written"),
    ]
    assert rig.call(print_only=True, json_out=True) == 0
    assert [f["state"] for f in json.loads(capsys.readouterr().out)["files"]] == ["same", "same"]

    assert rig.call(remove_files=True, json_out=True) == 0
    removed = json.loads(capsys.readouterr().out)
    assert removed["action"] == "remove"
    assert [(f["kind"], f["result"]) for f in removed["files"]] == [
        ("unit", "removed"),
        ("desktop", "removed"),
    ]


def test_json_errors_are_the_object_of_the_other_commands(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.targets.unit_file.parent.mkdir(parents=True)
    rig.targets.unit_file.write_text("mine")
    assert rig.call(json_out=True) == 1
    error = json.loads(capsys.readouterr().out)
    assert (error["ok"], error["exit"]) == (False, 1)
    assert str(rig.targets.unit_file) in error["error"]
    assert error["conflicts"] == [str(rig.targets.unit_file)]

    rig.runner.fail.add("enable")
    assert rig.call(json_out=True, force=True, enable=True) == 2
    failed = json.loads(capsys.readouterr().out)
    assert (failed["ok"], failed["exit"]) == (False, 2)
    assert [f["result"] for f in failed["files"]] == ["written", "replaced"]


# -- the guards ---------------------------------------------------------------------------------


def test_the_guard_refuses_the_real_folders_under_a_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``real_homes`` is pointed at a folder of the test, so a broken guard would write there and
    not into the maintainer's home."""
    home = tmp_path / "pretend-real-home"
    monkeypatch.setattr(session, "real_homes", lambda: {home})
    real = Targets(home / ".local/share/applications", home / ".config/systemd/user")
    runner = Systemctl(real)
    command = make_command(tmp_path / "bin")
    for what in ({}, {"remove_files": True}, {"enable": True}):
        code = session.run_command(targets=real, runner=runner, command=[command], **what)  # type: ignore[arg-type]
        assert code == 2
        assert "a test may not touch" in capsys.readouterr().err
    assert not home.exists() and runner.calls == []
    with pytest.raises(Refused):
        session.guard(home / ".config" / "systemd" / "user" / UNIT_NAME)
    with pytest.raises(Refused):
        session.guard(home / ".local" / "share" / "applications")
    session.guard(home / ".config" / "tesserae-shell")  # not a folder the command writes


def test_the_guard_follows_a_link_into_the_real_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "pretend-real-home"
    (home / ".config" / "systemd" / "user").mkdir(parents=True)
    monkeypatch.setattr(session, "real_homes", lambda: {home})
    link = tmp_path / "innocent"
    link.symlink_to(home / ".config" / "systemd" / "user")
    with pytest.raises(Refused):
        session.guard(link / UNIT_NAME)


def test_the_guard_does_nothing_outside_a_test(tmp_path: Path) -> None:
    session.guard(Path.home() / ".config" / "systemd" / "user", environ={})


def test_the_real_runner_refuses_while_a_test_runs() -> None:
    assert "PYTEST_CURRENT_TEST" in os.environ
    with pytest.raises(Refused):
        session.systemctl_runner(["systemctl", "--user", "enable", UNIT_NAME])


def test_enable_with_no_runner_is_refused_under_a_test_after_the_files_are_written(
    tmp_path: Path,
) -> None:
    """The command line of a test has no hook for the runner: ``--enable`` must not reach the real
    ``systemctl``. The files go to the temporary folders; the enable is refused."""
    env = temporary_env(tmp_path)
    done = tesserae(env, "install-session", "--enable", extra={"PYTEST_CURRENT_TEST": "x (call)"})
    assert done.returncode == 2 and "a test may not run systemctl" in done.stderr
    assert files_under(tmp_path) == [
        f"config/systemd/user/{UNIT_NAME}",
        f"data/applications/{DESKTOP_NAME}",
    ]


def test_without_xdg_variables_the_files_go_under_home(tmp_path: Path) -> None:
    """A child with no XDG variables falls back to ``$HOME``: here a temporary one, so it is
    fine; with the real one in a test, the guard says no (read from the password database, so a
    changed ``$HOME`` does not hide it)."""
    env = temporary_env(tmp_path)
    env.pop("XDG_CONFIG_HOME")
    env.pop("XDG_DATA_HOME")
    done = tesserae(env, "install-session", extra={"PYTEST_CURRENT_TEST": "x (call)"})
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "home" / ".config" / "systemd" / "user" / UNIT_NAME).is_file()


# -- the command that is written ----------------------------------------------------------------


def test_the_command_is_the_script_that_ran_else_the_one_beside_the_interpreter(
    tmp_path: Path,
) -> None:
    script = make_command(tmp_path / "tool" / "bin")
    link = tmp_path / "local" / "tesserae-shell"
    link.parent.mkdir()
    link.symlink_to(script)
    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("")
    other = make_command(python.parent)
    # run by its link: the link is kept (it survives an upgrade of the tool environment)
    assert session.current_command(str(link), str(python)) == [str(link)]
    # `python -m tess_shell` in a virtual environment: the script beside the interpreter
    assert session.current_command("/x/tess_shell/__main__.py", str(python)) == [other]
    # a relative argv[0] is made absolute
    old = os.getcwd()
    os.chdir(tmp_path / "tool")
    try:
        assert session.current_command("bin/tesserae-shell", str(python)) == [script]
    finally:
        os.chdir(old)
    # no script anywhere: the interpreter and the module
    bare = tmp_path / "bare" / "python"
    bare.parent.mkdir()
    bare.write_text("")
    assert session.current_command("-c", str(bare)) == [str(bare), "-m", "tess_shell"]


@pytest.mark.parametrize(
    "arg",
    [
        "/plain/path/tesserae-shell",
        "/with space/a b/tesserae-shell",
        "/quote\"s/it's/tesserae-shell",
        "/percent%h/dollar$HOME/${x}/tesserae-shell",
        "/back\\slash/tesserae-shell",
        "/ünïcode/ταίρι/tesserae-shell",
        "",
    ],
)
def test_a_word_survives_the_unit_quoting(arg: str) -> None:
    # the first word is the program, which systemd takes as it stands; the others are arguments
    line = " ".join([systemd_quote(arg, executable=True), "run", systemd_quote(arg)])
    assert systemd_split(line) == [arg, "run", arg]


def test_the_desktop_quoting_follows_the_specification() -> None:
    assert desktop_quote("/usr/bin/tesserae-shell") == "/usr/bin/tesserae-shell"
    assert desktop_quote("/a b/c") == '"/a b/c"'
    assert desktop_quote("50%") == "50%%"
    # reserved characters: quoted, and `"`, backquote, `$` and `\` backslash-escaped; each
    # backslash is then doubled for the string layer of the file
    assert desktop_quote('/a"b') == '"/a\\\\"b"'
    assert desktop_quote("/a$b") == '"/a\\\\$b"'
    assert desktop_quote("/a\\b") == '"/a\\\\\\\\b"'


def test_a_line_break_in_the_command_is_refused_not_written(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.call(command=["/bin/x\nExecStartPre=/bin/evil"]) == 2
    assert "line break" in capsys.readouterr().err
    assert files_under(rig.root) == [rig.command.removeprefix(str(rig.root) + "/")]


# -- the files are valid ------------------------------------------------------------------------

AWKWARD = "dir with space/%h $x"


def rendered(tmp_path: Path, awkward: bool) -> tuple[Path, Path, str]:
    command = make_command(tmp_path / "bin" / (AWKWARD if awkward else "plain"))
    targets = targets_in(tmp_path)
    desktop, unit = session.render_files([command], targets)
    verify = tmp_path / "verify"
    verify.mkdir()
    (verify / DESKTOP_NAME).write_text(desktop.content)
    (verify / UNIT_NAME).write_text(unit.content)
    return verify / DESKTOP_NAME, verify / UNIT_NAME, command


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze is missing")
@pytest.mark.parametrize("awkward", [False, True], ids=["plain", "awkward-path"])
def test_the_unit_passes_systemd_analyze_verify(tmp_path: Path, awkward: bool) -> None:
    """A read-only check of a COPY in a temporary folder (it loads the file and reads the unit
    folders; it starts and changes nothing). A key in the wrong section would be 'ignored' with a
    warning that is as much a failure here as an error is."""
    _, unit, _ = rendered(tmp_path, awkward)
    env = temporary_env(tmp_path)
    done = subprocess.run(
        ["systemd-analyze", "--user", "verify", str(unit)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "ignoring" not in done.stderr + done.stdout, done.stdout + done.stderr
    assert "Unknown" not in done.stderr + done.stdout


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze is missing")
def test_systemd_analyze_catches_a_unit_with_a_key_in_the_wrong_section(tmp_path: Path) -> None:
    """The check above must be able to fail: StartLimit* sit in [Unit] (in [Service] systemd
    ignores them, which is why the note's draft was corrected)."""
    _, unit, _ = rendered(tmp_path, False)
    text = (
        unit.read_text()
        .replace("StartLimitIntervalSec=60\n", "")
        .replace("Restart=on-failure\n", "Restart=on-failure\nStartLimitIntervalSec=60\n")
    )
    unit.write_text(text)
    done = subprocess.run(
        ["systemd-analyze", "--user", "verify", str(unit)],
        env=temporary_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "Unknown key" in done.stdout + done.stderr


@pytest.mark.skipif(
    shutil.which("desktop-file-validate") is None, reason="desktop-file-validate is not installed"
)
@pytest.mark.parametrize("awkward", [False, True], ids=["plain", "awkward-path"])
def test_the_desktop_file_passes_desktop_file_validate(tmp_path: Path, awkward: bool) -> None:
    desktop, _, _ = rendered(tmp_path, awkward)
    done = subprocess.run(
        ["desktop-file-validate", str(desktop)], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout + done.stderr == ""


def test_the_files_keep_what_the_note_asks_for(tmp_path: Path) -> None:
    desktop, unit, command = rendered(tmp_path, False)
    d = {
        k: v
        for k, v in (line.split("=", 1) for line in desktop.read_text().splitlines() if "=" in line)
    }
    assert d["Type"] == "Application" and d["Name"] == "Tesserae Shell"
    assert d["NoDisplay"] == "true" and d["Icon"] == "io.github.mindderivative.TesseraeShell"
    assert d["Exec"] == f"{command} run" and d["X-KDE-Wayland-Interfaces"] == ""
    text = unit.read_text()
    for line in (
        "PartOf=graphical-session.target",
        "After=graphical-session.target",
        "Type=notify",
        "NotifyAccess=main",
        f"ExecStart={command} run",
        "Restart=on-failure",
        "RestartSec=2",
        "RestartPreventExitStatus=1 2 4",
        "StartLimitIntervalSec=60",
        "StartLimitBurst=5",
        "Slice=session.slice",
        "WantedBy=graphical-session.target",
    ):
        assert line in text.splitlines(), line
    assert "WatchdogSec" not in text
    # the two start-limit keys are in [Unit]: in [Service] systemd ignores them
    unit_section = text.split("[Service]")[0]
    assert "StartLimitIntervalSec=60" in unit_section and "StartLimitBurst=5" in unit_section


# -- the wheel carries the files ----------------------------------------------------------------


def test_the_built_wheel_carries_both_files_as_package_data(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not installed")
    out = tmp_path / "dist"
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTEST_CURRENT_TEST")}
    done = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(out), str(REPO)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if done.returncode != 0:
        text = (done.stdout + done.stderr).lower()
        if "failed to fetch" in text or "failed to download" in text or "dns error" in text:
            pytest.skip("the build backend could not be fetched (no network)")
        pytest.fail(done.stdout + done.stderr)
    (wheel,) = out.glob("*.whl")
    assert wheel.name.endswith("-py3-none-any.whl"), wheel.name  # a pure wheel carries them
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for name in (DESKTOP_NAME, UNIT_NAME):
            member = f"tess_shell/data/{name}"
            assert member in names, sorted(names)
            assert (
                archive.read(member).decode()
                == (REPO / "src" / "tess_shell" / "data" / name).read_text()
            )


def test_the_templates_are_read_as_package_data() -> None:
    assert "[Desktop Entry]" in session.read_template(DESKTOP_NAME)
    assert "[Service]" in session.read_template(UNIT_NAME)


# -- READY=1 and STOPPING=1 -------------------------------------------------------------------


@pytest.fixture
def short_dir() -> Iterator[Path]:
    """A socket path is at most 107 bytes: a short folder under /tmp."""
    folder = Path(tempfile.mkdtemp(prefix="ns-", dir="/tmp"))
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def receiver(address: str) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(address)
    sock.settimeout(5)
    return sock


def test_ready_and_stopping_reach_a_path_socket(short_dir: Path) -> None:
    path = str(short_dir / "notify")
    sock = receiver(path)
    try:
        env = {"NOTIFY_SOCKET": path}
        assert notify.notify(notify.READY, env) is True
        assert sock.recv(256) == b"READY=1"
        assert notify.notify(notify.STOPPING, env) is True
        assert sock.recv(256) == b"STOPPING=1"
    finally:
        sock.close()


def test_ready_reaches_an_abstract_socket() -> None:
    name = f"tess-shell-test-{os.getpid()}-{os.urandom(4).hex()}"
    sock = receiver("\0" + name)
    try:
        assert notify.notify(notify.READY, {"NOTIFY_SOCKET": "@" + name}) is True
        assert sock.recv(256) == b"READY=1"
    finally:
        sock.close()


def test_nothing_is_sent_when_notify_socket_is_unset_or_not_an_address(short_dir: Path) -> None:
    sock = receiver(str(short_dir / "notify"))
    sock.settimeout(0.2)
    try:
        for env in ({}, {"NOTIFY_SOCKET": ""}, {"NOTIFY_SOCKET": "relative/path"}):
            assert notify.notify(notify.READY, env) is None
        with pytest.raises(TimeoutError):
            sock.recv(256)
    finally:
        sock.close()


def test_a_socket_nobody_listens_on_is_a_false_not_an_exception(short_dir: Path) -> None:
    assert notify.notify(notify.READY, {"NOTIFY_SOCKET": str(short_dir / "nobody")}) is False
    assert notify.notify(notify.READY, {"NOTIFY_SOCKET": "@no-such-abstract-socket"}) is False


def test_the_default_environment_is_os_environ(
    monkeypatch: pytest.MonkeyPatch, short_dir: Path
) -> None:
    path = str(short_dir / "notify")
    sock = receiver(path)
    try:
        monkeypatch.setenv("NOTIFY_SOCKET", path)
        assert notify.notify(notify.READY) is True
        assert sock.recv(256) == b"READY=1"
    finally:
        sock.close()


# -- the status warning --------------------------------------------------------------------------


def write_unit(path: Path, exec_start: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"[Unit]\nDescription=x\n\n[Service]\nType=notify\nExecStart={exec_start}\n")
    return path


def test_exec_start_is_read_from_the_service_section(tmp_path: Path) -> None:
    text = (
        "[Unit]\nExecStart=/ignored\n[Service]\nExecStart=\n"
        'ExecStart=-"/a b/c" run --x\n[Install]\n'
    )
    assert session.unit_exec_start(text) == ["/a b/c", "run", "--x"]
    assert session.unit_exec_start("[Service]\nType=notify\n") is None
    assert session.unit_exec_start("[Service]\nExecStart=\n") is None


def test_a_unit_that_names_this_install_has_no_warning(tmp_path: Path) -> None:
    command = make_command(tmp_path / "bin")
    unit = write_unit(tmp_path / "unit" / UNIT_NAME, f"{command} run")
    assert session.stale_warnings(unit, [command]) == []
    link = tmp_path / "link"
    link.symlink_to(command)  # the same file by another name is the same install
    assert session.stale_warnings(unit, [str(link)]) == []
    assert session.stale_warnings(tmp_path / "none" / UNIT_NAME, [command]) == []  # no unit


def test_a_command_that_no_longer_exists_is_a_warning_that_says_how_to_fix_it(
    tmp_path: Path,
) -> None:
    command = make_command(tmp_path / "bin")
    unit = write_unit(tmp_path / "unit" / UNIT_NAME, "/gone/venv/bin/tesserae-shell run")
    (warning,) = session.stale_warnings(unit, [command])
    assert "/gone/venv/bin/tesserae-shell" in warning and "does not exist" in warning
    assert "install-session --force" in warning and str(unit) in warning


def test_a_command_that_is_not_executable_or_not_absolute_is_a_warning(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.write_text("x")
    unit = write_unit(tmp_path / "unit" / UNIT_NAME, f"{plain} run")
    (warning,) = session.stale_warnings(unit, [str(plain)])
    assert "not an executable file" in warning
    relative = write_unit(tmp_path / "unit2" / UNIT_NAME, "tesserae-shell run")
    (warning,) = session.stale_warnings(relative, [str(plain)])
    assert "not an absolute path" in warning


def test_a_script_whose_interpreter_is_gone_is_a_warning(tmp_path: Path) -> None:
    script = tmp_path / "bin" / "tesserae-shell"
    script.parent.mkdir()
    script.write_text("#!/gone/venv/bin/python\nprint(1)\n")
    script.chmod(0o755)
    unit = write_unit(tmp_path / "unit" / UNIT_NAME, f"{script} run")
    (warning,) = session.stale_warnings(unit, [str(script)])
    assert "interpreter /gone/venv/bin/python does not exist" in warning


def test_a_unit_that_starts_another_install_is_a_warning(tmp_path: Path) -> None:
    one = make_command(tmp_path / "one")
    two = make_command(tmp_path / "two")
    unit = write_unit(tmp_path / "unit" / UNIT_NAME, f"{one} run")
    (warning,) = session.stale_warnings(unit, [two])
    assert "a different install" in warning and one in warning and two in warning
    # the module form of the same interpreter is the same install; another interpreter is not
    py = make_command(tmp_path / "py")
    unit = write_unit(tmp_path / "unit" / UNIT_NAME, f"{py} -m tess_shell run")
    assert session.stale_warnings(unit, [py, "-m", "tess_shell"]) == []
    assert session.stale_warnings(unit, [two, "-m", "tess_shell"])


def test_a_unit_written_by_install_session_is_never_stale_for_the_command_that_wrote_it(
    rig: Rig,
) -> None:
    assert rig.call() == 0
    assert session.stale_warnings(rig.targets.unit_file, [rig.command]) == []


@pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")
def test_status_warns_about_a_stale_unit_in_text_and_in_json(tmp_path: Path) -> None:
    unit = tmp_path / ".config" / "systemd" / "user" / UNIT_NAME  # HOME is tmp_path there
    write_unit(unit, "/gone/venv/bin/tesserae-shell run")
    with control_rig() as r:
        text = client_tesserae(r.bus.address, tmp_path, "status")
        as_json = client_tesserae(r.bus.address, tmp_path, "status", "--json")
        unit.unlink()
        clean = client_tesserae(r.bus.address, tmp_path, "status", "--json")
    assert text.returncode == 0 and "state: running" in text.stdout
    assert "warning:" not in text.stdout  # standard output stays what the shell said
    assert "/gone/venv/bin/tesserae-shell" in text.stderr and "does not exist" in text.stderr
    data = json.loads(as_json.stdout)
    assert len(data["warnings"]) == 1 and "/gone/venv/bin/tesserae-shell" in data["warnings"][0]
    assert data["state"] == "running"
    assert "warnings" not in json.loads(clean.stdout)  # the key is there only with a warning


def test_status_with_no_shell_running_still_warns_about_the_unit(tmp_path: Path) -> None:
    """The case the warning matters most: the unit's command is gone, so no shell started."""
    write_unit(tmp_path / ".config" / "systemd" / "user" / UNIT_NAME, "/gone/tesserae-shell run")
    env = env_for(f"unix:path={tmp_path}/none", tmp_path)
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "--json", "status"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(done.stdout)
    assert done.returncode == 2 and data["ok"] is False
    assert "/gone/tesserae-shell" in data["warnings"][0]


def test_the_status_check_never_breaks_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> list[str]:
        raise RuntimeError("no interpreter")

    monkeypatch.setattr(session, "current_command", boom)
    assert session.installed_warnings({"HOME": "/nonexistent"}) == []
