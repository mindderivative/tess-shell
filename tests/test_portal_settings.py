"""The portal's other settings (Portals > Settings Read in M5h): the icon theme, the UI font and
``enable-animations``, from the keys to what the shell does with them. Fakes only: a temporary icon
folder, a fake Settings portal on a private bus."""

from __future__ import annotations

from pathlib import Path

import pytest
from dbus_fast import Variant

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.model.look import make_look, resolve
from tess_shell.schema.look import GENERIC_FONT, SYSTEM_FONT, effective_tokens
from tess_shell.services.bus import ServiceThread
from tess_shell.services.icons import IconService
from tess_shell.services.portal import (
    INTERFACE_NAMESPACE,
    NAMESPACE,
    PortalReader,
    apply_key,
    font_family,
    parse,
)
from tests.fake_portal import HAVE_DAEMON, fake_portal, wait_for
from tests.icon_theme import Dir, svg, write_theme
from tests.test_look import theme
from tests.test_tray_module import settle, up, values
from tests.tray_rig import tray_desk, tray_shell

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

# -- the keys -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "family"),
    [
        ("Hack Nerd Font  10", "Hack Nerd Font"),  # as read on the maintainer's machine
        ("Noto Sans 11", "Noto Sans"),
        ("Noto Sans Bold 11", "Noto Sans"),  # style words and the size go
        ("Sans Italic Semi-Bold 9.5", "Sans"),
        ("Sans, Serif 10", "Sans"),  # a family list: the first
        ("Ubuntu", "Ubuntu"),  # no size
        ("Bold 10", "Bold"),  # a family that is a style word keeps itself
        ("", None),
        ("   ", None),
        ("10", None),
        (12, None),  # not a string
        (["Sans 10"], None),
    ],
)
def test_the_font_family_is_taken_from_a_pango_description(raw: object, family: str | None) -> None:
    assert font_family(Variant("s", raw) if isinstance(raw, str) else raw) == family


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("icon-theme", 7, Appearance()),  # wrong type: the default
        ("icon-theme", "", Appearance()),
        ("font-name", 7, Appearance()),
        ("enable-animations", "false", Appearance()),  # a string is not a bool: animations stay on
        ("enable-animations", 0, Appearance()),
        ("enable-animations", False, Appearance(animations=False)),
        ("icon-theme", " Papirus ", Appearance(icon_theme="Papirus")),
        ("cursor-theme", "Oxygen", Appearance()),  # read on 2026-11-13, not used
    ],
)
def test_odd_values_of_the_interface_keys_are_that_keys_default(
    key: str, value: object, expected: Appearance
) -> None:
    assert apply_key(Appearance(), INTERFACE_NAMESPACE, key, value) == expected


def test_a_key_counts_only_in_its_own_namespace() -> None:
    got = parse(
        {
            INTERFACE_NAMESPACE: {"reduced-motion": Variant("u", 1), "color-scheme": 1},
            NAMESPACE: {"icon-theme": Variant("s", "x"), "enable-animations": Variant("b", False)},
            "org.example.other": {"font-name": Variant("s", "Sans 10")},
        }
    )
    assert got == Appearance()


def test_a_wrong_typed_key_does_not_stop_the_others() -> None:
    got = parse(
        {
            NAMESPACE: {"color-scheme": Variant("u", 2)},
            INTERFACE_NAMESPACE: {
                "icon-theme": Variant("u", 3),
                "font-name": Variant("s", "Sans 10"),
            },
        }
    )
    assert (got.scheme, got.icon_theme, got.font_family) == ("light", None, "Sans")


# -- reduced motion from either source ------------------------------------------------------------


@pytest.mark.parametrize(
    ("appearance", "reduced"),
    [
        (Appearance(), False),
        (Appearance(reduced_motion=True), True),
        (Appearance(animations=False), True),
        (Appearance(reduced_motion=True, animations=False), True),
    ],
)
def test_either_source_gives_no_animation(appearance: Appearance, reduced: bool) -> None:
    assert appearance.motion_reduced is reduced
    durations = effective_tokens(theme(), appearance)["motion.duration.long"].value
    assert getattr(durations, "value", None) == (0 if reduced else 400)
    node = m.Node(
        "Rectangle",
        props={"Transition": m.Text("x")},
        style={},  # asks for the theme's default
    )
    look = make_look(theme(), [], appearance)
    (out,), _ = resolve([node], look)
    duration = out.style["Duration"]
    assert isinstance(duration, m.Number)
    assert (duration.value == 0) is reduced


# -- the font token ---------------------------------------------------------------------------


def test_the_desktop_font_is_a_token_and_a_layout_can_use_it() -> None:
    node = m.Node(
        "Text",
        props={"Text": m.Text("x")},
        style={"Font_Family": m.TokenRef(SYSTEM_FONT, "font_family")},
    )
    look = make_look(theme(), [], Appearance(font_family="Hack Nerd Font"))
    (out,), errors = resolve([node], look)
    assert errors == []
    assert out.style["Font_Family"] == m.Text("Hack Nerd Font")
    other = look.with_appearance(Appearance(font_family="Noto Sans"))  # a change re-resolves
    (out,), _ = resolve([node], other)
    assert out.style["Font_Family"] == m.Text("Noto Sans")


