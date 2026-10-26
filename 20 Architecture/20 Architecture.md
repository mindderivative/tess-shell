---
title: 20 Architecture
aliases: [Architecture, Architecture Index]
type: moc
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [moc, architecture]
related: ["[[Index]]", "[[AGENTS]]"]
depends_on: []
---

# 20 Architecture

How Tesserae Shell is put together. The decisions behind it are the ADRs in [[30 Decisions]]; these notes show where each lands.

| Note | Purpose | Status |
|---|---|---|
| [[System Context]] | Who the shell talks to: KWin, D-Bus services, the config directory | draft |
| [[Layers and Components]] | tre, TEL, the shell's UI layer, the runtime, modules; dependency rules | draft |
| [[Process Model and Threading]] | One process, one loop; threads, hand-off, lifecycle, failure | draft |
| [[Data Flow]] | Loading, live data, hot reload, monitor hot-plug, input | draft |

All four are proposals built on accepted ADRs. They are marked where they add a proposal beyond an ADR. The maintainer decides what becomes `stable`.
