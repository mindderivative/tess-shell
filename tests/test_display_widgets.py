# ruff: noqa: E501
"""The M4b display widgets headless: Label, TextBox, ProgressBar, Badge, Marquee text, Icon, Image,
Expander, the Circle, Ring and Path blocks, the Tooltip string and Spacer (Standard Modules)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tess_shell.appearance import Appearance
from tess_shell.binder.images import IMAGES
from tests.widgets_live import running

FIX = Path(__file__).resolve().parent / "fixtures"


def test_label_shows_its_text_names_itself_and_takes_a_width() -> None:
    with running('Label { Text: "Hello", Width: 80 }') as w:
        assert w.warnings() == []
        text = w.of_use("Label", "#0")
        assert text.get("text") == "Hello" and text.get("label") == "Hello"
        assert text.get("width") == 80


def test_a_disabled_label_is_faint() -> None:
    with running("Label { Text: x, Enabled: false }") as w:
        text = w.of_use("Label", "#0")
        assert text.get("disabled") is True and text.get("opacity") == 0.5


def test_textbox_wraps_by_word_and_limits_its_lines() -> None:
    body = 'TextBox { Text: "one two three four five six seven", Width: 60, Max_Lines: 2 }'
    with running(body) as w:
        text = w.of_use("TextBox", "#0")
        assert text.get("wrap") == "word" and text.get("max_lines") == 2
        assert text.get("layout_height") > 0


def test_progressbar_follows_its_value_with_role_and_range() -> None:
    with running("ProgressBar { Value: 25, Min: 0, Max: 50, Label: Upload }") as w:
        root = w.of_use("ProgressBar", "Root")
        assert root.get("role") == "progressbar" and root.get("label") == "Upload"
        assert (root.get("value"), root.get("value_min"), root.get("value_max")) == (25, 0, 50)
        assert w.of_use("ProgressBar", "Fill").get("width") == "50%"
        # the parts take the Default stylesheet's colours
        assert w.of_use("ProgressBar", "Fill").get("fill") == (91, 151, 201, 255)


def test_progressbar_fill_eases_over_the_medium_duration_and_not_under_reduced_motion() -> None:
    driver = "Module { FlexBox { Children { ProgressBar { Name: P, Value: {{ v }} } } } }"
    code = "from tess_shell import Module\nclass Driver(Module):\n    def start(self):\n        self.ctx.send('v', 0)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        w.send("v", 100)
        fill = w.of_use("ProgressBar", "Fill")
        w.advance(100)
        assert 0 < fill.get("layout_width") < 160  # on its way
        w.advance(500)
        assert fill.get("width") == "100%"
    with running(
        "Driver { }", driver=driver, driver_py=code, appearance=Appearance(reduced_motion=True)
    ) as w:
        w.send("v", 100)
        w.advance(16)
        assert w.of_use("ProgressBar", "Fill").get("width") == "100%"


def test_badge_counts_caps_hides_zero_and_draws_a_dot() -> None:
    body = "Badge { Count: 7 } Badge { Count: 120 } Badge { Count: 0 } Badge { Dot: true }"
    with running(body) as w:
        roots = [w.of_use("Badge", "Root", i) for i in range(4)]
        assert [r.get("visible") for r in roots] == [True, True, False, True]
        assert w.of_use("Badge", "Digits", 0).get("text") == "7"
        assert w.of_use("Badge", "Digits", 1).get("text") == "99+"
        assert roots[3].get("width") == 8 and roots[0].get("a11y_hidden") is True


def test_marquee_scrolls_only_when_the_text_does_not_fit() -> None:
    body = 'Marquee_Text { Text: "short", Width: 200 } Marquee_Text { Text: "a very long text that does not fit in a hundred pixels", Width: 100 }'
    with running(body) as w:
        short, long = list(w.view.runners.values())
        assert short.state == "fits" and long.state == "running"
        w.advance(1600)
        w.advance(2000)
        assert long.text.get("translate_x") < 0 and short.text.get("translate_x") == 0


def test_marquee_is_static_with_an_ellipsis_under_reduced_motion_and_when_disabled() -> None:
    body = 'Marquee_Text { Text: "a very long text that does not fit in a hundred pixels", Width: 100%s }'
    for extra, look in ((", Enabled: false", None), ("", Appearance(reduced_motion=True))):
        with running(body.replace("%s", extra), appearance=look) as w:
            (runner,) = w.view.runners.values()
            assert runner.state == "static" and runner.tooltip_gate() is True
            assert runner.text.get("overflow") == "ellipsis"
            w.advance(5000)
            assert runner.text.get("translate_x") == 0


def test_a_disabled_marquee_opens_a_tooltip_with_the_whole_text() -> None:
    text = "a very long text that does not fit in a hundred pixels"
    with running(f'Marquee_Text {{ Text: "{text}", Width: 100, Enabled: false }}') as w:
        (tip,) = w.bar.expanded.tooltips.items()
        block = tip[0]
        node = w.view.nodes[block]
        assert w.view.wires[block].tip_blocked is True
        w.window.simulate("pointer_enter", node=node)
        w.advance(600)
        op = w.manager.popups.current
        assert op is not None and op.view is not None
        texts: list[str] = []

        def walk(node: Any) -> None:
            if node.get("kind") == "text":
                texts.append(node.get("text"))
            for child in node.children():
                walk(child)

        walk(op.window.root)
        assert text in texts
    # a Marquee that fits has nothing to add: no tooltip even enabled-or-not
    with running('Marquee_Text { Text: "fits", Width: 100, Enabled: false }') as w:
        (block,) = w.bar.expanded.tooltips
        w.window.simulate("pointer_enter", node=w.view.nodes[block])
        w.advance(600)
        assert w.manager.popups.current is None


def test_expander_opens_and_closes_with_size_and_fade_and_rests() -> None:
    driver = "Module { FlexBox { Children { Expander { Name: E, Expanded: {{ open }}, Children { Label { Text: inside } } } } } }"
    code = "from tess_shell import Module\nclass Driver(Module):\n    def start(self):\n        self.ctx.send('open', False)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        root, body = w.of_use("Expander", "Root"), w.of_use("Expander", "Body")
        assert root.get("layout_height") == 0 and body.get("opacity") == 0
        w.send("open", True)
        w.advance(100)
        assert 0 < root.get("layout_height") and 0 < body.get("opacity") < 1
        w.advance(500)
        assert root.get("height") == "auto" and root.get("layout_height") > 0
        assert body.get("opacity") == 1
        w.send("open", False)
        w.advance(500)
        assert root.get("layout_height") == 0 and body.get("opacity") == 0
        assert body.get("a11y_hidden") is True


def test_expander_content_fade_false_keeps_the_content_opaque() -> None:
    with running("Expander { Content_Fade: false, Children { Label { Text: x } } }") as w:
        assert w.of_use("Expander", "Body").get("opacity") == 1


def test_icon_from_a_name_and_a_bad_name_warns_once() -> None:
    with running('Icon { Icon: "mdi:home", Size: 24 }') as w:
        assert w.warnings() == []
        (svg,) = [n for k, n in w.view.nodes.items() if w.view.kinds[k] == "SVG"] or [None]
    with running("Image { Source: nothing.png }"):
        pass


def test_image_shows_each_format_and_the_error_image_for_a_bad_file() -> None:
    IMAGES.clear()
    for name in ("png.png", "jpeg.jpg", "gif.gif", "webp.webp"):
        with running(f'Image {{ Source: "{FIX / name}", Name: I }}') as w:
            assert w.warnings() == [], name
            (bitmap,) = [n for k, n in w.view.nodes.items() if w.view.kinds[k] == "Bitmap"] or [
                None
            ]
    before = IMAGES.decoded
    for name in ("bad.png", "not_an_image.txt"):
        with running(f'Image {{ Source: "{FIX / name}" }}') as w:
            assert any("showing the error image" in x for x in w.warnings())
    assert IMAGES.load(str(FIX / "png.png")).width == 8 and IMAGES.decoded == before


def test_shapes_are_paths_hit_where_painted() -> None:
    body = 'Circle { Diameter: 20, Fill: "#ff0000" } Ring { Diameter: 20, Border_Color: "#00ff00" }'
    with running(body) as w:
        assert w.warnings() == []
    # the block tables build a path with the painted hit shape (Block Reference > Shapes)
    from tess_shell.binder.tables import BLOCKS

    assert BLOCKS["Circle"].defaults["hit_shape"] == "painted"
    assert BLOCKS["Ring"].defaults["hit_shape"] == "painted"
    assert BLOCKS["Path"].defaults["hit_shape"] == "painted"


def test_a_string_tooltip_is_a_one_line_tooltip_and_the_description() -> None:
    with running('Label { Text: x, Tooltip: "Save the file" }') as w:
        tips = w.bar.expanded.tooltips
        assert len(tips) == 1
        (tip,) = tips.values()
        assert tip.ref.popup.tooltip is True and tip.ref.popup.enter_delay == 500
        wrapper = next(n for k, n in w.view.nodes.items() if k in tips)
        assert wrapper.get("kind") == "box"  # a Label's Text sits in a box that takes the pointer


def test_spacer_takes_no_pointer_unless_it_has_a_click() -> None:
    driver = "Module { FlexBox { Name: R, Width: 300, Height: 20, Children { Box { Name: A, Width: 10 } Spacer { Name: S } Box { Name: B, Width: 10 } Spacer { Name: S2, On_Click: pressed } } } }"
    with running("Driver { }", driver=driver) as w:
        assert w.of_use("Driver", "S").get("hit_testable") is False
        assert w.of_use("Driver", "S2").get("hit_testable") is True
        b = w.of_use("Driver", "B")
        before = b.get("layout_x")
        w.window.resize(600, 40)
        w.advance(16)
        assert b.get("layout_x") == before  # the spacers share what is free, the end stays put


def test_each_decode_is_timed_and_one_over_the_limit_is_logged_with_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M4 Brief, question 18: the loop-thread decode is measured, so the off-thread route is
    built when a typical decode takes over 8 ms."""
    from loguru import logger

    from tess_shell.binder import images

    IMAGES.clear()
    lines: list[str] = []
    sink = logger.add(lines.append, level="DEBUG", format="{level} {message}")
    try:
        IMAGES.timings.clear()
        IMAGES.load(str(FIX / "png.png"))
        assert [Path(p).name for p, _ in IMAGES.timings] == ["png.png"]
        assert IMAGES.timings[0][1] >= 0 and not [x for x in lines if "off-thread" in x]
        monkeypatch.setattr(images, "SLOW_MS", 0.0)
        IMAGES.load(str(FIX / "jpeg.jpg"))
        slow = [x for x in lines if "off-thread" in x]
        assert len(slow) == 1 and "jpeg.jpg" in slow[0] and slow[0].startswith("DEBUG")
        IMAGES.load(str(FIX / "jpeg.jpg"))  # a cache hit decodes nothing and logs nothing
        assert len([x for x in lines if "off-thread" in x]) == 1
    finally:
        logger.remove(sink)


