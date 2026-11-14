"""The JSON export of the schema (``tesserae-shell schema --json``): it carries every key the loader
accepts and nothing it refuses, with what the loader says of each key's value.

The export reads the loader's tables, so these tests do not compare it with those tables alone:
they put keys in files and ask the loader (``read_shell``, ``read_module``, ``read_stylesheet``,
``load_settings``), the way a person's file would."""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import tess_dl

from tess_shell.binder import convert
from tess_shell.binder import model as m
from tess_shell.cli import main
from tess_shell.config import settings as cfg
from tess_shell.config.paths import FOLDERS
from tess_shell.config.settings import load_settings
from tess_shell.schema import blocks, docs, export
from tess_shell.schema.export import schema_dict, schema_json
from tess_shell.schema.findings import Finding
from tess_shell.schema.look import STYLE_UNION, read_stylesheet
from tess_shell.schema.shell import BAR_KEYS, read_module, read_shell
from tess_shell.schema.values import ValueProblem, coerce

D: dict[str, Any] = schema_dict()
SVG = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 4'><rect width='4' height='4'/></svg>"
SHELL_HEAD = "---\nTDL: 0.1\nShell: 0.1\nName: Main_Shell\n---\n"
FILE_HEAD = "---\nTDL: 0.1\nName: Probe\n---\n"
ORIGIN = m.Origin("", 1, 1)


class Icons:
    def lookup(self, name: str) -> str | None:
        return SVG

    def nearest(self, name: str) -> list[str]:
        return []


# the findings that say a key or its value was not taken as written
BAD = {"unknown-key", "bad-value", "bad-token", "bad-sides", "bad-name"}
REFUSED = {"unknown-key", "event-not-raised", "peek-slide-from"}


# -- running the loader on a probe --------------------------------------------------------------

# spec -> (file kind, a file with the line ``@`` where the probes go)
CONTEXTS: dict[str, tuple[str, str]] = {
    "Monitor": ("shell", "Shell { Monitor {\n@\n} }"),
    "Bar": ("shell", "Shell { Monitor { Name: M, Children { Bar {\n@\n} } } }"),
    "Bar.style": ("shell", "Shell { Monitor { Name: M, Children { Bar { Style {\n@\n} } } } }"),
    "Panel": ("shell", "Shell { Monitor { Name: M, Children { Panel {\n@\n} } } }"),
    "Panel.style": (
        "shell",
        "Shell { Monitor { Name: M, Children { Panel { Style {\n@\n} } } } }",
    ),
    "Popup": ("shell", "Shell { Monitor { Name: M, Children { Popup {\n@\n} } } }"),
    "Popup.style": (
        "shell",
        "Shell { Monitor { Name: M, Children { Popup { Style {\n@\n} } } } }",
    ),
    "Tooltip": (
        "module",
        "Module { Children { Box { Tooltip {\n@\n} } } }",
    ),
    "Frame": ("shell", "Shell { Monitor { Name: M, Children { Frame {\n@\n} } } }"),
    "Frame.style": (
        "shell",
        "Shell { Monitor { Name: M, Children { Frame { Style {\n@\n} } } } }",
    ),
    "Edge": (
        "shell",
        "Shell { Monitor { Name: M, Children { Frame { Name: F, Edges { Top {\n@\n} } } } } }",
    ),
    "Border": (
        "shell",
        "Shell { Monitor { Name: M, Children { Frame { Inner_Border {\n@\n} } } } }",
    ),
    "Animation": (
        "shell",
        "Shell { Monitor { Name: M, Children { Panel { Animation {\n@\n} } } } }",
    ),
    "Peek": (
        "shell",
        "Shell { Monitor { Name: M, Children { Panel { Peek {\n@\n} } } } }",
    ),
    "Edge_Peek": (
        "shell",
        "Shell { Monitor { Name: M, Children { Frame { Edges { Top { Peek {\n@\n} } } } } } }",
    ),
    "Shadow": (
        "module",
        "Module { Children { Box { Style { Shadows { Shadow {\n@\n} } } } } }",
    ),
    "Sides": ("module", "Module { Children { Box { Padding {\n@\n} } } }"),
    "Rule": ("stylesheet", 'Stylesheet { Rule { Selector: ".c"\n@\n} }'),
    "Class": ("style", "Style { Classes { c { Kind: Text\n@\n} } }"),
    "Param": ("module", "Module { Params { p {\n@\n} } Children { Box { } } }"),
}
for _name in blocks.BLOCKS:
    CONTEXTS[_name] = ("module", f"Module {{ Children {{ {_name} {{\n@\n}} }} }}")
    CONTEXTS[f"{_name}.style"] = (
        "module",
        f"Module {{ Children {{ {_name} {{ Style {{\n@\n}} }} }} }}",
    )


def run(kind: str, text: str) -> list[Finding]:
    if kind == "shell":
        result = tess_dl.parse(SHELL_HEAD + text, path="Main_Shell.tdl")
        assert not result.errors and result.document is not None, result.errors
        return read_shell(
            result.document, "Main_Shell.tdl", lambda p: SVG, icons=Icons(), resolve_path=str
        )[1]
    result = tess_dl.parse(FILE_HEAD + text, path="Probe.tdl")
    assert not result.errors and result.document is not None, (result.errors, text)
    if kind == "module":
        return read_module(
            result.document, "Probe_Module.tdl", None, None, None, Icons(), lambda p: SVG, str
        )[1]
    if kind == "stylesheet":
        return read_stylesheet(result.document, "Probe_Stylesheet.tdl")[1]
    assert kind == "style"
    from tess_shell.schema.shell import read_style

    return read_style(result.document, "Probe_Style.tdl")[1]


def probe(spec: str, lines: list[str]) -> dict[int, list[Finding]]:
    """The findings of each probe line, by its index in ``lines``."""
    kind, template = CONTEXTS[spec]
    marker = "@"
    head = (SHELL_HEAD if kind == "shell" else FILE_HEAD).count("\n")
    before = template.split(marker)[0]
    first = head + before.count("\n") + 1
    # the ``@`` stands alone on its line, so probe i is on line ``first + i``
    findings = run(kind, template.replace(marker, "\n".join(lines)))
    out: dict[int, list[Finding]] = {i: [] for i in range(len(lines))}
    for f in findings:
        if first <= f.line < first + len(lines):
            out[f.line - first].append(f)
    return out


def probe_each(spec: str, lines: list[str]) -> dict[int, list[Finding]]:
    """As :func:`probe`, one file for each line (a key written twice is a syntax error)."""
    return {i: probe(spec, [line])[0] for i, line in enumerate(lines)}


# -- a sample of each kind ----------------------------------------------------------------------


