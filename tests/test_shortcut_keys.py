"""Key strings of the shortcuts (Global Shortcuts > Key Names): every name, alias and modifier
order, the Qt numbers pinned to Qt's own header when it is installed, and the errors."""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest

from tess_shell.schema import keys
from tess_shell.schema.keys import (
    ALIASES,
    KEY_CODES,
    KEYS,
    MODIFIER_BITS,
    MODIFIER_ORDER,
    QT_NAMES,
    Chord,
    ChordError,
    key_names,
    parse_chord,
)

HEADERS = (
    Path("/usr/include/qt6/QtCore/qnamespace.h"),
    Path("/usr/include/QtCore/qnamespace.h"),
    Path("/usr/include/x86_64-linux-gnu/qt6/QtCore/qnamespace.h"),
)
HEADER = next((p for p in HEADERS if p.is_file()), None)


def test_the_canonical_form_is_ctrl_alt_shift_meta_then_the_key() -> None:
    assert MODIFIER_ORDER == ("Ctrl", "Alt", "Shift", "Meta")
    assert parse_chord("meta+shift+alt+ctrl+f1").text == "Ctrl+Alt+Shift+Meta+F1"


@pytest.mark.parametrize("name", KEYS)
def test_every_key_name_is_read_in_any_case_and_written_back_as_it_is(name: str) -> None:
    for spelling in (name, name.lower(), name.upper()):
        chord = parse_chord(spelling)
        assert chord.key == name and chord.text == name
        assert chord.qt == KEY_CODES[name]
        assert parse_chord("Ctrl+" + spelling).qt == MODIFIER_BITS["Ctrl"] | KEY_CODES[name]


@pytest.mark.parametrize("alias", sorted(ALIASES))
def test_every_alias_is_read_and_never_written(alias: str) -> None:
    chord = parse_chord(alias)
    assert chord.key == ALIASES[alias]
    assert chord.text == ALIASES[alias] != alias
    assert parse_chord(alias.lower()) == chord


def test_the_short_names_of_kde_and_qt_are_aliases() -> None:
    assert {a: ALIASES[a] for a in ("Return", "Esc", "Del", "Ins", "PgUp", "PgDown")} == {
        "Return": "Enter",
        "Esc": "Escape",
        "Del": "Delete",
        "Ins": "Insert",
        "PgUp": "PageUp",
        "PgDown": "PageDown",
    }
    assert parse_chord("Return") == parse_chord("Enter")


def test_the_media_keys_are_the_x_names_without_the_prefix_and_the_prefix_is_an_alias() -> None:
    for name in (
        "AudioRaiseVolume",
        "AudioLowerVolume",
        "AudioMute",
        "AudioMicMute",
        "AudioPlay",
        "AudioPause",
        "AudioStop",
        "AudioNext",
        "AudioPrev",
        "MonBrightnessUp",
        "MonBrightnessDown",
    ):
        assert name in KEYS and ALIASES["XF86" + name] == name
        assert parse_chord("XF86" + name).text == name
        assert parse_chord("xf86" + name.lower()).text == name
    assert not any(a.startswith("XF86") and a in KEYS for a in ALIASES)


def test_the_spec_lists_the_names_of_the_plain_keys() -> None:
    wanted = (
        "Enter Escape Tab Space Backspace Delete Insert Home End PageUp PageDown Left Right Up "
        "Down Plus"
    ).split()
    assert set(wanted) <= set(KEYS)
    assert [f"F{n}" for n in range(1, 25)] == [k for k in KEYS if re.fullmatch(r"F\d+", k)]
    assert "".join(k for k in KEYS if len(k) == 1 and k.isalpha()) == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert "".join(k for k in KEYS if len(k) == 1 and k.isdigit()) == "0123456789"


@pytest.mark.parametrize("order", list(itertools.permutations(MODIFIER_ORDER)))
def test_modifiers_are_read_in_any_order(order: tuple[str, ...]) -> None:
    chord = parse_chord("+".join([*order, "Space"]))
    assert chord == Chord(MODIFIER_ORDER, "Space")
    assert chord.qt == 0x04000000 | 0x08000000 | 0x02000000 | 0x10000000 | 0x20


def test_a_subset_of_the_modifiers_keeps_the_written_order() -> None:
    assert parse_chord("Shift+Ctrl+a").text == "Ctrl+Shift+A"
    assert parse_chord("alt+Tab").qt == 0x08000000 | 0x01000001
    assert parse_chord("Meta+Plus").qt == 0x10000000 | 0x2B


