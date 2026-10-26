---
title: 80 Engine Requests
aliases: [Engine Requests, TRE-REQ Index]
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-10-25
tags: [moc, engine-request]
related: ["[[Index]]", "[[AGENTS]]"]
depends_on: []
---

# 80 Engine Requests

Scoped requests for tre and Tesserae. Each is written here and carried upstream by the maintainer; none is filed from this vault ([[AGENTS#6. Engine requests (tre / Tesserae)]]).

| Request | Status | Blocks | Decision |
|---|---|---|---|
| [[TRE-REQ-001 Layer Surface Window]] | stable (confirmed 2026-10-25). Released in tre 0.5.8 (tre #195 closed) | Nothing in the engine; surface specs name the untested gaps that affect them | [[ADR-0001 Shell Surface Strategy]] (Option A, accepted) |
| [[TRE-REQ-004 Tesserae Layer and Popup Windows]] | draft. Addressed to Tesserae | Surface specs (opening a view as a layer or popup window) | [[ADR-0002 Relationship to Tesserae UI]] |

Not written: `TRE-REQ-002` (external-surface hand-off, ADR-0001 Option B). Write it only if TRE-REQ-001 proves infeasible.