def sample(key: dict[str, Any]) -> str | None:
    """A value the loader should take for this key, written as TDL; ``None`` for a block."""
    match key["kind"]:
        case "string" | "font" | "text_or_number":
            return '"Sans"' if key["kind"] == "font" else '"x"'
        case "name" | "name_ref":
            return "Foo"
        case "bool" | "enabled":
            return "true"
        case "number" | "whole":
            low = key.get("min")
            return str(max(1, low or 0))
        case "duration":
            return "100"
        case "percent":
            return "20%"
        case "length":
            return "10"
        case "sides" | "radius":
            return "4"
        case "color":
            return '"#112233"'
        case "enum":
            return key["choices"][0]
        case "path":
            return '"x.svg"'
        case "icon":
            return '"mdi:account"'
        case "input_region":
            return "[]"
        case "monitor_index":
            return "0"
        case "list":
            item, length = key["item_kind"], key.get("length")
            if item == "number" and length == 4:
                return "[0, 0, 4, 4]"
            if item == "whole" and length == 2:
                return "[0, 1]"
            if item == "enum":
                return f"[{key['choices'][0]}]"
            return "[Width]" if item == "string" else "[a]"
    return None  # a block, a tooltip, a shadow list


def every_key() -> list[tuple[str, str, str, dict[str, Any]]]:
    """(context, part, key, spec) of every key of every root and block."""
    out = []
    for sect in ("roots", "blocks"):
        for name, spec in D[sect].items():
            for part in ("keys", "style"):
                for key, entry in spec[part].items():
                    out.append((name, part, key, entry))
    return out


# -- the shape ----------------------------------------------------------------------------------


def test_top_level_shape() -> None:
    assert D["schema_version"] == "1.2"
    assert D["shell_version"]
    assert list(D) == [
        "schema_version",
        "shell_version",
        "kinds",
        "roots",
        "blocks",
        "settings",
        "events",
        "actions",
        "enums",
        "tokens",
        "modules",
        "popups",
    ]
    assert list(D["blocks"]) == list(blocks.BLOCKS)
    for spec in (*D["roots"].values(), *D["blocks"].values()):
        assert set(spec) == {
            "doc",
            "heads",
            "keys",
            "style",
            "events",
            "required",
            "repeatable",
            "allowed_children",
            "module_calls",
            "example",
            "not_built",
        }
    for _, _, _, key in every_key():
        assert {
            "kind",
            "choices",
            "enum",
            "default",
            "doc",
            "slot",
            "required",
            "built",
            "group",
            "tokens",
            "preferred_tokens",
        } <= set(key)


def test_two_runs_give_the_same_bytes_and_the_tables_order() -> None:
    assert schema_json() == schema_json()
    assert json.loads(schema_json()) == D
    assert list(D["roots"]["Bar"]["keys"]) == [
        "Name",
        *BAR_KEYS,
        *blocks.BAR_NOT_BUILT,
    ]
    assert list(D["blocks"]["Box"]["keys"]) == [
        *export.IDENTITY_KEYS,
        *blocks.BLOCKS["Box"][0],
    ]
    assert list(D["blocks"]["Box"]["style"]) == list(blocks.BLOCKS["Box"][1])


def test_another_process_with_another_hash_seed_gives_the_same_bytes(tmp_path: Path) -> None:
    outputs = []
    for seed in ("1", "2"):
        done = subprocess.run(
            [sys.executable, "-m", "tess_shell", "schema", "--json"],
            capture_output=True,
            text=True,
            check=False,
            env={"PYTHONHASHSEED": seed, "PATH": "", "HOME": str(tmp_path)},
        )
        assert done.returncode == 0, done.stderr
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1] == schema_json()


def test_every_loader_kind_is_mapped_and_every_output_kind_is_described() -> None:
    for model_kind in export.LOADER_KINDS:
        export._kind_fields(model_kind, "Box", "Width", ())
    tables = [
        blocks.COMMON,
        BAR_KEYS,
        blocks.BAR_STYLE,
        blocks.PANEL_KEYS,
        blocks.PANEL_STYLE,
        blocks.POPUP_KEYS,
        blocks.FRAME_KEYS,
        blocks.FRAME_STYLE,
        *(t for pair in blocks.BLOCKS.values() for t in pair),
    ]
    for table in tables:
        for kind in table.values():
            assert kind in export.LOADER_KINDS, kind
    for _, _, _, key in every_key():
        assert key["kind"] is None or key["kind"] in D["kinds"], key
    for kind in D["kinds"].values():
        assert kind["ui"] and kind["note"]


# -- (a) every key the loader accepts is in the export, and only those ---------------------------


def words() -> list[str]:
    """Every capitalised word in the sources that read a file, and every exported key: the keys a
    person might write, found without the export's tables."""
    src = Path(export.__file__).parent
    found: set[str] = set()
    for path in (
        src / "shell.py",
        src / "blocks.py",
        src / "look.py",
        src / "values.py",
        src.parent / "config" / "settings.py",
        src.parent / "config" / "paths.py",
    ):
        found.update(re.findall(r'"([A-Z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)"', path.read_text()))
    found.update(key for _, _, key, _ in every_key())
    found.update({"Colour", "Zzz_Not_A_Key", "Border_Colour"})
    return sorted(found)


def writable(shape: str) -> list[str]:
    """The words that can be written in ``shape`` (some are the language's own: ``If``, ``Key``)."""
    head = "---\nTDL: 0.1\nName: P\n---\n"
    return [
        w
        for w in words()
        if not tess_dl.parse(head + "X { " + shape.replace("@@", w) + " }").errors
    ]


PROP_POOL = writable("@@: 1")
BLOCK_POOL = writable("@@ { }")
# the blocks (and the one property) a context takes besides its keys
STRUCTURAL = {"Children", "Style", "Border"}


def collides(spec: str, key: str) -> bool:
    """Whether the context's own block already writes this key (a key written twice is a syntax
    error): the key is there by construction."""
    template = CONTEXTS[spec][1]
    inner = template.split("@")[0]
    inner = inner[inner.rfind("{") + 1 :]
    return re.search(rf"\b{key}\s*:", inner) is not None


