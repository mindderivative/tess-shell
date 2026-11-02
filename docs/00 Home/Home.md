---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-11-02
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
| Phase               | Design only. No code.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Updated             | 2026-11-02 |
| Last change         | tre's occlusion fix (#246, local branch) recorded in TRE-REQ-008 and R-24; first reviewed `docs/` commit and push in the tess-shell clone |
| Decided             | [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md), [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md) to [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) (13 accepted; ADR-0002 superseded)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Waiting on you      | the list of built-in shell actions; shipping the icon licence texts; the `TEL:` and `TRE:` release numbers to pin |
| Next                | The shipped-module list ([V1 Widgets](../50%20Design%20System/V1%20Widgets.md)); then the missing Integration notes ([Roadmap > Spec backlog (proposed order)](Roadmap.md#spec-backlog-proposed-order)) |
| Blocked             | Nothing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Tracking            | The GitHub copy: `docs/` in the tess-shell clone is generated from this vault by `tools/sync_docs.py` through a post-commit hook (log `~/.cache/tess-shell-docs-sync.log`); the Obsidian Git plugin no longer pushes or pulls |
| Deferred to testing | Which global settings belong in `settings.tdl` ([Settings File](../41%20TDL%20Reference/Settings%20File.md)); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([ADR-0001 Shell Surface Strategy > Open items](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md#open-items)); how KWin presents mirrored outputs ([V1 Scope > Multi-monitor](../10%20Vision/V1%20Scope.md#multi-monitor)); the four reservers plus the painter on KWin and a 4K Frame with many joins ([Frame](../40%20Specifications/Surfaces/Frame.md)); fractional scale at 1.5x ([Frame](../40%20Specifications/Surfaces/Frame.md)); fullscreen stacking and detection ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](../40%20Specifications/Surfaces/Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)); Bar over a Plasma panel ([Bar](../40%20Specifications/Surfaces/Bar.md)) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-11-02 | tre's occlusion fix #246 recorded ([TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Engine%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md), R-24); docs first pushed to the tess-shell clone's remote |
| 2026-11-02 | Docs export to the tess-shell clone set up (`tools/sync_docs.py`, post-commit hook); three stale heading links fixed |
| 2026-11-02 | tre built SMIL (#245) on a local branch; idle cost measured; R-24 added ([TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Engine%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md)) |
| 2026-11-01 | tre recorded the shell's answers on #245; idle-CPU measurement added as an acceptance item ([TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Engine%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md)) |
| 2026-11-01 | tre scoped SMIL as issue #245; the shell answered tre's questions ([TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Engine%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md)) |
| 2026-11-01 | Status question on SMIL sent to the `tre` session ([TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Engine%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md)) |
| 2026-11-01 | Animated icons: `mdi` only in v1; [TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Engine%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md) written |
| 2026-11-01 | Animated icons tested in tre (SMIL not played, masks drawn); icon licences present ([Block Reference](../41%20TDL%20Reference/Block%20Reference.md)) |

## Go to

| Track             | Notes                                                                                                                                                                                                                                                                                                                                                                                           |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Project           | [Index](Index.md) · [Roadmap](Roadmap.md) · [Glossary](Glossary.md) · AGENTS                                                                                                                                                                                                                        |
| Unknowns and risk | [Open Questions](Open%20Questions.md) · [Risk Register](Risk%20Register.md)                                                                                                                                                                                                                                                                                                              |
| Decisions         | [30 Decisions](../30%20Decisions/30%20Decisions.md)                                                                                                                                                                                                                                                                                                                                                         |
| Research          | [90 Research](../90%20Research/90%20Research.md): [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md), [Shadows on Layer Surfaces](../90%20Research/Shadows%20on%20Layer%20Surfaces.md), [Hit Testing for Concave Corners](../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md), [D-Bus Libraries for Python](../90%20Research/D-Bus%20Libraries%20for%20Python.md), [Logging with Loguru](../90%20Research/Logging%20with%20Loguru.md), [Expression Languages for YAML](../90%20Research/Expression%20Languages%20for%20YAML.md), [Shell File Syntax Comparison](../90%20Research/Shell%20File%20Syntax%20Comparison.md)                                                                                                   |
| Design areas      | [10 Vision](../10%20Vision/10%20Vision.md) · [20 Architecture](../20%20Architecture/20%20Architecture.md) · [40 Specifications](../40%20Specifications/40%20Specifications.md) · [41 TDL Reference](../41%20TDL%20Reference/41%20TDL%20Reference.md) · [42 Python API](../42%20Python%20API/42%20Python%20API.md) · [50 Design System](../50%20Design%20System/50%20Design%20System.md) · 60 Quality · 70 Delivery · [80 Engine Requests](../80%20Engine%20Requests/80%20Engine%20Requests.md) |

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
| tre      | Rendering engine (Rust, Python module `tre`)                                                                                             | [docs](https://mindderivative.github.io/tre/) | 0.5.9    |
| Tesserae | Separate project: declarative app framework (`tesserae-ui`). Reference only, not a dependency ([ADR-0006 Shell Independent of Tesserae UI](../30%20Decisions/ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md)). | [docs](https://mindderivative.github.io/tesserae/) | 0.5.1    |

Versions drift. If the live docs disagree with this table, the docs win; update the table.


## Session Routine

1. Read AGENTS, [Index](Index.md), [Open Questions](Open%20Questions.md) and [Roadmap](Roadmap.md).
2. Extend an existing note before creating a new one.
3. Record decisions as `proposed` ADRs, unknowns in [Open Questions](Open%20Questions.md), risks in [Risk Register](Risk%20Register.md).
4. Commit locally after each task. Never push without an explicit instruction.
