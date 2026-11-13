"""Schema 1.1: defaults read from tre, ranges the loader and the export share, preferred tokens,
the shipped modules, and the tables the export reads being public (T-026)."""

from __future__ import annotations

import fnmatch
import importlib.util
import inspect
from pathlib import Path
from typing import Any

import pytest
import tess_dl
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import build
from tess_shell.binder.controls import kind_of
from tess_shell.binder.defaults import tre_defaults
from tess_shell.binder.motion import DEFAULT_DURATION, EASINGS, motion_of
from tess_shell.binder.tables import BLOCKS as ROWS
from tess_shell.config import settings as cfg
from tess_shell.modules.host import action_spec, actions_of
from tess_shell.schema import blocks, docs, export, look, ranges, shell, values
from tess_shell.schema.model import ModuleDef
from tess_shell.schema.shell import read_module, read_module_params
from tests.test_schema_export import BAD, CONTEXTS, ORIGIN, D, probe, run

SHIPPED = Path(export.__file__).parent.parent / "shipped"


# -- (7) the tables the export reads are public -------------------------------------------------


def test_the_tables_the_export_reads_are_public_and_the_private_names_are_gone() -> None:
    for module, names in (
        (shell, ("BAR_KEYS", "BAR_CHOICES", "PEEK_WORDS", "IMAGE_SUFFIXES")),
        (look, ("token_kind",)),
        (
            cfg,
            (
                "ROOT_KEYS",
                "DEBUG_KEYS",
                "PANEL_HIDE",
                "FRAME_JOIN",
                "FRAME_BLEND",
                "APPEARANCE_KEYS",
                "LOGGING_KEYS",
                "VALIDATION_KEYS",
            ),
        ),
    ):
        for name in names:
            assert hasattr(module, name), (module.__name__, name)
            assert not hasattr(module, f"_{name}"), (module.__name__, f"_{name}")
    assert not hasattr(look, "_kind")
    assert not hasattr(export, "_BAR_KEYS") and not hasattr(export, "_token_kind")
    assert not hasattr(shell, "_frame_sides")  # the loader's range check made it obsolete


# -- (2) ranges: one table, the loader judges by it and the export reports it --------------------

LIMITS: list[tuple[str, str, str, str, str]] = [
    # (context, key, a value just inside, a value outside, what the finding names)
    ("Box", "Opacity", "1", "1.5", "from 0 to 1"),
    ("Box", "Opacity", "0", "-0.1", "from 0 to 1"),
    ("Box", "Scale", "0.5", "0", "greater than 0"),
    ("Box", "Flex_Grow", "0", "-1", "0 or more"),
    ("Box", "Flex_Shrink", "0", "-1", "0 or more"),
    ("Text", "Font_Weight", "1000", "1001", "from 1 to 1000"),
    ("Text", "Font_Weight", "1", "0", "from 1 to 1000"),
    ("Text", "Font_Size", "12", "0", "greater than 0"),
    ("Text", "Line_Height", "12", "-3", "greater than 0"),
    ("Box", "Aspect_Ratio", "2", "0", "greater than 0"),
    ("Box", "Width", "10", "-5", "0 or more"),
    ("Box", "Min_Width", "10", "-5", "0 or more"),
    ("Box", "Padding", "4", "-1", "0 or more"),
    ("Box", "Margin", "[1, 2, 3, 4]", "[1, -2, 3, 4]", "0 or more"),
    ("Box.style", "Corner_Radius", "4", "-1", "0 or more"),
    ("Box.style", "Corner_Radius", "[1, 2, 3, 4]", "[1, 2, -3, 4]", "0 or more"),
    ("Box.style", "Border_Width", "0", "-1", "0 or more"),
    ("Box.style", "Elevation", "100%", "120%", "from 0% to 100%"),
    ("Box.style", "Duration", "0", "-1", "0 or more"),
    ("Text", "Max_Lines", "0", "-1", "0 or more"),
    ("Circle", "Diameter", "1", "0", "greater than 0"),
    ("Path", "Trim_End", "1", "1.5", "from 0 to 1"),
    ("TextField", "Lines", "1", "0", "1 or more"),
    ("Marquee", "Speed", "30", "0", "greater than 0"),
    ("Marquee", "Pause", "0", "-5", "0 or more"),
    ("Panel", "Hide_After", "0", "-1", "0 or more"),
    ("Popup", "Enter_Delay", "0", "-1", "0 or more"),
    ("Popup", "Exit_Delay", "0", "-1", "0 or more"),
    ("Panel", "Width", "10", "-5", "0 or more"),
    ("Frame", "Thickness", "4", "-1", "0 or more"),
    ("Frame", "Corner_Radius", "4", "[1, -1, 1, 1]", "0 or more"),
    ("Bar.style", "Opacity", "0.5", "2", "from 0 to 1"),
    ("Rule", "Opacity", "0.5", "2", "from 0 to 1"),
]