def accepted(spec: str) -> tuple[set[str], set[str]]:
    """The words of the pool the loader takes in this context, written ``Word: 1`` and as a block
    ``Word { }`` (the second only where the context reports a block it does not know)."""
    kind, template = CONTEXTS[spec]
    if spec in ("Shadow", "Sides"):  # the loader reports the first unknown key of these, once
        return {
            w
            for w in PROP_POOL
            if not any(f.rule == "unknown-key" for f in run(kind, template.replace("@", f"{w}: 1")))
        }, set()
    props = {w for w in PROP_POOL if collides(spec, w)}
    pool = [w for w in PROP_POOL if not collides(spec, w)]
    found = probe(spec, [f"{w}: 1" for w in pool])
    props |= {w for i, w in enumerate(pool) if not any(f.rule in REFUSED for f in found[i])}
    taken: set[str] = set()
    if any(f.rule in REFUSED for f in probe(spec, ["Zzz_Not_A_Key { }"])[0]):
        found = probe(spec, [f"{w} {{ }}" for w in BLOCK_POOL])
        taken = {
            w for i, w in enumerate(BLOCK_POOL) if not any(f.rule in REFUSED for f in found[i])
        }
    return props, taken


def names(spec: Mapping[str, Any], part: str = "keys") -> set[str]:
    return set(spec[part])


def agree(
    spec: str,
    keys: Mapping[str, Mapping[str, Any]],
    events: set[str] | None = None,
    extra: set[str] | None = None,
) -> None:
    """What the loader takes in ``spec`` is what ``keys`` lists: every listed key is taken (a block
    key as a block), nothing else is, but the structure the context has besides its keys."""
    props, blocks_ = accepted(spec)
    exported = set(keys)
    events = events or set()
    assert "Zzz_Not_A_Key" not in props | blocks_
    assert props & set(blocks.EVENT_KEYS) == events, spec
    assert props - events - (extra or set()) <= exported, (spec, sorted(props - exported))
    assert exported <= props | blocks_, (spec, sorted(exported - props - blocks_))
    block_only = {k for k in exported - props}
    assert all(keys[k]["kind"] in ("block", "shadows", "sides") for k in block_only), (
        spec,
        sorted(block_only),
    )
    assert blocks_ - props - exported <= STRUCTURAL, (spec, sorted(blocks_ - props - exported))


@pytest.mark.parametrize("name", list(blocks.BLOCKS))
def test_a_block_takes_the_exported_keys_and_no_other(name: str) -> None:
    spec = D["blocks"][name]
    agree(name, {**spec["keys"], **spec["style"]}, set(spec["events"]), {"Style"})


@pytest.mark.parametrize("name", list(blocks.BLOCKS))
def test_a_blocks_style_takes_the_exported_style_keys_and_no_other(name: str) -> None:
    agree(f"{name}.style", D["blocks"][name]["style"])


@pytest.mark.parametrize(
    ("spec", "extra"),
    [
        ("Monitor", set()),
        ("Bar", {"Style"}),
        ("Panel", {"Style"}),
        ("Popup", {"Style"}),
        ("Frame", {"Style"}),
        ("Edge", set()),
        ("Border", set()),
        ("Animation", set()),
        ("Peek", set()),
        ("Edge_Peek", {"Slide_From"}),
        ("Shadow", set()),
        ("Sides", set()),
        ("Rule", set()),
        ("Class", set()),
        ("Param", set()),
    ],
)
def test_a_root_takes_the_exported_keys_and_no_other(spec: str, extra: set[str]) -> None:
    root = D["roots"][spec]
    keys = dict(root["keys"])
    if spec == "Rule":  # a rule writes style keys beside its Selector
        keys |= root["style"]
    if spec == "Class":  # the keys of the block its Kind names come with it
        keys |= {k: {"kind": None} for k in blocks.BLOCKS["Text"][1]}
    agree(spec, keys, set(root["events"]), extra)


@pytest.mark.parametrize("spec", ["Bar", "Panel", "Popup", "Frame"])
def test_a_surfaces_style_takes_the_exported_style_keys_and_no_other(spec: str) -> None:
    agree(f"{spec}.style", D["roots"][spec]["style"])


def test_the_root_tables_are_what_the_export_lists() -> None:
    roots = D["roots"]
    assert names(roots["Panel"]) >= set(blocks.PANEL_KEYS) | set(blocks.PANEL_NOT_BUILT_ERROR)
    assert names(roots["Popup"]) >= set(blocks.POPUP_KEYS) | set(blocks.POPUP_NOT_BUILT)
    assert names(roots["Frame"]) >= set(blocks.FRAME_KEYS) | set(blocks.FRAME_NOT_BUILT_ERROR)
    assert names(roots["Tooltip"]) == names(roots["Popup"]) - {"Name", "Tooltip"}
    assert names(roots["Edge"]) >= set(blocks.EDGE_KEYS)
    assert names(roots["Peek"]) - {"Slide_From"} == names(roots["Edge_Peek"])
    assert set(roots["Edges"]["allowed_children"]) == set(blocks.EDGE_SIDES)
    assert set(roots["Edge"]["heads"]) == set(blocks.EDGE_SIDES)
    assert set(roots["Bar"]["style"]) == set(blocks.BAR_STYLE)
    assert set(roots["Frame"]["style"]) == set(blocks.FRAME_STYLE)
    assert set(roots["Rule"]["style"]) == set(STYLE_UNION)


def test_the_children_a_block_may_hold_are_the_ones_the_loader_takes() -> None:
    for name, spec in D["blocks"].items():
        found = probe(name, ["Children { }"])[0]
        refused = any(f.rule == "bad-children" for f in found)
        assert refused == (not spec["allowed_children"]), name
        assert (spec["allowed_children"] == list(blocks.BLOCKS)) or not spec["allowed_children"]


def test_every_exported_key_takes_a_value_of_its_kind() -> None:
    bad = []
    for name, part, key, entry in every_key():
        value = sample(entry)
        spec = name if part == "keys" else f"{name}.style"
        if value is None or spec not in CONTEXTS or not entry["built"]:
            continue
        if name in D["blocks"] and key in blocks.A11Y_STATE:
            pass  # a module's layout writes these: the harness is one
        if collides(spec, key):
            continue
        found = probe_each(spec, [f"{key}: {value}"])[0]
        problems = [f for f in found if f.rule in BAD]
        if problems:
            bad.append((spec, key, value, problems[0].message))
    assert bad == []


def test_a_state_key_is_for_a_module_and_a_shell_file_refuses_it() -> None:
    for key in blocks.A11Y_STATE:
        assert D["blocks"]["Box"]["keys"][key]["module_only"] is True
    found = run(
        "shell",
        "Shell { Monitor { Name: M, Children { Bar { Name: B, Edge: TOP, "
        "Width: 10, Height: 10, Children { Box { Checked: true } } } } } }",
    )
    assert any(f.rule == "state-by-module" for f in found)


def test_a_slot_is_taken_where_the_export_says() -> None:
    bad = []
    for name, spec in D["blocks"].items():
        for part, context in (("keys", name), ("style", f"{name}.style")):
            for key, entry in spec[part].items():
                if entry["kind"] in ("block", "tooltip", "shadows"):
                    continue
                found = probe(context, [f"{key}: {{{{ x }}}}"])[0]
                refused = any(f.rule in BAD for f in found)
                if refused == entry["slot"]:
                    bad.append((name, part, key, entry["slot"]))
    assert bad == []


