---
title: TRE-REQ-010 Colour Strings
aliases: [TRE-REQ-010, Colour Strings in tre, Colour Parsing in tre]
type: engine-request
status: superseded
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [engine-request, design, needs-verification]
---

# TRE-REQ-010: Colour Strings

> [!CAUTION]
> **Withdrawn by the maintainer (2026-11-03)**
> "I dont want tre to do the conversions." tre takes one standard form for each kind of value, and the framework converts; see [ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md). This note stays as the record. It is not carried to tre.

> [!NOTE]
> Ask tre to accept colour strings (`"#RRGGBB"`, `"#RRGGBBAA"`, `rgba(...)` and the other common CSS forms) anywhere it accepts an `(r, g, b, a)` tuple today, and to expose its colour parser as a function. Every project that sets a colour on a tre node converts a string to a tuple first: the shell will, and Tesserae UI already does. The maintainer proposed a shared utilities project for such helpers (2026-11-03); asking tre to take the colour part is the smaller change. Draft for the maintainer to carry to the tre project; nothing is filed from this vault (AGENTS > 6. Requests Between Projects).

> [!TIP]
> **Not blocking**
> The shell converts colours in its binder ([Render Binder Design > Converters](../20%20Architecture/Render%20Binder%20Design.md#converters)). Nothing waits on this request.

## Shell Need

TDL writes a colour as `"#RRGGBB"`, `"#RRGGBBAA"` or `rgba(r g b a)` with red, green and blue 0 to 255 and alpha 0.0 to 1.0 ([TDL Language > Values](../41%20TDL%20Reference/TDL%20Language.md#values)). tre takes a tuple of four 0 to 255 integers. The shell needs a converter for every colour key (`Fill`, `Border_Color`, `Foreground`, shadow colours and the rest).

## What tre Does Today

Tested on tre 0.5.10 on 2026-11-03, by calling `Window.create` and `Node.set`:

| Where | Accepts |
|---|---|
| `fill` on a box | An `(r, g, b, a)` tuple of 0 to 255 integers, or a `Gradient`; a string such as `"#ffffff"` is refused |
| `stroke_color`, `svg_color` | A tuple only; strings refused |
| `Gradient.linear` stops | `(r, g, b, a)` colours or `(offset, colour)` pairs; strings refused |
| Lengths such as `width`, `padding` | A number or a percentage string such as `"50%"` |

So tre already takes a string where it is a length, but not where it is a colour. Tesserae UI's `tess_ui/tokens.py` has `parse_color(raw) -> RGBA` that handles hex (3, 4, 6 and 8 digits), CSS names, `transparent`, `rgb()`, `rgba()`, `hsl()` and the wide-gamut CSS functions; its docstring says "as `tre` parses it" and copies tre's error wording, which suggests tre has a colour parser of its own (Rust side) that Python cannot reach. #needs-verification

## Why it Belongs in the Engine

Parsing a colour is mechanism with one correct answer, needed by everything that draws. A converter in each project means the same code written several times, with different edge cases, and in Tesserae UI's case a dependency on Pillow just for `ImageColor`. In tre it is written once.

## Proposed API

Minimal, and tre's to rename.

- **A function:** `tess_re.parse_color("#89b4fa") -> (137, 180, 250, 255)` (name tre's to choose), raising `ValueError` with a message that names the bad part. This alone removes every converter.
- **Strings where tuples are accepted:** `node.set(fill="#89b4fa")`, `stroke_color`, `svg_color`, shader and shadow colours, and gradient stops, parsed by the same function.
- **Forms:** `#RGB`, `#RGBA`, `#RRGGBB`, `#RRGGBBAA` (alpha last, as CSS and TDL write it); `rgb()` and `rgba()` in comma and in space syntax, with alpha as a number from 0 to 1 or a percentage; `transparent`. CSS colour names and `hsl()` are welcome but not needed.
- The tuple form stays accepted, so nothing changes for current callers.

## Alternatives

| Option | For | Against |
|---|---|---|
| Strings and a function in tre (recommended) | Written once; no dependency for callers | A change in tre |
| A function only | Smaller; callers still convert before `set` | Callers still write the call |
| A shared utilities project | Reusable beyond colour | A new project to run; see [ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md) |
| Each project converts (today) | No change | Duplicate code, as in Tesserae UI and the shell |

## If Declined

The shell converts colours in `binder/convert.py`, as a pure function with no dependencies, written so it can move to a shared package unchanged.

## Size

Small, if tre already has the parser on the Rust side: expose it and call it from the property setters.

## Open Questions

1. [ ] Does tre already have a colour parser in its Rust code, and where? Ask tre.
2. [ ] The form of alpha in `rgba()`: 0 to 1, a percentage, or both.
3. [ ] The set of colour names, if any.
4. [ ] The name of the function and the error wording.
5. [ ] Whether the same applies to `Painter` colours.

## Acceptance Criteria

- [ ] `node.set(fill="#89b4fa")` and `node.set(fill=(137, 180, 250, 255))` give the same result.
- [ ] A bad string raises `ValueError` and changes nothing, as `Node.set` already does.
- [ ] The function and the property setters accept the same strings.
- [ ] The tuple form is unchanged.

## Links

- [80 Requests](80%20Requests.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) · [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) · [ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md)
