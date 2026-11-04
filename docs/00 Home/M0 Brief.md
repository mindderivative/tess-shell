---
title: M0 Brief
aliases: [M0, Skeleton Brief, Shell M0]
type: moc
status: stable
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [moc, roadmap, brief]
---

# M0 Brief

> [!NOTE]
> M0 is built and pushed (maintainer, 2026-11-03); the results are under "Result". The brief for milestone M0, the skeleton: a `tess_shell` package that installs, answers `tesserae-shell version` and `check`, reads `settings.tdl`, starts logging, takes the instance lock, runs the start and stop sequences with no windows, and stops cleanly on a signal. The maintainer started M0 on 2026-11-03 ("Go for M0") and said a new session in Oh My Pi, in the `tess-shell` project directory, writes the code. This note is that session's starting point. The vault stays the design record; the code session does not edit it.

## Goal and Definition of Done

M0 is done when all of these hold:

- `uv sync` in `tess-shell` gives a working environment, and `uv run pytest`, `ruff` and `mypy` pass.
- `tesserae-shell version` prints the versions of the shell, `tess_re`, `tess_el` and `tess_dl`.
- `tesserae-shell check` reads `settings.tdl` and every shell file it finds, reports syntax errors as `file:line:column` (syntax only, no schema check), and exits 0 or 1.
- `tesserae-shell run` starts, logs, holds the lock, idles at about 0% CPU with no windows, and stops on SIGTERM or SIGINT with exit code 0; a second signal exits with 130; a second `run` exits with 4.
- Nothing else is built: no windows, no binder, no modules, no D-Bus, no hot reload.

## What to Read

| Note | For |
|---|---|
| [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) | Names, folders, import rules, dependencies, tooling |
| [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md) | The start and stop sequences, process rules, exit codes (steps 1 to 9 and the stop steps 1 to 6 are M0) |
| [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) | Finding the config directory and the registry file |
| [Settings File](../41%20TDL%20Reference/Settings%20File.md) | The keys of `settings.tdl` |
| [Logging](../40%20Specifications/Runtime/Logging.md) | Loguru setup, log files, levels |
| [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) | The error record and how errors print |
| [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md) | The command line (`#The Command Line`) |
| [Testing Strategy](../60%20Quality/Testing%20Strategy.md) | Test layers, markers, conventions |
| [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) | One loop, `keep_alive`, the signal watcher |
| [TDL Library API](../42%20Python%20API/TDL%20Library%20API.md) and the `tess-dl` repository docs (`docs/api.md`, `docs/language.md`) | Reading `settings.tdl` |
| [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md), [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) | Why the layout is as it is |

## Dependencies

Ranges, because the projects are 0.x and a minor release can break (maintainer, 2026-11-03):

| Package | Range | Import | State on 2026-11-03 |
|---|---|---|---|
| `tesserae-engine` | `>=0.6.0,<0.7` | `tess_re` | 0.6.0 is on PyPI (checked 2026-11-03; it imports as `tess_re`, `import tre` no longer works) |
| `tesserae-el` | `>=0.1.2,<0.2` | `tess_el` | 0.1.2 is on PyPI |
| `tesserae-dl` | `>=0.1.1,<0.2` | `tess_dl` | 0.1.1 is on PyPI. 0.1.0 also exists and imports as `tdl`, so the lower bound matters |
| `dbus-fast`, `loguru` | as in [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) | | `dbus-fast` is not needed before M4. `jsonschema` is not a dependency ([ADR-0020 Validation in Code](../30%20Decisions/ADR-0020%20Validation%20in%20Code.md)) |

The code session waited for `tesserae-engine` 0.6.0 (maintainer, 2026-11-03); it is now on PyPI, so every task can proceed. Earlier advice to start on the tasks that do not import `tess_re` no longer matters. Import `tess_re` only where it is needed (`version`, and the loop in `run`), and mark tests that need it `tre`, so the rest builds and tests now.

## Tasks

In this order. Each ends with its tests.