def test_a_surface_takes_no_slot() -> None:
    for name in ("Bar", "Panel", "Popup", "Frame"):
        for key, entry in D["roots"][name]["keys"].items():
            assert entry["slot"] is False
            if entry["kind"] in ("block", "tooltip", None) or not entry["built"]:
                continue
            found = probe(name, [f"{key}: {{{{ x }}}}"])[0]
            assert any(f.rule in BAD for f in found), (name, key)


def test_the_required_keys_are_the_ones_the_loader_asks_for() -> None:
    # a block: nothing written, and the loader says what is missing
    for name, spec in D["blocks"].items():
        wanted = {tuple(group) for group in spec["required"]}
        text = run(CONTEXTS[name][0], CONTEXTS[name][1].replace("@", ""))
        said = {f.message for f in text if f.rule == "missing-key"}
        assert bool(wanted) == bool(said), name
        for group in wanted:
            assert any(" or ".join(group) in message for message in said), (name, group)
    # a surface: it loads with every required key, and leaving out any one is a missing key
    bodies = {
        "Bar": "Shell {{ Monitor {{ Name: M, Children {{ Bar {{ {body} }} }} }} }}",
        "Panel": "Shell {{ Monitor {{ Name: M, Children {{ Panel {{ {body} }} }} }} }}",
        "Popup": "Shell {{ Monitor {{ Name: M, Children {{ Popup {{ {body} }} }} }} }}",
        "Frame": "Shell {{ Monitor {{ Name: M, Children {{ Frame {{ {body} }} }} }} }}",
        "Monitor": "Shell {{ Monitor {{ {body} }} }}",
    }
    full = {
        "Bar": ["Name: B", "Edge: TOP", "Width: 10", "Height: 10"],
        "Panel": ["Name: P", "Width: 10", "Height: 10"],
        "Popup": ["Name: P"],
        "Frame": ["Name: F", "Thickness: 4"],
        "Monitor": ["Name: M"],
    }
    for spec, template in bodies.items():
        entries = full[spec]
        loaded = run("shell", template.format(body=", ".join(entries)))
        assert [f for f in loaded if f.rule == "missing-key"] == [], spec
        keys = D["roots"][spec]["keys"]
        alone = {group[0] for group in D["roots"][spec]["required"] if len(group) == 1}
        assert {k for k, v in keys.items() if v["required"]} == alone, spec
        for entry in entries:
            rest = [e for e in entries if e != entry]
            answer = run("shell", template.format(body=", ".join(rest)))
            assert any(f.rule == "missing-key" for f in answer), (spec, entry)
        # every group the export lists names a key of the Bar, Panel, ... the loader asks for
        for group in D["roots"][spec]["required"]:
            assert any(e.split(":")[0] in group for e in entries), (spec, group)


# -- (b) every enum choice is taken and a word outside is refused --------------------------------


def test_every_exported_choice_is_taken_and_a_word_outside_is_refused() -> None:
    bad = []
    for name, part, key, entry in every_key():
        if entry["kind"] != "enum" or not entry["built"]:
            continue
        spec = name if part == "keys" else f"{name}.style"
        if spec not in CONTEXTS or collides(spec, key):
            continue
        lines = [f"{key}: {choice}" for choice in entry["choices"]] + [f"{key}: ZZZ_NOT_A_CHOICE"]
        found = probe_each(spec, lines)
        for i, choice in enumerate(entry["choices"]):
            if any(f.rule in BAD for f in found[i]):
                bad.append((spec, key, choice, "refused"))
        if not any(f.rule == "bad-value" for f in found[len(lines) - 1]):
            bad.append((spec, key, "ZZZ_NOT_A_CHOICE", "taken"))
    assert bad == []


def test_a_lower_case_enum_word_is_refused_with_the_hint() -> None:
    found = probe("Bar", ["Edge: top"])[0]
    assert any(f.rule == "bad-value" and "upper case" in f.hint for f in found)


def test_named_enums_are_the_lists_the_keys_use() -> None:
    assert D["enums"] == {name: list(words) for name, words in export.NAMED_ENUMS.items()}
    for _, _, _, entry in every_key():
        if entry["enum"] is not None:
            assert entry["choices"] == D["enums"][entry["enum"]]
    for name in blocks.BLOCKS:
        for key, entry in D["blocks"][name]["keys"].items():
            if entry["kind"] == "enum":
                words = blocks.CHOICES.get((name, key)) or blocks.CHOICES.get(("*", key))
                assert entry["choices"] == list(words or ()), (name, key)
                assert entry["choices"], (name, key)


# -- (c) the kinds say what the loader checks ----------------------------------------------------


def accepts(kind: str, text: str, choices: tuple[str, ...] = ()) -> bool:
    result = tess_dl.parse(f"---\nTDL: 0.1\nName: P\n---\nX {{ K: {text} }}")
    assert not result.errors and result.document is not None, text
    (entry,) = result.document.root.entries
    assert isinstance(entry, tess_dl.Property)
    try:
        coerce(kind, entry.value, ORIGIN, choices)
        return True
    except ValueProblem:
        return False


def test_the_ranges_of_the_kinds_are_the_loaders() -> None:
    def fields(kind: str) -> dict[str, Any]:
        return export._kind_fields(kind, "Box", "Opacity", ())[1]

    assert fields("max_length")["min"] == 0
    assert accepts("max_length", "0") and not accepts("max_length", "-1")
    assert fields("lines")["min"] == 1
    assert accepts("lines", "1") and not accepts("lines", "0")
    assert (fields("unit")["min"], fields("unit")["max"]) == (0, 1)
    assert accepts("unit", "0") and accepts("unit", "1") and not accepts("unit", "1.5")
    assert fields("duration")["min"] == 0
    assert accepts("duration", "0") and not accepts("duration", "-1")
    assert fields("diameter")["min"] == 1
    assert accepts("diameter", "1") and not accepts("diameter", "0")
    assert (fields("elevation")["min"], fields("elevation")["max"]) == (0, 100)
    assert accepts("elevation", "100%") and not accepts("elevation", "101%")
    assert fields("whole")["step"] == 1
    assert not accepts("whole", "1.5")
    assert fields("view_box")["length"] == 4
    assert accepts("view_box", "[0, 0, 1, 1]") and not accepts("view_box", "[0, 0, 1]")
    assert fields("selection")["length"] == 2
    assert accepts("selection", "[0, 1]") and not accepts("selection", "[0]")
    assert accepts("sides", "[1, 2, 3, 4]") and not accepts("sides", "[1, 2]")
    assert fields("sides")["arity"] == [1, 4]
    assert fields("radius")["arity"] == [1, 4]
    assert accepts("radius", "[1, 2, 3, 4]") and not accepts("radius", "[1, 2]")
    assert accepts("bleed", "AUTO") and fields("bleed")["auto"] is True
    for form in ('"#112233"', '"#11223344"', '"#123"', '"#1234"', "rgba(1 2 3 0.5)"):
        assert accepts("color", form)
    # an unquoted # starts a comment, so the colour is written quoted (the form says so)


