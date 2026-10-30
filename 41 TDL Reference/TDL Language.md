---
title: TDL Language
aliases: [TDL Reference, Tesserae Data Language, TDL Syntax]
type: tdl-ref
status: draft
owner: phil
created: 2026-10-29
updated: 2026-10-30
tags: [tdl-ref, tdl, needs-verification]
related: ["[[ADR-0014 Shell File Language]]", "[[41 TDL Reference]]", "[[Common Keys and Conventions]]", "[[Shell File]]", "[[Module File]]", "[[Shell File Syntax Comparison]]"]
depends_on: ["[[ADR-0014 Shell File Language]]"]
---

# TDL Language

> [!summary]
> The Tesserae Data Language (TDL) is a structure-only data language. It is its own project, like TEL, and until that project has a repository this note defines it (D25 in [[ADR-0014 Shell File Language#Second-Sketch Decisions (2026-10-30)]]). TDL has no knowledge of bars or monitors: the shell and Tesserae UI each define the blocks and keys they accept on top of it. Expressions are TEL's ([[ADR-0008 Tesserae Expression Language]]); TDL only marks where one starts. The decisions are the maintainer's (2026-10-29 and 2026-10-30); this note states them as rules and does not re-argue them.

## Two Layers

| Layer                     | Defines                                                                                                                     | Where                                                                                                   |
|---------------------------|-----------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| TDL (the language)        | The metadata block, punctuation, values, names, the root block, `Children`, `Import`, `If`, `Else`, `For`, `In`, `Key`, case rules, errors | This note                                                                                               |
| The shell's schema        | `Shell`, `Monitor`, `Bar`, `Frame`, `Panel`, `Popup`, the building blocks, modules and their keys                                  | [[Shell File]], [[Module File]], [[Building Blocks]], [[Style Schema]], [[Settings File]]                |
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

This is an illustration: the version values are made up, and the keys inside `Bar` follow the notes linked under "Where the Keys Are". The version fields are the maintainer's sketch; whether each is required is open.

## The Metadata Block

| Rule                                                                                                                                                                                          | Source             |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------|
| Every file starts with a block between two lines that hold only `---`. The block is required.                                                                                                | ADR-0014 item 1    |
| `TDL:` is the language version. Required. Versions are strings, never numbers.                                                                                                               | Items 1 and 3      |
| `TEL:`, `TRE:`, `TUIF:` and `Shell:` say which versions of the other projects the file was written for (`TUIF` for a Tesserae app, `Shell` for a shell). Whether each is a minimum or an exact version, and which are required per file, is open. | Second sketch      |
| There is no file-type key. The root block names the file type (see below).                                                                                                                   | D26                |
| `Name:` is the unique name of the file's root (`Shell_Root`, a module's call name). It follows the name rules below.                                                                         | Second sketch, D28 |
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
| Four-sided    | One number, a list of four (top, right, bottom, left), or a block of named sides: `Thickness { Top: 8, Left: 24 }` (D7)                     |
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
  | Surfaces  | Bar, Frame, Panel, Popup ([[Surface Types]])                                                                       |
  | Blocks    | Box, FlexBox, Grid, Text, TextField, Bitmap, SVG, Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path, Terminal, Canvas ([[Building Blocks]]) |
  | Modules   | The shipped modules (Label, Icon, Button, ... , [[V1 Widgets]]) and every module with a `Name:` in its metadata   |

- **Kind has one meaning.** `Kind:` references a type by its exact name (`Kind: Panel`, `Kind: Clock`), where a type is named by value rather than by a block head, such as a style class.
- A name registered twice is a load error. A user module of the same name overrides a shipped module ([[ADR-0007 Shell UI Layer#Module Call, Shipped Modules and Path (2026-10-26)]]).
- **Repeats.** The same block or module name may appear many times in one `Children { }`. Entries are ordered by position and named from it (`Square_1`, `Square_2`). Siblings are separated by a newline or `,`.
- **Modules and surfaces.** A user module may hold a surface as its root: a module `Top_Bar` can hold a `Bar` and be used under several `Monitor` blocks. Surfaces do not nest inside surfaces (D29).
- **Instances.** Python keys each use by the module name and the UID, `Clock@<uid>`. The shell writes `UID:` into a block only if it has a `Name:` and the user asks for stable identity across reordering (D30).

## Structure Words

| Word                                               | Use                                                                                                             |
|----------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `Children`                                         | The only holder of contents                                                                                     |
| `Import`                                           | One file name or a list: `Import: Applications_Module.tdl`, or `Import: [A_Module.tdl, B_Module.tdl,]`. Paths are relative to the importing file; imports nest. The spelling is `Import` (the sketch also wrote `import:`, which is open) |
| `If`, `Else`                                       | `If {{ cond }} { ... } Else { ... }`; no `Else If`; nest an `If` inside `Else`                                   |
| `For`, `In`, `Key`                                 | `For item In {{ list }} Key {{ item.id }} { ... }`. `Key` is required: it gives each entry a stable identity     |

`If`, `Else`, `For`, `In` and `Key` cannot be the name of a block or module. The rules for conditions and repeats are in [[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]].

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
- `Index:` is not a stable name: the position can change after a hot-plug, a wake or a reboot. This is [[Risk Register]] R-21 and why `Connector:` and `Description:` exist.

## Sizes (Shell Schema)

A `Width` or `Height` is a number of pixels, a percentage, `AUTO` or `EXPAND`. `AUTO` shrinks to wrap the content on that axis. `EXPAND` stretches edge to edge along the edge a surface is attached to; across that axis it cannot stretch, so a top Bar with `Height: EXPAND` resolves to `Max_Height`, else `Min_Height`, else 0 px. `Max_Width`, `Max_Height`, `Min_Width` and `Min_Height` bound a size (D34). A resolved size of 0 may be invalid for a layer surface (see the danger callout in [[ADR-0014 Shell File Language#Second-Sketch Decisions (2026-10-30)]]).

## Errors

Every error carries `file:line:column` from the shell's own TDL parser, which keeps a lossless tree (comments and layout survive the UID write). A TEL error inside a slot points into the file because the parser gives TEL the slot's start ([[Expression Language Requirements]], T17). The error list for TDL syntax is not written (see Open).

## Editor Support

No language server in v1. A small TextMate grammar ships in v1 for highlighting in Kate and VS Code. Its content comes from this note once the open items are settled ([[ADR-0014 Shell File Language#What TDL Is (Decided)]], item 18).

## Where the Keys Are

| Note                                      | Holds                                              |
|-------------------------------------------|----------------------------------------------------|
| [[Common Keys and Conventions]]           | Keys every file has, value forms, names, errors    |
| [[Shell File]]                            | `Monitor` and the surface keys                     |
| [[Module File]]                           | The module file, params, data slots                |
| [[Style, Theme and Stylesheet Files]]     | Style, theme and stylesheet files                  |
| [[Style Schema]]                          | Style properties                                   |
| [[Settings File]]                         | `settings.tdl`                                     |

These notes still show the layout of 2026-10-29 (a file-type key in the metadata block, lowercase enum values, `Span` and `Thickness` for a Bar). They are revised after the maintainer confirms the open items below.

## Open

- [ ] Whether `TEL:`, `TRE:`, `TUIF:` and `Shell:` are minimum or exact versions, and which are required for which file type.
- [ ] Whether `Name:` is required in the metadata of every file, or only for a module.
- [ ] The spelling `Import` against `import:`.
- [ ] `Margin` (outside the block) against the Bar's edge offset, and `Padding` (inside the block).
- [ ] The names and slugs of TDL syntax errors.
- [ ] A form for tre's `calc(100% - 16)`, when a surface needs it (D6).
- [ ] The full list of shipped modules and their registry names ([[V1 Widgets]]).
- [ ] A resolved size of 0 on a layer surface (#needs-verification against the layer-shell protocol).

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
- A property key written twice in one block is an error naming both places.
- `Color: #fff` is an error that says to quote the colour; `Color: "#fff"   # note` is the colour `#fff` and a comment.
- `Edge: top` is an error that says enum values are upper case; `Edge: TOP` loads.
- `true`, `false` and `null` are accepted where the schema declares a boolean or null, and refused (with the expected type) where it declares a string or number.
- `Thickness { Top: 8, Left: 24 }`, `Thickness: 8` and `Thickness: [8, 8, 8, 8]` load to the same four-sided value shape.
- A top Bar with `Height: EXPAND` resolves to its `Max_Height`, else its `Min_Height`, else 0 px.

## Links

- [[ADR-0014 Shell File Language]] · [[41 TDL Reference]] · [[Common Keys and Conventions]] · [[Shell File Syntax Comparison]] · [[Expression Language Requirements]] · [[Risk Register]]
