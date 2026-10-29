---
title: 30 Decisions
aliases: [Decisions, ADR Index]
type: moc
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [moc, adr]
related: ["[[Index]]", "[[AGENTS]]"]
depends_on: []
---

# 30 Decisions

| ADR                                     | Decision                                                                            | Status                 |
|-----------------------------------------|-------------------------------------------------------------------------------------|------------------------|
| [[ADR-0001 Shell Surface Strategy]] | Layer surfaces in tre (Option A)                                                    | accepted 2026-10-25    |
| [[ADR-0002 Relationship to Tesserae UI]] | Depend on `tesserae-ui`                                                             | superseded by ADR-0006 |
| [[ADR-0003 Process Model]] | One process, one event loop                                                         | accepted 2026-10-25    |
| [[ADR-0004 Plasma Coexistence]] | Coexist by default, replace per service with an ADR                                 | accepted 2026-10-25    |
| [[ADR-0005 Global Shortcuts]] | KDE global-accel service                                                            | accepted 2026-10-25    |
| [[ADR-0006 Shell Independent of Tesserae UI]] | Separate project on tre; no `tesserae-ui` dependency                                | accepted 2026-10-25    |
| [[ADR-0007 Shell UI Layer]] | A small shell-owned view layer on tre                                               | accepted 2026-10-25    |
| [[ADR-0008 Tesserae Expression Language]] | A separate expression-language library (TEL)                                        | accepted 2026-10-25    |
| [[ADR-0009 D-Bus Client Library]] | `dbus-fast` on a shared asyncio service thread                                      | accepted 2026-10-26    |
| [[ADR-0010 Surface Shadows]] | Shadows drawn inside the surface with a transparent margin                          | accepted 2026-10-27    |
| [[ADR-0011 JSON Schema for Shell Files]] | JSON Schema generated from block and module declarations, for editors and the shell | accepted 2026-10-27    |
| [[ADR-0012 Keeping the Shell Above Plasma Panels]] | Ways to keep the Bar above a Plasma panel: KWin rules, a KWin script, others        | accepted 2026-10-27    |
| [[ADR-0013 Control Interface]] | One D-Bus interface for commands and the KWin script (A socket, B D-Bus, C both)    | accepted 2026-10-28    |
