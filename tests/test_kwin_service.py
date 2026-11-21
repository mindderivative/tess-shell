"""The shell's side of its KWin script on a private bus (KWin Integration, Tasks Module): a fake
KWin with a fake ``/Scripting`` and a fake script that calls the shell's exported interface the way
the real script's ``callDBus`` does. Nothing here touches the real session bus or the real KWin."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from tess_shell.services.api import WindowInfo
from tess_shell.services.bus import ServiceThread
from tess_shell.services.control import ControlService
from tess_shell.services.kwin import KWinService, parse_fullscreen, parse_windows
from tess_shell.services.kwin_package import (
    PACKAGE_ID,
    RefusedInTest,
    install_package,
    main_script,
    parse_version,
    refuse_real_bus,
)
from tests.fake_dbus import HAVE_DAEMON, FakeBus, fake_bus, wait_for
from tests.fake_kwin import FakeKWin, Loaded, uuid, window
from tests.test_control import FakeCommands, FakeLoop

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

SECRET = "SECRET-TITLE-OF-A-WINDOW"


class HeldLoop(FakeLoop):
    """A loop thread that can be told to hold what it is given (to see a burst arrive as one)."""

    def __init__(self) -> None:
        super().__init__()
        self.held: list[Callable[[], None]] | None = None

    def call_soon(self, fn: Callable[[], None]) -> None:
        if self.held is not None:
            self.held.append(fn)
        else:
            super().call_soon(fn)

    def release(self) -> None:
        held, self.held = self.held or [], None
        for fn in held:
            super().call_soon(fn)


@dataclass
class Rig:
    bus: FakeBus
    service: ServiceThread
    loop: HeldLoop
    kwin: KWinService
    control: ControlService
    fake: FakeKWin
    fullscreen: list[tuple[str, frozenset[str]]] = field(default_factory=list)
    windows: list[tuple[str, tuple[WindowInfo, ...]]] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    def start(self) -> None:
        self.service.submit(self.kwin.start()).result(10)

    def stop(self) -> None:
        self.service.submit(self.kwin.stop()).result(10)

    def log(self, contains: str = "kwin:", level: str = "") -> list[str]:
        return [x for x in self.lines if contains in x and level in x]

    def settle(self) -> None:
        """Everything handed to the loop thread so far has run."""
        done = threading.Event()
        self.loop.call_soon(done.set)
        assert done.wait(5)


@contextmanager
def rig(
    tmp_path: Path,
    *,
    kwin_up: bool = True,
    mode: str = "RUNTIME",
    wanted: bool = False,
    private: bool = True,
    **kw: Any,
) -> Iterator[Rig]:
    with fake_bus() as bus:
        fake = FakeKWin(bus, refuse_load=kw.pop("refuse_load", False))
        if kwin_up:
            fake.up()
        service = ServiceThread(bus.address)
        service.start()
        # the bus the environment gives is the real one: the shell's KWin service on it must refuse
        other = ServiceThread(None)
        if not private:
            other.start()
        loop = HeldLoop()
        kw.setdefault("silent_after", 5.0)
        kw.setdefault("action_linger", 0.05)
        kw.setdefault("runtime_dir", tmp_path / "run")
        kwin = KWinService(service if private else other, loop.call_soon, mode=mode, **kw)
        control = ControlService(service, loop.call_soon, FakeCommands(), "x", None, kwin)  # type: ignore[arg-type]
        state = Rig(bus, service, loop, kwin, control, fake)
        kwin.on_fullscreen = lambda outputs: state.fullscreen.append(
            (threading.current_thread().name, outputs)
        )
        kwin.on_windows = lambda windows: state.windows.append(
            (threading.current_thread().name, windows)
        )
        kwin.on_state = lambda: state.states.append(kwin.state)
        if wanted:
            kwin.set_windows_wanted(True)
        sink = logger.add(lambda m: state.lines.append(str(m).rstrip()), level="DEBUG")
        try:
            assert service.submit(control.start()).result(10)
            control.set_state("running")
            yield state
        finally:
            logger.remove(sink)
            try:
                service.submit(kwin.stop()).result(10)
            finally:
                service.submit(control.stop()).result(10)
                fake.close()
                other.stop()
                service.stop()
                loop.close()


# -- reading what the script sends ---------------------------------------------------------------


def test_the_version_is_the_line_of_the_support_information() -> None:
    assert parse_version("Version\n=======\nKWin version: 6.8.2\nQt: 6\n") == "6.8.2"
    assert parse_version("nothing of the kind") is None


@pytest.mark.parametrize("raw", ["", "nope", "{}", "[1]", '["a", 2]', '"DP-1"', "[null]"])
def test_a_fullscreen_state_that_is_not_an_array_of_names_is_malformed(raw: str) -> None:
    assert parse_fullscreen(raw) is None


def test_a_fullscreen_state_is_a_set_of_output_names() -> None:
    assert parse_fullscreen('["DP-1"]') == {"DP-1"}
    assert parse_fullscreen("[]") == frozenset()
    assert parse_fullscreen('["a","a"]') == {"a"}


def test_a_window_list_keeps_the_scripts_order_and_drops_the_shells_own_surfaces() -> None:
    raw = json.dumps(
        [
            window("b", "Second", "org.b"),
            window("a", "First", "org.a", active=True, minimized=True, desktops=["d1"]),
            window("s", "ours", "tesserae-shell.bar.top_bar"),
        ]
    )
    got = parse_windows(raw)
    assert got is not None
    assert [w.id for w in got] == ["b", "a"]
    assert got[1] == WindowInfo("a", "First", "org.a", True, True, ("d1",), "DP-1", False)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "nope",
        "{}",
        '["x"]',
        '[{"title": "no id"}]',
        '[{"id": ""}]',
        '[{"id": "a"}, {"id": "a"}]',  # an id twice
        '[{"id": "a", "title": 3}]',
        '[{"id": "a", "active": "yes"}]',
        '[{"id": "a", "desktops": "d1"}]',
        '[{"id": "a", "desktops": [1]}]',
        "[" * 3 + "]" * 3,
        "x" * (2 * 1024 * 1024 + 1),
    ],
)
def test_a_window_list_that_is_not_what_the_script_sends_is_malformed(raw: str) -> None:
    assert parse_windows(raw) is None


# -- loading (KWin Integration > Loading the script) ---------------------------------------------


def test_mode_r_loads_the_script_after_reading_the_version_and_unloads_it_at_stop(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.start()
        assert r.kwin.version == "6.8.2" and r.kwin.state == "loaded"
        assert any("KWin 6.8.2" in x for x in r.log())
        assert r.fake.order() == [
            "supportInformation",
            "isScriptLoaded",
            "loadScript",
            "start",
        ]
        (path, name), *_ = r.fake.names("loadScript")
        assert (Path(path), name) == (main_script(), PACKAGE_ID)
        assert Path(path).read_text().startswith("/*")  # it is the real script file
        assert r.fake.loaded()
        r.stop()
        assert not r.fake.loaded()  # after a normal stop isScriptLoaded is false
        assert r.fake.names("unloadScript") == [(PACKAGE_ID,)]


def test_a_script_that_was_left_loaded_is_unloaded_before_the_new_load(tmp_path: Path) -> None:
    with rig(tmp_path) as r:
        r.start()
        r.stop()
        r.fake.scripts[PACKAGE_ID] = r.fake.history[0]  # a shell that crashed left it
        r.fake.calls.clear()
        r.kwin = KWinService(r.service, r.loop.call_soon, runtime_dir=tmp_path / "run")
        r.start()
        assert r.fake.order() == [
            "supportInformation",
            "isScriptLoaded",
            "unloadScript",
            "loadScript",
            "start",
        ]


def test_the_package_the_shell_loads_is_a_kwin_script_package() -> None:
    from tess_shell.services.kwin_package import package_folder

    meta = json.loads((package_folder() / "metadata.json").read_text())
    assert meta["KPackageStructure"] == "KWin/Script"
    assert meta["KPlugin"]["Id"] == PACKAGE_ID and meta["X-Plasma-API"] == "javascript"
    assert main_script().is_file()


def test_a_kwin_that_is_not_there_switches_the_features_off_and_loads_nothing(
    tmp_path: Path,
) -> None:
    with rig(tmp_path, kwin_up=False) as r:
        r.start()
        assert r.kwin.state == "not-kwin" and not r.kwin.available
        assert r.fake.calls == []
        (line,) = r.log()
        assert "INFO" in line and "org.kde.KWin is not on the session bus" in line


def test_a_script_kwin_refuses_is_one_warning_and_the_shell_goes_on(tmp_path: Path) -> None:
    with rig(tmp_path, refuse_load=True) as r:
        r.start()
        assert r.kwin.state == "failed" and "refused" in r.kwin.detail
        warnings = r.log(level="WARNING")
        assert len(warnings) == 1 and "fullscreen hiding and the window list are off" in warnings[0]
        assert r.fake.names("start") == []  # nothing was started


def test_kwin_calls_that_fail_are_one_warning_naming_the_reason(tmp_path: Path) -> None:
    with rig(tmp_path) as r:
        r.fake.fail_calls = True
        r.start()
        assert r.kwin.state == "failed"
        (warning,) = r.log(level="WARNING")
        assert "the call to KWin failed" in warning


def test_a_silent_script_is_one_warning_after_the_wait_and_not_available(tmp_path: Path) -> None:
    with rig(tmp_path, silent_after=0.3) as r:
        r.fake.script.silent = True
        r.start()
        assert wait_for(lambda: r.kwin.silent)
        assert not r.kwin.available and r.kwin.state == "loaded"
        (warning,) = r.log(level="WARNING")
        assert "sent nothing within 0.3 s" in warning
        # it spoke after all: available again
        r.fake.script.silent = False
        r.fake.set_fullscreen([])
        assert wait_for(lambda: r.kwin.available)


def test_a_script_that_speaks_in_time_is_never_called_silent(tmp_path: Path) -> None:
    with rig(tmp_path, silent_after=0.3) as r:
        r.start()
        assert wait_for(lambda: r.kwin.fullscreen_reports >= 1)
        import time

        time.sleep(0.5)  # past the wait: a flag raised late would show now
        assert not r.kwin.silent and r.log(level="WARNING") == []


def test_mode_off_makes_no_call_at_all(tmp_path: Path) -> None:
    with rig(tmp_path, mode="OFF") as r:
        r.start()
        assert r.kwin.state == "off" and r.fake.calls == []


def test_mode_p_loads_nothing_but_checks_that_kwin_runs_the_installed_script(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    with rig(tmp_path, mode="PERSISTENT", scripts=scripts) as r:
        r.start()  # not installed in KWin: one warning
        assert r.kwin.state == "failed"
        assert r.fake.names("loadScript") == [] and r.fake.names("start") == []
        assert "not installed" in r.log(level="WARNING")[0]
    with rig(tmp_path, mode="PERSISTENT", scripts=scripts) as r:
        r.fake.scripts[PACKAGE_ID] = Loaded(PACKAGE_ID, "installed", "", started=True)
        r.start()
        assert r.kwin.state == "loaded" and r.fake.names("loadScript") == []
        r.stop()
        assert r.fake.names("unloadScript") == []  # a persistent script outlives the shell


# -- the guard ------------------------------------------------------------------------------------


def test_a_test_never_loads_a_script_into_a_bus_that_is_not_private(tmp_path: Path) -> None:
    """The bus the environment gives is the real session bus: in a test the service refuses."""
    with rig(tmp_path, private=False) as r:
        with pytest.raises(RefusedInTest):
            r.start()
        assert r.kwin.loads == 0 and r.fake.calls == []
        with pytest.raises(RefusedInTest):
            r.kwin.act("close", uuid(1)).result(5)
        assert r.fake.calls == []


def test_the_guard_tells_a_private_bus_from_the_real_one(tmp_path: Path) -> None:
    refuse_real_bus(f"unix:path={tmp_path}/bus")  # under the temporary folder: private
    for real in (None, "", "unix:path=/run/user/1000/bus", "tcp:host=localhost,port=1"):
        with pytest.raises(RefusedInTest):
            refuse_real_bus(real)


# -- FullscreenState ------------------------------------------------------------------------------


def test_the_outputs_with_an_active_fullscreen_window_reach_the_loop_and_a_repeat_does_not(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.start()
        assert wait_for(lambda: r.kwin.fullscreen_reports >= 1)  # the load reported "[]"
        r.fake.set_fullscreen(["DP-1"])
        assert wait_for(lambda: r.fullscreen == [("fake-loop", frozenset({"DP-1"}))])
        r.fake.set_fullscreen(["DP-1"])  # the full state again: nothing changed
        r.fake.set_fullscreen(["DP-1", "HDMI-A-1"])
        assert wait_for(lambda: len(r.fullscreen) == 2)
        r.fake.set_fullscreen([])
        assert wait_for(lambda: len(r.fullscreen) == 3)
        assert [o for _, o in r.fullscreen] == [
            frozenset({"DP-1"}),
            frozenset({"DP-1", "HDMI-A-1"}),
            frozenset(),
        ]
        assert {t for t, _ in r.fullscreen} == {"fake-loop"}  # on the loop thread, not the bus's


def test_hide_on_fullscreen_false_hands_nothing_to_the_loop(tmp_path: Path) -> None:
    with rig(tmp_path, hide_on_fullscreen=False) as r:
        r.start()
        r.fake.set_fullscreen(["DP-1"])
        assert wait_for(lambda: r.kwin.fullscreen == frozenset({"DP-1"}))
        r.settle()
        assert r.fullscreen == []


def test_after_a_restart_of_the_shell_the_fresh_load_carries_the_current_state(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.start()
        r.fake.set_fullscreen(["DP-1"])
        assert wait_for(lambda: len(r.fullscreen) == 1, timeout=20)
        r.stop()
        # the shell starts again; a window is fullscreen all the time (no event happens)
        r.kwin = KWinService(r.service, r.loop.call_soon, runtime_dir=tmp_path / "run")
        seen: list[frozenset[str]] = []
        r.kwin.on_fullscreen = seen.append
        r.control.script = r.kwin
        r.start()
        # the restart hands the state over through a fresh load on a loaded CI runner: wait for it,
        # not for 3 s (the wait ends as soon as it holds)
        assert wait_for(lambda: seen == [frozenset({"DP-1"})], timeout=20)


def test_a_malformed_fullscreen_state_is_ignored_with_one_warning_and_still_answered(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.start()
        r.fake.set_fullscreen(["DP-1"])
        assert wait_for(lambda: len(r.fullscreen) == 1)
        for raw in ("not json", "[1, 2]", "{}", "x" * 100):
            answer = r.fake.raw("FullscreenState", raw)
            assert json.loads(answer or "") == {"windows": False}
        r.settle()
        assert len(r.fullscreen) == 1 and r.kwin.fullscreen == frozenset({"DP-1"})
        (warning,) = r.log(level="WARNING")
        assert "not a JSON array of output names" in warning and "not json" not in warning


def test_a_call_with_the_string_reaches_the_shell_and_a_call_with_as_does_not(
    tmp_path: Path,
) -> None:
    """KWin Integration > Acceptance: ``["DP-1"]`` as one string arrives; a script's ``as`` (which
    ``callDBus`` cannot send anyway) is refused by the interface's signature."""
    with rig(tmp_path) as r:
        r.start()
        assert wait_for(lambda: r.kwin.fullscreen_reports >= 1)
        assert r.fake.raw("FullscreenState", '["DP-1"]') is not None
        assert wait_for(lambda: r.kwin.fullscreen == frozenset({"DP-1"}))
        reports = r.kwin.fullscreen_reports
        assert r.fake.raw("FullscreenState", "DP-2", "as") is None
        assert r.fake.script.errors[-1] in (
            "org.freedesktop.DBus.Error.InvalidArgs",
            "org.freedesktop.DBus.Error.UnknownMethod",
        )
        r.settle()
        assert r.kwin.fullscreen_reports == reports and r.kwin.fullscreen == {"DP-1"}