def test_what_the_binders_converters_refuse_the_export_says() -> None:
    def refused(kind: str, value: m.Value) -> bool:
        try:
            convert.CONVERTERS[kind](value, ("x",) * 4 if kind in ("sides",) else ("x",), ())
            return False
        except m.BindError:
            return True

    assert refused("positive", m.Number(0, origin=ORIGIN))
    assert export._kind_fields("positive", "Text", "Font_Size", ())[1]["min_exclusive"] is True
    assert refused("length", m.Length(-1, origin=ORIGIN))
    assert export._kind_fields("length", "Box", "Width", ())[1]["negative"] is False
    assert refused("sides", m.Length(-1, origin=ORIGIN))
    assert refused("radius", m.Length(-1, origin=ORIGIN))


def test_the_units_of_a_length_are_the_ones_it_takes() -> None:
    for name, part, key, entry in every_key():
        if entry["kind"] != "length" or not entry["built"] or name in ("Rule",):
            continue
        if key in ("Depth", "Length"):
            continue  # only a melded Panel's size: the loader judges them with Meld
        units = entry["units"]
        sizes = key in ("Width", "Height")
        assert units[0] == "px" and ("EXPAND" not in units or sizes), (name, key, units)
        context = name if part == "keys" else f"{name}.style"
        if context not in CONTEXTS:
            continue
        # the loader judges a percentage and AUTO; EXPAND on a size is its too, and on another
        # key the binder's converter refuses it
        for word, text in (("%", "10%"), ("AUTO", "AUTO")):
            found = probe_each(context, [f"{key}: {text}"])[0]
            refused = any(f.rule in BAD | {"not-built"} for f in found)
            assert refused == (word not in units), (name, key, word, units)
        if sizes:
            found = probe_each(context, [f"{key}: EXPAND"])[0]
            refused = any(f.rule in BAD | {"not-built"} for f in found)
            assert refused == ("EXPAND" not in units), (name, key, units)
        elif entry["kind"] == "length" and key not in ("Max_Width", "Max_Height"):
            with pytest.raises(m.BindError):
                convert.length(m.Expand(origin=ORIGIN), ("left",))


# -- (d) a line of doc for every key, nothing stale ----------------------------------------------


def settings_keys() -> list[tuple[str, str, dict[str, Any]]]:
    return [(s, k, v) for s, keys in D["settings"].items() for k, v in keys.items()]


def test_every_key_has_a_doc_line_and_a_group() -> None:
    missing = [(n, p, k) for n, p, k, e in every_key() if not e["doc"].strip()]
    assert missing == []
    ungrouped = [(n, p, k) for n, p, k, e in every_key() if not e["group"]]
    assert ungrouped == []
    assert [(s, k) for s, k, v in settings_keys() if not v["doc"].strip()] == []
    assert [
        (g, n) for g, tokens in D["tokens"].items() for n, v in tokens.items() if not v["doc"]
    ] == []
    assert [n for n, e in D["events"].items() if not e["doc"]] == []
    assert [a["name"] for a in D["actions"] if not a["doc"]] == []
    assert [n for n, s in {**D["roots"], **D["blocks"]}.items() if not s["doc"]] == []


def test_no_doc_line_describes_a_key_nothing_accepts() -> None:
    used = {k for _, _, k, _ in every_key()}
    pairs = {(n, k) for n, _, k, _ in every_key()}
    assert [k for k in docs.KEY_DOCS if k not in used] == []
    assert [p for p in docs.SPEC_DOCS if p not in pairs] == []
    assert [p for p in docs.SPEC_GROUPS if p not in pairs] == []
    assert [k for keys in docs.GROUPS.values() for k in keys if k not in used] == []
    assert [k for k in docs.UNITS if k not in used] == []
    assert [p for p in docs.LITERAL_DEFAULTS if p not in pairs] == []
    settings = {(s, k) for s, k, _ in settings_keys()}
    assert [p for p in docs.SETTINGS_DOCS if p not in settings] == []
    tokens = {v["ref"][1:] for g in D["tokens"].values() for v in g.values()}
    assert set(docs.TOKEN_DOCS) == tokens
    assert set(docs.EVENT_DOCS) == set(blocks.EVENT_KEYS)
    assert set(docs.ACTION_DOCS) == set(blocks.BUILTIN_ACTIONS)
    assert set(docs.EXAMPLES) <= set(D["roots"]) | set(D["blocks"])
    assert set(docs.SPEC_NOTES) == set(D["roots"]) | set(D["blocks"])


def test_a_key_is_in_one_group_only() -> None:
    seen: dict[str, str] = {}
    for group, keys in docs.GROUPS.items():
        for key in keys:
            assert key not in seen, (key, seen.get(key), group)
            seen[key] = group


# -- (e) a key not built is listed, flagged and refused or warned as the loader does -------------


def test_a_key_not_built_is_listed_flagged_and_reported_by_the_loader() -> None:
    for name, spec in D["roots"].items():
        for key in spec["not_built"]:
            assert key in spec["keys"], (name, key)
            assert spec["keys"][key]["built"] is False, (name, key)
        flagged = {k for k, v in spec["keys"].items() if not v["built"]}
        assert flagged == set(spec["not_built"]), name
    for name in ("Bar", "Panel", "Popup", "Frame"):
        for key in D["roots"][name]["not_built"]:
            entry = D["roots"][name]["keys"][key]
            found = probe(name, [f"{key}: 1", f"{key} {{ }}"])
            assert not any(f.rule == "unknown-key" for f in found[0]), (name, key)
            reported = [f for f in found[0] + found[1] if f.rule == "not-built"]
            assert reported, (name, key)
            assert any(f.severity == "error" for f in reported) == entry["refused"], (name, key)


