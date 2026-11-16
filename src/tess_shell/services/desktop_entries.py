"""The desktop-entry index (Applications Module > The Application Index; Tasks Module > Icons).

One index of the ``.desktop`` files of the ``applications`` folders, read as the Desktop Entry
Specification says. Two users share it: the icon service (``ctx.icons.app_icon``: an application's
icon from its desktop file name) and, in M6, the launcher (``ctx.apps``).

* Where: ``$XDG_DATA_HOME/applications`` (default ``~/.local/share``) and the ``applications``
  folder of each ``$XDG_DATA_DIRS`` entry (default ``/usr/local/share:/usr/share``), sub-folders
  included. An entry's id is its path below that folder with ``/`` replaced by ``-``. The first
  folder that has an id wins, also when it is ``Hidden`` (that is how a user deletes an entry the
  system ships).
* What is kept: every ``Type=Application`` entry that parses, ``NoDisplay`` and ``Hidden`` ones too,
  because a window whose application is ``NoDisplay`` still needs its icon. :meth:`applications`
  is the launcher's view: not ``Hidden``, not ``NoDisplay``, passing ``OnlyShowIn`` and
  ``NotShowIn`` against ``XDG_CURRENT_DESKTOP``, and with ``TryExec`` found on the path.
* Localised keys (``Name[de]``) follow the locale of ``LC_ALL``, ``LC_MESSAGES``, ``LANG``, in the
  specification's order: ``lang_COUNTRY@MODIFIER``, ``lang_COUNTRY``, ``lang@MODIFIER``, ``lang``.
* When: the folders are read on the first use and the result kept. The first use blocks on files:
  call from a worker or the ``dbus`` thread, never the loop thread. :meth:`watch` follows the
  folders with inotify (the file watcher the shell's files use) and forgets the index 500 ms after
  the last change; the next use reads it again.
* A broken entry is skipped with one debug line naming the file; it never stops the index.

Safety: a process that is a test (``PYTEST_CURRENT_TEST``) never reads a folder under the real home
unless the caller named it, so a test that forgot to point ``XDG_DATA_HOME`` at a temporary folder
reads nothing of the user's.
"""

from __future__ import annotations

import os
import shutil
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

DEFAULT_DATA_DIRS = "/usr/local/share:/usr/share"
DEBOUNCE = 0.5  # seconds of quiet before a change of the folders makes the index stale
_ESCAPES = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}


class EntryError(ValueError):
    """A ``.desktop`` file that is not an application the index can use (the reason in text)."""


@dataclass(frozen=True, slots=True)
class DesktopEntry:
    """One application, with the keys the shell reads."""

    id: str  # ``org.kde.dolphin.desktop``: the path below the folder, ``/`` as ``-``
    path: Path
    name: str
    generic_name: str
    comment: str
    keywords: tuple[str, ...]
    icon: str
    exec: str
    terminal: bool
    working_dir: str  # ``Path``
    startup_wm_class: str
    try_exec: str
    categories: tuple[str, ...]
    no_display: bool
    hidden: bool
    only_show_in: tuple[str, ...]
    not_show_in: tuple[str, ...]

    @property
    def app(self) -> str:
        """The id without ``.desktop`` (what KWin reports as ``desktopFileName``)."""
        return self.id.removesuffix(".desktop")

    def shown(self, desktops: Sequence[str], which: Callable[[str], str | None]) -> bool:
        """Does the launcher list this entry on a desktop named ``desktops`` (the entries of
        ``XDG_CURRENT_DESKTOP``)? ``which`` finds a program on the path (``TryExec``)."""
        if self.hidden or self.no_display:
            return False
        if self.only_show_in and not any(d in self.only_show_in for d in desktops):
            return False
        if any(d in self.not_show_in for d in desktops):
            return False
        return not (self.try_exec and which(self.try_exec) is None)


# -- reading one file -------------------------------------------------------------------------


def unescape(value: str) -> str:
    """A ``string`` value: ``\\s`` ``\\n`` ``\\t`` ``\\r`` ``\\\\`` are replaced; any other
    backslash sequence is kept as written (the specification leaves it undefined)."""
    if "\\" not in value:
        return value
    out: list[str] = []
    i = 0
    while i < len(value):
        char = value[i]
        if char == "\\" and i + 1 < len(value) and value[i + 1] in _ESCAPES:
            out.append(_ESCAPES[value[i + 1]])
            i += 2
        else:
            out.append(char)
            i += 1
    return "".join(out)


def split_list(value: str) -> tuple[str, ...]:
    """A ``strings`` value: items separated by ``;``, a literal ``;`` written ``\\;``, a trailing
    ``;`` allowed, empty items dropped."""
    items: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(value):
        char = value[i]
        if char == "\\" and i + 1 < len(value) and value[i + 1] == ";":
            current.append(";")
            i += 2
        elif char == ";":
            items.append("".join(current))
            current = []
            i += 1
        else:
            current.append(char)
            i += 1
    items.append("".join(current))
    return tuple(unescape(item) for item in items if item)


