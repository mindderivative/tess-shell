---
title: Value Types and Conversion
aliases: [Value Types, Conversions]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [api, needs-verification]
related: ["[[42 Python API]]", "[[Module Context]]", "[[ADR-0007 Shell UI Layer]]", "[[Expression Language Requirements]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Value types and conversion

> [!summary]
> A module sends plain values. The values the renderer accepts are the types tre already accepts; where a module would naturally use another form, such as a HEX colour, the shell converts it. If a module needs a conversion the shell does not provide, the module converts to a type the shell does provide. The shell is there so a module author can use tre without Rust, so it covers the common conversions (maintainer, 2026-10-25). The list of conversions below is proposed; the principle is decided.

## What tre accepts

From the tre reference ([painting guide](https://mindderivative.github.io/tre/guide/painting/), [properties](https://mindderivative.github.io/tre/reference/properties/), [paint](https://mindderivative.github.io/tre/reference/paint/)), read 2026-10-26:

| Kind | tre type |
|---|---|
| Colour | `(r, g, b, a)`, a tuple of 0 to 255 integers, straight (not premultiplied) alpha |
| Opacity | `0.0` to `1.0`, group opacity of a node and its subtree |
| Size and position | A number of pixels; `"auto"`; a percentage such as `"50%"`; a percentage plus pixels such as `"calc(100% - 16)"` (0.5.7) |
| Text | A string; `font_size` in pixels; styled spans as `(start, end, style)` byte ranges |
| Corner radius | One number or `(top_left, top_right, bottom_right, bottom_left)` |
| Shadows | A list of `(color, offset_x, offset_y, blur, spread)` |
| Gradient | `Gradient.linear`, `.radial` or `.sweep` with colour stops |
| Image | Straight-alpha RGBA8 bytes with `pixel_width` and `pixel_height`, set together |
| Booleans, numbers | Plain Python |

## What a module sends

| Kind | A module may send | The shell turns it into |
|---|---|---|
| Text, numbers, booleans, `None` | Plain Python values | Unchanged |
| Lists and dicts | JSON-like data, nested; a list feeds a repeater (workspaces, tray items) | Unchanged; TEL reads it |
| Colour | A `(r, g, b, a)` tuple; or `"#RRGGBB"` / `"#RRGGBBAA"`; or `RGBA(r, g, b, a)` with alpha 0.0 to 1.0 (the forms in the maintainer's style example); or a theme token name | The tre tuple (0 to 255 integers, so an alpha of 1.0 becomes 255). HEX to RGBA is the maintainer's example of a conversion the shell does |
| Size | A number, `"auto"`, a percentage string | Unchanged (tre accepts them) |
| Image | An image object with RGBA bytes and its size | The tre image properties; decoding files is the module's work, on its own thread ([[Process Model and Threading]]) |
| Time and dates | A string the module formats, or a `datetime` | A formatted string for text; formatting is the module's choice |

Conversions the shell provides in v1 (the starting list was accepted by the maintainer on 2026-10-26):

1. HEX colour strings (3, 4, 6 or 8 digits) to `(r, g, b, a)`.
2. Theme token names to colours (for example the primary colour) through the active theme.
3. Float colour components (0.0 to 1.0) to 0 to 255 integers.
4. A `datetime` or timestamp to the string a view asks for.

Everything else a module converts itself.

## Four-sided values

A style value with four sides (a border thickness, a corner radius, a margin, padding) is written in forms plain YAML already understands (maintainer, 2026-10-26, option A in [[ADR-0007 Shell UI Layer#Open items]]): one number for all sides, a list of four, or named sides:

```yaml
border_thickness: 2                                   # all four sides
border_thickness: [2, 2, 2, 2]                        # four values; order not yet confirmed
border_thickness: {left: 2, top: 2, right: 2, bottom: 2}   # named sides
```

The order of a list of four is recommended clockwise from the top, as tre's `margin` and `corner_radius` are. The shell converts the shorthand to tre's tuples.

## Where conversion runs

- **On send (module thread):** pure conversions that need no shell state (HEX to RGBA). Cheap, off the loop.
- **On flush (loop thread):** conversions that need shell state (theme tokens). Done once per turn.
- Open: which the API specifies ([[Process Model and Threading#Open questions]]).

## Errors

- A value of a type the shell cannot convert is a logged error naming the module, the key and the type; the view keeps the previous value.
- A key that no view reads is stored and ignored; no error.
- A conversion failure never raises into the module's thread: `ctx.send` returns, the error is logged.

## Open questions

- [x] The four conversions above are v1 (maintainer, 2026-10-26). Additions later.
- [ ] Whether the shell warns when a key is sent but no view reads it (useful while building a shell).
- [ ] Units (logical pixels only, or also percentages and a scale-aware unit).
- [ ] How an image is sent and who owns the buffer (copy or hand over).
- [ ] Whether a module can declare its keys and types in its YAML so the shell can check a view against them at load.

## Acceptance criteria

- [ ] A module sends `"#8fd3b6"` and a view shows the matching tre colour.
- [ ] A module sends a list of dicts and a repeater makes one entry per item.
- [ ] A module sends a value of an unconvertible type; an error names the module and key and the view keeps its last value.
- [ ] Sends from two threads in one turn leave the latest value per key.

## Links

- [[42 Python API]] · [[Module Contract]] · [[Module Context]] · [[ADR-0007 Shell UI Layer]]
