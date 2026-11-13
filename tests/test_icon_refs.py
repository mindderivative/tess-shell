"""What the Tray needs of the shell besides the D-Bus layer: icon references (``pixels:...``) that a
block's ``Icon:`` and a Bitmap's ``Source`` accept, and the members ``ctx.icons``, ``ctx.tray``,
``ctx.call_soon`` and ``ctx.is_popup_open`` of the module context."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest
from loguru import logger

from tess_shell.binder import images
from tess_shell.binder.images import ImageCache
from tess_shell.binder.model import PIXELS_PREFIX
from tess_shell.model.icons import RuntimeIcons
from tess_shell.modules.context import ModuleContext
from tess_shell.modules.ticks import TimeSource
from tests.test_popup import Port


def test_registered_pixels_have_one_reference_for_the_same_pixels_and_load_like_a_file() -> None:
    cache = ImageCache()
    red = bytes([255, 0, 0, 255]) * 4
    ref = cache.register(2, 2, red)
    assert ref.startswith(PIXELS_PREFIX)
    assert cache.register(2, 2, red) == ref  # the same pixels, the same reference
    assert cache.register(1, 4, red) != ref  # the same bytes in another shape are other pixels
    pixels = cache.load(ref)
    assert (pixels.width, pixels.height, pixels.rgba) == (2, 2, red)
    cache.clear()  # the cache of files goes; what was registered stays
    assert cache.load(ref).rgba == red


def test_an_unknown_reference_shows_the_error_image_with_one_warning() -> None:
    cache = ImageCache()
    lines: list[str] = []
    sink = logger.add(lines.append, level="WARNING", format="{message}")
    try:
        gone = cache.load(f"{PIXELS_PREFIX}deadbeef")
        again = cache.load(f"{PIXELS_PREFIX}deadbeef")
    finally:
        logger.remove(sink)
    assert gone == again == cache.error_image()
    assert len([x for x in lines if "deadbeef" in x]) == 1


def test_the_least_recently_used_references_go_when_the_registry_is_over_its_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(images, "REGISTERED_BUDGET", 100)
    cache = ImageCache()
    a = cache.register(5, 5, bytes([1]) * 100)
    b = cache.register(5, 5, bytes([2]) * 100)  # over the budget: a goes
    assert cache.load(b).rgba[0] == 2
    assert cache.load(a) == cache.error_image()


def test_registering_from_a_worker_thread_is_safe() -> None:
    cache = ImageCache()
    refs: list[str] = []

    def work(n: int) -> None:
        for i in range(50):
            refs.append(cache.register(1, 1, bytes([n, i % 7, 0, 255])))

    threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(refs) == 200 and all(cache.load(r).width == 1 for r in set(refs))


class Icons:
    def lookup(self, name: str) -> str | None:
        return "<svg/>" if name == "mdi:home" else None

    def nearest(self, name: str) -> list[str]:
        return []


def test_an_icon_slot_passes_a_document_and_pixels_through_and_looks_a_name_up() -> None:
    icons = RuntimeIcons(Icons())
    assert icons.document("<svg id='x'/>") == "<svg id='x'/>"
    assert icons.document(f"{PIXELS_PREFIX}abc123") == f"{PIXELS_PREFIX}abc123"
    assert icons.document("mdi:home") == "<svg/>"


def context(**kwargs: Any) -> ModuleContext:
    return ModuleContext("M", "uid", {}, {}, lambda use, key, value: None, TimeSource(), **kwargs)


def test_the_context_has_icons_tray_and_call_soon_only_where_the_shell_gave_them() -> None:
    ctx = context()
    for name in ("icons", "tray"):
        with pytest.raises(RuntimeError, match="no .* service"):
            getattr(ctx, name)
    with pytest.raises(RuntimeError, match="no loop"):
        ctx.call_soon(lambda: None)
    assert ctx.is_popup_open("P") is False  # no surfaces: nothing is open


class Helper:
    def __init__(self, module: str) -> None:
        self.module, self.closed = module, False

    def close(self) -> None:
        self.closed = True


class HelperPort:
    def __init__(self) -> None:
        self.made: list[Helper] = []

    def for_module(self, module: str) -> Helper:
        helper = Helper(module)
        self.made.append(helper)
        return helper


def test_the_helpers_are_made_once_per_module_and_the_tray_one_is_closed_with_the_module() -> None:
    icons, tray = HelperPort(), HelperPort()
    ctx = context(icons=lambda: icons, tray=lambda: tray)  # type: ignore[arg-type]
    assert ctx.icons is ctx.icons and ctx.tray is ctx.tray  # type: ignore[comparison-overlap]
    assert [h.module for h in icons.made + tray.made] == ["M", "M"]
    ctx.close()
    assert tray.made[0].closed is True


def boom() -> None:
    raise ZeroDivisionError


def test_call_soon_runs_on_the_loop_logs_what_raises_and_drops_after_the_module_stopped() -> None:
    queue: list[Callable[[], None]] = []
    ctx = context(call_soon=lambda: queue.append)
    ran: list[int] = []
    ctx.call_soon(lambda: ran.append(1))
    ctx.call_soon(boom)  # logged with the module's name, not raised into the loop
    lines: list[str] = []
    sink = logger.add(lines.append, level="ERROR", format="{message}")
    try:
        for fn in queue:
            fn()
        assert ran == [1] and any("call_soon callback raised" in x for x in lines)
        queue.clear()
        ctx.call_soon(lambda: ran.append(2))
        ctx.close()  # the module stopped: what was queued is dropped
        for fn in queue:
            fn()
    finally:
        logger.remove(sink)
    assert ran == [1]


def test_is_popup_open_asks_the_surface_manager() -> None:
    port = Port()
    ctx = context(popups=lambda: port)
    assert ctx.is_popup_open("Tray_Menu") is False
    port.is_open = lambda name: name == "Tray_Menu"  # type: ignore[method-assign]
    assert ctx.is_popup_open("Tray_Menu") is True and ctx.is_popup_open("Other") is False
