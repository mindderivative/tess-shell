"""The shell's own icon lookup (Tray Module > Icons; Tasks and the launcher use it too).

``IconService`` finds an icon by its freedesktop name as the Icon Theme Specification says: the
folders ``$XDG_DATA_HOME/icons``, ``~/.icons`` and each ``$XDG_DATA_DIRS/icons``; a theme is a
folder with an ``index.theme`` that lists its directories (with their sizes and kinds) and the
themes it ``Inherits``; ``hicolor`` is always the last theme, and ``/usr/share/pixmaps`` after it. A
scalable SVG is preferred; otherwise the png whose size is nearest above the size wanted.

What comes out is a *reference* a block's ``Icon:`` accepts (``ModuleIcons``): an SVG document, or
the name of decoded pixels. The shell reads the files and decodes a png itself with ``tess_utils``;
tre is given pixels or a document, never a path (AGENTS, Layering Principle). The pixels go to the
registry the binder reads (``register`` is handed in: ``services`` import nothing from the binder).

Every folder of a theme chain is read once, when a lookup first needs that chain (the index); a
lookup after that reads no folder, only ``stat`` of the file it found, whose modification time is
part of the cache entry. Nothing polls: a file that changed is noticed by that stat, a theme that
changed by :meth:`IconService.invalidate`. Thread safe; the calls block on files, so a caller on the
loop thread must use a worker (the Tray does).
"""

from __future__ import annotations

import configparser
import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from tess_shell._vendor import tess_utils
from tess_shell.services.api import ModuleIcons

Register = Callable[[int, int, bytes], str]  # (width, height, RGBA) -> a reference to the pixels
MAX_SIDE = 1024  # an icon larger than this in either side is refused
MAX_SVG = 2 * 1024 * 1024  # an SVG larger than this is not read
MAX_FILE = 16 * 1024 * 1024  # a png larger than this is not read
HICOLOR = "hicolor"
PIXMAPS = Path("/usr/share/pixmaps")
SUFFIXES = (".svg", ".png")  # what a flat folder is searched for, in this order


@dataclass(frozen=True, slots=True)
class _Dir:
    """One directory of a theme (a section of ``index.theme``): its sizes."""

    size: int
    kind: str  # Fixed, Scalable or Threshold
    low: int  # the smallest size it serves (Scalable: MinSize)
    high: int  # the largest size it serves (Scalable: MaxSize)
    scale: int

    @property
    def pixels(self) -> int:
        return self.size * self.scale


@dataclass(frozen=True, slots=True)
class _Hit:
    path: str
    svg: bool
    directory: _Dir


class _Theme:
    """One theme in one set of base folders: its inherited themes and, once indexed, where each
    icon name is."""

    __slots__ = ("icons", "inherits", "name", "present")

    def __init__(self, name: str) -> None:
        self.name = name
        self.present = False  # some base folder has this theme's index.theme
        self.inherits: list[str] = []
        self.icons: dict[str, list[_Hit]] = {}


def _int(parser: configparser.RawConfigParser, section: str, key: str, default: int) -> int:
    try:
        return parser.getint(section, key, fallback=default)
    except ValueError:
        return default


def _dirs_of(parser: configparser.RawConfigParser) -> dict[str, _Dir]:
    """The directories an ``index.theme`` lists, with their kinds and sizes."""
    listed: list[str] = []
    if parser.has_section("Icon Theme"):
        for key in ("Directories", "ScaledDirectories"):
            listed += [d.strip() for d in parser.get("Icon Theme", key, fallback="").split(",")]
    out: dict[str, _Dir] = {}
    for name in listed:
        if not name or not parser.has_section(name):
            continue
        size = _int(parser, name, "Size", 0)
        if size <= 0:
            continue
        kind = parser.get(name, "Type", fallback="Threshold")
        if kind == "Scalable":
            low, high = _int(parser, name, "MinSize", size), _int(parser, name, "MaxSize", size)
        elif kind == "Fixed":
            low = high = size
        else:
            kind = "Threshold"
            threshold = _int(parser, name, "Threshold", 2)
            low, high = size - threshold, size + threshold
        out[name] = _Dir(size, kind, low, high, max(_int(parser, name, "Scale", 1), 1))
    return out