| # | Task | Done when | Spec |
|---|---|---|---|
| T1 | Repository: `pyproject.toml` (hatchling, src layout, `requires-python >=3.14`, the ranges above, dev group `pytest`, `ruff`, `mypy`), `LICENSE` (MIT), `CHANGELOG.md`, `README.md`, `src/tess_shell/` with `__init__.py` (`__version__`), `py.typed`, `tests/` | `uv sync`, `ruff`, `mypy` and `pytest` run clean on an empty test | [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) |
| T2 | `cli.py` and `__main__.py`: `version`, `check`, `run`; global options `--config-dir`, `--json`, `--quiet`; the other subcommands print "not implemented in M0" and exit 1 | `tesserae-shell version` and `python -m tess_shell version` agree | [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md) |
| T3 | `config/`: the config directory (`XDG_CONFIG_HOME`, else `~/.config/tesserae-shell/`, created with the default folders), `settings.tdl` read with `tess_dl`, the keys `Directories`, `Registry`, `Logging`, `Validation`, `Main_Shell`, defaults when the file is absent, a bad file stops with exit 1 and a `file:line:column` error | The cases in [Settings File](../41%20TDL%20Reference/Settings%20File.md) acceptance criteria that do not need other milestones | [Settings File](../41%20TDL%20Reference/Settings%20File.md), [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) |
| T4 | `logging.py`: Loguru, console and file sinks, levels, the log folder, `enqueue=True` as decided | A log line reaches the console and the file with the right level and source | [Logging](../40%20Specifications/Runtime/Logging.md) |
| T5 | The lock and the process rules: `XDG_RUNTIME_DIR` checks (exit 2), the lock file under `$XDG_RUNTIME_DIR/tesserae-shell/`, exit 4 for a second shell | Two `run` commands: the second exits 4 and names the first's pid | [Shell Start and Stop > Process Rules](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#process-rules) |
| T6 | `app.py`: start steps 1 to 9 (pre-flight, config directory, settings, logging, lock, registry open or create empty, discover and parse files with `tess_dl`, the loop with `keep_alive`), steps 10 to 12 log "not built in M0"; the stop steps 1 to 6; signals through `set_wakeup_fd`, a watcher thread and `LoopHandle.stop()` | The shell idles and stops on SIGTERM with exit 0, and on a second signal with 130 | [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md), [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) |
| T7 | `check`: parse every `.tdl` file found with `tess_dl.parse`, print every error (up to 50) with code, message, hint and position, `--json` form, exit 0 or 1 | A file with an unclosed block prints `file:line:column` and exits 1 | [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) |
| T8 | Tests per [Testing Strategy](../60%20Quality/Testing%20Strategy.md): unit tests for config, lock and exit codes; the import-rules test (`binder/` not yet present, so the test covers the packages that exist); a headless start-and-stop test that sends SIGTERM | `uv run pytest` passes with no display | [Testing Strategy](../60%20Quality/Testing%20Strategy.md) |
| T9 | A measurement: idle CPU and wake-ups of `run` over 60 seconds, written to a file under `tests/perf/` (not `docs/`; the maintainer asked for a file, 2026-11-03) and compared with the budget | The numbers are reported, not yet enforced | [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |

The `tess_dl` 0.1 tree has `Document`, `Block.entries`, `Property` and the value classes. It does not have `Block.properties`, `Block.blocks`, `Block.get`, `Block.walk`, `Document.imports` or `to_data` (reported by `tess-dl` on 2026-11-03). Write a small helper in `files/` for what M0 needs and keep it free of shell meaning. If a helper belongs in the library, record it as a `TDL-REQ-###` for the maintainer to carry.

## Rules for the Code Session

- Work only in `~/Projects/pyDev/projects/tess-shell`: `src/`, `tests/`, `pyproject.toml`, `README.md`, `CHANGELOG.md`, `LICENSE`. Do not edit `docs/` (it is generated from the vault) or `tools/`, and do not edit the vault.
- Commit locally after each task, with a short imperative message. Never push, open a pull request or touch a remote without the maintainer's instruction.
- Follow the layout and the import rules in [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md). If a design is wrong, unclear or missing, stop and tell the maintainer, who brings it to the vault session; do not decide it silently. A design change is a dated amendment in the vault, not a quiet edit in code.
- Do not invent tre, TEL or `tess_dl` API. Check the installed package or its docs; ask for a request if something is missing.
- Style: ruff line length 100, rules `E F I B UP`, mypy on the whole package, everything typed, no per-frame Python (there is no frame in M0), no blocking call on the loop thread.
- Keep a short `AGENTS.md` in the repository with these rules (draft below).

## Draft Repository Instructions

For the new session's `AGENTS.md` in `tess-shell`:

```
Tesserae Shell code. The design is in the vault at
~/Projects/Obsidian/Tesserae Shell (read it, do not edit it).
Start from 00 Home/M0 Brief.md there. Package: src/tess_shell. Python >= 3.14.
Deps: tess_re (tesserae-engine), tess_el (tesserae-el), tess_dl (tesserae-dl), loguru.
Rules: commit locally after each task; never push without the maintainer's word;
do not edit docs/ or tools/; follow the import rules in 20 Architecture/Shell Package Layout.md;
ruff (line 100) and mypy must pass; report design gaps to the maintainer instead of guessing.
```

## Result (2026-11-03)

Built by the code session in `tess-shell` and pushed to `origin/main`. Checked against the repository on 2026-11-03:

| Check | Result |
|---|---|
| Tests | 97 passed (`uv run pytest`) |
| Tasks | T1 to T9 are in the history: skeleton and tooling, `version`, settings and config directory, Loguru, lock and runtime-directory checks, start and stop sequences with signals, `check` (syntax only), tests and the import-rules test, the idle measurement |
| Idle cost of `run` over 60 s, headless sway, no windows, Python 3.14.9 with the GIL | 0.017 % of one core (budget at most 0.5 %); about 2.0 wake-ups per second (budget at most 5), counted as context switches, which over-counts ([Performance Budgets](../60%20Quality/Performance%20Budgets.md)) |
| Engine | `tesserae-engine` 0.6.1 in the lock file (0.6.0 was the minimum) |
| Python | The repository stays on the system Python with the GIL |

Not checked by the vault session: the code itself, and the list of design gaps (see the open item below).

## Open Questions

1. [x] The code session waits for `tesserae-engine` 0.6.0 (maintainer, 2026-11-03).
2. [x] `check` is syntax-only in M0; the schema comes with M1 (maintainer, 2026-11-03).
3. [x] T9 results are written to a file under `tests/perf/` in the repository (maintainer, 2026-11-03: "add it to a file"), not only reported in chat.

## Acceptance Criteria

- [x] Every item under "Goal and Definition of Done" is true (tests and idle measurement above; the maintainer reports M0 built and pushed).
- [x] Each task T1 to T9 has at least one test or a recorded measurement (`tests/` and `tests/perf/idle-results.md`).
- [x] No file outside the allowed list was changed, as far as the history shows (the agent setup files are in the list).
- [ ] A list of design gaps found is handed to the vault session.

## Links

- [Development Readiness](Development%20Readiness.md) · [Roadmap](Roadmap.md) · [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) · [Testing Strategy](../60%20Quality/Testing%20Strategy.md) · [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)
