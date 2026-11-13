"""The shell's icon lookup (Tray Module > Icons, G8): a temporary theme folder under the pytest tmp
dir, never a real one. The Inherits chain, hicolor, SVG over png, the png nearest above, an item's
``IconThemePath``, the ARGB32 pixmap, the cache and its invalidation, and the cost."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from loguru import logger

from tess_shell.services.icons import IconService, argb_to_rgba, default_bases, desktop_theme
from tests.icon_theme import Dir, png_bytes, svg, write_theme


class Pixels:
    """What the binder's registry is to the service: a table of registered pixels."""

    def __init__(self) -> None:
        self.table: dict[str, tuple[int, int, bytes]] = {}

    def register(self, width: int, height: int, rgba: bytes) -> str:
        ref = f"pixels:{len(self.table)}"
        for known, value in self.table.items():
            if value == (width, height, rgba):
                return known
        self.table[ref] = (width, height, rgba)
        return ref

    def colour(self, ref: str) -> tuple[int, ...]:
        _, _, rgba = self.table[ref]
        return tuple(rgba[:4])


def service(tmp_path: Path, theme: str = "Mine", **kw: object) -> tuple[IconService, Pixels]:
    pixels = Pixels()
    kw.setdefault("bases", [tmp_path / "icons"])
    kw.setdefault("pixmaps", None)
    return IconService(pixels.register, theme=theme, **kw), pixels  # type: ignore[arg-type]


def test_an_icon_is_found_through_inherits_and_the_user_theme_wins_over_its_parent(
    tmp_path: Path,
) -> None:
    base = tmp_path / "icons"
    write_theme(base, "Grand", [Dir("scalable/apps", 48, "Scalable", {"deep.svg": svg("#000001")})])
    write_theme(
        base,
        "Parent",
        [
            Dir(
                "scalable/apps",
                48,
                "Scalable",
                {"up.svg": svg("#000002"), "both.svg": svg("#0000a1")},
            )
        ],
        inherits=["Grand"],
    )
    write_theme(
        base,
        "Mine",
        [Dir("scalable/apps", 48, "Scalable", {"both.svg": svg("#0000b2")})],
        inherits=["Parent"],
    )
    icons, _ = service(tmp_path)
    assert icons.theme_icon("deep", 18) == svg("#000001")  # two themes up
    assert icons.theme_icon("up", 18) == svg("#000002")
    assert icons.theme_icon("both", 18) == svg("#0000b2")  # the user's theme first
    assert icons.theme_icon("nowhere", 18) is None


def test_hicolor_is_the_last_theme_even_when_nobody_inherits_it(tmp_path: Path) -> None:
    base = tmp_path / "icons"
    write_theme(base, "Mine", [Dir("scalable/apps", 48, "Scalable", {"mine.svg": svg("#000003")})])
    write_theme(
        base,
        "hicolor",
        [Dir("scalable/apps", 48, "Scalable", {"only-hicolor.svg": svg("#000004")})],
    )
    icons, _ = service(tmp_path)
    assert icons.theme_icon("only-hicolor", 18) == svg("#000004")
    assert icons.theme_icon("mine", 18) == svg("#000003")


def test_an_svg_is_preferred_to_a_png_whatever_the_size(tmp_path: Path) -> None:
    base = tmp_path / "icons"
    write_theme(
        base,
        "Mine",
        [
            Dir("18x18/apps", 18, "Fixed", {"a.png": png_bytes(18, 18, (255, 0, 0, 255))}),
            Dir("scalable/apps", 48, "Scalable", {"a.svg": svg("#00ff00")}),
        ],
    )
    icons, _ = service(tmp_path)
    got = icons.theme_icon("a", 18)  # the png is exactly 18 px; the svg still wins
    assert got is not None and got.startswith("<svg") and "#00ff00" in got


def test_the_png_nearest_above_the_size_is_chosen_else_the_largest(tmp_path: Path) -> None:
    base = tmp_path / "icons"
    sizes = {16: (1, 0, 0, 255), 32: (0, 2, 0, 255), 64: (0, 0, 3, 255)}
    write_theme(
        base,
        "Mine",
        [Dir(f"{s}x{s}/apps", s, "Fixed", {"p.png": png_bytes(s, s, c)}) for s, c in sizes.items()],
    )
    icons, pixels = service(tmp_path)

    def colour(size: int) -> tuple[int, ...]:
        ref = icons.theme_icon("p", size)
        assert ref is not None and ref.startswith("pixels:")
        return pixels.colour(ref)

    assert colour(16) == (1, 0, 0, 255)  # exact
    assert colour(17) == (0, 2, 0, 255)  # nearest above
    assert colour(24) == (0, 2, 0, 255)
    assert colour(33) == (0, 0, 3, 255)
    assert colour(100) == (0, 0, 3, 255)  # nothing above: the largest
    assert colour(1) == (1, 0, 0, 255)


