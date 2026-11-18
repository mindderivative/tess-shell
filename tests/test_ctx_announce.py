"""``ctx.announce`` (tre 0.6.9, ``Window.announce``): what a module may ask for, which use is
asked for, the hop to the loop thread, and what the surface manager does with it. What a screen
reader hears is read in ``tests/test_announce_atspi.py``; the modules' own announcements in
``tests/test_accessibility.py``."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tess_shell.modules.context import ModuleContext
from tess_shell.modules.host import UseRecord
from tess_shell.modules.ticks import TimeSource
from tests.launcher_rig import launcher_desk
from tests.test_launcher import BROWSERS


class Port:
    """The surface manager as the context sees it: records each ``announce``."""

    def __init__(self, result: bool = True) -> None:
        self.calls: list[tuple[list[str], str, str]] = []
        self.result = result

    def announce(self, use_keys: Any, text: str, politeness: str) -> bool:
        self.calls.append((list(use_keys), text, politeness))
        return self.result


def context(
    port: Any, queue: list[Callable[[], None]] | None = None
) -> tuple[ModuleContext, list[UseRecord]]:
    uses = [UseRecord(f"M@u{i}", f"S.M.B.M_{i}", f"u{i}", "Main", {}) for i in (1, 2)]
    ctx = ModuleContext(
        "M",
        "uid",
        {},
        {u.key: u for u in uses},
        lambda use, key, value: None,
        TimeSource(),
        call_soon=(lambda: queue.append) if queue is not None else None,
        surfaces=(lambda: port) if port is not None else None,
    )
    return ctx, uses


def test_a_text_that_is_empty_and_a_politeness_that_is_unknown_raise_ValueError() -> None:
    port = Port()
    ctx, _ = context(port)
    for text in ("", "   "):
        with pytest.raises(ValueError, match="not empty"):
            ctx.announce(text)
    with pytest.raises(ValueError, match="polite"):
        ctx.announce("Hi", politeness="loud")
    assert port.calls == []


def test_with_no_use_every_use_is_offered_in_order_and_with_a_use_only_that_one() -> None:
    port = Port()
    ctx, (first, second) = context(port)
    ctx.announce("Hi")
    ctx.announce("Urgent", politeness="assertive", use=second)
    ctx.announce("By key", use=first.key)
    assert port.calls == [
        ([first.key, second.key], "Hi", "polite"),
        ([second.key], "Urgent", "assertive"),
        ([first.key], "By key", "polite"),
    ]


def test_an_announcement_waits_for_the_loop_and_is_dropped_when_the_module_stopped() -> None:
    port = Port()
    queue: list[Callable[[], None]] = []
    ctx, _ = context(port, queue)
    done = threading.Thread(target=lambda: ctx.announce("From a thread"))
    done.start()
    done.join()
    assert port.calls == [] and len(queue) == 1  # nothing touches the window off the loop
    queue.pop()()
    assert [text for _, text, _ in port.calls] == ["From a thread"]
    ctx.announce("Too late")
    ctx._closed = True  # the module stopped before the loop got to it
    queue.pop()()
    assert [text for _, text, _ in port.calls] == ["From a thread"]


def test_a_shell_without_surfaces_says_nothing_and_does_not_raise() -> None:
    ctx, _ = context(None)
    ctx.announce("Nobody is there")
    port = Port(result=False)  # no use of the module is on an open window
    ctx, _ = context(port)
    ctx.announce("Not on a window")
    assert len(port.calls) == 1


def test_the_manager_says_it_on_the_open_window_of_a_use_and_nothing_for_an_unknown_one(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        (key,) = d.w.host.loaded["Applications"].instance.ctx.uses
        assert d.w.manager.announce(["nope", key], "Said", "polite") is True
        assert d.w.manager.announce(["nope"], "Said", "polite") is False
