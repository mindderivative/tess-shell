"""A Panel's Animation, its own events and Movable (Panel > Behaviour), headless: tre's
``advance`` runs the engine's animations and timers without a compositor."""

from __future__ import annotations

from pathlib import Path

import pytest

from tess_shell.appearance import Appearance
from tests.test_panel import manager, panel_errors, panel_of, surface

SLIDE = (
    "Panel { Name: Drawer, Layer: OVERLAY, Anchor: [TOP, LEFT], Inset: [20, 100, 0, 0], "
    "Width: 200, Height: 100, Visible: false, Animation { Type: SLIDE, Duration: 200 }, "
    "Children { FlexBox { } } }"
)


# -- the keys ---------------------------------------------------------------------------------


def test_animation_defaults_to_a_200_ms_slide_and_none_means_none() -> None:
    p = panel_of("Panel { Name: P, Width: 9, Height: 9, Animation { } }")
    assert (p.animation, p.duration) == ("SLIDE", 200)
    p = panel_of("Panel { Name: P, Width: 9, Height: 9, Animation { Type: FADE, Duration: 80 } }")
    assert (p.animation, p.duration) == ("FADE", 80)
    assert panel_of("Panel { Name: P, Width: 9, Height: 9 }").animation == "NONE"
    for off in ("Type: NONE", "Duration: 0"):
        assert (
            panel_of(f"Panel {{ Name: P, Width: 9, Height: 9, Animation {{ {off} }} }}").animation
            == "NONE"
        )


@pytest.mark.parametrize(
    ("snippet", "rule"),
    [
        ("Panel { Name: P, Width: 9, Height: 9, Animation { Type: SPIN } }", "bad-value"),
        ("Panel { Name: P, Width: 9, Height: 9, Animation { Speed: 3 } }", "unknown-key"),
        ("Panel { Name: P, Width: 9, Height: 9, On_Click: Hide }", "event-not-raised"),
        ("Panel { Name: P, Width: 9, Height: 9, On_Open: Hide }", "missing-key"),
        ("Panel { Name: P, Width: 9, Height: 9, On_Open: my_action }", "unknown-action"),
        ("Panel { Name: P, Width: 9, Height: 9, On_Opened: Hide }", "unknown-key"),
        (
            "Panel { Name: P, Width: 9, Height: 9, Movable: true, Attach_To: Top_Bar, "
            "Attach: BOTTOM }",
            "movable-attached",
        ),
    ],
)
def test_a_bad_animation_event_or_movable_is_an_error_at_load(snippet: str, rule: str) -> None:
    assert any(f.rule == rule for f in panel_errors(snippet))


def test_the_panel_events_take_a_builtin_action_with_a_target() -> None:
    p = panel_of(
        "Panel { Name: P, Width: 9, Height: 9, On_Visible { Action: Show, Target: Q }, "
        "On_Hidden { Action: Hide, Target: Q } }"
    )
    assert set(p.handlers) == {"On_Visible", "On_Hidden"}
    assert p.handlers["On_Visible"].args["Target"] == "Q"


# -- the animation ----------------------------------------------------------------------------


def test_a_slide_starts_24_px_toward_its_edge_and_ends_at_rest_while_it_fades_in() -> None:
    m = manager(panel=SLIDE, hide_mode="KEEP")
    s = surface(m, "Drawer")
    assert s.window is not None and s.hidden
    rest = s.geometry.margin
    assert rest == (100, 0, 0, 20)
    m.show(s)
    assert s.window.get("margin") == (76, 0, 0, 20)  # 24 px closer to the top edge
    assert s.window.root.get("opacity") == 0.0
    s.window.advance(100)
    assert 76 < s.window.get("margin")[0] < 100 and 0.0 < s.window.root.get("opacity") < 1.0
    s.window.advance(150)
    assert s.window.get("margin") == rest and s.window.root.get("opacity") == 1.0


def test_hide_slides_out_takes_no_input_at_once_and_is_hidden_when_it_ends() -> None:
    m = manager(panel=SLIDE, hide_mode="KEEP")
    s = surface(m, "Drawer")
    m.show(s)
    assert s.window is not None
    s.window.advance(300)
    m.hide(s)
    assert s.hidden and s.window.get("input_region") == []  # a hiding Panel takes no pointer
    assert s.window.root.get("visible") is True  # still drawn while it leaves
    s.window.advance(100)
    assert s.window.root.get("visible") is True
    s.window.advance(150)
    assert s.window.root.get("visible") is False
    assert s.window.get("margin") == s.geometry.margin and s.window.root.get("opacity") == 1.0