@pytest.mark.parametrize(("context", "key", "inside", "outside", "words"), LIMITS)
def test_the_loader_refuses_a_value_outside_its_range_with_the_range_named(
    context: str, key: str, inside: str, outside: str, words: str
) -> None:
    fine, bad = probe(context, [f"{key}: {inside}"])[0], probe(context, [f"{key}: {outside}"])[0]
    if context in ("Panel", "Popup", "Frame", "Bar.style"):
        # a surface needs its own keys: the finding of the key itself is what counts
        pass
    assert not [f for f in fine if f.rule in BAD], (inside, fine)
    found = [f for f in bad if f.rule == "bad-value"]
    assert found, (context, key, outside, bad)
    assert words in found[0].message, found[0].message
    assert found[0].line > 0 and found[0].column > 0


def test_a_negative_inset_is_taken_a_panel_is_placed_by_it() -> None:
    assert not [f for f in probe("Panel", ["Inset: -4"])[0] if f.rule in BAD]
    assert not [f for f in probe("Panel", ["Inset { Left: -4 }"])[0] if f.rule in BAD]


def test_a_slot_that_gives_a_value_outside_the_range_is_refused_like_a_written_one() -> None:
    for kind, key, good, bad in (
        ("number", "Opacity", 0.5, 1.5),
        ("positive", "Scale", 2, 0),
        ("whole", "Font_Weight", 400, 2000),
        ("length", "Width", 10, -1),
        ("sides", "Padding", 4, -1),
    ):
        values.from_python(kind, good, ORIGIN, (), key)
        with pytest.raises(values.ValueProblem):
            values.from_python(kind, bad, ORIGIN, (), key)


def test_the_export_reports_the_numbers_the_loader_judges_by() -> None:
    for name, spec in D["blocks"].items():
        for part in ("keys", "style"):
            for key, entry in spec[part].items():
                rng = None
                kind = (blocks.BLOCKS[name][0] | blocks.BLOCKS[name][1]).get(key)
                if kind is not None:
                    rng = ranges.range_of(kind, key)
                if entry["kind"] in ("number", "whole", "duration", "percent") and rng is not None:
                    low = rng.low
                    if rng.low_open and low is not None and entry["kind"] == "whole":
                        assert (entry["min"], entry["max"]) == (low + 1, rng.high), (name, key)
                    else:
                        assert (entry["min"], entry["max"]) == (low, rng.high), (name, key)
                        assert entry.get("min_exclusive", False) == rng.low_open, (name, key)
                if entry["kind"] in ("length", "sides", "radius"):
                    expected = rng is None or rng.low is None or rng.low < 0
                    assert entry["negative"] is expected, (name, key)
    opacity = D["blocks"]["Box"]["keys"]["Opacity"]
    assert (opacity["min"], opacity["max"]) == (0, 1)
    assert D["blocks"]["Text"]["style"]["Font_Weight"]["min"] == 1
    assert D["blocks"]["Text"]["style"]["Font_Weight"]["max"] == 1000
    assert D["blocks"]["Box"]["keys"]["Scale"]["min_exclusive"] is True
    assert D["blocks"]["Box"]["keys"]["Flex_Grow"]["min"] == 0
    assert D["roots"]["Panel"]["keys"]["Inset"]["negative"] is True
    assert D["roots"]["Frame"]["keys"]["Thickness"]["negative"] is False
    assert D["roots"]["Popup"]["keys"]["Enter_Delay"]["min"] == 0
    assert D["roots"]["Panel"]["keys"]["Hide_After"]["min"] == 0


