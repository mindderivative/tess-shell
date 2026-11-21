---
title: ADR-0024 tre Never Blocks Design
aliases: [ADR-0024, tre Never Blocks a Design Change, Adjustable From Python]
type: adr
status: proposed
owner: phil
created: 2026-11-21
updated: 2026-11-21
tags: [adr, architecture/layering]
---

# ADR-0024: tre Never Blocks a Design Change

## Context

The layering principle is "mechanism in the engine, meaning and look in the layer above" ([Vault Reference > Layering principle](../00%20Home/Vault%20Reference.md#layering-principle)). The maintainer stated on 2026-11-21 (relayed by the Orchestrator) a stronger form: tre never blocks a design change. Every visual element and parameter of tre is adjustable from Python through properties, tokens or declarative hooks, with no per-frame Python. The Tesserae UX vault is to carry a matching decision record; I looked in `~/Projects/Obsidian/Tesserae UX/50 Decisions` and found ADR-0001 to ADR-0019 and none on this, so the cross-reference below is to be filled in when that ADR exists.

## Options

### Option A: adopt it as an explicit layering rule (recommended)

- A design in this vault is never reshaped to fit a fixed look inside tre. If the design needs something tre's look does not expose, that is an engine request ([Vault Reference > Requests between projects](../00%20Home/Vault%20Reference.md#requests-between-projects)) for a property, token or declarative hook; the design stays as it is.
- Hooks are declarative and mechanism-level (a property, a token, a state-layer rule), so Python still never runs in layout or paint.
- The shell's own look (surfaces, tooltips, state layers) stays under the shell's control through these hooks; tre supplies no widgets, theme or meaning ([Layers and Components](../20%20Architecture/Layers%20and%20Components.md)).
- Pro: keeps the existing layering and gives a clear rule for the request path; matches the owner's wording.
- Con: some requests get filed for what a designer might accept as a default; each hook is tre work.

### Option B: leave it as a principle in prose only

- Pro: no new text to maintain.
- Con: the next design gap may again be settled by bending the design, not by a request.

### Option C: let tre's defaults win where a hook does not exist

- Pro: fewer requests.
- Con: contradicts the maintainer's stated principle; the shell's look then depends on engine defaults.

## Decision

Blank until the maintainer accepts. Recommendation: A. On acceptance, add the matching ADR link in the Tesserae UX vault.

## Consequences

[Layers and Components](../20%20Architecture/Layers%20and%20Components.md) and [Vault Reference > Layering principle](../00%20Home/Vault%20Reference.md#layering-principle) carry the rule as a numbered dependency rule; no existing spec changes. Engine requests become the only route for a missing hook.

## Links

[Layers and Components](../20%20Architecture/Layers%20and%20Components.md) · [Vault Reference](../00%20Home/Vault%20Reference.md) · [ADR-0018 One Entry Form in tre](ADR-0018%20One%20Entry%20Form%20in%20tre.md) · Tesserae UX: ADR to be linked
