"""Notice changes to the shell's files (Hot Reload > How a Change is Noticed).

One thread blocks in ``select`` on the inotify descriptor and wakes only on a file event. Events
are coalesced: the callback gets the set of changed paths once, after ``debounce`` seconds with no
further event, so an editor's atomic save or a multi-file save is one reload. Close-write and
moved-to events on a directory are the signal (an atomic save ends in moved-to); names that start
with a dot or end in ``~``, ``.swp``, ``.tmp`` or ``.bak`` are ignored, and so are the ``schemas``,
``logs`` and ``backups`` folders. A path the shell wrote itself is dropped through ``is_own``.
"""

from __future__ import annotations

import select
import socket
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from inotify_simple import INotify, flags
from loguru import logger

IGNORED_ENDINGS = ("~", ".swp", ".tmp", ".bak")
IGNORED_DIRS = frozenset({"schemas", "logs", "backups"})
_FILE_MASK = flags.CLOSE_WRITE | flags.MOVED_TO | flags.MOVED_FROM | flags.DELETE
_DIR_MASK = _FILE_MASK | flags.CREATE


def ignored(name: str) -> bool:
    return name.startswith(".") or name.endswith(IGNORED_ENDINGS)


class Watcher:
    def __init__(
        self,
        trees: Iterable[Path],
        on_change: Callable[[set[Path]], None],
        *,
        files: Mapping[Path, frozenset[str]] | None = None,
        debounce: float = 0.2,
        is_own: Callable[[Path], bool] | None = None,
    ) -> None:
        """``trees`` are watched with everything below them; ``files`` maps a directory to the only
        names in it that count (the config directory holds ``settings.tdl`` and much else)."""
        self._trees = [t for t in trees]
        self._files = dict(files or {})
        self._on_change = on_change
        self._debounce = debounce
        self._is_own = is_own or (lambda _: False)
        self._inotify = INotify()
        self._dirs: dict[int, Path] = {}
        self._only: dict[int, frozenset[str]] = {}
        self._wake_r, self._wake_w = socket.socketpair()
        self._thread = threading.Thread(target=self._run, name="file-watcher", daemon=True)
        self.ok = True  # false when a watch could not be added (the limit): no automatic reload

    # -- watches ------------------------------------------------------------------------------

    def _watch(self, directory: Path, mask: int, only: frozenset[str] | None = None) -> None:
        try:
            wd = self._inotify.add_watch(str(directory), mask)
        except OSError as exc:
            self.ok = False
            logger.warning(f"cannot watch {directory}: {exc.strerror}; hot reload is off for it")
            return
        self._dirs[wd] = directory
        if only is not None:
            self._only[wd] = only

    def _watch_tree(self, root: Path) -> None:
        if not root.is_dir():
            return
        self._watch(root, _DIR_MASK)
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name not in IGNORED_DIRS and not child.name.startswith("."):
                self._watch_tree(child)

    def start(self) -> None:
        for tree in self._trees:
            self._watch_tree(tree)
        for directory, names in self._files.items():
            if directory.is_dir():
                self._watch(directory, _FILE_MASK, names)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._wake_w.send(b"x")
        except OSError:
            pass
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        self._inotify.close()
        self._wake_r.close()
        self._wake_w.close()

    # -- the thread ---------------------------------------------------------------------------

    def _collect(self, pending: set[Path]) -> None:
        for event in self._inotify.read(timeout=0):
            directory = self._dirs.get(event.wd)
            if directory is None or not event.name:
                continue
            path = directory / event.name
            if event.mask & flags.ISDIR:
                if event.mask & flags.CREATE and event.name not in IGNORED_DIRS:
                    self._watch_tree(path)
                    pending.update(
                        p for p in path.rglob("*") if p.is_file() and not ignored(p.name)
                    )
                continue
            if ignored(event.name):
                continue
            only = self._only.get(event.wd)
            if only is not None and event.name not in only:
                continue
            if event.mask & (flags.CLOSE_WRITE | flags.MOVED_TO | flags.MOVED_FROM | flags.DELETE):
                pending.add(path)

    def _run(self) -> None:
        pending: set[Path] = set()
        deadline: float | None = None
        while True:
            timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([self._inotify.fd, self._wake_r], [], [], timeout)
            if self._wake_r in ready:
                return
            if self._inotify.fd in ready:
                before = len(pending)
                try:
                    self._collect(pending)
                except OSError:
                    return
                if len(pending) != before or pending:
                    deadline = time.monotonic() + self._debounce
                continue
            # quiet for ``debounce``: deliver what is left after dropping the shell's own writes
            changed = {p for p in pending if not self._is_own(p)}
            pending.clear()
            deadline = None
            if changed:
                try:
                    self._on_change(changed)
                except Exception:
                    logger.opt(exception=True).error("the reload callback raised")


def hash_of(path: Path) -> str | None:
    """A content hash, or ``None`` if the file is gone; used to recognise the shell's own writes."""
    import hashlib

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class OwnWrites:
    """Remembers the hash of each file the shell wrote, so the watcher can drop the event that
    write causes. A change by anyone else has a different hash and passes."""

    def __init__(self) -> None:
        self._hashes: dict[Path, str] = {}
        self._lock = threading.Lock()

    def wrote(self, path: Path, content: bytes) -> None:
        import hashlib

        with self._lock:
            self._hashes[path.resolve()] = hashlib.sha256(content).hexdigest()

    def is_own(self, path: Path) -> bool:
        with self._lock:
            expected = self._hashes.get(path.resolve())
        return expected is not None and hash_of(path) == expected
