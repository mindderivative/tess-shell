---
title: M0 Build Log
aliases: [M0 Log]
type: moc
status: draft
owner: phil
created: 2026-11-04
updated: 2026-11-04
tags: [moc, build-log]
---

# M0 Build Log

> [!NOTE]
> The log of milestone M0, the skeleton. The `tess-shell` code session owns this note ([Build Logs](Build%20Logs.md)). It was first written by the vault session on 2026-11-04 from the code session's mailbox reports and the repository history, so the code session can take it over; text in it may be corrected by the code session without asking.

## Tasks

| Task | State | Commits in `tess-shell` | Note |
|---|---|---|---|
| T1 Repository and tooling | Built | 0cb6986 | hatchling, src layout, ruff, mypy, pytest; `uv` on the system CPython 3.14.9 with the GIL (2f5c38f) |
| T2 Commands | Built | f4f8bb3 | `version`, `check`, `run`; the others print "not implemented in M0" and exit 1 |
| T3 Config | Built | 58a76ae | Config directory and every key of the Settings File note |
| T4 Logging | Built | dd38f17 | Loguru, console and a daily file |
| T5 Lock | Built | 28ad2ca | `flock` lock and `XDG_RUNTIME_DIR` checks |
| T6 Start and stop | Built | 449e708, 8062958 | Start steps 1 to 7 and 9, the stop sequence, signals, a stop retry for a signal before the loop |
| T7 Check | Built | 4d3386b | Syntax scan, `--json`, capped at 50 |
| T8 Tests | Built | 05baf12 | Import rules enforced by `tests/test_imports.py` |
| T9 Idle measurement | Built | b4d9235, 61954dc | `tests/perf/measure_idle.py` and `idle-results.md` |

## Measurements

| What | Result | Date and conditions |
|---|---|---|
| Tests | 97 passed | 2026-11-03, `uv run pytest` |
| Idle CPU of `run` | 0.017 % of one core (budget 0.5 %) | 2026-11-03, private headless sway, no windows, Python 3.14.9 with the GIL, 60 s |
| Idle wake-ups | About 2.0 per second (budget 5), counted as context switches | same run |

## Differences from the Specs

Recorded in [M0 Brief > Result (2026-11-03)](M0%20Brief.md#result-2026-11-03) with what the vault did about each.

## Facts About tre, TEL and tess_dl

- A `call_soon` queued before `App.run()` is not drained at loop start (tess_re 0.6.0 and 0.6.1): [TRE-REQ-011 Drain call_soon at Loop Start](../80%20Requests/TRE-REQ-011%20Drain%20call_soon%20at%20Loop%20Start.md).
- `tess_re` has no `__version__`; versions come from `importlib.metadata`.
- `tess_dl` 0.1.1 has no `Block.properties`, `blocks`, `get` or `walk`; the shell's helpers are in `files/tree.py`.

## Decisions Needed

None open.

## For the Vault Session

None.

## Links

- [Build Logs](Build%20Logs.md) · [M0 Brief](M0%20Brief.md) · [Development Readiness](Development%20Readiness.md)
