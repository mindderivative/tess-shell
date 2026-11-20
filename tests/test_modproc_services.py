"""The shell's services as a module in a process sees them: every call lands on the shell's own
helper of the process's context, and what the service says comes back as the contract has it (same
classes, same threads, tuples as tuples). The services behind are fakes (a private bus for D-Bus);
the process is real."""

from __future__ import annotations

import concurrent.futures
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tess_shell.binder.model import Handler
from tess_shell.modules.host import LoadedModule
from tess_shell.services.api import (
    AppInfo,
    AudioError,
    AudioState,
    LaunchResult,
    Output,
    WindowInfo,
)
from tess_shell.services.bus import ServiceThread
from tess_shell.services.layer import Layer
from tests.fake_dbus import HAVE_DAEMON, FakeBus, fake_bus
from tests.modproc_rig import ProcRig, new_rig


class Sub:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakePopups:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.open: set[str] = set()
        self.threads: set[int] = set()

    def call(self, module: str, use: Any, name: str, data: Any, anchor: Any = None) -> None:
        self.threads.add(threading.get_ident())
        self.calls.append((module, use, name, data, anchor))
        self.open.add(name)

    def close_named(self, name: str | None = None) -> None:
        self.calls.append(("close", name))
        self.open.discard(name or "")

    def update_data(self, name: str, data: Mapping[str, Any]) -> bool:
        self.calls.append(("update", name, dict(data)))
        return name in self.open

    def is_open(self, name: str) -> bool:
        return name in self.open


class FakeSurfaces:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.shown: Callable[[tuple[str, ...]], None] | None = None
        self.sub = Sub()

    def hide_use(self, use_key: str) -> bool:
        self.calls.append(("hide", use_key))
        return True

    def show_use(self, use_key: str, hide_after: float | None = None) -> bool:
        self.calls.append(("show", use_key, hide_after))
        return False

    def watch_shown(self, callback: Callable[[tuple[str, ...]], None]) -> Sub:
        self.shown = callback
        return self.sub

    def focus_block(self, use_key: str, name: str, select_all: bool = False) -> bool:
        self.calls.append(("focus", use_key, name, select_all))
        return True

    def request_token(self, use_key: str, callback: Callable[[str | None], None]) -> None:
        callback("token-123")

    def announce(self, use_keys: Sequence[str], text: str, politeness: str) -> bool:
        self.calls.append(("announce", list(use_keys), text, politeness))
        return True


class FakeFocus:
    def __init__(self) -> None:
        self.default: str | None = "Frame"
        self.modes: list[tuple[str, bool]] = []

    def get_default(self) -> str | None:
        return self.default

    def set_default(self, name: str | None, who: str = "") -> None:
        self.default = name

    def set_mode(self, name: str, value: bool, who: str = "") -> bool:
        self.modes.append((name, value))
        return name == "Dock"


APP = AppInfo(
    "firefox", "Firefox", "Browser", "a browser", "mdi:web", ("web",), False, "/x/firefox.desktop"
)


class FakeApps:
    ready = True
    watching = True

    def __init__(self) -> None:
        self.launched: list[tuple[str, str | None]] = []
        self.changed: Callable[[], None] | None = None
        self.sub = Sub()

    def start(self) -> None: ...

    def search(self, query: str, limit: int = 8) -> list[AppInfo]:
        return [APP] if "fire" in query else []

    def get(self, entry_id: str) -> AppInfo | None:
        return APP if entry_id.removesuffix(".desktop") == "firefox" else None

    def launch(
        self,
        entry_id: str,
        token: str | None = None,
        on_done: Callable[[LaunchResult], None] | None = None,
    ) -> None:
        self.launched.append((entry_id, token))
        if on_done is not None:
            on_done(LaunchResult(True, "", "Firefox"))

    def on_changed(self, callback: Callable[[], None]) -> Sub:
        self.changed = callback
        return self.sub

    def refresh(self) -> None: ...


