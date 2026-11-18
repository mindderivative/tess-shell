"""The hand-check kit framework (``tests/kitlib.py``): the sandboxes start and leave nothing behind,
refuse a real-looking bus, a step with a failing expectation fails the run, and a manual step never
runs. Every sandbox here is private (its own ``dbus-run-session`` and runtime directory); a test
that needs ``dbus-run-session``, ``/usr/lib/systemd/systemd``, ``kwin_wayland`` or ``sway`` is
skipped when it is missing."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests import kitlib
from tests.kitlib import (
    RealSession,
    SandboxRefused,
    Step,
    refuse_real,
    run_kit,
    write_kit,
)

needs_bus = pytest.mark.skipif(
    not (shutil.which("dbus-run-session") and shutil.which("dbus-send")),
    reason="dbus-run-session is not installed",
)


@pytest.fixture
def systemd_or_skip() -> None:
    """Skip, with the reason, where a private systemd user manager cannot run (not installed, or
    installed but not startable: a CI runner)."""
    if not (
        os.path.exists(kitlib.SYSTEMD)
        and shutil.which("systemctl")
        and shutil.which("dbus-run-session")
    ):
        pytest.skip("the systemd user manager is not installed")
    if not kitlib.systemd_works():
        pytest.skip("a private systemd user manager cannot be started on this machine")


needs_systemd = pytest.mark.usefixtures("systemd_or_skip")
needs_kwin = pytest.mark.skipif(
    not (shutil.which("kwin_wayland") and shutil.which("dbus-run-session")),
    reason="kwin_wayland is not installed",
)
needs_sway = pytest.mark.skipif(
    not (shutil.which("sway") and shutil.which("dbus-run-session")),
    reason="sway is not installed",
)

REAL = RealSession(
    bus="unix:path=/run/user/1000/bus", runtime="/run/user/1000", uid_runtime="/run/user/1000"
)


def private_env(tmp_path: Path, bus: str) -> dict[str, str]:
    runtime = tmp_path / "run"
    runtime.mkdir(exist_ok=True)
    return {"XDG_RUNTIME_DIR": str(runtime), "DBUS_SESSION_BUS_ADDRESS": bus}


@pytest.fixture
def made_dirs(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """The folders ``tempfile.mkdtemp`` made during a test, so a test can assert they are gone."""
    made: list[str] = []
    real = tempfile.mkdtemp

    def record(*args: object, **kwargs: object) -> str:
        path = real(*args, **kwargs)  # type: ignore[call-overload]
        made.append(path)
        return path  # type: ignore[no-any-return]

    monkeypatch.setattr(tempfile, "mkdtemp", record)
    yield made


# -- the refusal -----------------------------------------------------------------------------


def test_a_private_looking_environment_passes_the_refusal_check(tmp_path: Path) -> None:
    env = private_env(tmp_path, f"unix:path={tmp_path}/run/bus,guid=abc")
    refuse_real(env, REAL)


@pytest.mark.parametrize(
    "bus",
    [
        "unix:path=/run/user/1000/bus",  # the real session bus
        "unix:path=/run/user/1000/bus,guid=xyz",  # in the real runtime directory
        "unix:abstract=/tmp/dbus-real",  # the real bus again, by address
    ],
)
def test_the_refusal_triggers_on_a_real_looking_bus(tmp_path: Path, bus: str) -> None:
    real = RealSession(bus="unix:abstract=/tmp/dbus-real", runtime="", uid_runtime="/run/user/1000")
    env = private_env(tmp_path, bus)
    with pytest.raises(SandboxRefused):
        refuse_real(env, real)


def test_the_refusal_triggers_on_the_real_runtime_directory() -> None:
    for runtime in ("/run/user/1000", "/run/user/1000/sub"):
        env = {"XDG_RUNTIME_DIR": runtime, "DBUS_SESSION_BUS_ADDRESS": "unix:path=/tmp/x/bus"}
        with pytest.raises(SandboxRefused):
            refuse_real(env, REAL)


def test_the_refusal_needs_a_runtime_directory_and_a_bus(tmp_path: Path) -> None:
    with pytest.raises(SandboxRefused):
        refuse_real({"DBUS_SESSION_BUS_ADDRESS": "unix:path=/tmp/x/bus"}, REAL)
    with pytest.raises(SandboxRefused):
        refuse_real({"XDG_RUNTIME_DIR": str(tmp_path / "run")}, REAL)
    with pytest.raises(SandboxRefused):  # a runtime directory outside the temporary folder
        refuse_real(
            {"XDG_RUNTIME_DIR": "/var/tmp/x", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/tmp/b"}, REAL
        )


def test_a_compositor_socket_outside_the_sandbox_is_refused(tmp_path: Path) -> None:
    env = private_env(tmp_path, f"unix:path={tmp_path}/run/bus")
    env["WAYLAND_DISPLAY"] = "/run/user/1000/wayland-0"
    with pytest.raises(SandboxRefused):
        refuse_real(env, REAL)
    env["WAYLAND_DISPLAY"] = "pkwin"  # a name in the private runtime directory is fine
    refuse_real(env, REAL)


def test_the_environment_of_a_sandbox_never_names_the_real_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "DISPLAY", "SWAYSOCK"):
        monkeypatch.setenv(name, "real-" + name)
    env = kitlib.scrubbed_environ()
    assert not any(
        name in env
        for name in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "DISPLAY", "SWAYSOCK")
    )


# -- the sandboxes ---------------------------------------------------------------------------


@needs_bus
def test_private_bus_starts_is_private_and_leaves_nothing(
    monkeypatch: pytest.MonkeyPatch, made_dirs: list[str]
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1/not-the-bus")
    monkeypatch.setenv("WAYLAND_DISPLAY", "real-display")
    with kitlib.private_bus() as bus:
        runtime = bus.runtime
        assert runtime.stat().st_mode & 0o777 == 0o700
        assert bus.address.startswith(f"unix:path={runtime}/bus")
        assert "real-display" not in bus.env.values()
        assert bus.name_owned("org.freedesktop.DBus")
        assert str(runtime).startswith(tempfile.gettempdir())
        for name in (
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
            "XDG_STATE_HOME",
            "HOME",
        ):
            assert bus.env[name].startswith(str(bus.root))
        done = bus.run(["sh", "-c", "echo $DBUS_SESSION_BUS_ADDRESS"])
        assert done.stdout.strip() == bus.address
    assert not runtime.exists()
    assert not any(Path(p).exists() for p in made_dirs)
    assert kitlib.processes_with_runtime(runtime) == []
    assert not subprocess.run(["pgrep", "-f", str(runtime)], capture_output=True).stdout


@needs_bus
def test_private_bus_refuses_when_the_runtime_directory_looks_real_and_cleans_up(
    made_dirs: list[str],
) -> None:
    """The check runs after the setup, on what the bus really reports: with the temporary folder
    declared 'real' it must refuse, and still leave nothing behind."""
    real = RealSession(bus="", runtime="", uid_runtime=tempfile.gettempdir())
    with pytest.raises(SandboxRefused), kitlib.private_bus(real):
        pytest.fail("the sandbox must not be entered")
    assert made_dirs
    assert not any(Path(p).exists() for p in made_dirs)


@needs_bus
def test_kill_strays_removes_a_process_that_outlives_its_sandbox() -> None:
    with kitlib.private_bus() as bus:
        sleeper = subprocess.Popen(["sleep", "300"], env=bus.env, start_new_session=True)
        try:
            # exec closes Popen's error pipe a moment before the kernel fills in the new
            # process's /proc/PID/environ, so a scan right away can miss it: wait for it
            kitlib.wait_until(
                lambda: sleeper.pid in kitlib.processes_with_runtime(bus.runtime),
                10,
                "the sleeper's environment to name the sandbox",
            )
        finally:
            runtime = bus.runtime
    # the sandbox's own clean-up killed it (no bus, no sleeper)
    assert sleeper.wait(timeout=10) != 0
    assert kitlib.processes_with_runtime(runtime) == []


@needs_systemd
def test_private_systemd_runs_a_unit_and_leaves_no_process() -> None:
    with kitlib.private_bus() as bus:
        runtime = bus.runtime
        units = Path(bus.env["XDG_CONFIG_HOME"]) / "systemd" / "user"
        units.mkdir(parents=True)
        (units / "probe.service").write_text("[Service]\nExecStart=/usr/bin/sleep 300\n")
        with kitlib.private_systemd(bus) as manager:
            assert manager.ctl("daemon-reload").returncode == 0
            assert manager.ctl("start", "probe.service").returncode == 0
            assert manager.ctl("is-active", "probe.service").stdout.strip() == "active"
            assert "probe.service" in manager.active_units()
            assert kitlib.processes_with_runtime(runtime)  # the unit's sleep carries the runtime
            assert manager.ctl("stop", "probe.service").returncode == 0
            assert manager.ctl("is-active", "probe.service").stdout.strip() == "inactive"
            # a unit still running when the context ends is stopped by it
            assert manager.ctl("start", "probe.service").returncode == 0
    assert not runtime.exists()
    assert kitlib.processes_with_runtime(runtime) == []
    assert subprocess.run(["pgrep", "-f", str(runtime)], capture_output=True).returncode == 1


@needs_systemd
def test_private_systemd_leaves_the_real_manager_alone() -> None:
    real_state = subprocess.run(
        ["systemctl", "--user", "is-system-running"], capture_output=True, text=True
    ).stdout.strip()
    with kitlib.private_bus() as bus, kitlib.private_systemd(bus) as manager:
        assert manager.ctl("show", "-p", "Names", "probe.service").returncode == 0
        env = manager.env
        assert env["XDG_RUNTIME_DIR"] == str(bus.runtime)
        assert env["XDG_RUNTIME_DIR"] != f"/run/user/{os.getuid()}"
        assert manager.ctl("show-environment").stdout.count(f"XDG_RUNTIME_DIR={bus.runtime}") == 1
    after = subprocess.run(
        ["systemctl", "--user", "is-system-running"], capture_output=True, text=True
    ).stdout.strip()
    assert after == real_state


@needs_kwin
def test_private_kwin_answers_on_the_private_bus_and_leaves_nothing() -> None:
    with kitlib.private_bus() as bus:
        runtime = bus.runtime
        with kitlib.private_kwin(bus) as kwin:
            assert (runtime / "pkwin").exists()
            assert kwin.env["WAYLAND_DISPLAY"] == "pkwin"
            assert bus.name_owned("org.kde.KWin")
            done = kwin.run(
                [
                    "dbus-send",
                    "--session",
                    "--dest=org.kde.KWin",
                    "--print-reply",
                    "/Scripting",
                    "org.kde.kwin.Scripting.isScriptLoaded",
                    "string:none",
                ]
            )
            assert done.returncode == 0, done.stderr
    assert kitlib.processes_with_runtime(runtime) == []
    assert not subprocess.run(
        ["pgrep", "-f", f"kwin_wayland.*{runtime}"], capture_output=True
    ).stdout


@needs_sway
def test_private_sway_starts_and_stops() -> None:
    with kitlib.private_bus() as bus:
        runtime = bus.runtime
        with kitlib.private_sway(bus) as sway:
            done = sway.run(["swaymsg", "-t", "get_version"])
            assert done.returncode == 0, done.stderr
            assert sway.env["WAYLAND_DISPLAY"] == sway.display
    assert kitlib.processes_with_runtime(runtime) == []


# -- steps, the runner, the kit folder -------------------------------------------------------


def test_a_step_is_validated() -> None:
    with pytest.raises(ValueError, match="kind"):
        Step("x", "t", kind="sometimes", command="true")
    with pytest.raises(ValueError, match="sandbox"):
        Step("x", "t", command="true", sandbox="real")
    with pytest.raises(ValueError, match="reason"):
        Step("x", "t", kind="manual")
    with pytest.raises(ValueError, match="exact action"):
        Step("x", "t", kind="real-session", reason="why")
    with pytest.raises(ValueError, match="command"):
        Step("x", "t")


def test_the_sandboxes_of_a_step_are_started_in_a_fixed_order() -> None:
    assert Step("x", "t", command="true", sandbox="systemd+kwin").needs == [
        "bus",
        "kwin",
        "systemd",
    ]
    assert Step("x", "t", command="true", sandbox="kwin").needs == ["bus", "kwin"]
    assert Step("x", "t", command="true").needs == []


def test_the_expectation_checks_the_exit_code_the_regexes_and_the_check() -> None:
    result = kitlib.Result(2, "hello world\n", "boom\n", 0.1)
    assert (
        kitlib.evaluate(Step("x", "t", command="x", exit_code=2, expect=("hello",)), result) == []
    )
    assert kitlib.evaluate(Step("x", "t", command="x", exit_code=0), result) == [
        "exit code 2, expected 0"
    ]
    assert kitlib.evaluate(Step("x", "t", command="x", exit_code=None, expect=("absent",)), result)
    forbidden = kitlib.evaluate(Step("x", "t", command="x", exit_code=2, forbid=("boom",)), result)
    assert forbidden and "boom" in forbidden[0]
    source = "def check(result):\n    return None if 'world' in result.stdout else 'no world'\n"
    assert kitlib.evaluate(Step("x", "t", command="x", exit_code=2, check=source), result) == []
    bad = "def check(result):\n    return 'always wrong'\n"
    assert kitlib.evaluate(Step("x", "t", command="x", exit_code=2, check=bad), result) == [
        "always wrong"
    ]
    broken = "def check(result):\n    raise KeyError('k')\n"
    (reason,) = kitlib.evaluate(Step("x", "t", command="x", exit_code=2, check=broken), result)
    assert "KeyError" in reason
    with pytest.raises(ValueError, match=r"check\(result\)"):
        kitlib.compile_check("x = 1")


def test_a_failing_step_is_reported_as_fail_and_the_run_fails(tmp_path: Path) -> None:
    steps = [
        Step("ok", "passes", command="echo fine", expect=("fine",)),
        Step("bad", "fails", command="echo wrong; exit 4", expect=("fine",)),
        Step("after", "still runs after a failure", command="echo later", expect=("later",)),
    ]
    lines: list[str] = []
    run = run_kit(steps, tmp_path, echo=lines.append)
    assert run.verdict("ok") == "PASS"
    assert run.verdict("bad") == "FAIL"
    assert run.verdict("after") == "PASS"
    assert run.failed
    detail = (tmp_path / "results" / "bad.txt").read_text()
    assert "verdict: FAIL" in detail and "exit code 4, expected 0" in detail
    assert "wrong" in detail and "command:" in detail and "expectation:" in detail
    summary = (tmp_path / "results.txt").read_text().splitlines()
    assert summary[0].startswith("PASS  ok") and summary[1].startswith("FAIL  bad")
    assert summary[-1] == "2 PASS, 1 FAIL, 0 SKIP"
    assert lines[1].startswith("FAIL  bad")


def test_a_manual_step_never_runs_and_is_listed_as_skip(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    steps = [
        Step("m", "look", kind="manual", command=f"touch {marker}", reason="needs eyes"),
        Step(
            "r",
            "ask",
            kind="real-session",
            command=f"touch {marker}",
            reason="the real portal",
            action="run X",
        ),
        Step("a", "auto", command="true"),
    ]
    run = run_kit(steps, tmp_path / "kit_out", echo=lambda _: None)
    assert not marker.exists()
    assert [o.verdict for o in run.outcomes] == ["SKIP", "SKIP", "PASS"]
    assert not run.failed
    assert (
        "manual, see checklist.txt: needs eyes"
        in (tmp_path / "kit_out" / "results.txt").read_text()
    )


def test_a_step_that_times_out_fails(tmp_path: Path) -> None:
    run = run_kit(
        [Step("slow", "never ends", command="sleep 60", timeout=0.5)], tmp_path, echo=lambda _: None
    )
    assert run.verdict("slow") == "FAIL"
    assert "timed out" in (tmp_path / "results" / "slow.txt").read_text()


def test_a_missing_tool_skips_the_step(tmp_path: Path) -> None:
    run = run_kit(
        [Step("t", "needs a tool", command="true", tools=("no-such-program-xyz",))],
        tmp_path,
        echo=lambda _: None,
    )
    assert run.verdict("t") == "SKIP"
    assert "not installed" in (tmp_path / "results.txt").read_text()


def test_the_step_sees_the_kit_variables_and_a_scrubbed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    run = run_kit(
        [
            Step(
                "e",
                "env",
                command='echo "[$KIT] [$BIN] [$STEP] [${DBUS_SESSION_BUS_ADDRESS-unset}]"',
            )
        ],
        tmp_path,
        variables={"BIN": "/x/bin"},
        echo=lambda _: None,
    )
    assert run.verdict("e") == "PASS"
    assert f"[{tmp_path}] [/x/bin] [e] [unset]" in (tmp_path / "results" / "e.txt").read_text()


def test_a_kit_folder_is_self_contained_and_its_runner_exits_non_zero_on_a_failure(
    tmp_path: Path,
) -> None:
    steps = [
        Step("one", "passes", command="echo one", expect=("one",)),
        Step("two", "fails", command="exit 3"),
        Step("three", "manual", kind="manual", reason="a screen", expect=("the ring is visible",)),
        Step("four", "real", kind="real-session", reason="the real portal", action="do Y"),
    ]
    kit = tmp_path / "kit"
    write_kit(kit, steps, title="Demo kit", intro="Hello.", files={"helper.sh": "echo hi\n"})
    assert sorted(p.name for p in kit.iterdir()) == [
        "checklist.txt",
        "helper.sh",
        "kit_runner.py",
        "run-all.sh",
        "steps.json",
    ]
    assert (kit / "kit_runner.py").read_text() == Path(kitlib.__file__).read_text()
    assert os.access(kit / "run-all.sh", os.X_OK)
    assert json.loads((kit / "steps.json").read_text())["steps"][0]["id"] == "one"
    # copy it away: only its own files and the interpreter are needed
    moved = tmp_path / "elsewhere"
    shutil.copytree(kit, moved)
    done = subprocess.run(
        [str(moved / "run-all.sh")],
        capture_output=True,
        text=True,
        cwd="/",
        env={"PATH": os.environ["PATH"]},
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "PASS  one" in done.stdout and "FAIL  two" in done.stdout
    assert "1 PASS, 1 FAIL, 2 SKIP" in done.stdout
    text = (moved / "results.txt").read_text()
    assert "PASS  cleanup" in text and "results/two.txt" in text
    assert (moved / "results" / "one.txt").exists()
    # the same kit without the failing step exits 0
    ok = tmp_path / "ok"
    write_kit(ok, [steps[0], steps[2]], title="Demo")
    done = subprocess.run([str(ok / "run-all.sh")], capture_output=True, text=True, cwd="/")
    assert done.returncode == 0, done.stdout + done.stderr
    assert sys.executable in (ok / "run-all.sh").read_text()


def test_the_checklist_lists_only_manual_and_real_session_steps(tmp_path: Path) -> None:
    steps = [
        Step("a1", "auto one", command="true"),
        Step("a2", "auto two", command="true"),
        Step("m1", "look at the ring", kind="manual", reason="a screen"),
        Step("r1", "the real portal", kind="real-session", reason="real bus", action="run Z"),
    ]
    text = kitlib.checklist_text("Kit", steps)
    assert "2 steps run unattended" in text and "results.txt" in text
    assert text.index("results.txt") < text.index("m1")
    assert "m1  [manual]" in text and "why a session cannot: a screen" in text
    assert "r1  [real-session]" in text and "exact action (ask permission first): run Z" in text
    assert "a1" not in text and "auto one" not in text
    only_auto = kitlib.checklist_text("Kit", steps[:2])
    assert "Nothing is left for you" in only_auto


def test_the_steps_survive_the_kit_file() -> None:
    step = Step(
        "s",
        "t",
        command=("echo", "a b"),
        sandbox="systemd+kwin",
        expect=("a",),
        forbid=("z",),
        tools=("echo",),
        check="def check(result):\n    return None\n",
        exit_code=None,
    )
    assert Step.from_json(json.loads(json.dumps(step.to_json()))) == step
    with pytest.raises(ValueError, match="source text"):
        Step("s", "t", command="x", check=lambda r: None).to_json()


@needs_bus
def test_a_kit_step_in_the_bus_sandbox_runs_in_a_private_bus_and_cleans_up(tmp_path: Path) -> None:
    run = run_kit(
        [
            Step(
                "bus",
                "the step sees a private bus",
                command="echo $DBUS_SESSION_BUS_ADDRESS; echo $XDG_RUNTIME_DIR",
                sandbox="bus",
                expect=(r"/tmp/tk-\w+/run/bus",),
            ),
            Step("same", "and the next one the same bus", command="echo $SANDBOX", sandbox="bus"),
        ],
        tmp_path,
        echo=lambda _: None,
    )
    assert not run.failed, (tmp_path / "results.txt").read_text()
    runtime = Path(
        (tmp_path / "results" / "bus.txt").read_text().split("--- stdout ---")[1].splitlines()[2]
    )
    assert not runtime.exists()
    assert "no process left" in (tmp_path / "results.txt").read_text()


def test_unmount_under_leaves_a_folder_with_no_mount_alone(tmp_path: Path) -> None:
    (tmp_path / "gvfs").mkdir()
    assert kitlib.unmount_under(tmp_path) == []
    assert (tmp_path / "gvfs").is_dir()