def locale_candidates(locale: str) -> tuple[str, ...]:
    """The localised-key suffixes to try for ``locale`` (``de_AT.UTF-8@euro``), best first. The
    encoding is dropped; ``C`` and ``POSIX`` have none."""
    if not locale or locale in ("C", "POSIX"):
        return ()
    rest, _, modifier = locale.partition("@")
    rest = rest.partition(".")[0]
    lang, _, country = rest.partition("_")
    if not lang:
        return ()
    out: list[str] = []
    if country and modifier:
        out.append(f"{lang}_{country}@{modifier}")
    if country:
        out.append(f"{lang}_{country}")
    if modifier:
        out.append(f"{lang}@{modifier}")
    out.append(lang)
    return tuple(out)


def environment_locale(env: Mapping[str, str]) -> str:
    """The locale messages are shown in: ``LC_ALL``, ``LC_MESSAGES``, then ``LANG``."""
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(name, "")
        if value:
            return value
    return ""


def read_group(text: str) -> dict[str, str]:
    """The ``[Desktop Entry]`` group as written: key (with its ``[locale]``) to raw value. Raises
    :class:`EntryError` when the file has no such group."""
    keys: dict[str, str] = {}
    inside = False
    seen = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise EntryError(f"a group header is not closed: {line[:40]!r}")
            inside = line[1:-1] == "Desktop Entry"
            seen = seen or inside
            continue
        if not inside:
            continue
        key, equals, value = line.partition("=")
        if not equals:
            raise EntryError(f"a line is not Key=Value: {line[:40]!r}")
        key = key.strip()
        if key and key not in keys:  # a repeated key: the first stands
            keys[key] = value.strip()
    if not seen:
        raise EntryError("no [Desktop Entry] group")
    return keys


def parse_entry(
    text: str, entry_id: str, path: Path, candidates: Sequence[str] = ()
) -> DesktopEntry:
    """One ``.desktop`` file as a :class:`DesktopEntry`. Raises :class:`EntryError` when it is not
    an application (no ``Type=Application``, no ``Name``) or not readable as the specification
    writes it."""
    keys = read_group(text)

    def raw(key: str) -> str | None:
        for locale in candidates:
            value = keys.get(f"{key}[{locale}]")
            if value is not None:
                return value
        return keys.get(key)

    def string(key: str) -> str:
        value = raw(key)
        return unescape(value) if value is not None else ""

    def strings(key: str) -> tuple[str, ...]:
        value = raw(key)
        return split_list(value) if value is not None else ()

    def flag(key: str) -> bool:
        return keys.get(key, "").lower() in ("true", "1")

    if keys.get("Type") != "Application":
        raise EntryError(f"Type is {keys.get('Type', 'missing')!r}, not Application")
    name = string("Name")
    if not name:
        raise EntryError("no Name")
    return DesktopEntry(
        id=entry_id,
        path=path,
        name=name,
        generic_name=string("GenericName"),
        comment=string("Comment"),
        keywords=strings("Keywords"),
        icon=string("Icon"),
        exec=string("Exec"),
        terminal=flag("Terminal"),
        working_dir=string("Path"),
        startup_wm_class=string("StartupWMClass"),
        try_exec=string("TryExec"),
        categories=strings("Categories"),
        no_display=flag("NoDisplay"),
        hidden=flag("Hidden"),
        only_show_in=strings("OnlyShowIn"),
        not_show_in=strings("NotShowIn"),
    )


# -- the index --------------------------------------------------------------------------------


def default_folders(env: Mapping[str, str] | None = None) -> list[Path]:
    """The ``applications`` folders, highest priority first."""
    env = os.environ if env is None else env
    home = Path(env.get("HOME") or "~").expanduser()
    data_home = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    dirs = (env.get("XDG_DATA_DIRS") or DEFAULT_DATA_DIRS).split(":")
    roots = [str(data_home), *dirs]
    return list(dict.fromkeys(Path(d) / "applications" for d in roots if d))


def _under_real_home(path: Path) -> bool:
    try:
        path.resolve().relative_to(Path(os.path.expanduser("~")).resolve())
    except ValueError:
        return False
    return True