def test_an_items_icon_theme_path_is_looked_in_first_flat_or_as_a_theme_folder(
    tmp_path: Path,
) -> None:
    base = tmp_path / "icons"
    write_theme(base, "Mine", [Dir("scalable/apps", 48, "Scalable", {"x.svg": svg("#111111")})])
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "x.png").write_bytes(png_bytes(8, 8, (9, 9, 9, 255)))
    (flat / "y.svg").write_text(svg("#222222"))
    own = tmp_path / "own"
    write_theme(
        own,
        "hicolor",
        [Dir("24x24/apps", 24, "Fixed", {"z.png": png_bytes(24, 24, (7, 7, 7, 255))})],
    )
    icons, pixels = service(tmp_path)
    ref = icons.theme_icon("x", 18, str(flat))
    assert ref is not None and pixels.colour(ref) == (9, 9, 9, 255)  # the item's folder wins
    assert icons.theme_icon("x", 18) == svg("#111111")  # without it, the theme
    assert icons.theme_icon("y", 18, str(flat)) == svg("#222222")
    ref = icons.theme_icon("z", 18, str(own))  # a folder with a hicolor inside
    assert ref is not None and pixels.colour(ref) == (7, 7, 7, 255)
    assert icons.theme_icon("y", 18) is None  # not in the theme: the path was the only place


def test_an_absolute_path_is_read_as_it_is(tmp_path: Path) -> None:
    (tmp_path / "abs.svg").write_text(svg("#333333"))
    icons, _ = service(tmp_path)
    assert icons.theme_icon(str(tmp_path / "abs.svg"), 18) == svg("#333333")
    assert icons.theme_icon(str(tmp_path / "missing.svg"), 18) is None


def test_pixmaps_pixmaps_pixmaps_the_argb32_bytes_become_rgba_and_the_size_is_chosen(
    tmp_path: Path,
) -> None:
    icons, pixels = service(tmp_path)
    # one pixel A=0x80 R=1 G=2 B=3, network byte order
    small = [2, 1, bytes([0x80, 1, 2, 3, 0xFF, 10, 20, 30])]
    big = [2, 2, bytes([0xFF, 4, 5, 6]) * 4]
    ref = icons.pixmap_icon([small], 18)
    assert ref is not None and pixels.table[ref] == (2, 1, bytes([1, 2, 3, 0x80, 10, 20, 30, 0xFF]))
    assert argb_to_rgba(bytes([0x11, 0x22, 0x33, 0x44])) == bytes([0x22, 0x33, 0x44, 0x11])
    # the entry nearest above the size; the largest when none is above
    a, b = [16, 16, bytes([255, 1, 1, 1]) * 256], [32, 32, bytes([255, 2, 2, 2]) * 1024]
    assert pixels.table[icons.pixmap_icon([b, a], 18) or ""][:2] == (32, 32)
    assert pixels.table[icons.pixmap_icon([a, b], 16) or ""][:2] == (16, 16)
    assert pixels.table[icons.pixmap_icon([a, b], 99) or ""][:2] == (32, 32)
    assert icons.pixmap_icon([big], 2) is not None
    assert icons.pixmap_icon([], 18) is None


def test_a_pixmap_of_the_wrong_length_is_ignored_with_one_warning_naming_the_item(
    tmp_path: Path,
) -> None:
    icons, _ = service(tmp_path)
    lines: list[str] = []
    sink = logger.add(lines.append, level="WARNING", format="{message}")
    try:
        bad = [4, 4, b"\x00" * 10]
        assert icons.pixmap_icon([bad], 18, "org.kde.item-1/StatusNotifierItem") is None
        assert icons.pixmap_icon([bad], 18, "org.kde.item-1/StatusNotifierItem") is None
        good = [1, 1, bytes([255, 1, 2, 3])]
        assert icons.pixmap_icon([bad, good], 18, "x") is not None  # the usable one is used
    finally:
        logger.remove(sink)
    warned = [x for x in lines if "org.kde.item-1" in x]
    assert len(warned) == 1 and "4x4" in warned[0]


