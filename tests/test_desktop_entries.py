"""The desktop-entry index (Applications Module > The Application Index): the Desktop Entry
Specification's rules on temporary ``applications`` folders. Never a real data folder: every index
is given a temporary folder, or an environment that points at one."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from tess_shell.services.desktop_entries import (
    ApplicationIndex,
    EntryError,
    default_folders,
    locale_candidates,
    parse_entry,
    split_list,
    unescape,
)
from tests.fake_dbus import wait_for

FIREFOX = """\
# a comment
[Desktop Entry]
Version=1.0
Type=Application
Name=Web Browser
Name[de]=Webbrowser
Name[de_AT]=Webbrowser (Österreich)
GenericName=Browser
Comment=Browse\\sthe\\sweb
Keywords=internet;www;web\\;surf;
Categories=Network;WebBrowser;
Exec=firefox %u
Icon=firefox-icon
Terminal=false
StartupWMClass=Navigator
TryExec=firefox

[Desktop Action new-window]
Name=New Window
Exec=firefox --new-window
"""


def entry(name: str = "App", **keys: str) -> str:
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}"]
    lines += [f"{k}={v}" for k, v in keys.items()]
    return "\n".join(lines) + "\n"


def put(folder: Path, relative: str, text: str) -> Path:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def index(*folders: Path, **kw: object) -> ApplicationIndex:
    kw.setdefault("locale", "")
    kw.setdefault("desktops", ())
    kw.setdefault("which", lambda program: f"/bin/{program}")
    return ApplicationIndex(folders=folders, **kw)  # type: ignore[arg-type]


# -- one file ---------------------------------------------------------------------------------


def test_a_file_is_read_as_the_specification_writes_it(tmp_path: Path) -> None:
    got = parse_entry(FIREFOX, "firefox.desktop", tmp_path / "firefox.desktop")
    assert (got.name, got.generic_name, got.exec, got.icon) == (
        "Web Browser",
        "Browser",
        "firefox %u",
        "firefox-icon",
    )
    assert got.comment == "Browse the web"  # \s is a space
    assert got.keywords == ("internet", "www", "web;surf")  # \; is a semicolon in an item
    assert got.categories == ("Network", "WebBrowser")
    assert got.startup_wm_class == "Navigator" and got.try_exec == "firefox"
    assert got.app == "firefox"
    assert not (got.terminal or got.no_display or got.hidden)


def test_a_localised_key_follows_the_locale_in_the_specifications_order(tmp_path: Path) -> None:
    path = tmp_path / "f.desktop"
    for locale, expected in (
        ("de_AT.UTF-8", "Webbrowser (Österreich)"),  # lang_COUNTRY before lang
        ("de_DE.UTF-8", "Webbrowser"),  # no Name[de_DE]: lang
        ("fr_FR.UTF-8", "Web Browser"),  # no French at all: the plain key
        ("C", "Web Browser"),
    ):
        got = parse_entry(FIREFOX, "f.desktop", path, locale_candidates(locale))
        assert got.name == expected, locale
    assert locale_candidates("sr_RS.UTF-8@latin") == ("sr_RS@latin", "sr_RS", "sr@latin", "sr")


def test_escapes_and_lists() -> None:
    assert unescape("a\\sb\\nc\\\\d\\q") == "a b\nc\\d\\q"  # an unknown escape stays as written
    assert split_list("a;b\\;c;;d;") == ("a", "b;c", "d")
    assert split_list("") == ()


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("[Other]\nName=x\n", "no [Desktop Entry]"),
        ("[Desktop Entry\nName=x\n", "not closed"),
        ("[Desktop Entry]\nType=Link\nName=x\nURL=y\n", "not Application"),
        ("[Desktop Entry]\nType=Application\nExec=x\n", "no Name"),
        ("[Desktop Entry]\nType=Application\nName=x\nnonsense\n", "not Key=Value"),
    ],
)
def test_a_file_that_is_not_an_application_is_refused_with_a_reason(
    text: str, why: str, tmp_path: Path
) -> None:
    with pytest.raises(EntryError, match=re.escape(why)):
        parse_entry(text, "x.desktop", tmp_path / "x.desktop")


# -- the folders ------------------------------------------------------------------------------


def test_the_folders_are_read_in_priority_order_and_the_first_id_wins(tmp_path: Path) -> None:
    home, system = tmp_path / "home", tmp_path / "system"
    put(home, "app.desktop", entry("Mine"))
    put(system, "app.desktop", entry("Theirs"))
    put(system, "other.desktop", entry("Other"))
    got = index(home, system)
    assert got.get("app").name == "Mine"  # type: ignore[union-attr]
    assert [e.id for e in got.entries()] == ["app.desktop", "other.desktop"]


def test_an_id_is_the_path_below_the_folder_with_slashes_as_dashes(tmp_path: Path) -> None:
    put(tmp_path, "kde/org.kde.dolphin.desktop", entry("Files"))
    got = index(tmp_path)
    assert [e.id for e in got.entries()] == ["kde-org.kde.dolphin.desktop"]
    assert got.get("kde-org.kde.dolphin") is not None


def test_a_hidden_entry_in_a_folder_of_higher_priority_deletes_the_one_below(
    tmp_path: Path,
) -> None:
    home, system = tmp_path / "home", tmp_path / "system"
    put(home, "gone.desktop", entry("Gone", Hidden="true"))
    put(system, "gone.desktop", entry("Gone"))
    put(system, "kept.desktop", entry("Kept"))
    got = index(home, system)
    assert [e.name for e in got.applications()] == ["Kept"]
    assert got.get("gone") is not None and got.get("gone").hidden  # type: ignore[union-attr]


def test_a_broken_file_never_stops_the_index(tmp_path: Path) -> None:
    put(tmp_path, "good.desktop", entry("Good"))
    put(tmp_path, "bad.desktop", "[Desktop Entry]\nno equals sign\n")
    put(tmp_path, "link.desktop", "[Desktop Entry]\nType=Link\nName=L\n")
    (tmp_path / "binary.desktop").write_bytes(b"\xff\xfe\x00[\x00")
    put(tmp_path, "readme.txt", "not an entry")
    assert [e.id for e in index(tmp_path).entries()] == ["good.desktop"]


def test_the_launchers_view_applies_nodisplay_onlyshowin_notshowin_and_tryexec(
    tmp_path: Path,
) -> None:
    put(tmp_path, "plain.desktop", entry("Plain"))
    put(tmp_path, "nodisplay.desktop", entry("NoDisplay", NoDisplay="true"))
    put(tmp_path, "gnome.desktop", entry("GnomeOnly", OnlyShowIn="GNOME;Unity;"))
    put(tmp_path, "kde.desktop", entry("KdeOnly", OnlyShowIn="KDE;"))
    put(tmp_path, "notkde.desktop", entry("NotKde", NotShowIn="KDE;"))
    put(tmp_path, "tryexec.desktop", entry("Present", TryExec="present"))
    put(tmp_path, "missing.desktop", entry("Missing", TryExec="missing"))
    got = index(
        tmp_path,
        desktops=("KDE",),
        which=lambda program: "/bin/x" if program == "present" else None,
    )
    assert [e.name for e in got.applications()] == ["KdeOnly", "Plain", "Present"]
    # every entry is still there for an icon: a NoDisplay application has windows too
    assert got.get("nodisplay") is not None and len(got.entries()) == 7


def test_an_entry_is_found_for_a_window_by_id_case_or_startup_class(tmp_path: Path) -> None:
    put(tmp_path, "org.kde.dolphin.desktop", entry("Dolphin"))
    put(tmp_path, "firefox.desktop", entry("Firefox", StartupWMClass="Navigator"))
    got = index(tmp_path)
    assert got.for_window("org.kde.dolphin").name == "Dolphin"  # type: ignore[union-attr]
    assert got.for_window("org.kde.dolphin.desktop").name == "Dolphin"  # type: ignore[union-attr]
    assert got.for_window("Org.KDE.Dolphin").name == "Dolphin"  # type: ignore[union-attr]
    assert got.for_window("navigator").name == "Firefox"  # type: ignore[union-attr]
    assert got.for_window("unknown") is None and got.for_window("") is None


def test_the_folders_are_read_once(tmp_path: Path) -> None:
    put(tmp_path, "a.desktop", entry("A"))
    got = index(tmp_path)
    for _ in range(5):
        got.get("a")
        got.for_window("a")
        got.applications()
    assert got.scans == 1
    got.invalidate()
    got.get("a")
    assert got.scans == 2


# -- the environment --------------------------------------------------------------------------


def test_the_folders_come_from_xdg_data_home_and_xdg_data_dirs(tmp_path: Path) -> None:
    env = {
        "XDG_DATA_HOME": str(tmp_path / "h"),
        "XDG_DATA_DIRS": f"{tmp_path / 'a'}:{tmp_path / 'b'}",
    }
    assert default_folders(env) == [
        tmp_path / "h" / "applications",
        tmp_path / "a" / "applications",
        tmp_path / "b" / "applications",
    ]
    put(tmp_path / "b" / "applications", "x.desktop", entry("X"))
    got = ApplicationIndex(env, locale="", desktops=())
    assert [e.id for e in got.entries()] == ["x.desktop"]
    # the defaults of the specification when the variables are empty
    assert default_folders({"HOME": "/h"}) == [
        Path("/h/.local/share/applications"),
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
    ]


def test_locale_and_desktop_come_from_the_environment(tmp_path: Path) -> None:
    put(tmp_path / "applications", "a.desktop", FIREFOX)
    put(tmp_path / "applications", "k.desktop", entry("K", OnlyShowIn="KDE;"))
    env = {
        "XDG_DATA_HOME": str(tmp_path),
        "XDG_DATA_DIRS": str(tmp_path / "no-such-folder"),
        "LANG": "en_US.UTF-8",
        "LC_MESSAGES": "de_DE.UTF-8",  # LC_MESSAGES beats LANG
        "XDG_CURRENT_DESKTOP": "KDE",
    }
    got = ApplicationIndex(env, which=lambda p: "/bin/" + p)
    assert sorted(e.name for e in got.applications()) == ["K", "Webbrowser"]


def test_a_test_that_names_no_folder_never_reads_the_users_home() -> None:
    """The guard: with ``PYTEST_CURRENT_TEST`` set, a default index drops a folder under the real
    home, so a test that forgot to point ``XDG_DATA_HOME`` at a temporary folder reads nothing."""
    assert os.environ.get("PYTEST_CURRENT_TEST")
    home = Path(os.path.expanduser("~"))
    got = ApplicationIndex({"HOME": str(home), "XDG_DATA_DIRS": "/usr/share"})
    assert got.folders == [Path("/usr/share/applications")]
    # ... and a folder a test names itself is read even when it is under the home
    named = ApplicationIndex(folders=[home / "nowhere-at-all"])
    assert named.folders == [home / "nowhere-at-all"] and named.entries() == []


# -- following the folders --------------------------------------------------------------------


def test_a_new_file_makes_the_index_stale_and_the_listener_hears_of_it(tmp_path: Path) -> None:
    put(tmp_path, "a.desktop", entry("A"))
    got = index(tmp_path)
    assert [e.id for e in got.entries()] == ["a.desktop"]
    heard: list[int] = []
    got.on_changed(lambda: heard.append(got.scans))
    got.watch(debounce=0.05)
    try:
        put(tmp_path, "b.desktop", entry("B"))
        assert wait_for(lambda: heard, timeout=5)
        assert [e.id for e in got.entries()] == ["a.desktop", "b.desktop"]
        assert got.scans == 2  # read again, once
        put(tmp_path, "notes.txt", "x")  # not an entry: no change
        before = len(heard)
        put(tmp_path, "c.desktop", entry("C"))
        assert wait_for(lambda: len(heard) > before, timeout=5)
        assert [e.id for e in got.entries()][-1] == "c.desktop"
    finally:
        got.unwatch()


def test_a_cancelled_listener_hears_nothing(tmp_path: Path) -> None:
    put(tmp_path, "a.desktop", entry("A"))
    got = index(tmp_path)
    got.entries()
    kept: list[int] = []
    gone: list[int] = []
    got.on_changed(lambda: kept.append(1))
    cancel = got.on_changed(lambda: gone.append(1))
    cancel()
    got.watch(debounce=0.05)
    try:
        put(tmp_path, "b.desktop", entry("B"))
        assert wait_for(lambda: kept, timeout=5)
        assert gone == []
    finally:
        got.unwatch()
