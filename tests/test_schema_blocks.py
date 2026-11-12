"""The schema's key declaration and the binder's tables describe the same keys."""

from __future__ import annotations

from tess_shell.binder.tables import BLOCKS as TABLES
from tess_shell.schema import blocks

FIELD_ROWS = ("TextField", "TextField.line", "TextField.size", "TextField.input")


def _schema(name: str) -> tuple[dict[str, str], dict[str, str]]:
    return blocks.BLOCKS.get(name) or blocks.INTERNAL[name]


def test_same_blocks() -> None:
    assert set(blocks.BLOCKS) | set(blocks.INTERNAL) == set(TABLES)


def test_same_keys_kinds_and_choices() -> None:
    for name, row in TABLES.items():
        if name == "TextField":
            props, style = blocks.FIELD_BOX
        elif name == "Marquee":
            props, style = blocks.MARQUEE_BOX
        else:
            props, style = _schema(name)
        assert {k: v.convert for k, v in row.keys.items()} == _kinds(props, name), name
        assert {k: v.convert for k, v in row.style.items()} == _kinds(style, name), name
        for scope_table, schema_table in ((row.keys, props), (row.style, style)):
            for key, key_row in scope_table.items():
                if key_row.convert == "enum":
                    assert key_row.choices == (
                        blocks.CHOICES.get((name, key)) or blocks.CHOICES[("*", key)]
                    ), (name, key)
                assert schema_table[key] is not None


def test_the_textfield_block_is_the_keys_of_its_three_nodes() -> None:
    """The user-facing TextField takes the keys of the box, the size text and the text input
    together; the model splits them (``model.field``), each node taking its own."""
    props, style = blocks.BLOCKS["TextField"]
    rows = [TABLES[name] for name in FIELD_ROWS]
    assert props.keys() == {k for r in rows for k in r.keys}
    assert style.keys() == {k for r in rows for k in r.style}
    for key, kind in {**props, **style}.items():
        kinds = {
            r.convert
            for row in rows
            for t in (row.keys, row.style)
            for k, r in t.items()
            if k == key
        }
        assert kinds == {kind}, key
    # the sets the split uses are the tables'
    for name, wanted in (
        ("TextField", blocks.FIELD_BOX_KEYS),
        ("TextField.input", blocks.FIELD_INPUT_KEYS),
        ("TextField.size", blocks.FIELD_SIZE_KEYS),
    ):
        assert wanted == TABLES[name].keys.keys() | TABLES[name].style.keys(), name


def _kinds(table: dict[str, str], block: str) -> dict[str, str]:
    # the SVG source is text to the binder; the schema reads the file it names
    return {k: ("text" if v in ("svg_source", "icon") else v) for k, v in table.items()}


def test_required_keys_agree() -> None:
    for name, row in TABLES.items():
        assert row.required == blocks.REQUIRED.get(name, ())


def test_there_is_no_key_that_opens_a_disabled_blocks_tooltip() -> None:
    """The one exception is a cut Marquee text (M4 Brief, question 24); no block key opts in."""
    from tess_shell.binder.tables import BLOCKS

    assert "Tooltip_When_Disabled" not in blocks.COMMON
    assert all("Tooltip_When_Disabled" not in row.keys for row in BLOCKS.values())
