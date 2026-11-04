---
title: 80 Requests
aliases: [80 Engine Requests, Engine Requests, TRE-REQ Index]
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-11-03
tags: [moc, engine-request]
---

# 80 Requests

Scoped requests between the projects. The prefix names the project that receives the request: `TRE-REQ`, `TEL-REQ`, `TDL-REQ`, `SHELL-REQ` and `TUIF-REQ`, each with a three-digit counter; tre sends no requests (AGENTS > 6. Requests Between Projects). Only `TRE-REQ` notes exist so far. Each is written here and carried upstream by the maintainer; none is filed from this vault (AGENTS > 6. Requests Between Projects).

| Request                                 | Status                                                                 | Blocks                                                                                    | Decision                                                     |
|-----------------------------------------|------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| [TRE-REQ-001 Layer Surface Window](TRE-REQ-001%20Layer%20Surface%20Window.md) | stable (confirmed 2026-10-25). Released in tre 0.5.8 (tre #195 closed) | Nothing in the engine; surface specs name the untested gaps that affect them              | [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md) (Option A, accepted) |
| [TRE-REQ-004 Tesserae Layer and Popup Windows](TRE-REQ-004%20Tesserae%20Layer%20and%20Popup%20Windows.md) | superseded 2026-10-25. Withdrawn, never carried to Tesserae            | Nothing                                                                                   | [ADR-0006 Shell Independent of Tesserae UI](../30%20Decisions/ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md)                      |
| [TRE-REQ-005 Keep-Alive and Loop Stop](TRE-REQ-005%20Keep-Alive%20and%20Loop%20Stop.md) | stable. Released in tre 0.5.9 (2026-10-27) as #238                     | Staying alive with no windows; a clean shutdown ([Process Model and Threading > No windows: what tre offers](../20%20Architecture/Process%20Model%20and%20Threading.md#no-windows-what-tre-offers)) | [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md)                      |
| [TRE-REQ-006 Repeating Gradients](TRE-REQ-006%20Repeating%20Gradients.md) | draft. Written 2026-10-27 for the future; not filed                    | Nothing: the shell repeats stops itself if it is declined                                 | [Frame > Thickness, radii, border, colours](../40%20Specifications/Surfaces/Frame.md#thickness-radii-border-colours)                      |
| [TRE-REQ-007 Popup Body Geometry](TRE-REQ-007%20Popup%20Body%20Geometry.md) | draft. Written 2026-10-28 for the future; not filed                    | Nothing: the shell shifts `offset` by the shadow margin                                   | [Popup > Placement](../40%20Specifications/Surfaces/Popup.md#placement)                      |
| [TRE-REQ-008 SMIL Animation in SVG Nodes](TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md) | review. Taken up by tre as [tre #245](https://github.com/mindderivative/tre/issues/245); built 2026-11-02 on the local branch `svg-smil-245` (not pushed, not released) | Nothing: v1 ships only the static `mdi` icons; the animated line set waits | [Block Reference > The Icon Set Files (2026-11-01)](../41%20TDL%20Reference/Block%20Reference.md#the-icon-set-files-2026-11-01) |
| [TRE-REQ-009 Batch and Tree Building](TRE-REQ-009%20Batch%20and%20Tree%20Building.md) | review. Scoped by tre as #253 (Ready, not started), wanted in 0.5.10. Measured: about 1 µs per call, a 3,100-node tree builds in about 3.8 ms | Nothing: the shell builds per node if it is declined | [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) |
| [TRE-REQ-010 Colour Strings](TRE-REQ-010%20Colour%20Strings.md) | superseded. Withdrawn by the maintainer 2026-11-03: tre takes one entry form ([ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md)) | Nothing: the shell converts colours in its binder | [ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md) |

Not written: `TRE-REQ-002` (external-surface hand-off, ADR-0001 Option B). Write it only if TRE-REQ-001 proves infeasible.
