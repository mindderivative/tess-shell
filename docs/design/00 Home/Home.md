---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-11-20
tags:
  - moc
---

# Tesserae Shell

> [!IMPORTANT]
> **Phase: design only**
> A tool for building desktop shells (bars, panels, docks, launchers, OSDs, widgets) that run alongside KDE Plasma on Wayland. Built on the **tre** engine with Python logic and a front-end in TDL, the Tesserae Data Language. No code is written until the [Roadmap](Roadmap.md) checklist is `stable` or deferred by an ADR.

## Status

<!-- Maintained by the agent after every change (AGENTS.md section 11). Replace the values; do not append. -->

|                     |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Phase               | Design with staged development ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). M0 to M6 built; M7 hardening (release 0.2.0) is built apart from the maintainer's real-KWin and attended checks ([M7 Brief](M7%20Brief.md), [M7 Build Log](M7%20Build%20Log.md)); M8 use-case sweep to be decided |
| Updated | 2026-11-21 |
| Last change | 2026-11-21: M7a to M7k folded into the specs; schema 1.12 to 1.15 (default stylesheet [ADR-0022 Default Stylesheet](../30%20Decisions/ADR-0022%20Default%20Stylesheet.md), content-sized Panels, `Active_Descendant` [ADR-0023 Active Descendant Key](../30%20Decisions/ADR-0023%20Active%20Descendant%20Key.md)) |
| Decided             | [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md), [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md) to [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) and [ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md) (20 accepted; ADR-0002 superseded); [ADR-0021 Audio Access](../30%20Decisions/ADR-0021%20Audio%20Access.md) (decided 2026-11-13, confirmed by the maintainer 2026-11-16) |
| Waiting on you | Real-KWin checks: M7j with Orca (M7k click-away and M7i content-sized Panels verified on KWin, 2026-11-21); PR #118 (AT-SPI contract test) is open. Attended measurements: M7a2 cell P and the M7c budgets. Earlier small decisions are listed in [Security Model](../60%20Quality/Security%20Model.md), [Crash Recovery and Watchdog](../60%20Quality/Crash%20Recovery%20and%20Watchdog.md), [Version Policy and Migration](../70%20Delivery/Version%20Policy%20and%20Migration.md) and [Shell File](../41%20TDL%20Reference/Shell%20File.md) |
| Next | The vault folds the code session's reports as they arrive; the code session fixes what the KWin checks find; M8 is decided after M7 has been seen ([M7 Brief](M7%20Brief.md)); the shell's next release is yours to name |
| Blocked | Nothing known; the weekly usage limit noted earlier reset on 2026-11-17 |
| Tracking            | The GitHub copy: `docs/` in the tess-shell clone is generated from this vault by `tools/sync_docs.py` through a post-commit hook (log `~/.cache/tess-shell-docs-sync.log`); the Obsidian Git plugin no longer pushes or pulls |
| Deferred to testing | The elevation curve and the 64 px figure, until tre's shadows are seen ([Style Schema](../41%20TDL%20Reference/Style%20Schema.md)); Which global settings belong in `settings.tdl` ([Settings File](../41%20TDL%20Reference/Settings%20File.md)); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([ADR-0001 Shell Surface Strategy > Open items](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md#open-items)); how KWin presents mirrored outputs ([V1 Scope > Multi-monitor](../10%20Vision/V1%20Scope.md#multi-monitor)); the four reservers plus the painter on KWin and a 4K Frame with many joins ([Frame](../40%20Specifications/Surfaces/Frame.md)); fractional scale at 1.5x ([Frame](../40%20Specifications/Surfaces/Frame.md)); fullscreen stacking and detection ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](../40%20Specifications/Surfaces/Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)); Bar over a Plasma panel ([Bar](../40%20Specifications/Surfaces/Bar.md)) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-11-21 | M7 folded: status, schema 1.12 to 1.15, unverified KWin checks ([M7 Brief](M7%20Brief.md)) |
| 2026-11-21 | Absent `Appearance.Stylesheets` now means `[Default]` ([ADR-0022 Default Stylesheet](../30%20Decisions/ADR-0022%20Default%20Stylesheet.md), accepted) |
| 2026-11-20 | AGENTS.md cut from 315 to under 100 lines; reference material moved to [Vault Reference](Vault%20Reference.md) |
| 2026-11-17 | Four M7 specs and three tre requests drafted ([M7 Brief](M7%20Brief.md), [TRE-REQ-022 Content-Sized Layer Surface](../80%20Requests/TRE-REQ-022%20Content-Sized%20Layer%20Surface.md)) |
| 2026-11-17 | Plan for the next milestones: M7 hardening and M8 use-case sweep ([M7 Brief](M7%20Brief.md)) |
| 2026-11-16 | Two tre requests drafted; work plan done; 0.1.2 released ([TRE-REQ-020 Layer Window Update Before the Surface Exists](../80%20Requests/TRE-REQ-020%20Layer%20Window%20Update%20Before%20the%20Surface%20Exists.md), [TRE-REQ-021 Announce Without a Node](../80%20Requests/TRE-REQ-021%20Announce%20Without%20a%20Node.md), [Next Work Plan](Next%20Work%20Plan.md)) |
| 2026-11-16 | Work plan for the code session written and sent ([Next Work Plan](Next%20Work%20Plan.md)) |
| 2026-11-15 | Docs publishing automated: vault commit to live site, no manual step ([Docs Publishing](../70%20Delivery/Docs%20Publishing.md)) |
| 2026-11-15 | Request to tre drafted; portal settings as built, with questions ([TRE-REQ-019 Popup Close Before Placement](../80%20Requests/TRE-REQ-019%20Popup%20Close%20Before%20Placement.md), [Portals](../40%20Specifications/Integration/Portals.md), [Popup](../40%20Specifications/Surfaces/Popup.md)) |

