"""An icon name a module sends (``Icon: {{ icon }}``): the same lookup as a name written in a
file, in an ``SVG`` block, in an ``Icon`` call's param, inside ``If`` and ``For`` (Standard Modules
> Icon; Battery Module). Headless, through the real binder."""

from __future__ import annotations

from typing import Any

from tess_shell.files.icons import IconSets
from tests.widgets_live import SHIPPED, running

SETS = IconSets([SHIPPED / "Icons"])
BROKEN = SETS.lookup("mdi:image-broken-variant")
HOME = SETS.lookup("mdi:home")
ACCOUNT = SETS.lookup("mdi:account")

DRIVER = (
    "Module { FlexBox { Name: Root, Children { "
    "SVG { Name: Plain, Icon: {{ ic }}, Width: 16, Height: 16 } "
    "Icon { Name: Called, Icon: {{ ic }} } "
    "If {{ show }} { SVG { Name: Shown, Icon: {{ ic }}, Width: 16, Height: 16 } } "
    "For r In {{ rows }} Key {{ r.id }} { "
    "SVG { Name: Row, Icon: {{ r.icon }}, Width: 16, Height: 16 } } "
    "} } }"
)
CODE = (
    "from tess_shell import Module\n"
    "class Driver(Module):\n"
    "    def start(self):\n"
    "        self.ctx.send('ic', 'mdi:home')\n"
    "        self.ctx.send('show', True)\n"
    "        self.ctx.send('rows', [{'id': 'a', 'icon': 'mdi:home'},\n"
    "                               {'id': 'b', 'icon': 'mdi:account'}])\n"
)


def svg_of(w: Any, suffix: str) -> str:
    (node,) = [n for k, n in w.view.nodes.items() if k.endswith(f"/{suffix}")]
    return str(node.get("svg"))


def called(w: Any) -> list[str]:
    """The SVG documents drawn by the ``Icon`` call (the first child of its root, if any)."""
    root = w.of_use("Icon", "Root")
    return [str(c.get("svg")) for c in root.children() if c.get("kind") == "svg"]


def rows(w: Any) -> list[str]:
    return [
        str(n.get("svg"))
        for k, n in w.view.nodes.items()
        if "/Row" in k and w.view.kinds[k] == "SVG"
    ]


def test_a_sent_name_is_looked_up_like_a_written_one_everywhere() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        assert w.warnings() == [], w.warnings()
        assert svg_of(w, "Plain") == HOME  # an SVG block's Icon
        assert svg_of(w, "Shown") == HOME  # inside an If
        assert rows(w) == [HOME, ACCOUNT]  # inside a For
        # an Icon call's param: the module's own layout shows the document
        assert called(w) == [HOME]


def test_a_change_of_the_name_swaps_the_document_in_the_same_node() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        plain = [n for k, n in w.view.nodes.items() if k.endswith("/Plain")][0]
        w.send("ic", "mdi:account")
        assert svg_of(w, "Plain") == ACCOUNT and svg_of(w, "Shown") == ACCOUNT
        assert [n for k, n in w.view.nodes.items() if k.endswith("/Plain")][0] == plain
        assert called(w) == [ACCOUNT]
        w.send("rows", [{"id": "b", "icon": "mdi:home"}, {"id": "a", "icon": "mdi:account"}])
        assert rows(w) == [HOME, ACCOUNT]


def test_an_unknown_name_shows_the_broken_image_icon_with_one_warning() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        for _ in range(3):
            w.send("ic", "mdi:no-such-icon-anywhere")
            w.send("ic", "mdi:home")
        w.send("ic", "mdi:no-such-icon-anywhere")
        assert svg_of(w, "Plain") == BROKEN
        warned = [x for x in w.warnings() if "no-such-icon-anywhere" in x]
        assert len(warned) == 1 and "| WARNING " in warned[0]
        w.send("ic", "mdi:another-missing-one")
        assert len([x for x in w.warnings() if "no icon named" in x]) == 2  # one per name


def test_an_empty_name_shows_nothing_and_warns_nothing() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        w.send("ic", "")
        assert "<path" not in svg_of(w, "Plain") and "<path" not in svg_of(w, "Shown")
        assert called(w) == []  # the Icon module draws no SVG for an empty name
        assert w.warnings() == []


def test_a_document_is_used_as_it_is_and_a_number_is_a_warning_not_a_crash() -> None:
    doc = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 4'>"
        "<rect width='4' height='4'/></svg>"
    )
    with running("Driver { }", driver=DRIVER, driver_py=CODE) as w:
        w.send("ic", doc)
        assert svg_of(w, "Plain") == doc
        w.send("ic", 5)
        assert svg_of(w, "Plain") == doc  # the last value stays
        assert any("expected an icon name" in x for x in w.warnings())
