---
title: 30 Decisions
aliases: [Decisions, ADR Index]
type: moc
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-29
tags: [moc, adr]
---

# 30 Decisions

| ADR                                     | Decision                                                                            | Status                 |
|-----------------------------------------|-------------------------------------------------------------------------------------|------------------------|
| [ADR-0001 Shell Surface Strategy](ADR-0001%20Shell%20Surface%20Strategy.md) | Layer surfaces in tre (Option A)                                                    | accepted 2026-10-25    |
| [ADR-0002 Relationship to Tesserae UI](ADR-0002%20Relationship%20to%20Tesserae%20UI.md) | Depend on `tesserae-ui`                                                             | superseded by ADR-0006 |
| [ADR-0003 Process Model](ADR-0003%20Process%20Model.md) | One process, one event loop                                                         | accepted 2026-10-25    |
| [ADR-0004 Plasma Coexistence](ADR-0004%20Plasma%20Coexistence.md) | Coexist by default, replace per service with an ADR                                 | accepted 2026-10-25    |
| [ADR-0005 Global Shortcuts](ADR-0005%20Global%20Shortcuts.md) | KDE global-accel service                                                            | accepted 2026-10-25    |
| [ADR-0006 Shell Independent of Tesserae UI](ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md) | Separate project on tre; no `tesserae-ui` dependency                                | accepted 2026-10-25    |
| [ADR-0007 Shell UI Layer](ADR-0007%20Shell%20UI%20Layer.md) | A small shell-owned view layer on tre                                               | accepted 2026-10-25    |
| [ADR-0008 Tesserae Expression Language](ADR-0008%20Tesserae%20Expression%20Language.md) | A separate expression-language library (TEL)                                        | accepted 2026-10-25    |
| [ADR-0009 D-Bus Client Library](ADR-0009%20D-Bus%20Client%20Library.md) | `dbus-fast` on a shared asyncio service thread                                      | accepted 2026-10-26    |
| [ADR-0010 Surface Shadows](ADR-0010%20Surface%20Shadows.md) | Shadows drawn inside the surface with a transparent margin                          | accepted 2026-10-27    |
| [ADR-0011 JSON Schema for Shell Files](ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md) | JSON Schema generated from block and module declarations, for editors and the shell | accepted 2026-10-27    |
| [ADR-0012 Keeping the Shell Above Plasma Panels](ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md) | Ways to keep the Bar above a Plasma panel: KWin rules, a KWin script, others        | accepted 2026-10-27    |
| [ADR-0013 Control Interface](ADR-0013%20Control%20Interface.md) | One D-Bus interface for commands and the KWin script (A socket, B D-Bus, C both)    | accepted 2026-10-28    |
| [ADR-0014 Shell File Language](ADR-0014%20Shell%20File%20Language.md) | A structure-only data language of the shell's own, TDL, in place of YAML (A custom, B YAML, C KDL, D QML) | accepted 2026-10-29    |