def test_the_answer_to_a_report_is_a_small_json_string(tmp_path: Path) -> None:
    with rig(tmp_path) as r:
        r.start()
        assert r.fake.raw("FullscreenState", "[]") == '{"windows": false}'
        assert r.fake.raw("WindowsState", "[]") == '{"windows": false}'


# -- WindowsState: on, off and what arrives -------------------------------------------------------


def test_with_no_tasks_module_a_window_list_that_arrives_anyway_is_ignored_and_never_logged(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.start()
        assert wait_for(lambda: r.kwin.fullscreen_reports >= 1)
        assert not r.fake.script.sends_windows  # the script was answered {"windows": false}
        answer = r.fake.raw("WindowsState", json.dumps([window(uuid(1), SECRET)]))
        assert json.loads(answer or "") == {"windows": False}
        r.settle()
        assert r.windows == [] and r.kwin.window_reports == 0
        assert not any(SECRET in x for x in r.lines)  # no title in any line, debug included


def test_a_tasks_use_that_exists_at_the_load_turns_the_list_on_with_the_first_answer(
    tmp_path: Path,
) -> None:
    with rig(tmp_path, wanted=True) as r:
        r.fake.script.windows = [window(uuid(1), "One"), window(uuid(2), "Two", active=True)]
        r.start()
        assert wait_for(lambda: len(r.windows) == 1)
        thread, got = r.windows[0]
        assert thread == "fake-loop" and [w.title for w in got] == ["One", "Two"]
        assert got[1].active and len(r.fake.names("loadScript")) == 1  # no reload needed


def test_a_tasks_module_that_comes_later_reloads_the_script_so_the_answer_comes_at_once(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.fake.script.windows = [window(uuid(1), "One")]
        r.start()
        assert wait_for(lambda: r.kwin.fullscreen_reports >= 1)
        assert not r.fake.script.sends_windows
        r.kwin.set_windows_wanted(True)
        assert wait_for(lambda: len(r.windows) == 1)
        assert r.fake.order().count("loadScript") == 2  # a fresh load carried the new answer
        assert r.fake.order().count("unloadScript") == 1
        # the last module leaves: reloaded again, the script is told to stop
        r.kwin.set_windows_wanted(False)
        assert wait_for(lambda: r.fake.order().count("loadScript") == 3)
        assert wait_for(lambda: not r.fake.script.sends_windows and r.fake.script.running)
        before = len(r.windows)
        r.fake.set_windows([window(uuid(2), SECRET)])
        r.settle()
        assert len(r.windows) == before and not any(SECRET in x for x in r.lines)


def test_a_change_of_the_wanted_state_before_the_script_has_spoken_loads_nothing_again(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.fake.script.silent = True  # loaded, has not called yet
        r.start()
        r.kwin.set_windows_wanted(True)
        r.settle()
        r.service.submit(_nothing()).result(5)
        assert r.fake.order().count("loadScript") == 1


async def _nothing() -> None:
    return None


def test_a_malformed_window_list_leaves_the_row_and_is_one_warning_without_its_content(
    tmp_path: Path,
) -> None:
    with rig(tmp_path, wanted=True) as r:
        r.fake.script.windows = [window(uuid(1), "One")]
        r.start()
        assert wait_for(lambda: len(r.windows) == 1)
        for raw in (f'[{{"id": "{SECRET}", "title": 5}}]', f"{SECRET} not json", "{}"):
            r.fake.raw("WindowsState", raw)
        r.settle()
        assert len(r.windows) == 1  # the last list stays
        (warning,) = r.log(level="WARNING")
        assert "not a list of window records" in warning
        assert not any(SECRET in x for x in r.lines)
        # a good list clears the flag: the next malformed one warns again
        r.fake.set_windows([window(uuid(1), "One again")])
        assert wait_for(lambda: len(r.windows) == 2)
        r.fake.raw("WindowsState", "nope")
        assert wait_for(lambda: len(r.log(level="WARNING")) == 2)


def test_a_burst_of_window_lists_reaches_the_loop_as_one_call_with_the_newest(
    tmp_path: Path,
) -> None:
    with rig(tmp_path, wanted=True) as r:
        r.start()
        assert wait_for(lambda: r.kwin.window_reports >= 1)
        r.settle()
        before = len(r.windows)
        r.loop.held = []  # hold what the service hands to the loop
        for n in range(1, 6):
            r.fake.set_windows([window(uuid(n), f"T{n}")])
        assert wait_for(lambda: r.kwin.window_reports >= before + 5)
        r.loop.release()
        r.settle()
        assert len(r.windows) == before + 1  # five reports, one call
        assert [w.title for w in r.windows[-1][1]] == ["T5"]


def test_a_window_list_with_a_surface_of_the_shell_in_it_drops_that_entry(tmp_path: Path) -> None:
    with rig(tmp_path, wanted=True) as r:
        r.fake.script.windows = [
            window(uuid(1), "Mine", "tesserae-shell.panel.launcher"),
            window(uuid(2), "Theirs", "org.example.app"),
        ]
        r.start()
        assert wait_for(lambda: len(r.windows) == 1)
        assert [w.title for w in r.windows[0][1]] == ["Theirs"]


def test_a_wanted_window_list_that_never_comes_is_one_warning_and_not_available(
    tmp_path: Path,
) -> None:
    with rig(tmp_path, wanted=True, silent_after=0.3) as r:
        r.fake.script.windows = []
        # the script answers the first call but never sends the list
        orig = r.fake.script.report_windows

        async def never() -> None:
            return None

        r.fake.script.report_windows = never  # type: ignore[method-assign]
        r.start()
        assert wait_for(lambda: r.kwin.silent)
        assert any("window list was asked for" in x for x in r.log(level="WARNING"))
        r.fake.script.report_windows = orig  # type: ignore[method-assign]


# -- acting on a window -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "marker"),
    [
        ("activate", "workspace.activeWindow = window"),
        ("minimize", "window.minimized = true"),
        ("close", "window.closeWindow()"),
    ],
)
def test_an_action_loads_a_one_shot_script_for_that_window_starts_it_and_unloads_it(
    kind: str, marker: str, tmp_path: Path
) -> None:
    wid = uuid(7)
    with rig(tmp_path) as r:
        r.start()
        assert r.kwin.act(kind, wid).result(5) is True
        (shot,) = r.fake.one_shots()
        assert shot.name.startswith(f"{PACKAGE_ID}-{kind}-") and shot.started
        assert Path(shot.path).parent == tmp_path / "run"
        assert f'"{wid}"' in shot.text and marker in shot.text
        assert "__WINDOW_ID__" not in shot.text
        # it is unloaded again (after KWin has had time to read its file) and its file is gone
        assert wait_for(lambda: not r.fake.loaded(shot.name))
        assert wait_for(lambda: not Path(shot.path).exists())
        assert r.fake.loaded()  # the shell's own script stays


def test_an_action_never_puts_anything_but_a_checked_uuid_into_a_script(tmp_path: Path) -> None:
    with rig(tmp_path) as r:
        r.start()
        for bad in ('x"; evil(); "', "not-a-uuid", "", SECRET, uuid(1)[:-1], "{" + uuid(1) + "}"):
            assert r.kwin.act("close", bad).result(5) is False
        assert r.fake.one_shots() == []
        assert len(r.log(level="WARNING")) == 1  # one warning, not one per attempt
        with pytest.raises(ValueError, match="no such window action"):
            r.kwin.act("format-disk", uuid(1)).result(5)


def test_an_action_does_nothing_while_the_script_is_not_loaded(tmp_path: Path) -> None:
    with rig(tmp_path, kwin_up=False) as r:
        r.start()
        assert r.kwin.act("activate", uuid(1)).result(5) is False
        assert r.fake.calls == []


def test_an_action_script_that_kwin_refuses_is_one_warning_and_leaves_no_file(
    tmp_path: Path,
) -> None:
    with rig(tmp_path) as r:
        r.start()
        r.fake.refuse_load = True
        assert r.kwin.act("close", uuid(1)).result(5) is False
        assert list((tmp_path / "run").glob("*.js")) == []
        assert any("the close script did not load" in x for x in r.log(level="WARNING"))


def test_stopping_unloads_the_one_shot_scripts_that_are_still_loaded(tmp_path: Path) -> None:
    with rig(tmp_path, action_linger=60.0) as r:
        r.start()
        assert r.kwin.act("minimize", uuid(3)).result(5) is True
        (shot,) = r.fake.one_shots()
        assert r.fake.loaded(shot.name)
        r.stop()
        assert not r.fake.loaded(shot.name) and not r.fake.loaded()
        assert list((tmp_path / "run").glob("*.js")) == []


def test_installing_the_package_for_mode_p_copies_it_to_a_temporary_scripts_folder(
    tmp_path: Path,
) -> None:
    folder = install_package(tmp_path / "kwin" / "scripts")
    assert folder.name == PACKAGE_ID
    assert (folder / "metadata.json").is_file() and (folder / "contents/code/main.js").is_file()
    assert (folder / "contents/code/main.js").read_text() == main_script().read_text()
