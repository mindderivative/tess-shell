---
title: Style, Theme and Stylesheet Files
aliases: [_Style.tdl, _Theme.tdl, _Stylesheet.tdl, _Style.yaml, _Theme.yaml, _Stylesheet.yaml, Style Files]
type: tdl-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [tdl-ref, design, needs-verification]
---

# Style, Theme and Stylesheet Files

> [!NOTE]
> Three files control how things look. A **style** file holds the values for one surface or module, like its inline `Style:` key. A **stylesheet** holds shared rules that apply across the shell by widget type or class. A **theme** holds design tokens (colour, type, shape, motion) that the others refer to. The split is the maintainer's ([ADR-0007 Shell UI Layer > Theme, style and stylesheet (2026-10-25)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#theme-style-and-stylesheet-2026-10-25)). The Style format below comes from the maintainer's Label example; Theme and Stylesheet are proposed in [Style Schema](Style%20Schema.md).

All three are shell files: each starts with a metadata block (`TDL:` and a required `Name:`, [TDL Language > The Metadata Block](TDL%20Language.md#the-metadata-block)) and holds one root block: `Style { }`, `Theme { }` or `Stylesheet { }` ([TDL Language > The Root Block](TDL%20Language.md#the-root-block)). Their suffixes are `_Style.tdl`, `_Theme.tdl` and `_Stylesheet.tdl`, the same suffixes as Tesserae's, with the extension `.tdl` ([ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)). The root block is authoritative; a mismatch with the suffix is a load error naming both.

## Style File

```
---
TDL: 0.1
Name: Label_Style
---

Style {
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
}
```

| Key                                                   | Meaning                                                                                                                            | Status                                  |
|-------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------|
| `Classes`                                             | Named groups of values a widget picks up with `Class:`                                                                             | Decided (the form)                      |
| A widget name as a block (`Icon { }`, `FlexBox { }`, `Text { }`) | Defaults for every widget of that type in the file that uses this style                                                            | Decided (the form)                      |
| Property names                                        | `Size`, `Weight`, `Foreground`, `Fill`, `Background`, `Border`, `Border_Thickness`, `Border_Color`, `Corner_Radius`, `Font_Family` | From the example; the full list is open |

- **Colour** forms: the quoted hex `"#RRGGBB"` and `"#RRGGBBAA"`, and `rgba(r g b a)` with spaces, red, green and blue 0 to 255 and alpha 0.0 to 1.0 ([ADR-0014 Shell File Language > What TDL Is (Decided)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#what-tdl-is-decided); the list in [Common Keys and Conventions > Value forms](Common%20Keys%20and%20Conventions.md#value-forms) uses the same spelling).
- **Four-sided** values: a number, a list of four in the order left, top, right, bottom (D50), or a block of named sides such as `Margin { Top: 8, Left: 24 }` (D7, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)). `Padding` is transparent space inside an element that has `Children`; `Margin` is transparent space around the element ([Style Schema > Style Keys](Style%20Schema.md#style-keys)). The example's `{2, 2, 2, 2}` becomes `2` or `[2, 2, 2, 2]`; `Corner_Radius: {8, 8, 8, 8}` becomes `8` or `[8, 8, 8, 8]` (top-left, top-right, bottom-right, bottom-left, clockwise from top-left).
- **Lists:** `Font_Family: ["Hack Nerd Font Mono", "JetBrains Mono"]`, an ordered fallback list (the example's braces become square brackets).
- The same values may be written inline under `Style:` in a module or surface.
- `Border: true` is a bare word that the key's schema type reads as a boolean (D2, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).

### Classes

- A widget picks a class with `Class: text_style`.
- `Kind: Text` inside a class names the type it applies to. This is the one meaning of `Kind:`, a reference to a type by its exact name ([TDL Language > Names and the Registry](TDL%20Language.md#names-and-the-registry), [ADR-0014 Shell File Language > Layout Rules](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#layout-rules) item 11). The earlier recommendation `block: Text` is gone, because there is no `Block:` key.
- A class is a block named by the user inside `Classes { }`, and `Kind: Text` names the type it applies to (D19, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)). The user's class name is not a registered type; it is a name, as `Name:` values are.
- A class applies to the type its `Kind:` names.

## Theme File (Not yet Designed)

A theme holds design tokens: colour roles, type scale, shape (radii), motion (durations, easing), spacing. Styles and stylesheets refer to tokens by name instead of repeating values, which is how light and dark, high contrast and reduced motion are followed from the desktop ([Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) G7). The token set and file shape belong to `50 Design System/`; this reference records only the file's metadata block and root block (`Theme { }`).

```
---
TDL: 0.1
Name: Dark
---

Theme {
    # token groups: colour, type, shape, motion, spacing -- not designed
}
```

`Name:` is required in the metadata, as in every file (D39); unknown metadata is kept (D19, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)). [Style Schema > Theme Tokens](Style%20Schema.md#theme-tokens) shows the proposed token shape.

## Stylesheet File (Not yet Designed)

A stylesheet holds shared rules that apply across the shell by widget type or class, so a shell author can restyle every `Text` or every `.warning` in one place. A rule is a `Rule { Selector: ".warning", ... }` block inside the root `Stylesheet { }`, repeated as needed, and the selector is a quoted string (D5, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30); the forms are in [Style Schema > Stylesheet Selectors](Style%20Schema.md#stylesheet-selectors)).

```
---
TDL: 0.1
Name: Base_Stylesheet
---

Stylesheet {
    # Rule blocks (Selector plus style values) -- see Style Schema
}
```

## Rules

Decided by the maintainer on 2026-10-26 ([ADR-0007 Shell UI Layer > Blocks, modules and styling (2026-10-26)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#blocks-modules-and-styling-2026-10-26)).

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

Proposed (to confirm): when two files of the same type set the same property, the later import wins; a style cannot import anything; an import cycle is a load error naming the chain ([Common Keys and Conventions > Errors](Common%20Keys%20and%20Conventions.md#errors)).

The maintainer's Edge Shell notes ordered it Theme, Frame, Panel, Widget with a widget's own property winning ([Shadows on Layer Surfaces > The maintainer's earlier work](../90%20Research/Shadows%20on%20Layer%20Surfaces.md#the-maintainers-earlier-work), `Shell_Specs`); the new rule is the same idea over the file types.

## Errors Specific to These Files

- A property name the widget does not have: error with the closest names.
- A value of the wrong form (a colour that is not one of the three): error with the forms.
- A class used and not defined: error naming the file searched.
- A token that does not exist: error with the nearest names.

## Open

- [ ] The full property list per widget, and which belong in style and which on the widget.
- [x] The class key: `Kind: Text` inside the class, the one meaning of `Kind:` ([ADR-0014 Shell File Language > Layout Rules](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#layout-rules) item 11).
- [ ] The theme token set and file shape: proposed in [Style Schema > Theme Tokens](Style%20Schema.md#theme-tokens); the values belong to [50 Design System](../50%20Design%20System/50%20Design%20System.md) (not started).
- [x] The stylesheet rule shape: `Rule { Selector: "...", ... }` blocks, the selector a quoted string (D5; [Style Schema > Stylesheet Selectors](Style%20Schema.md#stylesheet-selectors)).
- [x] The precedence order: theme, stylesheet, style, inline (decided).
- [ ] Whether a style file may extend another.
- [ ] Light/dark and high-contrast switching: in the theme, or in several theme files.

## Links

- [41 TDL Reference](41%20TDL%20Reference.md) · [Common Keys and Conventions](Common%20Keys%20and%20Conventions.md) · [Module File](Module%20File.md) · [Shell File](Shell%20File.md) · [50 Design System](../50%20Design%20System/50%20Design%20System.md)