class FakeIcons:
    def for_module(self, module: str) -> FakeIcons:
        return self

    def theme_icon(self, name: str, size: int, theme_path: str | None = None) -> str | None:
        return None if name == "missing" else f"<svg>{name}:{size}:{theme_path}</svg>"

    def pixmap_icon(self, pixmaps: Sequence[Sequence[Any]], size: int, source: str = "") -> str:
        return f"pixels:{len(pixmaps)}:{size}"

    def png_icon(self, data: bytes, source: str = "") -> str:
        return f"pixels:png:{len(data)}:{data[:2]!r}"

    def app_icon(self, app: str, size: int) -> str:
        return f"app:{app}:{size}"

    def app_name(self, app: str) -> str:
        return app.title()

    def on_theme_changed(self, callback: Callable[[], None]) -> Sub:
        self.changed = callback
        return Sub()

    def close(self) -> None: ...


WINDOW = WindowInfo("w1", "Title", "firefox", True, False, ("d0",), "DP-1", False)


class FakeWindows:
    available = True
    ready = True

    def __init__(self) -> None:
        self.callback: Callable[[], None] | None = None
        self.items: tuple[WindowInfo, ...] = ()
        self.activated: list[str] = []

    def for_module(self, module: str) -> FakeWindows:
        return self

    def list(self) -> tuple[WindowInfo, ...]:
        return self.items

    def on_changed(self, callback: Callable[[], None]) -> Sub:
        self.callback = callback
        return Sub()

    def activate(self, window_id: str) -> concurrent.futures.Future[bool]:
        self.activated.append(window_id)
        done: concurrent.futures.Future[bool] = concurrent.futures.Future()
        done.set_result(True)
        return done

    def minimize(self, window_id: str) -> concurrent.futures.Future[bool]:
        return self.activate(window_id)

    def close_window(self, window_id: str) -> concurrent.futures.Future[bool]:
        return self.activate(window_id)

    def close(self) -> None: ...


OUT = Output("sink1", "Speakers", "SPEAKER")
STATE = AudioState(OUT, 42, False, True, False, (OUT,))


class FakeAudio:
    available = True

    def __init__(self) -> None:
        self.callback: Callable[[AudioState | None], None] | None = None
        self.volumes: list[float] = []
        self.sub = Sub()

    def for_module(self, module: str) -> FakeAudio:
        return self

    @property
    def state(self) -> AudioState:
        return STATE

    def on_changed(self, callback: Callable[[AudioState | None], None]) -> Sub:
        self.callback = callback
        callback(STATE)
        return self.sub

    def set_volume(self, percent: float) -> concurrent.futures.Future[None]:
        self.volumes.append(percent)
        done: concurrent.futures.Future[None] = concurrent.futures.Future()
        done.set_result(None)
        return done

    def set_output(self, name: str) -> concurrent.futures.Future[None]:
        done: concurrent.futures.Future[None] = concurrent.futures.Future()
        done.set_exception(AudioError(f"no output {name}"))
        return done

    def close(self) -> None: ...


class FakeTray:
    def __init__(self) -> None:
        self.sub = Sub()

    def for_module(self, module: str) -> FakeTray:
        return self

    def on_host(self, callback: Callable[[bool], None]) -> Sub:
        callback(True)
        return self.sub

    def close(self) -> None: ...


class Shell:
    def __init__(self, rig: ProcRig) -> None:
        self.rig = rig
        self.popups, self.surfaces, self.focus = FakePopups(), FakeSurfaces(), FakeFocus()
        self.apps, self.windows, self.audio, self.tray = (
            FakeApps(),
            FakeWindows(),
            FakeAudio(),
            FakeTray(),
        )
        host = rig.host
        host.popups = self.popups  # type: ignore[assignment]
        host.surfaces = self.surfaces  # type: ignore[assignment]
        host.focus = self.focus  # type: ignore[assignment]
        host.apps = self.apps  # type: ignore[assignment]
        host.icons = FakeIcons()  # type: ignore[assignment]
        host.windows = self.windows  # type: ignore[assignment]
        host.audio = self.audio  # type: ignore[assignment]
        host.tray = self.tray  # type: ignore[assignment]

    def run(self, name: str, code: str) -> LoadedModule:
        loaded, findings = self.rig.load(name, code)
        assert loaded is not None and findings == [], findings
        assert self.rig.host.start(loaded) == []
        return loaded


