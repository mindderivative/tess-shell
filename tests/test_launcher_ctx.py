"""What a module gets for the launcher (``ctx.apps``, ``ctx.surface``): the calls of the Module
Context that ``Applications`` is built on, on the launcher rig of ``tests/launcher_rig.py`` (a
recorded starter, temporary entries)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tess_shell.modules.context import ModuleContext
from tests.launcher_rig import Desk, launcher_desk
from tests.widgets_live import running

ENTRIES = {"One": {"Exec": "fake-app --one"}, "Two": {"Exec": "fake-app --two"}}


def ctx_of(d: Desk) -> ModuleContext:
    return d.w.host.loaded["Applications"].ctx


def test_a_surface_watcher_hears_each_show_with_the_use_keys_until_it_is_cancelled(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, ENTRIES) as d:
        heard: list[tuple[str, ...]] = []
        sub = d.w.manager.watch_shown(heard.append)
        d.toggle()  # shown
        d.toggle()  # hidden: no call
        d.toggle()  # shown again
        assert len(heard) == 2 and all(k[0].startswith("Applications@") for k in heard)
        sub.cancel()
        d.toggle()
        d.toggle()
        assert len(heard) == 2


def test_hide_and_focus_name_what_they_could_not_do_and_nothing_is_raised(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, ENTRIES) as d:
        manager = d.w.manager
        assert manager.hide_use("Nothing@nowhere") is False
        assert manager.focus_block("Nothing@nowhere", "query") is False
        (use,) = ctx_of(d).uses.values()
        assert manager.focus_block(use.key, "no-such-block") is False
        d.toggle()
        # the field takes the focus by the name the layout gave the call
        assert manager.focus_block(use.key, "query", select_all=True) is True
        assert d.field().get("focused")
        # outside an action there is no caller: the module has to say which use
        assert ctx_of(d).surface.hide() is False
        assert not d.hidden
        assert ctx_of(d).surface.hide(use) is True
        assert d.hidden


def test_request_token_gives_none_for_a_use_on_no_window(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, ENTRIES) as d:
        got: list[Any] = []
        d.w.manager.request_token("Nothing@nowhere", got.append)
        assert got == [None]


def test_launch_with_no_use_and_no_caller_starts_without_asking_for_a_token(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, ENTRIES) as d:
        done: list[Any] = []
        ctx_of(d).apps.launch("one", on_done=done.append)  # no use: no surface to ask
        assert d.settle(lambda: done) and done[0].ok
        assert d.runner.started[0].argv[-2:] == ("fake-app", "--one")
        assert "XDG_ACTIVATION_TOKEN" not in d.runner.started[0].env


def test_refresh_builds_the_list_again_only_when_the_folders_are_not_watched(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, ENTRIES) as d:
        apps = ctx_of(d).apps
        assert d.apps.watching is False  # the rig never watched the folders
        before = d.apps.stats.builds
        apps.refresh()
        assert d.settle(lambda: d.apps.stats.builds == before + 1)
        d.apps.index.watching = True  # as after a successful inotify watch
        apps.refresh()
        d.settle(lambda: False, 0.2)
        assert d.apps.stats.builds == before + 1  # a watched index tells by itself


def test_a_module_that_stops_cancels_its_subscriptions(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, ENTRIES) as d:
        ctx = ctx_of(d)
        assert d.apps._listeners  # the module's on_changed
        assert d.w.manager._shown_listeners
        d.w.host.stop_all()
        assert not d.apps._listeners and not d.w.manager._shown_listeners
        assert ctx._apps is None and ctx._surface is None


def test_a_shell_with_no_application_service_or_surfaces_says_so() -> None:
    with running("Label { Text: x }") as w:
        ctx = w.host.loaded["Driver"].ctx
        w.host.apps = None
        w.host.surfaces = None
        with pytest.raises(RuntimeError, match="no application service"):
            ctx.apps  # noqa: B018
        with pytest.raises(RuntimeError, match="no surfaces"):
            ctx.surface  # noqa: B018