def test_showing_again_while_it_leaves_turns_it_round_from_where_it_is() -> None:
    m = manager(panel=SLIDE, hide_mode="KEEP")
    s = surface(m, "Drawer")
    m.show(s)
    assert s.window is not None
    s.window.advance(300)
    m.hide(s)
    s.window.advance(100)
    midway = s.window.get("margin")[0]
    assert midway > 76
    m.show(s)
    assert s.hidden is False and s.window.get("margin")[0] == midway  # no jump back to the start
    s.window.advance(300)
    assert s.window.get("margin") == s.geometry.margin and s.window.root.get("visible") is True


def test_reduced_motion_shows_and_hides_at_once() -> None:
    m = manager(panel=SLIDE, hide_mode="KEEP", appearance=Appearance(reduced_motion=True))
    s = surface(m, "Drawer")
    m.show(s)
    assert s.window is not None
    assert s.window.get("margin") == s.geometry.margin and s.window.root.get("opacity") == 1.0
    m.hide(s)
    assert s.window.root.get("visible") is False


def test_a_fade_leaves_the_margin_alone_and_close_mode_closes_when_the_fade_ends() -> None:
    fade = SLIDE.replace("Type: SLIDE", "Type: FADE")
    m = manager(panel=fade, hide_mode="CLOSE")
    s = surface(m, "Drawer")
    m.show(s)
    window = s.window
    assert window is not None and window.get("margin") == s.geometry.margin
    assert window.root.get("opacity") == 0.0
    window.advance(250)
    assert window.root.get("opacity") == 1.0
    m.hide(s)
    assert s.window is window  # still there while it fades out
    window.advance(250)
    assert s.window is None and s.hidden


# -- the events -------------------------------------------------------------------------------

WATCHER = (
    "Panel { Name: Drawer, Layer: OVERLAY, Anchor: [TOP, LEFT], Width: 200, Height: 100, "
    "Visible: false, Animation { Type: FADE, Duration: 100 }, "
    "On_Open { Action: Show, Target: Open_Flag }, "
    "On_Visible { Action: Show, Target: Seen_Flag }, "
    "On_Close { Action: Show, Target: Closing_Flag }, "
    "On_Hidden { Action: Show, Target: Gone_Flag }, "
    "Children { FlexBox { } } }\n"
    + "\n".join(
        f"Panel {{ Name: {n}, Width: 9, Height: 9, Visible: false }}"
        for n in ("Open_Flag", "Seen_Flag", "Closing_Flag", "Gone_Flag")
    )
)


def test_open_and_close_run_when_asked_and_visible_and_hidden_when_it_has_happened() -> None:
    m = manager(panel=WATCHER, hide_mode="KEEP")
    drawer = surface(m, "Drawer")
    flags = {n: surface(m, n) for n in ("Open_Flag", "Seen_Flag", "Closing_Flag", "Gone_Flag")}

    def raised() -> set[str]:
        return {n for n, f in flags.items() if not f.hidden}

    m.show(drawer)
    assert raised() == {"Open_Flag"}  # before: the request, the animation has not run
    assert drawer.window is not None
    drawer.window.advance(150)
    assert raised() == {"Open_Flag", "Seen_Flag"}  # after: it is visible
    m.hide(drawer)
    assert raised() == {"Open_Flag", "Seen_Flag", "Closing_Flag"}
    drawer.window.advance(150)
    assert raised() == {"Open_Flag", "Seen_Flag", "Closing_Flag", "Gone_Flag"}


def test_a_handler_loop_is_stopped_and_logged() -> None:
    from loguru import logger

    loop = (
        "Panel { Name: Ping, Width: 9, Height: 9, Visible: false, "
        "On_Open { Action: Toggle, Target: Pong } }\n"
        "Panel { Name: Pong, Width: 9, Height: 9, Visible: false, "
        "On_Open { Action: Toggle, Target: Ping } }"
    )
    m = manager(panel=loop, hide_mode="KEEP")
    errors: list[str] = []
    sink = logger.add(lambda message: errors.append(str(message)), level="ERROR")
    try:
        m.show(surface(m, "Ping"))  # must return, not recurse until Python gives up
    finally:
        logger.remove(sink)
    assert any("calls itself in a loop" in e for e in errors)


