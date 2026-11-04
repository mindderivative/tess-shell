---
title: Shell Package Layout
aliases: [Package Layout, Repository Layout, Dependencies]
type: architecture
status: review
owner: phil
created: 2026-11-02
updated: 2026-11-03
tags: [architecture, delivery]
---

# Shell Package Layout

> [!NOTE]
> Where the shell's code lives and what may import what: the `tess-shell` repository, the `tess_shell` package and its sub-packages, the import rules that keep the layers apart, the dependencies with their minimum versions, and the tooling. It follows the house style of the TEL project (src layout, hatchling, uv, ruff, mypy, pytest). This is a proposal for the maintainer; the repository choice is decided: the code goes in `tess-shell` under `src/tess_shell/` and `tests/`, with the docs export kept in `docs/` (maintainer, 2026-11-02, as recommended).

## Purpose and Scope

- Fix the names and the folder structure before M0 ([Development Readiness](../00%20Home/Development%20Readiness.md)), so the first commit has a place for everything.
- Not in this note: what each component does ([Layers and Components](Layers%20and%20Components.md)), the test plan ([Testing Strategy](../60%20Quality/Testing%20Strategy.md)), and packaging for users ([Roadmap](../00%20Home/Roadmap.md), Delivery, M6).

## Names

The Python import names of all projects changed on 2026-11-03 to avoid conflicts in the future ([ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) D95). PyPI distribution names did not change (maintainer, 2026-11-03), and the GitHub repositories are `tess-re`, `tess-ui`, `tess-el`, `tess-dl` and `tess-shell`.

| Project | Distribution (PyPI) | Import name | GitHub repository |
|---|---|---|---|
| tre | `tesserae-engine` | `tess_re` (was `tre`) | `tess-re` (still `tre` on 2026-11-03; docs at `mindderivative.github.io/tre/`) |
| Tesserae UI | `tesserae-ui` | `tess_ui` (was `tesserae`) | `tess-ui` (renamed; docs at `mindderivative.github.io/tess-ui/`) |
| TEL | `tesserae-el` | `tess_el` (was `tel`) | `tess-el` |
| TDL | `tesserae-dl` | `tess_dl` (was `tdl`) | `tess-dl` |
| Tesserae Shell | `tesserae-shell` | `tess_shell` (was `tesserae_shell`) | `tess-shell` |

