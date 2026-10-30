---
title: Style, Theme and Stylesheet Files
aliases: [_Style.tdl, _Theme.tdl, _Stylesheet.tdl, _Style.yaml, _Theme.yaml, _Stylesheet.yaml, Style Files]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [yaml-ref, design, needs-verification]
related: ["[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Module File]]", "[[Shell File]]", "[[50 Design System]]"]
depends_on: ["[[Common Keys and Conventions]]"]
---

# Style, Theme and Stylesheet Files

> [!summary]
> Three files control how things look. A **style** file holds the values for one surface or module, like its inline `Style:` key. A **stylesheet** holds shared rules that apply across the shell by widget type or class. A **theme** holds design tokens (colour, type, shape, motion) that the others refer to. The split is the maintainer's ([[ADR-0007 Shell UI Layer#Theme, style and stylesheet (2026-10-25)]]). The Style format below comes from the maintainer's Label example; Theme and Stylesheet are proposed in [[Style Schema]].

All three are shell files: each starts with a metadata block whose file-type key is `Style:`, `Theme:` or `Stylesheet:` ([[TDL Language#The Metadata Block]]). Their suffixes are `_Style.tdl`, `_Theme.tdl` and `_Stylesheet.tdl`, the same suffixes as Tesserae's, with the extension `.tdl` ([[ADR-0014 Shell File Language]]); the metadata block and the file-type key tell them apart from a Tesserae file, and the key is authoritative over the suffix ([[ADR-0014 Shell File Language#Layout Rules]], item 16).

## Style File

```
---
TDL: 0.1
Style: v1
---

Classes {
    text_style {
        Kind: Text            # the type the class applies to; see Classes below
        Size: 16
        Weight: 500
        Foreground: "#ffffff"
    }
}

Icon {
    Foreground: "#ffffff"
    Fill: "#00000000"
}

FlexBox {
    Background: "#000000"
    Border: true
    Border_Thickness: 2
    Border_Color: "#ffffff"
    Corner_Radius: 8
}

Text {
    Font_Family: ["Hack Nerd Font Mono", "JetBrains Mono"]
}
```

| Key                                                   | Meaning                                                                                                                            | Status                                  |
|-------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------|
| `Classes`                                             | Named groups of values a widget picks up with `Class:`                                                                             | Decided (the form)                      |
| A widget name as a block (`Icon { }`, `FlexBox { }`, `Text { }`) | Defaults for every widget of that type in the file that uses this style                                                            | Decided (the form)                      |
| Property names                                        | `Size`, `Weight`, `Foreground`, `Fill`, `Background`, `Border`, `Border_Thickness`, `Border_Color`, `Corner_Radius`, `Font_Family` | From the example; the full list is open |

- **Colour** forms: the quoted hex `"#RRGGBB"` and `"#RRGGBBAA"`, and `rgba(r g b a)` with spaces, red, green and blue 0 to 255 and alpha 0.0 to 1.0 ([[ADR-0014 Shell File Language#What TDL Is (Decided)]]; the list in [[Common Keys and Conventions#Value forms]] may still show the older spelling).
- **Four-sided** values: a number, a list of four clockwise from the top, or named sides. The example's `{2, 2, 2, 2}` becomes `2` or `[2, 2, 2, 2]`; `Corner_Radius: {8, 8, 8, 8}` becomes `8` or `[8, 8, 8, 8]` (top-left, top-right, bottom-right, bottom-left, clockwise from top-left).
- **Lists:** `Font_Family: ["Hack Nerd Font Mono", "JetBrains Mono"]`, an ordered fallback list (the example's braces become square brackets).
- The same values may be written inline under `Style:` in a module or surface.
- `Border: true` assumes a boolean spelling that is not defined yet ([[TDL Language#Open]]).

### Classes

- A widget picks a class with `Class: text_style`.
- `Kind: Text` inside a class names the type it applies to. This is the one meaning of `Kind:`, a reference to a type by its exact name ([[TDL Language#Names and the Registry]], [[ADR-0014 Shell File Language#Layout Rules]] item 11). The earlier recommendation `block: Text` is gone, because there is no `Block:` key.
- A class name (`text_style`) is the block head here, though a head is normally a registered type. Whether a class is written that way or another way is open.
- Whether a class applies only to the widget type named, or to any widget that picks it, is open.

## Theme File (Not yet Designed)

A theme holds design tokens: colour roles, type scale, shape (radii), motion (durations, easing), spacing. Styles and stylesheets refer to tokens by name instead of repeating values, which is how light and dark, high contrast and reduced motion are followed from the desktop ([[Goals and Non-Goals]] G7). The token set and file shape belong to `50 Design System/`; this reference records only the file's metadata block (`Theme:`).

```
---
TDL: 0.1
Theme: v1
Name: dark
---
# token groups: colour, type, shape, motion, spacing -- not designed
```

`Name: dark` is an assumption: ADR-0014 gives `Name:` in the metadata only to a module. Other metadata keys are kept and ignored, so it does no harm; whether a theme has a name is open ([[Style Schema#Theme Tokens]] shows the proposed token shape).

## Stylesheet File (Not yet Designed)

A stylesheet holds shared rules that apply across the shell by widget type or class, so a shell author can restyle every `Text` or every `.warning` (the class selector form is open, [[Style Schema#Stylesheet Selectors]]) in one place.

```
---
TDL: 0.1
Stylesheet: v1
---
# rules by widget type or class -- not designed
```

## Rules

Decided by the maintainer on 2026-10-26 ([[ADR-0007 Shell UI Layer#Blocks, modules and styling (2026-10-26)]]).

- Styling applies to building blocks and to everything else that can be styled (surfaces, modules). The forms are `<Name>_Theme.tdl`, `<Name>_Stylesheet.tdl`, `<Name>_Style.tdl` and inline `Style:`.
- Customising a block is referencing another stylesheet or style, or writing inline `Style:`. A custom style is not a full replacement; it changes only what it names.
- **Priority**, lowest to highest: theme, then stylesheet, then style, then inline `Style:`. It applies to all styling.
- **Imports go downwards:**

| File            | May import                                       | May not import                                      |
|-----------------|--------------------------------------------------|-----------------------------------------------------|
| Theme           | Stylesheets, styles; or use inline styling       | n/a                                                 |
| Stylesheet      | Styles; or use inline styling                    | A theme                                             |
| Style           | Nothing beneath it; inline values only           | A theme or a stylesheet (proposed, to avoid cycles) |
| Inline `Style:` | A theme, a stylesheet, a style; or inline values | n/a                                                 |

- Priority follows the type of each file, not the path it was imported by. A stylesheet that a theme imports still outranks the theme.

Proposed (to confirm): when two files of the same type set the same property, the later import wins; a style cannot import anything; an import cycle is a load error naming the chain ([[Common Keys and Conventions#Errors]]).

The maintainer's Edge Shell notes ordered it Theme, Frame, Panel, Widget with a widget's own property winning ([[Shadows on Layer Surfaces#The maintainer's earlier work]], `Shell_Specs`); the new rule is the same idea over the file types.

## Errors Specific to These Files

- A property name the widget does not have: error with the closest names.
- A value of the wrong form (a colour that is not one of the three): error with the forms.
- A class used and not defined: error naming the file searched.
- A token that does not exist: error with the nearest names.

## Open

- [ ] The full property list per widget, and which belong in style and which on the widget.
- [x] The class key: `Kind: Text` inside the class, the one meaning of `Kind:` ([[ADR-0014 Shell File Language#Layout Rules]] item 11).
- [ ] The theme token set and file shape ([[50 Design System]], not started).
- [ ] The stylesheet rule shape (selectors by type, class, name). The class, name, state and part selectors cannot be written as TDL block names yet: see [[Style Schema#Stylesheet Selectors]].
- [x] The precedence order: theme, stylesheet, style, inline (decided).
- [ ] Whether a style file may extend another.
- [ ] Light/dark and high-contrast switching: in the theme, or in several theme files.

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Module File]] · [[Shell File]] · [[50 Design System]]