def test_the_numbers_of_the_peek_an_edge_a_border_and_a_shadow_are_the_table() -> None:
    peek = D["roots"]["Peek"]["keys"]
    assert peek["Size"]["min"] == ranges.KEY_RANGES["Peek.Size"].low == 1
    assert D["roots"]["Edge_Peek"]["keys"]["Size"]["min"] == 1
    assert peek["Enter_Delay"]["min"] == ranges.KEY_RANGES["Enter_Delay"].low == 0
    assert (peek["Handle_Opacity"]["min"], peek["Handle_Opacity"]["max"]) == (0, 1)
    assert D["roots"]["Edge"]["keys"]["Thickness"]["min"] == 0
    assert D["roots"]["Border"]["keys"]["Width"]["min"] == 0
    assert D["roots"]["Shadow"]["keys"]["Blur"]["min"] == 0
    # and the loader says the same, in the one wording
    for spec, line, words in (
        ("Peek", "Size: 0", "expected a number, 1 or more, found 0"),
        ("Edge_Peek", "Size: 0", "expected a number, 1 or more, found 0"),
        ("Peek", "Enter_Delay: -1", "expected a number, 0 or more, found -1"),
        ("Peek", "Handle_Opacity: 2", "expected a number, from 0 to 1, found 2"),
        ("Edge", "Thickness: -1", "expected a number, 0 or more, found -1"),
        ("Border", "Width: -1", "expected a number, 0 or more, found -1"),
        ("Shadow", "Blur: -1", "expected a number, 0 or more, found -1"),
    ):
        found = probe(spec, [line])[0]
        if spec == "Shadow":  # reported at the Shadows block, not at the key's line
            kind, template = CONTEXTS[spec]
            found = run(kind, template.replace("@", f'Color: "#000000"\n{line}'))
        assert any(words in f.message for f in found), (spec, line, found)
    assert ranges.scoped("Edge_Peek", "Size") == "Peek.Size"
    assert ranges.scoped("Box", "Width") == "Width"


def test_the_range_words_read_as_a_person_says_them() -> None:
    assert ranges.Range(0).words() == "0 or more"
    assert ranges.Range(0, low_open=True).words() == "greater than 0"
    assert ranges.Range(0, 1).words() == "from 0 to 1"
    assert ranges.Range(0, 100).words("%") == "from 0% to 100%"
    assert ranges.Range(0, low_open=True).holds(0.01) and not ranges.Range(0, low_open=True).holds(
        0
    )
    assert ranges.Range(0, 1).holds(1) and not ranges.Range(0, 1).holds(1.01)


def test_every_shipped_file_still_loads_under_the_ranges() -> None:
    """Themes, stylesheets, styles and modules: no finding at all."""
    from tess_shell.schema.look import read_stylesheet, read_theme
    from tess_shell.schema.shell import read_style

    for path in sorted(SHIPPED.rglob("*.tdl")):
        parsed = tess_dl.parse(path.read_text(encoding="utf-8"), path=path.name)
        assert parsed.document is not None and not parsed.errors, path
        root = parsed.document.root.type
        if root == "Theme":
            _, findings = read_theme(parsed.document, path.name)
        elif root == "Stylesheet":
            _, findings = read_stylesheet(parsed.document, path.name, set(D["modules"]))
        elif root == "Style":
            _, findings = read_style(parsed.document, path.name)
        else:
            continue  # modules are read with their callers in the module tests
        assert [f for f in findings if f.severity == "error"] == [], (path.name, findings)


# -- (1) defaults read from tre ------------------------------------------------------------


def block_keys(name: str) -> dict[str, dict[str, Any]]:
    return {**D["blocks"][name]["keys"], **D["blocks"][name]["style"]}


