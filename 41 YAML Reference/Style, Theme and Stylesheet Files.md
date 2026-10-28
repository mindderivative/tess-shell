---
title: Style, Theme and Stylesheet Files
aliases: [_Style.yaml, _Theme.yaml, _Stylesheet.yaml, Style Files]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [yaml-ref, design, needs-verification]
related: ["[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Module File]]", "[[Shell File]]", "[[50 Design System]]"]
depends_on: ["[[Common Keys and Conventions]]"]
---

# Style, theme and stylesheet files

> [!summary]
> Three files control how things look. A **style** file holds the values for one surface or module, like its inline `style:` key. A **stylesheet** holds shared rules that apply across the shell by widget type or class. A **theme** holds design tokens (colour, type, shape, motion) that the others refer to. The split is the maintainer's ([[ADR-0007 Shell UI Layer#Theme, style and stylesheet (2026-10-25)]]). The Style format below comes from the maintainer's Label example; Theme and Stylesheet are proposed in [[Style Schema]].

All three are shell files: they carry `shell:` and `type:` (`Style`, `Theme`, `Stylesheet`). Their suffixes are `_Style.yaml`, `_Theme.yaml` and `_Stylesheet.yaml`, the same as Tesserae's; the `shell:` key tells them apart ([[Common Keys and Conventions]]).

## Style file

```yaml
shell: v1
type: Style

classes:
    text_style:
        block: Text           # the example writes `kind: Text`; see Classes below
        size: 16
        weight: 500
        foreground: "#ffffff"

Icon:
    foreground: "#ffffff"
    fill: "#00000000"

FlexBox:
    background: "#000000"
    border: true
    border_thickness: 2
    border_color: "#ffffff"
    corner_radius: 8

Text:
    font_family: ["Hack Nerd Font Mono", "JetBrains Mono"]
```

| Key | Meaning | Status |
|---|---|---|
| `classes` | Named groups of values a widget picks up with `class:` | Decided (the form) |
| A widget name as a key (`Icon:`, `FlexBox:`, `Text:`) | Defaults for every widget of that type in the file that uses this style | Decided (the form) |
| Property names | `size`, `weight`, `foreground`, `fill`, `background`, `border`, `border_thickness`, `border_color`, `corner_radius`, `font_family` | From the example; the full list is open |

- **Colour** forms: `"#RRGGBB"`, `"#RRGGBBAA"`, `RGBA(r, g, b, a)` ([[Common Keys and Conventions#Value forms]]).
- **Four-sided** values: a number, a list of four clockwise from the top, or named sides. The example's `{2, 2, 2, 2}` becomes `2` or `[2, 2, 2, 2]`; `corner_radius: {8, 8, 8, 8}` becomes `8` or `[8, 8, 8, 8]` (top-left, top-right, bottom-right, bottom-left, clockwise from top-left).
- **Lists:** `font_family: ["Hack Nerd Font Mono", "JetBrains Mono"]`, an ordered fallback list (the example's braces become square brackets).
- The same values may be written inline under `style:` in a module or surface.

### Classes

- A widget picks a class with `class: text_style`.
- The example writes `kind: Text` inside a class to say which block it applies to. `kind:` means a surface's kind everywhere else ([[Common Keys and Conventions#Keys that say what something is]]). With `widget:` gone the recommendation is `block: Text` inside a class. Maintainer to confirm.
- Whether a class applies only to the widget type named, or to any widget that picks it, is open.

## Theme file (not yet designed)

A theme holds design tokens: colour roles, type scale, shape (radii), motion (durations, easing), spacing. Styles and stylesheets refer to tokens by name instead of repeating values, which is how light and dark, high contrast and reduced motion are followed from the desktop ([[Goals and Non-Goals]] G7). The token set and file shape belong to `50 Design System/`; this reference records only the file's header (`shell:`, `type: Theme`).

```yaml
shell: v1
type: Theme
name: dark
# token groups: colour, type, shape, motion, spacing -- not designed
```

## Stylesheet file (not yet designed)

A stylesheet holds shared rules that apply across the shell by widget type or class, so a shell author can restyle every `Text` or every `.warning` in one place.

```yaml
shell: v1
type: Stylesheet
# rules by widget type or class -- not designed
```

## Rules

Decided by the maintainer on 2026-10-26 ([[ADR-0007 Shell UI Layer#Blocks, modules and styling (2026-10-26)]]).

- Styling applies to building blocks and to everything else that can be styled (surfaces, modules). The forms are `<Name>_Theme.yaml`, `<Name>_Stylesheet.yaml`, `<Name>_Style.yaml` and inline `style:`.
- Customising a block is referencing another stylesheet or style, or writing inline `style:`. A custom style is not a full replacement; it changes only what it names.
- **Priority**, lowest to highest: theme, then stylesheet, then style, then inline `style:`. It applies to all styling.
- **Imports go downwards:**

| File | May import | May not import |
|---|---|---|
| Theme | Stylesheets, styles; or use inline styling | n/a |
| Stylesheet | Styles; or use inline styling | A theme |
| Style | Nothing beneath it; inline values only | A theme or a stylesheet (proposed, to avoid cycles) |
| Inline `style:` | A theme, a stylesheet, a style; or inline values | n/a |

- Priority follows the type of each file, not the path it was imported by. A stylesheet that a theme imports still outranks the theme.

Proposed (to confirm): when two files of the same type set the same property, the later import wins; a style cannot import anything; an import cycle is a load error naming the chain ([[Common Keys and Conventions#Errors]]).

The maintainer's Edge Shell notes ordered it Theme, Frame, Panel, Widget with a widget's own property winning ([[Shadows on Layer Surfaces#The maintainer's earlier work]], `Shell_Specs`); the new rule is the same idea over the file types.

## Errors specific to these files

- A property name the widget does not have: error with the closest names.
- A value of the wrong form (a colour that is not one of the three): error with the forms.
- A class used and not defined: error naming the file searched.
- A token that does not exist: error with the nearest names.

## Open

- [ ] The full property list per widget, and which belong in style and which on the widget.
- [ ] The class key (`block: Text`, recommended).
- [ ] The theme token set and file shape ([[50 Design System]], not started).
- [ ] The stylesheet rule shape (selectors by type, class, name).
- [x] The precedence order: theme, stylesheet, style, inline (decided).
- [ ] Whether a style file may extend another.
- [ ] Light/dark and high-contrast switching: in the theme, or in several theme files.

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Module File]] · [[Shell File]] · [[50 Design System]]