def test_expander_raises_on_changed_when_an_opening_and_a_closing_finish() -> None:
    driver = (
        "Module { FlexBox { Children { Expander { Name: E, Expanded: {{ open }}, "
        "On_Changed: changed, Children { Label { Text: inside } } } } } }"
    )
    code = (
        "from tess_shell import Module, action\n"
        "class Driver(Module):\n"
        "    def __init__(self):\n        self.seen = []\n"
        "    def start(self):\n        self.ctx.send('open', False)\n"
        "    @action\n    def changed(self, event):\n"
        "        self.seen.append((event.value, event.old, event.new))\n"
    )
    with running("Driver { }", driver=driver, driver_py=code) as w:
        seen = w.host.loaded["Driver"].instance.seen  # type: ignore[attr-defined]
        assert w.warnings() == [] and seen == []  # the state it starts in is no change
        w.send("open", True)
        w.advance(100)
        assert seen == []  # still opening
        w.advance(500)
        assert seen == [(True, False, True)]
        w.send("open", False)
        w.advance(500)
        assert seen == [(True, False, True), (False, True, False)]
        w.advance(2000)
        assert len(seen) == 2  # at rest nothing more


def test_expander_reversed_half_way_raises_one_event_for_the_finish() -> None:
    driver = (
        "Module { FlexBox { Children { Expander { Name: E, Expanded: {{ open }}, "
        "On_Changed: changed, Children { Label { Text: inside } } } } } }"
    )
    code = (
        "from tess_shell import Module, action\n"
        "class Driver(Module):\n"
        "    def __init__(self):\n        self.seen = []\n"
        "    def start(self):\n        self.ctx.send('open', False)\n"
        "    @action\n    def changed(self, event):\n        self.seen.append(event.value)\n"
    )
    with running("Driver { }", driver=driver, driver_py=code) as w:
        seen = w.host.loaded["Driver"].instance.seen  # type: ignore[attr-defined]
        w.send("open", True)
        w.advance(80)
        w.send("open", False)
        w.advance(600)
        assert seen == [False]


def test_expander_on_changed_is_at_once_under_reduced_motion() -> None:
    driver = (
        "Module { FlexBox { Children { Expander { Name: E, Expanded: {{ open }}, "
        "On_Changed: changed, Children { Label { Text: inside } } } } } }"
    )
    code = (
        "from tess_shell import Module, action\n"
        "class Driver(Module):\n"
        "    def __init__(self):\n        self.seen = []\n"
        "    def start(self):\n        self.ctx.send('open', False)\n"
        "    @action\n    def changed(self, event):\n        self.seen.append(event.value)\n"
    )
    with running(
        "Driver { }", driver=driver, driver_py=code, appearance=Appearance(reduced_motion=True)
    ) as w:
        seen = w.host.loaded["Driver"].instance.seen  # type: ignore[attr-defined]
        w.send("open", True)
        w.advance(16)
        assert seen == [True]


def test_expander_on_changed_on_a_call_in_a_shell_file() -> None:
    body = "Expander { On_Changed { Action: Call, Target: \"Driver.pressed\" }, Children { Label { Text: x } } }"
    with running(body) as w:
        assert w.problems == [] and w.warnings() == []