def _read_index(path: Path) -> configparser.RawConfigParser | None:
    parser = configparser.RawConfigParser(strict=False, interpolation=None)
    parser.optionxform = str  # type: ignore[assignment,method-assign]  # keys are case sensitive
    try:
        parser.read_string(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error) as exc:
        logger.debug(f"icons: cannot read {path} ({exc})")
        return None
    return parser


def desktop_theme(config_home: Path) -> str:
    """The user's icon theme: ``kdeglobals`` ``[Icons] Theme``, else ``hicolor`` (Tray Module,
    open question 6; the Settings portal offers no icon theme as far as it was read)."""
    parser = _read_index(config_home / "kdeglobals")
    if parser is not None and parser.has_section("Icons"):
        name = parser.get("Icons", "Theme", fallback="").strip()
        if name:
            return name
    return HICOLOR


def default_bases(env: Mapping[str, str] | None = None) -> list[Path]:
    """The folders themes live in, in the specification's order."""
    env = os.environ if env is None else env
    home = Path(env.get("HOME", "~")).expanduser()
    data_home = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    dirs = (env.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    out = [data_home / "icons", home / ".icons", *(Path(d) / "icons" for d in dirs if d)]
    return list(dict.fromkeys(out))


@dataclass(slots=True)
class _Cached:
    ref: str
    path: str
    mtime: int


@dataclass(slots=True)
class Stats:
    """What the service did (the measurements and the tests)."""

    folder_reads: int = 0  # directories listed
    index_builds: int = 0  # themes indexed
    index_ms: list[float] = field(default_factory=list)  # milliseconds of each theme chain built
    hits: int = 0  # lookups answered from the cache
    decodes: int = 0  # png files decoded


class IconService:
    def __init__(
        self,
        register: Register,
        *,
        theme: str | None = None,
        bases: Sequence[Path] | None = None,
        pixmaps: Path | None = PIXMAPS,
        config_home: Path | None = None,
    ) -> None:
        self._register = register
        self._theme = theme
        self._bases = list(bases) if bases is not None else default_bases()
        self._pixmaps = pixmaps
        env = os.environ
        self._config_home = config_home or Path(
            env.get("XDG_CONFIG_HOME") or Path(env.get("HOME", "~")).expanduser() / ".config"
        )
        self._lock = threading.RLock()
        self._themes: dict[tuple[str, tuple[Path, ...]], _Theme] = {}
        self._cache: dict[tuple[str, int, str], _Cached] = {}
        self._pixmap_refs: dict[bytes, str] = {}
        self._warned: set[str] = set()
        self.stats = Stats()

    def for_module(self, module: str) -> ModuleIcons:
        """The helper for one module (``ctx.icons``)."""
        return _ModuleIcons(self)

    # -- the theme ------------------------------------------------------------------------------

    @property
    def theme(self) -> str:
        """The user's icon theme name (read once, from ``kdeglobals``)."""
        with self._lock:
            if self._theme is None:
                self._theme = desktop_theme(self._config_home)
            return self._theme

    def set_theme(self, name: str) -> None:
        """The user changed the theme: forget every index and result."""
        with self._lock:
            self._theme = name
            self.invalidate()

    def invalidate(self) -> None:
        """Forget every index and every cached result: the next lookup reads the folders again."""
        with self._lock:
            self._themes.clear()
            self._cache.clear()

    # -- the lookup -----------------------------------------------------------------------------

    def theme_icon(self, name: str, size: int, theme_path: str | None = None) -> str | None:
        if not name:
            return None
        key = (name, size, theme_path or "")
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                if self._unchanged(cached):
                    self.stats.hits += 1
                    return cached.ref
                del self._cache[key]  # the file changed (or went): look again, indexes included
                self._themes.clear()
            found = self._find(name, size, theme_path)
            if found is None:
                return None
            ref, path, mtime = found
            self._cache[key] = _Cached(ref, path, mtime)
            return ref

    @staticmethod
    def _unchanged(cached: _Cached) -> bool:
        try:
            return os.stat(cached.path).st_mtime_ns == cached.mtime
        except OSError:
            return False

    def _find(self, name: str, size: int, theme_path: str | None) -> tuple[str, str, int] | None:
        if name.startswith("/"):
            return self._load(name)
        if theme_path:
            base = Path(theme_path)
            path = self._flat(base, name)
            if path is None:
                path = self._themed(name, size, (base,))
            found = self._load(path) if path is not None else None
            if found is not None:
                return found
        path = self._themed(name, size, tuple(self._bases))
        if path is None and self._pixmaps is not None:
            path = self._flat(self._pixmaps, name)
        return self._load(path) if path is not None else None

    @staticmethod
    def _flat(folder: Path, name: str) -> str | None:
        """``folder/name.svg`` or ``folder/name.png``: a folder of icons with no theme layout."""
        for suffix in SUFFIXES:
            candidate = folder / f"{name}{suffix}"
            if candidate.is_file():
                return str(candidate)
        return None

    def _themed(self, name: str, size: int, bases: tuple[Path, ...]) -> str | None:
        for theme in self._chain(bases):
            hits = theme.icons.get(name)
            if hits:
                return _best(hits, size)
        return None

    def _chain(self, bases: tuple[Path, ...]) -> list[_Theme]:
        """The user's theme, the themes it inherits (depth first) and ``hicolor``, indexed."""
        started = time.perf_counter()
        before = self.stats.index_builds
        out: list[_Theme] = []
        seen: set[str] = set()

        def visit(name: str) -> None:
            if name in seen:
                return
            seen.add(name)
            theme = self._index(name, bases)
            if theme.present:
                out.append(theme)
            for parent in theme.inherits:
                visit(parent)

        visit(self.theme)
        visit(HICOLOR)
        if self.stats.index_builds != before:
            self.stats.index_ms.append((time.perf_counter() - started) * 1000)
        return out

    def _index(self, name: str, bases: tuple[Path, ...]) -> _Theme:
        key = (name, bases)
        theme = self._themes.get(key)
        if theme is not None:
            return theme
        theme = self._themes[key] = _Theme(name)
        self.stats.index_builds += 1
        roots = [b / name for b in bases if (b / name / "index.theme").is_file()]
        if not roots:
            return theme
        theme.present = True
        parser = _read_index(roots[0] / "index.theme")
        if parser is None:
            return theme
        if parser.has_section("Icon Theme"):
            theme.inherits = [
                p.strip() for p in parser.get("Icon Theme", "Inherits", fallback="").split(",")
            ]
            theme.inherits = [p for p in theme.inherits if p]
        for sub, directory in _dirs_of(parser).items():
            for root in roots:
                self._scan(theme, root / sub, directory)
        return theme

    def _scan(self, theme: _Theme, folder: Path, directory: _Dir) -> None:
        self.stats.folder_reads += 1
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            stem, dot, suffix = entry.name.rpartition(".")
            if not dot or suffix not in ("svg", "png"):
                continue
            theme.icons.setdefault(stem, []).append(_Hit(entry.path, suffix == "svg", directory))

    # -- reading what was found -----------------------------------------------------------------

    def _load(self, path: str) -> tuple[str, str, int] | None:
        """The reference of the icon file ``path``, its path and its modification time."""
        try:
            stat = os.stat(path)
            if path.endswith(".svg"):
                if stat.st_size > MAX_SVG:
                    return self._refuse(path, f"the SVG is {stat.st_size} bytes")
                text = Path(path).read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
                if not text.lstrip().startswith("<"):
                    return self._refuse(path, "not an SVG document")
                return text.lstrip(), path, stat.st_mtime_ns
            if stat.st_size > MAX_FILE:
                return self._refuse(path, f"the file is {stat.st_size} bytes")
            ref = self.png_icon(Path(path).read_bytes(), path)
        except OSError as exc:
            return self._refuse(path, str(exc))
        return (ref, path, stat.st_mtime_ns) if ref is not None else None

    def _refuse(self, path: str, why: str) -> tuple[str, str, int] | None:
        self._warn(f"file:{path}", f"icon {path}: {why}; it is not used")
        return None

    def _warn(self, key: str, message: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            logger.warning(message)

    def png_icon(self, data: bytes, source: str = "") -> str | None:
        try:
            width, height, rgba = tess_utils.decode_image(data, MAX_SIDE)
        except (ValueError, OSError) as exc:
            self._warn(f"png:{source}", f"icon {source or '(data)'}: cannot decode it ({exc})")
            return None
        self.stats.decodes += 1
        return self._register(width, height, rgba)

    def pixmap_icon(
        self, pixmaps: Sequence[Sequence[Any]], size: int, source: str = ""
    ) -> str | None:
        usable: list[tuple[int, int, bytes]] = []
        for entry in pixmaps:
            try:
                width, height, data = int(entry[0]), int(entry[1]), bytes(entry[2])
            except IndexError, TypeError, ValueError:
                continue
            if width <= 0 or height <= 0 or len(data) != width * height * 4:
                self._warn(
                    f"pixmap:{source}:{width}x{height}",
                    f"{source or 'an item'}: a {width}x{height} pixmap has {len(data)} bytes, not "
                    f"{width * height * 4}; it is ignored",
                )
                continue
            usable.append((width, height, data))
        if not usable:
            return None
        above = [p for p in usable if max(p[0], p[1]) >= size]
        width, height, data = (
            min(above, key=lambda p: max(p[0], p[1]))
            if above
            else max(usable, key=lambda p: max(p[0], p[1]))
        )
        ref = self._pixmap_refs.get(data)
        if ref is None:
            ref = self._register(width, height, argb_to_rgba(data))
            if len(self._pixmap_refs) >= 256:
                self._pixmap_refs.clear()
            self._pixmap_refs[data] = ref
        return ref


def argb_to_rgba(data: bytes) -> bytes:
    """ARGB32 in network byte order (bytes ``A R G B`` per pixel) to the engine's RGBA."""
    out = bytearray(len(data))
    out[0::4] = data[1::4]
    out[1::4] = data[2::4]
    out[2::4] = data[3::4]
    out[3::4] = data[0::4]
    return bytes(out)


def _distance(directory: _Dir, size: int) -> int:
    """How far ``size`` is from what ``directory`` serves (0 when it serves it)."""
    if directory.low <= size <= directory.high:
        return 0
    return directory.low - size if size < directory.low else size - directory.high


def _best(hits: Sequence[_Hit], size: int) -> str:
    """The SVG that serves ``size`` best; with no SVG the png whose size is nearest above it (else
    the largest below it)."""
    svgs = [h for h in hits if h.svg]
    if svgs:
        return min(svgs, key=lambda h: _distance(h.directory, size)).path
    above = [h for h in hits if h.directory.pixels >= size]
    if above:
        return min(above, key=lambda h: h.directory.pixels).path
    return max(hits, key=lambda h: h.directory.pixels).path


class _ModuleIcons:
    """``ctx.icons`` of one module: the three lookups and nothing of the service's internals."""

    def __init__(self, service: IconService) -> None:
        self._service = service

    def theme_icon(self, name: str, size: int, theme_path: str | None = None) -> str | None:
        return self._service.theme_icon(name, size, theme_path)

    def pixmap_icon(
        self, pixmaps: Sequence[Sequence[Any]], size: int, source: str = ""
    ) -> str | None:
        return self._service.pixmap_icon(pixmaps, size, source)

    def png_icon(self, data: bytes, source: str = "") -> str | None:
        return self._service.png_icon(data, source)