## Go to

| Track             | Notes                                                                                                                                                                                                                                                                                                                                                                                           |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Project           | [Index](Index.md) · [Roadmap](Roadmap.md) · [Glossary](Glossary.md) · AGENTS · [Vault Reference](Vault%20Reference.md) · [M7 Brief](M7%20Brief.md) · [Next Work Plan](Next%20Work%20Plan.md) · [Hand Checks](Hand%20Checks.md) · [Docs Publishing](../70%20Delivery/Docs%20Publishing.md) · [Tesserae Shell Directive](Tesserae%20Shell%20Directive.md) · [Orchestration Log](Orchestration%20Log.md) · [Task Owners](Task%20Owners.md)                                                                                                                                                                                                                        |
| Unknowns and risk | [Open Questions](Open%20Questions.md) · [Risk Register](Risk%20Register.md)                                                                                                                                                                                                                                                                                                              |
| Decisions         | [30 Decisions](../30%20Decisions/30%20Decisions.md)                                                                                                                                                                                                                                                                                                                                                         |
| Research          | [90 Research](../90%20Research/90%20Research.md): [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md), [Shadows on Layer Surfaces](../90%20Research/Shadows%20on%20Layer%20Surfaces.md), [Hit Testing for Concave Corners](../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md), [D-Bus Libraries for Python](../90%20Research/D-Bus%20Libraries%20for%20Python.md), [Logging with Loguru](../90%20Research/Logging%20with%20Loguru.md), [Expression Languages for YAML](../90%20Research/Expression%20Languages%20for%20YAML.md), [Shell File Syntax Comparison](../90%20Research/Shell%20File%20Syntax%20Comparison.md)                                                                                                   |

## Current


1. [10 Vision](../10%20Vision/10%20Vision.md) is confirmed (`stable`); confirm the draft [20 Architecture](../20%20Architecture/20%20Architecture.md) notes, then module and integration specs.
2. Seed [Open Questions](Open%20Questions.md) from the known gaps in AGENTS §4.


> [!WARNING]
> **Critical path**
> tre 0.5.8 has layer surfaces ([ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md)). The shell's own view layer on tre is the largest piece to design ([ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md)).

## Decisions

> [!NOTE]
> This is an Obsidian view of `Home.base` (section Decisions) and is not shown on GitHub.

Only the maintainer moves an ADR from `proposed` to `accepted`.

## Needs Verification

Claims tagged `#needs-verification`. Each must be sourced or listed in [Open Questions](Open%20Questions.md).

> [!NOTE]
> This is an Obsidian view of `Home.base` (section Needs verification) and is not shown on GitHub.

## Recently Updated

> [!NOTE]
> This is an Obsidian view of `Home.base` (section Recently updated) and is not shown on GitHub.

## Coverage

Which design areas have notes, and how mature they are. A folder missing from the list has not been started.

> [!NOTE]
> This is an Obsidian view of `Home.base` (section By folder) and is not shown on GitHub.

> [!NOTE]
> This is an Obsidian view of `Home.base` (section By status) and is not shown on GitHub.

## Upstream Baselines


| Project  | Role                                                                                                                                     | Docs                                       | Baseline |
|----------|------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|----------|
| tre      | Rendering engine (Rust, Python module `tess_re`)                                                                                             | [docs](https://mindderivative.github.io/tre/) | 0.5.9    |
| Tesserae | Separate project: declarative app framework (`tesserae-ui`). Reference only, not a dependency ([ADR-0006 Shell Independent of Tesserae UI](../30%20Decisions/ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md)). | [docs](https://mindderivative.github.io/tess-ui/) | 0.5.1    |

Versions drift. If the live docs disagree with this table, the docs win; update the table.


## Session Routine

1. Read AGENTS, [Index](Index.md), [Open Questions](Open%20Questions.md) and [Roadmap](Roadmap.md).
2. Extend an existing note before creating a new one.
3. Record decisions as `proposed` ADRs, unknowns in [Open Questions](Open%20Questions.md), risks in [Risk Register](Risk%20Register.md).
4. Commit locally after each task. Never push without an explicit instruction.