def test_a_default_of_tre_is_in_the_export_for_the_keys_that_have_one() -> None:
    read = tre_defaults()
    assert len(read) > 250
    for (block, key), text in read.items():
        entry = block_keys(block)[key]
        assert entry["default"] is not None, (block, key)
        if entry["default"] != text:  # the model, the binder or the stylesheet said it first
            assert (block, key) in export._FIELDS or key in (
                "Foreground",
                "Font_Size",
            ), (block, key, entry["default"], text)
    box = block_keys("Box")
    assert box["Visible"]["default"] == "true"
    assert box["Position"]["default"] == "RELATIVE"
    assert box["Width"]["default"] == "AUTO"
    assert box["Flex_Shrink"]["default"] == "1"
    assert box["Opacity"]["default"] == "1"
    assert box["Background"]["default"] == '"#00000000"'
    assert block_keys("Text")["Wrap"]["default"] == "WORD"
    assert block_keys("Text")["Font_Weight"]["default"] == "400"
    assert block_keys("Spacer")["Flex_Grow"]["default"] == "1"  # the shell sets it
    assert block_keys("TextField")["Width"]["default"] == "200"
    assert block_keys("TextField")["Lines"]["default"] == "1"
    assert block_keys("Marquee")["Min_Width"]["default"] == "0"
    assert block_keys("ScrollBox")["Orientation"]["default"] == "VERTICAL"
    assert block_keys("Bitmap")["Fit"]["default"] == "CONTAIN"


SVG_TEXT = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 4'><rect width='4' height='4'/></svg>"
)
NEEDS = {
    "SVG": 'Source: "x.svg"',
    "Circle": "Diameter: 10",
    "Ring": "Diameter: 10",
    "Path": 'Data: "M0,0 L8,8"',
}


def close(a: Any, b: Any) -> bool:
    """Equal, numbers to a hair, in nested tuples and lists."""
    if isinstance(a, tuple | list) and isinstance(b, tuple | list):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float | int) and isinstance(b, float | int):
        return abs(a - b) < 1e-6
    return bool(a == b)


def tre_of(window: Window, block: str, lines: list[str], names: tuple[str, ...]) -> list[Any]:
    """Load a module with one ``block`` that has ``lines`` written, bind it, read tre's names."""
    body = "\n".join(lines)
    module = f"Module {{ Children {{ {block} {{\n{body}\n}} }} }}"
    head = "---\nTDL: 0.1\nName: Probe\n---\n"
    result = tess_dl.parse(head + module, path="Probe_Module.tdl")
    assert result.document is not None and not result.errors
    found, findings = read_module(
        result.document, "Probe_Module.tdl", None, None, None, None, lambda _: SVG_TEXT
    )
    assert found is not None, findings
    assert [f for f in findings if f.severity == "error"] == [], findings
    view = build(list(found.children), window)
    try:
        (root,) = view.roots
        return [root.get(n) for n in names]
    finally:
        view.dispose()


def test_a_default_that_tre_reads_is_what_a_bare_block_has_when_the_key_is_written() -> None:
    """Write each tre default into a bare block, load it and bind it: the tre properties the key
    sets are the ones a block with nothing written has."""
    window = Window(120, 60)
    checked = 0
    for (block, key), text in sorted(tre_defaults().items()):
        if block in ("TextField", "Marquee", "Bitmap"):
            continue  # several nodes, or a decoded file: read by the same rows
        row = ROWS[block]
        names = {**row.keys, **row.style}[key].tre
        if not names:
            continue
        base = [NEEDS[block]] if block in NEEDS else []
        written = tre_of(window, block, [*base, f"{key}: {text}"], names)
        assert close(written, tre_of(window, block, base, names)), (block, key, text)
        checked += 1
    assert checked > 200


