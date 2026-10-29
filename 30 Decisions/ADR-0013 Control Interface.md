---
title: ADR-0013 Control Interface
aliases: [ADR-0013, IPC Decision, Shell D-Bus Interface]
type: adr
status: proposed
owner: phil
created: 2026-10-28
updated: 2026-10-28
tags: [adr, integration/dbus, needs-verification]
related: ["[[IPC and CLI]]", "[[ADR-0009 D-Bus Client Library]]", "[[ADR-0012 Keeping the Shell Above Plasma Panels]]", "[[ADR-0004 Plasma Coexistence]]", "[[Shell Start and Stop]]"]
depends_on: ["[[ADR-0009 D-Bus Client Library]]", "[[ADR-0012 Keeping the Shell Above Plasma Panels]]"]
---

# ADR-0013: Control interface

> [!summary]
> How anything outside the shell process tells it to do something: the command line, a keyboard shortcut, the KWin script that reports fullscreen windows. Recommendation: the shell owns one session-bus name and exports a small D-Bus interface; the command line is a thin client of it. Status is `proposed`.

## Context

- The shell is one process with one loop ([[ADR-0003 Process Model]]). It needs commands from outside: reload, quit, show or hide a surface, call a module action, report status.
- ADR-0012 (accepted) has a KWin script report fullscreen windows to the shell. A KWin script can call a D-Bus method (`callDBus(service, path, interface, method, args, callback)`, asynchronous) and the scripting page documents no way to run a process ([KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/), read 2026-10-28). So the shell must offer a D-Bus method for the script, whatever else it offers.
- A keyboard shortcut for a launcher can be a KDE custom shortcut that runs a command; that command must start fast.
- Measured on this machine (2026-10-28, Python 3.14.8, median of 9 runs): a bare Python start is 7.6 ms; importing `argparse`, `json`, `socket` and `os` brings it to 16.7 ms; a stdlib Unix-socket connect attempt takes 13.8 ms; `jeepney` (pure Python, 0.9.0) connecting to the session bus and making one call takes 20.0 ms; importing `jsonschema` alone takes 57.5 ms. `dbus-fast` 5.2.0 was then installed in a scratch folder (not on the system) and tested the same day. Importing `dbus_fast.aio` takes 54.3 ms and a `dbus-fast` client making one call takes 53.2 ms, against 21.0 ms for the `jeepney` client and 1.5 ms for `busctl --user call` as a reference. A test service on the session bus, written with `dbus-fast`, exported a method returning two values, a method that raises a named D-Bus error, a method taking an array of strings, a read-only property that emits changes, and a signal; `busctl introspect` listed them all, `busctl call` reached them, `busctl monitor` saw the signal, and a second process requesting the same name with `DO_NOT_QUEUE` got `EXISTS`. So `dbus-fast` is fit to export the interface; as a command-line client its import cost makes `jeepney` the better choice.

## Options

### Option A — A Unix socket with JSON lines, and D-Bus only for the KWin script
- **For:** a client with no dependencies; trivial to script (`nc -U`).
- **Against:** two mechanisms, two front-ends, two security stories; the socket does nothing the D-Bus interface cannot do.

### Option B — One D-Bus interface for everything (recommended)
The shell requests a bus name on the session bus and exports one object. The command line, the KWin script, `busctl`, `qdbus` and shortcut commands all call it. The command line is a thin client.
- **For:** one front-end and one set of commands; the KWin script needs it anyway; introspectable (`busctl introspect`); signals for free (events); the bus enforces that only the same user's processes connect; measured client cost is close to the socket's (20 ms against 14 ms).
- **Against:** needs the session bus (always present in a Plasma session); the CLI needs a small D-Bus client (`jeepney`, the named fallback in [[ADR-0009 D-Bus Client Library]], is 21 ms against `dbus-fast`'s 53 ms); a name on the bus must be chosen. A shortcut command can also call `busctl --user call` directly, which took 1.5 ms.

### Option C — Both, behind one command table
- **For:** a CLI that works with no bus.
- **Against:** the cost of A for a case that does not arise in the target session.

## Decision

Blank until the maintainer accepts.

## Consequences

- The shell's D-Bus service thread (shared, [[ADR-0009 D-Bus Client Library]]) also exports the shell's own object. ADR-0009 had named `bus.export` and name requests as later work; this makes them v1 work.
- If B is accepted, [[Shell Start and Stop]] changes: the control socket is replaced by the D-Bus interface, and the lock file stays for the single-instance rule. The runtime directory then holds the lock file only.
- The bus name is a project identifier that must be chosen and kept ([[IPC and CLI#The bus name]]).
- The interface has no method that evaluates code or reads files ([[IPC and CLI#Security]]).

## Links

[[IPC and CLI]] · [[ADR-0009 D-Bus Client Library]] · [[ADR-0012 Keeping the Shell Above Plasma Panels]] · [[30 Decisions]]
