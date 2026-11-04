"""Small helpers over the ``tess_dl`` tree, which has no accessors of its own in 0.1."""

from __future__ import annotations

from tess_dl import Block, Origin, Property, String, Value, Word


def properties(block: Block) -> list[Property]:
    return [e for e in block.entries if isinstance(e, Property)]


def child_blocks(block: Block) -> list[Block]:
    return [e for e in block.entries if isinstance(e, Block)]


def find_property(block: Block, key: str) -> Property | None:
    for prop in properties(block):
        if prop.key == key:
            return prop
    return None


def value_text(value: Value) -> str | None:
    """The text of a word or string value, ``None`` for any other kind of value."""
    if isinstance(value, Word):
        return value.text
    if isinstance(value, String):
        return value.value
    return None


def position(origin: Origin | None) -> tuple[int, int]:
    """``(line, column)`` of an origin, ``(1, 1)`` for a node built in code."""
    if origin is None:
        return (1, 1)
    return (origin.line, origin.column)
