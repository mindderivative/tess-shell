---
title: 20 Architecture
aliases: [Architecture, Architecture Index]
type: moc
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [moc, architecture]
---

# 20 Architecture

How Tesserae Shell is put together. The decisions behind it are the ADRs in [30 Decisions](../30%20Decisions/30%20Decisions.md); these notes show where each lands.

| Note                                    | Purpose                                                                                                            | Status |
|-----------------------------------------|--------------------------------------------------------------------------------------------------------------------|--------|
| [System Context](System%20Context.md) | Who the shell talks to: KWin, D-Bus services, the config directory                                                 | draft  |
| [Layers and Components](Layers%20and%20Components.md) | tre, TEL, the shell's UI layer, the runtime, modules; dependency rules                                             | draft  |
| [Process Model and Threading](Process%20Model%20and%20Threading.md) | One process, one loop; threads, hand-off, lifecycle, failure                                                       | draft  |
| [Data Flow](Data%20Flow.md) | Loading, live data, hot reload, monitor hot-plug, input                                                            | draft  |
| [Shell Structure](Shell%20Structure.md) | The maintainer's flow diagram in words: layers, layer windows, containers, modules, widgets; differences to settle | draft  |

All four are proposals built on accepted ADRs. They are marked where they add a proposal beyond an ADR. The maintainer decides what becomes `stable`.
