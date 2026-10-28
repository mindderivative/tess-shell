---
title: Style Schema
aliases: [Shell Style Schema, Token Names, Style Keys]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [yaml-ref, design]
related: ["[[41 YAML Reference]]", "[[Style, Theme and Stylesheet Files]]", "[[Common Keys and Conventions]]", "[[Building Blocks]]", "[[ADR-0010 Surface Shadows]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[Style, Theme and Stylesheet Files]]"]
---

# Style schema

> [!summary]
> The shell defines its own schema for style keys and design tokens. The names are the shell's, chosen once, and the same key means the same thing on every block, module and surface. This note is a proposal for the maintainer (2026-10-27, from "create our own YAML schema"): every name below is proposed until accepted. It fills the gaps that [[Style, Theme and Stylesheet Files]] leaves open: the full property list, the theme token set, the stylesheet selectors and the shadow keys.

## Principles

1. **One name per concept.** `corner_radius` is the radius everywhere; a block never has its own spelling.
2. **snake_case keys, lower case.** Block and kind names keep the case they have ([[Common Keys and Conventions#Keys that say what something is]]).
3. **Pixels, not CSS units.** A number is logical pixels; the forms in [[Common Keys and Conventions#Value forms]] apply. No `px`, `em`, `rem` suffixes.
4. **Flat first, groups where they pay.** The maintainer's Style example is flat (`border_thickness`, `border_color`); keep that. Groups appear only for repeated structures (a shadow list).
5. **Tokens are referenced, never copied.** A theme defines a value once; styles and stylesheets name it.
6. **The schema is generated from the blocks.** Each block and module declares its properties (type, default, choices, doc), parts and states in Python ([[Building Blocks#Properties, parts and states]]); the shell builds the key lists, the validation errors and a JSON Schema for editors from those declarations, so the YAML reference and the code cannot drift. The declaration form is proposed; Tesserae's mechanism is a model, not a dependency.

## Style keys

Proposed set for v1. A key a block does not have is an error with the nearest names ([[Style, Theme and Stylesheet Files#Errors specific to these files]]).

| Group | Keys | Notes |
|---|---|---|
| Fill | `background`, `foreground`, `fill`, `opacity` | `foreground` is text and icon colour; `fill` is a shape's interior (from the maintainer's Icon example) |
| Border | `border` (bool), `border_thickness`, `border_color`, `corner_radius` | Four-sided forms; `border_thickness` and `corner_radius` take one number, four clockwise or named sides |
| Space | `padding`, `margin`, `gap` | Four-sided for the first two; `gap` is a number |
| Text | `font_family`, `size`, `weight`, `line_height`, `align`, `overflow` | `font_family` is an ordered fallback list; `size` is the text size in pixels |
| Shadow | `elevation`, `shadow`, `shadow_bleed` | See below |
| Motion | `transition`, `duration`, `easing` | A property list plus timing; token names allowed |
| State | A state key (`hovered`, `pressed`, `focused`, `disabled`) holding style values | Overrides the base values while the state holds |

Layout keys (`direction`, `align_items`, `justify`, `width`, `height`, `flex_grow`) belong to the block's properties, not to style ([[Building Blocks]]); the split is open.

## Shadow keys

Decision behind them: shadows are drawn inside the surface with a transparent margin ([[ADR-0010 Surface Shadows]]).

| Key | Meaning |
|---|---|
| `elevation` | A level from the theme's elevation scale (`0` to `5`); the theme turns it into shadow layers |
| `shadow` | An explicit list that replaces the elevation: each item has `color`, `x`, `y`, `blur`, `spread` |
| `shadow_bleed` | The transparent margin around a surface body. `auto` (default) computes it from the shadow; a number or four-sided value overrides it |

```yaml
Panel_Card:
    elevation: 2
    corner_radius: 12
    shadow:
        - {color: "#00000040", x: 0, y: 2, blur: 6, spread: 0}
```

An `elevation` and a `shadow` on one entry: `shadow` wins and a warning names both. `shadow_bleed` applies to surfaces only; on a block it is an error, because only a surface owns a buffer. The names follow tre's four numbers per shadow (offset, blur, spread) without copying its tuple form ([[Value Types and Conversion]]).

## Theme tokens

A theme file holds token groups. Proposed groups and starting names, small on purpose; the design system fills the values ([[50 Design System]]).

| Group | Names (proposed) | Holds |
|---|---|---|
| `color` | `surface`, `surface_raised`, `on_surface`, `on_surface_muted`, `primary`, `on_primary`, `accent`, `error`, `warning`, `success`, `outline`, `scrim` | Colour roles, not raw colours: a role says what it is for |
| `type` | `caption`, `label`, `body`, `title`, `display`; each with `size`, `weight`, `line_height` and optional `font_family` | The type scale |
| `shape` | `none`, `small`, `medium`, `large`, `full` | Corner radii in pixels |
| `space` | `1` to `8` | A spacing scale in pixels |
| `elevation` | `0` to `5` | Each level is a shadow list |
| `motion` | `duration.short`, `duration.medium`, `duration.long`, `easing.standard`, `easing.emphasised` | Milliseconds and easing names; zero under reduced motion |

A token is referenced as `$group.name`, for example `$color.surface` or `$type.body.size`. The `$` prefix is plain YAML and does not clash with TEL's delimiter. An unknown token is an error with the nearest names.

```yaml
shell: v1
type: Theme
name: dark
color:
    surface: "#1D1B20"
    on_surface: "#E6E0E9"
    primary: "#D0BCFF"
shape:
    small: 4
    medium: 8
    large: 16
elevation:
    1: [{color: "#00000033", x: 0, y: 1, blur: 3, spread: 0}]
    2: [{color: "#00000040", x: 0, y: 2, blur: 6, spread: 0}]
```

Light, dark, high contrast and reduced motion are modes of one theme: a `modes:` mapping (`light`, `dark`, `high_contrast`, `reduced_motion`) overrides token values, and the shell picks the mode from the desktop ([[Goals and Non-Goals]] G7). Recommendation over one theme file per mode: tokens stay in one place and a missing override is easy to spot. Open.

## Stylesheet selectors

Keys of a stylesheet are selectors; the value is a style mapping.

| Selector | Matches | Example key |
|---|---|---|
| A block or module name | Every use of it | `Text` |
| A leading dot | A class set with `class:` | `.warning` |
| A leading hash | One unique `name:` | `#clock_label` |
| A trailing state | The state | `Button:hovered` |
| A trailing double colon | A named part of a block | `Slider::track` |

All five parse as plain YAML keys (checked with PyYAML, 2026-10-27). Specificity is the order in the table, reversed: name beats class beats type; a state adds to the base rule. Within the priority order theme, stylesheet, style, inline ([[Style, Theme and Stylesheet Files#Rules]]).

```yaml
shell: v1
type: Stylesheet
Text:
    foreground: $color.on_surface
    size: $type.body.size
.warning:
    foreground: $color.warning
Button:hovered:
    background: $color.primary
```

## Why not copy CSS or another framework's names

- A CSS-shaped schema invites properties the shell does not support and raises the expectation that CSS behaviour (cascade by specificity across the tree, inheritance) carries over. The shell has one priority rule and opt-in inheritance ([[ADR-0007 Shell UI Layer#Blocks, modules and styling (2026-10-26)]]).
- The shell is independent of Tesserae UI ([[ADR-0006 Shell Independent of Tesserae UI]]); sharing its key names would imply a compatibility the shell does not promise. #needs-verification against the Tesserae theme reference before any name is declared the same or different on purpose.

## Open

- [ ] Accept the principles and the key set, or change them.
- [ ] The colour role names (a Material 3 list is the usual starting point; the set above is smaller).
- [ ] Modes inside one theme, or one file per mode.
- [ ] The `$group.name` reference form.
- [ ] The state, part and selector forms.
- [ ] Which keys are style and which are block properties (layout).
- [ ] Whether `elevation` stays a level number or becomes names.
- [ ] The JSON Schema generation from block declarations (a tooling note in `70 Delivery` or `41 YAML Reference`).

## Acceptance criteria

- [ ] Every style key in the shell notes appears in this schema once, with one meaning.
- [ ] A theme with every token group loads; an unknown token reports `file:line:column` and the nearest names.
- [ ] A stylesheet with each selector form loads and applies in the stated priority.
- [ ] A surface with an elevation draws its shadow inside a margin sized by `shadow_bleed: auto`, and the reserved space is unchanged.
- [ ] The generated JSON Schema rejects an unknown key in an editor.

## Links

- [[41 YAML Reference]] · [[Style, Theme and Stylesheet Files]] · [[Common Keys and Conventions]] · [[Building Blocks]] · [[ADR-0010 Surface Shadows]]
