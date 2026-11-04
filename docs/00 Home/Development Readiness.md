---
title: Development Readiness
aliases: [Readiness, Ready to Code, Milestone Plan]
type: moc
status: review
owner: phil
created: 2026-11-02
updated: 2026-11-03
tags: [moc, roadmap]
---

# Development Readiness

> [!NOTE]
> Where the design stands against the rule that coding starts only when every row of the checklist is `stable` or deferred by an accepted ADR (AGENTS > 12. Design Completeness Checklist), and a proposal for starting in stages instead of waiting for every row. The maintainer's stance is that TDL, TEL, tre and the shell are developed together and the design stays open to change ([Roadmap > Working Mode: Fluid Dependencies](Roadmap.md#working-mode-fluid-dependencies)). Everything below is a proposal; the maintainer decides (AGENTS > 2. Hard Rules rule 5). Written 2026-11-02 from the note statuses at that date.

## Where Each Row Stands

Status is the lowest status among the row's notes. "Needed for" names the first milestone ([Proposed Milestones](#proposed-milestones)) that cannot go on without it.

| Row | State | Missing or open | Needed for |
|---|---|---|---|
| Vision | stable | Nothing | n/a |
| Architecture | draft | [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) is accepted; [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) is written (draft) | M0 |
| Surfaces | review | [Popup](../40%20Specifications/Surfaces/Popup.md) is draft; the Panel position key is settled (`Inset`) | M3 |
| Integration | draft | Written; live tests (shortcut registration from Python, portal change signals, tray host beside plasmashell) are deferred to the testing phase | M5 |
| Runtime | review | [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md), [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md), [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md), [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md), [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md), [Logging](../40%20Specifications/Runtime/Logging.md) are written; the settings list ([Settings File](../41%20TDL%20Reference/Settings%20File.md)) is deferred | M0 |
| Python API | draft | Module contract and context are drafts; no surface or widget API for Python-built shells, no registry API, no package layout and version policy | M2 |
| TDL reference | draft | `tess-dl` owns the language; the shell schema notes are drafts; the built-in actions list and the event and action vocabulary are open | M1 |
| Design system | draft | [Building Blocks](../50%20Design%20System/Building%20Blocks.md) and [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) exist; the shipped-module list, principles, token values (colour, type, shape, motion, elevation curve) and iconography are not written | M1 for blocks, M2 for modules |
| Quality | draft | [Performance Budgets](../60%20Quality/Performance%20Budgets.md) and [Testing Strategy](../60%20Quality/Testing%20Strategy.md) are written; accessibility, security model and crash recovery are not | M2 for accessibility and security, M6 for recovery |
| Delivery | none | Packaging, install and autostart, versioning and release, licensing; the `.desktop` file for portal calls ([Portals](../40%20Specifications/Integration/Portals.md)) | M6 |
| Engine requests | review | TRE-REQ-001 to 009 are released or in tre 0.5.10; nothing blocks | n/a |
| Decisions | 16 accepted (ADR-0002 superseded) | [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) and [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) accepted 2026-11-02 | n/a |

## What Already Exists to Build On

- `tess_dl` is published: `tesserae-dl` 0.1.1 is on PyPI (checked 2026-11-03; the first release importing as `tess_dl`; 0.1.0 imported as `tdl`; Python 3.14 or later, no dependencies), with the language reference, the API and a conformance corpus in the `tess-dl` repository ([TDL Library API](../42%20Python%20API/TDL%20Library%20API.md)).
- TEL 0.1.2 and tre 0.6.0 are on PyPI (imports `tess_el`, `tess_re`), with `Window.build`, `Window.apply` and `Node.set_children` ([TRE-REQ-009 Batch and Tree Building](../80%20Requests/TRE-REQ-009%20Batch%20and%20Tree%20Building.md)).
- The `tess-shell` repository exists with the docs export and the sync tool; it holds no code, no `pyproject.toml` and no package yet.

## Proposed Milestones

Each milestone is a vertical slice that runs, so the design is tested early. The notes in "Needs" must reach `review` before the milestone starts; the rest can follow while it is built.

