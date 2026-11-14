"""The ranges of values: one table that the loader checks and the schema export reports.

A *kind* has a range of its own (``positive`` is above 0, a length is 0 or more); a few *keys* of
the ``number`` kind have one that the kind does not (``Opacity`` is 0 to 1). ``schema.values``
raises a finding for a written value outside its range, ``schema.export`` writes the same numbers
as ``min`` and ``max``, so the two cannot disagree. Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Range:
    """The numbers a value may be: from ``low`` (``None``: no least) to ``high``; ``low_open`` makes
    ``low`` itself too small (above 0)."""

    low: float | None = None
    high: float | None = None
    low_open: bool = False

    def holds(self, n: float) -> bool:
        if self.low is not None and (n <= self.low if self.low_open else n < self.low):
            return False
        return self.high is None or n <= self.high

    def words(self, unit: str = "") -> str:
        """The range as a person reads it: ``0 or more``, ``greater than 0``, ``from 0 to 1``;
        ``unit`` follows each number (``%``)."""
        low = None if self.low is None else f"{plain(self.low)}{unit}"
        high = None if self.high is None else f"{plain(self.high)}{unit}"
        if low is not None and high is not None:
            return f"from {low} to {high}"
        if low is not None:
            return f"greater than {low}" if self.low_open else f"{low} or more"
        return f"{high} or less"


def plain(n: float) -> str:
    """A whole number in full (``2147483647``, not ``2.14748e+09``), another as ``g`` writes it."""
    return str(int(n)) if float(n).is_integer() else f"{n:g}"


# the largest ``Tab_Index``: the largest signed 32-bit integer (Focus and Keyboard > Tab Order)
TAB_INDEX_MAX = 2_147_483_647

# the range of every value of a kind (the loader's kind words, ``schema.values``)
KIND_RANGES: dict[str, Range] = {
    "positive": Range(0, low_open=True),
    "max_length": Range(0),
    "lines": Range(1),
    "tab_index": Range(0, TAB_INDEX_MAX),
    "duration": Range(0),
    "pause": Range(0),
    "unit": Range(0, 1),
    "diameter": Range(0, low_open=True),
    "elevation": Range(0, 100),
    # a length, a bound, the sides of a block and a radius cannot be negative (the binder's
    # converters refuse them as well)
    "length": Range(0),
    "text_length": Range(0),
    "bound": Range(0),
    "sides": Range(0),
    "bleed": Range(0),
    "radius": Range(0),
}

# the keys that take a range the kind does not give them
KEY_RANGES: dict[str, Range] = {
    "Opacity": Range(0, 1),
    "Handle_Opacity": Range(0, 1),
    "Flex_Grow": Range(0),
    "Flex_Shrink": Range(0),
    "Font_Weight": Range(1, 1000),
    "Border_Width": Range(0),
    # keys of a block of their own, listed as ``<Block>.<Key>`` (``scoped``)
    "Peek.Size": Range(1),
    "Edge.Thickness": Range(0),
    "Border.Width": Range(0),
    "Shadow.Blur": Range(0),
    "Hide_After": Range(0),
    "Enter_Delay": Range(0),
    "Exit_Delay": Range(0),
}

# a key that takes a percentage of something has its own range for it: a Popup's ``Max_Height`` is a
# share of the output's height, above 0 and at most 100 (a share of nothing is no limit at all).
# Listed as ``<Block>.<Key>``; ``percent_range`` is what the loader and the export read
PERCENT_RANGES: dict[str, Range] = {
    "Popup.Max_Height": Range(0, 100, low_open=True),
    "Tooltip.Max_Height": Range(0, 100, low_open=True),
}


def percent_range(spec: str, key: str) -> Range | None:
    """The range of a percentage written as ``key`` of the block ``spec``, or ``None`` when the
    key takes none (or a percentage is not built there)."""
    return PERCENT_RANGES.get(f"{spec}.{key}")


# keys of a kind with a non-negative range that may be negative: a Panel's ``Inset`` is a distance
# from the edge it is anchored to, and a compositor takes a negative margin
NEGATIVE_OK = frozenset({"Inset"})


# the kinds whose numbers a key's own range may narrow (the key is a plain number of that kind)
KEY_RANGE_KINDS = frozenset({"number", "whole", "unit"})


def scoped(spec: str, key: str) -> str:
    """The name a key's range is listed under: ``Peek.Size`` for a key whose range belongs to the
    block that has it (a strip's Peek is a Peek), else the key's own name."""
    name = f"{'Peek' if spec == 'Edge_Peek' else spec}.{key}"
    return name if name in KEY_RANGES else key


def range_of(kind: str, key: str = "") -> Range | None:
    """The range of a key of this kind: the key's own (for a plain number), else the kind's, else
    ``None``."""
    if key in KEY_RANGES and kind in KEY_RANGE_KINDS:
        return KEY_RANGES[key]
    if key in NEGATIVE_OK:
        return None
    return KIND_RANGES.get(kind)