@pytest.fixture(name="rig")
def rig_fixture(tmp_path: Path) -> Iterator[ProcRig]:
    yield from new_rig(tmp_path)


@pytest.fixture
def shell(rig: ProcRig) -> Shell:
    return Shell(rig)


def test_popups_open_close_update_and_ask_whether_they_are_open(shell: Shell) -> None:
    code = """
from tess_shell import Module, action

class Pp(Module):
    @action
    def go(self, event):
        self.ctx.popup("menu", {"n": 1}, use="Pp@u1", anchor=(1.0, 2.0, 3.0, 4.0))
        self.ctx.send("open", self.ctx.is_popup_open("menu"))
        self.ctx.send("updated", self.ctx.update_popup("menu", {"n": 2}))
        self.ctx.close_popup("menu")
        self.ctx.send("after", self.ctx.is_popup_open("menu"))
"""
    shell.run("Pp", code)
    result = shell.rig.host.call_action("Pp", "go", [])
    shell.rig.pump(result.done)
    assert shell.rig.wait_value("Pp@u1", "after") is False
    assert shell.rig.value("Pp@u1", "open") is True and shell.rig.value("Pp@u1", "updated") is True
    assert shell.popups.calls[0] == ("Pp", "Pp@u1", "menu", {"n": 1}, (1.0, 2.0, 3.0, 4.0))
    assert shell.popups.threads == {threading.get_ident()}, "a popup opens on the shell's loop"
    assert ("update", "menu", {"n": 2}) in shell.popups.calls and (
        "close",
        None,
    ) not in shell.popups.calls


