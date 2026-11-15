---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-11-15
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
| Phase               | Design with staged development ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). M0 built 2026-11-03 ([M0 Brief](M0%20Brief.md)); M1, M2 and M3 built and KWin-checked ([M1 Brief](M1%20Brief.md), [M2 Brief](M2%20Brief.md), [M3 Brief](M3%20Brief.md)); M3 confirmed completed by the maintainer 2026-11-08. Planned: M4 widgets ([M4 Brief](M4%20Brief.md)), M5 services and desktop integration in parts ([M5 Brief](M5%20Brief.md)), M6 focus and keyboard ([M6 Brief](M6%20Brief.md)), M7 release. |
| Updated | 2026-11-15 |
| Last change | 2026-11-15: the maintainer's KWin hand check of M6c shortcuts passed except one real gap: the real shortcut service accepts a key another component owns, so the shell must ask `isGlobalShortcutAvailable` first ([Global Shortcuts > Registration](../40%20Specifications/Integration/Global%20Shortcuts.md#registration)); tre 0.6.8 builds TRE-REQ-018 and 019; `tesserae-utils` 0.2.1 is on PyPI |
| Decided             | [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md), [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md) to [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) and [ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md) (20 accepted; ADR-0002 superseded); [ADR-0021 Audio Access](../30%20Decisions/ADR-0021%20Audio%20Access.md) (orchestrator, 2026-11-13) |
| Waiting on you | Test tre 0.6.8's Tab and popup-close changes ([TRE-REQ-018 Tab Leaves a Multi-Line Text Input](../80%20Requests/TRE-REQ-018%20Tab%20Leaves%20a%20Multi-Line%20Text%20Input.md), [TRE-REQ-019 Popup Close Before Placement](../80%20Requests/TRE-REQ-019%20Popup%20Close%20Before%20Placement.md)) and the activation token on KWin. Answer [Portals > Open Questions](../40%20Specifications/Integration/Portals.md#open-questions) 3 to 11. Everything the orchestrator decided alone (D-001 to D-059 in [Orchestration Log](Orchestration%20Log.md), [ADR-0021 Audio Access](../30%20Decisions/ADR-0021%20Audio%20Access.md)) is yours to keep or change. Whether TEL's own templates move to the new slot form too |
| Next | Yours to set. Merged on `tess-shell` `main` (read from the repository, not run here): M6a focus, shortcut mode, M6b widget keys, M5h portal settings, the Media fix, the shortcut restart test, a CI baseline. Not started: M5g (KWin and Tasks), the launcher, the user guide, `install-session`, the schema additions for the configuration application ([Task Owners](Task%20Owners.md), a closed record). The configuration application still writes the old slot form |
| Blocked | Weekly usage near its limit, reset Tuesday 2026-11-17 05:00 |
| Tracking            | The GitHub copy: `docs/` in the tess-shell clone is generated from this vault by `tools/sync_docs.py` through a post-commit hook (log `~/.cache/tess-shell-docs-sync.log`); the Obsidian Git plugin no longer pushes or pulls |
| Deferred to testing | The elevation curve and the 64 px figure, until tre's shadows are seen ([Style Schema](../41%20TDL%20Reference/Style%20Schema.md)); Which global settings belong in `settings.tdl` ([Settings File](../41%20TDL%20Reference/Settings%20File.md)); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([ADR-0001 Shell Surface Strategy > Open items](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md#open-items)); how KWin presents mirrored outputs ([V1 Scope > Multi-monitor](../10%20Vision/V1%20Scope.md#multi-monitor)); the four reservers plus the painter on KWin and a 4K Frame with many joins ([Frame](../40%20Specifications/Surfaces/Frame.md)); fractional scale at 1.5x ([Frame](../40%20Specifications/Surfaces/Frame.md)); fullscreen stacking and detection ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](../40%20Specifications/Surfaces/Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)); Bar over a Plasma panel ([Bar](../40%20Specifications/Surfaces/Bar.md)) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-11-15 | `tesserae-shell` 0.1.0 published on PyPI ([Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md)) |
| 2026-11-15 | Tab request to tre drafted; shortcut mode keeps `EXCLUSIVE` by default ([TRE-REQ-018 Tab Leaves a Multi-Line Text Input](../80%20Requests/TRE-REQ-018%20Tab%20Leaves%20a%20Multi-Line%20Text%20Input.md), [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)) |
| 2026-11-15 | Request to tre drafted; portal settings as built, with questions ([TRE-REQ-019 Popup Close Before Placement](../80%20Requests/TRE-REQ-019%20Popup%20Close%20Before%20Placement.md), [Portals](../40%20Specifications/Integration/Portals.md), [Popup](../40%20Specifications/Surfaces/Popup.md)) |
| 2026-11-14 | TDL notes and examples moved to language 0.2, the slot written `<\| \|>` ([TDL Language](../41%20TDL%20Reference/TDL%20Language.md), [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)) |
| 2026-11-14 | Directive withdrawn and archived; the maintainer directs the work again ([Tesserae Shell Directive](Tesserae%20Shell%20Directive.md), [Orchestration Log](Orchestration%20Log.md)) |
| 2026-11-13 | Launcher and shortcut actions specified; M6 tasks written; Task Owners note after the restart ([Applications Module](../40%20Specifications/Modules/Applications%20Module.md), [M6 Brief](M6%20Brief.md), [Task Owners](Task%20Owners.md)) |
| 2026-11-13 | Tray, control interface and application phase C2 merged; decisions D-038 to D-041 ([Orchestration Log](Orchestration%20Log.md)) |
| 2026-11-13 | Configuration Application specified; tess_dl edits and formatter merged ([Configuration Application](../40%20Specifications/Configuration%20Application.md), [Orchestration Log](Orchestration%20Log.md)) |