def test_the_numbers_the_brief_names() -> None:
    assert parse_chord("A").qt == 0x41
    assert parse_chord("Space").qt == 0x20
    assert parse_chord("Plus").qt == 0x2B
    assert parse_chord("Enter").qt == 0x01000004  # Qt::Key_Return
    assert parse_chord("Escape").qt == 0x01000000
    assert parse_chord("F1").qt == 0x01000030 and parse_chord("F24").qt == 0x01000047
    assert parse_chord("MonBrightnessUp").qt == 0x010000B2


def test_equal_presses_are_equal_whatever_the_spelling() -> None:
    assert parse_chord("ctrl+shift+F1") == parse_chord("Shift+CTRL+f1")
    assert hash(parse_chord("ctrl+a")) == hash(parse_chord("Ctrl+A"))
    assert parse_chord("Ctrl+A") != parse_chord("Ctrl+B")


def test_a_space_around_the_plus_is_allowed() -> None:
    assert parse_chord("Ctrl + Alt + T") == parse_chord("Ctrl+Alt+T")


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("Ctrl+", "empty part"),
        ("+A", "empty part"),
        ("Ctrl++A", "empty part"),
        ("Ctrl+Alt", "no key"),
        ("Ctrl", "no key"),
        ("Ctrl+Ctrl+A", "twice"),
        ("A+B", "not a modifier"),
        ("Ctrl+Hyper+A", "unknown modifier"),
        ("Ctrl+Spacebar", "unknown key name"),
        ("Plus+A", "not a modifier"),
    ],
)
def test_a_malformed_string_is_an_error_with_words(text: str, needle: str) -> None:
    with pytest.raises(ChordError) as caught:
        parse_chord(text)
    assert needle in caught.value.message


def test_an_unknown_key_names_the_nearest_known_one() -> None:
    with pytest.raises(ChordError) as caught:
        parse_chord("Ctrl+Spce")
    assert "did you mean Space" in caught.value.hint
    with pytest.raises(ChordError) as caught:
        parse_chord("PageDwn")
    assert "PageDown" in caught.value.hint
    with pytest.raises(ChordError) as caught:
        parse_chord("AudioRaiseVolum")
    assert "AudioRaiseVolume" in caught.value.hint
    with pytest.raises(ChordError) as caught:
        parse_chord("Contrl+A")
    assert "Ctrl" in caught.value.hint


def test_the_export_lists_the_names_the_parser_reads() -> None:
    data = key_names()
    assert data["modifiers"] == list(MODIFIER_ORDER) and data["separator"] == "+"
    assert data["keys"] == list(KEYS) and data["aliases"] == dict(ALIASES)
    groups = data["groups"]
    assert isinstance(groups, dict)
    assert [k for names in groups.values() for k in names] == list(KEYS)
    for name in (*KEYS, *ALIASES):  # every exported name parses
        parse_chord(name)


# -- the numbers, pinned to Qt's header ----------------------------------------------------------


def _header_values() -> dict[str, int]:
    assert HEADER is not None
    text = HEADER.read_text(encoding="utf-8")
    found: dict[str, int] = {}
    for name, value in re.findall(r"\b((?:Key|\w+Modifier)_?\w*)\s*=\s*(0x[0-9a-fA-F]+)", text):
        found.setdefault(name, int(value, 16))
    return found


@pytest.mark.skipif(HEADER is None, reason="Qt's qnamespace.h is not installed")
def test_every_key_number_is_the_value_in_qts_header() -> None:
    header = _header_values()
    wrong = []
    for name in KEYS:
        enumerator = QT_NAMES[name]
        if header.get(enumerator) != KEY_CODES[name]:
            wrong.append((name, enumerator, KEY_CODES[name], header.get(enumerator)))
    assert wrong == []


@pytest.mark.skipif(HEADER is None, reason="Qt's qnamespace.h is not installed")
def test_the_modifier_bits_are_the_values_in_qts_header() -> None:
    header = _header_values()
    assert MODIFIER_BITS == {
        "Shift": header["ShiftModifier"],
        "Ctrl": header["ControlModifier"],
        "Alt": header["AltModifier"],
        "Meta": header["MetaModifier"],
    }


def test_no_two_names_share_a_number_but_the_enter_pair() -> None:
    seen: dict[int, str] = {}
    for name in KEYS:
        assert KEY_CODES[name] not in seen, (name, seen.get(KEY_CODES[name]))
        seen[KEY_CODES[name]] = name


def test_the_module_is_pure() -> None:
    source = Path(keys.__file__).read_text(encoding="utf-8")
    assert "dbus" not in source and "open(" not in source