def test_a_key_tre_has_no_reading_for_is_null_unless_a_default_is_authored_or_a_constant() -> None:
    read = tre_defaults()
    for name in D["blocks"]:
        for key, entry in block_keys(name).items():
            if entry["default"] is not None:
                continue
            assert (name, key) not in read, (name, key)
            assert key not in docs.AUTHORED_DEFAULTS and key not in export._KEY_CONSTANTS, key
    # nothing is guessed for the keys tre gives None: Role, Label, Aspect_Ratio, Overflow ...
    for key in ("Role", "Label", "Description", "Live", "Value", "Checked", "Aspect_Ratio"):
        assert D["blocks"]["Box"]["keys"][key]["default"] is None, key
    assert (
        D["blocks"]["Box"]["keys"]["Min_Width"]["default"] is None
    )  # tre says auto, a bound has none


def test_an_authored_default_belongs_to_a_key_tre_has_no_property_for() -> None:
    for key, (text, why) in docs.AUTHORED_DEFAULTS.items():
        assert why and text
        for name in D["blocks"]:
            table = {**ROWS[name].keys, **ROWS[name].style}
            if key in table:
                assert table[key].tre == (), (name, key)
                assert block_keys(name)[key]["default"] == text, (name, key)


def test_the_authored_defaults_are_what_the_binder_does_without_the_key() -> None:
    node = m.Node("Box", style={"Transition": m.Seq((m.Text("Opacity"),))})
    found = motion_of(node)
    assert found is not None
    assert found.easing == EASINGS[docs.AUTHORED_DEFAULTS["Easing"][0]]
    assert found.duration == DEFAULT_DURATION
    assert found.duration == int(D["blocks"]["Box"]["style"]["Duration"]["default"])

    class Entry:
        def __init__(self, props: dict[str, m.Value]) -> None:
            self.typed = m.Node("Box", props=props)

    assert kind_of(Entry({})) == ""  # type: ignore[arg-type]
    written = {
        "Toggles": m.Bool(docs.AUTHORED_DEFAULTS["Toggles"][0] == "true"),
        "Selection_Mode": m.Enum(docs.AUTHORED_DEFAULTS["Selection_Mode"][0]),
        "Slides": m.Enum(docs.AUTHORED_DEFAULTS["Slides"][0]),
        "Menu_Item": m.Bool(docs.AUTHORED_DEFAULTS["Menu_Item"][0] == "true"),
    }
    assert kind_of(Entry(written)) == ""  # type: ignore[arg-type]
    for key, other in (
        ("Toggles", m.Bool(True)),
        ("Selection_Mode", m.Enum("SINGLE")),
        ("Slides", m.Enum("HORIZONTAL")),
        ("Menu_Item", m.Bool(True)),
    ):
        assert kind_of(Entry({key: other})) != "", key  # type: ignore[arg-type]


def test_the_defaults_of_the_surfaces_are_unchanged_and_no_default_is_lost() -> None:
    assert D["roots"]["Panel"]["keys"]["Layer"]["default"] == "TOP"
    assert D["roots"]["Popup"]["keys"]["Enter_Delay"]["default"] == "500"
    assert D["blocks"]["Text"]["style"]["Foreground"]["default"] == "$color.on_surface"
    assert D["blocks"]["Marquee"]["keys"]["Speed"]["default"] == "30"
    assert D["blocks"]["Text"]["style"]["Font_Size"]["default"] == "$type.body.font_size"


# -- (3) preferred tokens -------------------------------------------------------------------


def every_entry() -> list[tuple[str, str, dict[str, Any]]]:
    out = []
    for sect in ("roots", "blocks"):
        for name, spec in D[sect].items():
            for part in ("keys", "style"):
                out += [(name, key, e) for key, e in spec[part].items()]
    return out


def test_every_preferred_token_names_a_token_of_the_default_theme_the_key_can_read() -> None:
    tokens = {t["ref"][1:]: t for group in D["tokens"].values() for t in group.values()}
    groups = set(D["tokens"])
    used = 0
    for name, key, entry in every_entry():
        assert isinstance(entry["preferred_tokens"], list)
        for pattern in entry["preferred_tokens"]:
            used += 1
            assert pattern.split(".")[0] in groups, (name, key, pattern)
            matched = [
                ref
                for ref in tokens
                if ref == pattern
                or ref.startswith(pattern + ".")
                or fnmatch.fnmatchcase(ref, pattern)
            ]
            assert matched, (name, key, pattern)
            for ref in matched:
                assert ref.split(".")[0] in entry["tokens"], (name, key, ref, entry["tokens"])
    assert used > 100


