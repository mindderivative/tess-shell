---
title: ADR-0018 One Entry Form in tre
aliases: [ADR-0018, tre Entry Points, Single Standard Form]
type: adr
status: accepted
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [adr, architecture, tre]
---

# ADR-0018: One Entry Form in tre

> [!NOTE]
> tre takes one standard form for each kind of value at its entry points, and the framework above it converts every other form to that one. tre does not learn colour strings, image formats or any other convenience form. Stated by the maintainer on 2026-11-03 and recorded here as the rule for every request to tre.

## Context

The shell's binder and Tesserae UI both turn a colour string into the `(r, g, b, a)` tuple that tre takes. [TRE-REQ-010 Colour Strings](../80%20Requests/TRE-REQ-010%20Colour%20Strings.md) asked tre to accept strings so the converters could disappear. The maintainer declined (2026-11-03): "I dont want tre to do the conversions, I want it to have a simple entry point that is not confusing. If I start having tre convert everything it goes from being a rendering engine to a general purpose engine. Also, having a single standard is important, if another format comes along then tre does not need to add another conversion form. It is why tre does not decompress images into bitmap format. That is the job of the framework. This should apply to all of tre's entry points."

## Options

### Option A — One Entry Form per Kind of Value; the Framework Converts (Chosen)

- **For:** tre stays a rendering engine; its entry points stay few and unambiguous; a new input format (a new colour syntax, a new image codec) changes the frameworks, not tre; the rule already holds for images (decoded pixels in) and fonts (bytes in).
- **Against:** every framework writes or shares its converters ([ADR-0017 Shared Utilities](ADR-0017%20Shared%20Utilities.md)).

### Option B — tre Accepts Convenience Forms

- **Against:** each form tre accepts is one more thing to specify, test and keep in step; the entry points grow without end. Rejected.

## Decision

Accepted 2026-11-03 by the maintainer in chat, in the words quoted in Context: **Option A**.

## Consequences

- No request to tre asks it to convert, parse or accept another form of a value it already takes. [TRE-REQ-010 Colour Strings](../80%20Requests/TRE-REQ-010%20Colour%20Strings.md) is withdrawn.
- The binder and Tesserae UI own their converters. Sharing them is a separate question, [ADR-0017 Shared Utilities](ADR-0017%20Shared%20Utilities.md).
- [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) lists format conversion among the things tre never owns (AGENTS > 3. Layering Principle).
- Existing entry points that already accept more than one form (tre 0.5.10 takes a length as a number or as a percentage string such as `"50%"`) are tre's to review against this rule. The shell passes whatever form tre documents and does not rely on extra forms.
- A request to tre must name a mechanism the engine lacks, not a convenience.

## Links

- [ADR-0015 Render Binder](ADR-0015%20Render%20Binder.md) · [ADR-0017 Shared Utilities](ADR-0017%20Shared%20Utilities.md) · [TRE-REQ-010 Colour Strings](../80%20Requests/TRE-REQ-010%20Colour%20Strings.md) · [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) · [30 Decisions](30%20Decisions.md)