def test_a_style_key_of_a_frame_not_built_is_flagged_too() -> None:
    style = D["roots"]["Frame"]["style"]
    written = {
        "Elevation": "Elevation: 20%",
        "Shadows": 'Shadows { Shadow { Color: "#000000" } }',
        "Shadow_Bleed": "Shadow_Bleed: AUTO",
    }
    for key in blocks.FRAME_STYLE_NOT_BUILT:
        assert style[key]["built"] is False and style[key]["refused"] is True
        found = run(
            "shell",
            "Shell { Monitor { Name: M, Children { Frame { Name: F, Thickness: 4, "
            f"Style {{ {written[key]} }} }} }} }} }}",
        )
        assert any(f.rule == "not-built" for f in found), key
    for key in set(style) - set(blocks.FRAME_STYLE_NOT_BUILT):
        assert style[key]["built"] is True


# -- (f) the command ------------------------------------------------------------------------------


def test_the_command_prints_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema", "--json"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out) == D
    assert out == schema_json()


def test_the_command_takes_json_before_the_command_too(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "schema"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == "1.2"


def test_out_writes_the_file_and_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "schema.json"
    assert main(["schema", "--json", "--out", str(target)]) == 0
    assert capsys.readouterr().out == ""
    assert target.read_text(encoding="utf-8") == schema_json()
    assert json.loads(target.read_text(encoding="utf-8")) == D


def test_out_into_a_missing_folder_is_an_environment_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["schema", "--json", "--out", str(tmp_path / "no" / "schema.json")]) == 2
    assert "cannot write" in capsys.readouterr().err


