---
title: D-Bus Libraries for Python
aliases: [D-Bus Survey, Python D-Bus Options]
type: research
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [research, integration/dbus, needs-verification]
related: ["[[System Context]]", "[[Process Model and Threading]]", "[[ADR-0004 Plasma Coexistence]]"]
depends_on: []
---

# D-Bus libraries for Python

> [!success] Decided 2026-10-26
> The maintainer accepted the recommendation: [[ADR-0009 D-Bus Client Library]].

> [!summary]
> The shell and its modules need a D-Bus client for UPower, NetworkManager, MPRIS, KWin, the tray and the global shortcut service ([[System Context]]). This survey compares the Python options. Recommendation: **`dbus-fast`**, run on one shared asyncio service thread that the shell provides, with **`jeepney`** as the fallback. The maintainer asked for the survey and a recommendation (2026-10-26); the choice is theirs. Release data comes from PyPI and GitHub on 2026-10-26; nothing was installed or run.

## What the shell needs

| Need | Why |
|---|---|
| Read properties and watch signals | Battery, network, media, workspaces, tray |
| Call methods | Mute, play and pause, activate a window |
| Session and system buses | UPower and NetworkManager are on the system bus; the rest on the session bus ([[System Context#Observed D-Bus names]]) |
| Work off the loop thread | Blocking work never runs on the loop ([[Process Model and Threading]]) |
| Export an interface and own a name (later) | A notification server or tray watcher is outside v1, but the choice should not block it |
| Python 3.14, Linux | The shell's minimum ([[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]]) |
| Few dependencies, installable | The shell is a Python package |

## Candidates

| Library | Release (PyPI) | Last activity | Python | Model | Licence | Notes |
|---|---|---|---|---|---|---|
| **dbus-fast** 5.2.0 | 2026-10-02 | GitHub push 2026-10-24 | `>=3.11`; classifiers list 3.13, 3.14, 3.15 | asyncio, or the GLib main loop; non-blocking | MIT | Zero dependencies and pure Python, with an optional Cython extension in the wheels for faster (un)marshalling; `SKIP_CYTHON=1` builds pure Python. High-level proxy objects (methods, properties, signals), introspection, and `bus.export` plus name requests for services. A faster fork of dbus-next ([PyPI](https://pypi.org/project/dbus-fast/)) |
| **jeepney** 0.9.0 | 2025-02-27 | GitLab activity 2026-10-16 | `>=3.7` (no version classifiers) | Pure Python with an I/O-free core and integration modules for different event loops | MIT | Low-level: you build messages and handle replies. More code per module, no hidden thread or loop ([PyPI](https://pypi.org/project/jeepney/)). #needs-verification: the list of integrations (blocking, threading, asyncio) against its docs |
| **sdbus** 0.14.3 | 2026-08-20 | GitHub push 2026-08-20 | `>=3.9` | Uses libsystemd's sd-bus; asyncio and blocking (from general knowledge) | LGPL-2.1+ | Compiled, needs the system library; Linux only. Strong fit on Linux, heavier to package #needs-verification |
| dbus-python 1.5.1 | 2026-10-23 | Maintained | `>=3.7` | Bindings to libdbus; signals need a GLib main loop | MIT and GPL/AFL mix | `sdist` only: builds against libdbus; the legacy option |
| PyGObject / Gio 3.58.1 | 2026-10-09 | Maintained | `>=3.10` | GLib main loop | LGPL | `sdist` only; heavy; ties the shell to GLib |
| dasbus 1.7 | 2022-11-07 | GitHub push 2025-06-25 | `>=3.6` | GLib | none listed | GLib-based; last release four years old |
| dbus-next 0.2.3 | 2021-07-25 | GitHub push 2024-06-12 | `>=3.6` | asyncio | MIT | Superseded by dbus-fast |
| pydbus 0.6.0 | 2016-12-18 | GitHub push 2023-12-05 | none | GLib | LGPL | Unmaintained |

## Fit with the architecture

[[Process Model and Threading]] says each module owns its threads and the shell provides a helper, with a shared service thread as an option. D-Bus is I/O-bound, which suits asyncio: one event loop on one thread can hold the session and system bus connections for every module, instead of a thread per module.

| Option | Description | Verdict |
|---|---|---|
| **Shared asyncio service thread with dbus-fast (recommended)** | The shell starts one thread running an asyncio loop. A helper (`ctx.dbus`, name not decided) gives a module a connected session or system bus, proxies and signal subscriptions. A subscription callback runs on the service thread and calls the module's send entry point, which crosses to the loop with `call_soon`. | Few threads and connections; fits signals and properties; keeps the loop clear. A module that blocks in a callback stalls every D-Bus module, so the contract says callbacks are short. |
| jeepney in module threads | Each module opens its own connection and reads on its own thread | No shared loop; simple and explicit; more code per module and more connections |
| sdbus | Compiled sd-bus wrapper | Good on Linux; needs a system library at install and build time |
| GLib-based (dbus-python, Gio, dasbus) | Run a GLib main loop | Adds a second event loop to a program that already has tre's |

## Recommendation

1. **Use `dbus-fast`**, on a shell-provided shared asyncio service thread, for the shell's own D-Bus work and as the library modules use through `ctx.dbus`.
2. **Do not forbid others.** A module is Python and may import whatever it needs; the shell recommends and helps with `dbus-fast`.
3. **Keep `jeepney` as the fallback** if the Cython wheels or the asyncio helper cause packaging or threading trouble.
4. **Test early** (a short spike): read UPower's battery percentage, watch a `PropertiesChanged` signal, and read KWin's `/VirtualDesktopManager`, from the service thread on Python 3.14, and measure the idle cost.

## Risks and checks

- #needs-verification: that `dbus-fast` 5.2.0 installs and runs on Python 3.14 (classifiers say so; nothing was run).
- A single service thread is a shared resource: one slow callback delays all D-Bus modules. The contract and a watchdog on the service thread help ([[Process Model and Threading#Failure and recovery]]).
- Exceptions in a callback on the service thread must be caught and logged with the module's name ([[Logging with Loguru]]).
- The Cython extension adds binary wheels; the pure-Python build is the escape hatch.

## Open

- [x] The maintainer's choice of library: `dbus-fast` on a shared asyncio service thread, `jeepney` as the fallback ([[ADR-0009 D-Bus Client Library]]).
- [x] The shared service thread is part of the chosen design ([[ADR-0009 D-Bus Client Library]]).
- [ ] The name and shape of the helper for modules ([[42 Python API]], to write).
- [ ] PipeWire access path (D-Bus, `wpctl`, a library): a separate survey.

## Links

- [[System Context]] · [[Process Model and Threading]] · [[90 Research]]