## Go to

| Track             | Notes                                                                                                                                                                                                                                                                                                                                                                                           |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Project           | [Index](Index.md) · [Roadmap](Roadmap.md) · [Glossary](Glossary.md) · AGENTS · [Tesserae Shell Directive](Tesserae%20Shell%20Directive.md) · [Orchestration Log](Orchestration%20Log.md) · [Task Owners](Task%20Owners.md)                                                                                                                                                                                                                        |
| Unknowns and risk | [Open Questions](Open%20Questions.md) · [Risk Register](Risk%20Register.md)                                                                                                                                                                                                                                                                                                              |
| Decisions         | [30 Decisions](../30%20Decisions/30%20Decisions.md)                                                                                                                                                                                                                                                                                                                                                         |
| Research          | [90 Research](../90%20Research/90%20Research.md): [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md), [Shadows on Layer Surfaces](../90%20Research/Shadows%20on%20Layer%20Surfaces.md), [Hit Testing for Concave Corners](../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md), [D-Bus Libraries for Python](../90%20Research/D-Bus%20Libraries%20for%20Python.md), [Logging with Loguru](../90%20Research/Logging%20with%20Loguru.md), [Expression Languages for YAML](../90%20Research/Expression%20Languages%20for%20YAML.md), [Shell File Syntax Comparison](../90%20Research/Shell%20File%20Syntax%20Comparison.md)                                                                                                   |
| Design areas      | [10 Vision](../10%20Vision/10%20Vision.md) · [20 Architecture](../20%20Architecture/20%20Architecture.md) · [40 Specifications](../40%20Specifications/40%20Specifications.md) · [41 TDL Reference](../41%20TDL%20Reference/41%20TDL%20Reference.md) · [42 Python API](../42%20Python%20API/42%20Python%20API.md) · [50 Design System](../50%20Design%20System/50%20Design%20System.md) · [60 Quality](../60%20Quality/60%20Quality.md) · [70 Delivery](../70%20Delivery/70%20Delivery.md) · [80 Requests](../80%20Requests/80%20Requests.md) |

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