| # | Milestone | What works at the end | Needs |
|---|---|---|---|
| M0 | Skeleton | `tesserae-shell run`, `check`, `version`; config directory, logging, lock, start and stop with no windows; `pyproject.toml` with the dependencies; tests run headless | [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md), [Logging](../40%20Specifications/Runtime/Logging.md), [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md), the package layout, the testing strategy |
| M1 | A static Bar ([M1 Brief](M1%20Brief.md)) | One `Bar` on one monitor from a `.tdl` file: `tess_dl` parse, a minimal schema check, the binder with the table for `Box`, `FlexBox`, `Text`, `Rectangle`, `Svg`; a `LayerWindow`; the Clock as a fixed string | [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) accepted, [Bar](../40%20Specifications/Surfaces/Bar.md), [Block Reference](../41%20TDL%20Reference/Block%20Reference.md), [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) |
| M2 | Live and modular | TEL slots and tracked updates, the value store, the module contract (Clock updates every second), hot reload by keyed diff | [Module Contract](../42%20Python%20API/Module%20Contract.md), [Module Context](../42%20Python%20API/Module%20Context.md), [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md), the shipped-module list |
| M3 | More surfaces | `Panel`, `Popup`, `Frame`, multi-monitor and hot-plug, shadows | [Panel](../40%20Specifications/Surfaces/Panel.md), [Popup](../40%20Specifications/Surfaces/Popup.md), [Frame](../40%20Specifications/Surfaces/Frame.md), [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) |
| M4 | Services | The D-Bus service layer, then Workspaces, Battery, Network, Audio, Media, Tray one at a time | [D-Bus Service Layer](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md), the module specs |
| M5 | Desktop integration | The KWin script, global shortcuts, portal settings, fullscreen hiding | [KWin Integration](../40%20Specifications/Integration/KWin%20Integration.md), [Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md), [Portals](../40%20Specifications/Integration/Portals.md) |
| M6 | Release | Packaging, autostart, the `.desktop` file, version policy, security model | `70 Delivery` (to write) |

M0 and M1 are the smallest steps that prove the layering: a file is read by `tess_dl`, bound to tre by the binder, and shown on screen.

## Design Work Before M0 and M1

Recommended order. Each item is small and unblocks code.

1. Done: [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) accepted, Option A (2026-11-02).
2. Done (draft): [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) — the layout and the dependency list: `src/tess_shell/`, the binder as a package that imports nothing from the shell, `tests/`, the minimums `tesserae-engine>=0.5.10` once the binder uses `Window.build`, `tesserae-el>=0.1.0`, `tesserae-dl` (from its first release), `dbus-fast`, `loguru` ([Roadmap > Working Mode: Fluid Dependencies](Roadmap.md#working-mode-fluid-dependencies)).
3. Done (draft): [Testing Strategy](../60%20Quality/Testing%20Strategy.md) — headless windows with tre's `window.simulate` and `snapshot`, the `tess_dl` corpus, the binder-table-against-Block-Reference test, and the budget tests ([Performance Budgets](../60%20Quality/Performance%20Budgets.md)).
4. Write the shipped-module list ([V1 Widgets](../50%20Design%20System/V1%20Widgets.md)), needed from M2.
5. Write a short accessibility note for v1 (roles and names are already in [Block Reference](../41%20TDL%20Reference/Block%20Reference.md); keyboard reach, contrast and reduced motion come from [Portals](../40%20Specifications/Integration/Portals.md)).
6. Write the security model for user Python or defer it by ADR with the risk kept in [Risk Register](Risk%20Register.md) R-19.
7. Write the delivery basics (packaging, autostart, the `.desktop` file) before M6.

## The Staged Start (Accepted)

[ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) (accepted 2026-11-02) defers the rows that a milestone does not need to the milestone that does. M0 is built and pushed (maintainer, 2026-11-03): 97 tests pass and `run` idles at 0.017 % of one core ([M0 Brief > Result (2026-11-03)](M0%20Brief.md#result-2026-11-03)). M1 is next ([M1 Brief](M1%20Brief.md)). Each later milestone starts when its "Needs" notes are at `review`.

## Questions for the Maintainer

All five were answered on 2026-11-02.

1. [x] The milestone plan is agreed ("agree").
2. [x] [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) Option A is accepted.
3. [x] The staged start and the deferral ADR are agreed ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)).
4. [x] The recommended order of design work is fine: the binder, then the package layout, then the testing strategy; then the shipped-module list and the rest.
5. [x] The code goes in `tess-shell` under `src/tess_shell/` and `tests/`, with `docs/` kept as the export.

Open: when M0 starts, and the next design items in the order above (the shipped-module list, accessibility, the security model, delivery basics).

## Links

- [Home](Home.md) · [Roadmap](Roadmap.md) · [Open Questions](Open%20Questions.md) · [Risk Register](Risk%20Register.md) · [Performance Budgets](../60%20Quality/Performance%20Budgets.md)
