"""The cheap measure of a Popup that is a list of uniform rows (a menu).

``popup.measure`` builds the whole content in the headless meter window and reads the body's laid
out size: for a menu of 100 rows that is a second build of 100 module uses (about 50 ms) before the
Popup's own build. A menu is a column of rows that differ only in their texts, so its size follows
from a few facts:

* the rows are sorted into KINDS (the same blocks, the same keys and values but for the texts and
  icon documents: an item, a separator, an item with a shortcut or a submenu arrow...);
* ONE row of each kind is built in the meter window: its height and its width give the fixed parts
  (icon slot, spacing, paddings, arrow) and the font of each text, as tre lays them out;
* a row's width is that fixed part plus its texts, each measured with ``Window.measure_text`` (tre's
  own text layout, which a text node takes ``ceil(width)`` plus a pixel of margin of: the margin is
  read from the built row, not assumed);
* the column is the widest row plus the menu's padding (at least its ``Min_Width``), as tall as the
  rows and the padding.

Anything that is not exactly that shape returns ``None`` and the caller does the full pass: wrapper
blocks with keys of their own, a menu with spacing, a text wider than the Popup (it wraps), a
border width, a fixed Popup size, rows with no explicit height. ``tests/test_popup_measure.py`` pins
that the two give the same numbers.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from tess_shell.binder import model as m
from tess_shell.binder.build import build

# keys that differ from row to row without changing the row's size: its words, its name for
# assistive technology and the picture an icon shows (its size is a key of its own)
_ROW_DATA = frozenset({"Text", "Label", "Description", "Source", "Icon", "Id", "Key"})
# what a wrapper block around the menu may carry (the module roots of Tray_Menu, Audio_Outputs)
_WRAPPER_KEYS = frozenset({"Flex", "Name"})
_MENU_KEYS = frozenset({"Role", "Flex", "Min_Width", "Padding", "Label", "Name"})
_TEXT_FONT = ("font_size", "font_family", "font_weight", "font_style", "letter_spacing")


def _node(value: object) -> m.Node | None:
    return value if isinstance(value, m.Node) else None


def _vertical(node: m.Node) -> bool:
    flex = node.props.get("Flex")
    return flex is None or (isinstance(flex, m.Enum) and flex.name == "VERTICAL")


def find_menu(nodes: Sequence[Any]) -> m.Node | None:
    """The menu column inside plain wrapper blocks, or ``None`` for any other content."""
    current = _node(nodes[0]) if len(nodes) == 1 else None
    while current is not None:
        role = current.props.get("Role")
        if isinstance(role, m.Enum) and role.name == "MENU":
            return current
        if (
            current.kind != "FlexBox"
            or current.style
            or current.handlers
            or current.tooltip is not None
            or not set(current.props) <= _WRAPPER_KEYS
            or not _vertical(current)
            or len(current.children) != 1
        ):
            return None
        current = _node(current.children[0])
    return None


def _padding(value: m.Value | None) -> tuple[float, float, float, float] | None:
    """``(top, right, bottom, left)`` of a menu's padding, or ``None`` when it is not plain."""
    if value is None:
        return (0.0, 0.0, 0.0, 0.0)
    if isinstance(value, m.Length):
        return (value.px, value.px, value.px, value.px)
    if isinstance(value, m.Sides):
        return (value.top, value.right, value.bottom, value.left)
    return None


def _signature(node: m.Node) -> Any:
    """What the size of a row depends on: its blocks with their keys and values, not the texts and
    pictures. ``None`` when a block's size could depend on what is not in the key (a picture with
    no size of its own)."""
    if node.tooltip is not None:
        return None
    if node.kind in ("SVG", "Bitmap") and not (
        isinstance(node.props.get("Width"), m.Length)
        and isinstance(node.props.get("Height"), m.Length)
    ):
        return None
    kids = []
    for child in node.children:
        sub = _node(child)
        if sub is None:
            return None
        sig = _signature(sub)
        if sig is None:
            return None
        kids.append(sig)
    props = tuple(sorted((k, v) for k, v in node.props.items() if k not in _ROW_DATA))
    style = tuple(sorted(node.style.items()))
    return (node.kind, props, style, tuple(sorted(node.handlers)), tuple(kids))


def _texts(node: m.Node) -> list[str]:
    """The words of the visible Text blocks of a row, in tree order."""
    out: list[str] = []
    visible = node.props.get("Visible")
    if isinstance(visible, m.Bool) and not visible.value:
        return out
    if node.kind == "Text":
        text = node.props.get("Text")
        out.append(text.value if isinstance(text, m.Text) else "")
    for child in node.children:
        sub = _node(child)
        if sub is not None:
            out.extend(_texts(sub))
    return out


