---
title: ADR-0015 Render Binder
aliases: [ADR-0015, Render Binder, Table-Driven Binder, Binder]
type: adr
status: accepted
owner: phil
created: 2026-11-02
updated: 2026-11-03
tags: [adr, architecture, performance]
---

# ADR-0015: Render Binder

> [!NOTE]
> Who turns a parsed TDL file into tre nodes? Accepted (Option A, maintainer, 2026-11-02): a generic, table-driven binder inside the shell package. `tess_dl` reads the file and stops. The shell checks and types the tree, and the binder applies a table (block to tre node kind, key to tre property) to build nodes, link `{{ }}` slots to node properties, and update only what changed. The binder imports nothing from the shell, so it can be split into its own library later. Accepted by the maintainer in chat on 2026-11-02 ("accept option a").

## Context

The maintainer asked whether `tess_dl` sends render requests to tre, or the shell does, and compared WPF, where XAML only describes objects and the framework builds and renders them (2026-11-02). Facts that shape the choice:

- tre builds its tree one call at a time from Python: `Window.create(kind, **props)`, `Node.add_child` and `Node.set(**props)`. tre 0.5.10 adds `Window.build(spec)` (a whole detached subtree from a dict, checked as a whole, returning the root and an id-to-node mapping), `Window.apply([(node, props), ...])` (all-or-nothing changes to many nodes) and `Node.set_children(list)` ([TRE-REQ-009 Batch and Tree Building](../80%20Requests/TRE-REQ-009%20Batch%20and%20Tree%20Building.md), tre #253). A plain `add_child` is constant time since 0.5.10.
- The cost of a call across the Python-to-Rust boundary is about a microsecond, and a 3,100-node tree builds in a few milliseconds (tre's medians: 6.6 ms; the shell's single run: 3.8 ms). Call count is not the bottleneck at the expected size. tre also found that `build` is not faster than per-node calls (5.3 ms against 4.9 ms for 3,100 nodes); its gain is the all-or-nothing check and fewer lines.
- `tess_dl` is structure-only and independent of tre, TEL and the shell (D25, D66). It cannot know what a `Bar` means.
- No frame is drawn while a Python callback runs (a `call_soon` callback runs between frames, [tre threading guide](https://mindderivative.github.io/tre/guide/threading/)), so building in one callback shows no half-built tree. Whether a change made in a callback appears in the same frame or the next is not documented. #needs-verification

## Options

### Option A — A Table-Driven Binder in the Shell Package (Recommended)

The shell passes the typed tree to the binder. The binder holds two tables: block to tre node kind with fixed properties, and key to tre property with a converter. It walks the tree, builds each subtree detached, attaches the root last, records links from slots to node properties, and exposes `build`, `update`, `rebuild` and `dispose`. It imports nothing from the shell and is written so that it can be split out ([ADR-0014 Shell File Language](ADR-0014%20Shell%20File%20Language.md) item 9 did the same for the parser).

- **For:** one generic walk replaces per-widget code; a new block is a new table row; the table is data, so a second front end (Tesserae UI, later) could supply its own; hot reload is a diff by key; the shell keeps its own work (surfaces, services, modules); the existing "tre" column in [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) is the table.
- **Against:** a new layer to design and test; the table and the Block Reference must not drift apart.

### Option B — A Separate Library From the Start

The same binder, in its own repository and package.

- **For:** clean boundary from day one; reusable.
- **Against:** a new project to run before the first bar works; its API would be guessed before the shell has used it. Recommendation: start as Option A and split when the API has settled.

### Option C — Per-Widget Code in the Shell

Python classes for `Text`, `FlexBox` and the rest, each creating its own tre nodes.

- **For:** straightforward.
- **Against:** every block and key needs code; the Python builder and the TDL path would each need to be kept in step; the table in the Block Reference would be documentation only.

### Option D — `tess_dl` Calls tre Directly

- **Against:** `tess_dl` would need tre, TEL, the schema, styles and modules, which makes it the shell and breaks its independence and the lossless-tree guarantee. Rejected.

## Decision

Accepted 2026-11-02 by the maintainer in chat ("accept option a"): **Option A**, a table-driven binder in the shell package that imports nothing from the shell. It is split into its own library later only if its API settles and a second user appears (Option B stays open).

## Consequences

With Option A accepted:

- [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) gets a Render binder component and the dependency rule that the binder imports neither the shell nor `tess_dl`'s parser internals; [Data Flow > Loading a Shell](../20%20Architecture/Data%20Flow.md#loading-a-shell) gets a "bind to tre" step after the shell model is built.
- The block and key tables live in code with a test that checks them against the "tre" columns of [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and [Style Schema](../41%20TDL%20Reference/Style%20Schema.md), so the documents and the code cannot drift apart.
- The binder uses `Window.build`, `Window.apply` and `Node.set_children` (tre 0.5.10 or later), which raises the shell's minimum tre to 0.5.10 when the binder is built ([Roadmap > Working Mode: Fluid Dependencies](../00%20Home/Roadmap.md#working-mode-fluid-dependencies)).
- Hot reload becomes a keyed diff between two typed trees; `For` entries use TEL's entry names (`<name>_0001`, D65).
- A slot's link is created from the tracked paths TEL reports (`evaluate_tracked`, T20); an update runs only the links whose paths changed.
- An error while binding (a value tre refuses) is reported with the `file:line:column` of the key that caused it, because the tree carries positions.
- Open for the design: the shape of the converters (enums, lengths, colours, four-sided values), how the binder holds nodes for `If` and `For` branches, how it passes style resolution, and what a module-supplied node looks like.

## Links

- [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) · [Data Flow](../20%20Architecture/Data%20Flow.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [TDL Library API](../42%20Python%20API/TDL%20Library%20API.md) · [TRE-REQ-009 Batch and Tree Building](../80%20Requests/TRE-REQ-009%20Batch%20and%20Tree%20Building.md) · [ADR-0014 Shell File Language](ADR-0014%20Shell%20File%20Language.md) · [30 Decisions](30%20Decisions.md)
