---
title: Style Schema
aliases: [Shell Style Schema, Token Names, Style Keys]
type: yaml-ref
status: review
owner: phil
created: 2026-10-27
updated: 2026-10-29
tags: [yaml-ref, design]
related: ["[[41 YAML Reference]]", "[[Style, Theme and Stylesheet Files]]", "[[Common Keys and Conventions]]", "[[Building Blocks]]", "[[ADR-0010 Surface Shadows]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[Style, Theme and Stylesheet Files]]"]
---

# Style Schema

> [!summary]
> The shell defines its own schema for style keys and design tokens. The names are the shell's, chosen once, and the same key means the same thing on every block, module and surface. This note is the accepted proposal (the maintainer accepted it on 2026-10-27, from "create our own YAML schema"); the names are the starting set and may change while the shell is built. It fills the gaps that [[Style, Theme and Stylesheet Files]] leaves open: the full property list, the theme token set, the stylesheet selectors and the shadow keys.

## Principles

1. **One name per concept.** `Corner_Radius` is the radius everywhere; a block never has its own spelling.
2. **Capitalised keys.** Every key is Capitalised, and a key of several words Capitalises each word and joins them with `_` (`Border_Thickness`). Enum values stay lowercase. The rule is in [[TDL Language#Names and the Registry]]; this note does not restate it.
3. **Pixels, not CSS units.** A number is logical pixels; the forms in [[Common Keys and Conventions#Value forms]] apply. No `px`, `em`, `rem` suffixes.
4. **Flat first, groups where they pay.** The maintainer's Style example is flat (`Border_Thickness`, `Border_Color`); keep that. Groups appear only for repeated structures (a shadow list).
5. **Tokens are referenced, never copied.** A theme defines a value once; styles and stylesheets name it.
6. **The schema is generated from the blocks.** Each block and module declares its properties (type, default, choices, doc), parts and states in Python ([[Building Blocks#Properties, parts and states]]); the shell builds the key lists, the validation errors and a JSON Schema that validates the parsed tree from those declarations, so the TDL reference ([[TDL Language]]; folder 41 YAML Reference, rename pending) and the code cannot drift ([[JSON Schema and Editor Support]], [[ADR-0011 JSON Schema for Shell Files]]). The declaration form is proposed; Tesserae's mechanism is a model, not a dependency.

## Style Keys

Proposed set for v1. A key a block does not have is an error with the nearest names ([[Style, Theme and Stylesheet Files#Errors specific to these files]]).

| Group  | Keys                                                                           | Notes                                                                                                   |
|--------|--------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Fill   | `Background`, `Foreground`, `Fill`, `Opacity`                                  | `Foreground` is text and icon colour; `Fill` is a shape's interior (from the maintainer's Icon example) |
| Border | `Border` (bool), `Border_Thickness`, `Border_Color`, `Corner_Radius`           | Four-sided forms; `Border_Thickness` and `Corner_Radius` take one number, four clockwise or named sides |
| Space  | `Padding`, `Margin`, `Gap`                                                     | Four-sided for the first two; `Gap` is a number                                                         |
| Text   | `Font_Family`, `Size`, `Weight`, `Line_Height`, `Align`, `Overflow`            | `Font_Family` is an ordered fallback list; `Size` is the text size in pixels                            |
| Shadow | `Elevation`, `Shadow`, `Shadow_Bleed`                                          | See below                                                                                               |
| Motion | `Transition`, `Duration`, `Easing`                                             | A property list plus timing; token names allowed                                                        |
| State  | A state key (`Hovered`, `Pressed`, `Focused`, `Disabled`) holding style values | Overrides the base values while the state holds                                                         |

Layout keys (`Direction`, `Align_Items`, `Justify`, `Width`, `Height`, `Flex_Grow`) belong to the block's properties, not to style ([[Building Blocks]]); the split is open.

## Shadow Keys

Decision behind them: shadows are drawn inside the surface with a transparent margin ([[ADR-0010 Surface Shadows]]).

| Key            | Meaning                                                                                                                               |
|----------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `Elevation`    | A level from the theme's elevation scale (`0` to `5`); the theme turns it into shadow layers                                          |
| `Shadow`       | An explicit list that replaces the elevation: each item has `Color`, `X`, `Y`, `Blur`, `Spread`                                       |
| `Shadow_Bleed` | The transparent margin around a surface body. `auto` (default) computes it from the shadow; a number or four-sided value overrides it |

```
Panel {
    Elevation: 2
    Corner_Radius: 12
    Shadow: [{Color: "#00000040", X: 0, Y: 2, Blur: 6, Spread: 0}]
}
```

> [!question] Unnamed blocks as list items
> [[ADR-0014 Shell File Language#What TDL Is (Decided)]] defines named blocks and lists, but not an unnamed block `{ ... }` as a list item. The shadow list above assumes it. Open for the maintainer: allow unnamed blocks in a list, or write each shadow as a repeated named block.

An `Elevation` and a `Shadow` on one entry: `Shadow` wins and a warning names both. `Shadow_Bleed` applies to surfaces only; on a block it is an error, because only a surface owns a buffer. The names follow tre's four numbers per shadow (offset, blur, spread) without copying its tuple form ([[Value Types and Conversion]]).

## Theme Tokens

A theme file holds token groups, each a Capitalised key (`Color`, `Type`, `Shape`, `Space`, `Elevation`, `Motion`). Proposed groups and starting names, small on purpose; the design system fills the values ([[50 Design System]]).

| Group       | Names (proposed)                                                                                                                                    | Holds                                                     |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| `Color`     | `Surface`, `Surface_Raised`, `On_Surface`, `On_Surface_Muted`, `Primary`, `On_Primary`, `Accent`, `Error`, `Warning`, `Success`, `Outline`, `Scrim` | Colour roles, not raw colours: a role says what it is for |
| `Type`      | `Caption`, `Label`, `Body`, `Title`, `Display`; each with `Size`, `Weight`, `Line_Height` and optional `Font_Family`                                | The type scale                                            |
| `Shape`     | `None`, `Small`, `Medium`, `Large`, `Full`                                                                                                          | Corner radii in pixels                                    |
| `Space`     | `1` to `8`                                                                                                                                          | A spacing scale in pixels                                 |
| `Elevation` | `0` to `5`                                                                                                                                          | Each level is a shadow list                               |
| `Motion`    | `Duration.Short`, `Duration.Medium`, `Duration.Long`, `Easing.Standard`, `Easing.Emphasised`                                                        | Milliseconds and easing names; zero under reduced motion  |

A token is referenced as `$group.name`, for example `$color.surface` or `$type.body.size`; the reference text keeps its lowercase spelling (see the question below). The `$group.name` text is an ordinary unquoted string to TDL, and the shell resolves it by token lookup; it is not TDL syntax and does not clash with TEL's delimiter. An unknown token is an error with the nearest names.

```
---
TDL: 0.1
Theme: v1
Name: dark
---

Color {
    Surface: "#1D1B20"
    On_Surface: "#E6E0E9"
    Primary: "#D0BCFF"
}
Shape {
    Small: 4
    Medium: 8
    Large: 16
}
Elevation {
    1: [{Color: "#00000033", X: 0, Y: 1, Blur: 3, Spread: 0}]
    2: [{Color: "#00000040", X: 0, Y: 2, Blur: 6, Spread: 0}]
}
```

> [!question] Token name case
> Under [[TDL Language#Names and the Registry]] every key is Capitalised, so a token name in a theme file (`On_Surface`) is a key. The reference `$color.on_surface` is a string the layout rules do not cover. The agent assumed the shell matches the reference to the group and token by name ignoring case. Open for the maintainer: that rule, or Capitalised references (`$Color.On_Surface`). `Name: dark` in the metadata block is also an assumption: [[ADR-0014 Shell File Language#Layout Rules]] gives a name only to modules.

> [!question] Constructs ADR-0014 does not define
> Two forms in this example are not in [[ADR-0014 Shell File Language#What TDL Is (Decided)]]: keys that are numbers (`1`, `2`, and the `Space` scale `1` to `8`), and the unnamed block in a list (see [[#Shadow Keys]]). Open for the maintainer: allow number keys, or name the levels (`Level_1`).

Light, dark, high contrast and reduced motion are modes of one theme: a `Modes` block (`Light`, `Dark`, `High_Contrast`, `Reduced_Motion`) overrides token values, and the shell picks the mode from the desktop ([[Goals and Non-Goals]] G7). Recommendation over one theme file per mode: tokens stay in one place and a missing override is easy to spot. Open.

## Stylesheet Selectors

The block names of a stylesheet are selectors; the body is a style block.

| Selector                | Matches                   | Example key      |
|-------------------------|---------------------------|------------------|
| A block or module name  | Every use of it           | `Text`           |
| A leading dot           | A class set with `Class:` | `.warning`       |
| A leading hash          | One unique `Name:`        | `#clock_label`   |
| A trailing state        | The state                 | `Button:hovered` |
| A trailing double colon | A named part of a block   | `Slider::track`  |

Measured on YAML, 2026-10-27, with lowercase keys: all five parsed as plain YAML keys (checked with PyYAML). Specificity is the order in the table, reversed: name beats class beats type; a state adds to the base rule. Within the priority order theme, stylesheet, style, inline ([[Style, Theme and Stylesheet Files#Rules]]).

```
---
TDL: 0.1
Stylesheet: v1
---

Text {
    Foreground: $color.on_surface
    Size: $type.body.size
}
```

> [!question] Selector names are not valid TDL block names
> Under [[ADR-0014 Shell File Language#What TDL Is (Decided)]] a block is `Name { ... }` (its head a registered type, [[TDL Language#Names and the Registry]]) and `:` and `#` have syntax roles (`#` starts a comment). So `.warning`, `#clock_label`, `Button:hovered` and `Slider::track` cannot be written as block names, and the example shows only the plain type selector. The YAML check above no longer applies. Open for the maintainer: quoted block names (`"Button:hovered" { }`), or another selector syntax. Nothing is invented here.

## Why Not Copy CSS or Another Framework's Names

- A CSS-shaped schema invites properties the shell does not support and raises the expectation that CSS behaviour (cascade by specificity across the tree, inheritance) carries over. The shell has one priority rule and opt-in inheritance ([[ADR-0007 Shell UI Layer#Blocks, modules and styling (2026-10-26)]]).
- The shell is independent of Tesserae UI ([[ADR-0006 Shell Independent of Tesserae UI]]); sharing its key names would imply a compatibility the shell does not promise. #needs-verification against the Tesserae theme reference before any name is declared the same or different on purpose.

## Open

The maintainer accepted the proposal as written on 2026-10-27; the names below are the starting set and may change while the shell is built and tested.

- [x] The principles and the key set.
- [x] The colour role names.
- [x] Modes inside one theme.
- [x] The `$group.name` reference form.
- [x] The state, part and selector forms.
- [x] Which keys are style and which are block layout properties: as proposed, with the split revisited when the blocks are specified.
- [x] `Elevation` as a level number.
- [x] The JSON Schema generation from block declarations: [[JSON Schema and Editor Support]], [[ADR-0011 JSON Schema for Shell Files]].
- [ ] TDL forms for selectors, number keys and unnamed list blocks (see the callouts above), after [[ADR-0014 Shell File Language]].
- [ ] The case of token references against Capitalised token keys (see Theme Tokens).

## Acceptance Criteria

- [ ] Every style key in the shell notes appears in this schema once, with one meaning.
- [ ] A theme with every token group loads; an unknown token reports `file:line:column` and the nearest names.
- [ ] A stylesheet with each selector form loads and applies in the stated priority.
- [ ] A surface with an elevation draws its shadow inside a margin sized by `shadow_bleed: auto`, and the reserved space is unchanged.
- [ ] The generated JSON Schema rejects an unknown key when the shell validates the parsed tree at load (editor feedback is open: [[JSON Schema and Editor Support]]).

## Links

- [[41 YAML Reference]] · [[Style, Theme and Stylesheet Files]] · [[Common Keys and Conventions]] · [[Building Blocks]] · [[ADR-0010 Surface Shadows]]