| What | Value | Status |
|---|---|---|
| Repository | `github.com/mindderivative/tess-shell` (public, exists) | Decided |
| Local folder | `~/Projects/pyDev/projects/tess-shell` | Decided |
| PyPI package | `tesserae-shell` (free on PyPI on 2026-11-02) | Decided (maintainer, 2026-11-03) |
| Import name | `tess_shell` | Decided (maintainer, 2026-11-03; it was `tesserae_shell`) |
| Command | `tesserae-shell`, also `python -m tess_shell` | Decided ([IPC and CLI > The Command Line](../40%20Specifications/Runtime/IPC%20and%20CLI.md#the-command-line)) |
| Virtual environment | `~/Projects/pyDev/pyEnvs/tess-shell` (outside the repository) | Decided (the maintainer's layout) |

## The Repository

```
tess-shell/
├── src/tess_shell/        the package (below)
├── tests/                     the tests ([[Testing Strategy]])
├── docs/                      generated from the design vault by tools/sync_docs.py; never edited by hand
├── tools/                     sync_docs.py and other maintainer scripts
├── pyproject.toml
├── README.md   LICENSE   CHANGELOG.md
└── .gitignore
```

`docs/` stays an export of the vault, which remains the design record ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). The sync hook writes only there.

## The Package

```
tess_shell/
├── __init__.py          __version__
├── __main__.py          python -m tess_shell
├── cli.py               run, check, schema, reload, quit, status, show/hide/toggle, call, kwin, version
├── app.py               the start and stop sequences, the loop, signals
├── config/              discovery of the config directory, settings.tdl, the registry, paths
├── files/               loading with tdl: Import, name resolution, the UID write, file-type checks
├── schema/              the keys and types of each file type, checked in code ([[ADR-0020 Validation in Code]]); a later optional emitter of JSON Schema as plain JSON; error codes of the shell
├── model/               the shell model, the value store, TEL scope and compilation, If and For
├── binder/              the render binder (independent, below)
├── surfaces/            the surface manager: Bar, Panel, Popup, Frame, monitors, layer windows
├── modules/             the module host, the context, and the shipped modules (one folder each)
├── services/            D-Bus layer, KWin, shortcuts, portals
├── ipc/                 the shell's own D-Bus interface
├── logging.py           Loguru setup
└── py.typed
```

### The Binder Is Independent

`tess_shell/binder/` follows [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md): it holds the block table, the key table, the converters and the links, it imports only `tess_re`, `tess_utils` and the standard library, and it receives a typed tree through plain classes defined in `binder/`. A test fails if `binder/` imports any other part of `tess_shell`. It can then become its own library without edits.

### Import Rules

| Package | May import | Must not import |
|---|---|---|
| `binder` | `tess_re`, `tess_utils` (the vendored copy), the standard library | everything else in `tess_shell`, `tess_dl`, `tess_el` |
| `files` | `tess_dl`, `config`, `schema` | `tess_re`, `surfaces`, `services` |
| `schema` | the standard library, `binder.model` (the typed tree classes only) | `tess_re`, `tess_dl` internals (it reads the public tree) |
| `model` | `tess_el`, `schema`, `files` | `tess_re`, `surfaces`, `services` |
| `surfaces` | `tess_re`, `binder`, `model`, `config` | `services`, `modules` internals |
| `modules` | `model`, the module context, `services` through the context only | `tess_re`, `surfaces` ([Layers and Components > Dependency Rules](Layers%20and%20Components.md#dependency-rules) rule 3) |
| `services` | `dbus_fast`, the standard library | `tess_re`, `model`, `surfaces` |
| `ipc` | `services`, `app` hooks | `tess_re` |
| `app`, `cli` | anything above | n/a |

Only the vendored `tess_utils` imports `PIL` (Pillow); no other `tess_shell` module does, and a test checks it ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md)). A module (user or shipped) never imports `tess_re` ([Layers and Components > Dependency Rules](Layers%20and%20Components.md#dependency-rules)). The rules are enforced by an import-linter style test, not by convention.

## Dependencies

| Package | Import | Minimum | Why |
|---|---|---|---|
| `tesserae-engine` | `tess_re` | `>=0.6.0,<0.7`, the release that renames the import to `tess_re` (on PyPI, checked 2026-11-03; 0.5.10, with `Window.build` and `Window.apply`, imports as `tre`) | The renderer ([TRE-REQ-009 Batch and Tree Building](../80%20Requests/TRE-REQ-009%20Batch%20and%20Tree%20Building.md)) |
| `tesserae-el` | `tess_el` | `>=0.1.2,<0.2`, the first release with the import name `tess_el` (on PyPI, checked 2026-11-03) | Expressions ([Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md)) |
| `tesserae-dl` | `tess_dl` | `>=0.1.1,<0.2`, the first release with the import name `tess_dl` (on PyPI, checked 2026-11-03; 0.1.0 imported as `tdl`) | Reading and writing TDL ([TDL Library API](../42%20Python%20API/TDL%20Library%20API.md)) |
| `tess-utils` | `tess_utils` | a tagged copy vendored under `src/tess_shell/_vendor/tess_utils/` ([ADR-0017 Shared Utilities > Distribution (Decided by the Maintainer 2026-11-03; Details Proposed)](../30%20Decisions/ADR-0017%20Shared%20Utilities.md#distribution-decided-by-the-maintainer-2026-11-03-details-proposed)) | Converters to tre's forms ([tess-utils Brief](../00%20Home/tess-utils%20Brief.md)) |
| `Pillow` | `PIL` | `>=10.0` (the floor Tesserae UI declares), when the image blocks are built | Decoding PNG, JPEG, GIF and WebP, imported only by the vendored `tess_utils` ([Block Reference](../41%20TDL%20Reference/Block%20Reference.md) R8); listed here because a vendored copy brings no metadata |
| `dbus-fast` | `dbus_fast` | per [ADR-0009 D-Bus Client Library](../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md) | D-Bus |
| `loguru` | `loguru` | per [Logging](../40%20Specifications/Runtime/Logging.md) | Logging |

Python 3.14 or later ([V1 Scope](../10%20Vision/V1%20Scope.md)); the dependencies' own minimums are as they state (tre requires 3.12 or later, TEL 3.14). The pins are ranges with the next minor as the upper bound, because the projects are 0.x and a minor release can break (maintainer, 2026-11-03, "as you recommend for now"); an exact pin is a release choice ([Roadmap > Working Mode: Fluid Dependencies](../00%20Home/Roadmap.md#working-mode-fluid-dependencies)).

Each dependency needs a reason under [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md): a library only where building the same would be a project of its own. The ADR's table reviews these.

Dev dependencies (the TEL project's set): `pytest`, `ruff`, `mypy`, `hypothesis` where useful.

## Tooling

| Item | Choice | Source |
|---|---|---|
| Build backend | `hatchling`, wheel target `src/tess_shell` | TEL's `pyproject.toml` |
| Environment and installs | `uv`, with the venv outside the repository | The maintainer's layout |
| Lint and format | `ruff`, line length 100, rules `E F I B UP` | TEL's `pyproject.toml` |
| Types | `mypy`, the package fully typed | TEL's choice |
| Tests | `pytest`, markers described in [Testing Strategy](../60%20Quality/Testing%20Strategy.md) | TEL's choice |
| Version | one source: `tess_shell.__version__`; changes listed in `CHANGELOG.md` | TEL's practice |
| Licence | MIT | [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) |

## Open Questions

1. [ ] The PyPI name `tesserae-shell`: register it when the first release nears; it is free today.
2. [ ] Whether `services/` splits into its own library later (the D-Bus layer is useful beyond the shell); not now.
3. [ ] A shipped-module folder layout: `modules/<name>/` with the TDL and Python files side by side, as user modules are ([Module File](../41%20TDL%20Reference/Module%20File.md)).
4. [ ] Whether the import rules are enforced with `import-linter` or with a small test of our own.

## Acceptance Criteria

- [ ] `uv sync` in the repository gives a working environment that imports `tess_shell`.
- [ ] `tesserae-shell version` prints the shell, tess_re, tess_el and tess_dl versions.
- [ ] A test fails if `binder/` imports another part of `tess_shell`.
- [ ] A test fails if a package imports one its row in the import table forbids.
- [ ] `ruff` and `mypy` pass on a clean checkout.
- [ ] `docs/` is untouched by any build or test.

## Links

- [Layers and Components](Layers%20and%20Components.md) · [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) · [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) · [Development Readiness](../00%20Home/Development%20Readiness.md) · [Testing Strategy](../60%20Quality/Testing%20Strategy.md) · [20 Architecture](20%20Architecture.md)
