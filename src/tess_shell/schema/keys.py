"""Key strings of the shortcuts (Global Shortcuts > Key Names).

A value is modifiers and one key joined by ``+``: ``Ctrl+Shift+F1``. The written (canonical) order
is ``Ctrl``, ``Alt``, ``Shift``, ``Meta``, then the key; any order and any case is read. Key names
are full words in title case; the media and hardware keys carry the X key names without the
``XF86`` prefix (``AudioRaiseVolume``), and the form with the prefix is read, never written. The
short names KDE and Qt write (``Return``, ``Esc``, ``Del``, ``Ins``, ``PgUp``, ``PgDown``) are read
as aliases and never written.

:func:`parse_chord` gives the Qt key integer the desktop's shortcut service takes (modifier bits
OR-ed with the ``Qt::Key`` value). The numbers are those of Qt's ``qnamespace.h`` (Qt 6.12, read on
2026-11-13); ``tests/test_shortcut_keys.py`` pins every one of them to that header when it is
installed. This module is pure: no D-Bus, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from tess_shell.schema.findings import nearest

SEPARATOR = "+"
MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Meta")
# Qt::KeyboardModifier (qnamespace.h): ShiftModifier, ControlModifier, AltModifier, MetaModifier
MODIFIER_BITS = {"Shift": 0x02000000, "Ctrl": 0x04000000, "Alt": 0x08000000, "Meta": 0x10000000}
X_PREFIX = "XF86"

# canonical name -> (Qt::Key enumerator, its value). The key of the table is what is written.
_NAMED: dict[str, tuple[str, int]] = {
    "Enter": ("Key_Return", 0x01000004),  # the main Enter key; the keypad's is Key_Enter (0x5)
    "Escape": ("Key_Escape", 0x01000000),
    "Tab": ("Key_Tab", 0x01000001),
    "Space": ("Key_Space", 0x20),
    "Backspace": ("Key_Backspace", 0x01000003),
    "Delete": ("Key_Delete", 0x01000007),
    "Insert": ("Key_Insert", 0x01000006),
    "Home": ("Key_Home", 0x01000010),
    "End": ("Key_End", 0x01000011),
    "Left": ("Key_Left", 0x01000012),
    "Up": ("Key_Up", 0x01000013),
    "Right": ("Key_Right", 0x01000014),
    "Down": ("Key_Down", 0x01000015),
    "PageUp": ("Key_PageUp", 0x01000016),
    "PageDown": ("Key_PageDown", 0x01000017),
    "Plus": ("Key_Plus", 0x2B),
    "Print": ("Key_Print", 0x01000009),
    "Pause": ("Key_Pause", 0x01000008),
    "Menu": ("Key_Menu", 0x01000055),
}

# the hardware and media keys, by the X key name without ``XF86``; the Qt enumerator each one maps
# to (the pairs Qt's own xkb mapping makes) and its value
_HARDWARE: dict[str, tuple[str, int]] = {
    "AudioRaiseVolume": ("Key_VolumeUp", 0x01000072),
    "AudioLowerVolume": ("Key_VolumeDown", 0x01000070),
    "AudioMute": ("Key_VolumeMute", 0x01000071),
    "AudioMicMute": ("Key_MicMute", 0x01000113),
    "AudioPlay": ("Key_MediaPlay", 0x01000080),
    "AudioPause": ("Key_MediaPause", 0x01000085),
    "AudioStop": ("Key_MediaStop", 0x01000081),
    "AudioNext": ("Key_MediaNext", 0x01000083),
    "AudioPrev": ("Key_MediaPrevious", 0x01000082),
    "AudioRecord": ("Key_MediaRecord", 0x01000084),
    "AudioRewind": ("Key_AudioRewind", 0x010000C5),
    "AudioForward": ("Key_AudioForward", 0x01000102),
    "AudioMedia": ("Key_LaunchMedia", 0x010000A1),
    "MonBrightnessUp": ("Key_MonBrightnessUp", 0x010000B2),
    "MonBrightnessDown": ("Key_MonBrightnessDown", 0x010000B3),
    "KbdLightOnOff": ("Key_KeyboardLightOnOff", 0x010000B4),
    "KbdBrightnessUp": ("Key_KeyboardBrightnessUp", 0x010000B5),
    "KbdBrightnessDown": ("Key_KeyboardBrightnessDown", 0x010000B6),
    "PowerOff": ("Key_PowerOff", 0x010000B7),
    "WakeUp": ("Key_WakeUp", 0x010000B8),
    "Eject": ("Key_Eject", 0x010000B9),
    "ScreenSaver": ("Key_ScreenSaver", 0x010000BA),
    "WWW": ("Key_WWW", 0x010000BB),
    "Sleep": ("Key_Sleep", 0x01020004),
    "Suspend": ("Key_Suspend", 0x0100010C),
    "Hibernate": ("Key_Hibernate", 0x01000108),
    "Standby": ("Key_Standby", 0x01000093),
    "HomePage": ("Key_HomePage", 0x01000090),
    "Favorites": ("Key_Favorites", 0x01000091),
    "Search": ("Key_Search", 0x01000092),
    "Mail": ("Key_LaunchMail", 0x010000A0),
    "Calculator": ("Key_Calculator", 0x010000CB),
    "Calendar": ("Key_Calendar", 0x010000E4),
    "Explorer": ("Key_Explorer", 0x010000D5),
    "Documents": ("Key_Documents", 0x010000D3),
    "Tools": ("Key_Tools", 0x010000F1),
    "Music": ("Key_Music", 0x010000FD),
    "Video": ("Key_Video", 0x010000F3),
    "Display": ("Key_Display", 0x010000D1),
    "Battery": ("Key_Battery", 0x010000FE),
    "Bluetooth": ("Key_Bluetooth", 0x010000FF),
    "WLAN": ("Key_WLAN", 0x01000100),
    "TouchpadToggle": ("Key_TouchpadToggle", 0x01000110),
    "ZoomIn": ("Key_ZoomIn", 0x010000F6),
    "ZoomOut": ("Key_ZoomOut", 0x010000F7),
    "Back": ("Key_Back", 0x01000061),
    "Forward": ("Key_Forward", 0x01000062),
    "Refresh": ("Key_Refresh", 0x01000064),
}
# XF86Launch0 .. XF86Launch9, XF86LaunchA .. XF86LaunchF  ->  Key_Launch0 .. Key_LaunchF (0xa2 ..
# 0xb1, one after the other in qnamespace.h)
_HARDWARE.update(
    {
        f"Launch{digit}": (f"Key_Launch{digit}", 0x010000A2 + i)
        for i, digit in enumerate("0123456789ABCDEF")
    }
)

_ALIAS_NAMES = {
    "Return": "Enter",
    "Esc": "Escape",
    "Del": "Delete",
    "Ins": "Insert",
    "PgUp": "PageUp",
    "PgDown": "PageDown",
}


def _build() -> tuple[dict[str, int], dict[str, str], dict[str, str], dict[str, list[str]]]:
    codes: dict[str, int] = {}
    qt: dict[str, str] = {}
    groups: dict[str, list[str]] = {"letters": [], "digits": [], "function": [], "named": []}
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        codes[letter], qt[letter] = ord(letter), f"Key_{letter}"
        groups["letters"].append(letter)
    for digit in "0123456789":
        codes[digit], qt[digit] = ord(digit), f"Key_{digit}"
        groups["digits"].append(digit)
    for n in range(1, 25):
        codes[f"F{n}"], qt[f"F{n}"] = 0x01000030 + n - 1, f"Key_F{n}"
        groups["function"].append(f"F{n}")
    for name, (enumerator, code) in _NAMED.items():
        codes[name], qt[name] = code, enumerator
        groups["named"].append(name)
    groups["hardware"] = []
    for name, (enumerator, code) in _HARDWARE.items():
        codes[name], qt[name] = code, enumerator
        groups["hardware"].append(name)
    aliases = dict(_ALIAS_NAMES)
    for name in _HARDWARE:
        aliases[X_PREFIX + name] = name
    return codes, qt, aliases, groups


KEY_CODES, QT_NAMES, ALIASES, GROUPS = _build()
KEYS = tuple(KEY_CODES)  # the canonical names, in the order of GROUPS
_LOWER: dict[str, str] = {name.lower(): name for name in KEYS}
_LOWER.update({alias.lower(): target for alias, target in ALIASES.items()})
_MODIFIERS_LOWER = {name.lower(): name for name in MODIFIER_ORDER}


class ChordError(ValueError):
    """A key string that cannot be read: the message and a hint for the person who wrote it."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


