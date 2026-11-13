"""The D-Bus service thread and its two bus connections (D-Bus Service Layer > The Service Thread).

One thread named ``dbus`` runs one asyncio loop. Each of the two buses (session, system) is a
:class:`Bus` on that loop: a connection opened on first use, a registry of match rules (one rule
per distinct key however many subscribers), the owners of the well-known names that are watched,
and a reconnect with a back-off when the connection drops. Nothing here touches a node: a callback
on this thread hands its result to the loop thread (Process Model and Threading). No call is made
from the loop thread.

With a connected bus, subscriptions and no signal traffic nothing on this thread runs: there is no
timer in the layer, only the socket the loop waits on.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus
from loguru import logger

from tess_shell.services.api import (
    CALL_TIMEOUT,
    ServiceError,
    ServiceTimeout,
    ServiceUnavailable,
)

BUS_NAME = "org.freedesktop.DBus"
BUS_PATH = "/org/freedesktop/DBus"
BACKOFF = (1.0, 2.0, 4.0, 8.0, 16.0, 30.0)  # seconds; the last one repeats

# a call that fails like this means "nobody is there": the service's state is UNAVAILABLE
_UNAVAILABLE_ERRORS = frozenset(
    {
        "org.freedesktop.DBus.Error.ServiceUnknown",
        "org.freedesktop.DBus.Error.NameHasNoOwner",
        "org.freedesktop.DBus.Error.NoReply",
        "org.freedesktop.DBus.Error.Disconnected",
    }
)

BusKind = Literal["session", "system"]
Unsubscribe = Callable[[], None]
ReconnectHook = Callable[[MessageBus], Awaitable[None]]
OwnerCallback = Callable[[str | None, str | None], None]  # (old owner, new owner); None: no owner
PrefixCallback = Callable[[str, str | None, str | None], None]  # (name, old owner, new owner)
ReachCallback = Callable[[bool], None]  # the bus can (not) be reached


def unwrap(value: Any) -> Any:
    """Plain Python: a ``Variant`` is replaced by what it holds, at any depth."""
    if isinstance(value, Variant):
        return unwrap(value.value)
    if isinstance(value, list | tuple):
        return [unwrap(v) for v in value]
    if isinstance(value, dict):
        return {k: unwrap(v) for k, v in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class MatchKey:
    """What one match rule asks for. ``sender`` is a well-known name, a unique name or ``None``;
    ``arg0`` narrows on the first string argument (``PropertiesChanged``: the interface;
    ``NameOwnerChanged``: the name); ``arg0namespace`` on a first argument that is that name or
    a name under it (``org.mpris.MediaPlayer2`` takes ``org.mpris.MediaPlayer2.vlc``)."""

    sender: str | None
    path: str | None
    interface: str
    member: str
    arg0: str | None = None
    arg0namespace: str | None = None  # the first argument is this name or a name under it

    def rule(self) -> str:
        parts = ["type='signal'"]
        for field, value in (
            ("sender", self.sender),
            ("path", self.path),
            ("interface", self.interface),
            ("member", self.member),
            ("arg0", self.arg0),
            ("arg0namespace", self.arg0namespace),
        ):
            if value is not None:
                parts.append(f"{field}='{value}'")
        return ",".join(parts)


class _Sub:
    __slots__ = ("callback", "key")

    def __init__(self, key: MatchKey, callback: Callable[[Message], None]) -> None:
        self.key = key
        self.callback = callback


class _Name:
    """A watched well-known name: its owner now, and who wants to hear when it changes."""

    __slots__ = ("callbacks", "owner", "ready", "refs", "unsubscribe")

    def __init__(self) -> None:
        self.owner: str | None = None
        self.callbacks: list[OwnerCallback] = []
        self.unsubscribe: Unsubscribe | None = None
        self.refs = 0
        self.ready = asyncio.Event()  # set once the owner was read


class _Prefix:
    """A watch on every well-known name that starts with ``prefix``: the names with an owner now,
    and who wants to hear when one appears, goes or changes hands."""

    __slots__ = ("callbacks", "names", "prefix", "reach", "reachable", "ready", "unsubscribe")

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.names: dict[str, str] = {}  # name -> owner
        self.callbacks: list[PrefixCallback] = []
        self.reach: list[ReachCallback] = []
        self.reachable = False
        self.unsubscribe: Unsubscribe | None = None
        self.ready = asyncio.Event()


class Bus:
    """One bus connection. Every method runs on the service thread (coroutines and callbacks of
    its loop); the connection is made by the first call that needs it."""

    def __init__(self, kind: BusKind, address: str | None = None) -> None:
        self.kind = kind
        self._address = address
        self._conn: MessageBus | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._rules: dict[str, int] = {}  # rule string -> reference count
        self._subs: list[_Sub] = []
        self._names: dict[str, _Name] = {}
        self._prefixes: dict[str, _Prefix] = {}
        self._hooks: list[ReconnectHook] = []
        self._tasks: set[asyncio.Task[Any]] = set()
        self._reconnecting: asyncio.Task[None] | None = None
        self.connects = 0  # connections made so far (tests)
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep  # a test swaps it

    # -- state ----------------------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._conn is not None and self._conn.connected

    @property
    def rules(self) -> frozenset[str]:
        """The match rules the layer holds on the bus now (one entry per distinct rule)."""
        return frozenset(self._rules)

    def owner(self, name: str) -> str | None:
        """The unique name that owns the watched well-known ``name``, or ``None``."""
        watched = self._names.get(name)
        return watched.owner if watched is not None else None

    def on_reconnect(self, hook: ReconnectHook) -> Unsubscribe:
        """``await hook(connection)`` after every reconnect, once the match rules are back and the
        watched names are read again. This is where the owner of a bus name of the shell's own asks
        for it again (the shell owns no name yet: the control interface is not built)."""
        self._hooks.append(hook)

        def remove() -> None:
            if hook in self._hooks:
                self._hooks.remove(hook)

        return remove

    # -- connection -----------------------------------------------------------------------------

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _open(self) -> MessageBus:
        bus = (
            MessageBus(bus_address=self._address)
            if self._address
            else MessageBus(bus_type=BusType.SESSION if self.kind == "session" else BusType.SYSTEM)
        )
        conn = await asyncio.wait_for(bus.connect(), CALL_TIMEOUT)
        conn.add_message_handler(self._on_message)
        return conn

    def _wanted(self) -> bool:
        """Does anything depend on the connection staying up? Then a lost or unreachable bus is
        retried; otherwise the next call tries again."""
        return bool(self._rules or self._names or self._prefixes or self._hooks)

    async def connection(self) -> MessageBus:
        """The connection, opened now if it was never opened. Raises :class:`ServiceUnavailable`
        while the bus is not reachable (a retry with a back-off runs in the background when
        something depends on the bus)."""
        conn = self._conn
        if conn is not None and conn.connected:
            return conn
        async with self._lock:
            if self._conn is not None and self._conn.connected:
                return self._conn
            if self._reconnecting is not None and not self._reconnecting.done():
                raise ServiceUnavailable(f"{self.kind} bus", "not reachable; retrying")
            conn = None
            try:
                conn = await self._open()
                await self._adopt(conn)
            except Exception as exc:
                logger.debug(f"dbus: the {self.kind} bus is not reachable ({exc})")
                self._drop(conn)
                self._lost()
                raise ServiceUnavailable(f"{self.kind} bus", f"not reachable ({exc})") from exc
            return conn

    async def _adopt(self, conn: MessageBus) -> None:
        """A fresh connection: put every rule back, read the owners again, run the hooks."""
        first = self.connects == 0
        self._conn = conn
        self.connects += 1
        self._spawn(self._supervise(conn))
        logger.debug(f"dbus: connected to the {self.kind} bus")
        for rule in list(self._rules):
            await self._send_match(conn, "AddMatch", rule)
        for name, watched in list(self._names.items()):
            owner = await self._read_owner(conn, name)
            self._set_owner(name, watched, owner)
        for prefix in list(self._prefixes.values()):
            await self._list_prefix(conn, prefix)
        if not first:
            logger.info(f"dbus: the {self.kind} bus is back")
        for hook in list(self._hooks):
            try:
                await hook(conn)
            except Exception:
                logger.opt(exception=True).error(
                    f"dbus: a reconnect hook of the {self.kind} bus raised"
                )

    async def _supervise(self, conn: MessageBus) -> None:
        try:
            await conn.wait_for_disconnect()  # type: ignore[no-untyped-call]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug(f"dbus: the {self.kind} bus connection ended ({exc})")
        if self._closed or self._conn is not conn:
            return
        logger.warning(f"dbus: lost the {self.kind} bus; reconnecting")
        self._lost()

    def _lost(self) -> None:
        """No connection: every watched name has no owner now, and a reconnect starts if anything
        depends on the bus."""
        self._conn = None
        for name, watched in list(self._names.items()):
            self._set_owner(name, watched, None)
        for prefix in list(self._prefixes.values()):
            self._prefix_unreachable(prefix)
        if self._closed or not self._wanted():
            return
        if self._reconnecting is None or self._reconnecting.done():
            self._reconnecting = self._spawn(self._reconnect())

    async def _reconnect(self) -> None:
        attempt = 0
        while not self._closed:
            await self._sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
            attempt += 1
            conn: MessageBus | None = None
            try:
                async with self._lock:
                    conn = await self._open()
                    await self._adopt(conn)
                self._reconnecting = None
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._drop(conn)
                logger.debug(
                    f"dbus: the {self.kind} bus is still not reachable ({exc}); next in "
                    f"{BACKOFF[min(attempt, len(BACKOFF) - 1)]:g} s"
                )

    def _drop(self, conn: MessageBus | None) -> None:
        """Give up a connection that did not come up whole."""
        if conn is None:
            return
        if self._conn is conn:
            self._conn = None
        conn.disconnect()

    def close(self) -> None:
        self._closed = True
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.disconnect()

    # -- calls ----------------------------------------------------------------------------------

    async def call(
        self,
        destination: str,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: Sequence[Any] = (),
        *,
        timeout: float = CALL_TIMEOUT,
    ) -> list[Any]:
        """A method call; the reply's values, plain. Raises :class:`ServiceTimeout` after
        ``timeout`` seconds, :class:`ServiceUnavailable` when nobody owns ``destination`` (or the
        bus is gone) and :class:`ServiceError` for any other error the service sends."""
        conn = await asyncio.wait_for(self.connection(), timeout)
        message = Message(
            destination=destination,
            path=path,
            interface=interface,
            member=member,
            signature=signature,
            body=list(body),
        )
        try:
            reply = await asyncio.wait_for(conn.call(message), timeout)
        except TimeoutError as exc:
            raise ServiceTimeout(destination, f"no reply to {member} in {timeout:g} s") from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise ServiceUnavailable(
                destination, f"{self.kind} bus connection lost ({exc})"
            ) from exc
        if reply is not None and reply.message_type == MessageType.ERROR:
            name = reply.error_name or "unknown"
            text = str(reply.body[0]) if reply.body else ""
            if name in _UNAVAILABLE_ERRORS:
                raise ServiceUnavailable(destination, f"{name}: {text}", name)
            raise ServiceError(destination, f"{name}: {text}", name)
        return [unwrap(v) for v in (reply.body if reply is not None else [])]

    async def _send_match(self, conn: MessageBus, member: str, rule: str) -> None:
        message = Message(
            destination=BUS_NAME,
            path=BUS_PATH,
            interface=BUS_NAME,
            member=member,
            signature="s",
            body=[rule],
        )
        reply = await asyncio.wait_for(conn.call(message), CALL_TIMEOUT)
        if reply is not None and reply.message_type == MessageType.ERROR:
            logger.warning(f"dbus: {member} {rule!r} failed: {reply.error_name}")

    async def _read_owner(self, conn: MessageBus, name: str) -> str | None:
        message = Message(
            destination=BUS_NAME,
            path=BUS_PATH,
            interface=BUS_NAME,
            member="GetNameOwner",
            signature="s",
            body=[name],
        )
        reply = await asyncio.wait_for(conn.call(message), CALL_TIMEOUT)
        if reply is not None and reply.message_type == MessageType.METHOD_RETURN:
            return str(reply.body[0])
        return None

    # -- match rules and signal subscriptions ---------------------------------------------------

    def _on_message(self, message: Message) -> None:
        if message.message_type != MessageType.SIGNAL:
            return
        for sub in tuple(self._subs):
            if self._matches(sub.key, message):
                try:
                    sub.callback(message)
                except Exception:
                    logger.opt(exception=True).error(
                        f"dbus: a signal callback raised ({sub.key.interface}.{sub.key.member})"
                    )

    def _matches(self, key: MatchKey, message: Message) -> bool:
        if message.interface != key.interface or message.member != key.member:
            return False
        if key.path is not None and message.path != key.path:
            return False
        if key.arg0 is not None and (not message.body or message.body[0] != key.arg0):
            return False
        if key.arg0namespace is not None:
            first = str(message.body[0]) if message.body else ""
            if first != key.arg0namespace and not first.startswith(key.arg0namespace + "."):
                return False
        sender = key.sender
        if sender is None or sender == message.sender:
            return True
        # a signal carries the sender's unique name: a well-known name is judged by its owner
        watched = self._names.get(sender)
        return watched is not None and watched.owner is not None and watched.owner == message.sender

    async def subscribe(self, key: MatchKey, callback: Callable[[Message], None]) -> Unsubscribe:
        """Call ``callback(message)`` for each signal that matches ``key``. One match rule is on
        the bus per distinct key, however many subscribe, and goes with the last of them. A
        well-known ``sender`` is watched for its owner too. The returned function ends the
        subscription (call it on the service thread)."""
        unwatch: Unsubscribe | None = None
        if key.sender is not None and not key.sender.startswith(":") and key.sender != BUS_NAME:
            unwatch = await self.watch(key.sender, None)
        sub = _Sub(key, callback)
        self._subs.append(sub)
        try:
            await self.connection()  # the first use opens the bus
        except ServiceUnavailable:
            pass  # the rule is sent when the bus comes up
        await self._add_rule(key.rule())

        def remove() -> None:
            if sub in self._subs:
                self._subs.remove(sub)
                self._drop_rule(key.rule())
            if unwatch is not None:
                unwatch()

        return remove

    async def _add_rule(self, rule: str) -> None:
        count = self._rules.get(rule, 0)
        self._rules[rule] = count + 1
        if count == 0 and self.connected:
            try:
                assert self._conn is not None
                await self._send_match(self._conn, "AddMatch", rule)
            except Exception as exc:  # re-added on the next connection
                logger.debug(f"dbus: AddMatch {rule!r} did not go through ({exc})")

    def _drop_rule(self, rule: str) -> None:
        count = self._rules.get(rule, 0) - 1
        if count > 0:
            self._rules[rule] = count
            return
        self._rules.pop(rule, None)
        conn = self._conn
        if conn is not None and conn.connected:
            self._spawn(self._remove_match(conn, rule))

    async def _remove_match(self, conn: MessageBus, rule: str) -> None:
        try:
            await self._send_match(conn, "RemoveMatch", rule)
        except Exception as exc:
            logger.debug(f"dbus: RemoveMatch {rule!r} did not go through ({exc})")

    # -- well-known names -----------------------------------------------------------------------

    async def watch(self, name: str, callback: OwnerCallback | None = None) -> Unsubscribe:
        """Follow the owner of the well-known ``name``: the first watch adds the
        ``NameOwnerChanged`` rule for that name and reads the owner (``GetNameOwner``; see
        :meth:`owner` afterwards). ``callback(old, new)`` is called on the service thread whenever
        the owner changes (``None``: no owner), also when the connection is lost (new owner
        ``None``) and when it comes back. The result ends this watch; the rule goes with the last
        one."""
        watched = self._names.get(name)
        if watched is None:
            watched = self._names[name] = _Name()
            created = watched

            def changed(message: Message) -> None:
                self._set_owner(name, created, message.body[2] or None)

            key = MatchKey(BUS_NAME, BUS_PATH, BUS_NAME, "NameOwnerChanged", name)
            try:
                watched.unsubscribe = await self.subscribe(key, changed)
                try:
                    owner = await self._read_owner(await self.connection(), name)
                except ServiceUnavailable, TimeoutError, OSError:
                    owner = None
                self._set_owner(name, watched, owner, quiet=True)  # the caller reads ``owner``
            except BaseException:
                if self._names.get(name) is watched:
                    del self._names[name]
                if watched.unsubscribe is not None:
                    watched.unsubscribe()
                raise
            finally:
                watched.ready.set()
        else:
            await watched.ready.wait()
        watched.refs += 1
        if callback is not None:
            watched.callbacks.append(callback)

        def stop() -> None:
            if callback is not None and callback in watched.callbacks:
                watched.callbacks.remove(callback)
            watched.refs -= 1
            if watched.refs <= 0 and self._names.get(name) is watched:
                del self._names[name]
                if watched.unsubscribe is not None:
                    watched.unsubscribe()

        return stop

    async def watch_prefix(
        self, prefix: str, callback: PrefixCallback, reach: ReachCallback | None = None
    ) -> Unsubscribe:
        """Follow every well-known name that starts with ``prefix`` (``org.mpris.MediaPlayer2.``):
        one ``ListNames`` now, and one ``NameOwnerChanged`` rule by namespace for all of them (no
        polling). ``callback(name, old, new)`` runs on the service thread for each name that has an
        owner now (old ``None``), and afterwards when one appears, goes (new ``None``) or changes
        hands; ``reach(True or False)`` says whether the bus can be reached (the names of a bus
        that is lost go, and are listed again when it is back). The result ends this watch."""
        watched = self._prefixes.get(prefix)
        if watched is None:
            watched = self._prefixes[prefix] = _Prefix(prefix)
            created = watched

            def changed(message: Message) -> None:
                name, _, new = message.body[0], message.body[1], message.body[2]
                if str(name).startswith(created.prefix):
                    self._set_prefixed(created, str(name), str(new) or None)

            key = MatchKey(
                BUS_NAME,
                BUS_PATH,
                BUS_NAME,
                "NameOwnerChanged",
                arg0namespace=prefix.rstrip("."),
            )
            try:
                watched.unsubscribe = await self.subscribe(key, changed)
            except BaseException:
                self._prefixes.pop(prefix, None)
                watched.ready.set()
                raise
            # callbacks are added before the first list, so the first names reach them
            watched.callbacks.append(callback)
            if reach is not None:
                watched.reach.append(reach)
                if watched.reachable:  # the first connection listed the names already
                    reach(True)
            for name, owner in list(watched.names.items()):
                self._call_prefix(callback, name, None, owner)
            try:
                await self._list_prefix(await self.connection(), watched)
            except ServiceUnavailable, TimeoutError, OSError:
                self._prefix_unreachable(watched)  # listed when the bus is reached
            finally:
                watched.ready.set()
        else:
            await watched.ready.wait()
            watched.callbacks.append(callback)
            if reach is not None:
                watched.reach.append(reach)
                reach(watched.reachable)
            for name, owner in list(watched.names.items()):
                self._call_prefix(callback, name, None, owner)

        def stop() -> None:
            if callback in watched.callbacks:
                watched.callbacks.remove(callback)
            if reach is not None and reach in watched.reach:
                watched.reach.remove(reach)
            if not watched.callbacks and self._prefixes.get(prefix) is watched:
                del self._prefixes[prefix]
                if watched.unsubscribe is not None:
                    watched.unsubscribe()

        return stop

    async def _list_prefix(self, conn: MessageBus, watched: _Prefix) -> None:
        """Read every name on the bus and bring ``watched`` up to date: the names that are new
        are announced, the ones that went are told as gone."""
        reply = await asyncio.wait_for(
            conn.call(
                Message(
                    destination=BUS_NAME,
                    path=BUS_PATH,
                    interface=BUS_NAME,
                    member="ListNames",
                )
            ),
            CALL_TIMEOUT,
        )
        names = [
            str(n)
            for n in (reply.body[0] if reply is not None and reply.body else [])
            if str(n).startswith(watched.prefix)
        ]
        self._set_reachable(watched, True)
        for name in names:
            try:
                owner = await self._read_owner(conn, name)
            except ServiceUnavailable, TimeoutError, OSError:
                owner = None
            if owner is not None:
                self._set_prefixed(watched, name, owner)
        for name in list(watched.names):
            if name not in names:
                self._set_prefixed(watched, name, None)

    def _prefix_unreachable(self, watched: _Prefix) -> None:
        for name in list(watched.names):
            self._set_prefixed(watched, name, None)
        self._set_reachable(watched, False)

    def _set_reachable(self, watched: _Prefix, reachable: bool) -> None:
        if watched.reachable == reachable and watched.ready.is_set():
            return
        watched.reachable = reachable
        for fn in tuple(watched.reach):
            try:
                fn(reachable)
            except Exception:
                logger.opt(exception=True).error(
                    f"dbus: a reach callback of {watched.prefix} raised"
                )

    def _set_prefixed(self, watched: _Prefix, name: str, owner: str | None) -> None:
        old = watched.names.get(name)
        if owner == old:
            return
        if owner is None:
            del watched.names[name]
        else:
            watched.names[name] = owner
        for callback in tuple(watched.callbacks):
            self._call_prefix(callback, name, old, owner)

    @staticmethod
    def _call_prefix(callback: PrefixCallback, name: str, old: str | None, new: str | None) -> None:
        try:
            callback(name, old, new)
        except Exception:
            logger.opt(exception=True).error(f"dbus: a prefix callback of {name} raised")

    def _set_owner(
        self, name: str, watched: _Name, owner: str | None, *, quiet: bool = False
    ) -> None:
        old = watched.owner
        if owner == old:
            return
        watched.owner = owner
        if quiet:
            return
        for callback in tuple(watched.callbacks):
            try:
                callback(old, owner)
            except Exception:
                logger.opt(exception=True).error(f"dbus: an owner callback of {name} raised")


class ServiceThread:
    def __init__(self, address: str | None = None, system_address: str | None = None) -> None:
        """``address`` and ``system_address`` are bus addresses for tests; ``None`` is the bus as
        the environment gives it (``DBUS_SESSION_BUS_ADDRESS``; the system bus socket)."""
        self.session = Bus("session", address)
        self.system = Bus("system", system_address)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def bus(self, kind: BusKind) -> Bus:
        return self.session if kind == "session" else self.system

    @property
    def thread_id(self) -> int | None:
        """The ident of the ``dbus`` thread (``None`` before ``start``)."""
        return self._thread.ident if self._thread is not None else None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="dbus", daemon=True)
        self._thread.start()
        self._ready.wait()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            for bus in (self.session, self.system):
                bus.close()
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()

    def submit[T](self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """Run ``coro`` on the service thread; the future is for the caller's thread."""
        assert self._loop is not None, "the service thread is not started"
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def post(self, fn: Callable[[], object]) -> None:
        """Call ``fn()`` on the service thread, soon. Never blocks; a stopped thread drops it."""
        loop = self._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(fn)
        except RuntimeError:  # the loop is closed
            pass

    def stop(self) -> None:
        loop, thread = self._loop, self._thread
        if loop is None or thread is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        self._thread = None
        self._loop = None