class ApplicationIndex:
    """The index. ``folders`` (highest priority first) are given by a test; by default they come
    from the environment. ``desktops`` are the entries of ``XDG_CURRENT_DESKTOP``."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        folders: Sequence[Path] | None = None,
        locale: str | None = None,
        desktops: Sequence[str] | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        env = os.environ if env is None else env
        self.folders = list(folders) if folders is not None else default_folders(env)
        if folders is None and os.environ.get("PYTEST_CURRENT_TEST"):
            # a test that did not name its folders must not read the user's applications
            self.folders = [f for f in self.folders if not _under_real_home(f)]
        self._candidates = locale_candidates(
            locale if locale is not None else environment_locale(env)
        )
        current = env.get("XDG_CURRENT_DESKTOP", "") if desktops is None else ""
        self._desktops = (
            tuple(desktops) if desktops is not None else tuple(d for d in current.split(":") if d)
        )
        self._which = which
        self._lock = threading.RLock()
        self._entries: dict[str, DesktopEntry] | None = None  # None: not read (or stale)
        self._by_class: dict[str, DesktopEntry] = {}
        self._listeners: list[Callable[[], None]] = []
        self._stop_watch: Callable[[], None] | None = None
        self.scans = 0  # how many times the folders were read (the tests, the measurements)

    # -- reading ----------------------------------------------------------------------------

    def scan(self) -> None:
        """Read every folder now and keep the result (first use does it by itself)."""
        entries: dict[str, DesktopEntry] = {}
        for folder in self.folders:
            self._scan_folder(folder, entries)
        by_class: dict[str, DesktopEntry] = {}
        for entry in entries.values():
            if entry.startup_wm_class:
                by_class.setdefault(entry.startup_wm_class.lower(), entry)
        with self._lock:
            self._entries, self._by_class = entries, by_class
            self.scans += 1
        logger.debug(f"applications: {len(entries)} desktop entries in {len(self.folders)} folders")

    def _scan_folder(self, folder: Path, entries: dict[str, DesktopEntry]) -> None:
        if not folder.is_dir():
            return
        found: list[tuple[str, Path]] = []
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            base = Path(root)
            for name in sorted(files):
                if name.endswith(".desktop"):
                    path = base / name
                    entry_id = "-".join(path.relative_to(folder).parts)
                    found.append((entry_id, path))
        for entry_id, path in found:
            if entry_id in entries:  # a folder of higher priority has this id
                continue
            try:
                entries[entry_id] = parse_entry(
                    path.read_text(encoding="utf-8", errors="replace"),
                    entry_id,
                    path,
                    self._candidates,
                )
            except (OSError, EntryError) as exc:
                logger.debug(f"applications: skipped {path}: {exc}")

    def _read(self) -> dict[str, DesktopEntry]:
        with self._lock:
            entries = self._entries
        if entries is None:
            self.scan()
            with self._lock:
                entries = self._entries
        assert entries is not None
        return entries

    def invalidate(self) -> None:
        """Forget the index: the next use reads the folders again."""
        with self._lock:
            self._entries = None
            self._by_class = {}

    # -- asking -----------------------------------------------------------------------------

    def entries(self) -> list[DesktopEntry]:
        """Every application that parsed, in id order."""
        entries = self._read()
        return [entries[k] for k in sorted(entries)]

    def applications(self) -> list[DesktopEntry]:
        """The launcher's view: the entries the desktop lists (see the module's docstring)."""
        return [e for e in self.entries() if e.shown(self._desktops, self._which)]

    def get(self, app: str) -> DesktopEntry | None:
        """The entry for an id, with or without ``.desktop``, or ``None``. An exact id wins; a
        different case is accepted when it is unambiguous."""
        entries = self._read()
        wanted = app if app.endswith(".desktop") else f"{app}.desktop"
        found = entries.get(wanted)
        if found is not None:
            return found
        lower = wanted.lower()
        same = [e for k, e in entries.items() if k.lower() == lower]
        return same[0] if len(same) == 1 else None

    def for_window(self, app: str) -> DesktopEntry | None:
        """The entry of a window whose application is ``app``: the ``desktopFileName`` KWin
        reports, else its ``resourceClass``. An id first, then an entry whose ``StartupWMClass``
        is ``app`` (without regard to case)."""
        if not app:
            return None
        found = self.get(app)
        if found is not None:
            return found
        self._read()
        with self._lock:
            return self._by_class.get(app.lower())

    # -- following the folders --------------------------------------------------------------

    def on_changed(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Call ``callback`` (on the watcher's thread) after the folders changed and the index
        was forgotten; returns the function that stops it. Needs :meth:`watch`."""
        with self._lock:
            self._listeners.append(callback)

        def cancel() -> None:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)

        return cancel

    def watch(self, debounce: float = DEBOUNCE) -> None:
        """Follow the folders with inotify (one thread, no timer: it wakes on a file event only).
        A folder that does not exist yet is not watched."""
        from tess_shell.watch import Watcher

        if self._stop_watch is not None:
            return
        trees: Iterable[Path] = [f for f in self.folders if f.is_dir()]
        watcher = Watcher(trees, self._changed, debounce=debounce)
        watcher.start()
        self._stop_watch = watcher.stop

    def unwatch(self) -> None:
        stop, self._stop_watch = self._stop_watch, None
        if stop is not None:
            stop()

    def _changed(self, paths: set[Path]) -> None:
        if not any(p.name.endswith(".desktop") for p in paths):
            return
        self.invalidate()
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener()
            except Exception:
                logger.opt(exception=True).error("applications: a change listener raised")
