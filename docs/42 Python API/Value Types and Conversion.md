---
title: Value Types and Conversion
aliases: [Value Types, Conversions]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-11-02
tags: [api, needs-verification]
---

# Value Types and Conversion

> [!NOTE]
> A module sends plain values. The values the renderer accepts are the types tre already accepts; where a module would naturally use another form, such as a HEX colour, the shell converts it. If a module needs a conversion the shell does not provide, the module converts to a type the shell does provide. The shell is there so a module author can use tre without Rust, so it covers the common conversions (maintainer, 2026-10-25). The list of conversions below is proposed; the principle is decided.

## What Tre Accepts

From the tre reference ([painting guide](https://mindderivative.github.io/tre/guide/painting/), [properties](https://mindderivative.github.io/tre/reference/properties/), [paint](https://mindderivative.github.io/tre/reference/paint/)), read 2026-10-26:

| Kind              | tre type                                                                                                                 |
|-------------------|--------------------------------------------------------------------------------------------------------------------------|
| Colour            | `(r, g, b, a)`, a tuple of 0 to 255 integers, straight (not premultiplied) alpha                                         |
| Opacity           | `0.0` to `1.0`, group opacity of a node and its subtree                                                                  |
| Size and position | A number of pixels; `"auto"`; a percentage such as `"50%"`; a percentage plus pixels such as `"calc(100% - 16)"` (0.5.7) |
| Text              | A string; `font_size` in pixels; styled spans as `(start, end, style)` byte ranges                                       |
| Corner radius     | One number or `(top_left, top_right, bottom_right, bottom_left)`                                                         |
| Margin            | One number or `(top, right, bottom, left)`, tre's order (the order is not the TDL order; see [Four-sided Values](#four-sided-values))      |
| Enum-like options | Lowercase strings, for example a layer or a keyboard mode (see [Enum Values](#enum-values))                                          |
| Shadows           | A list of `(color, offset_x, offset_y, blur, spread)`                                                                    |
| Gradient          | `Gradient.linear`, `.radial` or `.sweep` with colour stops                                                               |
| Image             | Straight-alpha RGBA8 bytes with `pixel_width` and `pixel_height`, set together                                           |
| Booleans, numbers | Plain Python                                                                                                             |

## What a Module Sends

| Kind                            | A module may send                                                                                                                                                        | The shell turns it into                                                                                                                   |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| Text, numbers, booleans, `None` | Plain Python values                                                                                                                                                      | Unchanged                                                                                                                                 |
| Lists and dicts                 | JSON-like data, nested; a list feeds a repeater (workspaces, tray items)                                                                                                 | Unchanged; TEL reads it                                                                                                                   |
| Colour                          | A `(r, g, b, a)` tuple; or `"#RRGGBB"` / `"#RRGGBBAA"`; or the TDL colour form `rgba(r g b a)` with alpha 0.0 to 1.0 (the forms in the maintainer's style example, written in TDL spelling; [Colour and Length Literals in TDL](#colour-and-length-literals-in-tdl)); or a theme token name | The tre tuple (0 to 255 integers, so an alpha of 1.0 becomes 255). HEX to RGBA is the maintainer's example of a conversion the shell does |
| Size                            | A number, `"auto"`, a percentage string                                                                                                                                  | Unchanged (tre accepts them)                                                                                                              |
| Image                           | An image object with RGBA bytes and its size                                                                                                                             | The tre image properties; decoding files is the module's work, on its own thread ([Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md))                |
| Time and dates                  | A string the module formats, or a `datetime`                                                                                                                             | A formatted string for text; formatting is the module's choice                                                                            |

Conversions the shell provides in v1 (the starting list was accepted by the maintainer on 2026-10-26):

1. HEX colour strings (3, 4, 6 or 8 digits) to `(r, g, b, a)`.
2. Theme token names to colours (for example the primary colour) through the active theme.
3. Float colour components (0.0 to 1.0) to 0 to 255 integers.
4. A `datetime` or timestamp to the string a view asks for.

Everything else a module converts itself.

## Colour and Length Literals in TDL

A value written in a shell file reaches the shell as a TDL literal ([ADR-0014 Shell File Language > What TDL Is (Decided)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#what-tdl-is-decided), items 6, 7 and 14). The parser reads the literal; the conversions of this note then apply as for any other source. This table only maps the literal forms to the tre types above; it adds no conversion.

| Literal in a TDL file                 | Parsed as                                         | tre type it ends as (conversion)                                                         |
|---------------------------------------|---------------------------------------------------|------------------------------------------------------------------------------------------|
| `"#ffffff"`, `"#ffffff10"` (quoted)   | A hex colour string; quoted because `#` starts a comment | `(r, g, b, a)` by conversion 1 (HEX to RGBA)                                        |
| `rgba(0 0 0 0.5)`                     | Red, green, blue as whole numbers 0 to 255, alpha as a float 0.0 to 1.0, space separated | `(r, g, b, a)`; the alpha float becomes 0 to 255 by conversion 3 (0.5 becomes 128 or 127; the rounding is not decided) |
| `16`, `120` (a whole number)          | A length in pixels                                | A number of pixels, unchanged                                                            |
| `50%`                                 | A percentage length (`<int>%`)                    | tre's percentage string `"50%"`, unchanged                                               |
| `0.9` (a float)                       | A non-length number, such as `Opacity: 0.9`       | A float, unchanged                                                                       |
| `AUTO`                                | A keyword where the key allows it (D34)           | tre's `"auto"` (lowercase) where the property is a tre size; for a surface the shell resolves it (wrap the content on that axis) |
| `EXPAND`                              | A keyword where the key allows it (D34)           | Not a tre value. The shell resolves it against the surface's attached edge; how it reaches tre's `anchor` and `size` is open ([Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md)) |
| `TOP`, `OVERLAY`, `HORIZONTAL`        | An enum: a full upper-case bare word (D33)        | tre's lowercase value (`"top"`, `"overlay"`); see [Enum Values](#enum-values)                       |
| `[8, 0, 0, 24]` (four values)         | A four-sided list, in the order left, top, right, bottom (D50) | tre's `(top, right, bottom, left)`, reordered; see [Four-sided Values](#four-sided-values)            |
| `true`, `false`, `null`               | Bare words, kept by the parser as strings (D2)    | The key's declared type in the schema turns them into a Python boolean, number or `None`; `[]` is an empty list |
| A token name such as `primary`        | An unquoted word, so a string                     | A theme colour by conversion 2, when the key takes a colour                              |

- A float is not a length. A fraction of the parent is written `50%`, and the shell passes it to tre as the string `"50%"`. `calc(100% - 16)` has no TDL literal: a percent-plus-pixels form is not in v1 (D6, D47, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- Keywords and enum values are upper case in TDL (`AUTO`, `EXPAND`, `TOP`); `true`, `false` and `null` stay lowercase. tre's own values are lowercase.
- `rgba(...)` takes commas in the old YAML examples (`RGBA(255, 255, 255, 1.0)`); TDL uses spaces because `,` is a separator.
- Decided (D2, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)): the parser keeps `true`, `false`, `null` and bare numbers as strings, and the key's declared type in the schema turns them into booleans, numbers or null. The style example in [Module Context](Module%20Context.md) uses `Border_Width: [2, 2, 2, 2]` and `Font_Size: 16`, which come out as a list of numbers and a number by that rule.

## Four-sided Values

A style value with four sides (a border width, a corner radius, a margin, padding) is written in forms the file language already has (maintainer, 2026-10-26, option A in [ADR-0007 Shell UI Layer > Open items](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#open-items); fixed for TDL by D7, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)): one number for all sides, a list of four, or a block of named sides. In TDL the three forms read:

```
Border_Width: 2                                              # all four sides
Border_Width: [2, 2, 2, 2]                                   # four values: left, top, right, bottom
Border_Width { Left: 24, Top: 2 }                            # named sides, as a block; an unnamed side is not set here
```

The named-sides form was a YAML mapping; in TDL it is a block (D7). The brace shorthand `{2, 2, 2, 2}` is not valid TDL, because `{ }` opens a block.

The order of a list of four in TDL is left, top, right, bottom (D50, [ADR-0014 Shell File Language > Fourth-Round Decisions (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#fourth-round-decisions-2026-10-30)), which matches Flutter, Qt and WPF and differs from CSS and SwiftUI (#needs-verification). It replaces the clockwise order from the top that the maintainer confirmed on 2026-10-26. tre's `margin` is still `(top, right, bottom, left)`, so the shell reorders a four-sided value when it passes it to tre. A symmetric list such as `[2, 2, 2, 2]` is the same in both orders. A list of two or three items is an error with the slug `bad-sides` ([Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md)); the hint says to use one number, four items or named sides, because CSS orders its sides top, right, bottom, left and accepts two or three.

| TDL (left, top, right, bottom) | tre `margin` (top, right, bottom, left) | Reading                  |
|--------------------------------|------------------------------------------|--------------------------|
| `8`                            | `8`                                      | All four sides           |
| `[24, 8, 0, 4]`                | `(8, 0, 4, 24)`                          | The shell reorders       |
| `[0, 0, 0, 8]`                 | `(0, 0, 8, 0)`                           | 8 px at the bottom       |

Four corner radii are not reordered. They stay top-left, top-right, bottom-right, bottom-left in TDL and in tre's `corner_radius` ([ADR-0014 Shell File Language > Fourth-Round Decisions (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#fourth-round-decisions-2026-10-30), readings).

## Enum Values

An enum is written in TDL as a full upper-case bare word (D33, [TDL Language > Values](../41%20TDL%20Reference/TDL%20Language.md#values)). The shell converts it to tre's lowercase value when the property is a tre property, and keeps it as an upper-case word where it is the shell's own (a `Flex` value, an `Alignment`).

| TDL           | tre-side value                   |
|---------------|----------------------------------|
| `Layer: OVERLAY`       | `"overlay"`             |
| `Keyboard: EXCLUSIVE`  | `"exclusive"`           |
| `Edge: TOP`            | Used by the shell to compute tre's `anchor`, `size` and `margin`; the mapping is open ([Bar](../40%20Specifications/Surfaces/Bar.md)) |

An unknown word, or a lowercase word such as `top`, is a schema error that says enum values are upper case ([Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md)).

## Where Conversion Runs

- **On send (module thread):** pure conversions that need no shell state (HEX to RGBA). Cheap, off the loop.
- **On flush (loop thread):** conversions that need shell state (theme tokens). Done once per turn.
- Open: which the API specifies ([Process Model and Threading > Open questions](../20%20Architecture/Process%20Model%20and%20Threading.md#open-questions)).

## Errors

- A value of a type the shell cannot convert is a logged error naming the module, the key and the type; the view keeps the previous value.
- A key that no view reads is stored and ignored; no error.
- A conversion failure never raises into the module's thread: `ctx.send` returns, the error is logged.

## Open Questions

- [x] The four conversions above are v1 (maintainer, 2026-10-26). Additions later.
- [ ] Whether the shell warns when a key is sent but no view reads it (useful while building a shell).
- [ ] Units (logical pixels only, or also a scale-aware unit). TDL fixes the file spelling: pixels as a whole number, `50%` for a percentage ([ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)); percent plus pixels is not in v1 (D6, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] Named sides are a block, and no brace shorthand is defined (D7, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] `true`, `false` and numbers are typed by the key's schema, not the parser (D2, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [ ] How `rgba(...)` alpha converts to 0 to 255 (rounding).
- [ ] How an image is sent and who owns the buffer (copy or hand over).
- [ ] Whether a module can declare its keys and types in its TDL file so the shell can check a view against them at load.

## Acceptance Criteria

- [ ] A module sends `"#8fd3b6"` and a view shows the matching tre colour.
- [ ] A module sends a list of dicts and a repeater makes one entry per item.
- [ ] A module sends a value of an unconvertible type; an error names the module and key and the view keeps its last value.
- [ ] Sends from two threads in one turn leave the latest value per key.

## Links

- [42 Python API](42%20Python%20API.md) · [Module Contract](Module%20Contract.md) · [Module Context](Module%20Context.md) · [ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md) · [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)
