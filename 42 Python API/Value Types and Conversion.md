---
title: Value Types and Conversion
aliases: [Value Types, Conversions]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [api, needs-verification]
related: ["[[42 Python API]]", "[[Module Context]]", "[[ADR-0007 Shell UI Layer]]", "[[ADR-0014 Shell File Language]]", "[[Expression Language Requirements]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Value Types and Conversion

> [!summary]
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
| Shadows           | A list of `(color, offset_x, offset_y, blur, spread)`                                                                    |
| Gradient          | `Gradient.linear`, `.radial` or `.sweep` with colour stops                                                               |
| Image             | Straight-alpha RGBA8 bytes with `pixel_width` and `pixel_height`, set together                                           |
| Booleans, numbers | Plain Python                                                                                                             |

## What a Module Sends

| Kind                            | A module may send                                                                                                                                                        | The shell turns it into                                                                                                                   |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| Text, numbers, booleans, `None` | Plain Python values                                                                                                                                                      | Unchanged                                                                                                                                 |
| Lists and dicts                 | JSON-like data, nested; a list feeds a repeater (workspaces, tray items)                                                                                                 | Unchanged; TEL reads it                                                                                                                   |
| Colour                          | A `(r, g, b, a)` tuple; or `"#RRGGBB"` / `"#RRGGBBAA"`; or the TDL colour form `rgba(r g b a)` with alpha 0.0 to 1.0 (the forms in the maintainer's style example, written in TDL spelling; [[#Colour and Length Literals in TDL]]); or a theme token name | The tre tuple (0 to 255 integers, so an alpha of 1.0 becomes 255). HEX to RGBA is the maintainer's example of a conversion the shell does |
| Size                            | A number, `"auto"`, a percentage string                                                                                                                                  | Unchanged (tre accepts them)                                                                                                              |
| Image                           | An image object with RGBA bytes and its size                                                                                                                             | The tre image properties; decoding files is the module's work, on its own thread ([[Process Model and Threading]])                |
| Time and dates                  | A string the module formats, or a `datetime`                                                                                                                             | A formatted string for text; formatting is the module's choice                                                                            |

Conversions the shell provides in v1 (the starting list was accepted by the maintainer on 2026-10-26):

1. HEX colour strings (3, 4, 6 or 8 digits) to `(r, g, b, a)`.
2. Theme token names to colours (for example the primary colour) through the active theme.
3. Float colour components (0.0 to 1.0) to 0 to 255 integers.
4. A `datetime` or timestamp to the string a view asks for.

Everything else a module converts itself.

## Colour and Length Literals in TDL

A value written in a shell file reaches the shell as a TDL literal ([[ADR-0014 Shell File Language#What TDL Is (Decided)]], items 6, 7 and 14). The parser reads the literal; the conversions of this note then apply as for any other source. This table only maps the literal forms to the tre types above; it adds no conversion.

| Literal in a TDL file                 | Parsed as                                         | tre type it ends as (conversion)                                                         |
|---------------------------------------|---------------------------------------------------|------------------------------------------------------------------------------------------|
| `"#ffffff"`, `"#ffffff10"` (quoted)   | A hex colour string; quoted because `#` starts a comment | `(r, g, b, a)` by conversion 1 (HEX to RGBA)                                        |
| `rgba(0 0 0 0.5)`                     | Red, green, blue as whole numbers 0 to 255, alpha as a float 0.0 to 1.0, space separated | `(r, g, b, a)`; the alpha float becomes 0 to 255 by conversion 3 (0.5 becomes 128 or 127; the rounding is not decided) |
| `16`, `120` (a whole number)          | A length in pixels                                | A number of pixels, unchanged                                                            |
| `50%`                                 | A percentage length (`<int>%`)                    | tre's percentage string `"50%"`, unchanged                                               |
| `0.9` (a float)                       | A non-length number, such as `Opacity: 0.9`       | A float, unchanged                                                                       |
| `auto`                                | An unquoted word, so a string                     | tre's `"auto"`, unchanged                                                                |
| `true`, `false`, `null`               | Bare words, kept by the parser as strings (D2)    | The key's declared type in the schema turns them into a Python boolean, number or `None`; `[]` is an empty list |
| A token name such as `primary`        | An unquoted word, so a string                     | A theme colour by conversion 2, when the key takes a colour                              |

- A float is not a length. A fraction of the parent is written `50%`. `calc(100% - 16)` has no TDL literal: a percent-plus-pixels form is not in v1 (D6, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).
- `rgba(...)` takes commas in the old YAML examples (`RGBA(255, 255, 255, 1.0)`); TDL uses spaces because `,` is a separator.
- Decided (D2, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]): the parser keeps `true`, `false`, `null` and bare numbers as strings, and the key's declared type in the schema turns them into booleans, numbers or null. The style example in [[Module Context]] uses `Border: true` and `Size: 16`, which come out as a boolean and a number by that rule.

## Four-sided Values

A style value with four sides (a border thickness, a corner radius, a margin, padding) is written in forms the file language already has (maintainer, 2026-10-26, option A in [[ADR-0007 Shell UI Layer#Open items]]; fixed for TDL by D7, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]): one number for all sides, a list of four, or a block of named sides. In TDL the three forms read:

```
Border_Thickness: 2                                          # all four sides
Border_Thickness: [2, 2, 2, 2]                               # four values, clockwise from the top
Border_Thickness { Top: 2, Left: 24 }                         # named sides, as a block; an unnamed side is not set here
```

The named-sides form was a YAML mapping; in TDL it is a block (D7). The brace shorthand `{2, 2, 2, 2}` is not valid TDL, because `{ }` opens a block.

The order of a list of four is clockwise from the top (top, right, bottom, left), confirmed by the maintainer on 2026-10-26, as tre's `margin` and `corner_radius` are. The shell converts the shorthand to tre's tuples.

## Where Conversion Runs

- **On send (module thread):** pure conversions that need no shell state (HEX to RGBA). Cheap, off the loop.
- **On flush (loop thread):** conversions that need shell state (theme tokens). Done once per turn.
- Open: which the API specifies ([[Process Model and Threading#Open questions]]).

## Errors

- A value of a type the shell cannot convert is a logged error naming the module, the key and the type; the view keeps the previous value.
- A key that no view reads is stored and ignored; no error.
- A conversion failure never raises into the module's thread: `ctx.send` returns, the error is logged.

## Open Questions

- [x] The four conversions above are v1 (maintainer, 2026-10-26). Additions later.
- [ ] Whether the shell warns when a key is sent but no view reads it (useful while building a shell).
- [ ] Units (logical pixels only, or also a scale-aware unit). TDL fixes the file spelling: pixels as a whole number, `50%` for a percentage ([[ADR-0014 Shell File Language]]); percent plus pixels is not in v1 (D6, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).
- [x] Named sides are a block, and no brace shorthand is defined (D7, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).
- [x] `true`, `false` and numbers are typed by the key's schema, not the parser (D2, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).
- [ ] How `rgba(...)` alpha converts to 0 to 255 (rounding).
- [ ] How an image is sent and who owns the buffer (copy or hand over).
- [ ] Whether a module can declare its keys and types in its TDL file so the shell can check a view against them at load.

## Acceptance Criteria

- [ ] A module sends `"#8fd3b6"` and a view shows the matching tre colour.
- [ ] A module sends a list of dicts and a repeater makes one entry per item.
- [ ] A module sends a value of an unconvertible type; an error names the module and key and the view keeps its last value.
- [ ] Sends from two threads in one turn leave the latest value per key.

## Links

- [[42 Python API]] · [[Module Contract]] · [[Module Context]] · [[ADR-0007 Shell UI Layer]] · [[ADR-0014 Shell File Language]]