def test_schema_without_json_asks_for_it(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "--json" in captured.err


def test_the_module_entry_point_prints_the_same(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "schema", "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert done.returncode == 0 and json.loads(done.stdout) == D


# -- (g) the tokens are the shipped Default theme's -----------------------------------------------


def written(value: tess_dl.Value) -> str:
    match value:
        case tess_dl.String() | tess_dl.Number() | tess_dl.Percent() | tess_dl.Word():
            return value.text
    raise AssertionError(value)


def theme_entries(block: tess_dl.Block, prefix: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for entry in block.entries:
        if isinstance(entry, tess_dl.Property):
            out[".".join((*prefix, entry.key.lower()))] = entry.value
        elif isinstance(entry, tess_dl.Block) and entry.type == "Max":
            out[".".join((*prefix, "max"))] = entry
        elif isinstance(entry, tess_dl.Block):
            out.update(theme_entries(entry, (*prefix, entry.type.lower())))
    return out


def test_the_tokens_are_the_default_themes_with_its_modes() -> None:
    path = Path(export.__file__).parent.parent / "shipped" / "Themes" / "Default_Theme.tdl"
    result = tess_dl.parse(path.read_text(encoding="utf-8"), path=str(path))
    assert not result.errors and result.document is not None
    base: dict[str, Any] = {}
    modes: dict[str, set[str]] = {}
    for group in result.document.root.entries:
        assert isinstance(group, tess_dl.Block)
        if group.type != "Modes":
            base.update(theme_entries(group, (group.type.lower(),)))
            continue
        for mode in group.entries:
            assert isinstance(mode, tess_dl.Block)
            for sub in mode.entries:
                assert isinstance(sub, tess_dl.Block)
                for ref in theme_entries(sub, (sub.type.lower(),)):
                    modes.setdefault(mode.type.lower(), set()).add(ref)
    exported = {v["ref"][1:]: v for tokens in D["tokens"].values() for v in tokens.values()}
    assert set(exported) == set(base)
    assert list(D["tokens"]) == ["color", "type", "shape", "space", "elevation", "motion"]
    for ref, entry in exported.items():
        value = base[ref]
        if isinstance(value, tess_dl.Block):
            assert entry["default"].startswith("Max { Shadows { Shadow {")
        else:
            assert entry["default"] == written(value), ref
        group, _, name = ref.partition(".")
        assert D["tokens"][group][name] is entry
        assert (
            entry["modes"] == [mode for mode in modes if ref in modes[mode]] or not entry["modes"]
        )
    overridden = {ref for refs in modes.values() for ref in refs}
    assert {ref for ref, e in exported.items() if e["modes"]} == overridden
    for name_, refs in modes.items():
        assert {ref for ref, e in exported.items() if name_ in e["modes"]} == refs


def test_a_token_of_a_kind_the_loader_checks_has_that_kind_and_the_rest_none() -> None:
    assert D["tokens"]["color"]["surface"]["kind"] == "color"
    assert D["tokens"]["type"]["body.font_size"]["kind"] == "number"
    assert D["tokens"]["type"]["body.font_weight"]["kind"] == "whole"
    assert D["tokens"]["shape"]["small"]["kind"] == "number"
    assert D["tokens"]["motion"]["duration.short"]["kind"] == "number"
    assert D["tokens"]["elevation"]["max"]["kind"] == "shadows"
    assert D["tokens"]["elevation"]["reach"]["kind"] is None
    assert D["tokens"]["motion"]["easing.standard"]["kind"] is None


def test_a_key_lists_the_token_groups_whose_values_it_can_read() -> None:
    color = D["blocks"]["Box"]["style"]["Background"]
    assert color["tokens"] == ["color"]
    size = D["blocks"]["Text"]["style"]["Font_Size"]
    assert "type" in size["tokens"] and "color" not in size["tokens"]
    assert D["blocks"]["Box"]["style"]["Shadows"]["tokens"] == ["elevation"]
    assert D["blocks"]["Text"]["keys"]["Text"]["tokens"] == []
    assert D["roots"]["Panel"]["keys"]["Width"]["tokens"] == []  # a surface key reads none
    # and the loader reads a token there: it is a reference the model resolves
    each = probe_each(
        "Box.style",
        ["Background: $color.surface", "Background: $color.nope", "Background: $surface"],
    )
    assert all(not any(f.rule in BAD for f in each[i]) for i in (0, 1))
    assert any(f.rule in BAD for f in each[2])


# -- (h) settings -------------------------------------------------------------------------------


def load(tmp_path: Path, body: str) -> list[Any]:
    (tmp_path / "settings.tdl").write_text(f"---\nTDL: 0.1\nName: Settings\n---\n{body}")
    return load_settings(tmp_path)[1]


def settings_probe(tmp_path: Path, section: str, lines: list[str]) -> dict[int, list[Any]]:
    (tmp_path / "Shells").mkdir(exist_ok=True)
    body = "\n".join(lines)
    text = (
        f"Settings {{\n{body}\n}}"
        if section == "Settings"
        else f"Settings {{ {section} {{\n{body}\n}} }}"
    )
    findings = load(tmp_path, text)
    head = 5 + (1 if section == "Settings" else 1)
    out: dict[int, list[Any]] = {i: [] for i in range(len(lines))}
    for f in findings:
        if head <= f.line < head + len(lines):
            out[f.line - head].append(f)
    return out


def test_the_settings_are_the_keys_of_the_readers_tuples() -> None:
    s = D["settings"]
    assert tuple(s["Settings"]) == cfg.ROOT_KEYS
    assert tuple(s["Logging"]) == cfg.LOGGING_KEYS
    assert tuple(s["Appearance"]) == cfg.APPEARANCE_KEYS
    assert tuple(s["Debug"]) == cfg.DEBUG_KEYS
    assert tuple(s["Validation"]) == cfg.VALIDATION_KEYS
    assert tuple(s["Directories"]) == FOLDERS
    assert set(s) == {"Settings", "Directories", "Logging", "Validation", "Appearance", "Debug"}


@pytest.mark.parametrize(
    "section", ["Settings", "Directories", "Logging", "Validation", "Appearance", "Debug"]
)
def test_settings_takes_the_exported_keys_and_no_other(tmp_path: Path, section: str) -> None:
    pool = [w for w in PROP_POOL if not w.isupper()]
    found = settings_probe(tmp_path, section, [f"{w}: 1" for w in pool])
    taken = {w for i, w in enumerate(pool) if not any(f.rule == "unknown-key" for f in found[i])}
    assert taken == set(D["settings"][section]), sorted(taken ^ set(D["settings"][section]))


def settings_sample(tmp_path: Path, key: dict[str, Any]) -> str | None:
    match key["kind"]:
        case "bool":
            return "false"
        case "enum":
            return str(key["choices"][-1])
        case "number" | "whole":
            return "5"
        case "string":
            return "Mine"
        case "list":
            return "[Mine, Other]"
        case "path":
            if key["mode"] == "open":
                (tmp_path / "Shells" / "Mine_Shell.tdl").write_text("x")
                return "Mine_Shell.tdl"
            if key["mode"] == "folder":
                (tmp_path / "dir").mkdir(exist_ok=True)
                return f'"{tmp_path}/dir"'
            return f'"{tmp_path}/reg.json"'
    return None


def test_every_setting_takes_a_value_of_its_kind(tmp_path: Path) -> None:
    (tmp_path / "Shells").mkdir()
    for section, key, entry in settings_keys():
        value = settings_sample(tmp_path, entry)
        if value is None:
            assert entry["kind"] == "block", (section, key)
            continue
        text = (
            f"Settings {{ {key}: {value} }}"
            if section == "Settings"
            else f"Settings {{ {section} {{ {key}: {value} }} }}"
        )
        assert load(tmp_path, text) == [], (section, key, value)


def test_a_setting_enum_refuses_a_word_outside_and_takes_each_choice(tmp_path: Path) -> None:
    for section, key, entry in settings_keys():
        if entry["kind"] != "enum":
            continue
        for choice in entry["choices"]:
            text = f"Settings {{ {section} {{ {key}: {choice} }} }}"
            assert load(tmp_path, text) == [], (section, key, choice)
        text = f"Settings {{ {section} {{ {key}: ZZZ_NOT_A_CHOICE }} }}"
        assert any(f.rule == "bad-value" for f in load(tmp_path, text)), (section, key)


def test_a_setting_default_is_what_the_reader_gives_without_the_key(tmp_path: Path) -> None:
    settings = load_settings(tmp_path)[0]
    assert settings is not None
    d = D["settings"]
    assert d["Logging"]["Level"]["default"] == settings.logging.level
    assert d["Logging"]["Format"]["default"] == settings.logging.format
    assert d["Logging"]["Console"]["default"] == ("true" if settings.logging.console else "false")
    assert d["Settings"]["Hot_Reload"]["default"] == ("true" if settings.hot_reload else "false")
    assert float(d["Settings"]["Reload_Debounce"]["default"]) == settings.reload_debounce * 1000
    assert d["Settings"]["Main_Shell"]["default"] == f'"{settings.main_shell}"'
    assert d["Appearance"]["Follow_Desktop"]["default"] == "true"
    assert d["Debug"]["Panel_Hide"]["default"] == settings.debug.panel_hide
    assert d["Debug"]["Frame_Join"]["default"] == settings.debug.frame_join
    assert d["Debug"]["Frame_Blend"]["default"] == settings.debug.frame_blend
    assert d["Validation"]["Enabled"]["default"] == "true"


# -- defaults the model states -----------------------------------------------------------------


def strip(value: Any) -> Any:
    """A model value without the places in the file it came from."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: strip(getattr(value, f.name))
            for f in dataclasses.fields(value)
            if f.name not in ("origin", "keyboard_written")
        }
    if isinstance(value, Mapping):
        return {k: strip(v) for k, v in value.items()}
    if isinstance(value, tuple | list):
        return [strip(v) for v in value]
    return value


MINIMAL = {
    "Bar": ("Bar", "Name: B, Edge: TOP, Width: 10, Height: 10", ""),
    "Panel": ("Panel", "Name: P, Width: 10, Height: 10", ""),
    "Popup": ("Popup", "Name: P", ""),
    "Frame": ("Frame", "Name: F, Thickness: 4", ""),
    "Animation": ("Panel", "Name: P, Width: 10, Height: 10", "Animation"),
    "Peek": ("Frame", "Name: F, Thickness: 40", "Peek"),
    "Edge_Peek": ("Frame", "Name: F, Thickness: 40", "Peek"),
    "Edge": ("Frame", "Name: F, Thickness: 40", "Edge"),
}


def monitor_of(head: str, body: str, inner: str, line: str) -> Any:
    """The typed surface of a shell file with ``line`` written inside the ``inner`` block."""
    kid = "Children { Spacer { } }"
    match inner:
        case "":
            block = f"{head} {{ {body}{', ' + line if line else ''} }}"
        case "Animation":
            block = f"{head} {{ {body}, Animation {{ {line} }} }}"
        case "Peek":
            block = f"{head} {{ {body}, Edges {{ Top {{ {kid}, Peek {{ {line} }} }} }} }}"
        case "Edge":
            block = f"{head} {{ {body}, Edges {{ Top {{ {kid}, {line} }} }} }}"
        case _:
            raise AssertionError(inner)
    text = f"Shell {{ Monitor {{ Name: M, Children {{ {block} }} }} }}"
    result = tess_dl.parse(SHELL_HEAD + text, path="Main_Shell.tdl")
    assert not result.errors and result.document is not None
    shell, findings = read_shell(result.document, "Main_Shell.tdl", lambda p: SVG, icons=Icons())
    assert [f for f in findings if f.severity == "error"] == [], (text, findings)
    assert shell is not None
    (monitor,) = shell.monitors
    return monitor.frames[0] if head == "Frame" else (monitor.popups or monitor.surfaces)[0]


def test_writing_a_default_changes_nothing() -> None:
    checked = 0
    for spec, (head, body, inner) in MINIMAL.items():
        for key, entry in D["roots"][spec]["keys"].items():
            if entry["default"] is None or not entry["built"] or entry["kind"] == "block":
                continue
            if spec == "Panel" and key in ("Meld", "Gap", "Alignment", "Attach"):
                continue  # these need Attach_To, a target to meld into or to meet
            plain = monitor_of(head, body, inner, "")
            written_ = monitor_of(head, body, inner, f"{key}: {entry['default']}")
            if inner == "Animation":
                plain = monitor_of(head, body, inner, "")
            assert strip(plain) == strip(written_), (spec, key, entry["default"])
            checked += 1
    assert checked >= 30


def test_a_default_the_binder_holds_is_the_one_it_uses() -> None:
    from tess_shell.binder import marquee

    marquee_keys = D["blocks"]["Marquee"]["keys"]
    assert marquee_keys["Speed"]["default"] == str(int(marquee.DEFAULT_SPEED))
    assert marquee_keys["Pause"]["default"] == str(marquee.DEFAULT_PAUSE)
    runner = marquee.MarqueeRunner(None, None, None)  # type: ignore[arg-type]
    assert (runner.speed, runner.pause) == (marquee.DEFAULT_SPEED, marquee.DEFAULT_PAUSE)
    for key, word in (("Direction", runner.direction), ("Loop", runner.loop)):
        assert marquee_keys[key]["default"] == word
        assert word in marquee_keys[key]["choices"]
    assert marquee_keys["Animated"]["default"] == ("true" if runner.animated else "false")


def test_a_default_a_stylesheet_gives_is_the_shipped_ones() -> None:
    text = D["blocks"]["Text"]["style"]
    assert text["Foreground"]["default"] == "$color.on_surface"
    assert text["Font_Size"]["default"] == "$type.body.font_size"
    assert D["blocks"]["SVG"]["style"]["Foreground"]["default"] == "$color.on_surface"
    sheet = Path(export.__file__).parent.parent / "shipped" / "Stylesheets"
    source = (sheet / "Default_Stylesheet.tdl").read_text(encoding="utf-8")
    assert 'Selector: "Text"\n        Foreground: $color.on_surface' in source


# -- examples ----------------------------------------------------------------------------------


def example_findings(name: str, text: str) -> list[Finding]:
    if name in D["blocks"]:
        return run("module", f"Module {{ Children {{ {text} }} }}")
    match name:
        case "Shell":
            return run("shell", text)
        case "Monitor":
            return run("shell", f"Shell {{ {text} }}")
        case "Bar" | "Panel" | "Popup" | "Frame":
            return run("shell", f"Shell {{ Monitor {{ Name: M, Children {{ {text} }} }} }}")
        case "Peek":
            strip_ = f"Top {{ Children {{ Spacer {{ }} }}, {text} }}"
            frame = f"Frame {{ Name: F, Thickness: 40, Edges {{ {strip_} }} }}"
            return run("shell", f"Shell {{ Monitor {{ Name: M, Children {{ {frame} }} }} }}")
        case "Animation":
            panel = f"Panel {{ Name: P, Width: 10, Height: 10, {text} }}"
            return run("shell", f"Shell {{ Monitor {{ Name: M, Children {{ {panel} }} }} }}")
        case "Border":
            frame = f"Frame {{ Name: F, Thickness: 4, {text} }}"
            return run("shell", f"Shell {{ Monitor {{ Name: M, Children {{ {frame} }} }} }}")
        case "Rule":
            return run("stylesheet", f"Stylesheet {{ {text} }}")
        case "Stylesheet":
            return run("stylesheet", text)
    raise AssertionError(name)


@pytest.mark.parametrize("name", sorted(docs.EXAMPLES))
def test_an_example_loads_without_a_finding(name: str) -> None:
    findings = example_findings(name, docs.EXAMPLES[name])
    assert [f for f in findings if f.severity == "error"] == [], findings
    spec = {**D["roots"], **D["blocks"]}[name]
    assert spec["example"] == docs.EXAMPLES[name]


# -- the block specs read as the loader reads them ------------------------------------------


def test_a_block_takes_the_events_and_children_the_loader_says() -> None:
    assert D["blocks"]["Text"]["events"] == []
    assert D["blocks"]["Box"]["events"][0] == "On_Click"
    assert D["roots"]["Panel"]["events"] == list(blocks.BLOCK_EVENTS["Panel"])
    assert D["events"]["On_Changed"]["module_only"] is True
    assert D["events"]["On_Click"]["module_only"] is False
    assert set(D["events"]) == set(blocks.EVENT_KEYS)
    assert [a["name"] for a in D["actions"]] == list(blocks.BUILTIN_ACTIONS)
    assert D["roots"]["Shell"]["allowed_children"] == ["Monitor"]
    assert D["roots"]["Monitor"]["allowed_children"] == ["Bar", "Panel", "Popup", "Frame"]
    assert D["blocks"]["Box"]["allowed_children"] == list(blocks.BLOCKS)
    assert D["blocks"]["Text"]["allowed_children"] == []


def test_required_groups_come_from_the_blocks_table() -> None:
    assert D["blocks"]["SVG"]["required"] == [["Source", "Icon"]]
    assert D["blocks"]["Bitmap"]["required"] == [["Source"]]
    assert D["blocks"]["Bitmap"]["keys"]["Source"]["required"] is True
    assert D["blocks"]["SVG"]["keys"]["Source"]["required"] is False
    assert D["blocks"]["Circle"]["keys"]["Diameter"]["required"] is True
    assert D["roots"]["Bar"]["required"] == [["Name"], ["Edge"], ["Width"], ["Height"]]


@pytest.mark.parametrize("name", list(blocks.BLOCKS))
def test_a_block_spec_is_its_table_in_the_tables_order(name: str) -> None:
    props, style = blocks.BLOCKS[name]
    spec = D["blocks"][name]
    own = [k for k in spec["keys"] if k not in export.IDENTITY_KEYS]
    assert own == list(props), name
    assert list(spec["style"]) == list(style), name
    # the identity keys come first, in order; a Tooltip needs a block that raises pointer events
    wanted = [k for k in export.IDENTITY_KEYS if k != "Tooltip" or name in blocks.BLOCK_EVENTS]
    assert list(spec["keys"])[: len(wanted)] == wanted, name
    assert spec["events"] == list(blocks.BLOCK_EVENTS.get(name, ())), name
    for key, entry in {**spec["keys"], **spec["style"]}.items():
        table_kind = props.get(key) or style.get(key)
        if table_kind is not None and entry["kind"] == "enum":
            assert entry["choices"] == list(
                blocks.CHOICES.get((name, key)) or blocks.CHOICES[("*", key)]
            ), (name, key)
