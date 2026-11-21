"""The tooltip belongs to the control, never to a row, group or container, and never nests
(Tooltip > AC-TIP-1, owner feedback F8): a static check over every shipped module's layout, and the
Marquee inside a Task Item, which has its tooltip on the item, does not open one of its own."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tess_shell.binder import model as m
from tess_shell.config.settings import load_settings
from tess_shell.scanner import scan
from tests.shell_samples import write_example

NOT_A_CONTROL = {"GROUP", "LIST", "LISTITEM", "TREE", "TREEITEM", "TABPANEL", "DIALOG", "MENU"}


def modules() -> dict[str, Any]:
    folder = Path(tempfile.mkdtemp())
    write_example(folder)
    settings, _ = load_settings(folder)
    assert settings is not None
    return scan(settings, folder).modules


def walk(children: Any) -> Iterator[Any]:
    for child in children or ():
        yield child
        yield from walk(getattr(child, "children", ()))
        yield from walk(getattr(child, "body", ()))
        yield from walk(getattr(child, "else_body", ()))


def has_tooltip(node: Any) -> bool:
    return getattr(node, "tooltip", None) is not None or "Tooltip" in getattr(node, "props", {})


def role_of(node: Any) -> str:
    role = getattr(node, "props", {}).get("Role")
    return role.name if isinstance(role, m.Enum) else ""


def test_no_shipped_tooltip_is_on_a_group_row_or_container_and_none_nests() -> None:
    bad = []
    for name, module in modules().items():
        for node in walk(module.definition.children):
            if not has_tooltip(node):
                continue
            if role_of(node) in NOT_A_CONTROL:
                bad.append(
                    f"{name}: a tooltip on a {role_of(node)} block {getattr(node, 'name', '')}"
                )
            if any(has_tooltip(inner) for inner in walk(getattr(node, "children", ()))):
                bad.append(f"{name}: a tooltip on {getattr(node, 'name', node)} has one below it")
    assert not bad, bad


def test_the_task_item_has_its_tooltip_on_the_item_and_its_marquee_opens_none_of_its_own() -> None:
    root = next(
        n
        for n in walk(modules()["Task_Item"].definition.children)
        if getattr(n, "name", None) == "Root"
    )
    assert has_tooltip(root) and role_of(root) == "BUTTON"
    marquee = [n for n in walk(root.children) if getattr(n, "module", "") == "Marquee_Text"]
    assert marquee, "the title is a Marquee_Text"
    for call in marquee:
        flag = call.params.get("tooltip")
        assert isinstance(flag, m.Bool) and flag.value is False, "one tooltip per control"


@pytest.mark.parametrize("name", ["Battery", "Network"])
def test_a_display_module_has_its_tooltip_on_one_named_content_image(name: str) -> None:
    content = [
        n
        for n in walk(modules()[name].definition.children)
        if getattr(n, "name", None) == "Content"
    ]
    assert len(content) == 1 and has_tooltip(content[0]) and role_of(content[0]) == "IMG"
    root = next(
        n for n in walk(modules()[name].definition.children) if getattr(n, "name", None) == "Root"
    )
    assert not has_tooltip(root) and role_of(root) == ""


def test_audio_has_one_tooltip_on_the_mute_button_and_one_on_the_slider() -> None:
    nodes = list(walk(modules()["Audio"].definition.children))
    carriers = [n for n in nodes if has_tooltip(n)]
    names = sorted(getattr(n, "name", None) or getattr(n, "module", "") for n in carriers)
    assert names == ["Slider", "Toggle"] or names == ["Toggle", "Volume"], names
    assert not [n for n in carriers if role_of(n) in NOT_A_CONTROL]
