---
title: TDL Language
aliases: [TDL Reference, Tesserae Data Language, TDL Syntax]
type: tdl-ref
status: draft
owner: phil
created: 2026-10-29
updated: 2026-11-01
tags: [tdl-ref, tdl, needs-verification]
---

# TDL Language

> [!NOTE]
> The Tesserae Data Language (TDL) is a structure-only data language. It is its own project, like TEL, and until that project has a repository this note defines it (D25 in [ADR-0014 Shell File Language > Second-Sketch Decisions (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#second-sketch-decisions-2026-10-30)). TDL has no knowledge of bars or monitors: the shell and Tesserae UI each define the blocks and keys they accept on top of it. Expressions are TEL's ([ADR-0008 Tesserae Expression Language](../30%20Decisions/ADR-0008%20Tesserae%20Expression%20Language.md)); TDL only marks where one starts. The decisions are the maintainer's (2026-10-29 and 2026-10-30); this note states them as rules and does not re-argue them.

## Two Layers

| Layer                     | Defines                                                                                                                     | Where                                                                                                   |
|---------------------------|-----------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| TDL (the language)        | The metadata block, punctuation, values, names, the root block, `Children`, `Import`, `If`, `Else`, `For`, `In`, `Key`, case rules, errors | This note                                                                                               |
| The shell's schema        | `Shell`, `Monitor`, `Bar`, `Frame`, `Panel`, `Popup`, the building blocks, modules and their keys                                  | [Shell File](Shell%20File.md), [Module File](Module%20File.md), [Building Blocks](../50%20Design%20System/Building%20Blocks.md), [Style Schema](Style%20Schema.md), [Settings File](Settings%20File.md)                |
| Tesserae UI's schema      | `View` and its blocks                                                                                                       | Not designed here                                                                                       |

## A File

A file is a metadata block, then one root block.

```
---
TDL: 0.1                # Tesserae Data Language version
TEL: 0.1                # Tesserae Expression Language version
TRE: 0.5.9              # Tesserae Rendering Engine version
Shell: 0.1              # Tesserae Shell version (a shell app)
Name: Shell_Root        # Unique name of this file's root
UID: <UUIDv7>           # Written by the shell
---

# This is a comment

Shell {
  Monitor {
    Name: Main
    Connector: DP-1
    Children {
      Import: TopBar_Module.tdl
      Bar {
        Name: Top_Bar
        Edge: TOP
        Width: EXPAND
        Height: 32
        Style {
          Border { Color: "#1e1e1e", Thickness: [2, 2, 2, 2] }
          Background: "#1f1f1f"
          Corner_Radius: [8, 8, 8, 8]
        }
        Children {
          Label { text: Battery {{ battery.percent }}% }
        }
      }
    }
  }
}
```

This is an illustration: the version values are made up, and the keys inside `Bar` follow the notes linked under "Where the Keys Are". The version fields are minimum versions (D37); which are required depends on what the file builds (see "The Metadata Block").

## The Metadata Block

| Rule                                                                                                                                                                                          | Source             |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------|
| Every file starts with a block between two lines that hold only `---`. The block is required.                                                                                                | ADR-0014 item 1    |
| `TDL:` is the language version. Required. Versions are strings, never numbers.                                                                                                               | Items 1 and 3      |
| `TEL:`, `TRE:`, `TUIF:` and `Shell:` are minimum versions of the other projects (`Shell:` is the Tesserae Shell release). A shell requires `TEL`, `TRE` and `Shell`; a Tesserae app requires `TEL`, `TRE` and `TUIF`. A shell adds `TUIF` to use something from an app, and an app adds `Shell` to use something from the shell (D37, D38). | Second sketch      |
| There is no file-type key. The root block names the file type (see below).                                                                                                                   | D26                |
| `Name:` is required in every file (D39). It is the unique name of the file's root (`RootShell`, a module's call name) and the root of a dotted path, so the parser and TEL reach elements of the file by name: `RootShell.DP1.Top_Bar`. It follows the name rules below.                                                                         | Second sketch, D28 |
| `UID:` is written here by the shell when the file is first registered; authors do not write it. It goes directly after the last version field.                                               | D10                |
| Other keys are allowed. The shell keeps them and ignores them, so a user can add their own metadata and read it from `<Name>_Module.py`.                                                     | Item 14            |

## The Root Block

| Root block   | File                                              | Suffix                     |
|--------------|---------------------------------------------------|----------------------------|
| `Shell`      | A shell: `Monitor` blocks                         | `<Name>_Shell.tdl`         |
| `View`       | A Tesserae app (not designed here)                | `<Name>_View.tdl`          |
| `Module`     | A module: params, layout                          | `<Name>_Module.tdl`        |
| `Style`      | A style file                                      | `<Name>_Style.tdl`         |
| `Stylesheet` | A stylesheet                                      | `<Name>_Stylesheet.tdl`    |
| `Theme`      | A theme                                           | `<Name>_Theme.tdl`         |

The root block is authoritative. A mismatch with the suffix is a load error that names both. A file has exactly one root block. The settings file `settings.tdl` has the root block `Settings` (D20 of the 2026-10-30 decisions, with the file-type key replaced by the root block).

## Punctuation

| Mark                  | Meaning                                                                                                                              |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| `---`                 | Opens and closes the metadata block                                                                                                  |
| `#`                   | Starts a comment when it follows whitespace or starts a line; the comment runs to the end of the line                                |
| `Name { ... }`        | A block. The word before the brace is the block's type (see "Names and the Registry")                                                |
| `Key: value`          | A property                                                                                                                           |
| `[a, b]`              | A list of values. A group of `Key: value` pairs is a block, never a list (D31)                                                       |
| newline or `,`        | Separates entries. A trailing `,` is allowed and never required                                                                      |
| `"..."` or `'...'`    | A string, with `\` character escapes                                                                                                 |
| `rgba(0 0 0 0.5)`     | The colour constructor; values are separated by spaces                                                                               |
| `{{ ... }}`           | An expression slot on one line, no quotes needed. TEL evaluates it                                                                   |

Rules that follow from these:

- A `#` after whitespace begins a comment and ends an unquoted value, so `TDL: 0.1   # note` is the value `0.1` and a comment. A `#` inside quotes is part of the string. `Color: "#ffffff"` is a colour; `Color: #fff` is an error that says to quote it (D36).
- Spaces around `{` and after `:` are optional. A syntax word is special only where a key or keyword is expected (D1).
- Nested blocks close with a space or a newline between the braces: `} }`, never `}}`. `{{` always opens a slot, so a block directly inside a block is written `{ {`.
- An unquoted word is a string. An unquoted value runs to the end of the line, the next `,`, a closing brace or a comment; text that holds `,` or a brace is quoted.
- A hex colour is quoted, because `#` starts a comment: `"#ffffff10"`, `"#ffffff"`.
- **Where a slot ends (D54).** A slot starts at `{{` and ends at the first `}}` that is not inside a quoted string (single or double quotes, with `\` escapes). A `}}` meant for the expression is written `} }`, the same habit as closing nested blocks. The parser gives TEL only the inner text and the position where it starts. Everything between `{{` and the slot end is opaque to TDL: a `,`, `#`, `:` or single brace inside a slot does not end an unquoted value or start a comment, so `Text: {{ max(a, b) }}` and `Color: {{ hovered ? "#1e1e2e" : "#313244" }}` are one value each.
- A block may be written on one line (`Params { format { Type: string } }`) and may be empty (`Spacer { }`) (D8).
- A key starts with a letter. There are no numeric keys: scales use names such as `Level_1` and `Step_1`. A list holds values, not blocks: repeat a named block instead (`Shadows { Shadow { } Shadow { } }`) (D4).
- A property key may appear once in a block. A repeat is an error naming both places (D9). Repeated block names are allowed.

## Values

| Kind          | Forms                                                                                                                                     |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| Length        | A whole number is pixels (`16`). A percentage is `<int>%` (`50%`). The keywords `AUTO` and `EXPAND` apply where a key allows them (D34). There is no unit suffix; a float is never a length |
| Number        | A float is for values that are not lengths (`Opacity: 0.9`)                                                                               |
| Colour        | `"#RRGGBB"`, `"#RRGGBBAA"`, or `rgba(r g b a)` with red, green and blue 0 to 255 and alpha 0.0 to 1.0                                      |
| String        | An unquoted word, or `"..."` / `'...'`                                                                                                    |
| Enum          | A full upper-case bare word: `LEFT`, `TOP`, `RIGHT`, `BOTTOM`, `OVERLAY`, `HORIZONTAL` (D33)                                              |
| Boolean, null | `true`, `false` and `null` are lowercase bare words. The parser keeps them as strings; the key's declared type in the schema makes them a boolean or null (D2) |
| Four-sided    | One number, a list of four in the order left, top, right, bottom, or a block of named sides: `Thickness { Left: 24, Top: 8 }` (D7, D50). Four corner radii run from the top-left corner clockwise                     |
| List          | `[a, b, c]` or `[]`; an item may sit on its own line                                                                                      |
| Expression    | `{{ ... }}`. A value that is exactly one slot keeps its type; text with a slot inside is a string                                         |

A percentage plus pixels (tre's `calc(100% - 16)`) has no form in v1 (D6). A style token such as `$color.on_surface` is a plain string that the style engine resolves by theme key; it is not a variable, and matching ignores case (D16).

## Names and the Registry

- **Case.** Built-in syntax is Capitalised. A key of several words Capitalises each word and joins them with `_`: `Name`, `Children`, `Exclusive_Zone`, `Corner_Radius`, `Anchor_To`. There is one spelling per key (D32). Tre's names stay lowercase (`exclusive_zone`); the shell maps between them. Enum values are full upper case.
- **Unique names.** A `Name:` is unique across the shell. It uses letters, digits and `_` only, and starts with a letter, so `DP-1` is not a name. A dotted path of names (`Shell_Root.Main.Top_Bar`) is then valid in TDL and in a TEL expression (D28).
- **A block's head is its type.** `Panel { Name: Unique_Panel_Name }` needs no `Kind:` or `Type:`. `Name:` is the unique name.
- **One registry of names** holds the built-in blocks, the surface types and every module. They are treated the same way. The shell's built-in names:

  | Group     | Names                                                                                                              |
  |-----------|--------------------------------------------------------------------------------------------------------------------|
  | Top level | Shell, Monitor                                                                                                     |
  | Surfaces  | Bar, Frame, Panel, Popup ([Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md))                                                                       |
  | Blocks    | Box, FlexBox, Grid, Text, TextField, Bitmap, SVG, Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path, Terminal, Canvas ([Building Blocks](../50%20Design%20System/Building%20Blocks.md)) |
  | Modules   | The shipped modules (Label, Icon, Button, ... , [V1 Widgets](../50%20Design%20System/V1%20Widgets.md)) and every module with a `Name:` in its metadata   |

- **Kind has one meaning.** `Kind:` references a type by its exact name (`Kind: Panel`, `Kind: Clock`), where a type is named by value rather than by a block head, such as a style class.
- A name registered twice is a load error. A user module of the same name overrides a shipped module ([ADR-0007 Shell UI Layer > Module Call, Shipped Modules and Path (2026-10-26)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#module-call-shipped-modules-and-path-2026-10-26)).
- **Repeats.** The same block or module name may appear many times in one `Children { }`. Entries are ordered by position and named from it (`Square_1`, `Square_2`). Siblings are separated by a newline or `,`.
- **For entries.** The entries of a `For`: TEL names each entry `<name>_0001`, `<name>_0002` and so on from a counter that only grows; a key that disappears and returns gets a new number (D65). The entry is identified by its `Key`, which may be any value; only the generated name is limited to letters, digits and `_`. The `<name>` is the `Name:` of the `For` block when it has one, else the head of its child (for example `Icon_0001`), else `For`.
- **Modules and surfaces.** A user module may hold a surface as its root: a module `Top_Bar` can hold a `Bar` and be used under several `Monitor` blocks. Surfaces do not nest inside surfaces (D29).
- **Instances.** Python keys each use by the module name and the UID, `Clock@<uid>`. The shell writes `UID:` into a block only if it has a `Name:` and the user asks for stable identity across reordering (D30).

## Structure Words

| Word                                               | Use                                                                                                             |
|----------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `Children`                                         | The only holder of contents                                                                                     |
| `Import`                                           | One file name or a list: `Import: Applications_Module.tdl`, or `Import: [A_Module.tdl, B_Module.tdl,]`. Paths are relative to the importing file; imports nest. The spelling is `Import` (the sketch also wrote `import:`, which is open) |
| `If`, `Else`                                       | `If {{ cond }} { ... } Else { ... }`; no `Else If`; nest an `If` inside `Else`                                   |
| `For`, `In`, `Key`                                 | `For item In {{ list }} Key {{ item.id }} { ... }`. `Key` is required: it gives each entry a stable identity     |

`If`, `Else`, `For`, `In` and `Key` cannot be the name of a block or module. The rules for conditions and repeats are in [ADR-0014 Shell File Language > Conditions and Repeats (Decided)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#conditions-and-repeats-decided).

## Monitors (Shell Schema)

`Monitor { }` is a block of the shell's schema, one per monitor; several may appear under `Shell`. A `Monitor` names its monitor with one of three selectors and has its own `Name:` (D27):

| Selector       | Matches                                                                                       |
|----------------|-----------------------------------------------------------------------------------------------|
| `Index: 0`     | The position in the compositor's output array: `0` for the first (or only) monitor, then `1` |
| `Connector:`   | The connector name, for example `DP-1`                                                        |
| `Description:` | The display description                                                                       |

- `Index: default` applies to every monitor no other `Monitor` block names.
- A `Monitor` with no selector is ignored.
- If a block has several selectors, the shell tries `Connector`, then `Description`, then `Index` and uses the first match.
- `Index:` is not a stable name: the position can change after a hot-plug, a wake or a reboot. This is [Risk Register](../00%20Home/Risk%20Register.md) R-21 and why `Connector:` and `Description:` exist.

## Sizes (Shell Schema)

A `Width` or `Height` is a number of pixels, a percentage, `AUTO` or `EXPAND`. `AUTO` shrinks to wrap the content on that axis. `EXPAND` stretches edge to edge along the edge a surface is attached to; across that axis it cannot stretch, so a top Bar with `Height: EXPAND` resolves to `Max_Height`, else `Min_Height`, else 0 px. `Max_Width`, `Max_Height`, `Min_Width` and `Min_Height` bound a size (D34). A resolved size of 0 is invalid for a layer surface unless it is anchored to both opposite edges, so such a Bar is not created (D46, verified against the protocol 2026-10-31).

## Errors

Every error carries `file:line:column` from the shell's own TDL parser, which keeps a lossless tree (comments and layout survive the UID write). A TEL error inside a slot points into the file because the parser gives TEL the slot's start ([Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md), T17). The list below was accepted by the maintainer on 2026-10-30 (D52). New codes are added here as the parser is designed.

Proposed form, copied from TEL's decided errors ([Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md)): one base error class with a stable `code` slug on every error, a message, a hint that says what to write, and a 1-based `file`, `line` and `column`. Value and schema checks (unknown key, wrong type, enum case) belong to the shell's schema ([Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md)), not to TDL.

| Code                       | When                                                              | Hint                                           |
|----------------------------|-------------------------------------------------------------------|------------------------------------------------|
| `tdl-no-metadata`          | The file does not start with a `---` block                        | Start the file with `---`                      |
| `tdl-metadata-unclosed`    | The metadata block has no closing `---`                           | Close the block with `---`                     |
| `tdl-no-version`           | No `TDL:` in the metadata                                         | Add `TDL: <version>`                           |
| `tdl-no-name`              | No `Name:` in the metadata                                        | Add `Name: <identifier>`                       |
| `tdl-bad-name`             | A `Name:` with a character other than a letter, digit or `_`, or that starts with a digit | Use letters, digits and `_`            |
| `tdl-no-root`              | No root block after the metadata                                  | Add one root block, for example `Shell { }`    |
| `tdl-many-roots`           | More than one root block                                          | Keep one root block                            |
| `tdl-root-suffix`          | The root block disagrees with the file suffix                     | Rename the file or change the root block       |
| `tdl-unclosed-block`       | A `{` has no closing `}` before the end of the file               | Add the missing `}`                            |
| `tdl-unexpected-close`     | A `}` with no open block                                          | Remove the extra `}`                           |
| `tdl-double-close`         | `}}` where two blocks close                                       | Write `} }`                                    |
| `tdl-unclosed-slot`        | A `{{` with no `}}` on the same line                              | Close the slot on the same line                |
| `tdl-empty-slot`           | A `{{ }}` with nothing in it                                      | Put an expression in the slot                  |
| `tdl-unclosed-string`      | A quote with no closing quote on the line                         | Close the string                               |
| `tdl-bad-escape`           | A `\` followed by a character that is not an escape               | Use a valid escape or double the `\`           |
| `tdl-duplicate-key`        | A property key twice in one block                                 | Remove one; the message names both places      |
| `tdl-bare-hash`            | A value that starts with `#` outside quotes                       | Quote the colour: `"#ffffff"`                  |
| `tdl-reserved-name`        | A block or module named `If`, `Else`, `For`, `In` or `Key`        | Choose another name                            |

## Editor Support

No language server in v1. A small TextMate grammar ships in v1 for highlighting in Kate and VS Code. Its content comes from this note once the open items are settled ([ADR-0014 Shell File Language > What TDL Is (Decided)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#what-tdl-is-decided), item 18).

## Where the Keys Are

| Note                                      | Holds                                              |
|-------------------------------------------|----------------------------------------------------|
| [Common Keys and Conventions](Common%20Keys%20and%20Conventions.md)           | Keys every file has, value forms, names, errors    |
| [Shell File](Shell%20File.md)                            | `Monitor` and the surface keys                     |
| [Module File](Module%20File.md)                           | The module file, params, data slots                |
| [Style, Theme and Stylesheet Files](Style%2C%20Theme%20and%20Stylesheet%20Files.md)     | Style, theme and stylesheet files                  |
| [Style Schema](Style%20Schema.md)                          | Style properties                                   |
| [Settings File](Settings%20File.md)                         | `settings.tdl`                                     |

These notes were revised on 2026-10-30 to the decisions of [ADR-0014 Shell File Language > Third-Round Decisions (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#third-round-decisions-2026-10-30) and [ADR-0014 Shell File Language > Fourth-Round Decisions (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#fourth-round-decisions-2026-10-30): the root block names the file type, enum values are upper case, four-sided values run left, top, right, bottom, and the Bar uses `Edge`, `Width`, `Height`, `Gap` and `Offset`.

## Open

Decided on 2026-10-30 and removed from this list: the version pins are minimums (D37), `Name:` is required in every file (D39), the spelling is `Import` (D40), `Margin`, `Gap`, `Offset` and `Padding` meanings (D41 to D45), and `calc` is out of v1 (D47).

- [x] The names and slugs of TDL syntax errors: the list under "Errors" is accepted (D52).
- [ ] The full list of shipped modules and their registry names: after the building blocks are worked out (D48, [V1 Widgets](../50%20Design%20System/V1%20Widgets.md)).
- [ ] How a collapsed or hidden Bar keeps a layer surface: accepted in [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre) (D61): the window keeps its size and slides by a negative margin. The protocol makes a 0 size without opposite anchors an error, so D46 stands (verified 2026-10-31).
- [x] `Gap` is the distance to what a surface is attached to, and a layout's child spacing is `Spacing` (D49). The four-sided order is Left, Top, Right, Bottom (D50). A Bar's `Offset` is one number, a Panel's is four-sided (D51) ([ADR-0014 Shell File Language > Fourth-Round Decisions (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#fourth-round-decisions-2026-10-30)).

## Acceptance Criteria

- A file without a `---` block or without `TDL:` is refused with an error that names the file.
- A file with no root block, or more than one, is refused. A root block that disagrees with the suffix is a load error naming both.
- `Panel { Name: p1 }` loads with no `Kind:` or `Type:`.
- A `Name:` with a character other than a letter, digit or `_`, or one that starts with a digit, is an error that says so.
- Two `Monitor` blocks under `Shell` load; two that name the same monitor are an error naming both places.
- A name registered twice is a load error naming both; a user module of a shipped module's name overrides it.
- `Index: default` applies to a monitor no other block names.
- A metadata key the shell does not know is kept and ignored.
- `}}` where a block closes inside a block is an error that says to write `} }`.
- `Text: {{ max(a, b) }}` is one value: the `,` inside the slot does not end it.
- `{{ {'a': {'b': 1}} }}` ends the slot at the first `}}` and TEL reports the leftover text; `{{ {'a': {'b': 1} } }}` evaluates to the dict, and `{{ '}}' }}` is the string `}}` because the `}}` is inside quotes.
- A property key written twice in one block is an error naming both places.
- `Color: #fff` is an error that says to quote the colour; `Color: "#fff"   # note` is the colour `#fff` and a comment.
- `Edge: top` is an error that says enum values are upper case; `Edge: TOP` loads.
- `true`, `false` and `null` are accepted where the schema declares a boolean or null, and refused (with the expected type) where it declares a string or number.
- `Thickness { Top: 8, Left: 24 }`, `Thickness: 8` and `Thickness: [8, 8, 8, 8]` load to the same four-sided value shape.
- A top Bar with `Height: EXPAND` resolves to its `Max_Height`, else its `Min_Height`, else 0 px.

## Links

- [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) · [41 TDL Reference](41%20TDL%20Reference.md) · [Common Keys and Conventions](Common%20Keys%20and%20Conventions.md) · [Shell File Syntax Comparison](../90%20Research/Shell%20File%20Syntax%20Comparison.md) · [Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md) · [Risk Register](../00%20Home/Risk%20Register.md)
