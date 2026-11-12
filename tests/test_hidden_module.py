"""A hidden module takes no space in the Bar: its root is ``Visible: false``, which tre leaves out
of the layout, so the Spacing between its neighbours is the gap of the two and no more (Battery
Module and Workspaces Module > Hiding). Measured on the nodes' layout rectangles, headless."""

from __future__ import annotations

from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.modules_rig import desk, shell
from tests.widgets_live import Widgets

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def row(*middle: str) -> str:
    return (
        "FlexBox { Name: Row, Flex: HORIZONTAL, Spacing: 8, Width: EXPAND, Children { "
        'Text { Name: Left, Text: "AAA", Width: AUTO, Height: AUTO } '
        + " ".join(middle)
        + ' Text { Name: Right, Text: "BBB", Width: AUTO, Height: AUTO } } }'
    )


def node(w: Widgets, name: str) -> Any:
    return w.view.nodes[name]


def gap(w: Widgets) -> float:
    """The space between the end of ``Left`` and the start of ``Right``."""
    left, right = node(w, "Left"), node(w, "Right")
    return (
        float(right.get("layout_x")) - float(left.get("layout_x")) - float(left.get("layout_width"))
    )


def test_the_reference_gap_is_the_spacing() -> None:
    with desk() as d, shell(d, row()) as w:
        d.settle(w, lambda: False, 0.05)
        assert gap(w) == 8


def test_a_hidden_battery_leaves_exactly_the_gap_of_its_neighbours_and_showing_it_restores_it() -> (
    None
):
    with desk() as d:
        fake, obj = d.battery(present=False, percentage=0.0, state=0)
        fake.up()
        with shell(d, row("Battery { }")) as w:
            assert d.settle(w, lambda: w.store.values[w.uses[0]].get("available") is True)
            d.settle(w, lambda: False, 0.2)
            assert gap(w) == 8  # hidden: no second gap, no zero-size box
            obj.set("IsPresent", True)
            obj.set("Percentage", 64.0)
            obj.set("State", 2)
            assert d.settle(w, lambda: gap(w) > 8)
            (root,) = [n for k, n in w.view.nodes.items() if k.endswith("/Root")]
            width = float(root.get("layout_width"))
            assert width > 0 and gap(w) == pytest.approx(8 + width + 8)
            obj.set("IsPresent", False)
            assert d.settle(w, lambda: gap(w) == 8)


def test_a_battery_with_no_upower_at_all_takes_no_space() -> None:
    with desk() as d, shell(d, row("Battery { }", "Battery { show_percent: false }")) as w:
        d.settle(w, lambda: False, 0.3)
        assert gap(w) == 8
        fake, _ = d.battery()
        fake.up()  # UPower appears: both show
        assert d.settle(w, lambda: gap(w) > 8 + 8)
        fake.down()
        assert d.settle(w, lambda: gap(w) == 8)


def test_workspaces_without_kwin_takes_no_space_and_with_kwin_does() -> None:
    with desk() as d, shell(d, row("Workspaces { }")) as w:
        d.settle(w, lambda: False, 0.3)
        assert gap(w) == 8
        fake, _, _ = d.kwin()
        fake.up()
        assert d.settle(w, lambda: gap(w) > 8)
        fake.drop()
        assert d.settle(w, lambda: gap(w) == 8)


def test_a_block_written_hidden_takes_no_space_even_though_tre_builds_it_with_a_display() -> None:
    """tre 0.6.7 keeps the space of a node built with ``visible: false`` and an explicit
    ``display``; the binder takes it out after the build (``View.reindex``)."""
    from tests.widgets_live import running

    hidden = 'FlexBox { Name: Ghost, Visible: false, Children { Text { Text: "ghost" } } }'
    with running(row(hidden)) as w:
        assert gap(w) == 8