def test_a_synchronous_request_the_shell_does_not_answer_times_out_naming_the_module_and_call(
    shell: Shell, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shell's loop does not run here (nothing pumps while the module waits): the member
    raises ``ShellCallTimeout``, and the message says which module asked what."""
    monkeypatch.setenv("TESS_SHELL_TEST_WATCHDOG_SCALE", "0.1")
    code = """
from tess_shell import Module, ShellCallTimeout, action

class Slow(Module):
    @action
    def ask(self, event):
        try:
            self.ctx.is_popup_open("menu")
        except ShellCallTimeout as exc:  # caught by name: it is part of the module API
            self.ctx.send("error", [type(exc).__name__, str(exc)])
"""
    shell.run("Slow", code)
    shell.rig.host.dispatch(Handler("ask", use="Slow@u1"), "On_Click", None)
    time.sleep(0.05)
    # only the pipe is read here: the request is a loop-mode one, nobody runs the loop
    end = time.monotonic() + 15
    while shell.rig.value("Slow@u1", "error") is None and time.monotonic() < end:
        time.sleep(0.01)
        shell.rig.store.flush()  # what the reader thread queued, applied here, not by the loop
    error = shell.rig.value("Slow@u1", "error")
    assert error is not None and error[0] == "ShellCallTimeout"
    assert "module Slow" in error[1] and "popup.is_open" in error[1] and "0.2 s" in error[1]


def test_surface_focus_announce_and_a_use_that_is_not_the_modules(shell: Shell) -> None:
    code = """
from tess_shell import Module, action

class Sf(Module):
    def start(self):
        self.ctx.surface.on_shown(lambda use: self.ctx.send("shown", use.key))

    @action
    def go(self, event):
        self.ctx.send("hide", self.ctx.surface.hide(use="Sf@u1"))
        self.ctx.send("show", self.ctx.surface.show(use="Sf@u1", hide_after=500))
        self.ctx.send("focus", self.ctx.surface.focus("Query", select_all=True, use="Sf@u1"))
        self.ctx.focus.default = "Dock"
        self.ctx.send("default", self.ctx.focus.default)
        focus = self.ctx.focus
        self.ctx.send("mode", [focus.set_mode("Dock", True), focus.set_mode("X", True)])
        self.ctx.announce("hello", politeness="assertive")
        try:
            self.ctx.surface.hide(use="Other@u1")
        except Exception as exc:
            self.ctx.send("foreign", [type(exc).__name__, str(exc)])
        try:
            self.ctx.announce("")
        except ValueError as exc:
            self.ctx.send("empty", str(exc))
"""
    shell.run("Sf", code)
    shell.rig.pump(lambda: shell.surfaces.shown is not None)
    shell.surfaces.shown(("Sf@u1", "Other@u9"))  # type: ignore[misc]
    assert shell.rig.wait_value("Sf@u1", "shown") == "Sf@u1"
    result = shell.rig.host.call_action("Sf", "go", [])
    shell.rig.pump(result.done)
    shell.rig.wait_value("Sf@u1", "empty")
    value = shell.rig.value
    assert [value("Sf@u1", k) for k in ("hide", "show", "focus", "default", "mode")] == [
        True,
        False,
        True,
        "Dock",
        [True, False],
    ]
    assert (
        value("Sf@u1", "foreign")[0] == "ValueError"
        and "not a use of this module" in value("Sf@u1", "foreign")[1]
    )
    assert ("hide", "Sf@u1") in shell.surfaces.calls and (
        "show",
        "Sf@u1",
        500,
    ) in shell.surfaces.calls
    assert ("focus", "Sf@u1", "Query", True) in shell.surfaces.calls
    # ctx.announce hops to the module's loop (as it hops to the shell's): it arrives a moment later
    shell.rig.pump(lambda: ("announce", ["Sf@u1"], "hello", "assertive") in shell.surfaces.calls)
    assert "Other@u1" not in [c[1] for c in shell.surfaces.calls if c[0] == "hide"]


def test_applications_icons_and_their_callbacks(shell: Shell) -> None:
    code = """
from tess_shell import Module, action

class Ap(Module):
    def start(self):
        self.ctx.apps.on_changed(lambda: self.ctx.send("changed", True))
        self.ctx.icons.on_theme_changed(lambda: self.ctx.send("theme", True))

    @action
    def go(self, event):
        apps = self.ctx.apps
        found = apps.search("fire")
        self.ctx.send("search", [apps.ready, [(a.id, a.keywords) for a in found],
                                 apps.get("firefox.desktop").name, apps.get("none") is None])
        apps.launch("firefox", use="Ap@u1", on_done=lambda r: self.ctx.send("done", [r.ok, r.name]))
        icons = self.ctx.icons
        missing = icons.theme_icon("missing", 16) is None
        self.ctx.send("icons", [icons.theme_icon("mail", 16, "/t"), missing,
                                icons.png_icon(b"\\x89P", "x"),
                                icons.pixmap_icon([[1, 2, b"ab"]], 22),
                                icons.app_icon("a", 8), icons.app_name("kate")])
"""
    shell.run("Ap", code)
    result = shell.rig.host.call_action("Ap", "go", [])
    shell.rig.pump(result.done)
    assert shell.rig.wait_value("Ap@u1", "done") == [True, "Firefox"]
    assert shell.rig.value("Ap@u1", "search") == [True, [["firefox", ["web"]]], "Firefox", True]
    assert shell.rig.value("Ap@u1", "icons") == [
        "<svg>mail:16:/t</svg>",
        True,
        "pixels:png:2:b'\\x89P'",
        "pixels:1:22",
        "app:a:8",
        "Kate",
    ]
    assert shell.apps.launched == [("firefox", "token-123")], "the token came from the surface"
    shell.rig.pump(lambda: shell.apps.changed is not None)
    shell.apps.changed()  # type: ignore[misc]
    assert shell.rig.wait_value("Ap@u1", "changed") is True


def test_windows_audio_and_tray_state_is_pushed_and_setters_answer_with_the_services_errors(
    shell: Shell,
) -> None:
    code = """
from tess_shell import Module, action

class Sv(Module):
    def start(self):
        self.ctx.windows.on_changed(self.windows_changed)
        self.ctx.audio.on_changed(self.audio_changed)
        self.ctx.tray.on_host(lambda hosted: self.ctx.send("hosted", hosted))

    def windows_changed(self):
        w = self.ctx.windows
        listed = [(x.id, x.title, x.desktops) for x in w.list()]
        self.ctx.send("windows", [w.available, w.ready, listed])

    def audio_changed(self, state):
        self.ctx.send("audio", [state.volume, state.output.description, state.outputs[0].kind,
                                self.ctx.audio.state.volume])

    @action
    def go(self, event):
        self.ctx.send("activated", self.ctx.windows.activate("w1").result(5))
        self.ctx.audio.set_volume(70).result(5)
        try:
            self.ctx.audio.set_output("nope").result(5)
        except Exception as exc:
            self.ctx.send("audio_error", [type(exc).__name__, str(exc)])
"""
    shell.run("Sv", code)
    assert shell.rig.wait_value("Sv@u1", "hosted") is True
    assert shell.rig.wait_value("Sv@u1", "audio") == [42, "Speakers", "SPEAKER", 42]
    shell.rig.pump(lambda: shell.windows.callback is not None)
    shell.windows.items = (WINDOW,)
    shell.windows.callback()  # type: ignore[misc]
    assert shell.rig.wait_value("Sv@u1", "windows") == [True, True, [["w1", "Title", ["d0"]]]]
    result = shell.rig.host.call_action("Sv", "go", [])
    shell.rig.pump(result.done)
    assert shell.rig.wait_value("Sv@u1", "audio_error") == ["AudioError", "no output nope"]
    assert shell.rig.value("Sv@u1", "activated") is True
    assert shell.windows.activated == ["w1"] and shell.audio.volumes == [70]


def test_ticks_come_from_the_shells_one_time_source_and_stop_when_cancelled(shell: Shell) -> None:
    code = """
from tess_shell import Module

class Tk(Module):
    def start(self):
        self.n = 0
        self.sub = self.ctx.on_tick("second", self.tick)

    def tick(self):
        self.n += 1
        self.ctx.send("ticks", self.n)
        if self.n == 2:
            self.sub.cancel()
"""
    shell.run("Tk", code)
    shell.rig.wait_value("Tk@u1", "ticks", 2, timeout=10)
    shell.rig.pump(lambda: not shell.rig.ticks._subs)
    time.sleep(1.3)
    shell.rig.pump(lambda: True)
    assert shell.rig.value("Tk@u1", "ticks") == 2, "a cancelled subscription ticks no more"
    with pytest.raises(ValueError, match="'second' or 'minute'"):
        shell.rig.host.loaded["Tk"].ctx.on_tick("hour", lambda: None)


def test_a_modules_subscriptions_in_the_shell_end_with_it(shell: Shell) -> None:
    code = """
from tess_shell import Module

class En(Module):
    def start(self):
        self.ctx.audio.on_changed(lambda state: None)
        self.ctx.surface.on_shown(lambda use: None)
        self.ctx.apps.on_changed(lambda: None)
"""
    loaded = shell.run("En", code)
    shell.rig.pump(lambda: shell.apps.changed is not None and shell.surfaces.shown is not None)
    shell.rig.host.stop_all()
    assert loaded.state == "stopped"
    assert shell.audio.sub.cancelled and shell.surfaces.sub.cancelled and shell.apps.sub.cancelled


# -- D-Bus (a private bus) ------------------------------------------------------------------------

NAME, PATH, IFACE = "org.test.Battery", "/org/test/Battery", "org.test.Battery"


class DBusWorld:
    def __init__(self, rig: ProcRig, bus: FakeBus) -> None:
        self.fake = bus.service(NAME)
        self.obj = self.fake.add(
            PATH,
            IFACE,
            properties={"Percentage": ("d", 50.0)},
            methods={"Echo": (["s", "i"], "si", lambda s, i: [s, i + 1])},
            signals={"Ping": "su"},
            writable=["Percentage"],
        )
        self.fake.up()
        self.service = ServiceThread(bus.address)
        self.service.start()
        self.layer = Layer(self.service, rig.queue.put)
        rig.host.dbus = self.layer  # type: ignore[assignment]

    def close(self) -> None:
        self.service.stop()


DBUS_MODULE = """
import threading
from tess_shell import Module, action

class Db(Module):
    def start(self):
        bus = self.ctx.dbus.session()
        self.proxy = bus.proxy("org.test.Battery", "/org/test/Battery", "org.test.Battery")
        self.proxy.on_property_changed(self.changed)
        self.proxy.on_signal("Ping", lambda *body: self.ctx.send("signal", list(body)))
        self.ctx.send("started", True)

    def changed(self, values):
        if "Percentage" in values:
            self.ctx.send("pct", [values["Percentage"], threading.current_thread().name])

    def on_service_lost(self, name):
        self.ctx.send("lost", [name, self.ctx.dbus.available])

    def on_service_found(self, name):
        self.ctx.send("found", [name, self.ctx.dbus.available])

    @action
    def ask(self, event):
        threading.Thread(target=self.work).start()

    def work(self):
        bus = self.ctx.dbus.session()
        try:
            got = bus.run_blocking(self.proxy.get("Percentage", fresh=True), timeout=10)
            echo = bus.run_blocking(self.proxy.call("Echo", ["x", 7], "si"), timeout=10)
            bus.run_blocking(self.proxy.set("Percentage", 12.5, "d"), timeout=10)
            self.ctx.send("answers", [got, list(echo), type(echo).__name__])
        except Exception as exc:
            self.ctx.send("answers", ["error", type(exc).__name__, str(exc)])
        try:
            ghost = bus.proxy("org.test.Ghost", "/g", "org.test.Ghost", optional=True)
            bus.run_blocking(ghost.call("Nope", [], ""), timeout=10)
        except Exception as exc:
            self.ctx.send("ghost", type(exc).__name__)
        try:
            self.ctx.send("blocking_on_loop", "no error")
            bus.run_blocking(self.proxy.get("Percentage"))
        except Exception as exc:
            pass
"""


@pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")
def test_dbus_calls_properties_signals_and_the_hooks_go_through_the_shells_layer(
    rig: ProcRig,
) -> None:
    shell = Shell(rig)
    with fake_bus() as bus:
        world = DBusWorld(rig, bus)
        try:
            shell.run("Db", DBUS_MODULE)
            # the first state, then a change, both on the process's service thread
            pct = rig.wait_value("Db@u1", "pct")
            assert pct[0] == 50.0 and pct[1] == "module-service"
            result = rig.host.call_action("Db", "ask", [])
            rig.pump(result.done)
            answers = rig.wait_value("Db@u1", "answers")
            assert answers == [50.0, ["x", 8], "tuple"], answers
            assert world.obj.sets and world.obj.sets[-1][1] == 12.5
            assert rig.wait_value("Db@u1", "ghost") == "ServiceUnavailable"
            world.obj.set("Percentage", 77.0)
            rig.pump(
                lambda: (
                    rig.value("Db@u1", "pct") is not None and rig.value("Db@u1", "pct")[0] == 77.0
                )
            )
            world.obj.emit("Ping", "hello", 3)
            assert rig.wait_value("Db@u1", "signal") == ["hello", 3]
            # the layer's `available` reaches the module's view of it, and the hooks run in it
            rig.pump(lambda: rig.value("Db@u1", "available") is True)
            world.fake.down()
            lost = rig.wait_value("Db@u1", "lost")
            assert lost == [NAME, False]
            assert rig.value("Db@u1", "available") is False
            world.fake.up()
            assert rig.wait_value("Db@u1", "found") == [NAME, True]
        finally:
            world.close()


def test_shell_call_timeout_is_exported_and_is_a_runtime_error_in_both_places() -> None:
    """A module author imports it from ``tess_shell``; the class the child raises is that class, and
    it stays a ``RuntimeError``, so an ``except RuntimeError`` written before the export works."""
    import tess_shell
    from tess_shell.modproc import childctx

    assert tess_shell.ShellCallTimeout is childctx.ShellCallTimeout
    assert issubclass(tess_shell.ShellCallTimeout, RuntimeError)
    assert "ShellCallTimeout" in tess_shell.__all__