# -- Movable ----------------------------------------------------------------------------------


class Positions:
    """A registry stand-in: what is saved, by key."""

    def __init__(self, saved: dict[str, dict[str, float]] | None = None) -> None:
        self.saved = saved or {}

    def position(self, key: str) -> dict[str, float] | None:
        return self.saved.get(key)

    def set_position(self, key: str, position: dict[str, float]) -> None:
        self.saved[key] = position


WIDGET = (
    "Panel { Name: Widget, Layer: BOTTOM, Anchor: [TOP, LEFT], Inset: [40, 50, 0, 0], "
    "Width: 200, Height: 90, Movable: true, Children { FlexBox { } } }"
)


def test_a_movable_panel_has_a_drag_handle_and_takes_its_inset_until_it_is_moved() -> None:
    m = manager(panel=WIDGET, hide_mode="KEEP")
    s = surface(m, "Widget")
    assert s.window is not None and s.body is not None
    assert s.body.get("window_region") == "drag_margin"
    assert s.geometry.margin == (50, 0, 0, 40)
    plain = surface(
        manager(panel=WIDGET.replace("Movable: true, ", ""), hide_mode="KEEP"), "Widget"
    )
    assert plain.body is not None and plain.body.get("window_region") != "drag_margin"


def test_a_floating_movable_panel_starts_centred_and_is_anchored_top_left() -> None:
    floating = "Panel { Name: Widget, Width: 200, Height: 100, Movable: true }"
    s = surface(manager(panel=floating, hide_mode="KEEP"), "Widget")
    assert s.geometry.anchor == ("top", "left")
    assert s.geometry.margin == (350, 0, 0, 400)  # centred on the 1000 x 800 output


def test_the_end_of_a_drag_is_saved_as_an_inset_and_read_back_on_the_next_plan() -> None:
    store = Positions()
    m = manager(panel=WIDGET, hide_mode="KEEP", positions=store)
    s = surface(m, "Widget")
    assert s.window is not None
    m._moved(s, (120, 0, 0, 300))  # what tre reports when the button goes up
    assert store.saved == {
        "position:Main_Shell.Main@HDMI-A-1.Widget": {"left": 300.0, "top": 120.0}
    }
    assert s.geometry.margin == (120, 0, 0, 300)  # what a later reload must not undo
    again = surface(manager(panel=WIDGET, hide_mode="KEEP", positions=store), "Widget")
    assert again.geometry.margin == (120, 0, 0, 300)


def test_a_saved_position_is_kept_on_the_output_and_a_shadow_does_not_shift_it() -> None:
    far = Positions({"position:Main_Shell.Main@HDMI-A-1.Widget": {"left": 5000.0, "top": -30.0}})
    s = surface(manager(panel=WIDGET, hide_mode="KEEP", positions=far), "Widget")
    assert s.geometry.margin == (0, 0, 0, 800)  # clamped to the 1000 x 800 output
    shadowed = WIDGET.replace("Movable: true,", "Movable: true, Style { Elevation: 8% },")
    store = Positions()
    m = manager(panel=shadowed, hide_mode="KEEP", positions=store)
    s = surface(m, "Widget")
    top, _, _, left = s.geometry.body_margin[0], 0, 0, s.geometry.body_margin[3]
    assert s.window is not None and (top, left) != (0, 0)
    m._moved(s, (100, 0, 0, 200))
    saved = next(iter(store.saved.values()))
    assert saved == {
        "left": 200.0 + left,
        "top": 100.0 + top,
    }  # the body's place, not the surface's


def test_a_saved_position_survives_in_registry_json_and_the_latest_write_wins(
    tmp_path: Path,
) -> None:
    import json
    import time

    from tess_shell.config.registry import Registry

    registry = Registry.open(tmp_path / "registry.json")
    assert registry.position("position:S.M.P") is None
    registry.set_position("position:S.M.P", {"left": 10.0, "top": 20.0})
    registry.set_position("position:S.M.P", {"left": 30.0, "top": 40.0})
    for _ in range(100):  # the write is made off the loop thread
        saved = json.loads((tmp_path / "registry.json").read_text())["entries"]
        if saved.get("position:S.M.P", {}).get("position") == {"left": 30.0, "top": 40.0}:
            break
        time.sleep(0.02)
    else:
        raise AssertionError("the position was not written")
    again = Registry.open(tmp_path / "registry.json")
    assert again.position("position:S.M.P") == {"left": 30.0, "top": 40.0}
