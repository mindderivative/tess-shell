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
        low = None if self.low is None else f"{self.low:g}{unit}"
        high = None if self.high is None else f"{self.high:g}{unit}"
        if low is not None and high is not None:
            return f"from {low} to {high}"
        if low is not None:
            return f"greater than {low}" if self.low_open else f"{low} or more"
        return f"{high} or less"


# the range of every value of a kind (the loader's kind words, ``schema.values``)
KIND_RANGES: dict[str, Range] = {
    "positive": Range(0, low_open=True),
    "max_length": Range(0),
    "lines": Range(1),
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
    # kinds the export names for keys whose loader reads the number itself (the Peek, an Edge, a
    # Shadow): the shell checks them in place, with these numbers in its messages
    "peek_size": Range(1),
    "non_negative": Range(0),
    "non_negative_ms": Range(0),
}

# the keys that take a range the kind does not give them
KEY_RANGES: dict[str, Range] = {
    "Opacity": Range(0, 1),
    "Handle_Opacity": Range(0, 1),
    "Flex_Grow": Range(0),
    "Flex_Shrink": Range(0),
    "Font_Weight": Range(1, 1000),
    "Border_Width": Range(0),
    "Hide_After": Range(0),
    "Enter_Delay": Range(0),
    "Exit_Delay": Range(0),
}

# keys of a kind with a non-negative range that may be negative: a Panel's ``Inset`` is a distance
# from the edge it is anchored to, and a compositor takes a negative margin
NEGATIVE_OK = frozenset({"Inset"})


# the kinds whose numbers a key's own range may narrow (the key is a plain number of that kind)
KEY_RANGE_KINDS = frozenset({"number", "whole", "unit"})


def range_of(kind: str, key: str = "") -> Range | None:
    """The range of a key of this kind: the key's own (for a plain number), else the kind's, else
    ``None``."""
    if key in KEY_RANGES and kind in KEY_RANGE_KINDS:
        return KEY_RANGES[key]
    if key in NEGATIVE_OK:
        return None
    return KIND_RANGES.get(kind)