@dataclass(frozen=True, slots=True)
class Chord:
    """One key press: modifiers (canonical names, in ``MODIFIER_ORDER``) and a canonical key name.
    Two chords are equal when they are the same press, however they were written."""

    modifiers: tuple[str, ...]
    key: str

    @property
    def text(self) -> str:
        """The canonical written form: ``Ctrl+Alt+Shift+Meta+Key``."""
        return SEPARATOR.join((*self.modifiers, self.key))

    @property
    def qt(self) -> int:
        """The Qt key integer: modifier bits OR-ed with the ``Qt::Key`` value."""
        bits = 0
        for modifier in self.modifiers:
            bits |= MODIFIER_BITS[modifier]
        return bits | KEY_CODES[self.key]

    def __str__(self) -> str:
        return self.text


def _all_names() -> list[str]:
    return [*KEYS, *ALIASES]


def parse_chord(text: str) -> Chord:
    """Read a key string. Raises :class:`ChordError` for an empty string, a name that is no
    modifier before the last ``+``, a repeated modifier, a missing key, or an unknown key name (the
    hint names the nearest known one)."""
    if not text.strip():
        raise ChordError(
            "a key string is empty", 'write modifiers and one key, such as "Ctrl+Space"'
        )
    parts = [p.strip() for p in text.split(SEPARATOR)]
    if any(not p for p in parts):
        raise ChordError(
            f"'{text}' has an empty part between or after the +",
            f'the plus key is written Plus: "Ctrl+Plus"; found "{text}"',
        )
    *front, last = parts
    held: set[str] = set()
    for part in front:
        modifier = _MODIFIERS_LOWER.get(part.lower())
        if modifier is None:
            if part.lower() in _LOWER:
                raise ChordError(
                    f"'{part}' is a key, not a modifier: a key string has one key, the last part",
                    f"the modifiers are {', '.join(MODIFIER_ORDER)}",
                )
            close = nearest(part, MODIFIER_ORDER)
            raise ChordError(
                f"unknown modifier '{part}'",
                f"did you mean {', '.join(close)}?"
                if close
                else f"the modifiers are {', '.join(MODIFIER_ORDER)}",
            )
        if modifier in held:
            raise ChordError(f"the modifier {modifier} is written twice", "")
        held.add(modifier)
    if last.lower() in _MODIFIERS_LOWER:
        raise ChordError(
            f"'{text}' has no key after the modifiers",
            f'write a key last, such as "{text}+Space"',
        )
    name = _LOWER.get(last.lower())
    if name is None:
        close = nearest(last, _all_names())
        raise ChordError(
            f"unknown key name '{last}'",
            f"did you mean {', '.join(close)}?" if close else "see the key names in the schema",
        )
    return Chord(tuple(m for m in MODIFIER_ORDER if m in held), name)


def key_names() -> dict[str, object]:
    """The names a key string may use, for the schema export (the ``key_chord`` kind): the
    modifiers in the written order, the canonical key names by group, the aliases that are read and
    never written."""
    return {
        "separator": SEPARATOR,
        "modifiers": list(MODIFIER_ORDER),
        "case_sensitive": False,
        "keys": list(KEYS),
        "groups": {group: list(names) for group, names in GROUPS.items()},
        "aliases": dict(ALIASES),
    }