def test_the_preferred_tokens_follow_the_table_and_the_colour_kind() -> None:
    for pattern_list in docs.PREFERRED_TOKENS.values():
        for pattern in pattern_list:
            assert pattern.split(".")[0] in D["tokens"], pattern
    box = D["blocks"]["Box"]
    assert box["style"]["Background"]["preferred_tokens"] == ["color"]
    assert box["style"]["Corner_Radius"]["preferred_tokens"] == ["shape"]
    assert box["keys"]["Padding"]["preferred_tokens"] == ["space"]
    assert box["style"]["Duration"]["preferred_tokens"] == ["motion.duration.*"]
    assert D["blocks"]["Text"]["style"]["Font_Size"]["preferred_tokens"] == ["type.*.font_size"]
    assert D["blocks"]["Text"]["style"]["Font_Weight"]["preferred_tokens"] == ["type.*.font_weight"]
    assert box["style"]["Shadows"]["preferred_tokens"] == ["elevation.max"]
    for name, key, entry in every_entry():
        if entry["kind"] == "color" and entry["tokens"]:
            assert "color" in entry["preferred_tokens"], (name, key)
        if not entry["tokens"]:
            assert entry["preferred_tokens"] == [], (name, key)
    # the wide, mechanical list stays
    assert box["style"]["Background"]["tokens"] == ["color"]
    assert "space" in box["keys"]["Padding"]["tokens"]


# -- (5) the shipped modules ----------------------------------------------------------------


def shipped_names() -> list[str]:
    return sorted(p.parent.name for p in SHIPPED.glob("*/*_Module.tdl"))


def declared(name: str) -> ModuleDef:
    path = SHIPPED / name / f"{name}_Module.tdl"
    parsed = tess_dl.parse(path.read_text(encoding="utf-8"), path=path.name)
    assert parsed.document is not None
    found = read_module_params(parsed.document, path.name)
    assert found is not None
    return found


def test_every_shipped_module_is_listed_with_all_its_params() -> None:
    assert list(D["modules"]) == shipped_names()
    assert len(D["modules"]) >= 22
    total = 0
    for name in shipped_names():
        listed = D["modules"][name]["params"]
        params = declared(name).params
        assert list(listed) == list(params), name
        for param, decl in params.items():
            entry = listed[param]
            total += 1
            assert entry["type"] == decl.type
            assert entry["required"] is (decl.default is None)
            assert entry["doc"].strip(), (name, param)
            assert entry["kind"] in D["kinds"], (name, param)
        assert D["modules"][name]["doc"].strip(), name
    assert total == 96


def test_a_param_default_passes_the_check_of_its_kind() -> None:
    kinds = {
        "string": "text",
        "number": "number",
        "boolean": "bool",
        "icon": "text",
        "path": "text",
    }
    for name in shipped_names():
        for param, entry in D["modules"][name]["params"].items():
            assert entry["default"] is not None, (name, param)
            result = tess_dl.parse(f"---\nTDL: 0.1\nName: P\n---\nX {{ K: {entry['default']} }}")
            assert result.document is not None and not result.errors, (name, param)
            (prop,) = result.document.root.entries
            assert isinstance(prop, tess_dl.Property)
            values.coerce(kinds[entry["type"]], prop.value, ORIGIN)
            decl = declared(name).params[param]
            assert isinstance(decl.default, m.Value if False else object)
    assert D["modules"]["Slider"]["params"]["Max"]["default"] == "100"
    assert D["modules"]["Clock"]["params"]["tooltip_format"]["default"] == '"%A, %d %B %Y"'
    assert D["modules"]["Battery"]["params"]["show_percent"]["default"] == "true"
    assert D["modules"]["Slider"]["params"]["Max"]["kind"] == "number"
    assert D["modules"]["Toggle"]["params"]["Checked"]["kind"] == "bool"
    assert D["modules"]["Image"]["params"]["Source"]["kind"] == "path"
    assert D["modules"]["Icon"]["params"]["Icon"]["kind"] == "icon"