def _text_nodes(view: Any, row: m.Node) -> list[Any]:
    """The tre nodes of the visible Text blocks of a built ``row``, in the order of ``_texts``."""
    out: list[Any] = []

    def walk(node: m.Node) -> None:
        visible = node.props.get("Visible")
        if isinstance(visible, m.Bool) and not visible.value:
            return
        if node.kind == "Text" and node.name:
            out.append(view.nodes[node.name])
        for child in node.children:
            sub = _node(child)
            if sub is not None:
                walk(sub)

    walk(row)
    return out


class Kind:
    """One kind of row: the built row's numbers."""

    __slots__ = ("deltas", "fixed", "fonts", "height")

    def __init__(
        self,
        fixed: float,
        height: float,
        fonts: list[dict[str, Any]],
        deltas: list[float],
    ) -> None:
        self.fixed = fixed  # the row's width less its texts' widths
        self.height = height
        self.fonts = fonts  # the font of each text
        self.deltas = deltas  # what tre adds to ceil(measure_text) for each text


def _build_kind(meter: Any, row: m.Node) -> Kind | None:
    """Build ``row`` alone in a box that fits it, and read what its size is made of."""
    box = meter.create("box", align_self="start")
    meter.root.add_child(box)
    view = None
    try:
        view = build([row], meter, box)
        for _ in range(3):  # a text lays out one pass after the box around it
            meter.advance(16)
        root = view.nodes[row.name or ""]
        width, height = float(root.get("layout_width")), float(root.get("layout_height"))
        words = _texts(row)
        nodes = _text_nodes(view, row)
        if len(words) != len(nodes):
            return None
        fonts: list[dict[str, Any]] = []
        deltas: list[float] = []
        taken = 0.0
        for text, node in zip(words, nodes, strict=True):
            font = {key: node.get(key) for key in _TEXT_FONT}
            if node.get("line_height") is not None or node.get("max_lines") is not None:
                return None  # a text with a line height of its own: leave it to the full pass
            laid = float(node.get("layout_width"))
            said, _ = meter.measure_text(text, **font)
            fonts.append(font)
            deltas.append(laid - math.ceil(said))
            taken += laid
        return Kind(width - taken, height, fonts, deltas)
    finally:
        if view is not None:
            view.dispose()
        box.destroy()


def measure_menu(
    meter: Any,
    nodes: Sequence[Any],
    max_width: float,
    border: Mapping[str, Any] | None,
) -> tuple[float, float] | None:
    """``(width, height)`` of the menu in ``nodes`` as the full pass would lay it out, or ``None``
    when the content is not a plain menu (see the module's docstring)."""
    if border and border.get("stroke_width"):
        return None
    menu = find_menu(nodes)
    if menu is None or menu.style or menu.handlers or not set(menu.props) <= _MENU_KEYS:
        return None
    if not _vertical(menu) or not menu.children:
        return None
    pad = _padding(menu.props.get("Padding"))
    least = menu.props.get("Min_Width")
    if pad is None or not (least is None or isinstance(least, m.Length)):
        return None
    rows = [_node(c) for c in menu.children]
    kinds: dict[Any, Kind] = {}
    layout: list[tuple[m.Node, Kind]] = []
    for row in rows:
        if (
            row is None
            or row.kind != "FlexBox"
            or not row.name
            or not isinstance(row.props.get("Height"), m.Length)
        ):
            return None
        try:
            sig = _signature(row)
            if sig is None:
                return None
            kind = kinds.get(sig)
        except TypeError:  # a value that cannot be a key
            return None
        if kind is None:
            built = _build_kind(meter, row)
            if built is None:
                return None
            kind = kinds[sig] = built
        layout.append((row, kind))
    top, right, bottom, left = pad
    cache: dict[tuple[str, tuple[Any, ...]], float] = {}
    widest = 0.0
    tall = 0.0
    for row, kind in layout:
        width = kind.fixed
        for text, font, delta in zip(_texts(row), kind.fonts, kind.deltas, strict=True):
            key = (text, tuple(font.values()))
            said = cache.get(key)
            if said is None:
                said = cache[key] = math.ceil(meter.measure_text(text, **font)[0])
            width += said + delta
        widest = max(widest, width)
        tall += kind.height
    inner = widest + left + right
    wide = max(inner, least.px if isinstance(least, m.Length) else 0.0)
    if wide > max_width:  # the popup is narrower than its widest row: a text wraps
        return None
    return wide, tall + top + bottom
