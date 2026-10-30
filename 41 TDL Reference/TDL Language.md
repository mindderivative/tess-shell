---
title: TDL Language
aliases: [TDL Reference, Tesserae Data Language, TDL Syntax]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-29
updated: 2026-10-29
tags: [yaml-ref, tdl, needs-verification]
related: ["[[ADR-0014 Shell File Language]]", "[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Shell File]]", "[[Module File]]", "[[Shell File Syntax Comparison]]"]
depends_on: ["[[ADR-0014 Shell File Language]]"]
---

# TDL Language

> [!summary]
> The Tesserae Data Language (TDL) is the structure-only data language of every shell file. This note is the one place for its syntax, its case rules, the name registry and the file header. The decisions are in [[ADR-0014 Shell File Language]] (the maintainer's, 2026-10-29); this note states them as rules and does not re-argue them. The keys of each file type are in the notes linked at the end. Expressions are TEL's ([[ADR-0008 Tesserae Expression Language]]); TDL only marks where one starts.

## A File

A file is a metadata block, then blocks.

```
---
TDL: 0.1
Shell: v1
UID: 0190b3c2-7d4e-7a11-9a52-6c1f0b8d2e44
---

# A comment

Monitor {
    Name: main
    Index: 0
    Children {
        Bar {
            Name: top_bar
            Children {
                Label { Text: Battery {{ battery.percent }}% }
            }
        }
    }
}
```

This is an illustration. The key names inside the blocks follow the notes linked under "Where the Keys Are"; the UID value is made up.

## The Metadata Block

| Rule                                                                                                                                                                                                  | Source                                       |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| Every file starts with a block between two lines that hold only `---`. The block is required.                                                                                                         | [[ADR-0014 Shell File Language#Layout Rules]] |
| `TDL:` is the language version. Required.                                                                                                                                                             | ADR-0014, layout sketch                       |
| One file-type key is required: `Shell:`, `Module:`, `Style:`, `Stylesheet:` or `Theme:`. Its value is a version. There is no `Type:` and no separate `shell:` key.                                    | ADR-0014, Layout Rules item 2                 |
| The file name suffix (`<Name>_Shell.tdl`) agrees with the file-type key. The key is authoritative; a mismatch is a load error that names both.                                                        | ADR-0014, item 16                             |
| `UID:` is written here by the shell when the file is first registered. Authors do not write it.                                                                                                      | ADR-0014, item 1                              |
| A module file also has `Name:` here: its unique name, and the word used to call it (`Name: Clock` in `Clock_Module.tdl`; a use is written `Clock { }`).                                                | ADR-0014, item 7                              |
| Versions are strings (`v1`, `0.1`), never numbers.                                                                                                                                                    | ADR-0014, item 3                              |
| Other keys are allowed. The shell keeps them and ignores them, so a user can add their own metadata and read it from `<Name>_Module.py`. `FileName` in the sketch was an example, not a required key. | ADR-0014, items 1 and 14                      |

## Punctuation

| Mark                  | Meaning                                                                                                                              |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| `---`                 | Opens and closes the metadata block                                                                                                  |
| `#`                   | Starts a comment that runs to the end of the line                                                                                    |
| `Name { ... }`        | A block. The word before the brace is the block's type (see "Names and the Registry")                                                |
| `Key: value`          | A property                                                                                                                           |
| `[a, b]`              | A list                                                                                                                               |
| newline or `,`        | Separates entries. A trailing `,` is allowed and never required                                                                      |
| `"..."` or `'...'`    | A string, with `\` character escapes                                                                                                 |
| `rgba(0 0 0 0.5)`     | The colour constructor; values are separated by spaces                                                                               |
| `{{ ... }}`           | An expression slot on one line, no quotes needed. TEL evaluates it                                                                   |

Rules that follow from these:

- Spaces around `{` and after `:` are optional (the maintainer's example wrote `children{ key:value }`; to confirm, [[ADR-0014 Shell File Language#Open Items]]).
- Nested blocks close with a space or a newline between the braces: `} }`, never `}}`. `{{` always opens a slot, so a block directly inside a block is written `{ {`.
- An unquoted word is a string. An unquoted value runs to the end of the line or to the next `,` or closing brace; text that holds either is quoted.
- A hex colour is quoted, because `#` starts a comment: `"#ffffff10"`, `"#ffffff"`.

## Values

| Kind        | Forms                                                                                                                             |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------|
| Length      | A whole number is pixels (`16`). A percentage is `<int>%` (`50%`). There is no unit suffix; a float is never a length             |
| Number      | A float is for values that are not lengths (`Opacity: 0.9`)                                                                        |
| Colour      | `"#RRGGBB"`, `"#RRGGBBAA"`, or `rgba(r g b a)` with red, green and blue 0 to 255 and alpha 0.0 to 1.0                              |
| String      | An unquoted word, or `"..."` / `'...'`                                                                                             |
| List        | `[a, b, c]`; an item may sit on its own line                                                                                       |
| Enum        | A lowercase bare word (`Layer: overlay`, `Keyboard: exclusive`)                                                                    |
| Expression  | `{{ ... }}`. A value that is exactly one slot keeps its type; text with a slot inside is a string                                  |

Not yet defined, and listed under "Open": booleans, null, an empty list, a percentage plus pixels.

## Names and the Registry

- **Case.** Built-in syntax is Capitalised. A key of several words Capitalises each word and joins them with `_`: `Name`, `Children`, `Exclusive_Zone`, `Border_Thickness`, `Anchor_To`. Tre's names stay lowercase (`exclusive_zone`); the shell maps between them.
- **A block's head is its type.** `Panel { Name: Unique_Panel_Name }` needs no `Kind:` or `Type:`. `Name:` is the unique name, unique across the shell.
- **One registry of names** holds the built-in blocks, the surface types and every module. They are treated the same way. Built-in names:

  | Group     | Names                                                                                                              |
  |-----------|--------------------------------------------------------------------------------------------------------------------|
  | Top level | Monitor                                                                                                            |
  | Surfaces  | Bar, Frame, Panel, Popup ([[Surface Types]])                                                                       |
  | Blocks    | Box, FlexBox, Grid, Text, TextField, Bitmap, SVG, Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path, Terminal, Canvas ([[Building Blocks]]) |
  | Modules   | The shipped modules (Label, Icon, Button, ... , [[V1 Widgets]]) and every module with a `Name:` in its metadata   |

- **Kind has one meaning.** `Kind:` references a type by its exact name (`Kind: Panel`, `Kind: Clock`), where a type is named by value rather than by a block head, such as a style class. There is no `Kind: Block` or `Kind: Module`.
- A name registered twice is a load error. A user module of the same name overrides a shipped module ([[ADR-0007 Shell UI Layer#Module Call, Shipped Modules and Path (2026-10-26)]]).
- **Repeats.** The same block or module name may appear many times in one `Children { }`. Entries are ordered by position and named from it (`Square_1`, `Square_2`). Siblings are separated by a newline or `,`.
- **Instances.** Python keys each use by the module name and the UID, `Clock@<uid>`. The shell writes `UID:` into a use in a file only when the user asks for stable identity across reordering.

## Structure Words

| Word                                               | Use                                                                                                             |
|----------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `Children`                                         | The only holder of contents                                                                                     |
| `Import`                                           | One file name or a list: `Import: Applications_Module.tdl`, or `Import: [A_Module.tdl, B_Module.tdl,]`. Paths are relative to the importing file; imports nest |
| `If`, `Else`                                       | `If {{ cond }} { ... } Else { ... }`; no `Else If`; nest an `If` inside `Else`                                   |
| `For`, `In`, `Key`                                 | `For item In {{ list }} Key {{ item.id }} { ... }`. `Key` is required: it gives each entry a stable identity     |

`If`, `Else`, `For`, `In` and `Key` cannot be the name of a block or module. The rules for conditions and repeats are in [[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]]. The Capitalised spelling is the maintainer's (2026-10-29); the lowercase spelling in ADR-0014's example is the earlier form.

## Monitors

`Monitor { }` is a top-level block, one per monitor, and several may appear in one file. A `Monitor` names its monitor with one of three selectors:

| Selector       | Matches                                                                                       |
|----------------|-----------------------------------------------------------------------------------------------|
| `Index: 0`     | The position in the compositor's output array: `0` for the first (or only) monitor, then `1` |
| `Connector:`   | The connector name, for example `DP-1`                                                        |
| `Description:` | The display description                                                                       |

- `Index: default` applies to every monitor no other `Monitor` block names.
- A `Monitor` with no selector is ignored.
- If a block has several selectors, the shell tries `Connector`, then `Description`, then `Index` (proposed; the maintainer did not state an order).
- `Index:` is not a stable name: the position can change after a hot-plug, a wake or a reboot. This is [[Risk Register]] R-21 and why `Connector:` and `Description:` exist.

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
| [[Settings File]]                         | `settings.tdl` (assumed name, to confirm)          |

## Open

- [ ] Boolean and null spellings (`true`, `false`), and an empty list `[]`.
- [ ] A form for a percentage plus pixels (tre's `calc(100% - 16)`).
- [ ] Unnamed blocks as list items, numeric keys and stylesheet selectors (`.warning`, `#clock_label`, `Button:hovered`), which the block syntax does not cover ([[ADR-0014 Shell File Language#Open Items]]).
- [ ] The order of several monitor selectors on one block.
- [ ] Whether spaces around `{` and after `:` are optional.
- [ ] A repeated property key in one block: an error, or last wins.
- [ ] The names and slugs of TDL syntax errors.
- [ ] The key name for a use's own name: the head word is the type, and `Name:` is the unique name; how a repeated use names itself in the file is the position rule above.

## Acceptance Criteria

- A file without a `---` block, without `TDL:`, or without exactly one file-type key is refused with an error that names the file.
- A file-type key that disagrees with the suffix is a load error naming both.
- `Panel { Name: p1 }` loads with no `Kind:` or `Type:`.
- Two `Monitor` blocks in one file load; two that name the same monitor are an error naming both places.
- A name registered twice is a load error naming both; a user module of a shipped module's name overrides it.
- `Index: default` applies to a monitor no other block names.
- A metadata key the shell does not know is kept and ignored.
- `}}` where a block closes inside a block is an error that says to write `} }`.

## Links

- [[ADR-0014 Shell File Language]] · [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Shell File Syntax Comparison]] · [[Expression Language Requirements]] · [[Risk Register]]