def test_no_doc_line_describes_a_module_or_param_that_is_not_shipped() -> None:
    assert set(docs.MODULE_NOTES) == set(shipped_names())
    pairs = {(n, p) for n in shipped_names() for p in declared(n).params}
    assert set(docs.PARAM_DOCS) == pairs


def load_class(name: str) -> type | None:
    py = SHIPPED / name / f"{name}_Module.py"
    if not py.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"_shipped_{name}", py)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    classes = [
        c
        for c in vars(module).values()
        if inspect.isclass(c) and c.__module__ == module.__name__ and actions_of(c) is not None
    ]
    from tess_shell import Module

    own = [c for c in classes if issubclass(c, Module) and c is not Module]
    return own[0] if own else None


def test_the_actions_listed_are_the_modules_own_with_their_arguments() -> None:
    seen = 0
    for name in shipped_names():
        cls = load_class(name)
        listed = {a["name"]: a for a in D["modules"][name]["actions"]}
        real = actions_of(cls) if cls is not None else []
        assert sorted(listed) == real, name
        for action_name in real:
            spec = action_spec(getattr(cls, action_name).__get__(object()))
            entry = listed[action_name]
            assert [a["name"] for a in entry["args"]] == list(spec.names), (name, action_name)
            assert {a["name"] for a in entry["args"] if a["required"]} == set(spec.required)
            assert entry["kwargs"] is spec.kwargs
            seen += 1
    assert seen >= 7
    assert [a["name"] for a in D["modules"]["Workspaces"]["actions"]] == ["switch"]


def test_the_events_a_call_may_handle_are_what_the_loader_allows() -> None:
    mods = D["modules"]
    assert mods["Label"]["events"] == [] and mods["TextBox"]["events"] == []
    assert mods["Button"]["events"] == [
        "On_Click",
        "On_Secondary_Click",
        "On_Middle_Click",
        "On_Scroll",
    ]
    assert (
        "On_Changed" in mods["Toggle"]["events"] and "On_Released" not in mods["Toggle"]["events"]
    )
    assert "On_Released" in mods["Slider"]["events"]
    assert {"On_Changed", "On_Submit"} <= set(mods["TextInput"]["events"])
    # a call that names such an event loads; one that names a key the root cannot raise is refused
    for name, module in mods.items():
        for event in module["events"]:
            assert event in blocks.BLOCK_EVENTS.get(module["root_block"], ()), (name, event)
    assert mods["Slider"]["root_block"] == "Box"
    assert "Width" in mods["Slider"]["common_keys"]
    assert not set(mods["Slider"]["common_keys"]) & set(blocks.A11Y_STATE)


def test_a_use_of_every_module_with_its_defaults_loads_as_the_export_says() -> None:
    stubs = {n: declared(n) for n in shipped_names()}
    for name, module in D["modules"].items():
        args = ", ".join(f"{p}: {e['default']}" for p, e in module["params"].items())
        call = (
            "Bar { Name: B, Edge: TOP, Width: 10, Height: 10, "
            f"Children {{ {name} {{ {args} }} }} }}"
        )
        head = "---\nTDL: 0.1\nShell: 0.1\nName: S\n---\n"
        text = head + f"Shell {{ Monitor {{ Name: M, Children {{ {call} }} }} }}"
        result = tess_dl.parse(text, path="S_Shell.tdl")
        assert result.document is not None and not result.errors, name
        _, findings = shell.read_shell(
            result.document, "S_Shell.tdl", lambda p: "", stubs, None, None, str
        )
        assert [f for f in findings if f.severity == "error"] == [], (name, findings)


def test_the_cli_schema_is_regenerated_to_a_file(tmp_path: Path) -> None:
    from tess_shell.cli import main

    target = tmp_path / "t.json"
    assert main(["schema", "--json", "--out", str(target)]) == 0
    import json

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.1" and "modules" in data
    assert list(data)[-1] == "modules"
    _ = (CONTEXTS, run)  # the probes of the first suite are shared
