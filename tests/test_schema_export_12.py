"""Schema 1.2: the ``popups`` section lists the Popups the shell provides
(``schema/default_popups``). It is additive: every section of 1.1 is as it was."""

from __future__ import annotations

from pathlib import Path

from tess_shell.schema import default_popups
from tess_shell.schema.export import schema_dict, schema_json

D = schema_dict()
SHIPPED = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped"
SECTION = D["popups"]
POPUPS = SECTION["popups"]


def test_the_version_is_1_3_and_popups_is_the_section_before_shortcuts() -> None:
    assert D["schema_version"] == "1.3"
    assert list(D)[-2] == "popups" and set(SECTION) == {"monitors", "popups"}
    assert SECTION["monitors"] == default_popups.MONITORS


def test_every_shipped_popup_is_listed_once_with_the_module_that_brings_it() -> None:
    wanted = {name for pairs in default_popups.POPUPS.values() for name, _ in pairs}
    assert set(POPUPS) == wanted  # none missing, none invented
    assert (
        len(POPUPS) == len(wanted) == 4
    )  # names are unique (a dict key cannot repeat: count them)
    by_module = {
        module: [name for name, _ in pairs] for module, pairs in default_popups.POPUPS.items()
    }
    for module, names in by_module.items():
        for name in names:
            assert POPUPS[name]["shown_by"] == module
    assert list(POPUPS) == [n for names in by_module.values() for n in names]  # a stable order


def test_the_content_module_of_each_popup_exists_among_the_shipped_modules() -> None:
    folders = {p.name for p in SHIPPED.iterdir() if (p / f"{p.name}_Module.tdl").is_file()}
    assert set(D["modules"]) >= {"Tray", "Tray_Menu", "Audio", "Audio_Outputs"}
    for name, entry in POPUPS.items():
        assert entry["content"] in folders, (name, entry["content"])
        assert entry["content"] in D["modules"]
        assert entry["shown_by"] in D["modules"]
        assert entry["doc"], name  # a line for every one


def test_max_height_is_listed_as_written_and_the_placement_keys_follow_the_text() -> None:
    assert POPUPS["Tray_Menu"]["max_height"] == {"value": 60.0, "unit": "%"}
    assert POPUPS["Tray_Menu_2"]["max_height"] == {"value": 60.0, "unit": "%"}
    assert POPUPS["Audio_Outputs"]["max_height"] == {"value": 400, "unit": "px"}  # not written
    assert (POPUPS["Tray_Menu"]["attach"], POPUPS["Tray_Menu"]["gap"]) == ("BOTTOM", 4)
    assert POPUPS["Audio_Outputs"]["content"] == "Audio_Outputs"
    assert POPUPS["Tray_Menu_3"]["content"] == "Tray_Menu"


def test_the_section_is_plain_data_and_the_export_is_stable() -> None:
    assert schema_json() == schema_json()
    assert "Monitor" in SECTION["monitors"] and "replaces it whole" in SECTION["monitors"]


def test_a_module_that_is_not_there_brings_no_popup() -> None:
    assert default_popups.describe({}) == {}