def test_without_a_desktop_font_the_token_is_generic_so_a_layout_still_resolves() -> None:
    # the check before the shell runs uses an Appearance with no font: it must not fail
    value = effective_tokens(theme(), Appearance())[SYSTEM_FONT].value
    assert getattr(value, "value", None) == GENERIC_FONT


def test_a_theme_that_sets_the_token_itself_keeps_its_own() -> None:
    own = theme(
        "---\nTDL: 0.2\nName: T\n---\n\n"
        'Theme { Type { System { Font_Family: "Mine" } } Color { Surface: "#101010" } }\n'
    )
    value = effective_tokens(own, Appearance(font_family="Desktop"))[SYSTEM_FONT].value
    assert getattr(value, "value", None) == "Mine"


# -- the icon service -------------------------------------------------------------------------


def two_themes(base: Path) -> None:
    for name, fill in (("Portal", "#00ff00"), ("Kde", "#0000ff")):
        write_theme(base, name, [Dir("scalable/apps", 48, "Scalable", {"x.svg": svg(fill)})])


def test_the_portals_theme_comes_before_kdeglobals_and_kdeglobals_before_hicolor(
    tmp_path: Path,
) -> None:
    base, config = tmp_path / "icons", tmp_path / "config"
    config.mkdir()
    two_themes(base)
    write_theme(base, "hicolor", [Dir("scalable/apps", 48, "Scalable", {"x.svg": svg("#ff0000")})])
    refs: list[str] = []

    def service() -> IconService:
        return IconService(lambda w, h, b: "", bases=[base], pixmaps=None, config_home=config)

    icons = service()
    assert icons.theme == "hicolor"
    assert icons.theme_icon("x", 18) == svg("#ff0000")
    (config / "kdeglobals").write_text("[Icons]\nTheme=Kde\n")
    icons = service()
    assert icons.theme_icon("x", 18) == svg("#0000ff")
    icons.set_portal_theme("Portal")
    assert (icons.theme, icons.theme_icon("x", 18)) == ("Portal", svg("#00ff00"))
    icons.set_portal_theme(None)  # the portal names none: back to kdeglobals
    assert icons.theme_icon("x", 18) == svg("#0000ff")
    icons.set_portal_theme("NoSuchTheme")  # an unknown theme still ends in hicolor
    assert icons.theme_icon("x", 18) == svg("#ff0000")
    assert refs == []


def test_a_listener_hears_a_real_change_of_the_portals_theme_once(tmp_path: Path) -> None:
    icons = IconService(
        lambda w, h, b: "", bases=[tmp_path], pixmaps=None, config_home=tmp_path / "c"
    )
    heard: list[str] = []
    cancel = icons.on_theme_changed(lambda: heard.append(icons.theme))
    icons.set_portal_theme("A")
    icons.set_portal_theme("A")  # the same again: nothing changed, nothing to redo
    icons.set_portal_theme("B")
    cancel()
    icons.set_portal_theme("C")
    assert heard == ["A", "B"]


@needs_daemon
def test_a_changed_icon_theme_makes_the_trays_icons_again(tmp_path: Path) -> None:
    with tray_desk(tmp_path, theme=None) as t:
        two_themes(t.theme)
        t.icons.set_portal_theme("Kde")
        item = t.item("1-1", icon="x")
        with tray_shell(t) as w:
            up(t, item)
            assert settle(
                t, w, lambda: "#0000ff" in (values(w).get("items") or [{}])[0].get("icon", "")
            )
            t.icons.set_portal_theme("Portal")  # what the app does on the portal's signal
            assert settle(t, w, lambda: "#00ff00" in values(w)["items"][0]["icon"])
            assert w.warnings() == [], w.warnings()


# -- through the reader ------------------------------------------------------------------------


@needs_daemon
def test_the_reader_reads_the_interface_keys_at_start_and_follows_them() -> None:
    seen: list[Appearance] = []
    with fake_portal() as (address, portal):
        service = ServiceThread(address)
        service.start()
        reader = PortalReader(service, seen.append)
        try:
            reader.start()
            first = reader.first(5.0)
            assert (first.icon_theme, first.font_family, first.animations) == (
                "breeze-dark",
                "Hack Nerd Font",
                True,
            )
            assert portal.settings.calls == ["Register", "ReadAll"]  # still one read
            portal.set("icon-theme", Variant("s", "Papirus"), INTERFACE_NAMESPACE)
            portal.set("font-name", Variant("s", "Noto Sans Bold 11"), INTERFACE_NAMESPACE)
            portal.set("enable-animations", Variant("b", False), INTERFACE_NAMESPACE)
            assert wait_for(lambda: seen and seen[-1].motion_reduced, 10)
            last = seen[-1]
            assert (last.icon_theme, last.font_family, last.animations) == (
                "Papirus",
                "Noto Sans",
                False,
            )
            assert last.reduced_motion is False  # the other key did not say so
            portal.set("enable-animations", Variant("b", True), INTERFACE_NAMESPACE)
            portal.set("reduced-motion", Variant("u", 1))  # either one is enough
            assert wait_for(lambda: seen[-1].reduced_motion and seen[-1].animations, 10)
            assert seen[-1].motion_reduced
        finally:
            reader.stop()
            service.stop()
