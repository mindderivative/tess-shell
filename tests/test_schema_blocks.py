"""The schema's key declaration and the binder's tables describe the same keys."""

from __future__ import annotations

from tess_shell.binder.tables import BLOCKS as TABLES
from tess_shell.schema import blocks


def test_same_blocks() -> None:
    assert set(blocks.BLOCKS) == set(TABLES)


def test_same_keys_kinds_and_choices() -> None:
    for name, (props, style) in blocks.BLOCKS.items():
        row = TABLES[name]
        assert {k: v.convert for k, v in row.keys.items()} == _kinds(props, name), name
        assert {k: v.convert for k, v in row.style.items()} == _kinds(style, name), name
        for scope_table, schema_table in ((row.keys, props), (row.style, style)):
            for key, key_row in scope_table.items():
                if key_row.convert == "enum":
                    assert key_row.choices == (
                        blocks.CHOICES.get((name, key)) or blocks.CHOICES[("*", key)]
                    ), (name, key)
                assert schema_table[key] is not None


def _kinds(table: dict[str, str], block: str) -> dict[str, str]:
    # the SVG source is text to the binder; the schema reads the file it names
    return {k: ("text" if v == "svg_source" else v) for k, v in table.items()}


def test_required_keys_agree() -> None:
    for name, row in TABLES.items():
        assert row.required == blocks.REQUIRED.get(name, ())
