"""``ctx.icons.app_icon`` (Tasks Module > Icons, M5 Brief G3): an application's icon from its
desktop file name, in a temporary data folder and a temporary icon theme. Never a real folder."""

from __future__ import annotations

from pathlib import Path

from tess_shell.services.desktop_entries import ApplicationIndex
from tess_shell.services.icons import FALLBACK, IconService
from tests.icon_theme import Dir, svg, write_theme
from tests.test_icon_service import Pixels


def entry(name: str, **keys: str) -> str:
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}"]
    return "\n".join(lines + [f"{k}={v}" for k, v in keys.items()]) + "\n"


def rig(tmp_path: Path, **kw: object) -> tuple[IconService, Path, Path]:
    """An icon service over a theme ``Mine`` and an ``applications`` folder, both temporary."""
    icons_base, data = tmp_path / "icons", tmp_path / "data"
    apps = data / "applications"
    apps.mkdir(parents=True)
    write_theme(
        icons_base,
        "Mine",
        [Dir("scalable/apps", 48, "Scalable", {"mine-icon.svg": svg("#000001")})],
        inherits=["hicolor"],
    )
    write_theme(icons_base, "hicolor", [Dir("scalable/apps", 48, "Scalable", {})])
    index = ApplicationIndex(
        {"XDG_DATA_HOME": str(data), "XDG_DATA_DIRS": "", "HOME": str(tmp_path)},
        locale="",
        desktops=(),
    )
    service = IconService(
        Pixels().register,
        theme="Mine",
        bases=[icons_base],
        pixmaps=None,
        config_home=tmp_path / "config",
        apps=index,
        **kw,  # type: ignore[arg-type]
    )
    return service, icons_base, apps


def test_the_icon_is_found_from_the_desktop_file_name(tmp_path: Path) -> None:
    icons, _, apps = rig(tmp_path)
    (apps / "org.example.app.desktop").write_text(entry("App", Icon="mine-icon"))
    assert icons.app_icon("org.example.app", 18) == svg("#000001")
    assert icons.app_icon("org.example.app.desktop", 18) == svg("#000001")  # with the suffix
    assert icons.app_icon("ORG.example.App", 18) == svg("#000001")  # KWin's case


def test_an_entry_with_no_icon_or_an_unknown_one_falls_back_to_the_name_then_the_shipped_icon(
    tmp_path: Path,
) -> None:
    icons, base, apps = rig(tmp_path)
    (apps / "noicon.desktop").write_text(entry("No icon"))
    (apps / "badicon.desktop").write_text(entry("Bad icon", Icon="nothing-like-it"))
    assert icons.app_icon("noicon", 18) == FALLBACK
    assert icons.app_icon("badicon", 18) == FALLBACK
    assert icons.app_icon("not-installed-at-all", 18) == FALLBACK
    assert icons.app_icon("", 18) == FALLBACK
    # no desktop entry, but the application's own name is an icon in the theme
    write_theme(
        base, "Mine", [Dir("scalable/apps", 48, "Scalable", {"mine-icon.svg": svg("#000001")})]
    )
    assert icons.app_icon("mine-icon", 18) == svg("#000001")  # no entry: the name is the icon
    icons.invalidate()
    assert icons.app_icon("Mine-Icon", 18) == svg("#000001")  # a window class in capitals


def test_an_entry_found_by_its_startup_class_gives_its_icon(tmp_path: Path) -> None:
    icons, _, apps = rig(tmp_path)
    (apps / "web.desktop").write_text(entry("Web", Icon="mine-icon", StartupWMClass="Navigator"))
    assert icons.app_icon("Navigator", 18) == svg("#000001")  # a window with only a class


def test_an_absolute_path_is_an_icon_only_when_the_desktop_entry_writes_it(
    tmp_path: Path,
) -> None:
    icons, _, apps = rig(tmp_path)
    picture = tmp_path / "picture.svg"
    picture.write_text(svg("#000002"))
    (apps / "pic.desktop").write_text(entry("Pic", Icon=str(picture)))
    assert icons.app_icon("pic", 18) == svg("#000002")
    # a window's class is never read as a path, whatever it says
    assert icons.app_icon(str(picture), 18) == FALLBACK


def test_a_changed_desktop_entry_is_seen_after_the_index_is_forgotten(tmp_path: Path) -> None:
    icons, _, apps = rig(tmp_path)
    assert icons.app_icon("late", 18) == FALLBACK
    (apps / "late.desktop").write_text(entry("Late", Icon="mine-icon"))
    assert icons.app_icon("late", 18) == FALLBACK  # read once: the folders are not read again
    icons.apps.invalidate()
    assert icons.app_icon("late", 18) == svg("#000001")


def test_the_icon_follows_a_theme_change_of_the_portal(tmp_path: Path) -> None:
    """H1: the portal's icon-theme beats ``kdeglobals``; a change calls ``on_theme_changed``, and
    the icon of the same application then comes from the new theme."""
    icons, base, apps = rig(tmp_path)
    write_theme(
        base,
        "Other",
        [Dir("scalable/apps", 48, "Scalable", {"mine-icon.svg": svg("#000009")})],
        inherits=["hicolor"],
    )
    (apps / "app.desktop").write_text(entry("App", Icon="mine-icon"))
    icons.set_theme("Mine")
    helper = icons.for_module("Tasks")
    assert helper.app_icon("app", 18) == svg("#000001")
    heard: list[str] = []
    helper.on_theme_changed(lambda: heard.append(icons.theme))
    icons._theme = None  # the portal decides (set_theme fixes the theme for the caller)
    icons.set_portal_theme("Other")
    assert heard == ["Other"]
    assert helper.app_icon("app", 18) == svg("#000009")
    helper.close()
    icons.set_portal_theme("Mine")
    assert heard == ["Other"]  # the module stopped: it hears nothing more


def test_a_service_made_with_no_index_reads_no_folder_of_the_users_home(tmp_path: Path) -> None:
    from pathlib import Path as P

    icons = IconService(
        Pixels().register, theme="x", bases=[tmp_path], pixmaps=None, config_home=tmp_path
    )
    home = P.home()
    assert all(not str(folder).startswith(str(home)) for folder in icons.apps.folders)
