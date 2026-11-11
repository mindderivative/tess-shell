"""A new desktop look (light or dark) reaches everything a peek draws: the Frame's fill and border,
a melded Panel's content and text, a strip's content, and the handles (their colour comes from the
Frame's inner border). Headless; the test theme's Surface and On_Surface change with the mode."""

from __future__ import annotations

from typing import Any

import pytest

from tess_shell.appearance import Appearance
from tess_shell.model.store import ValueStore
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_frame import StubApp, look, only
from tests.test_frame_peek import act, advance, host, px
from tests.test_frame_strips import module, shell_of

FRAME = (
    "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
    "Inner_Border { Width: 2, Color: $color.on_surface }, "
    "Style { Background: $color.surface }, "
    "Edges { Left { Thickness: 40, Name: Side, Children { Rectangle { Name: Chip, Width: 10, "
    "Height: 10, Fill: $color.on_surface } }, Peek { Size: 8, Trigger: CLICK } } } }"
)
PANEL = (
    "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, Length: 120, "
    "Depth: 40, Peek { Size: 12, Trigger: CLICK }, Animation { Type: SLIDE, Duration: 400 }, "
    "Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: $color.on_surface }, "
    'Text { Name: Label, Text: "x", Foreground: $color.on_surface } } }'
)


def themed() -> SurfaceManager:
    app, store = StubApp(), ValueStore()
    m = SurfaceManager(app, module(), lambda key: key[-1], store, look(), blend_mode="SRGB")  # type: ignore[arg-type]
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(FRAME, PANEL))
    m.build()
    only(m).painter.resize(*app.size)
    only(m).painter.snapshot()
    return m


def switch(m: SurfaceManager, scheme: str) -> None:
    m.set_look(m.look.with_appearance(Appearance(scheme=scheme)))  # type: ignore[arg-type]


def colours(m: SurfaceManager) -> dict[str, Any]:
    st = only(m)
    tab = host(m)
    side = next(h for h in st.hosts.values() if h.plan.name == "Side")
    nodes = tab.surface.view.nodes
    return {
        "fill": st.nodes[1].get("fill"),
        "border": st.nodes[2].get("fill"),
        "dot": nodes["Dot"].get("fill"),
        "text": nodes["Label"].get("fill"),
        "chip": side.surface.view.nodes["Chip"].get("fill"),
        "handle": tab.handle.colour,
        "handle_node": tab.handle.parts[0].get("fill"),
        "side_handle": side.handle.colour,
    }


@pytest.mark.parametrize("state", ["tab", "out", "animating"])
def test_a_new_desktop_look_repaints_the_frame_the_panel_the_strip_and_the_handle(
    state: str,
) -> None:
    m = themed()
    if state != "tab":
        act(m, "Show")
        advance(m, 100 if state == "animating" else 450)
        assert (host(m).anim is not None) == (state == "animating")
    dark = colours(m)
    if state == "animating":  # the ring is an alpha 1 ghost under the join: compare the rest
        dark = {k: v for k, v in dark.items() if k not in ("fill", "border")}
    switch(m, "light")
    light = colours(m)
    for key in dark:
        assert light[key] != dark[key], f"{key} did not follow the look: {dark[key]}"
    assert light["fill"] == (0xFF, 0xFF, 0xFF, 255)  # (a slide in flight was settled at once)
    assert light["handle"] == light["border"] == light["handle_node"] == light["side_handle"]
    advance(m, 600)
    assert colours(m) == light
    switch(m, "dark")
    assert colours(m)["fill"] == (0x10, 0x10, 0x10, 255)
    assert colours(m)["handle"] == colours(m)["border"] == (0xEE, 0xEE, 0xEE, 255)


def test_a_look_that_arrives_during_a_slide_settles_it_in_the_new_colours() -> None:
    """A join in flight holds the old colours, so the slide ends at once and the ring draws it."""
    m = themed()
    act(m, "Show")
    advance(m, 100)
    assert host(m).anim == "in"
    switch(m, "light")
    assert host(m).anim is None and not any(n.get("visible") for n in host(m).join.nodes)
    assert px(m)(60, 50)[:3] == (0xFF,) * 3  # the whole body, in the light fill
    assert colours(m)["handle"] == colours(m)["border"] == (0x11, 0x11, 0x11, 255)
    advance(m, 600)
    assert host(m).anim is None and px(m)(60, 50)[:3] == (0xFF,) * 3


def test_the_pixels_of_the_band_the_tab_and_the_body_follow_a_new_look() -> None:
    m = themed()
    assert px(m)(60, 15) == (0x10, 0x10, 0x10, 255) and px(m)(60, 28)[:3] == (0x10,) * 3
    switch(m, "light")
    assert px(m)(60, 15) == (0xFF, 0xFF, 0xFF, 255) and px(m)(60, 28)[:3] == (0xFF,) * 3
    act(m, "Show")
    advance(m, 450)
    assert px(m)(60, 50)[:3] == (0xFF,) * 3


# -- a button inside an open body ------------------------------------------------------------------


@pytest.mark.parametrize("trigger", ["HOVER", "CLICK", "DRAG"])
def test_a_button_in_an_open_body_runs_its_action_and_does_not_toggle_the_peek(
    trigger: str,
) -> None:
    """The KWin demo's bodies (``prepare_m3c_strips.body``): a labelled FlexBox with an On_Click
    that Toggles another Panel. Its click reaches it, not the peek's own trigger."""
    from tests.kwin.prepare_m3c_strips import body
    from tests.test_frame_peek import point

    frame = (
        "Frame { Name: Screen_Frame, Thickness: 20, Inner_Radius: 8, "
        "Inner_Border { Width: 2, Color: $color.primary }, Style { Background: $color.surface } }"
    )
    one = (
        "Panel { Name: One, Meld: true, Attach_To: Screen_Frame, Attach: TOP, Alignment: START, "
        f"Length: 200, Depth: 60, Peek {{ Size: 12, Trigger: {trigger} }}, "
        "Animation { Type: SLIDE, Duration: 200 }, " + body("One", "Toggle Two", "Two") + " }"
    )
    two = (
        "Panel { Name: Two, Meld: true, Attach_To: Screen_Frame, Attach: BOTTOM, "
        "Alignment: START, Length: 100, Depth: 40, Peek { Size: 12, Trigger: CLICK }, "
        "Animation { Type: NONE } }"
    )
    app, store = StubApp(), ValueStore()
    m = SurfaceManager(app, module(), lambda key: key[-1], store, look(), blend_mode="SRGB")  # type: ignore[arg-type]
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(frame, one + two))
    m.build()
    st = only(m)
    st.painter.resize(*app.size)
    st.painter.snapshot()
    hosts = {h.plan.name: h for h in st.hosts.values()}
    m.frames.run("Show", "One")
    advance(m, 400)
    assert "One" not in st.tab_melds and "Two" in st.tab_melds
    point(m, (60, 40))
    button = hosts["One"].surface.view.nodes["Toggle_Two_Button"]
    st.painter.simulate("click", node=button)
    advance(m, 50)
    assert "Two" not in st.tab_melds  # its action ran: Two came out
    assert "One" not in st.tab_melds and hosts["One"].anim is None  # and One was not toggled
    st.painter.simulate("click", node=button)
    advance(m, 50)
    assert "Two" in st.tab_melds and "One" not in st.tab_melds
