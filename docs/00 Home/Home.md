---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-11-03
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
| Phase               | Design with staged development ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). M0 started 2026-11-03 ([M0 Brief](M0%20Brief.md)).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Updated             | 2026-11-02 |
| Last change         | M0 decisions recorded: the code session waits for `tesserae-engine` 0.6.0; `check` is syntax-only in M0 ([M0 Brief](M0%20Brief.md)) |
| Decided             | [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md), [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md) to [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) (16 accepted; ADR-0002 superseded)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Waiting on you      | Read the four new Integration specs ([Integration](../40%20Specifications/Integration/Integration.md)); permission for the throwaway shortcut-registration test ([Global Shortcuts > Open Questions](../40%20Specifications/Integration/Global%20Shortcuts.md#open-questions)); the list of built-in shell actions; shipping the icon licence texts; the `TRE:` release number to pin (tre 0.5.10 is out; `TEL:` is 0.1); whether the TEL dependency is a range during development ([Roadmap > Working Mode: Fluid Dependencies](Roadmap.md#working-mode-fluid-dependencies)); the `.desktop` file id for delivery ([Portals](../40%20Specifications/Integration/Portals.md)) |
| Next                | The code session builds M0 ([M0 Brief](M0%20Brief.md)); this session takes its design questions and writes the shipped-module list, accessibility, the security model and delivery basics |
| Blocked             | Nothing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Tracking            | The GitHub copy: `docs/` in the tess-shell clone is generated from this vault by `tools/sync_docs.py` through a post-commit hook (log `~/.cache/tess-shell-docs-sync.log`); the Obsidian Git plugin no longer pushes or pulls |
| Deferred to testing | The elevation curve and the 64 px figure, until tre's shadows are seen ([Style Schema](../41%20TDL%20Reference/Style%20Schema.md)); Which global settings belong in `settings.tdl` ([Settings File](../41%20TDL%20Reference/Settings%20File.md)); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([ADR-0001 Shell Surface Strategy > Open items](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md#open-items)); how KWin presents mirrored outputs ([V1 Scope > Multi-monitor](../10%20Vision/V1%20Scope.md#multi-monitor)); the four reservers plus the painter on KWin and a 4K Frame with many joins ([Frame](../40%20Specifications/Surfaces/Frame.md)); fractional scale at 1.5x ([Frame](../40%20Specifications/Surfaces/Frame.md)); fullscreen stacking and detection ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](../40%20Specifications/Surfaces/Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)); Bar over a Plasma panel ([Bar](../40%20Specifications/Surfaces/Bar.md)) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-11-02 | TDL-REQ-001 from `tess-dl` applied: 22 error codes, grammar rules ([TDL Language](../41%20TDL%20Reference/TDL%20Language.md), [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) D93, D94) |
| 2026-11-03 | M0: the session waits for tess_re 0.6.0; `check` stays syntax-only ([M0 Brief](M0%20Brief.md)) |
| 2026-11-03 | M0 started; [M0 Brief](M0%20Brief.md) written; dependency ranges set |
| 2026-11-03 | Dependency minimums follow the new import names (TEL 0.1.2, tdl 0.1.1, tre 0.6.0 pending) |
| 2026-11-03 | Repo names and PyPI names confirmed; Tesserae UI links updated to `tess-ui` ([Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md)) |
| 2026-11-03 | Import names changed: `tess_re`, `tess_ui`, `tess_el`, `tess_dl`, `tess_shell` (D95, [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md)) |
| 2026-11-03 | `tesserae-dl` 0.1.0 published (tdl first slice done); [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) dependency updated |
| 2026-11-02 | ADR-0015 and ADR-0016 accepted; [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) and [Testing Strategy](../60%20Quality/Testing%20Strategy.md) written |

## Go to

| Track             | Notes                                                                                                                                                                                                                                                                                                                                                                                           |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Project           | [Index](Index.md) · [Roadmap](Roadmap.md) · [Glossary](Glossary.md) · AGENTS                                                                                                                                                                                                                        |
| Unknowns and risk | [Open Questions](Open%20Questions.md) · [Risk Register](Risk%20Register.md)                                                                                                                                                                                                                                                                                                              |
| Decisions         | [30 Decisions](../30%20Decisions/30%20Decisions.md)                                                                                                                                                                                                                                                                                                                                                         |
| Research          | [90 Research](../90%20Research/90%20Research.md): [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md), [Shadows on Layer Surfaces](../90%20Research/Shadows%20on%20Layer%20Surfaces.md), [Hit Testing for Concave Corners](../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md), [D-Bus Libraries for Python](../90%20Research/D-Bus%20Libraries%20for%20Python.md), [Logging with Loguru](../90%20Research/Logging%20with%20Loguru.md), [Expression Languages for YAML](../90%20Research/Expression%20Languages%20for%20YAML.md), [Shell File Syntax Comparison](../90%20Research/Shell%20File%20Syntax%20Comparison.md)                                                                                                   |
| Design areas      | [10 Vision](../10%20Vision/10%20Vision.md) · [20 Architecture](../20%20Architecture/20%20Architecture.md) · [40 Specifications](../40%20Specifications/40%20Specifications.md) · [41 TDL Reference](../41%20TDL%20Reference/41%20TDL%20Reference.md) · [42 Python API](../42%20Python%20API/42%20Python%20API.md) · [50 Design System](../50%20Design%20System/50%20Design%20System.md) · [60 Quality](../60%20Quality/60%20Quality.md) · 70 Delivery · [80 Requests](../80%20Requests/80%20Requests.md) |

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
