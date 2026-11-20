"""The user guide (``guide/``) stays true to the code.

The tables and example listings of the pages are generated (``tests/guide_tables.py``); these tests
generate them again in memory and compare, so a change in the schema, the command line or an
example fails until the pages are written again, and they check what a generator cannot: that every
module, settings section and example is on a page, that the links between pages land, and that the
commands and options the prose names exist.
"""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

import pytest

from tess_shell.cli import _build_parser
from tess_shell.exit_codes import ExitCode
from tess_shell.schema.export import schema_dict
from tests import guide_tables as g

SCHEMA = schema_dict()
PAGES = g.pages()
PAGE_NAMES = (
    "index.md",
    "install.md",
    "configuration-folder.md",
    "first-bar.md",
    "surfaces.md",
    "modules.md",
    "styling.md",
    "settings.md",
    "keyboard.md",
    "command-line.md",
    "troubleshooting.md",
    "tutorial.md",
    "monitors.md",
    "hot-reload.md",
    "session.md",
    "security.md",
    "writing-a-module.md",
)
FENCE = re.compile(r"^```")


def page_text(name: str) -> str:
    return (g.GUIDE / name).read_text(encoding="utf-8")


def test_the_guide_has_exactly_its_pages() -> None:
    assert sorted(p.name for p in PAGES) == sorted(PAGE_NAMES)


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_the_generated_parts_are_what_the_code_says_now(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    assert g.regenerate(text, SCHEMA) == text, (
        f"{page.name} is out of date: run "
        "`env -u WAYLAND_DISPLAY -u DISPLAY uv run python -m tests.guide_tables`"
    )


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_marker_is_part_of_a_pair(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    assert g.stray_markers(text) == []
    begins = re.findall(r"<!-- BEGIN generated: ([^>]+?) -->", text)
    ends = re.findall(r"<!-- END generated: ([^>]+?) -->", text)
    assert begins == ends == g.markers(text)


def test_every_page_has_the_tables_the_schema_asks_for() -> None:
    for name, wanted in g.required_markers(SCHEMA).items():
        have = g.markers(page_text(name))
        missing = [w for w in wanted if w not in have]
        assert not missing, f"{name} lacks the generated parts {missing}"


def test_every_example_set_is_shown_on_a_page() -> None:
    shown = {m for page in PAGES for m in g.markers(page.read_text(encoding="utf-8"))}
    sets = g.example_sets()
    assert sets, "no example sets"
    for folder in sets:
        name = folder.relative_to(g.EXAMPLES).as_posix()
        assert f"example-set:{name}" in shown, f"the example set {name} is on no page"


def test_every_example_file_is_inside_a_set() -> None:
    """A file straight under ``docs/guide/examples/`` or under a page folder belongs to no set, so
    no
    page would show it."""
    for path in g.EXAMPLES.iterdir():
        assert path.is_dir(), f"{path.name} is not in an example set"
        for inner in path.iterdir():
            assert inner.is_dir(), f"{path.name}/{inner.name} is not in an example set"


def test_every_marker_of_an_example_set_names_a_folder_that_exists() -> None:
    for page in PAGES:
        for name in g.markers(page.read_text(encoding="utf-8")):
            if name.startswith("example-set:"):
                assert (g.EXAMPLES / name.partition(":")[2]).is_dir(), (page.name, name)


def test_the_listing_of_a_set_holds_each_of_its_text_files() -> None:
    for folder in g.example_sets():
        name = folder.relative_to(g.EXAMPLES).as_posix()
        listing = g.render(f"example-set:{name}", SCHEMA)
        for path in g.set_files(folder):
            assert path.read_text(encoding="utf-8").rstrip("\n") in listing, (name, path.name)


def test_every_kind_dependency_and_exit_code_has_a_line_of_text() -> None:
    assert set(SCHEMA["kinds"]) <= set(g.KIND_HELP)
    project = tomllib.loads((g.REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = {re.split(r"[\[<>=]", spec)[0] for spec in project["dependencies"]}
    assert names <= set(g.DEPENDENCY_NOTES)
    assert {c.name for c in ExitCode} == set(g.EXIT_NOTES)


def test_a_marker_the_generator_does_not_know_is_refused() -> None:
    with pytest.raises(KeyError):
        g.regenerate("<!-- BEGIN generated: nothing -->\n<!-- END generated: nothing -->", SCHEMA)


# -- links between the pages --------------------------------------------------------------------


def headings(text: str) -> set[str]:
    """The anchors GitHub makes for the headings of a page (not for a `#` line in a code block)."""
    anchors: set[str] = set()
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = re.match(r"^#{1,6}\s+(.*?)\s*#*$", line)
        if not fenced and match:
            slug = re.sub(r"[^\w\- ]", "", match.group(1).lower()).replace(" ", "-")
            anchors.add(slug)
    return anchors


def links(text: str) -> list[str]:
    """The relative links of a page that point inside the guide."""
    found = re.findall(r"\]\(([^)\s]+)\)", text)
    return [
        link
        for link in found
        if not link.startswith(("http", "mailto:", "..")) and not link.startswith("examples/")
    ]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_link_between_pages_lands(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    for link in links(text):
        target, _, anchor = link.partition("#")
        path = page if not target else g.GUIDE / target
        assert path.is_file(), f"{page.name}: the link {link} names no page"
        if anchor:
            assert anchor in headings(path.read_text(encoding="utf-8")), (
                f"{page.name}: the link {link} names no heading of {path.name}"
            )


def test_the_links_into_examples_land() -> None:
    for page in PAGES:
        for link in re.findall(r"\]\((examples/[^)\s]+)\)", page.read_text(encoding="utf-8")):
            assert (g.GUIDE / link).exists(), (page.name, link)


# -- the commands and options the prose names ---------------------------------------------------


def all_options(parser: argparse.ArgumentParser) -> set[str]:
    options: set[str] = set()
    for action in parser._actions:
        options.update(action.option_strings)
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                options |= all_options(child)
    return options


def command_names(parser: argparse.ArgumentParser) -> set[str]:
    names: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                names.add(name)
                names |= command_names(child)
    return names


def command_lines(text: str) -> list[str]:
    """Every ``tesserae-shell ...`` the page writes as a command: a line of a ``sh`` code block, or
    an inline code span."""
    found: list[str] = []
    lines = text.splitlines()
    block = ""
    for line in lines:
        fence = re.match(r"^```(\w*)", line)
        if fence:
            block = "" if block else fence.group(1) or "plain"
            continue
        if block == "sh":
            stripped = line.split("#", 1)[0].strip()
            if stripped.startswith("tesserae-shell"):
                found.append(stripped)
        elif not block:
            found.extend(m for m in re.findall(r"`(tesserae-shell[^`]*)`", line))
    return found


# an inline span that starts with the program's name but quotes a message, not a command
MESSAGES = ("tesserae-shell needs ", "tesserae-shell: ", "tesserae-shell <version>")


def test_the_commands_and_options_the_guide_names_exist() -> None:
    parser = _build_parser()
    commands = command_names(parser)
    options = all_options(parser)
    for page in PAGES:
        for line in command_lines(page.read_text(encoding="utf-8")):
            if line.startswith(MESSAGES) or line == "tesserae-shell":
                continue
            words = line.split()
            rest = [w for w in words[1:] if not w.startswith("-")]
            if rest and not rest[0].startswith(("[", "<", "NAME", "COMMAND", "SECONDS")):
                assert rest[0] in commands, f"{page.name}: `{line}` names no command {rest[0]}"
            for word in words[1:]:
                if word.startswith("--"):
                    flag = word.split("=")[0].rstrip(",;")
                    assert flag in options, f"{page.name}: `{line}` names no option {flag}"