def test_a_second_lookup_reads_no_folder_and_decodes_nothing(tmp_path: Path) -> None:
    base = tmp_path / "icons"
    files = {f"icon{i}.png": png_bytes(16, 16, (i % 255, 0, 0, 255)) for i in range(60)}
    write_theme(base, "Mine", [Dir("16x16/apps", 16, "Fixed", files)])
    icons, _ = service(tmp_path)
    first = icons.theme_icon("icon3", 16)
    reads, decodes = icons.stats.folder_reads, icons.stats.decodes
    assert reads > 0 and decodes == 1
    assert icons.theme_icon("icon3", 16) == first
    assert (icons.stats.hits, icons.stats.decodes) == (1, 1)
    for i in range(4, 40):  # other names of the same chain: the index answers, no folder is read
        assert icons.theme_icon(f"icon{i}", 16) is not None
    assert icons.stats.folder_reads == reads


def test_a_changed_file_is_noticed_by_its_modification_time_and_the_theme_can_be_forgotten(
    tmp_path: Path,
) -> None:
    base = tmp_path / "icons"
    root = write_theme(
        base, "Mine", [Dir("scalable/apps", 48, "Scalable", {"c.svg": svg("#aa0000")})]
    )
    icons, _ = service(tmp_path)
    assert icons.theme_icon("c", 18) == svg("#aa0000")
    target = root / "scalable/apps/c.svg"
    target.write_text(svg("#00bb00"))
    stat = target.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    assert icons.theme_icon("c", 18) == svg("#00bb00")  # the cache entry is stale: read again
    (root / "scalable/apps/new.svg").write_text(svg("#0000cc"))
    assert icons.theme_icon("new", 18) is None  # the index is not read again by itself
    icons.invalidate()
    assert icons.theme_icon("new", 18) == svg("#0000cc")
    target.unlink()  # a file that went: a lookup gives what the theme has now
    assert icons.theme_icon("c", 18) is None


def test_the_theme_name_comes_from_kdeglobals_else_hicolor(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    assert desktop_theme(config) == "hicolor"
    (config / "kdeglobals").write_text("[General]\nx=1\n\n[Icons]\nTheme=breeze-dark\n")
    assert desktop_theme(config) == "breeze-dark"
    pixels = Pixels()
    icons = IconService(
        pixels.register, bases=[tmp_path / "icons"], pixmaps=None, config_home=config
    )
    assert icons.theme == "breeze-dark"
    icons.set_theme("Other")
    assert icons.theme == "Other"


def test_the_search_folders_follow_the_xdg_variables() -> None:
    env = {"HOME": "/home/u", "XDG_DATA_HOME": "/data", "XDG_DATA_DIRS": "/a:/b"}
    assert [str(p) for p in default_bases(env)] == [
        "/data/icons",
        "/home/u/.icons",
        "/a/icons",
        "/b/icons",
    ]
    assert str(default_bases({"HOME": "/h"})[0]) == "/h/.local/share/icons"


def test_a_png_that_cannot_be_decoded_is_none_with_one_warning(tmp_path: Path) -> None:
    base = tmp_path / "icons"
    write_theme(base, "Mine", [Dir("16x16/apps", 16, "Fixed", {"bad.png": b"not a png"})])
    icons, _ = service(tmp_path)
    lines: list[str] = []
    sink = logger.add(lines.append, level="WARNING", format="{message}")
    try:
        assert icons.theme_icon("bad", 16) is None
        assert icons.theme_icon("bad", 16) is None
    finally:
        logger.remove(sink)
    assert len([x for x in lines if "bad.png" in x]) == 1


def test_the_index_of_a_theme_chain_is_built_in_under_100_ms(tmp_path: Path) -> None:
    """Tray Module > Performance Budget: a chain of three themes with 6 directories and 120 icons
    each, indexed once."""
    base = tmp_path / "icons"
    for name, inherits in (("Mine", ["Mid"]), ("Mid", ["hicolor"]), ("hicolor", [])):
        dirs = [
            Dir(f"{s}x{s}/apps", s, "Fixed", {f"{name}-{i}.png": b"x" for i in range(120)})
            for s in (16, 22, 24, 32, 48, 64)
        ]
        write_theme(base, name, dirs, inherits=inherits)
    icons, _ = service(tmp_path)
    started = time.perf_counter()
    icons.theme_icon("nothing", 18)
    took = (time.perf_counter() - started) * 1000
    print(f"\nicon index of 3 themes x 6 dirs x 120 files: {took:.1f} ms")
    assert took < 100 and len(icons.stats.index_ms) == 1
    assert icons.stats.folder_reads == 18


def test_a_module_gets_only_the_three_lookups(tmp_path: Path) -> None:
    icons, _ = service(tmp_path)
    helper = icons.for_module("Tray")
    public = {n for n in dir(helper) if not n.startswith("_")}
    assert public == {"theme_icon", "pixmap_icon", "png_icon"}
    with pytest.raises(AttributeError):
        helper.invalidate  # type: ignore[attr-defined]  # noqa: B018
